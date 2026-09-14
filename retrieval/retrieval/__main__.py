"""python -m retrieval.retrieval build|query|status."""

import argparse
import json
import sqlite3
import sys

from knowflow_contracts.models import QueryContext, QueryRequest
from retrieval.indexing.embeddings import GeminiEmbedder
from retrieval.indexing.search_index import build_index, read_corpus, require_index
from .engine import RetrievalConfig, retrieve


def main(argv=None):
    parser = argparse.ArgumentParser(description="WP2: lexical / multilingual vector / hybrid retrieval")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "query", "status"):
        sub = commands.add_parser(name)
        sub.add_argument("--db", required=True)
        sub.add_argument("--mode", choices=("real", "synthetic"), required=True)
        sub.add_argument("--split", choices=("dev", "holdout"), required=True)
        if name == "build":
            sub.add_argument("--embedding", choices=("gemini", "none"), default="gemini")
            sub.add_argument("--dimensions", type=int, choices=(768, 1536, 3072), default=768)
        if name == "query":
            sub.add_argument("question")
            sub.add_argument("--strategy", choices=("lexical", "vector", "hybrid"), default="hybrid")
            sub.add_argument("--top-k", type=int, default=5)
            sub.add_argument("--candidate-k", type=int, default=20)
            sub.add_argument("--min-cosine", type=float, default=.25)
            sub.add_argument("--intent", choices=("auto", "detail", "procedure"), default="auto")
            sub.add_argument("--summary", action="store_true", help="show compact hits; omit to include evidence and trace")
            for key in ("manufacturer", "machine-family", "machine-model", "subsystem", "task-type"):
                sub.add_argument("--" + key)
            sub.add_argument("--alarm-code", action="append", default=[])
            sub.add_argument("--component", action="append", default=[])
            sub.add_argument("--symptom", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            embedder = GeminiEmbedder(args.dimensions) if args.embedding == "gemini" else None
            try:
                result = build_index(args.db, mode=args.mode, split=args.split, embedder=embedder)
            finally:
                if embedder:
                    embedder.close()
        elif args.command == "status":
            result = require_index(read_corpus(args.db, args.mode, args.split))[0]
        else:
            context = QueryContext(
                manufacturer=args.manufacturer, machine_family=args.machine_family, machine_model=args.machine_model,
                subsystem=args.subsystem, task_type=args.task_type, alarm_codes=args.alarm_code,
                components=args.component, symptoms=args.symptom,
            )
            result = retrieve(args.db, QueryRequest(question=args.question, context=context,
                                                   mode=args.mode, dataset_split=args.split),
                              config=RetrievalConfig(strategy=args.strategy, top_k=args.top_k,
                                                     candidate_k=args.candidate_k, min_cosine=args.min_cosine,
                                                     intent=args.intent))
            if args.summary:
                result = {key: result[key] for key in (
                    "status", "index_build_id", "selected_workflow", "missing_context", "steps",
                )} | {
                    "claim_count": len(result["claims"]), "conflict_count": len(result["conflicts"]),
                    "latency_ms": result["trace"]["latency_ms"],
                }
                result["steps"] = [{key: step[key] for key in (
                    "step_id", "title", "score", "lexical_score", "vector_score",
                )} for step in result["steps"]]
    except (OSError, ValueError, sqlite3.Error, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
