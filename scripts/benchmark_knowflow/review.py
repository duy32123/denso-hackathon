"""Import independent semantic verdicts. Does not call AI or modify gold/answers."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from retrieval.indexing.search_index import digest
from .report import read_jsonl, ratio


def flag(text):
    if text.casefold().strip() not in ("true", "false"):
        raise ValueError("Verdict flags must be true or false")
    return text.casefold().strip() == "true"


def import_reviews(rows, sheets):
    answers = {(r["arm"], r["question_id"]): r for r in rows}
    seen, graded = set(), []
    for sheet in sheets:
        if not sheet.get("reviewer_kind", "").strip():
            continue
        key = (sheet["arm"], sheet["question_id"])
        if key in seen or key not in answers:
            raise ValueError("Duplicate or unknown review row")
        seen.add(key)
        row = answers[key]
        if row["http_status"] != 200:
            raise ValueError("An API error has no answer to grade")
        body = row["response"]
        actual = digest([body["status"], body["answer"], body["citations"]])
        if sheet["answer_sha256"] != row["answer_sha256"] or actual != row["answer_sha256"]:
            raise ValueError("Stale or tampered answer hash")
        if sheet["reviewer_kind"] not in ("human", "ai"):
            raise ValueError("Explicit reviewer_kind must be human or ai")
        if not sheet["reviewer_id"].strip() or not sheet["reviewed_at"].strip():
            raise ValueError("Named reviewer and timestamp required")
        supported = json.loads(sheet["citations_supported_json"])
        if (not isinstance(supported, list) or len(supported) != len(body["citations"])
                or any(type(value) is not bool for value in supported)):
            raise ValueError("Citation verdicts must be booleans in exact citation order")
        graded.append({"arm": key[0], "question_id": key[1], "answer_sha256": actual,
                       "reviewer_kind": sheet["reviewer_kind"], "reviewer_id": sheet["reviewer_id"],
                       "reviewed_at": sheet["reviewed_at"], "answers_question": flag(sheet["answers_question"]),
                       "conditions_correct": flag(sheet["conditions_correct"]),
                       "source_supported": flag(sheet["source_supported"]),
                       "citations_supported": supported, "note": sheet.get("note", "")})
    summaries = {}
    for arm in sorted({r["arm"] for r in rows}):
        human = [v for v in graded if v["arm"] == arm and v["reviewer_kind"] == "human"]
        answered = [v for v in human if answers[(arm, v["question_id"])]["status"] == "answered"]
        citation_flags = [mechanic["valid"] and semantic for v in human
            for mechanic, semantic in zip(answers[(arm, v["question_id"])]["citation_checks"], v["citations_supported"], strict=True)]
        summaries[arm] = {"human_reviewed_questions": len(human), "human_reviewed_answered_questions": len(answered),
            "ai_assisted_reviewed_questions": sum(v["arm"] == arm and v["reviewer_kind"] == "ai" for v in graded),
            "answers_question": ratio(sum(v["answers_question"] for v in answered), len(answered)),
            "conditions_correct": ratio(sum(v["conditions_correct"] for v in answered), len(answered)),
            "source_supported": ratio(sum(v["source_supported"] for v in answered), len(answered)),
            "citation_correctness": ratio(sum(citation_flags), len(citation_flags))}
    return graded, summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--sheet", required=True, type=Path)
    args = parser.parse_args()
    with args.sheet.open(encoding="utf-8-sig", newline="") as stream:
        verdicts, summary = import_reviews(read_jsonl(args.run_dir / "rows.jsonl"), list(csv.DictReader(stream)))
    (args.run_dir / "semantic_verdicts.jsonl").write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in verdicts), encoding="utf-8")
    (args.run_dir / "semantic_review_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
