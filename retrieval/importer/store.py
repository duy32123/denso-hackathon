"""Transactional, local WP1 store. One database is bound to one corpus/split.

The active build indexes search records only, not embeddings or a vector index.
All accepted source/snapshot copies and previous builds are retained for replay.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from pydantic import ValidationError

from knowflow_contracts.enums import DatasetSplit, SourceType
from knowflow_contracts.issues import Report
from knowflow_contracts.loader import REQUIRED_FILES, load_bundle
from knowflow_contracts.models import Manifest, ParsedBundle, Source, Workflow
from knowflow_contracts.rules import check_bundle
from knowflow_contracts.search import IndexBuild
from knowflow_contracts.snapshot import decide_reimport, snapshot_content_hash
from retrieval.indexing.records import TEXT_TEMPLATE_VERSION, build_records

STORE_VERSION = "1"
BUILD_CONFIG = {
    "index_kind": "search-records", "embedding_model": "none",
    "embedding_version": "not-built", "text_template_version": TEXT_TEMPLATE_VERSION,
    "store_version": STORE_VERSION,
}


class ImportError(ValueError):
    """An actionable input, namespace or immutable-content conflict."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _raise_errors(report: Report) -> None:
    if not report.ok:
        raise ImportError("\n".join(str(issue) for issue in report.errors))


def _read_validated(root: Path) -> tuple[ParsedBundle, Report]:
    # Capture input once so bytes parsed/hashed cannot change during import.
    manifest_bytes = (root / "manifest.json").read_bytes()
    try:
        manifest = Manifest.model_validate_json(manifest_bytes)
    except ValidationError as exc:
        raise ImportError(f"V01 manifest.json: {exc}") from exc
    declared = [entry.path for entry in manifest.files]
    if sorted(declared) != sorted(REQUIRED_FILES):
        raise ImportError("V02 WP1 requires exactly sources.jsonl and workflows.jsonl in manifest.files")
    contents = {name: (root / name).read_bytes() for name in REQUIRED_FILES}
    # Check transport integrity BEFORE parsing source/workflow schema.
    for entry in manifest.files:
        if hashlib.sha256(contents[entry.path]).hexdigest() != entry.sha256:
            raise ImportError(f"V02 checksum mismatch: {entry.path}")
    report = Report(bundle_path=str(root))
    with tempfile.TemporaryDirectory(prefix="knowflow-import-") as scratch:
        stage = Path(scratch)
        (stage / "manifest.json").write_bytes(manifest_bytes)
        for name, data in contents.items():
            (stage / name).write_bytes(data)
        bundle = load_bundle(stage, report)
        if bundle is not None:
            check_bundle(bundle, report)
        _raise_errors(report)
        if bundle is None:
            raise ImportError("V01 could not parse bundle")
    return bundle, report


def _initialize(conn: sqlite3.Connection, source_type: str, split: str) -> None:
    statements = [
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        """CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, payload TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS snapshots (
            workflow_id TEXT NOT NULL, revision INTEGER NOT NULL,
            content_hash TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY (workflow_id, revision))""",
        """CREATE TABLE IF NOT EXISTS builds (
            index_build_id TEXT PRIMARY KEY, manifest TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS search_records (
            index_build_id TEXT NOT NULL REFERENCES builds(index_build_id),
            record_type TEXT NOT NULL, workflow_id TEXT NOT NULL, revision INTEGER NOT NULL,
            step_id TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY (index_build_id, record_type, workflow_id, revision, step_id))""",
        """CREATE TABLE IF NOT EXISTS imports (
            bundle_hash TEXT PRIMARY KEY, bundle_manifest TEXT NOT NULL,
            index_build_id TEXT NOT NULL REFERENCES builds(index_build_id))""",
    ]
    for statement in statements:
        conn.execute(statement)
    for key, value in {"store_version": STORE_VERSION, "source_type": source_type, "dataset_split": split}.items():
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if row is not None and row[0] != value:
            raise ImportError(f"store {key}={row[0]}, requested {value}; use a separate database")
        conn.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (key, value))


def _insert_inputs(conn: sqlite3.Connection, bundle: ParsedBundle) -> tuple[int, int]:
    new_sources = new_workflows = 0
    for source in bundle.sources:
        payload = source.model_dump(mode="json")
        digest = _hash(payload)
        row = conn.execute("SELECT content_hash FROM sources WHERE source_id=?", (source.source_id,)).fetchone()
        if row is not None:
            if row[0] != digest:
                raise ImportError(f"source conflict: {source.source_id}; stored source cannot be overwritten")
        else:
            conn.execute("INSERT INTO sources VALUES (?, ?, ?)", (source.source_id, digest, _json(payload)))
            new_sources += 1
    for workflow in bundle.workflows:
        row = conn.execute(
            "SELECT content_hash FROM snapshots WHERE workflow_id=? AND revision=?", workflow.key,
        ).fetchone()
        decision = decide_reimport(row[0] if row else None, workflow)
        if decision == "conflict":
            raise ImportError(f"V09 snapshot conflict: {workflow.workflow_id}@r{workflow.revision}")
        if decision == "new":
            conn.execute("INSERT INTO snapshots VALUES (?, ?, ?, ?)", (
                *workflow.key, snapshot_content_hash(workflow), _json(workflow.model_dump(mode="json")),
            ))
            new_workflows += 1
    return new_sources, new_workflows


