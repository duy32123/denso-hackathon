"""D2-A orchestration: fixed namespace routing, read-only snapshots, no KB writes."""

import json
from contextlib import closing
from pathlib import Path

from knowflow_contracts.models import QueryRequest, Source, Workflow
from retrieval.indexing.search_index import RetrievalError, read_connection, read_corpus, require_index
from retrieval.retrieval.engine import RetrievalConfig, retrieve

from .engine import generate_answer
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
