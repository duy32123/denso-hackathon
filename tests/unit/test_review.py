"""Tests for the D1-B source-review tool (acquisition/extraction/review.py).

The guarantees under test: only a named human decision marks a claim
source_checked, the decision is bound to the exact content that was checked,
and nothing reaches the exporter until the review is complete.
"""
from __future__ import annotations

import copy
import json

import pytest

from acquisition.extraction import compile_workflow as cw
from acquisition.extraction import review as rv

DRAFT_PATH = cw.REPO_ROOT / "acquisition" / "extraction" / "drafts" / "REAL_WF_0001.r1.draft.json"
FIXED = lambda: "2026-09-12T09:00:00Z"
REVIEWER = {"reviewer_id": "d1c-reviewer", "reviewer_role": "D1-C annotation/QA"}


@pytest.fixture
def draft() -> dict:
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def snapshot(draft) -> dict:
    return cw.compile_draft(draft)


@pytest.fixture(scope="module")
def sources() -> dict[str, dict]:
    return rv._sources("dev")


def filled(snapshot: dict, sources: dict, decision: str = "source_checked", note: str = "", only: set[str] | None = None) -> list[dict]:
    rows = rv.build_sheet(snapshot, sources)
    for row in rows:
        if only is None or row["claim_id"] in only:
            row["decision"], row["note"] = decision, note
    return rows


def session(snapshot, rows, **kw) -> dict:
    args = {**REVIEWER, "author": "claude-code-d1b-draft", "clock": FIXED, **kw}
    return rv.session_from_sheet(snapshot, rows, **args)


def record_with(snapshot, *sessions) -> dict:
    return {"workflow_id": snapshot["workflow_id"], "revision": snapshot["revision"], "sessions": list(sessions)}


# --- sheet -----------------------------------------------------------------------


def test_sheet_has_one_row_per_claim(snapshot, sources):
    rows = rv.build_sheet(snapshot, sources)
    assert [r["claim_id"] for r in rows] == [c["claim_id"] for c in snapshot["claims"]]
    assert all(r["decision"] == "" and r["fingerprint"] for r in rows)


def test_sheet_shows_verbatim_quotes_and_where_the_claim_sits(snapshot, sources):
    row = next(r for r in rv.build_sheet(snapshot, sources) if "shoulder bolt is attached" in r["claim"])
    assert '"tighten it so now we will install the shoulder boat' in row["evidence"], "quote must stay verbatim"
    assert row["step"].startswith("7. ") and row["field"] == "action"


def test_watch_link_jumps_to_the_cue(snapshot, sources):
    row = next(r for r in rv.build_sheet(snapshot, sources) if r["claim"] == "The presenter says to press E-stop.")
    assert row["watch"] == "https://www.youtube.com/watch?v=cs-BvWsKXyU&t=23s"


def test_relation_claim_is_labelled_as_a_relation(snapshot, sources):
    row = next(r for r in rv.build_sheet(snapshot, sources) if r["field"] == "relation")
    assert row["step"] == "requires: step 6 -> step 7"


def test_corrected_cue_shows_the_raw_caption_next_to_it(sources):
    draft = {
        "workflow_id": "REAL_WF_9997", "revision": 1, "dataset_split": "dev", "title": "t", "language": "en",
        "created_at": "2026-09-12T00:00:00Z", "source_ids": ["SRC_HAAS_0001"], "scope": "test",
        "attribution": {"label": "narrator", "kind": "speaker"}, "context": {},
        "steps": [{"title": "s", "fields": {"action": [
            {"text": "Check the gap.", "evidence": [["SRC_HAAS_0001:C0021"]], "explanation": "x"}]}}],
    }
    row = rv.build_sheet(cw.compile_draft(draft), sources)[0]
    assert "(corrected caption)" in row["evidence"] and "(raw caption)" in row["evidence"]
    assert "20,000 meter" in row["evidence"]


def test_sheet_round_trips_through_write_and_read(snapshot, sources, tmp_path):
    rows = filled(snapshot, sources, only={"REAL_WF_0001_CL_001"})
    back = rv.read_sheet(rv.write_sheet(rows, tmp_path / "sheet.csv"))
    assert [r["claim_id"] for r in back] == [r["claim_id"] for r in rows]
    assert back[0]["decision"] == "source_checked"
    assert back[0]["evidence"] == rows[0]["evidence"], "verbatim quotes with '\"' must survive the CSV"


