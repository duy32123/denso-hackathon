"""Build immutable lexical/dense artifacts and activate them atomically in the WP1 DB."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from knowflow_contracts.eligibility import claim_blockers
from knowflow_contracts.enums import QueryMode
from knowflow_contracts.models import Source, Workflow
from knowflow_contracts.search import IndexBuild, StepSearchRecord, WorkflowSearchRecord
from knowflow_contracts.snapshot import snapshot_content_hash
from retrieval.indexing.embeddings import Embedder, unit_vector
from retrieval.indexing.records import _claim_text
from retrieval.retrieval.ranking import TOKENIZER_VERSION, tokens

INDEX_VERSION = "wp2-1"
POLICY_VERSION = "contract-1.0.0-eligibility-1"


class RetrievalError(ValueError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_connection(db: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)


def read_corpus(db: str | Path, mode: str, split: str) -> dict:
    """Namespace check precedes reads of search records, vectors or snapshots."""
    with closing(read_connection(db)) as conn:
        conn.execute("BEGIN")
        settings = dict(conn.execute("SELECT key,value FROM settings"))
        if (settings.get("source_type"), settings.get("dataset_split")) != (mode, split):
            raise RetrievalError("Corpus/split mismatch; use the database for the requested namespace")
        base = settings.get("active_build")
        row = conn.execute("SELECT manifest FROM builds WHERE index_build_id=?", (base,)).fetchone()
        if row is None:
            raise RetrievalError("No imported active build")
        manifest = json.loads(row[0])
        records = [json.loads(r[0]) for r in conn.execute(
            "SELECT payload FROM search_records WHERE index_build_id=? "
            "ORDER BY record_type,workflow_id,revision,step_id", (base,),
        )]
        workflows = {}
        for key in sorted({(r["workflow_id"], r["revision"]) for r in records}):
            raw = conn.execute("SELECT payload FROM snapshots WHERE workflow_id=? AND revision=?", key).fetchone()
            wf = Workflow.model_validate_json(raw[0])
            latest = conn.execute("SELECT MAX(revision) FROM snapshots WHERE workflow_id=?", (key[0],)).fetchone()[0]
            if wf.revision != latest or wf.lifecycle != "active":
                raise RetrievalError("Active record references an old/withdrawn snapshot")
            if (wf.source_type, wf.dataset_split) != (mode, split):
                raise RetrievalError("Snapshot namespace mismatch")
            workflows[key[0]] = wf
        sources = {}
        for sid in sorted({sid for wf in workflows.values() for sid in wf.source_ids}):
            row = conn.execute("SELECT payload FROM sources WHERE source_id=?", (sid,)).fetchone()
            src = Source.model_validate_json(row[0])
            if src.source_type != mode:
                raise RetrievalError("Source namespace mismatch")
            sources[sid] = src
        index_manifest = documents = None
        active = settings.get("active_retrieval_build")
        if active:
            row = conn.execute("SELECT manifest FROM retrieval_builds WHERE index_build_id=?", (active,)).fetchone()
            if row:
                index_manifest = json.loads(row[0])
                # Never load old vectors into the new corpus view.
                if index_manifest["record_build_id"] == base:
                    documents = [json.loads(r[0]) for r in conn.execute(
                        "SELECT payload FROM retrieval_documents WHERE index_build_id=? ORDER BY document_id", (active,),
                    )]
        return {"manifest": manifest, "records": records, "workflows": workflows, "sources": sources,
                "index_manifest": index_manifest, "documents": documents}


def project_documents(corpus: dict) -> list[dict]:
    """Index assertable content separately from unresolved-conflict diagnostics."""
    docs = []
    for record in corpus["records"]:
        model = StepSearchRecord if record["record_type"] == "step" else WorkflowSearchRecord
        model.model_validate(record)
        wf = corpus["workflows"][record["workflow_id"]]
        if record["build"]["snapshot_hash"] != snapshot_content_hash(wf):
            raise RetrievalError("Search record/snapshot hash mismatch")
        claims = {c.claim_id: c for c in wf.claims}
        ids = record.get("claim_ids", [f["claim_id"] for f in record["claim_review_flags"]])
        for purpose in ("answer", "conflict"):
            selected = [claims[cid] for cid in ids if (
                bool(claims[cid].conflicts_with) if purpose == "conflict" else
                not claim_blockers(claims[cid], wf, mode=QueryMode(wf.source_type),
                                   is_latest_indexed_revision=True)
            )]
            if not selected:
                continue
            payload = json.loads(canonical(record))
            selected_ids = {c.claim_id for c in selected}
            payload["claim_review_flags"] = [f for f in payload["claim_review_flags"] if f["claim_id"] in selected_ids]
            if "claim_ids" in payload:
                payload["claim_ids"] = [c.claim_id for c in selected]
            text = "\n".join([wf.title, record["title"], f"context: {canonical(record['metadata'])}",
                              *(_claim_text(c) for c in selected)])
            payload["text"]["search_text_original"] = text
            doc_id = canonical([record["record_type"], wf.workflow_id, wf.revision,
                                record.get("step_id", ""), purpose])
            docs.append({"id": doc_id, "purpose": purpose, "record": payload,
                         "tokens": tokens(text), "text_hash": digest(text), "vector": None})
    return sorted(docs, key=lambda d: d["id"])


def build_index(db: str | Path, *, mode: str, split: str, embedder: Embedder | None = None) -> dict:
    corpus = read_corpus(db, mode, split)
    config = {"index_version": INDEX_VERSION, "policy_version": POLICY_VERSION,
              "tokenizer_version": TOKENIZER_VERSION, "lexical": "BM25",
              "embedding": embedder.config if embedder else None,
              "source_type": mode, "dataset_split": split,
              "record_build_id": corpus["manifest"]["index_build_id"]}
    config_hash = digest(config)
    active = corpus["index_manifest"]
    if active and active["config_hash"] == config_hash and corpus["documents"] is not None:
        require_index(corpus)
        return {"status": "noop", **active}
    docs = project_documents(corpus)
    if embedder and docs:
        vectors = embedder.documents([d["record"]["text"]["search_text_original"] for d in docs])
        if len(vectors) != len(docs):
            raise RetrievalError("Embedding count mismatch; index not activated")
        for doc, vector in zip(docs, vectors, strict=True):
            doc["vector"] = unit_vector(vector, embedder.config["dimensions"])
    output_hash = digest(docs)
    build_id = "IDX_SEARCH_" + digest([config_hash, output_hash])
    for doc in docs:
        base = doc["record"]["build"]
        doc["record"]["build"] = IndexBuild(
            index_build_id=build_id, snapshot_hash=base["snapshot_hash"],
            embedding_model=embedder.config["model"] if embedder else "none",
            embedding_version=embedder.config["version"] if embedder else "not-built",
            text_template_version=base["text_template_version"] + "+wp2-eligible-1",
        ).model_dump(mode="json")
    manifest = {**config, "config_hash": config_hash, "index_build_id": build_id,
                "documents_sha256": digest(docs), "record_count": len(docs),
                "workflow_records": sum(d["record"]["record_type"] == "workflow" for d in docs),
                "step_records": sum(d["record"]["record_type"] == "step" for d in docs),
                "conflict_records": sum(d["purpose"] == "conflict" for d in docs),
                "embedding_calls": getattr(embedder, "calls", 0)}
    # Network work finishes before the write lock. Reject if importer advanced meanwhile.
    with closing(sqlite3.connect(db, timeout=30)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            now = conn.execute("SELECT value FROM settings WHERE key='active_build'").fetchone()
            if now[0] != config["record_build_id"]:
                raise RetrievalError("Importer changed during index build; rerun build")
            conn.execute("CREATE TABLE IF NOT EXISTS retrieval_builds (index_build_id TEXT PRIMARY KEY, manifest TEXT NOT NULL)")
            conn.execute("""CREATE TABLE IF NOT EXISTS retrieval_documents (
                index_build_id TEXT NOT NULL REFERENCES retrieval_builds(index_build_id),
                document_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(index_build_id,document_id))""")
            conn.execute("INSERT OR IGNORE INTO retrieval_builds VALUES (?,?)", (build_id, canonical(manifest)))
            conn.executemany("INSERT OR IGNORE INTO retrieval_documents VALUES (?,?,?)",
                             [(build_id, d["id"], canonical(d)) for d in docs])
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('active_retrieval_build',?)", (build_id,))
    return {"status": "built", **manifest}


def require_index(corpus: dict) -> tuple[dict, list[dict]]:
    manifest, docs = corpus["index_manifest"], corpus["documents"]
    if manifest is None or docs is None:
        raise RetrievalError("Search index missing/stale after import; run retrieval.retrieval build")
    if (manifest["index_version"] != INDEX_VERSION or manifest["policy_version"] != POLICY_VERSION
            or manifest["tokenizer_version"] != TOKENIZER_VERSION):
        raise RetrievalError("Index implementation/policy changed; rebuild required")
    if manifest["record_count"] != len(docs) or digest(docs) != manifest["documents_sha256"]:
        raise RetrievalError("Search index checksum/count mismatch; do not serve this index")
    return manifest, docs