def _build(conn: sqlite3.Connection, bundle: ParsedBundle) -> tuple[str, dict, bool]:
    sources = [Source.model_validate_json(r[0]) for r in conn.execute("SELECT payload FROM sources ORDER BY source_id")]
    workflows = [Workflow.model_validate_json(r[0]) for r in conn.execute(
        "SELECT payload FROM snapshots ORDER BY workflow_id, revision"
    )]
    # The common rules also check evidence immutability ACROSS separate imports.
    report = Report(bundle_path="staged store")
    check_bundle(ParsedBundle(manifest=bundle.manifest, sources=sources, workflows=workflows), report)
    _raise_errors(report)
    latest: dict[str, Workflow] = {}
    for workflow in workflows:
        latest[workflow.workflow_id] = workflow
    # Select latest first, then exclude withdrawn. Never resurrect an older revision.
    active = [wf for wf in latest.values() if wf.lifecycle == "active"]
    inventory = {
        "sources": [[r[0], r[1]] for r in conn.execute("SELECT source_id, content_hash FROM sources ORDER BY source_id")],
        "snapshots": [[r[0], r[1], r[2]] for r in conn.execute(
            "SELECT workflow_id, revision, content_hash FROM snapshots ORDER BY workflow_id, revision"
        )],
    }
    build_hash = _hash({
        **BUILD_CONFIG, **inventory,
        "source_type": bundle.manifest.source_type, "dataset_split": bundle.manifest.dataset_split,
    })
    build_id = f"IDX_WP1_{build_hash}"
    previous = conn.execute("SELECT value FROM settings WHERE key='active_build'").fetchone()
    existing = conn.execute("SELECT manifest FROM builds WHERE index_build_id=?", (build_id,)).fetchone()
    if existing is None:
        manifest = {
            **BUILD_CONFIG, "index_build_id": build_id, "snapshot_hash": _hash(inventory),
            "source_type": bundle.manifest.source_type, "dataset_split": bundle.manifest.dataset_split,
            "inventory": inventory, "sources": len(sources), "snapshots": len(workflows),
            "active_workflows": len(active), "active_steps": sum(len(wf.steps) for wf in active),
            "withdrawn_workflows": sum(wf.lifecycle == "withdrawn" for wf in latest.values()),
        }
        conn.execute("INSERT INTO builds VALUES (?, ?)", (build_id, _json(manifest)))
        for workflow in active:
            provenance = IndexBuild(
                index_build_id=build_id, snapshot_hash=snapshot_content_hash(workflow),
                embedding_model=BUILD_CONFIG["embedding_model"],
                embedding_version=BUILD_CONFIG["embedding_version"],
                text_template_version=TEXT_TEMPLATE_VERSION,
            )
            for record in build_records(workflow, provenance):
                conn.execute("INSERT INTO search_records VALUES (?, ?, ?, ?, ?, ?)", (
                    build_id, record.record_type, workflow.workflow_id, workflow.revision,
                    getattr(record, "step_id", ""), _json(record.model_dump(mode="json")),
                ))
    else:
        manifest = json.loads(existing[0])
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('active_build', ?)", (build_id,))
    return build_id, manifest, previous is None or previous[0] != build_id


def import_bundle(
    bundle_dir: str | Path, db: str | Path, *, source_type: str, split: str,
) -> dict:
    """Validate whole input, then commit snapshots/records/active pointer together."""
    source_type, split = SourceType(source_type).value, DatasetSplit(split).value
    bundle, report = _read_validated(Path(bundle_dir))
    if (bundle.manifest.source_type, bundle.manifest.dataset_split) != (source_type, split):
        raise ImportError(f"V02 bundle namespace does not match requested {source_type}/{split}")
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db, timeout=30)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            _initialize(conn, source_type, split)
            new_sources, new_workflows = _insert_inputs(conn, bundle)
            build_id, manifest, changed = _build(conn, bundle)
            bundle_manifest = bundle.manifest.model_dump(mode="json")
            conn.execute("INSERT OR IGNORE INTO imports VALUES (?, ?, ?)", (
                _hash(bundle_manifest), _json(bundle_manifest), build_id,
            ))
    return {
        "status": "imported" if changed else "noop", "db": str(db),
        "bundle_id": bundle.manifest.bundle_id, "index_build_id": build_id,
        "new_sources": new_sources, "new_workflows": new_workflows,
        "unchanged_workflows": len(bundle.workflows) - new_workflows,
        "active_workflows": manifest["active_workflows"], "active_steps": manifest["active_steps"],
        "warnings": [str(warning) for warning in report.warnings],
        "index_kind": BUILD_CONFIG["index_kind"],
    }


def status(db: str | Path) -> dict:
    """Inspect a store without creating it; active pointer and counts are one read."""
    uri = Path(db).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        row = conn.execute(
            "SELECT b.manifest FROM builds b JOIN settings s ON b.index_build_id=s.value "
            "WHERE s.key='active_build'"
        ).fetchone()
        if row is None:
            raise ImportError("no completed active build")
        return json.loads(row[0])


def read_active_records(db: str | Path) -> tuple[dict, list[dict]]:
    """Read manifest and records from one committed build, even during a new import.

    These are search candidates, not permission to assert claims. WP2 must apply
    the shared eligibility policy and resolve evidence from the original snapshot.
    """
    uri = Path(db).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("BEGIN")
        row = conn.execute(
            "SELECT b.manifest FROM builds b JOIN settings s ON b.index_build_id=s.value "
            "WHERE s.key='active_build'"
        ).fetchone()
        if row is None:
            raise ImportError("no completed active build")
        manifest = json.loads(row[0])
        records = [json.loads(r[0]) for r in conn.execute(
            "SELECT payload FROM search_records WHERE index_build_id=? "
            "ORDER BY record_type, workflow_id, revision, step_id", (manifest["index_build_id"],),
        )]
        return manifest, records
