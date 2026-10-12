"""Offline comparison and AI investigation notes; never semantic approval."""
import argparse
import json
from pathlib import Path

from .report import ARMS, csv_file, infer_guard, read_jsonl


def write(run_dir, historical_dir):
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    old_summary = json.loads((historical_dir / "summary.json").read_text(encoding="utf-8"))
    rows = read_jsonl(run_dir / "rows.jsonl")
    old_rows = read_jsonl(historical_dir / "rows.jsonl")
    current = {(r["arm"], r["question_id"]): r for r in rows}
    previous = {(r["arm"], r["question_id"]): r for r in old_rows}
    comparison = {"comparison_kind": "historical_descriptive_not_causal",
                  "historical_run": historical_dir.name, "current_run": run_dir.name,
                  "historical_commit": old_summary["product_commit"],
                  "current_commit": summary["product_commit"],
                  "confounders": ["expanded corpus and annotations", "component/alarm retrieval fixes",
                      "q2en-3 translation", "shared A/C retrieval instead of independent retrieval",
                      "independent generation and rate-limit conditions"], "arms": {}}
    per_question = []
    for arm in ARMS:
        before = old_summary["summaries"][arm]
        after = summary["by_cohort"]["old_66"][arm]
        common = sorted(qid for a, qid in previous if a == arm and (arm, qid) in current)
        mismatch = [qid for qid in common if previous[arm, qid]["expected_status"] != current[arm, qid]["expected_status"]]
        if mismatch:
            raise ValueError("Historical labels differ; stratify before comparing")
        improved = [qid for qid in common if not previous[arm, qid]["status_ok"] and current[arm, qid]["status_ok"]]
        regressed = [qid for qid in common if previous[arm, qid]["status_ok"] and not current[arm, qid]["status_ok"]]
        comparison["arms"][arm] = {"matched_questions": len(common), "status_labels_changed": [],
            "historical_status_correct": before["status_accuracy"]["numerator"],
            "current_status_correct": after["status_accuracy"]["numerator"],
            "historical_retrieval": before["retrieval"], "current_retrieval": after["retrieval"],
            "improved_status_questions": improved, "regressed_status_questions": regressed,
            "historical_api_errors": before["api_errors"], "current_api_errors": after["api_errors"]}
        for qid in common:
            old, new = previous[arm, qid], current[arm, qid]
            per_question.append({"arm": arm, "question_id": qid, "language": new["language"],
                "expected_status": new["expected_status"], "historical_status": old["status"],
                "current_status": new["status"], "historical_http": old["http_status"],
                "current_http": new["http_status"], "historical_status_ok": old["status_ok"],
                "current_status_ok": new["status_ok"], "historical_recall_at_5": old["recall_at_5"],
                "current_recall_at_5": new["recall_at_5"], "current_guard": infer_guard(new),
                "historical_answer_sha256": old["answer_sha256"], "current_answer_sha256": new["answer_sha256"]})
    (run_dir / "historical_comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_file(run_dir / "historical_comparison.csv", list(per_question[0]), per_question)
    targets = {
        "HAAS_DEV_Q015": "Check component routing separately from draft abstention; grease action is not a grade specification.",
        "HAAS_DEV_Q031": "Negative grease-grade question; compare pocket-slider sources with double-arm grease specifications. Do not transfer specifications between components.",
        "HAAS_DEV_Q069": "Exact alarm lookup exception is limited to the requested alarm code and eligible source claim; status is not a human correctness verdict.",
        "HAAS_DEV_Q041": "Compare expected retrieval and expected answer separately. Check the refractometer-check source for an actual concentration percentage, rather than treating related evidence as an answer.",
        "HAAS_DEV_Q049": "Compare expected retrieval and answer separately. Check whether the cited belt inspection/conditional drive type actually supplies the requested replacement procedure.",
        "HAAS_DEV_Q039": "Supplied subsystem=SMTC differs from Q049 with empty context; preserve this filter in source review.",
        "HAAS_DEV_Q050": "Supplied subsystem=SMTC differs from Q041 with empty context; preserve this filter in source review.",
        "HAAS_DEV_Q012": "Inspect translation of reinstall/return and same-claim min_matches, plus the source condition for reinstalling the tool.",
        "HAAS_DEV_Q056": "Inspect verbose/inflected translation terms, double-arm gripper aliases and same-claim coverage. Do not tune a single global threshold on the run being reported.",
        "HAAS_DEV_Q083": "Compare numeric 21 versus spelled twenty one in the draft and cited transcript; numbers() does not normalize number words. Tap notation 1032 also needs source check; do not silently normalize dimensions.",
        "HAAS_DEV_Q005": "Check whether the rationale and prerequisite strength stay within the exact quote; compare with the old run's extra screw-access wording.",
        "HAAS_DEV_Q021": "Check singular/plural mounting-screw scope against the exact quote. Mechanically valid IDs do not prove the full claim.",
        "HAAS_DEV_Q062": "Inspect 429 retries, endpoint timeout and post-timeout provider expense; do not delete or rerun the failed task to improve scores.",
        "HAAS_DEV_Q064": "A/C may use keyframe annotation unavailable to transcript-only B. This is a modality/preprocessing difference, not an isolated graph benefit.",
    }
    notes = []
    for row in rows:
        if row["question_id"] not in targets:
            continue
        retrieval = row.get("retrieval") or {}
        notes.append({"reviewer_kind": "ai", "human_reviewed": False,
            "arm": row["arm"], "question_id": row["question_id"], "answer_sha256": row["answer_sha256"],
            "status": row["status"], "http_status": row["http_status"], "guard": infer_guard(row),
            "retrieval_status": retrieval.get("status"),
            "workflow_id": (retrieval.get("selected_workflow") or {}).get("workflow_id"),
            "expected_status": row["expected_status"], "expected_retrieval_status": row["expected_retrieval_status"],
            "translation": retrieval.get("trace", {}).get("query_translation"),
            "relevance": retrieval.get("trace", {}).get("relevance"),
            "investigation_note": targets[row["question_id"]],
            "answers_question": None, "conditions_correct": None, "source_supported": None,
            "raw_row_location": f"rows.jsonl ({row['arm']}, {row['question_id']})"})
    (run_dir / "ai_case_notes.jsonl").write_text("".join(json.dumps(n, ensure_ascii=False) + "\n" for n in notes), encoding="utf-8")
    return comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--historical-dir", default="benchmarks/results/20261011_real_dev", type=Path)
    args = parser.parse_args()
    write(args.run_dir, args.historical_dir)


if __name__ == "__main__":
    main()
