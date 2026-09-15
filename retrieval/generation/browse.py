"""Read-only WP4 views pinned to indexed snapshots; never writes review or KB data."""

import json
from collections import Counter
from contextlib import closing

from knowflow_contracts.models import Source, Workflow
from retrieval.indexing.search_index import read_connection, read_corpus, require_index

from .evidence import external_url


class WorkflowNotFound(ValueError):
    pass


def review_counts(workflow):
    return {
        "source": dict(Counter(str(c.source_review) for c in workflow.claims)),
        "technical": dict(Counter(str(c.technical_review) for c in workflow.claims)),
    }


def snapshot_diff(before: Workflow, after: Workflow) -> dict:
    """Compare explicit immutable snapshots, not a fresh model interpretation."""
    def changes(old, new, key):
        a = {getattr(item, key): item.model_dump(mode="json") for item in old}
        b = {getattr(item, key): item.model_dump(mode="json") for item in new}
        return {
            "added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()),
            "changed": [{"id": identifier, "fields": [field for field in a[identifier]
                           if a[identifier][field] != b[identifier][field]],
                         "before": a[identifier], "after": b[identifier]}
                        for identifier in sorted(a.keys() & b.keys()) if a[identifier] != b[identifier]],
        }

    evidence = changes(before.evidence, after.evidence, "evidence_id")
    # Never expose local asset paths through the browser/diff endpoints.
    for item in evidence["changed"]:
        item["before"].pop("asset_uri", None)
        item["after"].pop("asset_uri", None)
    return {
        "from_revision": before.revision, "to_revision": after.revision,
        "claims": changes(before.claims, after.claims, "claim_id"),
        "steps": changes(before.steps, after.steps, "step_id"),
        "questions": changes(before.questions, after.questions, "question_id"),
        "relations": changes(before.relations, after.relations, "relation_id"),
        "evidence": evidence,
        "context_changed": before.context != after.context,
        "source_ids_added": sorted(set(after.source_ids) - set(before.source_ids)),
        "source_ids_removed": sorted(set(before.source_ids) - set(after.source_ids)),
    }


