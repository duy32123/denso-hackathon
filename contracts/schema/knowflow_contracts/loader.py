"""Doc bundle tu dia va kiem tang V01/V02 (schema, checksum, so dong)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from .issues import Report
from .models import Manifest, ParsedBundle, Source, Workflow

MANIFEST_NAME = "manifest.json"
SOURCES_NAME = "sources.jsonl"
WORKFLOWS_NAME = "workflows.jsonl"
REQUIRED_FILES = (SOURCES_NAME, WORKFLOWS_NAME)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _format_validation_error(exc: ValidationError, prefix: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        out.append((f"{prefix} $.{loc}", f"{err['type']}: {err['msg']}"))
    return out


def load_bundle(bundle_dir: str | Path, report: Report) -> ParsedBundle | None:
    """Parse ba tep cua bundle. Tra None neu khong the parse tiep."""
    root = Path(bundle_dir)

    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        report.error("V02", MANIFEST_NAME, "thieu manifest.json")
        return None

    try:
        manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        report.error("V01", MANIFEST_NAME, f"khong doc duoc JSON: {exc}")
        return None

    try:
        manifest = Manifest.model_validate(manifest_raw)
    except ValidationError as exc:
        for path, msg in _format_validation_error(exc, MANIFEST_NAME):
            report.error("V01", path, msg)
        return None

    declared = {entry.path: entry for entry in manifest.files}
    for name in REQUIRED_FILES:
        if name not in declared:
            report.error("V02", MANIFEST_NAME, f"manifest.files thieu {name}")

    sources = _load_records(root / SOURCES_NAME, SOURCES_NAME, Source, report)
    workflows = _load_records(root / WORKFLOWS_NAME, WORKFLOWS_NAME, Workflow, report)
    if sources is None or workflows is None:
        return None

    counts = {SOURCES_NAME: len(sources), WORKFLOWS_NAME: len(workflows)}
    for name, count in counts.items():
        entry = declared.get(name)
        path = root / name
        if entry is None or not path.is_file():
            continue
        actual_sha = sha256_file(path)
        if actual_sha != entry.sha256:
            report.error(
                "V02",
                name,
                f"checksum lech: manifest={entry.sha256[:12]}... thuc te={actual_sha[:12]}...",
            )
        if entry.record_count != count:
            report.error(
                "V02",
                name,
                f"record_count lech: manifest={entry.record_count} thuc te={count}",
            )

    for entry in manifest.files:
        if not (root / entry.path).is_file():
            report.error("V02", MANIFEST_NAME, f"manifest.files tro toi tep khong ton tai: {entry.path}")

    report.stats.update(
        {
            "sources": len(sources),
            "workflows": len(workflows),
            "steps": sum(len(w.steps) for w in workflows),
            "claims": sum(len(w.claims) for w in workflows),
            "evidence": sum(len(w.evidence) for w in workflows),
            "questions": sum(len(w.questions) for w in workflows),
        }
    )

    return ParsedBundle(manifest=manifest, sources=sources, workflows=workflows)


def _load_records(path: Path, name: str, model, report: Report) -> list | None:
    if not path.is_file():
        report.error("V02", name, "thieu tep bat buoc")
        return None

    records = []
    failed = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            report.error("V01", f"{name}:{lineno}", "dong rong: moi dong phai la mot object hoan chinh")
            failed = True
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            report.error("V01", f"{name}:{lineno}", f"khong doc duoc JSON: {exc}")
            failed = True
            continue
        if not isinstance(raw, dict):
            report.error("V01", f"{name}:{lineno}", "moi dong phai la object JSON")
            failed = True
            continue
        try:
            records.append(model.model_validate(raw))
        except ValidationError as exc:
            for loc, msg in _format_validation_error(exc, f"{name}:{lineno}"):
                report.error("V01", loc, msg)
            failed = True

    return None if failed else records
