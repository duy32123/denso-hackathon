"""Bundle -> import -> index -> retrieval -> guarded answer -> exact evidence HTTP.

Only the external LLM is a test double. No API key, embeddings, or media network
calls in CI. This is integration/contract coverage, not an answer-quality score.
"""

import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from conftest import FIXTURE_ROOT, REPO_ROOT
from knowflow_contracts.models import AnswerResponse
from retrieval.api.app import create_app
from retrieval.generation.models import AnswerDraft, GenerationError, Verification
from retrieval.generation.service import QAService
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index
from retrieval.retrieval.engine import RetrievalConfig


class Model:
    def __init__(self):
        self.calls = 0
        self.closed = False
        self.accept = True

    def draft(self, payload):
        self.calls += 1
        item = payload["candidates"][0]
        return AnswerDraft(status="answered", statements=[{
            "text": item["claim"]["text"], "claim_ref": item["claim_ref"],
            "evidence_ids": [item["evidence"][0]["evidence"]["evidence_id"]]}])

    def verify(self, payload):
        self.calls += 1
        return Verification(answers_question=self.accept, supported=[self.accept])

    def close(self):
        self.closed = True


@pytest.fixture
def setup_api(tmp_path):
    db = tmp_path / "real.sqlite"
    import_bundle(REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle", db, source_type="real", split="dev")
    build_index(db, mode="real", split="dev")
    model = Model()
    service = QAService({("real", "dev"): db}, repo_root=REPO_ROOT,
                        config=RetrievalConfig(strategy="lexical"), model_factory=lambda: model)
    return service, model


def question(**kwargs):
    return {"question": "How is the pocket slider lubricated?", "context": {"manufacturer": "Haas", "subsystem": "SMTC"},
            "mode": "real", "dataset_split": "dev", **kwargs}


def evidence_path(answer, mode="real"):
    citation = answer["citations"][0]
    ref = citation["claim_ref"]
    path = f"/v1/evidence/{ref['workflow_id']}/{ref['revision']}/{citation['evidence_ids'][0]}"
    return path, {"mode": mode, "dataset_split": "dev", "index_build_id": answer["index_build_id"]}


def test_real_question_to_openable_citation_and_ui(setup_api):
    service, model = setup_api
    before = service.databases[("real", "dev")].read_bytes()
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/ask", json=question())
        assert response.status_code == 200, response.text
        answer = AnswerResponse.model_validate(response.json())
        assert answer.status == "answered" and answer.citations
        assert model.closed and model.calls == 2
        path, params = evidence_path(response.json())
        evidence = client.get(path, params=params)
        assert evidence.status_code == 200
        body = evidence.json()
        assert body["available"] and body["access_kind"] == "retained_transcript"
        assert not body["external_video_checked"]
        assert body["text"] == body["evidence"]["quote"]
        assert "raw_text" not in body["source"]
        assert body["workflow"]["revision"] == answer.citations[0].claim_ref.revision
        assert client.get(path + "/asset", params=params).status_code == 404
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/v1/health").json()["namespaces"] == [{"mode": "real", "dataset_split": "dev"}]
    assert service.databases[("real", "dev")].read_bytes() == before  # entire ask/view flow is read-only


@pytest.mark.parametrize("patch", [
    {"question": " "}, {"question": "x" * 4001}, {"question": None}, {"mode": "other"},
    {"context": {"unknown": "bad"}}, {"database": "C:/secret.sqlite"}, {"model": "unsafe"},
])
def test_bad_request_has_safe_error_without_call(setup_api, patch):
    service, model = setup_api
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/ask", json=question(**patch))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
        assert not model.calls


@pytest.mark.parametrize("patch", [{"mode": "synthetic"}, {"dataset_split": "holdout"}])
def test_disabled_namespace_never_falls_back_to_real_dev(setup_api, patch):
    service, model = setup_api
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/ask", json=question(**patch))
        assert response.status_code == 422 and not model.calls
        assert response.json()["error"]["code"] == "namespace_unavailable"


def test_out_of_scope_and_unknown_model_no_generation(setup_api):
    service, model = setup_api
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/ask", json=question(question="How to cook spaghetti?", context={}))
        assert response.json()["status"] == "insufficient_evidence"
        response = client.post("/v1/ask", json=question(context={"machine_model": "VF-2"}))
        assert response.json()["status"] == "needs_clarification"
        assert "machine_model" in response.json()["missing_context"]
        assert model.calls == 0


def test_semantic_verifier_rejects_related_but_non_answer(setup_api):
    service, model = setup_api
    model.accept = False
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/ask", json=question(question="What grade of grease is required for the pocket slider?"))
        assert response.status_code == 200
        assert response.json()["status"] == "insufficient_evidence" and response.json()["citations"] == []


def test_provider_error_does_not_expose_exception_or_key(setup_api):
    service, _ = setup_api
    def fail(payload):
        raise GenerationError("https://provider?key=SECRET")
    service.model_factory().draft = fail
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/ask", json=question())
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "provider_unavailable"
        assert "SECRET" not in response.text


def test_index_missing_and_index_change_during_generation_are_blocked(setup_api):
    service, model = setup_api
    db = service.databases[("real", "dev")]
    original = model.verify
    def advance(payload):
        verdict = original(payload)
        with sqlite3.connect(db) as conn:
            conn.execute("DELETE FROM settings WHERE key='active_retrieval_build'")
        return verdict
    model.verify = advance
    with TestClient(create_app(service)) as client:
        for _ in range(2):
            response = client.post("/v1/ask", json=question())
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "index_unavailable"


def test_citation_cannot_switch_revision_build_or_corpus(setup_api):
    service, _ = setup_api
    with TestClient(create_app(service)) as client:
        answer = client.post("/v1/ask", json=question()).json()
        path, params = evidence_path(answer)
        # Swap the revision segment itself: the cited workflow may be at any revision,
        # and a string replace of "/1/" silently left an r2 path valid (200, not 404).
        parts = path.split("/")  # ["", "v1", "evidence", workflow_id, revision, evidence_id]
        assert parts[4] != "999"
        parts[4] = "999"
        assert client.get("/".join(parts), params=params).status_code == 404
        assert client.get(path, params={**params, "index_build_id": "invented"}).status_code == 404
        assert client.get(path, params={**params, "mode": "synthetic"}).status_code == 422
        assert client.get(path, params={**params, "dataset_split": "holdout"}).status_code == 422


def test_valid_keyframe_is_served_without_external_network(setup_api, tmp_path):
    import json
    from PIL import Image

    from retrieval.generation.evidence import EvidenceAccess

    service, _ = setup_api
    service.access = EvidenceAccess(tmp_path)
    db = service.databases[("real", "dev")]
    with sqlite3.connect(db) as conn:
        wf = json.loads(conn.execute("SELECT payload FROM snapshots WHERE workflow_id='REAL_WF_0001'").fetchone()[0])
        build = conn.execute("SELECT value FROM settings WHERE key='active_retrieval_build'").fetchone()[0]
    ev = next(e for e in wf["evidence"] if e["modality"] == "visual")
    path = tmp_path / ev["asset_uri"]
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16)).save(path)
    params = {"mode": "real", "dataset_split": "dev", "index_build_id": build}
    url = f"/v1/evidence/{wf['workflow_id']}/{wf['revision']}/{ev['evidence_id']}"
    with TestClient(create_app(service)) as client:
        metadata = client.get(url, params=params).json()
        assert metadata["available"] and metadata["access_kind"] == "keyframe"
        response = client.get(url + "/asset", params=params)
        assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
        assert response.content == path.read_bytes()
        path.write_text("corrupted image", encoding="utf-8")
        assert not client.get(url, params=params).json()["available"]
        assert client.get(url + "/asset", params=params).status_code == 404


