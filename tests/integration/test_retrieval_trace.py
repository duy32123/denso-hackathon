"""Real retrieval telemetry, exact scope and guarded generation; no external AI."""
import json
import sqlite3
import threading
import time

import pytest
from fastapi.testclient import TestClient

from conftest import REPO_ROOT
from retrieval.api.app import create_app
from retrieval.generation.models import AnswerDraft, GenerationError, Verification
from retrieval.generation.service import QAService
from retrieval.generation.tracing import TraceRequest, TraceCancelled
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index
from retrieval.retrieval.engine import RetrievalConfig, retrieve


class Model:
    def __init__(self):
        self.calls = 0
        self.closed = False

    def draft(self, payload):
        self.calls += 1
        candidate = payload["candidates"][0]
        return AnswerDraft(status="answered", statements=[{
            "text": candidate["claim"]["text"], "claim_ref": candidate["claim_ref"],
            "evidence_ids": [candidate["evidence"][0]["evidence"]["evidence_id"]]}])

    def verify(self, payload):
        self.calls += 1
        return Verification(answers_question=True, supported=[True])

    def close(self):
        self.closed = True


@pytest.fixture
def traced(tmp_path):
    db = tmp_path / "real.sqlite"
    import_bundle(REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle", db, source_type="real", split="dev")
    build = build_index(db, mode="real", split="dev")["index_build_id"]
    model = Model()
    service = QAService({("real", "dev"): db}, repo_root=REPO_ROOT,
                        config=RetrievalConfig(strategy="lexical"), model_factory=lambda: model)
    payload = {"query": {"question": "What should I do if automatic recovery fails?",
                         "context": {"manufacturer": "Haas", "subsystem": "SMTC"},
                         "mode": "real", "dataset_split": "dev"}, "index_build_id": build}
    return service, model, payload


def events(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_observed_route_matches_real_dependency_and_openable_evidence(traced):
    service, model, payload = traced
    db = service.databases[("real", "dev")]
    before = db.read_bytes()
    with TestClient(create_app(service)) as client:
        items = events(client.post("/v1/trace", json=payload))
        assert [e["stage"] for e in items] == ["started", "context", "relevance", "ranked", "matched", "expanded",
                                              "retrieval_complete", "evidence", "done"]
        assert [e["seq"] for e in items] == list(range(1, len(items) + 1))
        assert all(e["origin"] == "observed_pipeline" and e["index_build_id"] == payload["index_build_id"] for e in items)
        result = retrieve(db, TraceRequest.model_validate(payload).query, config=RetrievalConfig(strategy="lexical", top_k=1))
        expanded = next(e for e in items if e["stage"] == "expanded")
        actual = {(s["workflow_id"], s["revision"], r["relation_id"]) for s in result["related_steps"] for r in s["via"]}
        assert {(r["workflow_id"], r["revision"], r["entity_id"]) for r in expanded["refs"] if r["kind"] == "relation"} == actual
        assert expanded["data"]["related_steps"] == 1
        final = items[-1]["data"]
        assert final["status"] == result["status"] == "retrieved"
        assert final["selected_workflow"] == result["selected_workflow"]
        assert final["answer"] is None and not model.calls
        for candidate in final["candidates"]:
            ref = candidate["claim_ref"]
            for eid in candidate["evidence_ids"]:
                response = client.get(f"/v1/evidence/{ref['workflow_id']}/{ref['revision']}/{eid}", params={
                    "mode": "real", "dataset_split": "dev", "index_build_id": payload["index_build_id"]})
                assert response.json()["available"]
        assert "asset_uri" not in json.dumps(items) and "raw_text" not in json.dumps(items)
    assert db.read_bytes() == before


def test_optional_model_runs_once_and_only_verified_citations_are_emitted(traced):
    service, model, payload = traced
    with TestClient(create_app(service)) as client:
        items = events(client.post("/v1/trace", json={**payload, "generate_answer": True}))
    assert model.calls == 2 and model.closed
    assert [e["stage"] for e in items][-4:] == ["drafting", "verifying", "citations", "done"]
    answer = items[-1]["data"]["answer"]
    assert answer["status"] == "answered" and answer["index_build_id"] == payload["index_build_id"]
    cited = next(e for e in items if e["stage"] == "citations")["refs"]
    assert {r["entity_id"] for r in cited if r["kind"] == "claim"} == {c["claim_ref"]["entity_id"] for c in answer["citations"]}
    assert all(r["state"] == "cited" for r in cited)


@pytest.mark.parametrize("query_patch,status", [
    ({"question": "How to cook spaghetti?", "context": {}}, "insufficient_evidence"),
    ({"context": {"machine_model": "VF-2"}}, "needs_clarification"),
])
def test_early_stop_has_no_fake_route_or_model_call(traced, query_patch, status):
    service, model, payload = traced
    payload["query"].update(query_patch)
    with TestClient(create_app(service)) as client:
        items = events(client.post("/v1/trace", json={**payload, "generate_answer": True}))
    assert items[-1]["data"]["status"] == status
    assert items[-1]["data"]["candidates"] == []
    assert not any(e["stage"] in ("ranked", "matched", "expanded", "drafting", "verifying") for e in items)
    assert not model.calls


@pytest.mark.parametrize("patch", [{"top_k": 0}, {"top_k": 6}, {"model": "unsafe"}, {"database": "C:/secret"}])
def test_trace_cannot_override_server_model_or_database(traced, patch):
    service, model, payload = traced
    with TestClient(create_app(service)) as client:
        assert client.post("/v1/trace", json={**payload, **patch}).status_code == 422
    assert not model.calls


def test_wrong_build_namespace_and_holdout_do_not_start_stream(traced):
    service, model, payload = traced
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/trace", json={**payload, "index_build_id": "other"})
        assert response.status_code == 409
        for patch in ({"mode": "synthetic"}, {"dataset_split": "holdout"}):
            assert client.post("/v1/trace", json={**payload, "query": {**payload["query"], **patch}}).status_code == 422
    assert not model.calls


def test_provider_failure_keeps_partial_real_trace_without_leaking_secret(traced):
    service, model, payload = traced
    def fail(payload):
        raise GenerationError("provider?key=SECRET")
    model.draft = fail
    with TestClient(create_app(service)) as client:
        items = events(client.post("/v1/trace", json={**payload, "generate_answer": True}))
    assert any(e.get("stage") == "evidence" for e in items)
    assert items[-1]["type"] == "error" and items[-1]["code"] == "provider_unavailable"
    assert "SECRET" not in json.dumps(items) and model.closed
    assert not any(e["type"] == "result" for e in items)


def test_cancelled_trace_never_starts_model(traced):
    service, model, payload = traced
    cancelled = threading.Event()
    def emit(event):
        if event["stage"] == "matched":
            cancelled.set()
    with pytest.raises(TraceCancelled):
        service.trace(TraceRequest.model_validate({**payload, "generate_answer": True}), emit, cancelled)
    assert not model.calls


def test_index_change_prevents_final_result(traced):
    service, model, payload = traced
    original = model.verify
    def advance(p):
        result = original(p)
        with sqlite3.connect(service.databases[("real", "dev")]) as conn:
            conn.execute("DELETE FROM settings WHERE key='active_retrieval_build'")
        return result
    model.verify = advance
    with TestClient(create_app(service)) as client:
        items = events(client.post("/v1/trace", json={**payload, "generate_answer": True}))
    assert items[-1]["type"] == "error" and items[-1]["code"] == "index_unavailable"
    assert not any(e["type"] == "result" for e in items)


def test_timeout_keeps_worker_counted_until_provider_finishes(traced):
    service, model, payload = traced
    started, release = threading.Event(), threading.Event()
    original = model.draft
    def slow(p):
        started.set()
        release.wait(timeout=5)
        return original(p)
    model.draft = slow
    try:
        with TestClient(create_app(service, timeout_seconds=1, max_in_flight=1)) as client:
            items = events(client.post("/v1/trace", json={**payload, "generate_answer": True}))
            assert started.is_set()
            assert items[-1]["code"] == "query_timeout"
            assert client.post("/v1/ask", json=payload["query"]).status_code == 429
            release.set()
            deadline = time.monotonic() + 3
            while not model.closed and time.monotonic() < deadline:
                time.sleep(.01)
            assert model.closed
    finally:
        release.set()
