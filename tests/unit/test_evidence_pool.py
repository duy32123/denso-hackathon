"""Tests for the D1-B evidence candidate pool (acquisition/extraction/evidence_pool.py).

The pool's job is narrow: every candidate points at verbatim source text with a
locator on the original video, IDs never silently shift, and whatever it emits
passes the shared contract validator once placed in a workflow.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from knowflow_contracts import validate_bundle

from acquisition.extraction import evidence_pool as ep


@pytest.fixture(scope="module")
def pool() -> dict[str, list[ep.Candidate]]:
    return ep.build_pool()


@pytest.fixture(scope="module")
def index(pool) -> dict[str, ep.Candidate]:
    return {c.candidate_id: c for cands in pool.values() for c in cands}


def dev_source(source_id: str) -> dict:
    for line in ep.DEV_SOURCES.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["source_id"] == source_id:
            return record
    raise KeyError(source_id)


# --- building ------------------------------------------------------------------


def test_only_dev_sources_are_read(pool):
    assert set(pool) == ep.dev_source_ids()
    assert "SRC_HAAS_0006" not in pool and "SRC_HAAS_0007" not in pool


def test_every_caption_cue_becomes_one_raw_candidate(pool):
    for sid in ("SRC_HAAS_0001", "SRC_HAAS_0003", "SRC_HAAS_0005"):
        raw = json.loads((ep.TRANSCRIPTS_DIR / sid / "raw.json").read_text(encoding="utf-8"))
        raw_cands = [c for c in pool[sid] if c.kind == "U"]
        assert [c.text for c in raw_cands] == [u["text"] for u in raw["utterances"]]


def test_speech_locators_stay_inside_the_original_video(pool):
    for sid, cands in pool.items():
        duration = dev_source(sid)["duration_ms"]
        for c in cands:
            if c.modality == "speech":
                assert 0 <= c.start_ms < c.end_ms <= duration, c.candidate_id


def test_candidate_ids_are_unique(pool):
    ids = [c.candidate_id for cands in pool.values() for c in cands]
    assert len(ids) == len(set(ids))


def test_corrected_cue_is_human_and_keeps_its_caption_parent(index):
    corrected = index["SRC_HAAS_0001:C0021"]
    assert corrected.transcript_origin == "human"
    assert corrected.parent_candidate_id == "SRC_HAAS_0001:U0021"
    assert "20,000 meter" in index["SRC_HAAS_0001:U0021"].text, "raw caption must be kept verbatim"


def test_corrected_candidate_count_matches_differing_cues(pool):
    """Every C-candidate corresponds to exactly one cue whose text actually changed
    -- the pool must not invent corrections, and must not miss any either."""
    for sid in ("SRC_HAAS_0001", "SRC_HAAS_0003", "SRC_HAAS_0005"):
        raw = json.loads((ep.TRANSCRIPTS_DIR / sid / "raw.json").read_text(encoding="utf-8"))["utterances"]
        corrected = json.loads((ep.TRANSCRIPTS_DIR / sid / "corrected.json").read_text(encoding="utf-8"))["utterances"]
        expected = sum(1 for r, c in zip(raw, corrected) if r["text"] != c["text"])
        actual = sum(1 for c in pool[sid] if c.kind == "C")
        assert actual == expected, sid


def test_guides_become_line_candidates(pool):
    assert all(c.modality == "text" and c.kind == "T" for c in pool["SRC_HAAS_0004"])
    assert any("[RECOVER]" in c.text for c in pool["SRC_HAAS_0004"])


def test_repeated_guide_lines_are_flagged(pool):
    dupes = [c for c in pool["SRC_HAAS_0002"] if c.text_span_unique is False]
    assert dupes, "TG0128 repeats part-list lines; text_span alone cannot locate them"


def test_holdout_source_in_the_input_is_refused(tmp_path):
    holdout = json.loads(Path(ep.REPO_ROOT / "data/sources/haas_pilot_holdout_sources.jsonl").read_text(encoding="utf-8").splitlines()[0])
    sources = tmp_path / "sources.jsonl"
    sources.write_text(json.dumps(holdout) + "\n", encoding="utf-8")
    with pytest.raises(ep.PoolError, match="not a dev source"):
        ep.build_pool(sources_path=sources)


def test_correction_may_not_move_timestamps(tmp_path):
    src_dir = ep.TRANSCRIPTS_DIR / "SRC_HAAS_0005"
    corrected = json.loads((src_dir / "corrected.json").read_text(encoding="utf-8"))
    corrected["utterances"][3]["start_ms"] += 500
    bad = tmp_path / "corrected.json"
    bad.write_text(json.dumps(corrected), encoding="utf-8")
    with pytest.raises(ep.PoolError, match="never timestamps"):
        ep.speech_candidates(dev_source("SRC_HAAS_0005"), src_dir / "raw.json", bad)


def test_guide_text_must_match_its_content_hash():
    source = dict(dev_source("SRC_HAAS_0004"))
    source["raw_text"] += "\nextra line"
    with pytest.raises(ep.PoolError, match="content_sha256"):
        ep.text_candidates(source)


# --- persisting ----------------------------------------------------------------


def test_rebuilding_from_same_inputs_is_byte_identical(pool, tmp_path):
    ep.write_pool(pool, tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    ep.write_pool(pool, tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == first


def test_committed_pool_matches_a_fresh_build(pool, tmp_path):
    """The committed pool must be exactly what the code produces from the committed inputs."""
    ep.write_pool(pool, tmp_path)
    for path in tmp_path.iterdir():
        assert (ep.POOL_DIR / path.name).read_bytes() == path.read_bytes(), path.name


def test_changed_input_refuses_to_renumber(pool, tmp_path):
    ep.write_pool(pool, tmp_path)
    shifted = dict(pool)
    shifted["SRC_HAAS_0005"] = [replace(c, input_sha256="0" * 64) for c in pool["SRC_HAAS_0005"]]
    with pytest.raises(ep.PoolError, match="inputs changed"):
        ep.write_pool(shifted, tmp_path)


def test_tampered_pool_file_is_detected(pool, tmp_path):
    ep.write_pool(pool, tmp_path)
    target = tmp_path / "SRC_HAAS_0005.jsonl"
    target.write_bytes(target.read_bytes().replace(b"Orville", b"Orvile"))
    with pytest.raises(ep.PoolError, match="checksum"):
        ep.load_pool(tmp_path)


# --- spans ---------------------------------------------------------------------


def test_consecutive_cues_join_into_one_span(index):
    sp = ep.span([index["SRC_HAAS_0005:U0003"], index["SRC_HAAS_0005:U0004"]])
    assert (sp.start_ms, sp.end_ms) == (index["SRC_HAAS_0005:U0003"].start_ms, index["SRC_HAAS_0005:U0004"].end_ms)
    assert sp.quote.startswith("press e stop")
    assert sp.transcript_origin == "official_caption"


@pytest.mark.parametrize(
    ("ids", "message"),
    [
        (["SRC_HAAS_0005:U0003", "SRC_HAAS_0005:U0005"], "consecutive"),
        (["SRC_HAAS_0005:U0003", "SRC_HAAS_0003:U0004"], "cross sources"),
        (["SRC_HAAS_0001:U0021", "SRC_HAAS_0001:C0021"], "twice"),
        ([], "at least one"),
    ],
)
def test_invalid_spans_are_refused(index, ids, message):
    with pytest.raises(ep.PoolError, match=message):
        ep.span([index[i] for i in ids])


def test_corrected_span_needs_its_raw_parent_as_evidence(index):
    sp = ep.span([index["SRC_HAAS_0001:C0021"], index["SRC_HAAS_0001:U0022"]])
    assert sp.transcript_origin == "human"
    with pytest.raises(ep.PoolError, match="parent_evidence_ids"):
        ep.to_evidence(sp, "REAL_WF_9999_EV_002")

    parent = ep.raw_parent(sp, index)
    assert parent.candidate_ids == ("SRC_HAAS_0001:U0021", "SRC_HAAS_0001:U0022")
    record = ep.to_evidence(sp, "REAL_WF_9999_EV_002", parent_evidence_ids=("REAL_WF_9999_EV_001",))
    assert record["parent_evidence_ids"] == ["REAL_WF_9999_EV_001"]


def test_text_span_locates_the_guide_line(index):
    record = ep.to_evidence(ep.span([index["SRC_HAAS_0004:T0004"]]), "REAL_WF_9999_EV_001")
    assert record["locator"]["text_span"] in dev_source("SRC_HAAS_0004")["raw_text"]
    assert record["locator"]["start_ms"] is None


# --- contract ------------------------------------------------------------------


def _write_bundle(root: Path, sources: list[dict], workflow: dict) -> Path:
    root.mkdir(parents=True)
    files = []
    for name, records in (("sources.jsonl", sources), ("workflows.jsonl", [workflow])):
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode("utf-8")
        (root / name).write_bytes(body)
        files.append({"path": name, "sha256": hashlib.sha256(body).hexdigest(), "record_count": len(records)})
    manifest = {
        "schema_version": "1.0.0", "bundle_id": "TEST_POOL", "source_type": "real", "dataset_split": "dev",
        "created_at": "2026-09-11T00:00:00Z", "files": files,
        "producer": {"team": "team_1", "pipeline_version": "test"},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_pool_evidence_passes_the_contract_validator(index, tmp_path):
    """Raw + corrected evidence from the pool, cited by one claim, must validate."""
    wf_id = "REAL_WF_9999"
    corrected = ep.span([index["SRC_HAAS_0001:C0021"], index["SRC_HAAS_0001:U0022"]])
    raw = ep.raw_parent(corrected, index)
    evidence = [
        ep.to_evidence(raw, f"{wf_id}_EV_001"),
        ep.to_evidence(corrected, f"{wf_id}_EV_002", parent_evidence_ids=(f"{wf_id}_EV_001",)),
    ]
    prov = {k: {"basis": "unknown", "source_ids": [], "note": None} for k in (
        "manufacturer", "machine_family", "machine_model", "subsystem", "task_type",
        "symptoms", "alarm_codes", "components")}
    missing = {"state": "missing", "claim_ids": []}
    workflow = {
        "schema_version": "1.0.0", "workflow_id": wf_id, "revision": 1, "source_type": "real",
        "dataset_split": "dev", "title": "Pool contract check", "language": "en",
        "created_at": "2026-09-11T00:00:00Z", "supersedes_revision": None, "lifecycle": "active",
        "source_ids": ["SRC_HAAS_0001"],
        "context": {
            "manufacturer": None, "machine_family": None, "machine_model": None, "subsystem": None,
            "task_type": None, "symptoms": [], "alarm_codes": [], "components": [], "metadata_provenance": prov,
        },
        "steps": [{
            "step_id": f"{wf_id}_ST_001", "display_order": 1, "title": "Check arm clearance",
            "fields": {**{r: missing for r in ("context", "observation", "rationale", "condition", "outcome", "acceptance_criteria")},
                       "action": {"state": "present", "claim_ids": [f"{wf_id}_CL_001"]}},
        }],
        "claims": [{
            "claim_id": f"{wf_id}_CL_001",
            "text": "The narrator says to check the gap between the arm finger and the V flange with a feeler gauge.",
            "role": "action", "evidence_type": "stated",
            "attribution": {"actor_id": None, "label": "narrator", "kind": "speaker"},
            "scope": {"level": "case", "description": "SRC_HAAS_0001 only"},
            "evidence_links": [{"evidence_id": f"{wf_id}_EV_001", "support_status": "supported",
                                "explanation": "Caption states the feeler-gauge check."}],
            "support_status": "supported", "source_review": "pending", "technical_review": "not_requested",
            "conflicts_with": [], "supersedes_claim_ids": [],
        }],
        "evidence": evidence, "relations": [], "questions": [], "review_events": [], "change_log": [],
    }
    bundle = _write_bundle(tmp_path / "bundle", [dev_source("SRC_HAAS_0001")], workflow)
    report = validate_bundle(bundle)
    assert report.ok, "\n".join(str(i) for i in report.errors)
