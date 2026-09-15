"""WP1: accepted inputs, repeat imports, namespace boundaries and atomic rollback."""

import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from conftest import FIXTURE_ROOT, REPO_ROOT, read_bundle, write_bundle
from knowflow_contracts.models import Workflow
from knowflow_contracts.search import StepSearchRecord, WorkflowSearchRecord
from knowflow_contracts.snapshot import snapshot_content_hash
from retrieval.importer import BundleImportError, import_bundle, read_active_records, status
from retrieval.importer import store
from retrieval.importer.__main__ import main


def ingest(path, db, source_type="synthetic", split="dev"):
    return import_bundle(path, db, source_type=source_type, split=split)


def counts(db):
    with sqlite3.connect(db) as conn:
        return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in ("sources", "snapshots", "builds", "search_records", "imports")}


def test_import_real_bundle_and_noop_preserves_inputs(tmp_path):
    bundle = REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle"
    hashes = {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest()
              for name in ("manifest.json", "sources.jsonl", "workflows.jsonl")}
    original = read_bundle(bundle)
    db = tmp_path / "real.sqlite"
    result = ingest(bundle, db, "real")
    assert result["status"] == "imported"
    assert result["new_sources"] == len(original["sources"])
    assert result["new_workflows"] == len(original["workflows"])
    manifest, records = read_active_records(db)
    assert manifest["embedding_model"] == "none"
    assert manifest["index_kind"] == "search-records"
    steps = [r for r in records if r["record_type"] == "step"]
    # Bundles retain historical revisions; search records contain only the
    # latest active revision of each workflow, not every stored snapshot.
    latest = {}
    for workflow in original["workflows"]:
        wid = workflow["workflow_id"]
        if wid not in latest or workflow["revision"] > latest[wid]["revision"]:
            latest[wid] = workflow
    active = [w for w in latest.values() if w["lifecycle"] == "active"]
    assert len(steps) == sum(len(w["steps"]) for w in active)
    assert {(r["workflow_id"], r["revision"]) for r in records} == {
        (w["workflow_id"], w["revision"]) for w in active}
    for record in records:
        (StepSearchRecord if record["record_type"] == "step" else WorkflowSearchRecord).model_validate(record)
        assert record["source_type"] == "real"
        assert record["text"]["search_text_vi"] is None
    before = counts(db)
    again = ingest(bundle, db, "real")
    assert again["status"] == "noop"
    assert again["index_build_id"] == result["index_build_id"]
    assert counts(db) == before
    with sqlite3.connect(db) as conn:
        saved = {(r[0], r[1]): (r[2], json.loads(r[3])) for r in conn.execute("SELECT * FROM snapshots")}
    for raw in original["workflows"]:
        wf = Workflow.model_validate(raw)
        assert saved[wf.key] == (snapshot_content_hash(wf), wf.model_dump(mode="json"))
    assert hashes == {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest() for name in hashes}


@pytest.mark.parametrize("fault,code", [
    ("checksum", "V02"), ("schema", "V01"), ("reference", "V03"), ("corpus", "V02"),
    ("split", "V02"), ("count", "V02"),
])
def test_invalid_bundle_rejected_before_db_creation(tmp_path, f01, fault, code):
    wf = f01["workflows"][0]
    if fault == "checksum":
        wf["title"] = "tampered"
    elif fault == "schema":
        wf["extra_key"] = True
    elif fault == "reference":
        wf["steps"][0]["fields"]["action"]["claim_ids"] = ["missing-id"]
    elif fault == "corpus":
        wf["source_type"] = "real"
    elif fault == "split":
        wf["dataset_split"] = "holdout"
    path = write_bundle(tmp_path / "bundle", f01, fix_checksums=fault != "checksum")
    if fault == "count":
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["files"][0]["record_count"] += 1
        (path / "manifest.json").write_text(json.dumps(manifest))
    db = tmp_path / "store.sqlite"
    with pytest.raises(BundleImportError, match=code):
        ingest(path, db)
    assert not db.exists()


def test_same_revision_different_content_rolls_back_whole_bundle(tmp_path, f01, f09):
    db = tmp_path / "store.sqlite"
    ingest(write_bundle(tmp_path / "initial", f01), db)
    before = counts(db), status(db)
    # Put new rows first to prove a later conflict rolls them back too.
    f09["sources"].extend(f01["sources"])
    f01["workflows"][0]["title"] = "changed without revision"
    f09["workflows"].extend(f01["workflows"])
    with pytest.raises(BundleImportError, match="V09 snapshot conflict"):
        ingest(write_bundle(tmp_path / "incoming", f09), db)
    assert (counts(db), status(db)) == before


def test_source_content_conflict_is_not_silently_overwritten(tmp_path, f01):
    db = tmp_path / "store.sqlite"
    ingest(write_bundle(tmp_path / "initial", f01), db)
    before = counts(db), status(db)
    f01["sources"][0]["title"] = "new source metadata"
    with pytest.raises(BundleImportError, match="source conflict"):
        ingest(write_bundle(tmp_path / "incoming", f01), db)
    assert (counts(db), status(db)) == before


