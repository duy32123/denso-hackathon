"""CLI `knowflow-contracts`.

    knowflow-contracts validate data/fixtures/F01_complete
    knowflow-contracts validate data/fixtures/* --json
    knowflow-contracts export-json-schema contracts/json-schema
    knowflow-contracts hash data/fixtures/F01_complete
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .issues import Report
from .loader import load_bundle
from .models import AnswerResponse, Manifest, QueryRequest, Source, Workflow
from .search import StepSearchRecord, WorkflowSearchRecord
from .snapshot import snapshot_content_hash
from .validator import validate_bundle

EXPORTED_MODELS = {
    "manifest": Manifest,
    "source": Source,
    "workflow": Workflow,
    "query_request": QueryRequest,
    "answer_response": AnswerResponse,
    # Dan xuat, do doi 2 so huu (D-03, D-06). Khong thuoc Canonical KB.
    "workflow_search_record": WorkflowSearchRecord,
    "step_search_record": StepSearchRecord,
}


def _print_report(report: Report, *, verbose: bool) -> None:
    label = "PASS" if report.ok else "FAIL"
    stats = " ".join(f"{k}={v}" for k, v in report.stats.items())
    print(f"{label}  {report.bundle_path}  {stats}")
    for issue in report.issues:
        if issue.severity == "warning" and not verbose:
            continue
        print(f"  {issue}")
    if not verbose and report.warnings:
        print(f"  ({len(report.warnings)} warning bi an, dung -v de xem)")


def cmd_validate(args: argparse.Namespace) -> int:
    reports = [validate_bundle(path) for path in args.bundles]
    failed = 0

    if args.json:
        print(json.dumps([r.as_dict() for r in reports], ensure_ascii=False, indent=2))
    for report in reports:
        if not args.json:
            _print_report(report, verbose=args.verbose)
        if not report.ok or (args.strict and report.warnings):
            failed += 1

    if not args.json:
        print(f"\n{len(reports) - failed}/{len(reports)} bundle hop le")
    return 1 if failed else 0


def cmd_export_json_schema(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, model in EXPORTED_MODELS.items():
        schema = model.model_json_schema(mode="validation")
        schema["$id"] = f"https://knowflow.ai/schema/1.0.0/{name}.json"
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path = out / f"{name}.schema.json"
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    report = Report(bundle_path=args.bundle)
    bundle = load_bundle(args.bundle, report)
    if bundle is None:
        _print_report(report, verbose=True)
        return 1
    for wf in bundle.workflows:
        print(f"{wf.workflow_id}\tr{wf.revision}\t{snapshot_content_hash(wf)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowflow-contracts", description=__doc__)
    parser.add_argument("--version", action="version", version=f"schema {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="kiem V01-V10 tren mot hoac nhieu bundle")
    p_validate.add_argument("bundles", nargs="+")
    p_validate.add_argument("-v", "--verbose", action="store_true", help="hien ca warning")
    p_validate.add_argument("--json", action="store_true", help="xuat JSON cho CI")
    p_validate.add_argument("--strict", action="store_true", help="coi warning la that bai")
    p_validate.set_defaults(func=cmd_validate)

    p_export = sub.add_parser("export-json-schema", help="sinh JSON Schema tu Pydantic models")
    p_export.add_argument("out_dir")
    p_export.set_defaults(func=cmd_export_json_schema)

    p_hash = sub.add_parser("hash", help="in snapshot_content_hash cho tung workflow")
    p_hash.add_argument("bundle")
    p_hash.set_defaults(func=cmd_hash)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
