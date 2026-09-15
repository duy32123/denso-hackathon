"""python -m retrieval.evaluation run | answers | sheet | apply."""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from retrieval.generation.gemini import GeminiAnswerModel

from .answers import evaluate_answers, format_answer_summary, verdict_template
from .harness import STRATEGIES, format_summary, run_evaluation, write_run
from .review import apply_sheet, build_sheet, write_sheet


def main(argv=None):
    parser = argparse.ArgumentParser(description="WP2 retrieval evaluation and gold review")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="score lexical / vector / hybrid on one KB")
    run.add_argument("--db", required=True)
    run.add_argument("--questions", required=True)
    run.add_argument("--mode", choices=("real", "synthetic"), required=True)
    run.add_argument("--split", choices=("dev", "holdout"), required=True)
    run.add_argument("--strategy", action="append", choices=STRATEGIES, help="repeat; default: all three")
    run.add_argument("--top-k", type=int, default=5)
    run.add_argument("--candidate-k", type=int, default=20)
    run.add_argument("--min-cosine", type=float, default=.25)
    run.add_argument("--rrf-k", type=int, default=60)
    run.add_argument("--min-term-coverage", type=float, default=.10, help="relevance gate; 0 disables it")
    run.add_argument("--out", default="out/eval", help="run folder with report.json and rows.jsonl")
    run.add_argument("--query-cache", default="out/eval/query_embeddings.jsonl",
                     help="reuse query embeddings across runs (keyed by embedding config + text)")
    run.add_argument("--no-query-cache", action="store_true")
    run.add_argument("--translation-cache", default="out/eval/query_translations.jsonl",
                     help="reuse query translations across runs (keyed by translator config + text)")
    run.add_argument("--no-translation", action="store_true",
                     help="search Vietnamese questions untranslated (relevance gate is then skipped for them)")
    run.add_argument("--allow-holdout", action="store_true", help="only after the D15 pipeline lock")
    run.add_argument("--json", action="store_true", help="print the full report instead of the table")
    answers = commands.add_parser("answers", help="score the served /v1/ask answers (WP3)")
    answers.add_argument("--db", required=True)
    answers.add_argument("--questions", required=True)
    answers.add_argument("--mode", choices=("real", "synthetic"), required=True)
    answers.add_argument("--split", choices=("dev",), default="dev", help="the served path is dev only")
    answers.add_argument("--strategy", choices=STRATEGIES, default="hybrid")
    answers.add_argument("--top-k", type=int, default=5)
    answers.add_argument("--candidate-k", type=int, default=20)
    answers.add_argument("--min-cosine", type=float, default=.25)
    answers.add_argument("--rrf-k", type=int, default=60)
    answers.add_argument("--min-term-coverage", type=float, default=.10)
    answers.add_argument("--model", default=os.getenv("KNOWFLOW_ANSWER_MODEL", "gemini-3.5-flash-lite"))
    answers.add_argument("--out", default="out/eval")
    answers.add_argument("--query-cache", default="out/eval/query_embeddings.jsonl")
    answers.add_argument("--no-query-cache", action="store_true")
    answers.add_argument("--translation-cache", default="out/eval/query_translations.jsonl")
    answers.add_argument("--no-translation", action="store_true")
    answers.add_argument("--verdicts", help="human verdict JSONL; without it the support-dependent rates stay null")
    answers.add_argument("--verdict-template", metavar="REVIEWER_ID",
                         help="also write verdicts.template.jsonl for this reviewer to fill in")
    answers.add_argument("--price-input", type=float, metavar="USD_PER_MILLION",
                         help="input token price; cost stays null unless both prices are given")
    answers.add_argument("--price-output", type=float, metavar="USD_PER_MILLION")
    answers.add_argument("--json", action="store_true")
    sheet = commands.add_parser("sheet", help="export a review sheet (CSV) for the gold labels")
    sheet.add_argument("--db", required=True)
    sheet.add_argument("--questions", required=True)
    sheet.add_argument("--out", help="default: out/eval/<questions>.sheet.csv")
    record = commands.add_parser("apply", help="record a filled review sheet into the question file")
    record.add_argument("--db", required=True)
    record.add_argument("--questions", required=True)
    record.add_argument("--sheet", required=True)
    record.add_argument("--reviewer-id", required=True, help="your GitHub username, or the AI tool name")
    record.add_argument("--reviewer-kind", choices=("human", "ai"), default="human",
                        help="ai: recorded as ai_reviewed; does not count as the human gold check")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            report, rows = run_evaluation(
                args.db, args.questions, mode=args.mode, split=args.split,
                strategies=args.strategy or STRATEGIES, top_k=args.top_k, candidate_k=args.candidate_k,
                min_cosine=args.min_cosine, rrf_k=args.rrf_k, allow_holdout=args.allow_holdout,
                query_cache=None if args.no_query_cache else args.query_cache,
                min_term_coverage=args.min_term_coverage, translate=not args.no_translation,
                translation_cache=args.translation_cache,
            )
            target = write_run(report, rows, args.out)
            print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_summary(report))
            print(f"\nreport: {target / 'report.json'}\nrows:   {target / 'rows.jsonl'}")
        elif args.command == "answers":
            price = None
            if (args.price_input is None) != (args.price_output is None):
                raise ValueError("Give both --price-input and --price-output, or neither")
            if args.price_input is not None:
                price = {"input_per_million_usd": args.price_input,
                         "output_per_million_usd": args.price_output, "currency": "USD"}
            report, rows = evaluate_answers(
                args.db, args.questions, mode=args.mode, split=args.split, strategy=args.strategy,
                top_k=args.top_k, candidate_k=args.candidate_k, min_cosine=args.min_cosine,
                rrf_k=args.rrf_k, min_term_coverage=args.min_term_coverage,
                translate=not args.no_translation, model_name=args.model,
                model_factory=lambda: GeminiAnswerModel(args.model),
                query_cache=None if args.no_query_cache else args.query_cache,
                translation_cache=args.translation_cache, verdicts_path=args.verdicts, price=price,
            )
            target = write_run(report, rows, args.out)
            if args.verdict_template:
                (target / "verdicts.template.jsonl").write_text(
                    verdict_template(rows, args.verdict_template), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2) if args.json
                  else format_answer_summary(report))
            print(f"\nreport: {target / 'report.json'}\nrows:   {target / 'rows.jsonl'}")
            if args.verdict_template:
                print(f"verdicts to fill in: {target / 'verdicts.template.jsonl'}")
        elif args.command == "sheet":
            out = Path(args.out) if args.out else Path("out/eval") / f"{Path(args.questions).stem}.sheet.csv"
            path = write_sheet(build_sheet(args.db, args.questions), out)
            print(f"sheet: {path}\nFill 'decision' (ok | fix | drop) and 'note', then run the apply command.")
        else:
            result = apply_sheet(args.db, args.questions, args.sheet, reviewer_id=args.reviewer_id,
                                 reviewer_kind=args.reviewer_kind)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, sqlite3.Error, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
