"""Gold review sheet: export, Excel round trip, and refusal of unsafe decisions."""

import csv
import json

import pytest

from conftest import FIXTURE_ROOT, read_bundle, write_bundle
from retrieval.evaluation.harness import EvaluationError, load_questions, run_evaluation
from retrieval.evaluation.review import SHEET_COLUMNS, apply_sheet, build_sheet
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index

WF = "SYN_WF_0001"
NOW = "2026-09-14T00:00:00+00:00"


def clock():
    return NOW


def question(qid, text, units):
    return {"question_id": qid, "source_type": "synthetic", "dataset_split": "dev", "language": "vi",
            "category": "detail", "intent": "detail", "question": text,
            "context": {"machine_model": "DEMO_TC_A"},
            "expected_status": "answered", "expected_retrieval_status": "retrieved",
            "gold_units": [[{"workflow_id": WF, "revision": 1, "step_id": f"{WF}_{step}"} for step in unit]
                           for unit in units],
            "label": {"status": "draft", "labeled_by": "drafter"}}


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "store.sqlite"
    bundle = write_bundle(tmp_path / "bundle", read_bundle(FIXTURE_ROOT / "F01_complete"))
    import_bundle(bundle, db, source_type="synthetic", split="dev")
    path = tmp_path / "questions.jsonl"
    path.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in [
        question("Q1", "xoay chot khoa", [["ST_001"]]), question("Q2", "mo nap che", [["ST_002"]]),
    ]), encoding="utf-8")
    return db, path


def fill(tmp_path, rows, delimiter=",", **edits):
    """Save the sheet the way Excel might; edits = {question_id: {column: value}}."""
    path = tmp_path / "sheet.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS, delimiter=delimiter)
        writer.writeheader()
        writer.writerows({**row, **edits.get(row["question_id"], {})} for row in rows)
    return path


def test_sheet_shows_claims_and_ok_marks_reviewed(tmp_path, store):
    db, path = store
    rows = build_sheet(db, path)
    assert rows[0]["gold_step_ids"] == f"{WF}_ST_001"
    assert "Khoa chot an toan" in rows[0]["gold"] and "LOCK" in rows[0]["gold"]
    before = path.read_text(encoding="utf-8").splitlines()
    sheet = fill(tmp_path, rows, delimiter=";", Q1={"decision": "ok"})
    assert apply_sheet(db, path, sheet, reviewer_id="alice", clock=clock)["reviewed"] == 1
    after = path.read_text(encoding="utf-8").splitlines()
    assert after[1] == before[1]  # untouched question stays byte-identical
    assert json.loads(after[0])["label"] == {"status": "reviewed", "labeled_by": "drafter",
                                             "reviewed_by": "alice", "reviewed_at": NOW, "review_note": ""}
    load_questions(path)


def test_fix_records_alternatives_and_drop_removes(tmp_path, store):
    db, path = store
    sheet = fill(tmp_path, build_sheet(db, path),
                 Q1={"decision": "fix", "gold_step_ids": f"{WF}_ST_001 | {WF}_ST_002", "note": "ST_002 cũng trả lời"},
                 Q2={"decision": "drop", "note": "trùng Q1"})
    assert apply_sheet(db, path, sheet, reviewer_id="alice", clock=clock) == {
        "reviewed": 1, "fixed": 1, "dropped": 1, "questions": 1}
    (q1,), _ = load_questions(path)
    assert [[ref.step_id for ref in unit] for unit in q1.gold_units] == [[f"{WF}_ST_001", f"{WF}_ST_002"]]
    assert q1.label.review_note == "ST_002 cũng trả lời"


@pytest.mark.parametrize("edit,reviewer,message", [
    ({"decision": "fix", "gold_step_ids": f"{WF}_ST_002"}, "alice", "needs a note"),
    ({"decision": "ok", "gold_step_ids": f"{WF}_ST_002"}, "alice", "use 'fix'"),
    ({"decision": "fix", "gold_step_ids": f"{WF}_ST_099", "note": "x"}, "alice", "unknown step_id"),
    ({"decision": "fix", "expected_retrieval_status": "insufficient_evidence", "note": "x"}, "alice", "must expect"),
    ({"decision": "ok"}, "drafter", "someone else"),
    ({"decision": "maybe"}, "alice", "decision must be"),
])
def test_unsafe_sheet_is_rejected_and_file_untouched(tmp_path, store, edit, reviewer, message):
    db, path = store
    before = path.read_bytes()
    sheet = fill(tmp_path, build_sheet(db, path), Q1=edit)
    with pytest.raises(EvaluationError, match=message):
        apply_sheet(db, path, sheet, reviewer_id=reviewer, clock=clock)
    assert path.read_bytes() == before


def test_ai_pass_is_kept_apart_from_the_human_check(tmp_path, store):
    db, path = store
    rows = build_sheet(db, path)
    with pytest.raises(EvaluationError, match="cannot drop"):
        apply_sheet(db, path, fill(tmp_path, rows, Q2={"decision": "drop", "note": "x"}),
                    reviewer_id="codex", reviewer_kind="ai", clock=clock)
    sheet = fill(tmp_path, rows, Q1={"decision": "ok", "note": "khớp nguồn"}, Q2={"decision": "ok"})
    apply_sheet(db, path, sheet, reviewer_id="codex", reviewer_kind="ai", clock=clock)
    build_index(db, mode="synthetic", split="dev")
    report, _ = run_evaluation(db, path, mode="synthetic", split="dev", strategies=["lexical"])
    assert report["gold_labels"] == {"draft": 0, "ai_reviewed": 2, "reviewed": 0} and "warning" in report
    rows = build_sheet(db, path)
    assert rows[0]["label"] == "ai_reviewed by codex" and "[AI codex] khớp nguồn" in rows[0]["label_note"]
    apply_sheet(db, path, fill(tmp_path, rows, Q1={"decision": "ok"}), reviewer_id="alice", clock=clock)
    q1 = load_questions(path)[0][0]
    assert (q1.label.status, q1.label.reviewed_by, q1.label.ai_reviewed_by) == ("reviewed", "alice", "codex")
    with pytest.raises(EvaluationError, match="cannot replace"):
        apply_sheet(db, path, fill(tmp_path, build_sheet(db, path), Q1={"decision": "ok"}),
                    reviewer_id="codex", reviewer_kind="ai", clock=clock)


def test_question_edited_after_export_needs_new_sheet(tmp_path, store):
    db, path = store
    rows = build_sheet(db, path)
    path.write_text(path.read_text(encoding="utf-8").replace("xoay chot khoa", "xoay chot"), encoding="utf-8")
    with pytest.raises(EvaluationError, match="regenerate"):
        apply_sheet(db, path, fill(tmp_path, rows, Q1={"decision": "ok"}), reviewer_id="alice", clock=clock)
