"""Evidence-only revisions preserve published IDs and never inherit source review."""
from __future__ import annotations

import copy
import json

import pytest

from acquisition.extraction import compile_workflow as cw
from acquisition.extraction import evidence_pool as ep
from acquisition.extraction import review as rv
from knowflow_contracts.models import Workflow
from knowflow_contracts.snapshot import snapshot_content_hash

ROOT = cw.REPO_ROOT
R2_PATH = ROOT / "acquisition/extraction/drafts/B0_SRC_HAAS_0005.r2.draft.json"
BASE_PATH = ROOT / "data/workflows/dev/B0_SRC_HAAS_0005.r1.json"
PREFIX = "B0_SRC_HAAS_0005"


@pytest.fixture(scope="module")
def pool():
    return ep.load_pool()


@pytest.fixture
def draft():
    return json.loads(R2_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def base():
    return json.loads(BASE_PATH.read_text(encoding="utf-8"))


def test_repair_keeps_all_prior_evidence_and_structural_ids(draft, base, pool):
    snapshot = cw.compile_draft(draft, pool)
    assert snapshot["evidence"][:-1] == base["evidence"]
    for key in ("steps", "questions", "relations", "context"):
        assert snapshot[key] == base[key]
    assert [c["claim_id"] for c in snapshot["claims"]] == [c["claim_id"] for c in base["claims"]]
    before, after = rv.fingerprints(base), rv.fingerprints(snapshot)
    assert [cid for cid in before if before[cid] != after[cid]] == [f"{PREFIX}_CL_020"]
    assert snapshot == cw.compile_draft(copy.deepcopy(draft), pool)


def test_repair_quote_is_exactly_two_cues_and_gets_new_id(draft, pool):
    snapshot = cw.compile_draft(draft, pool)
    evidence = snapshot["evidence"][-1]
    assert evidence["evidence_id"] == f"{PREFIX}_EV_033"
    assert evidence["locator"]["start_ms"] == 147840
    assert evidence["locator"]["end_ms"] == 165270
    assert evidence["quote"] == " ".join(pool[f"SRC_HAAS_0005:{cue}"].text for cue in ("U0020", "U0021"))
    assert "apply some grease" in evidence["quote"]
    claim = next(c for c in snapshot["claims"] if c["claim_id"] == f"{PREFIX}_CL_020")
    assert claim["text"] == "Apply grease to the pocket slider."
    assert claim["evidence_links"][0]["evidence_id"] == evidence["evidence_id"]
    assert snapshot["change_log"][-1]["id_mapping"] == [
        {"old_id": f"{PREFIX}_EV_019", "new_ids": [f"{PREFIX}_EV_033"]}]


def test_new_revision_has_blank_review_sheet_and_no_inherited_decisions(draft, pool, tmp_path):
    snapshot = cw.compile_draft(draft, pool)
    assert {c["source_review"] for c in snapshot["claims"]} == {"pending"}
    assert {c["technical_review"] for c in snapshot["claims"]} == {"not_requested"}
    assert snapshot["review_events"] == []
    rows = rv.build_sheet(snapshot, rv._sources("dev"))
    assert len(rows) == 33 and all(not row["decision"] and not row["note"] for row in rows)
    record = rv.load_record(PREFIX, 2, tmp_path / "reviews")
    status = rv.review_status(snapshot, record)
    assert status["source_checked"] == 0 and len(status["pending"]) == 33
    with pytest.raises(rv.ReviewError, match="33 claim\\(s\\) pending"):
        rv.promote(R2_PATH, reviews_dir=tmp_path / "reviews", workflows_root=tmp_path / "workflows")
    assert not (tmp_path / "workflows").exists()


def test_base_and_candidate_pass_shared_validation_together(draft, pool):
    report = cw.check_draft_snapshot(draft, cw.compile_draft(draft, pool)).report
    assert report.ok, [str(issue) for issue in report.errors]
    assert not report.warnings


def test_cross_revision_validation_catches_mutation_of_old_evidence(draft, pool):
    snapshot = cw.compile_draft(draft, pool)
    snapshot["evidence"][18]["quote"] += " fabricated grease"
    report = cw.check_draft_snapshot(draft, snapshot).report
    assert not report.ok
    assert any(issue.code == "V03" for issue in report.errors)


def _next_draft(draft, snapshot, tmp_path):
    inventory = tmp_path / "acquisition/preprocessing/haas_d1a_media_inventory.jsonl"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text("", encoding="utf-8")
    path = tmp_path / f"{snapshot['workflow_id']}.r{snapshot['revision']}.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    result = copy.deepcopy(draft)
    result["revision"] = snapshot["revision"] + 1
    result["supersedes_revision"] = snapshot["revision"]
    result["revision_base"] = {
        "path": path.name,
        "snapshot_sha256": snapshot_content_hash(Workflow.model_validate(snapshot)),
    }
    result["change_log"] = copy.deepcopy(snapshot["change_log"]) + [{
        "changed_at": "2026-09-15T07:00:00Z", "actor_id": "test-author",
        "reason": "Evidence-only test repair", "previous_revision": snapshot["revision"], "id_mapping": [],
    }]
    return result


def test_next_revision_never_recycles_retired_ids(draft, pool, tmp_path, monkeypatch):
    second = cw.compile_draft(draft, pool)
    third_draft = _next_draft(draft, second, tmp_path)
    third_draft["steps"][5]["fields"]["action"]["claims"][2]["evidence"] = [
        ["SRC_HAAS_0005:U0020", "SRC_HAAS_0005:U0021", "SRC_HAAS_0005:U0022"]]
    monkeypatch.setattr(cw, "REPO_ROOT", tmp_path)
    third = cw.compile_draft(third_draft, pool)
    assert third["evidence"][:-1] == second["evidence"]
    assert third["evidence"][-1]["evidence_id"] == f"{PREFIX}_EV_034"
    assert third["change_log"][-1]["id_mapping"] == [
        {"old_id": f"{PREFIX}_EV_033", "new_ids": [f"{PREFIX}_EV_034"]}]


def test_corrected_evidence_parent_uses_stable_raw_id(pool, tmp_path, monkeypatch):
    draft = {
        "workflow_id": "REAL_WF_9998", "revision": 1, "dataset_split": "dev", "title": "t",
        "language": "en", "created_at": "2026-09-15T00:00:00Z", "source_ids": ["SRC_HAAS_0001"],
        "attribution": {"label": "narrator", "kind": "speaker"}, "scope": "test", "context": {},
        "steps": [{"title": "s", "fields": {"action": [
            {"text": "a", "evidence": [["SRC_HAAS_0001:U0001"]], "explanation": "a"},
            {"text": "b", "evidence": [["SRC_HAAS_0001:U0021"]], "explanation": "b"},
        ]}}],
    }
    base = cw.compile_draft(draft, pool)
    new_draft = _next_draft(draft, base, tmp_path)
    new_draft["steps"][0]["fields"]["action"][0]["evidence"] = [["SRC_HAAS_0001:U0002"]]
    new_draft["steps"][0]["fields"]["action"][1]["evidence"] = [["SRC_HAAS_0001:C0021"]]
    monkeypatch.setattr(cw, "REPO_ROOT", tmp_path)
    result = cw.compile_draft(new_draft, pool)
    assert result["evidence"][:2] == base["evidence"]
    assert result["evidence"][-1]["evidence_id"] == "REAL_WF_9998_EV_004"
    assert result["evidence"][-1]["parent_evidence_ids"] == ["REAL_WF_9998_EV_002"]
    assert cw.check_draft_snapshot(new_draft, result).report.ok


@pytest.mark.parametrize("change, message", [
    ({"revision_base": None}, "requires revision_base"),
    ({"revision": 1}, "cannot have revision_base"),
    ({"revision": 3}, "base revision"),
    ({"supersedes_revision": None}, "supersedes_revision"),
    ({"workflow_id": "DIFFERENT"}, "workflow/corpus/split"),
    ({"dataset_split": "test"}, "workflow/corpus/split"),
    ({"source_type": "synthetic"}, "workflow/corpus/split"),
    ({"revision": True}, "positive integer"),
])
def test_revision_metadata_is_checked(draft, pool, change, message):
    draft.update(change)
    with pytest.raises(cw.DraftError, match=message):
        cw.compile_draft(draft, pool)


@pytest.mark.parametrize("field,value,message", [
    ("snapshot_sha256", "0" * 64, "hash mismatch"),
    ("snapshot_sha256", "not-a-hash", "canonical snapshot hash"),
    ("path", "../outside.json", "escapes the repo"),
    ("path", "C:/outside.json", "repo-relative"),
    ("path", "does-not-exist.json", "Cannot read"),
])
def test_revision_base_is_pinned_inside_repo(draft, pool, field, value, message):
    draft["revision_base"][field] = value
    with pytest.raises(cw.DraftError, match=message):
        cw.compile_draft(draft, pool)


@pytest.mark.parametrize("change", ["claim_text", "insert_claim", "reorder_claim", "step_title", "reverse_steps"])
def test_evidence_only_revision_refuses_identity_changes(draft, pool, change):
    claims = draft["steps"][5]["fields"]["action"]["claims"]
    if change == "claim_text":
        claims[2]["text"] += " with an invented specification."
    elif change == "insert_claim":
        claims.append(copy.deepcopy(claims[0]))
    elif change == "reorder_claim":
        claims.reverse()
    elif change == "step_title":
        draft["steps"][0]["title"] += " changed"
    else:
        draft["steps"].reverse()
    with pytest.raises(cw.DraftError, match="Evidence-only revision"):
        cw.compile_draft(draft, pool)


@pytest.mark.parametrize("change,message", [
    ("missing", "append exactly one"),
    ("wrong_previous", "base revision"),
    ("blank_reason", "base revision"),
    ("false_mapping", "id_mapping differs"),
])
def test_change_history_must_describe_actual_revision(draft, pool, change, message):
    event = draft["change_log"][-1]
    if change == "missing":
        draft["change_log"] = []
    elif change == "wrong_previous":
        event["previous_revision"] = 2
    elif change == "blank_reason":
        event["reason"] = "   "
    else:
        event["id_mapping"] = [{"old_id": f"{PREFIX}_EV_019", "new_ids": [f"{PREFIX}_EV_020"]}]
    with pytest.raises(cw.DraftError, match=message):
        cw.compile_draft(draft, pool)


def test_old_revision_review_record_cannot_be_merged(draft, pool):
    snapshot = cw.compile_draft(draft, pool)
    old_record = rv.load_record(PREFIX, 1)
    assert old_record["sessions"]
    with pytest.raises(rv.ReviewError, match="different workflow revisions"):
        rv.merge_reviews(snapshot, old_record)


def test_legacy_revision_is_replay_only_and_existing_id_conflict_is_detected(pool):
    path = ROOT / "acquisition/extraction/drafts/REAL_WF_0001.r2.draft.json"
    legacy = json.loads(path.read_text(encoding="utf-8"))
    assert "revision_base" not in legacy
    snapshot = cw.compile_draft(legacy, pool)
    report = cw.check_draft_snapshot(legacy, snapshot).report
    # The existing draft r2 changed a visual locator while keeping its r1 ID.
    # It remains reproducible but cannot pass the stronger cross-revision gate.
    assert not report.ok
    assert any(issue.code == "V03" for issue in report.errors)
    legacy["steps"][0]["title"] += " changed"
    with pytest.raises(cw.DraftError, match="exact existing compiled snapshot"):
        cw.compile_draft(legacy, pool)


def test_missing_base_does_not_enable_legacy_bypass(draft, pool):
    del draft["revision_base"]
    with pytest.raises(cw.DraftError, match="requires revision_base"):
        cw.compile_draft(draft, pool)