def test_excel_semicolon_sheet_is_read_back(snapshot, sources, tmp_path):
    """Excel in some locales saves ';'-separated CSV with a BOM and CRLF line endings."""
    import csv
    import io

    rows = filled(snapshot, sources, only={"REAL_WF_0001_CL_001"})
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=rv.SHEET_COLUMNS, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    path = tmp_path / "sheet.csv"
    path.write_bytes(out.getvalue().encode("utf-8-sig"))
    back = rv.read_sheet(path)
    assert back[0]["claim_id"] == "REAL_WF_0001_CL_001" and back[0]["decision"] == "source_checked"
    assert back[0]["fingerprint"] == rows[0]["fingerprint"]


# --- recording -------------------------------------------------------------------


def test_only_filled_rows_are_recorded(snapshot, sources):
    s = session(snapshot, filled(snapshot, sources, only={"REAL_WF_0001_CL_001", "REAL_WF_0001_CL_002"}))
    assert [d["claim_id"] for d in s["decisions"]] == ["REAL_WF_0001_CL_001", "REAL_WF_0001_CL_002"]
    assert s["reviewer_id"] == "d1c-reviewer" and s["reviewed_at"] == "2026-09-12T09:00:00Z"


def test_rejection_needs_a_note(snapshot, sources):
    with pytest.raises(rv.ReviewError, match="needs a note"):
        session(snapshot, filled(snapshot, sources, decision="rejected", only={"REAL_WF_0001_CL_001"}))


def test_unknown_decision_is_refused(snapshot, sources):
    with pytest.raises(rv.ReviewError, match="decision must be one of"):
        session(snapshot, filled(snapshot, sources, decision="ok", only={"REAL_WF_0001_CL_001"}))


def test_expert_validation_cannot_come_through_the_source_sheet(snapshot, sources):
    with pytest.raises(rv.ReviewError, match="decision must be one of"):
        session(snapshot, filled(snapshot, sources, decision="expert_validated", only={"REAL_WF_0001_CL_001"}))


def test_empty_sheet_is_refused(snapshot, sources):
    with pytest.raises(rv.ReviewError, match="no decisions"):
        session(snapshot, rv.build_sheet(snapshot, sources))


def test_duplicate_row_is_refused(snapshot, sources):
    rows = filled(snapshot, sources, only={"REAL_WF_0001_CL_001"})
    rows.append(dict(rows[0]))
    with pytest.raises(rv.ReviewError, match="twice"):
        session(snapshot, rows)


def test_reviewer_identity_is_required(snapshot, sources):
    with pytest.raises(rv.ReviewError, match="who checked"):
        session(snapshot, filled(snapshot, sources, only={"REAL_WF_0001_CL_001"}), reviewer_role=" ")


def test_author_cannot_check_their_own_draft(snapshot, sources):
    rows = filled(snapshot, sources, only={"REAL_WF_0001_CL_001"})
    with pytest.raises(rv.ReviewError, match="someone else"):
        session(snapshot, rows, reviewer_id="Claude-Code-D1B-Draft")
    s = session(snapshot, rows, reviewer_id="claude-code-d1b-draft", allow_self_review=True)
    assert s["self_review"] and s["decisions"][0]["note"].startswith("(self-review)")


def test_sheet_generated_before_a_draft_change_is_refused(draft, snapshot, sources):
    rows = filled(snapshot, sources, only={"REAL_WF_0001_CL_002"})
    changed = copy.deepcopy(draft)
    changed["steps"][0]["fields"]["action"][0]["text"] = "The presenter says to set the rapids to 25%."
    with pytest.raises(rv.ReviewError, match="changed since this sheet was generated"):
        session(cw.compile_draft(changed), rows)


# --- applying --------------------------------------------------------------------


def test_merged_reviews_become_events_and_pass_the_validator(snapshot, sources):
    s = session(snapshot, filled(snapshot, sources))
    merged = rv.merge_reviews(snapshot, record_with(snapshot, s))
    assert {c["source_review"] for c in merged["claims"]} == {"source_checked"}
    assert len(merged["review_events"]) == len(merged["claims"])
    event = merged["review_events"][0]
    assert (event["review_id"], event["reviewer_id"], event["dimension"]) == ("REAL_WF_0001_RV_001", "d1c-reviewer", "source")
    report = cw.check_snapshot(merged).report
    assert report.ok, "\n".join(str(i) for i in report.errors)


