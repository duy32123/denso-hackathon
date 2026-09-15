"""Contract-preserving HTTP facade. DB paths/model settings are never client input."""

import asyncio
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from knowflow_contracts.models import AnswerResponse, QueryRequest
from retrieval.generation.gemini import GeminiAnswerModel
from retrieval.generation.browse import WorkflowNotFound
from retrieval.generation.models import GenerationError
from retrieval.generation.service import EvidenceNotFound, NamespaceUnavailable, QAService
from retrieval.indexing.embeddings import EmbeddingError
from retrieval.indexing.search_index import RetrievalError
from retrieval.retrieval.engine import RetrievalConfig
from retrieval.retrieval.query import TranslationError


def error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def service_from_env():
    from dotenv import load_dotenv

    root = Path(os.getenv("KNOWFLOW_REPO_ROOT", ".")).resolve()
    load_dotenv(root / ".env")
    def db_path(value):
        path = Path(value)
        return path if path.is_absolute() else root / path

    databases = {("real", "dev"): db_path(os.getenv("KNOWFLOW_REAL_DEV_DB", "out/retrieval/real_dev.sqlite"))}
    if os.getenv("KNOWFLOW_SYNTHETIC_DEV_DB"):
        databases[("synthetic", "dev")] = db_path(os.environ["KNOWFLOW_SYNTHETIC_DEV_DB"])
    model = os.getenv("KNOWFLOW_ANSWER_MODEL", "gemini-3.5-flash-lite")
    return QAService(databases, repo_root=root,
                     config=RetrievalConfig(strategy=os.getenv("KNOWFLOW_RETRIEVAL_STRATEGY", "hybrid")),
                     model_factory=lambda: GeminiAnswerModel(model))


def create_app(service: QAService | None = None, *, timeout_seconds: float = 90, max_in_flight: int = 2):
    if timeout_seconds <= 0 or max_in_flight < 1:
        raise ValueError("Timeout and capacity must be positive")
    service = service or service_from_env()
    app = FastAPI(title="KnowFlow pilot QA", version="0.1.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
    # Keep timed-out jobs counted until their provider calls actually finish. There is
    # no unsafe thread kill; timeouts must not create unlimited background LLM calls.
    jobs: set[asyncio.Task] = set()

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error(422, "invalid_request", "Câu hỏi hoặc context không đúng contract.")

    @app.exception_handler(NamespaceUnavailable)
    async def invalid_namespace(request, exc):
        return error(422, "namespace_unavailable", "Corpus/split này chưa được bật; holdout đang khóa.")

    @app.exception_handler(EvidenceNotFound)
    async def not_found(request, exc):
        return error(404, "evidence_not_found", "Không tìm thấy bằng chứng trong phiên bản và corpus này.")

    @app.exception_handler(WorkflowNotFound)
    async def workflow_not_found(request, exc):
        return error(404, "workflow_not_found", "Không tìm thấy workflow trong phiên bản và index này.")

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return error(500, "internal_error", "Không thể xử lý yêu cầu lúc này.")

    @app.get("/v1/health")
    def health():
        return {"status": "running", "namespaces": [
            {"mode": mode, "dataset_split": split} for mode, split in sorted(service.databases) if split == "dev"]}

    @app.post("/v1/ask", response_model=AnswerResponse)
    async def ask(query: QueryRequest):
        if not query.question.strip() or len(query.question) > 4000 or len(query.model_dump_json()) > 12000:
            return error(422, "invalid_request", "Câu hỏi trống hoặc quá dài.")
        service.database(query.mode, query.dataset_split)
        if len(jobs) >= max_in_flight:
            return error(429, "busy", "Đang xử lý câu hỏi khác; vui lòng thử lại sau.")
        task = asyncio.create_task(asyncio.to_thread(service.ask, query))
        jobs.add(task)

        def finished(job):
            jobs.discard(job)
            if not job.cancelled():
                job.exception()  # consume errors from work that finished after HTTP timeout

        task.add_done_callback(finished)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout_seconds)
        except TimeoutError:
            return error(504, "query_timeout", "Hết thời gian xử lý; vui lòng thử lại sau.")
        except (RetrievalError, sqlite3.Error, OSError, ValidationError):
            return error(503, "index_unavailable", "Index chưa sẵn sàng hoặc vừa thay đổi; kiểm tra import/build.")
        except (GenerationError, EmbeddingError, TranslationError):
            return error(503, "provider_unavailable", "Dịch vụ AI chưa sẵn sàng; vui lòng thử lại sau.")

    @app.get("/v1/evidence/{workflow_id}/{revision}/{evidence_id}")
    def evidence(workflow_id: str, revision: int, evidence_id: str, mode: str,
                 dataset_split: str, index_build_id: str):
        try:
            data, _ = service.evidence(mode, dataset_split, index_build_id, workflow_id, revision, evidence_id)
            return data
        except (sqlite3.Error, OSError, RetrievalError):
            return error(503, "index_unavailable", "Kho bằng chứng chưa sẵn sàng.")

    @app.get("/v1/workflows")
    def workflows(mode: str, dataset_split: str):
        try:
            return service.browser.catalog(mode, dataset_split)
        except (sqlite3.Error, OSError, RetrievalError, ValidationError):
            return error(503, "index_unavailable", "Index chưa sẵn sàng; kiểm tra import/build.")

    @app.get("/v1/workflows/{workflow_id}/{revision}")
    def workflow(workflow_id: str, revision: int, mode: str, dataset_split: str, index_build_id: str):
        try:
            return service.browser.workflow(workflow_id, revision, mode, dataset_split, index_build_id)
        except (sqlite3.Error, OSError, RetrievalError, ValidationError):
            return error(503, "index_unavailable", "Kho workflow chưa sẵn sàng.")

    @app.get("/v1/workflows/{workflow_id}/{revision}/history")
    def history(workflow_id: str, revision: int, mode: str, dataset_split: str, index_build_id: str):
        try:
            return service.browser.history(workflow_id, revision, mode, dataset_split, index_build_id)
        except (sqlite3.Error, OSError, RetrievalError, ValidationError):
            return error(503, "index_unavailable", "Lịch sử workflow chưa sẵn sàng.")

    @app.get("/v1/evidence/{workflow_id}/{revision}/{evidence_id}/asset")
    def asset(workflow_id: str, revision: int, evidence_id: str, mode: str,
              dataset_split: str, index_build_id: str):
        try:
            _, view = service.evidence(mode, dataset_split, index_build_id, workflow_id, revision, evidence_id)
        except (sqlite3.Error, OSError, RetrievalError):
            return error(503, "index_unavailable", "Kho bằng chứng chưa sẵn sàng.")
        if view.asset_path is None:
            return error(404, "asset_unavailable", "Không có keyframe đã lưu cho bằng chứng này.")
        return FileResponse(view.asset_path, media_type=view.media_type,
                            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(static / "index.html")

    return app
