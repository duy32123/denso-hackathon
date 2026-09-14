"""Run from the repository root: python -m retrieval.importer --help."""

import argparse
import json
import sqlite3
import sys

from .store import ImportError, import_bundle, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WP1: validated bundle to local search-record store")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("import", help="validate and atomically import a bundle")
    ingest.add_argument("bundle")
    ingest.add_argument("--db", required=True)
    ingest.add_argument("--source-type", choices=["real", "synthetic"], required=True)
    ingest.add_argument("--split", choices=["dev", "holdout"], required=True)
    inspect = commands.add_parser("status", help="show active build manifest (read-only)")
    inspect.add_argument("--db", required=True)
    args = parser.parse_args(argv)
    try:
        result = status(args.db) if args.command == "status" else import_bundle(
            args.bundle, args.db, source_type=args.source_type, split=args.split,
        )
    except (ImportError, OSError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
