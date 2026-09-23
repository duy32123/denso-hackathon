"""D1-B / WP6: loi goi `preview` cua service ghi phan hoi.

Chay tren kho chuan that (`data/workflows/dev`) chu khong tren fixture, vi thu
dang duoc kiem chinh la: bam Luu tren man Bo sung cua doi 2 co ra mot bundle hop
le hay khong.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from acquisition.extraction.feedback_service import (
    FeedbackConflict,
    FeedbackNotFound,
    FeedbackRejected,
    FeedbackRequest,
    plan_feedback,
    preview,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DIRS = (
    REPO_ROOT / "data" / "workflows",
    REPO_ROOT / "data" / "sources",
    REPO_ROOT / "acquisition" / "export" / "haas_pilot_dev_bundle",
    REPO_ROOT / "acquisition" / "feedback",
)

# REAL_WF_0001_Q_001 dang mo: rationale cua ST_001 khong duoc nguon noi ra.
ASKED = {
    "mode": "real",
    "dataset_split": "dev",
    "workflow_id": "REAL_WF_0001",
    "base_revision": 1,
    "step_id": "REAL_WF_0001_ST_001",
    "target_field": "rationale",
    "question_id": "REAL_WF_0001_Q_001",
    "answer_text": "Main air is disconnected so the carousel cannot index while hands are inside.",
    "responder": {"actor_id": "dpv137", "label": "Pham Vu Dang", "role": "ky thuat vien bao tri"},
    "language": "en",
}


def _fingerprint() -> dict[str, str]:
    """Hash moi tep trong kho chuan, de phat hien bat ky lan ghi nao."""
    prints = {}
    for root in CANONICAL_DIRS:
        if not root.exists():
            prints[str(root)] = "<absent>"
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                prints[str(path.relative_to(REPO_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return prints


def _request(**overrides) -> FeedbackRequest:
    payload = {**ASKED, **overrides}
    return FeedbackRequest.model_validate(payload)


# --- dieu kien quan trong nhat -------------------------------------------------


def test_preview_does_not_touch_the_canonical_store():
    """`preview` khong ghi gi: khong snapshot, khong source, khong bundle."""
    before = _fingerprint()
    preview(_request())
    assert _fingerprint() == before


def test_preview_is_repeatable():
    """Goi hai lan cho cung ket qua: khong co bo dem ID hay trang thai an.

    Bo `change_log.changed_at` khoi phep so sanh: no la dong ho treo tuong, chinh
    xac toi giay. Hai lan goi vat qua ranh gioi giay thi khac nhau ma khong noi len
    dieu gi ve tinh lap lai -- ban dau test nay so sanh ca no nen thinh thoang do.
    """
    def stable(result: dict) -> dict:
        trimmed = {**result, "change_log": {**result["change_log"]}}
        trimmed["change_log"].pop("changed_at")
        return trimmed

    first, second = preview(_request()), preview(_request())

    assert stable(first) == stable(second)
    # ID phai on dinh: day moi la thu test nay giu.
    assert first["new_claims"][0]["claim_id"] == second["new_claims"][0]["claim_id"]
    assert first["new_evidence"][0]["evidence_id"] == second["new_evidence"][0]["evidence_id"]
    assert first["source"]["source_id"] == second["source"]["source_id"]


# --- noi dung ban xem truoc ----------------------------------------------------


def test_preview_shows_the_revision_that_would_be_written():
    result = preview(_request())

    assert result["workflow_id"] == "REAL_WF_0001"
    assert result["base_revision"] == 1
    assert result["next_revision"] == 2
    assert result["conflict"] is None
    assert result["validation"]["ok"], result["validation"]["errors"]


def test_preview_claim_is_not_reviewed():
    """Bat bien so 3: co phan hoi khong phai la da kiem nguon."""
    result = preview(_request())

    assert len(result["new_claims"]) == 1
    claim = result["new_claims"][0]
    assert claim["source_review"] == "pending"
    assert claim["technical_review"] == "not_requested"
    assert claim["text"] == ASKED["answer_text"]
    # Danh tinh tu khai: UI phai noi ro.
    assert result["responder_authenticated"] is False


def test_preview_source_has_an_openable_path():
    """V02: nguon real thieu url/asset_uri thi ca bundle bi tu choi."""
    source = preview(_request())["source"]

    assert source["source_kind"] == "expert_answer"
    assert source["raw_text"] == ASKED["answer_text"]
    assert source["asset_uri"] == f"acquisition/feedback/{source['source_id']}.json"


def test_preview_field_change_shows_before_and_after():
    change = preview(_request())["field_changes"][0]

    assert change["step_id"] == "REAL_WF_0001_ST_001"
    assert change["field"] == "rationale"
    assert change["before"]["state"] == "missing"
    assert change["before"]["claim_ids"] == []
    assert change["after"]["state"] == "present"
    assert len(change["after"]["claim_ids"]) == 1


def test_preview_question_moves_from_open_to_answered():
    transition = preview(_request())["question_transition"]

    assert transition["question_id"] == "REAL_WF_0001_Q_001"
    assert transition["from"] == "open"
    assert transition["to"] == "answered"
    assert transition["created_by_this_change"] is False


def test_preview_matches_what_plan_would_write(monkeypatch):
    """Ban xem truoc va ban that di qua cung mot ham, khong the lech nhau.

    plan_feedback(request) va preview(request) la hai lan goi rieng, moi lan
    tu doc dong ho that qua _utc_now(); tung flake khi hai lan goi bac qua
    ranh gioi giay (vd '...T11:43:02Z' != '...T11:43:01Z'). Khoa dong ho ve
    mot moc co dinh de phep so sanh khong con phu thuoc thoi diem chay that."""
    frozen = datetime(2026, 9, 23, 0, 0, 0, tzinfo=timezone.utc)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr("acquisition.extraction.feedback_loop.datetime", FrozenDatetime)
    request = _request()
    plan = plan_feedback(request)
    result = preview(request)

    assert result["next_revision"] == plan.new_snapshot["revision"]
    assert result["new_claims"][0]["claim_id"] == plan.new_snapshot["claims"][-1]["claim_id"]
    assert result["new_evidence"][0]["evidence_id"] == plan.new_snapshot["evidence"][-1]["evidence_id"]
    assert result["change_log"] == plan.new_snapshot["change_log"][-1]


def test_new_ids_do_not_collide_with_the_unpromoted_draft():
    """draft REAL_WF_0001.r2 da cap EV_036; preview khong duoc cap lai (D-02)."""
    result = preview(_request())

    draft = json.loads(
        (REPO_ROOT / "data/workflows/drafts/REAL_WF_0001.r2.json").read_text(encoding="utf-8")
    )
    taken = {e["evidence_id"] for e in draft["evidence"]}
    assert result["new_evidence"][0]["evidence_id"] not in taken


# --- ca loi (hop dong muc 4) ---------------------------------------------------


def test_stale_base_revision_is_a_conflict():
    """409 kem du lieu de UI dung diff, khong ghi de im lang."""
    # REAL_WF_0002 co r1 va r2; nguoi dung con dang xem r1.
    with pytest.raises(FeedbackConflict) as exc:
        plan_feedback(
            _request(
                workflow_id="REAL_WF_0002",
                base_revision=1,
                step_id="REAL_WF_0002_ST_001",
                question_id=None,
            )
        )

    assert exc.value.http_status == 409
    assert exc.value.conflict["latest_revision"] == 2
    assert exc.value.conflict["changed_fields"]


def test_unknown_workflow_is_not_found():
    with pytest.raises(FeedbackNotFound) as exc:
        plan_feedback(_request(workflow_id="REAL_WF_9999", question_id=None))
    assert exc.value.http_status == 404


def test_unknown_step_is_not_found():
    with pytest.raises(FeedbackNotFound) as exc:
        plan_feedback(_request(step_id="REAL_WF_0001_ST_999", question_id=None))
    assert exc.value.http_status == 404


def test_unknown_question_is_not_found():
    with pytest.raises(FeedbackNotFound) as exc:
        plan_feedback(_request(question_id="REAL_WF_0001_Q_999"))
    assert exc.value.http_status == 404


def test_question_pointing_at_another_field_is_rejected():
    """Khong cho dinh cau tra loi vao mot truong khac voi cau hoi."""
    with pytest.raises(FeedbackRejected) as exc:
        plan_feedback(_request(target_field="outcome"))
    assert exc.value.http_status == 422


def test_base_revision_ahead_of_the_store_is_rejected():
    with pytest.raises(FeedbackRejected):
        plan_feedback(_request(base_revision=99))


def test_synthetic_corpus_cannot_be_written():
    """KB synthetic la du lieu dan xuat cua doi 2, khong phai kho chuan."""
    with pytest.raises(FeedbackRejected):
        plan_feedback(_request(mode="synthetic"))


def test_holdout_is_locked():
    with pytest.raises(FeedbackRejected):
        plan_feedback(_request(dataset_split="holdout"))


def test_missing_responder_role_is_rejected_by_the_model():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FeedbackRequest.model_validate(
            {**ASKED, "responder": {"actor_id": "x", "label": "y", "role": "  "}}
        )


# --- canh bao ------------------------------------------------------------------


def test_warns_when_the_field_already_has_claims():
    """Bo sung ben canh claim cu, khong thay the -- nguoi dung phai thay dieu do."""
    result = preview(
        _request(
            step_id="REAL_WF_0001_ST_001",
            target_field="action",
            question_id=None,
        )
    )
    assert any("đã có" in w for w in result["warnings"])


def test_warns_on_a_language_mismatch():
    """D-03: Claim.text giu nguyen van, khong dich; nguoi kiem phai biet."""
    result = preview(_request(language="vi", answer_text="Ngắt khí nén để mâm dao không quay."))
    assert any("D-03" in w for w in result["warnings"])


def test_source_language_is_the_response_language_not_the_workflow_language():
    """D-03: `Source.language` la ngon ngu THUC TE cua nguon.

    REAL_WF_0001 la workflow tieng Anh. Mot cau tra loi tieng Viet van la mot
    nguon tieng Viet; ghi 'en' cho no la khai sai ngon ngu nguon.
    """
    result = preview(_request(language="vi", answer_text="Ngắt khí nén để mâm dao không quay."))
    assert result["source"]["language"] == "vi"

    english = preview(_request(language="en"))
    assert english["source"]["language"] == "en"
    # Workflow van la 'en' va van hop le: V02 chi doi wf.language nam trong tap
    # ngon ngu cua cac nguon, ma cac nguon Haas tieng Anh van con do.
    assert english["validation"]["ok"]


def test_supplementing_a_field_without_a_question_creates_one():
    """Bo sung truong con thieu van phai truy duoc nguon goc."""
    result = preview(
        _request(
            step_id="REAL_WF_0001_ST_002",
            target_field="rationale",
            question_id=None,
        )
    )
    transition = result["question_transition"]
    assert transition["created_by_this_change"] is True
    assert transition["to"] == "answered"
    assert any("không gắn với question" in w.lower() for w in result["warnings"])
