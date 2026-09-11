"""Tests for the draft -> snapshot compiler (acquisition/extraction/compile_workflow.py)
and for the first real workflow it produced (REAL_WF_0001, SRC_HAAS_0005).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from acquisition.extraction import compile_workflow as cw
from acquisition.extraction import evidence_pool as ep

DRAFT = cw.REPO_ROOT / "acquisition" / "extraction" / "drafts" / "REAL_WF_0001.r1.draft.json"
SNAPSHOT = cw.DRAFT_OUT / "REAL_WF_0001.r1.json"


@pytest.fixture(scope="module")
def pool() -> dict[str, ep.Candidate]:
    return ep.load_pool()


@pytest.fixture
def draft() -> dict:
    return json.loads(DRAFT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def tiny_draft(**claim) -> dict:
    spec = {"text": "The presenter says to press E-stop.", "evidence": [["SRC_HAAS_0005:U0003"]],
            "explanation": "Caption states it."}
    spec.update(claim)
    return {
        "workflow_id": "REAL_WF_9998", "revision": 1, "dataset_split": "dev", "title": "t", "language": "en",
        "created_at": "2026-09-11T00:00:00Z", "source_ids": ["SRC_HAAS_0005"],
        "attribution": {"label": "Orville (presenter)", "kind": "speaker"}, "scope": "test",
        "context": {}, "steps": [{"title": "s", "fields": {"action": [spec]}}],
    }


# --- REAL_WF_0001 ------------------------------------------------------------------


def test_committed_snapshot_is_exactly_the_compiled_draft(draft, pool, tmp_path):
    path = cw.write_snapshot(cw.compile_draft(draft, pool), tmp_path)
    assert path.read_bytes() == SNAPSHOT.read_bytes(), "edit the draft and recompile; never hand-edit the snapshot"


def test_snapshot_passes_the_contract_validator_without_warnings(snapshot):
    report = cw.check_snapshot(snapshot).report
    assert report.ok, "\n".join(str(i) for i in report.errors)
    assert not report.warnings, "\n".join(str(i) for i in report.warnings)


def test_every_speech_quote_is_verbatim_caption_text(snapshot, pool):
    by_window = {}
    for c in pool.values():
        if c.source_id == "SRC_HAAS_0005":
            by_window[c.start_ms] = c
    for ev in snapshot["evidence"]:
        if ev["modality"] != "speech":
            continue
        loc = ev["locator"]
        cues = sorted((c for c in by_window.values() if loc["start_ms"] <= c.start_ms < loc["end_ms"]), key=lambda c: c.ordinal)
        assert ev["quote"] == " ".join(c.text for c in cues), ev["evidence_id"]


def test_nothing_is_marked_reviewed_by_the_author(snapshot):
    assert {c["source_review"] for c in snapshot["claims"]} == {"pending"}
    assert {c["technical_review"] for c in snapshot["claims"]} == {"not_requested"}
    assert snapshot["review_events"] == []


def test_claims_are_in_the_source_language(snapshot):
    """D-03: English video -> English claims."""
    assert snapshot["language"] == "en"


def test_machine_model_is_left_unknown(snapshot):
    ctx = snapshot["context"]
    assert ctx["machine_model"] is None and ctx["machine_family"] is None
    assert ctx["metadata_provenance"]["machine_model"]["basis"] == "unknown"


def test_gaps_become_questions_not_claims(snapshot):
    steps = {s["step_id"]: s for s in snapshot["steps"]}
    for q in snapshot["questions"]:
        if q["reason"] == "missing":
            assert steps[q["step_id"]]["fields"][q["target_field"]]["state"] == "missing", q["question"]


def test_observed_claim_is_backed_by_a_keyframe_and_not_self_attributed_to_a_person(snapshot):
    observed = [c for c in snapshot["claims"] if c["evidence_type"] == "observed"]
    assert observed
    evidence = {e["evidence_id"]: e for e in snapshot["evidence"]}
    for claim in observed:
        visual = [evidence[l["evidence_id"]] for l in claim["evidence_links"] if evidence[l["evidence_id"]]["modality"] == "visual"]
        assert visual and all(Path(cw.REPO_ROOT / v["asset_uri"]).is_file() for v in visual)
        assert claim["attribution"]["kind"] == "model", "a draft observation is not a human observer until reviewed"


# --- compiler rules ------------------------------------------------------------------


def test_compiling_twice_gives_identical_ids(draft, pool):
    assert cw.compile_draft(draft, pool) == cw.compile_draft(copy.deepcopy(draft), pool)


def test_same_span_becomes_one_evidence_record(pool):
    d = tiny_draft()
    d["steps"][0]["fields"]["condition"] = [{"text": "Once in position.", "evidence": [["SRC_HAAS_0005:U0003"]], "explanation": "x"}]
    snap = cw.compile_draft(d, pool)
    assert len(snap["evidence"]) == 1
    assert {l["evidence_id"] for c in snap["claims"] for l in c["evidence_links"]} == {"REAL_WF_9998_EV_001"}


def test_corrected_span_brings_its_raw_caption_parent(pool):
    d = tiny_draft(evidence=[["SRC_HAAS_0001:C0021"]])
    d["source_ids"] = ["SRC_HAAS_0001"]
    snap = cw.compile_draft(d, pool)
    raw, corrected = snap["evidence"]
    assert corrected["parent_evidence_ids"] == [raw["evidence_id"]]
    assert raw["transcript_origin"] == "official_caption" and corrected["transcript_origin"] == "human"
    assert cw.check_snapshot(snap).report.ok


def test_support_status_is_derived_not_declared(pool):
    snap = cw.compile_draft(tiny_draft(support_status="ambiguous"), pool)
    assert snap["claims"][0]["support_status"] == "supported"


@pytest.mark.parametrize(
    ("claim", "message"),
    [
        ({"evidence": [["SRC_HAAS_0005:U9999"]]}, "unknown evidence-pool candidate"),
        ({"evidence": []}, "needs evidence"),
        ({"evidence": [["SRC_HAAS_0005:U0003", "SRC_HAAS_0005:U0005"]]}, "consecutive"),
        ({"explanation": None}, "without explanation"),
        ({"evidence": [{"keyframe": "acquisition/preprocessing/keyframes/SRC_HAAS_0005/kf_0142700.jpg",
                        "source_id": "SRC_HAAS_0005", "start_ms": 0, "end_ms": 1000, "observation_note": "x"}]},
         "outside"),
        ({"evidence": [{"keyframe": "acquisition/preprocessing/keyframes/SRC_HAAS_0005/kf_0142700.jpg",
                        "source_id": "SRC_HAAS_0005", "start_ms": 142680, "end_ms": 147840}]},
         "observation_note"),
    ],
)
def test_bad_claims_are_refused(pool, claim, message):
    with pytest.raises((cw.DraftError, ep.PoolError), match=message):
        cw.compile_draft(tiny_draft(**claim), pool)


def test_unknown_field_name_is_refused(pool):
    d = tiny_draft()
    d["steps"][0]["fields"]["reason"] = []
    with pytest.raises(cw.DraftError, match="unknown field"):
        cw.compile_draft(d, pool)


def test_context_value_needs_a_provenance_basis(pool):
    d = tiny_draft()
    d["context"] = {"machine_model": "VM-3"}
    with pytest.raises(cw.DraftError, match="no provenance basis"):
        cw.compile_draft(d, pool)


def test_relation_condition_must_point_at_a_condition_claim(pool):
    d = tiny_draft(key="press")
    d["steps"].append({"title": "s2", "fields": {"action": [{"text": "Next.", "evidence": [["SRC_HAAS_0005:U0004"]], "explanation": "x"}]}})
    d["relations"] = [{"type": "branch_if", "from_step": 1, "to_step": 2, "condition_keys": ["press"],
                       "claim": {"text": "r", "evidence": [["SRC_HAAS_0005:U0004"]], "explanation": "x"}}]
    with pytest.raises(cw.DraftError, match="not a condition claim"):
        cw.compile_draft(d, pool)
