"""D2-A: RealFeedbackService dich loi cua D1-B sang loai cua doi 2.

Chi kiem logic dich, khong cham dia: mock truc tiep `acquisition.extraction.
feedback_service.preview`/`.submit` de ep tung loai loi typed cua D1-B, roi kiem
adapter re-raise dung loai + dung thuoc tinh ma app.py/feedback.js dang doc.
"""
from __future__ import annotations

import pytest

from acquisition.extraction import feedback_service as d1b
from retrieval.generation.browse import WorkflowNotFound
from retrieval.generation.feedback import (
    FeedbackBusy,
    FeedbackConflict,
    FeedbackInvalid,
    FeedbackRequest,
    RealFeedbackService,
)

REQUEST = {
    "mode": "real", "dataset_split": "dev",
    "workflow_id": "REAL_WF_0001", "base_revision": 1,
    "step_id": "REAL_WF_0001_ST_001", "target_field": "rationale",
    "question_id": "REAL_WF_0001_Q_001",
    "answer_text": "Main air is disconnected so the carousel cannot index.",
    "responder": {"actor_id": "dpv137", "label": "Pham Vu Dang", "role": "ky thuat vien bao tri"},
    "language": "en",
}


@pytest.fixture
def adapter():
    return RealFeedbackService()


def _request() -> FeedbackRequest:
    return FeedbackRequest.model_validate(REQUEST)


def test_payload_carries_every_field_d1b_needs(adapter, monkeypatch):
    """Khong duoc lam roi truong nao khi doi dang request."""
    captured = {}

    def fake_preview(payload):
        captured.update(payload)
        return {"ok": True}

    monkeypatch.setattr(d1b, "preview", fake_preview)
    adapter.preview(_request())

    assert captured["workflow_id"] == "REAL_WF_0001"
    assert captured["base_revision"] == 1
    assert captured["step_id"] == "REAL_WF_0001_ST_001"
    assert captured["target_field"] == "rationale"
    assert captured["question_id"] == "REAL_WF_0001_Q_001"
    assert captured["answer_text"] == REQUEST["answer_text"]
    assert captured["responder"] == REQUEST["responder"]
    assert captured["language"] == "en"


def test_submit_adds_confirm_base_revision(adapter, monkeypatch):
    """submit them confirm_base_revision = base_revision nguoi dung dang xem."""
    captured = {}

    def fake_submit(payload):
        captured.update(payload)
        return {"revision": 2}

    monkeypatch.setattr(d1b, "submit", fake_submit)
    adapter.submit(_request())

    assert captured["confirm_base_revision"] == captured["base_revision"] == 1


def test_not_found_becomes_workflow_not_found(adapter, monkeypatch):
    def boom(payload):
        raise d1b.FeedbackNotFound("Không có workflow 'X' trong kho chuẩn.")

    monkeypatch.setattr(d1b, "preview", boom)
    with pytest.raises(WorkflowNotFound):
        adapter.preview(_request())


def test_conflict_keeps_latest_revision_and_uses_our_base_revision(adapter, monkeypatch):
    """Doi 2 doc .latest_revision/.base_revision (feedback.js dong 104); phai co ca hai."""
    def boom(payload):
        raise d1b.FeedbackConflict(
            "da co r2", conflict={"latest_revision": 2, "changed_fields": ["claims"],
                                   "changed_at": "2026-09-22T00:00:00Z", "actor_id": "ai_do"})

    monkeypatch.setattr(d1b, "preview", boom)
    with pytest.raises(FeedbackConflict) as exc:
        adapter.preview(_request())

    assert exc.value.latest_revision == 2
    assert exc.value.base_revision == 1  # tu request, khong phai tu D1-B


def test_busy_becomes_our_feedback_busy(adapter, monkeypatch):
    def boom(payload):
        raise d1b.FeedbackBusy("dang co lan ghi khac chay")

    monkeypatch.setattr(d1b, "submit", boom)
    with pytest.raises(FeedbackBusy):
        adapter.submit(_request())


def test_rejected_becomes_feedback_invalid_and_keeps_v0x_codes(adapter, monkeypatch):
    def boom(payload):
        raise d1b.FeedbackRejected("khong qua validator", errors=["V07 claims[X]: loi gia lap"])

    monkeypatch.setattr(d1b, "submit", boom)
    with pytest.raises(FeedbackInvalid) as exc:
        adapter.submit(_request())

    assert exc.value.errors == ["V07 claims[X]: loi gia lap"]


def test_unmapped_error_still_propagates(adapter, monkeypatch):
    """Neu D1-B them mot loai FeedbackError moi, khong duoc nuot lang le."""
    class SurpriseError(d1b.FeedbackError):
        http_status = 418

    def boom(payload):
        raise SurpriseError("loai loi moi chua duoc doi 2 biet")

    monkeypatch.setattr(d1b, "preview", boom)
    with pytest.raises(SurpriseError):
        adapter.preview(_request())


def test_successful_preview_passes_through_unchanged(adapter, monkeypatch):
    """Adapter khong duoc sua bat ky gia tri nao D1-B tra ve khi khong co loi."""
    sentinel = {"next_revision": 2, "warnings": ["a"], "responder_authenticated": False}
    monkeypatch.setattr(d1b, "preview", lambda payload: sentinel)
    assert adapter.preview(_request()) is sentinel
