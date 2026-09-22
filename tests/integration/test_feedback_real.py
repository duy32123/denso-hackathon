"""D2-A: duong ghi THAT qua HTTP -- POST /v1/feedback/submit -> kho chuan cua doi 1.

Khac `test_feedback.py` (chi kiem stub, khong bao gio ghi), bo nay chay dung
`RealFeedbackService` tren mot **ban sao** kho chuan trong thu muc tam. Day la
buoc 4-5 cua contract muc 7: phan hoi -> revision moi -> import lai -> hoi lai.

`test_the_real_repo_is_never_touched` giu dieu quan trong nhat: bo test nay ghi
that, nhung khong duoc cham vao `data/workflows`, `data/sources` hay bundle da xuat.
"""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest
from conftest import REPO_ROOT
from fastapi.testclient import TestClient

from acquisition.export.exporter import SPLITS
from acquisition.extraction import feedback_service as d1b
from retrieval.api.app import create_app
from retrieval.generation.feedback import RealFeedbackService
from retrieval.generation.service import QAService
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index

WATCHED = (
    REPO_ROOT / "data" / "workflows",
    REPO_ROOT / "data" / "sources",
    REPO_ROOT / "acquisition" / "export" / "haas_pilot_dev_bundle",
    REPO_ROOT / "acquisition" / "feedback",
)


def no_model():
    raise AssertionError("Feedback must never call an LLM")


