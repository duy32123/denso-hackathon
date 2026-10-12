"""Compare PR #53 code with current fixes using retained real translations.

Offline development diagnostics only. No synthetic vectors, fabricated translation,
API generation, parameter sweep, or approval of expanded-corpus negative labels.
"""
import argparse
import json
import subprocess
import sys
import types
from pathlib import Path

from knowflow_contracts.models import QueryRequest
from retrieval.evaluation.harness import load_questions, score_ranking
from retrieval.indexing.search_index import digest, read_corpus, require_index
from scripts.benchmark_knowflow.audit import sha_file
from scripts.benchmark_knowflow.__main__ import measurement_files
from retrieval.retrieval.engine import retrieve, RetrievalConfig
from retrieval.retrieval.query import TranslationError

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "4a18533"


def original_retriever():
    names = ["query", "relevance", "engine"]
    previous = {f"retrieval.retrieval.{name}": sys.modules.get(f"retrieval.retrieval.{name}") for name in names}
    try:
        for name in names:
            full = f"retrieval.retrieval.{name}"
            module = types.ModuleType(full)
            module.__package__ = "retrieval.retrieval"
            module.__file__ = str(ROOT / f"retrieval/retrieval/{name}.py")
            sys.modules[full] = module
            code = subprocess.check_output(["git", "show", f"{BASE_COMMIT}:retrieval/retrieval/{name}.py"], cwd=ROOT).decode("utf-8")
            exec(compile(code, module.__file__, "exec"), module.__dict__)
        return sys.modules["retrieval.retrieval.engine"].retrieve
    finally:
        for name, module in previous.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)


class RetainedTranslation:
    config = {"provider": "gemini", "model": "gemini-3.5-flash-lite", "prompt_version": "q2en-2",
              "diagnostic": "retained_real_full_run_translation_not_live_q2en_3"}
    def __init__(self, rows):
        self.texts = {}
        for row in rows:
            translation = ((row.get("retrieval") or {}).get("trace", {}).get("query_translation") or {}).get("text")
            if row["arm"] == "A_knowflow" and translation:
                key = row["question"]
                hints = row["context"].get("symptoms", []) + row["context"].get("components", [])
                if hints:
                    key += "\n" + "; ".join(hints)
                self.texts[key] = translation

    def to_english(self, text):
        if text not in self.texts:
            raise TranslationError("No retained real translation; diagnostic records a cache miss")
        return self.texts[text]


def run(db, destination):
    destination.mkdir(parents=True, exist_ok=False)
    manifest = require_index(read_corpus(db, "real", "dev"))[0]
    code_hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha_file(p) for p in measurement_files()}
    rows = [json.loads(line) for line in (ROOT / "benchmarks/results/20261011_real_dev/rows.jsonl").read_text(encoding="utf-8").splitlines()]
    translator = RetainedTranslation(rows)
    original = original_retriever()
    questions, qhash = load_questions(ROOT / "data/eval/haas_real_dev.retrieval.v0.jsonl")
    outputs = []
    for q in questions:
        request = QueryRequest(question=q.question, context=q.context, mode="real", dataset_split="dev")
        for version, fn in [("PR53", original), ("component_alarm_fix", retrieve)]:
            result, error = None, None
            try:
                result = fn(db, request, config=RetrievalConfig(strategy="lexical"), translator=translator)
            except Exception as exc:
                error = type(exc).__name__
            scores = None
            if q.scored and result:
                ranked = [(s["workflow_id"], s["revision"], s["step_id"]) for s in result["steps"]]
                scores = score_ranking(ranked, [{r.key for r in u} for u in q.gold_units], 5)
            outputs.append({"question_id": q.question_id, "version": version, "question": q.question,
                "expected_status": str(q.expected_status), "expected_retrieval_status": q.expected_retrieval_status,
                "scores": scores, "result": result, "error_class": error})
    path = destination / "rows.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in outputs), encoding="utf-8")
    stats = {}
    for version in ["PR53", "component_alarm_fix"]:
        selected = [r for r in outputs if r["version"] == version]
        scored = [r["scores"] for r in selected if r["scores"] is not None]
        stats[version] = {"planned": len(selected), "completed": sum(r["result"] is not None for r in selected),
                         "cache_misses_or_errors": [{"qid": r["question_id"], "error": r["error_class"]} for r in selected if r["error_class"]],
                         "recall_denominator": len(scored), "recall_at_5": sum(s["recall"] for s in scored) / len(scored),
                         "mrr_at_5": sum(s["reciprocal_rank"] for s in scored) / len(scored)}
    changed = []
    for old, new in zip(outputs[::2], outputs[1::2], strict=True):
        def signature(row):
            result = row["result"] or {}
            return [result.get("status"), (result.get("selected_workflow") or {}).get("workflow_id"),
                    [s["step_id"] for s in result.get("steps", [])]]
        if signature(old) != signature(new):
            changed.append({"question_id": old["question_id"], "before": signature(old), "after": signature(new),
                            "before_scores": old["scores"], "after_scores": new["scores"]})
    summary = {"development_diagnostic_only": True, "negative_label_review_pending": True, "api_calls": 0,
               "embedding_used": False, "translation_origin": "actual retained 20261011 A provider outputs",
               "not_measurement_of_current_translation_prompt": True, "questions_sha256": qhash,
               "base_commit": BASE_COMMIT, "stats": stats, "changed": changed,
               "code_sha256_at_start": code_hashes, "index_manifest_at_start": manifest,
               "translation_source_sha256": sha_file(ROOT / "benchmarks/results/20261011_real_dev/rows.jsonl"),
               "no_answer_accuracy_measured": True, "holdout_opened": False}
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stats": stats, "changed_question_ids": [r["question_id"] for r in changed]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="out/web/real_dev_4a18533.sqlite")
    parser.add_argument("--destination", default="benchmarks/diagnostics/20261012_expanded_fixes")
    args = parser.parse_args()
    run(Path(args.db), Path(args.destination))