def test_timeout_keeps_job_counted_until_provider_finishes(setup_api):
    service, _ = setup_api
    finished = threading.Event()
    started = threading.Event()
    def blocking(request):
        started.set()
        finished.wait(5)
        raise GenerationError("late provider error")
    service.ask = blocking
    with TestClient(create_app(service, timeout_seconds=.05, max_in_flight=1)) as client:
        try:
            assert client.post("/v1/ask", json=question()).status_code == 504
            assert started.is_set()
            assert client.post("/v1/ask", json=question()).status_code == 429
        finally:
            finished.set()


@pytest.mark.parametrize("fixture,query,status", [
    ("F01_complete", "Cách tháo nắp che?", "answered"),
    ("F06_conflict", "den bao sau reset", "conflicting_sources"),
])
def test_synthetic_and_conflict_http_flow(tmp_path, fixture, query, status):
    db = tmp_path / "synthetic.sqlite"
    import_bundle(FIXTURE_ROOT / fixture, db, source_type="synthetic", split="dev")
    build_index(db, mode="synthetic", split="dev")
    model = Model()
    service = QAService({("synthetic", "dev"): db}, repo_root=REPO_ROOT,
                        config=RetrievalConfig(strategy="lexical"), model_factory=lambda: model)
    with TestClient(create_app(service)) as client:
        context = {"machine_model": "DEMO_TC_A"} if fixture == "F01_complete" else {}
        response = client.post("/v1/ask", json=question(question=query, mode="synthetic", context=context))
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["status"] == status
        if status == "answered":
            assert "Dữ liệu mô phỏng" in answer["answer"]
            path, params = evidence_path(answer, "synthetic")
            evidence = client.get(path, params=params).json()
            assert evidence["access_kind"] == "synthetic_text" and evidence["source"]["url"] is None
            assert client.get(path + "/asset", params=params).status_code == 404
        else:
            assert not model.calls and answer["unresolved_claim_refs"] and not answer["citations"]


def test_historical_citation_stays_on_its_indexed_revision(tmp_path):
    from conftest import read_bundle, write_bundle

    data = read_bundle(FIXTURE_ROOT / "F09_revision_update")
    first = {**data, "workflows": data["workflows"][:1]}
    db = tmp_path / "history.sqlite"
    import_bundle(write_bundle(tmp_path / "r1", first), db, source_type="synthetic", split="dev")
    old_build = build_index(db, mode="synthetic", split="dev")["index_build_id"]
    import_bundle(FIXTURE_ROOT / "F09_revision_update", db, source_type="synthetic", split="dev")
    new_build = build_index(db, mode="synthetic", split="dev")["index_build_id"]
    service = QAService({("synthetic", "dev"): db}, repo_root=REPO_ROOT)
    wf = first["workflows"][0]
    ev = wf["evidence"][0]
    with TestClient(create_app(service)) as client:
        path = f"/v1/evidence/{wf['workflow_id']}/1/{ev['evidence_id']}"
        params = {"mode": "synthetic", "dataset_split": "dev", "index_build_id": old_build}
        result = client.get(path, params=params)
        assert result.status_code == 200 and result.json()["workflow"]["revision"] == 1
        assert client.get(path, params={**params, "index_build_id": new_build}).status_code == 404
