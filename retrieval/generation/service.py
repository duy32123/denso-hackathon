"""D2-A orchestration: fixed namespace routing, read-only snapshots, no KB writes."""

import json
from dataclasses import replace
from contextlib import closing
from pathlib import Path

from knowflow_contracts.models import QueryRequest, Source, Workflow
from retrieval.indexing.search_index import RetrievalError, read_connection, read_corpus, require_index
from retrieval.retrieval.engine import RetrievalConfig, retrieve

from .engine import generate_answer, checked_candidates
from .tracing import TraceRequest, TraceCancelled, retrieval_stage, ref
from .browse import WorkflowBrowser
from .feedback import FeedbackRequest, FeedbackService, FeedbackUnavailable
from .evidence import EvidenceAccess, external_url
from .gemini import GeminiAnswerModel


class NamespaceUnavailable(ValueError):
    pass


class EvidenceNotFound(ValueError):
    pass


class QAService:
    def __init__(self, databases: dict[tuple[str, str], Path], *, repo_root: Path,
                 config: RetrievalConfig | None = None, model_factory=GeminiAnswerModel,
                 retriever=retrieve, feedback: FeedbackService | None = None):
        self.databases = {key: Path(path).resolve() for key, path in databases.items()}
        self.config = config or RetrievalConfig()
        self.access = EvidenceAccess(repo_root)
        self.model_factory, self.retriever = model_factory, retriever
        self.browser = WorkflowBrowser(self.database)
        # None = chua co service ghi cua doi 1. Khong co duong nao khac de ghi KB.
        self.feedback = feedback

    def database(self, mode: str, split: str) -> Path:
        # Pilot only: holdout remains locked even if accidentally configured.
        if split != "dev" or (mode, split) not in self.databases:
            raise NamespaceUnavailable("Corpus/split not enabled")
        return self.databases[(mode, split)]

    def ask(self, request: QueryRequest):
        db = self.database(request.mode, request.dataset_split)
        result = self.retriever(db, request, config=self.config)
        corpus = read_corpus(db, request.mode, request.dataset_split)
        require_index(corpus)
        model = self.model_factory()
        try:
            answer = generate_answer(request, result, corpus, model=model, access=self.access)
        finally:
            model.close()
        current = read_corpus(db, request.mode, request.dataset_split)
        manifest, _ = require_index(current)
        if manifest["index_build_id"] != answer.index_build_id:
            raise RetrievalError("Index changed while answering; retry")
        return answer

    def trace(self, request: TraceRequest, emit, cancelled):
        """One actual retrieval run, optionally followed by the normal answer guard.

        Stream observable pipeline events, never a reconstructed model monologue.
        No persisted trace/session and no changes to shared AnswerResponse.
        """
        query = request.query
        db = self.database(query.mode, query.dataset_split)
        sequence = 0

        def send(event):
            nonlocal sequence
            if cancelled.is_set():
                raise TraceCancelled()
            sequence += 1
            emit({**event, "seq": sequence, "mode": str(query.mode), "dataset_split": str(query.dataset_split),
                  "index_build_id": request.index_build_id, "origin": "observed_pipeline"})

        def observe(stage, result):
            if (result["index_build_id"] != request.index_build_id or
                (result["source_type"], result["dataset_split"]) != (query.mode, query.dataset_split)):
                raise RetrievalError("Index changed while tracing; reload the graph")
            send(retrieval_stage(stage, result))

        config = replace(self.config, top_k=request.top_k, candidate_k=max(self.config.candidate_k, request.top_k))
        result = self.retriever(db, query, config=config, on_stage=observe)
        corpus = read_corpus(db, query.mode, query.dataset_split)
        manifest, _ = require_index(corpus)
        if (manifest["index_build_id"] != request.index_build_id or result["index_build_id"] != request.index_build_id):
            raise RetrievalError("Index changed while tracing; reload the graph")
        candidates, unavailable = checked_candidates(query, result, corpus, self.access)
        related, related_unavailable = checked_candidates(query, {**result, "claims": [
            {**c, "purpose": "answer_candidate"} for c in result["related_claims"]]}, corpus, self.access)
        evidence_refs = []
        for group, items in [("selected", candidates), ("context", related)]:
            for c in items.values():
                r = c["claim_ref"]
                evidence_refs.append(ref(r["workflow_id"], r["revision"], "claim", r["entity_id"], state=group))
                for e in c["evidence"]:
                    evidence_refs.append(ref(r["workflow_id"], r["revision"], "evidence", e["evidence"]["evidence_id"], state=group))
                    evidence_refs.append(ref(r["workflow_id"], r["revision"], "source", e["source_id"], state=group))
        evidence_refs += [ref(r.workflow_id, r.revision, "claim", r.entity_id, state="blocked", reasons=["evidence_unavailable"])
                          for r in unavailable + related_unavailable]
        send({"type": "stage", "stage": "evidence", "refs": evidence_refs,
              "data": {"answer_candidates": len(candidates), "context_candidates": len(related),
                       "unavailable": len(unavailable) + len(related_unavailable)}})
        answer = None
        def ensure_current():
            current = read_corpus(db, query.mode, query.dataset_split)
            current_manifest, _ = require_index(current)
            if current_manifest["index_build_id"] != request.index_build_id:
                raise RetrievalError("Index changed while tracing; reload the graph")

        if request.generate_answer:
            owner = self

            class ObservedModel:
                def __init__(self, model):
                    self.model = model

                def draft(self, payload):
                    send({"type": "stage", "stage": "drafting", "refs": [], "data": {"candidates": len(candidates)}})
                    return self.model.draft(payload)

                def verify(self, payload):
                    send({"type": "stage", "stage": "verifying", "refs": [], "data": {"statements": len(payload["statements"])}})
                    return self.model.verify(payload)

            # Early fallback doesn't require an external model or an API key.
            model = owner.model_factory() if result["status"] == "retrieved" and candidates else None
            try:
                answer = generate_answer(query, result, corpus, model=ObservedModel(model) if model else None, access=self.access)
            finally:
                if model:
                    model.close()
            ensure_current()
            refs = []
            for citation in answer.citations:
                r = citation.claim_ref
                refs.append(ref(r.workflow_id, r.revision, "claim", r.entity_id, state="cited"))
                refs += [ref(r.workflow_id, r.revision, "evidence", eid, state="cited") for eid in citation.evidence_ids]
            send({"type": "stage", "stage": "citations", "refs": refs, "data": {"status": str(answer.status)}})
        ensure_current()
        send({"type": "result", "stage": "done", "refs": [], "data": {
            "status": result["status"], "selected_workflow": result["selected_workflow"],
            "missing_context": result["missing_context"], "latency_ms": result["trace"]["latency_ms"],
            "strategy": config.strategy, "top_k": config.top_k,
            "candidates": [{"claim_ref": c["claim_ref"], "text": c["claim"]["text"],
                            "evidence_ids": [e["evidence"]["evidence_id"] for e in c["evidence"]],
                            "source_review": c["claim"]["source_review"], "technical_review": c["claim"]["technical_review"]}
                           for c in candidates.values()],
            "answer": answer.model_dump(mode="json") if answer else None}})

    def evidence(self, mode: str, split: str, build: str, workflow_id: str, revision: int, evidence_id: str):
        """Open the exact indexed revision, including historical builds; never resolve to latest."""
        db = self.database(mode, split)
        with closing(read_connection(db)) as conn:
            conn.execute("BEGIN")
            settings = dict(conn.execute("SELECT key,value FROM settings"))
            if (settings.get("source_type"), settings.get("dataset_split")) != (mode, split):
                raise EvidenceNotFound("Evidence not found in this namespace")
            row = conn.execute("SELECT manifest FROM retrieval_builds WHERE index_build_id=?", (build,)).fetchone()
            if not row:
                raise EvidenceNotFound("Index build not found")
            manifest = json.loads(row[0])
            if (manifest["source_type"], manifest["dataset_split"]) != (mode, split):
                raise EvidenceNotFound("Index namespace mismatch")
            records = [json.loads(r[0])["record"] for r in conn.execute(
                "SELECT payload FROM retrieval_documents WHERE index_build_id=?", (build,))]
            if not any(r["workflow_id"] == workflow_id and r["revision"] == revision for r in records):
                raise EvidenceNotFound("Snapshot was not part of this index")
            row = conn.execute("SELECT payload FROM snapshots WHERE workflow_id=? AND revision=?",
                               (workflow_id, revision)).fetchone()
            if not row:
                raise EvidenceNotFound("Snapshot not found")
            wf = Workflow.model_validate_json(row[0])
            if (wf.source_type, wf.dataset_split) != (mode, split):
                raise EvidenceNotFound("Snapshot namespace mismatch")
            ev = next((e for e in wf.evidence if e.evidence_id == evidence_id), None)
            if ev is None:
                raise EvidenceNotFound("Evidence not found")
            row = conn.execute("SELECT payload FROM sources WHERE source_id=?", (ev.source_id,)).fetchone()
            if not row:
                raise EvidenceNotFound("Source not found")
            src = Source.model_validate_json(row[0])
            if src.source_type != mode:
                raise EvidenceNotFound("Source namespace mismatch")
        view = self.access.view(ev, src)
        linked = [c for c in wf.claims if any(link.evidence_id == ev.evidence_id for link in c.evidence_links)]
        data = {"index_build_id": build, "mode": mode, "dataset_split": split,
                "workflow": {"workflow_id": wf.workflow_id, "revision": wf.revision, "title": wf.title},
                "evidence": ev.model_dump(mode="json", exclude={"asset_uri"}),
                "source": {"source_id": src.source_id, "title": src.title,
                           "url": external_url(src.url) if mode == "real" else None,
                           "access_note": src.access_note},
                "available": view.available, "access_kind": view.kind, "text": view.text,
                "external_video_checked": False, "asset_available": view.asset_path is not None,
                "claims": [{"claim_id": c.claim_id, "text": c.text, "role": c.role,
                            "evidence_type": c.evidence_type, "source_review": c.source_review,
                            "technical_review": c.technical_review,
                            "attribution": c.attribution.model_dump(mode="json"),
                            "scope": c.scope.model_dump(mode="json"),
                            "conflicts_with": c.conflicts_with} for c in linked]}
        return data, view

    # --- WP4 feedback: doi 1 so huu viec ghi; day chi la duong goi sang ---------

    def _writer(self) -> FeedbackService:
        if self.feedback is None:
            raise FeedbackUnavailable(
                "Service ghi phan hoi cua doi 1 (D1-B / WP6) chua duoc cau hinh.")
        return self.feedback

    def feedback_preview(self, request: FeedbackRequest) -> dict:
        self.database(request.mode, request.dataset_split)
        return self._writer().preview(request)

    def feedback_submit(self, request: FeedbackRequest) -> dict:
        self.database(request.mode, request.dataset_split)
        return self._writer().submit(request)
