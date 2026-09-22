"""Replay both relevance policies on real/dev using existing Gemini caches only.

Missing cache entries are explicit skips, never fake vectors or untranslated
fallbacks. Compare the SAME completed questions for each strategy, and report
the human-reviewed subset separately from draft diagnostic questions.

Run: python -m scripts.compare_relevance_gates
"""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from retrieval.evaluation.harness import (
    QueryCache,
    TranslationCache,
    _evaluate_one,
    check_gold,
    git_state,
    load_questions,
    summarize,
    write_run,
)
from retrieval.indexing.search_index import read_corpus, require_index
from retrieval.retrieval.engine import RetrievalConfig
from retrieval.retrieval.query import GeminiTranslator

POLICIES = ("legacy_corpus", "claim_coherence")
STRATEGIES = ("lexical", "vector", "hybrid")


class CacheMiss(RuntimeError):
    pass


class CacheOnly:
    def __init__(self, config):
        self.config = config

    def query(self, text):
        raise CacheMiss("query embedding is not cached")

    def to_english(self, text):
        raise CacheMiss("query translation is not cached")


def compare(db, questions_path, *, query_cache, translation_cache):
    questions, question_hash = load_questions(questions_path)
    if any((q.source_type, q.dataset_split) != ("real", "dev") for q in questions):
        raise ValueError("This diagnostic only accepts real/dev; holdout stays locked")
    corpus = read_corpus(db, "real", "dev")
    manifest, _ = require_index(corpus)
    check_gold(questions, corpus["workflows"])
    if manifest["embedding"] is None:
        raise ValueError("A real embedding index is required to compare all three strategies")
    embedding = QueryCache(CacheOnly(manifest["embedding"]), query_cache)
    translation = TranslationCache(CacheOnly(GeminiTranslator().config), translation_cache)
    rows, skipped = [], []
    for policy in POLICIES:
        for strategy in STRATEGIES:
            for q in questions:
                config = RetrievalConfig(strategy=strategy, intent=q.intent, relevance_policy=policy)
                try:
                    row = _evaluate_one(db, q, "real", "dev", config, embedding, translation,
                                        manifest["index_build_id"])
                    rows.append({"policy": policy, **row})
                except CacheMiss as exc:
                    skipped.append({"policy": policy, "strategy": strategy, "question_id": q.question_id,
                                    "reason": str(exc)})
    comparisons = {}
    for strategy in STRATEGIES:
        groups = {p: {r["question_id"]: r for r in rows if r["strategy"] == strategy and r["policy"] == p}
                  for p in POLICIES}
        common = sorted(set(groups[POLICIES[0]]) & set(groups[POLICIES[1]]))
        comparisons[strategy] = {
            "comparable_question_ids": common,
            "excluded_question_ids": sorted({q.question_id for q in questions} - set(common)),
            "all_cached": {p: summarize([groups[p][qid] for qid in common], 5) for p in POLICIES},
            "reviewed_only": {p: summarize([groups[p][qid] for qid in common
                                            if groups[p][qid]["label_status"] == "reviewed"], 5) for p in POLICIES},
        }
    root = Path(__file__).resolve().parents[1]
    files = ("retrieval/retrieval/relevance.py", "retrieval/retrieval/engine.py",
             "retrieval/retrieval/query.py", "scripts/compare_relevance_gates.py")
    report = {
        "run_id": "GATE_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "git": git_state(), "code_sha256": {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files},
        "source_type": "real", "dataset_split": "dev", "db": str(db),
        "index_build_id": manifest["index_build_id"], "record_build_id": manifest["record_build_id"],
        "embedding": manifest["embedding"], "translation": translation.config,
        "questions_path": str(questions_path), "questions_sha256": question_hash,
        "questions_total": len(questions), "gold_labels": dict(Counter(q.label.status for q in questions)),
        "config": asdict(RetrievalConfig()), "policies": list(POLICIES), "strategies": list(STRATEGIES),
        "query_cache": str(query_cache), "translation_cache": str(translation_cache),
        "query_embedding_calls": embedding.calls, "query_translation_calls": translation.calls,
        "skipped": skipped, "comparison": comparisons,
        "warning": "Development-set diagnostic, not a holdout result. Mixed draft-label metrics are not reportable. "
                   "Each comparison excludes cache misses from BOTH policies; these are not evaluated negatives.",
    }
    return report, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="out/retrieval/real_dev.sqlite")
    parser.add_argument("--questions", default="data/eval/haas_real_dev.retrieval.v0.jsonl")
    parser.add_argument("--query-cache", default="out/eval/query_embeddings.jsonl")
    parser.add_argument("--translation-cache", default="out/eval/query_translations.jsonl")
    parser.add_argument("--out", default="out/eval")
    args = parser.parse_args(argv)
    report, rows = compare(args.db, args.questions, query_cache=args.query_cache,
                           translation_cache=args.translation_cache)
    target = write_run(report, rows, args.out)
    print("report:", target / "report.json")
    print("skipped:", json.dumps(report["skipped"]))
    for strategy, comparison in report["comparison"].items():
        for subset in ("reviewed_only", "all_cached"):
            for policy, summary in comparison[subset].items():
                print(json.dumps({"strategy": strategy, "subset": subset, "policy": policy,
                                  "questions": summary["questions"], "recall": summary["retrieval"]["recall_at_5"],
                                  "workflow_accuracy": summary["workflow_selection"]["accuracy"],
                                  "status_accuracy": summary["status"]["accuracy"],
                                  "false_retrieved": summary["status"]["false_retrieved"],
                                  "missed": summary["status"]["missed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
