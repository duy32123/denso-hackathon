"""Prepare historical indexes in a separate local pilot demo DB.

Usage: python -m scripts.prepare_knowledge_space
Canonical snapshots and review flags are copied unchanged. No model/API calls.
An existing DB is reused only if all required historical indexes already exist.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from acquisition.export.exporter import export_bundle, load_snapshots
from knowflow_contracts.eligibility import claim_blockers
from knowflow_contracts.enums import QueryMode
from knowflow_contracts.models import Workflow
from retrieval.generation.browse import WorkflowBrowser
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index

ROOT = Path(__file__).resolve().parents[1]


def prepare(db: Path) -> dict:
    db = db.resolve()
    snapshots = load_snapshots(ROOT / "data/workflows/dev")
    if not snapshots:
        raise ValueError("No published pilot snapshots found")
    # Pending source review can yield no retrievable documents. Preserve the
    # shared policy; those revisions remain visible as unavailable in history.
    models = [Workflow.model_validate(w) for w in snapshots]
    expected = {w.key for w in models if w.lifecycle == "active" and any(
        c.conflicts_with or not claim_blockers(c, w, mode=QueryMode.REAL, is_latest_indexed_revision=True)
        for c in w.claims)}
    browser = WorkflowBrowser(lambda mode, split: db)
    if db.exists():
        catalog = browser.catalog("real", "dev")
        indexed = set()
        for w in catalog["workflows"]:
            history = browser.history(w["workflow_id"], w["revision"], "real", "dev", catalog["index_build_id"])
            indexed.update((w["workflow_id"], r["revision"]) for r in history["revisions"] if r["index_build_id"])
        if not expected <= indexed:
            raise ValueError("Existing DB lacks historical indexes. Use --db with a new file; the existing DB was left unchanged.")
        return {"status": "ready", "db": str(db), "indexed_revisions": len(indexed), "stored_snapshots": len(snapshots)}

    db.parent.mkdir(parents=True, exist_ok=True)
    # Import in revision order, building while each version is current. The
    # importer preserves snapshots/builds when the next bundle is activated.
    with tempfile.TemporaryDirectory(prefix="knowledge-space-", dir=db.parent) as temporary:
        work = Path(temporary)
        staging_db = work / "demo.sqlite"
        for revision in sorted({w["revision"] for w in snapshots}):
            snapshot_dir = work / f"snapshots-r{revision}"
            snapshot_dir.mkdir()
            for w in snapshots:
                if w["revision"] <= revision:
                    target = snapshot_dir / f"{w['workflow_id']}.r{w['revision']}.json"
                    target.write_text(json.dumps(w, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            bundle = work / f"bundle-r{revision}"
            result = export_bundle(split="dev", sources_path=ROOT / "data/sources/haas_pilot_sources.jsonl",
                                   snapshot_dir=snapshot_dir, out_dir=bundle, bundle_prefix="BUNDLE_SPACE_HISTORY")
            if not result.report.ok:
                raise ValueError(f"Historical bundle r{revision} failed contract validation")
            import_bundle(bundle, staging_db, source_type="real", split="dev")
            build_index(staging_db, mode="real", split="dev")
        # Publish only after every import/index succeeds. Never replace a DB.
        staging_db.rename(db)
    return {"status": "prepared", "db": str(db), "indexed_revisions": len(expected), "stored_snapshots": len(snapshots)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", type=Path, default=ROOT / "out/retrieval/space_demo.sqlite")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.db), ensure_ascii=False))
        return 0
    except ValueError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