class WorkflowBrowser:
    def __init__(self, database):
        self.database = database  # fixed server-owned namespace routing

    @staticmethod
    def _namespace(conn, mode, split):
        settings = dict(conn.execute("SELECT key,value FROM settings"))
        if (settings.get("source_type"), settings.get("dataset_split")) != (mode, split):
            raise WorkflowNotFound("Namespace mismatch")

    @staticmethod
    def _snapshot(conn, workflow_id, revision, mode, split):
        row = conn.execute("SELECT payload FROM snapshots WHERE workflow_id=? AND revision=?",
                           (workflow_id, revision)).fetchone()
        if not row:
            raise WorkflowNotFound("Snapshot not found")
        workflow = Workflow.model_validate_json(row[0])
        if (workflow.workflow_id, workflow.revision, workflow.source_type, workflow.dataset_split) != (
                workflow_id, revision, mode, split):
            raise WorkflowNotFound("Snapshot namespace/revision mismatch")
        return workflow

    @staticmethod
    def _members(conn, build, mode, split):
        row = conn.execute("SELECT manifest FROM retrieval_builds WHERE index_build_id=?", (build,)).fetchone()
        if not row:
            raise WorkflowNotFound("Index not found")
        manifest = json.loads(row[0])
        if (manifest["source_type"], manifest["dataset_split"]) != (mode, split):
            raise WorkflowNotFound("Index namespace mismatch")
        records = [json.loads(row[0])["record"] for row in conn.execute(
            "SELECT payload FROM retrieval_documents WHERE index_build_id=?", (build,))]
        if any((record["source_type"], record["dataset_split"]) != (mode, split) for record in records):
            raise WorkflowNotFound("Index document namespace mismatch")
        return {(record["workflow_id"], record["revision"]) for record in records}

    def _indexed(self, conn, workflow_id, revision, mode, split, build):
        self._namespace(conn, mode, split)
        if (workflow_id, revision) not in self._members(conn, build, mode, split):
            raise WorkflowNotFound("Snapshot was not part of this index")
        return self._snapshot(conn, workflow_id, revision, mode, split)

    def catalog(self, mode, split):
        corpus = read_corpus(self.database(mode, split), mode, split)
        manifest, documents = require_index(corpus)
        members = {(doc["record"]["workflow_id"], doc["record"]["revision"]) for doc in documents}
        return {
            "mode": mode, "dataset_split": split, "index_build_id": manifest["index_build_id"],
            "read_only": True,
            "workflows": [{"workflow_id": wf.workflow_id, "revision": wf.revision, "title": wf.title,
                           "steps": len(wf.steps), "claims": len(wf.claims), "review_counts": review_counts(wf)}
                          for wf in sorted(corpus["workflows"].values(), key=lambda w: w.workflow_id)
                          if (wf.workflow_id, wf.revision) in members],
        }

    def workflow(self, workflow_id, revision, mode, split, build):
        with closing(read_connection(self.database(mode, split))) as conn:
            conn.execute("BEGIN")
            wf = self._indexed(conn, workflow_id, revision, mode, split, build)
            sources = []
            for sid in wf.source_ids:
                row = conn.execute("SELECT payload FROM sources WHERE source_id=?", (sid,)).fetchone()
                if not row:
                    raise WorkflowNotFound("Source not found")
                source = Source.model_validate_json(row[0])
                if source.source_type != mode or source.source_id != sid:
                    raise WorkflowNotFound("Source namespace mismatch")
                sources.append({"source_id": sid, "title": source.title, "access_note": source.access_note,
                                "url": external_url(source.url) if mode == "real" else None})
            payload = wf.model_dump(mode="json", exclude={"evidence": {"__all__": {"asset_uri"}}})
        return {"index_build_id": build, "mode": mode, "dataset_split": split, "read_only": True,
                "workflow": payload, "sources": sources, "review_counts": review_counts(wf)}

    def history(self, workflow_id, revision, mode, split, build):
        with closing(read_connection(self.database(mode, split))) as conn:
            conn.execute("BEGIN")
            anchor = self._indexed(conn, workflow_id, revision, mode, split, build)
            # History is bounded by the requested revision, never silently latest.
            numbers = [row[0] for row in conn.execute(
                "SELECT revision FROM snapshots WHERE workflow_id=? AND revision<=? ORDER BY revision",
                (workflow_id, anchor.revision))]
            snapshots = {number: self._snapshot(conn, workflow_id, number, mode, split) for number in numbers}
            indexed = {}
            for row in conn.execute("SELECT index_build_id,manifest FROM retrieval_builds ORDER BY index_build_id"):
                manifest = json.loads(row[1])
                if (manifest["source_type"], manifest["dataset_split"]) != (mode, split):
                    continue
                for wid, number in self._members(conn, row[0], mode, split):
                    if wid == workflow_id and number in snapshots:
                        indexed[number] = row[0]
            indexed[anchor.revision] = build
            revisions = []
            for number, wf in snapshots.items():
                previous = snapshots.get(wf.supersedes_revision)
                revisions.append({
                    "revision": number, "created_at": wf.model_dump(mode="json")["created_at"], "lifecycle": wf.lifecycle,
                    "previous_revision": wf.supersedes_revision, "index_build_id": indexed.get(number),
                    "review_counts": review_counts(wf),
                    "review_events": [event.model_dump(mode="json") for event in wf.review_events],
                    "change_log": [event.model_dump(mode="json") for event in wf.change_log],
                    "unresolved_conflicts": [c.claim_id for c in wf.claims if c.conflicts_with],
                    "diff": snapshot_diff(previous, wf) if previous else None,
                })
        return {"workflow_id": workflow_id, "through_revision": revision, "index_build_id": build,
                "mode": mode, "dataset_split": split, "read_only": True, "revisions": revisions}
