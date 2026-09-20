"""D1-B bundle exporter (Team 1 plan, WP7).

Builds the Schema 1.0.0 hand-off bundle that Team 2 imports:

    sources.jsonl + workflow snapshots  ->  manifest.json + sources.jsonl + workflows.jsonl

Rules it enforces, all from 01_Schema_chung section 1:

- A wrong bundle is rejected whole. The bundle is written to a staging directory,
  validated with the shared ``knowflow_contracts`` validator, and only then moved
  over the previous bundle. On any error the previous bundle is left untouched.
- Deterministic bytes: ``sources.jsonl`` is copied byte for byte from the
  canonical Source file (Sources are immutable, never re-encoded); snapshots are
  sorted by (workflow_id, revision) and serialized the way D1-A serialized
  Sources. Exporting the same inputs twice produces byte-identical files.
- ``bundle_id`` identifies content. Same content -> same bundle_id and created_at
  (the export is a no-op). Different content -> a new content-derived bundle_id.
- A published snapshot is immutable: if the current bundle already holds
  ``(workflow_id, revision)`` with different content, the export is refused.
  Changing a published workflow means writing revision N+1 with a change_log.

Snapshots live one per file, pretty-printed for review, at
``data/workflows/<split>/<workflow_id>.r<revision>.json``. This is the interim
canonical store until the WP6 database exists.

Usage (from the repo root)::

    python -m acquisition.export.exporter --split dev
    python -m acquisition.export.exporter --split dev --check   # validate only, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from knowflow_contracts import snapshot_content_hash, validate_bundle
from knowflow_contracts.issues import Report
from knowflow_contracts.models import Workflow

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_VERSION = "d1b-exporter-0.1.0"

SPLITS = {
    "dev": {
        "sources": REPO_ROOT / "data" / "sources" / "haas_pilot_sources.jsonl",
        "snapshots": REPO_ROOT / "data" / "workflows" / "dev",
        "out": REPO_ROOT / "acquisition" / "export" / "haas_pilot_dev_bundle",
        "bundle_prefix": "BUNDLE_HAAS_SMTC_DEV",
    },
    "holdout": {
        "sources": REPO_ROOT / "data" / "sources" / "haas_pilot_holdout_sources.jsonl",
        "snapshots": REPO_ROOT / "data" / "workflows" / "holdout",
        "out": REPO_ROOT / "acquisition" / "export" / "haas_pilot_holdout_bundle",
        "bundle_prefix": "BUNDLE_HAAS_SMTC_HOLDOUT",
    },
}

_SNAPSHOT_NAME = re.compile(r"^(?P<workflow_id>.+)\.r(?P<revision>[1-9]\d*)\.json$")


class ExportError(ValueError):
    """The export would produce a wrong bundle or overwrite a published snapshot."""


@dataclass
class ExportResult:
    out_dir: Path
    bundle_id: str
    changed: bool
    report: Report
    counts: dict[str, int] = field(default_factory=dict)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _jsonl(records: list[dict]) -> bytes:
    # Same serialization D1-A used for data/sources/*.jsonl, so every JSONL in a bundle looks alike.
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- inputs --------------------------------------------------------------------


def load_sources(path: Path) -> tuple[bytes, int]:
    """The canonical Source file, byte for byte, and its record count.

    Source records are immutable (Schema section 1), so the exporter copies the
    file D1-A committed instead of re-encoding it: re-serializing could change
    bytes (escaping, key order) and with them every downstream checksum.
    """
    body = path.read_bytes()
    text = body.decode("utf-8")
    if "\r" in text:
        raise ExportError(f"{path.name}: must use LF line endings (checksums are computed on bytes)")
    if text and not text.endswith("\n"):
        raise ExportError(f"{path.name}: last record must end with a newline")
    return body, sum(1 for line in text.split("\n") if line.strip())


def load_snapshots(snapshot_dir: Path) -> list[dict]:
    """Read every ``<workflow_id>.r<revision>.json``; the filename must match the content."""
    if not snapshot_dir.is_dir():
        return []
    snapshots = []
    for path in sorted(snapshot_dir.glob("*.json")):
        match = _SNAPSHOT_NAME.match(path.name)
        if not match:
            raise ExportError(f"{path.name}: snapshot files must be named <workflow_id>.r<revision>.json")
        record = json.loads(path.read_text(encoding="utf-8"))
        key = (record.get("workflow_id"), record.get("revision"))
        if key != (match["workflow_id"], int(match["revision"])):
            raise ExportError(f"{path.name}: file name says {match['workflow_id']}@r{match['revision']}, content says {key[0]}@r{key[1]}")
        snapshots.append(record)
    return sorted(snapshots, key=lambda r: (r["workflow_id"], r["revision"]))


# --- published-snapshot guard ------------------------------------------------------


def _published_hashes(out_dir: Path) -> dict[tuple[str, int], str]:
    path = out_dir / "workflows.jsonl"
    if not path.is_file():
        return {}
    hashes = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            wf = Workflow.model_validate(json.loads(line))
            hashes[wf.key] = snapshot_content_hash(wf)
    return hashes


def check_published_snapshots(snapshots: list[dict], out_dir: Path) -> None:
    """Refuse to change a (workflow_id, revision) that is already in the bundle.

    A snapshot missing from the new export is refused too: dropping a published
    revision would let a withdrawn or corrected workflow disappear silently instead
    of being superseded by a new revision (plan: "không dùng bản cũ để né rút tri thức").
    """
    published = _published_hashes(out_dir)
    incoming: dict[tuple[str, int], str] = {}
    malformed: set[tuple[str, int]] = set()
    for record in snapshots:
        try:
            wf = Workflow.model_validate(record)
        except ValidationError:
            # The staging validator reports the exact V01 errors and rejects the bundle.
            malformed.add((record.get("workflow_id"), record.get("revision")))
            continue
        incoming[wf.key] = snapshot_content_hash(wf)

    for key, digest in published.items():
        if key in malformed:
            continue
        if key not in incoming:
            raise ExportError(f"{key[0]}@r{key[1]} is in the published bundle but missing from the snapshot store")
        if incoming[key] != digest:
            raise ExportError(
                f"{key[0]}@r{key[1]} is already published with different content. "
                f"Write {key[0]}.r{key[1] + 1}.json with supersedes_revision={key[1]} and a change_log instead."
            )


# --- export --------------------------------------------------------------------


def export_bundle(
    *,
    split: str,
    sources_path: Path,
    snapshot_dir: Path,
    out_dir: Path,
    bundle_prefix: str,
    source_type: str = "real",
    check_only: bool = False,
    clock: Callable[[], str] = _utc_now,
) -> ExportResult:
    sources_body, source_count = load_sources(sources_path)
    snapshots = load_snapshots(snapshot_dir)
    check_published_snapshots(snapshots, out_dir)

    workflows_body = _jsonl(snapshots)
    files = [
        {"path": "sources.jsonl", "sha256": _sha256(sources_body), "record_count": source_count},
        {"path": "workflows.jsonl", "sha256": _sha256(workflows_body), "record_count": len(snapshots)},
    ]

    previous = _read_manifest(out_dir)
    unchanged = previous is not None and previous.get("files") == files and previous.get("dataset_split") == split
    if unchanged:
        bundle_id, created_at = previous["bundle_id"], previous["created_at"]
    else:
        digest = _sha256(sources_body + b"\x00" + workflows_body)
        bundle_id, created_at = f"{bundle_prefix}_{digest[:12]}", clock()

    # An unchanged bundle keeps its original producer too: it is the same bundle.
    producer = previous["producer"] if unchanged else {"team": "team_1", "pipeline_version": PIPELINE_VERSION}
    manifest = {
        "schema_version": "1.0.0",
        "bundle_id": bundle_id,
        "source_type": source_type,
        "dataset_split": split,
        "created_at": created_at,
        "files": files,
        "producer": producer,
    }
    manifest_body = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    with tempfile.TemporaryDirectory(prefix="bundle-staging-") as tmp:
        staging = Path(tmp)
        (staging / "sources.jsonl").write_bytes(sources_body)
        (staging / "workflows.jsonl").write_bytes(workflows_body)
        (staging / "manifest.json").write_bytes(manifest_body)

        report = validate_bundle(staging)
        report.bundle_path = str(out_dir)
        result = ExportResult(out_dir=out_dir, bundle_id=bundle_id, changed=not unchanged, report=report,
                              counts={"sources": source_count, "workflows": len(snapshots)})
        if not report.ok or check_only or unchanged:
            return result

        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ("sources.jsonl", "workflows.jsonl", "manifest.json"):
            shutil.copyfile(staging / name, out_dir / name)
    return result


def _read_manifest(out_dir: Path) -> dict | None:
    path = out_dir / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


# --- CLI -----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="exporter", description=__doc__.split("\n\n")[0])
    parser.add_argument("--split", choices=sorted(SPLITS), required=True)
    parser.add_argument("--check", action="store_true", help="validate the would-be bundle, write nothing")
    parser.add_argument("-v", "--verbose", action="store_true", help="also print validator warnings")
    args = parser.parse_args(argv)

    cfg = SPLITS[args.split]
    try:
        result = export_bundle(
            split=args.split,
            sources_path=cfg["sources"],
            snapshot_dir=cfg["snapshots"],
            out_dir=cfg["out"],
            bundle_prefix=cfg["bundle_prefix"],
            check_only=args.check,
        )
    except ExportError as exc:
        print(f"REFUSED  {exc}", file=sys.stderr)
        return 1

    for issue in result.report.issues:
        if issue.severity == "error" or args.verbose:
            print(f"  {issue}")

    counts = " ".join(f"{k}={v}" for k, v in result.counts.items())
    if not result.report.ok:
        print(f"REJECTED {args.split} bundle ({counts}); previous bundle left untouched", file=sys.stderr)
        return 1
    if args.check:
        state = "would change" if result.changed else "unchanged"
    else:
        state = "written" if result.changed else "unchanged (no-op)"
    print(f"OK  {result.out_dir.relative_to(REPO_ROOT).as_posix()}  {result.bundle_id}  {counts}  {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
