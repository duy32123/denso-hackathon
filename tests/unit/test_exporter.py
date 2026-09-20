"""Tests for the D1-B bundle exporter (acquisition/export/exporter.py).

What matters for the hand-off: a bad bundle never replaces a good one, the same
inputs always produce the same bytes, and a published revision cannot be edited
in place.
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from knowflow_contracts import validate_bundle

from acquisition.export import exporter as ex

FIXED_CLOCK = lambda: "2026-09-12T00:00:00Z"
WF_ID = "REAL_WF_0001"


def minimal_workflow(revision: int = 1, claim_text: str = "The presenter says to press E-stop once the pocket is in position.") -> dict:
    """Smallest real workflow on SRC_HAAS_0005 that passes V01-V10."""
    prov: dict[str, Any] = {k: {"basis": "unknown", "source_ids": [], "note": None} for k in (
        "manufacturer", "machine_family", "machine_model", "subsystem", "task_type",
        "symptoms", "alarm_codes", "components")}
    missing = {"state": "missing", "claim_ids": []}
    record = {
        "schema_version": "1.0.0", "workflow_id": WF_ID, "revision": revision, "source_type": "real",
        "dataset_split": "dev", "title": "Replace a damaged SMTC pocket", "language": "en",
        "created_at": "2026-09-12T00:00:00Z", "supersedes_revision": None, "lifecycle": "active",
        "source_ids": ["SRC_HAAS_0005"],
        "context": {
            "manufacturer": None, "machine_family": None, "machine_model": None, "subsystem": None,
            "task_type": None, "symptoms": [], "alarm_codes": [], "components": [], "metadata_provenance": prov,
        },
        "steps": [{
            "step_id": f"{WF_ID}_ST_001", "display_order": 1, "title": "Stop at the damaged pocket",
            "fields": {**{r: missing for r in ("context", "observation", "rationale", "condition", "outcome", "acceptance_criteria")},
                       "action": {"state": "present", "claim_ids": [f"{WF_ID}_CL_001"]}},
        }],
        "claims": [{
            "claim_id": f"{WF_ID}_CL_001", "text": claim_text, "role": "action", "evidence_type": "stated",
            "attribution": {"actor_id": None, "label": "Orville", "kind": "speaker"},
            "scope": {"level": "case", "description": "SRC_HAAS_0005 only"},
            "evidence_links": [{"evidence_id": f"{WF_ID}_EV_001", "support_status": "supported",
                                "explanation": "The caption states the action."}],
            "support_status": "supported", "source_review": "pending", "technical_review": "not_requested",
            "conflicts_with": [], "supersedes_claim_ids": [],
        }],
        "evidence": [{
            "evidence_id": f"{WF_ID}_EV_001", "source_id": "SRC_HAAS_0005", "modality": "speech",
            "locator": {"start_ms": 23770, "end_ms": 33430, "page": None, "text_span": None},
            "quote": "press e stop once the pocket is in position okay we need to remove three pieces of sheet",
            "observation_note": None, "asset_uri": None, "transcript_origin": "official_caption",
            "parent_evidence_ids": [],
        }],
        "relations": [], "questions": [], "review_events": [], "change_log": [],
    }
    if revision > 1:
        record["supersedes_revision"] = revision - 1
        record["change_log"] = [{
            "changed_at": "2026-09-12T00:00:00Z", "actor_id": "d1b", "reason": "test revision",
            "previous_revision": revision - 1, "id_mapping": [],
        }]
    return record


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    """A copy of the real dev bundle + an empty snapshot store, so tests never touch the repo."""
    out = tmp_path / "bundle"
    shutil.copytree(Path(str(ex.SPLITS["dev"]["out"])), out)
    snapshots = tmp_path / "workflows"
    snapshots.mkdir()
    return {"out": out, "snapshots": snapshots, "sources": ex.SPLITS["dev"]["sources"]}


def run(ws: dict, **kw) -> ex.ExportResult:
    return ex.export_bundle(
        split="dev", sources_path=ws["sources"], snapshot_dir=ws["snapshots"], out_dir=ws["out"],
        bundle_prefix="BUNDLE_TEST", clock=FIXED_CLOCK, **kw,
    )


def put(ws: dict, record: dict) -> None:
    path = ws["snapshots"] / f"{record['workflow_id']}.r{record['revision']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot_bytes(out: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(out.iterdir())}


# --- the committed bundles -------------------------------------------------------


@pytest.mark.parametrize("split", sorted(ex.SPLITS))
def test_committed_bundles_are_what_the_exporter_would_produce(split):
    cfg = ex.SPLITS[split]
    result = ex.export_bundle(
        split=split, sources_path=cfg["sources"], snapshot_dir=cfg["snapshots"], out_dir=cfg["out"],
        bundle_prefix=cfg["bundle_prefix"], check_only=True,
    )
    assert result.report.ok, "\n".join(str(i) for i in result.report.errors)
    assert not result.changed, f"{split}: committed bundle differs from a fresh export"


def test_unchanged_export_keeps_d1a_bundle_identity(workspace):
    before = snapshot_bytes(workspace["out"])
    result = run(workspace)
    assert not result.changed
    assert result.bundle_id == "BUNDLE_HAAS_D1A_SMTC_DEV_PILOT"
    assert snapshot_bytes(workspace["out"]) == before


# --- writing ---------------------------------------------------------------------


def test_new_workflow_produces_a_valid_bundle_with_a_new_id(workspace):
    put(workspace, minimal_workflow())
    result = run(workspace)
    assert result.report.ok and result.changed
    assert result.bundle_id.startswith("BUNDLE_TEST_")
    assert validate_bundle(workspace["out"]).ok
    manifest = json.loads((workspace["out"] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["created_at"] == "2026-09-12T00:00:00Z"
    assert {f["path"]: f["record_count"] for f in manifest["files"]} == {"sources.jsonl": 5, "workflows.jsonl": 1}


def test_reexport_is_a_byte_identical_noop(workspace):
    put(workspace, minimal_workflow())
    first = run(workspace)
    written = snapshot_bytes(workspace["out"])
    second = ex.export_bundle(
        split="dev", sources_path=workspace["sources"], snapshot_dir=workspace["snapshots"],
        out_dir=workspace["out"], bundle_prefix="BUNDLE_TEST", clock=lambda: "2099-01-01T00:00:00Z",
    )
    assert not second.changed and second.bundle_id == first.bundle_id
    assert snapshot_bytes(workspace["out"]) == written, "a no-op must not even bump created_at"


def test_sources_are_copied_byte_for_byte(workspace):
    put(workspace, minimal_workflow())
    run(workspace)
    assert (workspace["out"] / "sources.jsonl").read_bytes() == workspace["sources"].read_bytes()


def test_crlf_source_file_is_refused(workspace, tmp_path):
    crlf = tmp_path / "sources_crlf.jsonl"
    crlf.write_bytes(workspace["sources"].read_bytes().replace(b"\n", b"\r\n"))
    workspace["sources"] = crlf
    with pytest.raises(ex.ExportError, match="LF"):
        run(workspace)


def test_check_only_writes_nothing(workspace):
    before = snapshot_bytes(workspace["out"])
    put(workspace, minimal_workflow())
    result = run(workspace, check_only=True)
    assert result.report.ok and result.changed
    assert snapshot_bytes(workspace["out"]) == before


# --- rejecting -------------------------------------------------------------------


def test_invalid_snapshot_leaves_previous_bundle_untouched(workspace):
    before = snapshot_bytes(workspace["out"])
    bad = minimal_workflow()
    bad["claims"][0]["confidence"] = 0.9  # unknown key -> V01
    put(workspace, bad)
    result = run(workspace)
    assert not result.report.ok and "V01" in result.report.error_codes
    assert snapshot_bytes(workspace["out"]) == before


def test_semantically_invalid_snapshot_is_rejected_whole(workspace):
    before = snapshot_bytes(workspace["out"])
    bad = minimal_workflow()
    bad["evidence"][0]["locator"]["end_ms"] = 10**9  # beyond duration_ms -> V04
    put(workspace, bad)
    result = run(workspace)
    assert "V04" in result.report.error_codes
    assert snapshot_bytes(workspace["out"]) == before


def test_published_revision_cannot_be_edited_in_place(workspace):
    put(workspace, minimal_workflow())
    run(workspace)
    put(workspace, minimal_workflow(claim_text="The presenter says to press E-stop first."))
    with pytest.raises(ex.ExportError, match="already published"):
        run(workspace)


def test_published_revision_cannot_be_dropped(workspace):
    put(workspace, minimal_workflow())
    run(workspace)
    (workspace["snapshots"] / f"{WF_ID}.r1.json").unlink()
    with pytest.raises(ex.ExportError, match="missing from the snapshot store"):
        run(workspace)


def test_change_goes_through_a_new_revision(workspace):
    put(workspace, minimal_workflow())
    run(workspace)
    put(workspace, minimal_workflow(revision=2, claim_text="The presenter says to press E-stop first."))
    result = run(workspace)
    assert result.report.ok and result.counts["workflows"] == 2


def test_snapshot_file_name_must_match_its_content(workspace):
    record = minimal_workflow()
    (workspace["snapshots"] / f"{WF_ID}.r2.json").write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ex.ExportError, match="file name says"):
        run(workspace)


def test_bad_snapshot_file_name_is_refused(workspace):
    (workspace["snapshots"] / "draft.json").write_text(json.dumps(minimal_workflow()), encoding="utf-8")
    with pytest.raises(ex.ExportError, match="must be named"):
        run(workspace)


def test_holdout_workflow_in_dev_bundle_is_rejected(workspace):
    wrong = copy.deepcopy(minimal_workflow())
    wrong["dataset_split"] = "holdout"
    put(workspace, wrong)
    assert "V02" in run(workspace).report.error_codes