def test_later_session_overrides_but_history_is_kept(snapshot, sources):
    first = session(snapshot, filled(snapshot, sources, decision="rejected", note="quote cut mid-sentence", only={"REAL_WF_0001_CL_001"}))
    second = session(snapshot, filled(snapshot, sources, only={"REAL_WF_0001_CL_001"}), reviewer_id="d1c-second")
    merged = rv.merge_reviews(snapshot, record_with(snapshot, first, second))
    claim = next(c for c in merged["claims"] if c["claim_id"] == "REAL_WF_0001_CL_001")
    assert claim["source_review"] == "source_checked"
    assert [e["decision"] for e in merged["review_events"]] == ["rejected", "source_checked"]


def test_claim_changed_after_review_is_stale(draft, snapshot, sources):
    rec = record_with(snapshot, session(snapshot, filled(snapshot, sources)))
    changed = copy.deepcopy(draft)
    changed["steps"][0]["fields"]["action"][0]["text"] = "The presenter says to set the rapids to 25%."
    new_snapshot = cw.compile_draft(changed)
    assert rv.review_status(new_snapshot, rec)["stale"] == ["REAL_WF_0001_CL_002"]
    with pytest.raises(rv.ReviewError, match="re-check them: REAL_WF_0001_CL_002"):
        rv.merge_reviews(new_snapshot, rec)


def test_re_reviewing_a_changed_claim_clears_the_stale_state(draft, snapshot, sources):
    rec = record_with(snapshot, session(snapshot, filled(snapshot, sources)))
    changed = copy.deepcopy(draft)
    changed["steps"][0]["fields"]["action"][0]["text"] = "The presenter says to set the rapids to 25%."
    new_snapshot = cw.compile_draft(changed)
    again = session(new_snapshot, filled(new_snapshot, sources, only={"REAL_WF_0001_CL_002"}))
    rec["sessions"].append(again)
    assert rv.review_status(new_snapshot, rec)["stale"] == []
    assert rv.merge_reviews(new_snapshot, rec)["claims"][1]["source_review"] == "source_checked"


def test_fingerprint_ignores_ids_but_not_content(snapshot):
    evidence = {e["evidence_id"]: e for e in snapshot["evidence"]}
    claim = snapshot["claims"][0]
    renamed = dict(claim, claim_id="OTHER")
    assert rv.claim_fingerprint(renamed, evidence) == rv.claim_fingerprint(claim, evidence)
    moved = copy.deepcopy(evidence)
    moved[claim["evidence_links"][0]["evidence_id"]]["locator"]["end_ms"] += 1000
    assert rv.claim_fingerprint(claim, moved) != rv.claim_fingerprint(claim, evidence)


# --- promotion -------------------------------------------------------------------


@pytest.fixture
def promote_env(draft, tmp_path) -> dict:
    draft_path = tmp_path / "REAL_WF_0001.r1.draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    return {"draft_path": draft_path, "reviews_dir": tmp_path / "reviews", "workflows_root": tmp_path / "workflows"}


def test_promotion_waits_for_a_complete_review(promote_env, snapshot, sources):
    with pytest.raises(rv.ReviewError, match="39 claim\\(s\\) pending"):
        rv.promote(promote_env["draft_path"], reviews_dir=promote_env["reviews_dir"], workflows_root=promote_env["workflows_root"])
    assert not promote_env["workflows_root"].exists()


def test_promotion_refuses_rejected_claims(promote_env, snapshot, sources):
    rows = filled(snapshot, sources)
    rows[0]["decision"], rows[0]["note"] = "rejected", "context is broader than the cue"
    rv.append_session(rv.load_record("REAL_WF_0001", 1, promote_env["reviews_dir"]), session(snapshot, rows), promote_env["reviews_dir"])
    with pytest.raises(rv.ReviewError, match="1 rejected"):
        rv.promote(promote_env["draft_path"], reviews_dir=promote_env["reviews_dir"], workflows_root=promote_env["workflows_root"])


def test_fully_reviewed_draft_is_promoted_for_the_exporter(promote_env, snapshot, sources):
    rv.append_session(rv.load_record("REAL_WF_0001", 1, promote_env["reviews_dir"]), session(snapshot, filled(snapshot, sources)), promote_env["reviews_dir"])
    path, status = rv.promote(promote_env["draft_path"], reviews_dir=promote_env["reviews_dir"], workflows_root=promote_env["workflows_root"])
    assert path == promote_env["workflows_root"] / "dev" / "REAL_WF_0001.r1.json"
    assert status["source_checked"] == 39
    promoted = json.loads(path.read_text(encoding="utf-8"))
    assert cw.check_snapshot(promoted).report.ok


