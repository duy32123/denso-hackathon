"""WP4 man Bo sung: duong goi sang service ghi cua doi 1.

Doi 2 khong ghi vao kho chuan. Bo test nay giu dung mot dieu: moi duong di qua
day deu KHONG lam thay doi database, va khi chua co service that thi khong co
cach nao "luu" duoc.
"""

import pytest
from fastapi.testclient import TestClient

from conftest import REPO_ROOT
from retrieval.api.app import create_app
from retrieval.generation.browse import WorkflowBrowser
from retrieval.generation.feedback import StubFeedbackService
from retrieval.generation.service import QAService
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index


def no_model():
    raise AssertionError("Feedback must never call an LLM")


def service_for(db, **kwargs):
    return QAService({("real", "dev"): db}, repo_root=REPO_ROOT, model_factory=no_model, **kwargs)


@pytest.fixture
def pilot(tmp_path):
    db = tmp_path / "real.sqlite"
    import_bundle(REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle", db,
                  source_type="real", split="dev")
    build_index(db, mode="real", split="dev")
    return db


@pytest.fixture
def stub(pilot):
    service = service_for(pilot)
    service.feedback = StubFeedbackService(WorkflowBrowser(service.database))
    with TestClient(create_app(service)) as client:
        yield client, pilot, service


def target(client, workflow_id="REAL_WF_0001"):
    """Lay revision, mot step va mot cau hoi dang mo tu chinh snapshot."""
    catalog = client.get("/v1/workflows", params={"mode": "real", "dataset_split": "dev"}).json()
    entry = next(w for w in catalog["workflows"] if w["workflow_id"] == workflow_id)
    data = client.get(f"/v1/workflows/{workflow_id}/{entry['revision']}", params={
        "mode": "real", "dataset_split": "dev", "index_build_id": catalog["index_build_id"]}).json()
    workflow = data["workflow"]
    question = next((q for q in workflow["questions"] if q["status"] == "open"), None)
    return workflow, question


def body(workflow, question=None, **over):
    payload = {
        "mode": "real", "dataset_split": "dev",
        "workflow_id": workflow["workflow_id"], "base_revision": workflow["revision"],
        "step_id": question["step_id"] if question else workflow["steps"][0]["step_id"],
        "target_field": question["target_field"] if question else "rationale",
        "question_id": question["question_id"] if question else None,
        "answer_text": "Phai thao nap che truoc vi khong nhin duoc duong day tin hieu.",
        "responder": {"actor_id": "dpv137", "label": "Nguoi thu nghiem",
                      "role": "ky thuat vien bao tri"},
        "language": "vi",
    }
    payload.update(over)
    return payload


def test_without_a_write_service_there_is_no_way_to_save(pilot):
    """Chua cau hinh service => 503 o ca preview lan submit, khong phai loi 500."""
    with TestClient(create_app(service_for(pilot))) as client:
        workflow, question = target(client)
        for path in ("/v1/feedback/preview", "/v1/feedback/submit"):
            response = client.post(path, json=body(workflow, question))
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "feedback_unavailable"


def test_preview_shows_the_change_and_writes_nothing(stub):
    client, db, _ = stub
    workflow, question = target(client)
    before = db.read_bytes()

    response = client.post("/v1/feedback/preview", json=body(workflow, question))
    assert response.status_code == 200
    preview = response.json()

    assert preview["simulated"] is True
    assert preview["next_revision"] == workflow["revision"] + 1
    assert preview["conflict"] is None
    # Co phan hoi KHONG phai la da kiem nguon, cang khong phai chuyen gia xac nhan (V07).
    claim = preview["new_claims"][0]
    assert claim["source_review"] == "pending" and claim["technical_review"] == "not_requested"
    # V02: nguon expert_answer trong corpus real phai co duong dan truy cap.
    assert preview["source"]["source_kind"] == "expert_answer"
    assert preview["source"]["raw_text"] and preview["source"]["asset_uri"]
    # Nguyen van phan hoi di thang vao quote, khong tom tat.
    assert preview["new_evidence"][0]["quote"] == body(workflow, question)["answer_text"]
    assert preview["responder_authenticated"] is False
    if question:
        assert preview["question_transition"]["to"] == "answered"
    assert db.read_bytes() == before, "preview khong duoc ghi gi"


def test_stale_base_revision_is_a_conflict_not_an_overwrite(stub):
    client, db, _ = stub
    workflow, question = target(client)
    before = db.read_bytes()

    response = client.post("/v1/feedback/preview",
                           json=body(workflow, question, base_revision=workflow["revision"] - 1))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "base_revision_conflict"
    assert error["latest_revision"] == workflow["revision"]
    assert error["base_revision"] == workflow["revision"] - 1
    assert db.read_bytes() == before


def test_step_and_question_must_belong_to_this_revision(stub):
    client, _, _ = stub
    workflow, question = target(client)
    assert client.post("/v1/feedback/preview",
                       json=body(workflow, question, step_id="KHONG_CO_STEP")).status_code == 404
    assert client.post("/v1/feedback/preview",
                       json=body(workflow, question, question_id="KHONG_CO_Q")).status_code == 404


def test_responder_role_and_text_are_required(stub):
    client, _, _ = stub
    workflow, question = target(client)
    no_role = client.post("/v1/feedback/preview", json=body(
        workflow, question, responder={"actor_id": "dpv137", "label": "Nguoi thu nghiem", "role": ""}))
    assert no_role.status_code == 422
    empty = client.post("/v1/feedback/preview", json=body(workflow, question, answer_text=""))
    assert empty.status_code == 422


def test_submit_refuses_while_the_service_is_only_a_stub(stub):
    client, db, _ = stub
    workflow, question = target(client)
    before = db.read_bytes()
    response = client.post("/v1/feedback/submit", json=body(workflow, question))
    assert response.status_code == 503
    assert "D1-B" in response.json()["error"]["message"]
    assert db.read_bytes() == before


def test_simulated_submit_still_leaves_the_knowledge_base_untouched(pilot):
    """allow_submit chi dung trong test; ke ca the thi KB van khong duoc dong vao."""
    service = service_for(pilot)
    service.feedback = StubFeedbackService(WorkflowBrowser(service.database), allow_submit=True)
    with TestClient(create_app(service)) as client:
        workflow, question = target(client)
        before = pilot.read_bytes()
        response = client.post("/v1/feedback/submit", json=body(workflow, question))
        assert response.status_code == 200
        data = response.json()
        assert data["simulated"] is True and data["revision"] == workflow["revision"] + 1
        assert pilot.read_bytes() == before
        assert len(service.feedback.submitted) == 1
        # Kho van chi co dung revision cu: khong co ban moi nao duoc tao.
        catalog = client.get("/v1/workflows", params={"mode": "real", "dataset_split": "dev"}).json()
        entry = next(w for w in catalog["workflows"] if w["workflow_id"] == workflow["workflow_id"])
        assert entry["revision"] == workflow["revision"]


def test_corpus_must_be_enabled(stub):
    client, _, _ = stub
    workflow, question = target(client)
    response = client.post("/v1/feedback/preview", json=body(workflow, question, mode="synthetic"))
    assert response.status_code == 422
