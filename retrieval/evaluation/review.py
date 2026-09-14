"""Human check of evaluation gold: export a CSV sheet, record decisions into the JSONL.

Same conventions as acquisition/extraction/review: Excel-friendly CSV, a fingerprint
per row so a question edited after export is never approved blind, and a reviewer
who is not the labeler. One invalid row rejects the whole sheet. An AI pass (e.g.
Codex) is recorded apart as ai_reviewed: it helps the human, it does not replace one.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from retrieval.indexing.search_index import canonical, read_corpus
from .harness import EvalQuestion, EvaluationError, Label, check_gold, load_questions

SHEET_COLUMNS = ["question_id", "category", "question", "context", "gold", "label", "label_note",
                 "expected_status", "expected_retrieval_status", "gold_step_ids", "decision", "note", "fingerprint"]
DECISIONS = ("ok", "fix", "drop")
REVIEWER_KINDS = ("human", "ai")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fingerprint(raw: dict) -> str:
    """Everything except the label: a changed question or gold needs a fresh sheet."""
    content = {key: value for key, value in raw.items() if key != "label"}
    return hashlib.sha256(canonical(content).encode("utf-8")).hexdigest()[:16]


def _read(questions_path) -> tuple[list[EvalQuestion], list[str]]:
    questions, _ = load_questions(questions_path)
    lines = [line for line in Path(questions_path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return questions, lines


def _workflows(db, questions: list[EvalQuestion]) -> dict:
    spaces = {(str(q.source_type), str(q.dataset_split)) for q in questions}
    if len(spaces) != 1:
        raise EvaluationError("One question file must cover exactly one corpus/split")
    workflows = read_corpus(db, *spaces.pop())["workflows"]
    check_gold(questions, workflows)
    return workflows


def format_gold_ids(units: list[list[dict]]) -> str:
    """'|' separates interchangeable Steps of one unit, ';' separates units."""
    return " ; ".join(" | ".join(ref["step_id"] for ref in unit) for unit in units)


def parse_gold_ids(text: str, steps: dict[str, tuple[str, int]]) -> list[list[dict]]:
    units = []
    for part in text.split(";"):
        unit = []
        for step_id in filter(None, (s.strip() for s in part.split("|"))):
            if step_id not in steps:
                raise EvaluationError(f"unknown step_id '{step_id}'")
            workflow_id, revision = steps[step_id]
            unit.append({"workflow_id": workflow_id, "revision": revision, "step_id": step_id})
        if unit:
            units.append(unit)
    return units


def _step_text(workflow, step_id: str) -> str:
    step = next(s for s in workflow.steps if s.step_id == step_id)
    claims = {c.claim_id: c for c in workflow.claims}
    lines = [f"{step_id} (#{step.display_order}) {step.title}"]
    for field, value in step.fields.model_dump().items():
        lines.extend(f"    {field}: {claims[cid].text}" for cid in value["claim_ids"])
    return "\n".join(lines)


def _gold_text(q: EvalQuestion, workflows: dict) -> str:
    blocks = [f"[{n}] " + "\n  OR ".join(_step_text(workflows[ref.workflow_id], ref.step_id) for ref in unit)
              for n, unit in enumerate(q.gold_units, start=1)]
    blocks += [f"workflow {ref.workflow_id} r{ref.revision}: {workflows[ref.workflow_id].title}"
               for ref in q.gold_workflows]
    return "\n".join(blocks) or "(no gold: retrieval is expected to abstain or ask)"


def _label_text(label: Label) -> tuple[str, str]:
    status = {"draft": "draft", "ai_reviewed": f"ai_reviewed by {label.ai_reviewed_by}",
              "reviewed": f"reviewed by {label.reviewed_by}"}[label.status]
    notes = [label.note,
             label.ai_review_note and f"[AI {label.ai_reviewed_by}] {label.ai_review_note}",
             label.review_note and f"[{label.reviewed_by}] {label.review_note}"]
    return status, "\n".join(filter(None, notes))


def build_sheet(db, questions_path) -> list[dict]:
    questions, lines = _read(questions_path)
    workflows = _workflows(db, questions)
    rows = []
    for q, line in zip(questions, lines, strict=True):
        raw = json.loads(line)
        label, label_note = _label_text(q.label)
        rows.append({
            "question_id": q.question_id, "category": f"{q.category} / {q.language} / {q.intent}",
            "question": q.question,
            "context": json.dumps(raw["context"], ensure_ascii=False) if raw["context"] else "",
            "gold": _gold_text(q, workflows), "label": label, "label_note": label_note,
            "expected_status": raw["expected_status"],
            "expected_retrieval_status": raw["expected_retrieval_status"],
            "gold_step_ids": format_gold_ids(raw.get("gold_units", [])),
            "decision": "", "note": "", "fingerprint": fingerprint(raw),
        })
    return rows


def write_sheet(rows: list[dict], path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM so Excel opens UTF-8 correctly
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_sheet(path) -> list[dict]:
    """Accepts what Excel or Google Sheets saves: with or without BOM, ',' ';' or tab."""
    text = Path(path).read_text(encoding="utf-8-sig")
    delimiter = max(",;\t", key=text.split("\n", 1)[0].count)
    rows = list(csv.DictReader(io.StringIO(text), dialect=csv.excel, delimiter=delimiter))
    missing = {"question_id", "fingerprint", "decision", "note", "expected_status",
               "expected_retrieval_status", "gold_step_ids"} - set(rows[0] if rows else {})
    if missing:
        raise EvaluationError(f"{Path(path).name}: sheet is missing column(s) {sorted(missing)}")
    return [{k: (v or "").strip() for k, v in row.items() if k is not None} for row in rows]


def apply_sheet(db, questions_path, sheet_path, *, reviewer_id: str, reviewer_kind: str = "human",
                clock: Callable[[], str] = _utc_now) -> dict:
    """ok = labels correct; fix = edited columns + note; drop = remove question + note (human only)."""
    reviewer = reviewer_id.strip()
    if not reviewer:
        raise EvaluationError("reviewer_id is required: a review must say who checked")
    if reviewer_kind not in REVIEWER_KINDS:
        raise EvaluationError(f"reviewer_kind must be one of {REVIEWER_KINDS}")
    questions, lines = _read(questions_path)
    by_id = {q.question_id: (q, json.loads(line)) for q, line in zip(questions, lines, strict=True)}
    steps = {s.step_id: (wf.workflow_id, wf.revision) for wf in _workflows(db, questions).values() for s in wf.steps}
    errors, changes, decided = [], {}, Counter()
    for n, row in enumerate(read_sheet(sheet_path), start=2):  # line 1 is the header
        decision, qid = row.get("decision", "").lower(), row.get("question_id", "")
        where = f"line {n} {qid}"
        if not decision:
            continue
        if decision not in DECISIONS:
            errors.append(f"{where}: decision must be one of {DECISIONS} or empty, got '{decision}'")
            continue
        if qid not in by_id or qid in changes:
            errors.append(f"{where}: unknown or repeated question_id")
            continue
        q, raw = by_id[qid]
        if row.get("fingerprint") != fingerprint(raw):
            errors.append(f"{where}: question changed since this sheet was generated; regenerate the sheet")
            continue
        if q.label.labeled_by.casefold() == reviewer.casefold():
            errors.append(f"{where}: {reviewer} labeled this question; the check must be done by someone else")
            continue
        if reviewer_kind == "ai" and q.label.status == "reviewed":
            errors.append(f"{where}: already human-reviewed; an AI pass cannot replace it")
            continue
        if reviewer_kind == "ai" and decision == "drop":
            errors.append(f"{where}: an AI pass cannot drop questions; leave a note for the human reviewer")
            continue
        note = row.get("note", "")
        if decision != "ok" and not note:
            errors.append(f"{where}: '{decision}' needs a note saying why")
            continue
        if decision == "drop":
            changes[qid] = None
            decided[decision] += 1
            continue
        try:
            edited = {"expected_status": row.get("expected_status", ""),
                      "expected_retrieval_status": row.get("expected_retrieval_status", ""),
                      "gold_units": parse_gold_ids(row.get("gold_step_ids", ""), steps)}
        except EvaluationError as exc:
            errors.append(f"{where}: {exc}")
            continue
        changed = any(raw.get(key, []) != value for key, value in edited.items())
        if decision == "ok" and changed:
            errors.append(f"{where}: values were edited but decision=ok; use 'fix' with a note")
            continue
        if decision == "fix" and not changed:
            errors.append(f"{where}: decision=fix but no editable column changed")
            continue
        stamp = ({"status": "reviewed", "reviewed_by": reviewer, "reviewed_at": clock(), "review_note": note}
                 if reviewer_kind == "human" else
                 {"status": "ai_reviewed", "ai_reviewed_by": reviewer, "ai_reviewed_at": clock(),
                  "ai_review_note": note})
        updated = {**raw, **edited, "label": {**raw["label"], **stamp}}
        try:
            EvalQuestion.model_validate_json(json.dumps(updated))
        except ValidationError as exc:
            errors.append(f"{where}: {exc.errors()[0]['msg']}")
            continue
        changes[qid] = updated
        decided[decision] += 1
    if errors:
        raise EvaluationError("sheet rejected, nothing recorded:\n  " + "\n  ".join(errors))
    if not changes:
        raise EvaluationError("the sheet has no decisions; fill the 'decision' column")
    kept = []
    for q, line in zip(questions, lines, strict=True):
        if q.question_id not in changes:
            kept.append(line)  # untouched questions stay byte-identical
        elif changes[q.question_id] is not None:
            kept.append(json.dumps(changes[q.question_id], ensure_ascii=False))
    Path(questions_path).write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    return {"reviewed": decided["ok"] + decided["fix"], "fixed": decided["fix"],
            "dropped": decided["drop"], "questions": len(kept)}