def test_promotion_never_overwrites_a_published_revision(promote_env):
    # #44: a feedback submit can publish rN before an older rN draft is promoted.
    published = promote_env["workflows_root"] / "dev" / "REAL_WF_0001.r1.json"
    published.parent.mkdir(parents=True)
    published.write_text('{"from": "feedback"}\n', encoding="utf-8")
    with pytest.raises(rv.ReviewError, match="REAL_WF_0001@r1 is already published"):
        rv.promote(promote_env["draft_path"], allow_incomplete=True,
                   reviews_dir=promote_env["reviews_dir"], workflows_root=promote_env["workflows_root"])
    assert published.read_text(encoding="utf-8") == '{"from": "feedback"}\n'


def test_allow_incomplete_promotes_with_pending_claims_left_pending(promote_env, snapshot, sources):
    rv.append_session(rv.load_record("REAL_WF_0001", 1, promote_env["reviews_dir"]),
                      session(snapshot, filled(snapshot, sources, only={"REAL_WF_0001_CL_001"})), promote_env["reviews_dir"])
    path, _ = rv.promote(promote_env["draft_path"], allow_incomplete=True,
                         reviews_dir=promote_env["reviews_dir"], workflows_root=promote_env["workflows_root"])
    states = [c["source_review"] for c in json.loads(path.read_text(encoding="utf-8"))["claims"]]
    assert states.count("source_checked") == 1 and states.count("pending") == 38


def test_cli_flow_sheet_apply_status_promote(monkeypatch, tmp_path, capsys):
    """The path D1-C actually takes, end to end, without touching the repo."""
    import csv

    repo_dev = cw.REPO_ROOT / "data" / "workflows" / "dev"
    existed_before = repo_dev.exists()
    before = {p.relative_to(repo_dev): p.read_bytes() for p in repo_dev.rglob("*") if p.is_file()}
    monkeypatch.setattr(rv, "REVIEWS_DIR", tmp_path / "reviews")
    monkeypatch.setattr(rv, "WORKFLOWS_ROOT", tmp_path / "workflows")
    draft = str(DRAFT_PATH)

    assert rv.main(["sheet", draft]) == 0
    sheet = tmp_path / "reviews" / "REAL_WF_0001.r1.sheet.csv"
    rows = rv.read_sheet(sheet)
    for row in rows:
        row["decision"] = "source_checked"
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:  # as a spreadsheet would save it
        writer = csv.DictWriter(f, fieldnames=rv.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    assert rv.main(["apply", draft, str(sheet), "--reviewer-id", "claude-code-d1b-draft", "--reviewer-role", "D1-C"]) == 1
    assert "someone else" in capsys.readouterr().err

    assert rv.main(["apply", draft, str(sheet), "--reviewer-id", "d1c-reviewer", "--reviewer-role", "D1-C"]) == 0
    assert rv.main(["status", draft]) == 0
    assert "39 source_checked, 0 rejected, 0 pending, 0 stale" in capsys.readouterr().out

    assert rv.main(["promote", draft]) == 0
    promoted = tmp_path / "workflows" / "dev" / "REAL_WF_0001.r1.json"
    assert cw.check_snapshot(json.loads(promoted.read_text(encoding="utf-8"))).report.ok
    assert repo_dev.exists() == existed_before, "the test must not create the repo's dev store"
    assert {p.relative_to(repo_dev): p.read_bytes() for p in repo_dev.rglob("*") if p.is_file()} == before


def test_the_committed_draft_has_been_source_checked(snapshot):
    """D1-A keyframe-evidence hardening (2026-09-14): the compiler bug fix that makes a
    keyframe's locator come from the verified media inventory instead of a fabricated
    transcript-cue span changed REAL_WF_0001_CL_021's evidence content, so the review
    system correctly marks it stale rather than still source_checked -- it is exactly the
    claim REAL_WF_0001.r2 (supersedes_revision=1) reworded to stop asserting an unverifiable
    component identity ("cam follower") and rotation from a still frame. r1's published
    dev/REAL_WF_0001.r1.json is untouched; this recompile of the draft is what would happen
    if r1 were re-reviewed today, which is why it goes stale rather than staying checked.
    """
    status = rv.review_status(snapshot, rv.load_record("REAL_WF_0001", 1))
    assert status["source_checked"] == 38
    assert status["stale"] == ["REAL_WF_0001_CL_021"]
    assert status["rejected"] == status["pending"] == []