def fingerprint() -> dict[str, str]:
    prints = {}
    for root in WATCHED:
        if not root.exists():
            prints[str(root)] = "<absent>"
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                prints[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return prints


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Ban sao kho chuan dev, moi duong dan tro sang thu muc tam."""
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "data/workflows", root / "data/workflows")
    shutil.copytree(REPO_ROOT / "data/sources", root / "data/sources")
    out = root / "acquisition/export/haas_pilot_dev_bundle"
    shutil.copytree(REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle", out)

    monkeypatch.setitem(SPLITS["dev"], "sources", root / "data/sources/haas_pilot_sources.jsonl")
    monkeypatch.setitem(SPLITS["dev"], "snapshots", root / "data/workflows/dev")
    monkeypatch.setitem(SPLITS["dev"], "out", out)
    monkeypatch.setattr(d1b, "REPO_ROOT", root)
    return root


@pytest.fixture
def client(sandbox, tmp_path):
    """API noi voi RealFeedbackService, index dung tu bundle trong sandbox."""
    db = tmp_path / "real.sqlite"
    import_bundle(sandbox / "acquisition/export/haas_pilot_dev_bundle", db,
                  source_type="real", split="dev")
    build_index(db, mode="real", split="dev")
    service = QAService({("real", "dev"): db}, repo_root=REPO_ROOT, model_factory=no_model)
    service.feedback = RealFeedbackService()
    with TestClient(create_app(service)) as http:
        yield http, sandbox, db


def target(http, workflow_id="REAL_WF_0001"):
    catalog = http.get("/v1/workflows", params={"mode": "real", "dataset_split": "dev"}).json()
    entry = next(w for w in catalog["workflows"] if w["workflow_id"] == workflow_id)
    data = http.get(f"/v1/workflows/{workflow_id}/{entry['revision']}", params={
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
        "answer_text": "Ngat khi nen chinh de mam dao khong the quay khi tay nguoi con ben trong.",
        "responder": {"actor_id": "dpv137", "label": "Nguoi thu nghiem",
                      "role": "ky thuat vien bao tri"},
        "language": "vi",
    }
    payload.update(over)
    return payload


# --- preview qua duong that ----------------------------------------------------


def test_preview_is_no_longer_simulated_and_writes_nothing(client):
    """Nut Luu bat duoc: preview that khong co co `simulated` nua (feedback.js dong 128)."""
    http, _sandbox, _ = client
    workflow, question = target(http)
    before = fingerprint()

    response = http.post("/v1/feedback/preview", json=body(workflow, question))
    assert response.status_code == 200
    preview = response.json()

    assert "simulated" not in preview
    assert preview["next_revision"] == workflow["revision"] + 1
    assert preview["conflict"] is None
    assert preview["validation"]["ok"], preview["validation"]["errors"]
    assert preview["responder_authenticated"] is False
    claim = preview["new_claims"][0]
    assert claim["source_review"] == "pending" and claim["technical_review"] == "not_requested"
    assert fingerprint() == before


def test_preview_gives_feedback_js_every_field_it_renders(client):
    """renderPreview() doc dung nhung khoa nay; thieu mot cai la man Bo sung vo."""
    http, _, _ = client
    workflow, question = target(http)
    preview = http.post("/v1/feedback/preview", json=body(workflow, question)).json()

    change = preview["field_changes"][0]
    assert {"step_id", "field", "before", "after"} <= set(change)
    assert {"state", "claim_ids"} <= set(change["before"]) <= set(change["after"]) | {"state", "claim_ids"}
    assert {"text", "source_review", "technical_review"} <= set(preview["new_claims"][0])
    assert {"evidence_id", "modality"} <= set(preview["new_evidence"][0])
    assert {"source_id", "source_kind"} <= set(preview["source"])
    assert preview["question_transition"]["from"] == "open"
    assert isinstance(preview["warnings"], list)


# --- submit: vong G2 -----------------------------------------------------------


def test_submit_creates_the_next_revision_in_the_store(client):
    http, sandbox, _ = client
    workflow, question = target(http)

    response = http.post("/v1/feedback/submit", json=body(workflow, question))
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["workflow_id"] == workflow["workflow_id"]
    assert data["revision"] == workflow["revision"] + 1
    assert data["created_source_id"].startswith("SRC_EXP_")
    assert len(data["created_claim_ids"]) == 1
    assert data["reindex_required"] is True
    assert data["review_required"] is True

    written = sandbox / data["snapshot_path"]
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8"))["revision"] == data["revision"]
    assert (sandbox / data["asset_path"]).is_file()


def test_submitted_claim_is_pending_so_it_cannot_answer_yet(client):
    """Bat bien so 3: phan hoi lam tri thuc day them, khong lam no dung them."""
    http, sandbox, _ = client
    workflow, question = target(http)
    data = http.post("/v1/feedback/submit", json=body(workflow, question)).json()

    snapshot = json.loads((sandbox / data["snapshot_path"]).read_text(encoding="utf-8"))
    claim = next(c for c in snapshot["claims"] if c["claim_id"] == data["created_claim_ids"][0])
    assert claim["source_review"] == "pending"
    assert claim["technical_review"] == "not_requested"


def test_the_new_revision_can_be_imported_and_served(client):
    """Buoc 5 cua contract muc 7: import lai bundle moi thi thay revision moi."""
    http, sandbox, _ = client
    workflow, question = target(http)
    data = http.post("/v1/feedback/submit", json=body(workflow, question)).json()

    fresh = sandbox / "reimported.sqlite"
    import_bundle(sandbox / data["bundle_export"], fresh, source_type="real", split="dev")
    build_index(fresh, mode="real", split="dev")

    service = QAService({("real", "dev"): fresh}, repo_root=REPO_ROOT, model_factory=no_model)
    with TestClient(create_app(service)) as after:
        workflow_after, _ = target(after)
        assert workflow_after["revision"] == data["revision"]
        question_after = next(q for q in workflow_after["questions"]
                              if q["question_id"] == question["question_id"])
        assert question_after["status"] == "answered"
        assert data["created_source_id"] in question_after["answer_source_ids"]


def test_old_revision_stays_readable_after_the_write(client):
    """Revision cu bat bien: citation da phat hanh van mo dung noi dung cu."""
    http, sandbox, _ = client
    workflow, question = target(http)
    before = (sandbox / f"data/workflows/dev/{workflow['workflow_id']}.r{workflow['revision']}.json").read_bytes()

    http.post("/v1/feedback/submit", json=body(workflow, question))

    after = (sandbox / f"data/workflows/dev/{workflow['workflow_id']}.r{workflow['revision']}.json").read_bytes()
    assert after == before


# --- ca loi di qua dung ma HTTP ------------------------------------------------


def test_stale_base_revision_is_409_not_an_overwrite(client):
    http, sandbox, _ = client
    workflow, question = target(http)
    http.post("/v1/feedback/submit", json=body(workflow, question))
    r2 = (sandbox / f"data/workflows/dev/{workflow['workflow_id']}.r2.json").read_bytes()

    again = http.post("/v1/feedback/submit", json=body(workflow, question))
    assert again.status_code == 409
    error = again.json()["error"]
    assert error["code"] == "base_revision_conflict"
    assert error["latest_revision"] == 2 and error["base_revision"] == 1
    assert (sandbox / f"data/workflows/dev/{workflow['workflow_id']}.r2.json").read_bytes() == r2


def test_unknown_step_is_404(client):
    http, _, _ = client
    workflow, question = target(http)
    response = http.post("/v1/feedback/preview", json=body(workflow, question, step_id="KHONG_CO"))
    assert response.status_code == 404


def test_locked_corpus_is_422_with_a_readable_reason(client):
    """synthetic/holdout bi chan o phia doi 1, khong duoc thanh loi 500."""
    http, _, _ = client
    workflow, question = target(http)
    response = http.post("/v1/feedback/preview", json=body(workflow, question, mode="synthetic"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] in ("feedback_invalid", "namespace_unavailable")


def test_a_held_lock_is_429_not_500(client, monkeypatch):
    """Ghi dong thoi: bao ban de thu lai, khong nuot thanh loi noi bo."""
    http, sandbox, _ = client
    workflow, question = target(http)
    monkeypatch.setattr(d1b, "LOCK_TIMEOUT_S", 0.1)
    lock = SPLITS["dev"]["snapshots"].parent / ".feedback.dev.lock"
    lock.write_text("held\n", encoding="utf-8")
    try:
        response = http.post("/v1/feedback/submit", json=body(workflow, question))
    finally:
        lock.unlink()

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "feedback_busy"
    assert not (sandbox / f"data/workflows/dev/{workflow['workflow_id']}.r2.json").exists()


# --- rang buoc quan trong nhat -------------------------------------------------


def test_the_real_repo_is_never_touched(client):
    """Bo test nay ghi that; kho chuan cua repo phai nguyen ven."""
    http, _, _ = client
    workflow, question = target(http)
    before = fingerprint()

    http.post("/v1/feedback/preview", json=body(workflow, question))
    http.post("/v1/feedback/submit", json=body(workflow, question))

    assert fingerprint() == before