def test_latest_revision_withdrawal_and_old_reimport(tmp_path, f09):
    db = tmp_path / "store.sqlite"
    old = copy.deepcopy(f09)
    old["workflows"] = old["workflows"][:1]
    ingest(write_bundle(tmp_path / "old", old), db)
    result = ingest(write_bundle(tmp_path / "new", f09), db)
    assert result["new_workflows"] == 1
    assert {r["revision"] for r in read_active_records(db)[1]} == {2}
    withdrawn = copy.deepcopy(f09)
    wf = withdrawn["workflows"][-1]
    wf.update(revision=3, supersedes_revision=2, lifecycle="withdrawn")
    wf["change_log"].append({
        "changed_at": "2026-09-14T00:00:00Z", "actor_id": "test-reviewer",
        "reason": "withdraw fixture", "previous_revision": 2, "id_mapping": [],
    })
    withdrawn["workflows"] = [wf]
    ingest(write_bundle(tmp_path / "withdrawn", withdrawn), db)
    manifest, records = read_active_records(db)
    assert manifest["withdrawn_workflows"] == 1
    assert records == []
    assert counts(db)["snapshots"] == 3
    assert ingest(tmp_path / "old", db)["status"] == "noop"
    assert read_active_records(db)[1] == []


def test_evidence_immutability_checked_across_imports(tmp_path, f09):
    db = tmp_path / "store.sqlite"
    old = copy.deepcopy(f09)
    old["workflows"] = old["workflows"][:1]
    ingest(write_bundle(tmp_path / "old", old), db)
    before = counts(db), status(db)
    f09["workflows"] = f09["workflows"][1:]
    f09["workflows"][0]["evidence"][0]["quote"] = "changed evidence retaining ID"
    with pytest.raises(BundleImportError, match="V03"):
        ingest(write_bundle(tmp_path / "new", f09), db)
    assert (counts(db), status(db)) == before


def test_build_failure_keeps_last_active_build(tmp_path, f01, f09, monkeypatch):
    db = tmp_path / "store.sqlite"
    ingest(write_bundle(tmp_path / "old", f01), db)
    before = counts(db), read_active_records(db)
    real_builder = store.build_records

    def broken_builder(workflow, build):
        yield real_builder(workflow, build)[0]
        raise RuntimeError("simulated build failure")

    monkeypatch.setattr(store, "build_records", broken_builder)
    with pytest.raises(RuntimeError, match="simulated build failure"):
        ingest(write_bundle(tmp_path / "new", f09), db)
    assert (counts(db), read_active_records(db)) == before


def test_wrong_requested_namespace_fails_before_creation(tmp_path, f01):
    db = tmp_path / "store.sqlite"
    with pytest.raises(BundleImportError, match="namespace"):
        ingest(write_bundle(tmp_path / "bundle", f01), db, "real")
    assert not db.exists()


@pytest.mark.parametrize("dimension", ["source_type", "dataset_split"])
def test_database_namespace_cannot_be_reused(tmp_path, f01, dimension):
    db = tmp_path / "store.sqlite"
    ingest(write_bundle(tmp_path / "synthetic", f01), db)
    before = counts(db), status(db)
    if dimension == "source_type":
        path = REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle"
        source_type, split = "real", "dev"
    else:
        f01["manifest"]["dataset_split"] = "holdout"
        for wf in f01["workflows"]:
            wf["dataset_split"] = "holdout"
        path = write_bundle(tmp_path / "holdout", f01)
        source_type, split = "synthetic", "holdout"
    with pytest.raises(BundleImportError, match="separate database"):
        ingest(path, db, source_type, split)
    assert (counts(db), status(db)) == before


def test_search_text_preserves_claim_scope_attribution_and_missing(tmp_path, f01):
    wf = f01["workflows"][0]
    claim = wf["claims"][0]
    claim["text"] = "Only if alarm 2066 occurs, do not remove the cover."
    db = tmp_path / "store.sqlite"
    ingest(write_bundle(tmp_path / "bundle", f01), db)
    records = read_active_records(db)[1]
    for record in records:
        if record["record_type"] == "step" and claim["claim_id"] not in record["claim_ids"]:
            continue
        text = record["text"]["search_text_original"]
        assert claim["text"] in text
        assert claim["scope"]["description"] in text
        assert claim["attribution"]["label"] in text
        flag = next(f for f in record["claim_review_flags"] if f["claim_id"] == claim["claim_id"])
        assert flag["source_review"] == "pending"
        assert record["metadata"]["machine_model"] == wf["context"]["machine_model"]


def test_build_is_reproducible_across_input_order(tmp_path, f09):
    first = ingest(write_bundle(tmp_path / "a", f09), tmp_path / "a.sqlite")
    f09["sources"].reverse()
    f09["workflows"].reverse()
    second = ingest(write_bundle(tmp_path / "b", f09), tmp_path / "b.sqlite")
    assert first["index_build_id"] == second["index_build_id"]


def test_cli_import_status_and_invalid_input(tmp_path, capsys):
    db = str(tmp_path / "store.sqlite")
    args = ["import", str(FIXTURE_ROOT / "F01_complete"), "--db", db,
            "--source-type", "synthetic", "--split", "dev"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "imported"
    assert main(["status", "--db", db]) == 0
    assert json.loads(capsys.readouterr().out)["active_steps"] > 0
    assert main(["status", "--db", str(tmp_path / "missing.sqlite")]) == 1
    assert "ERROR" in capsys.readouterr().err
    assert not (tmp_path / "missing.sqlite").exists()
