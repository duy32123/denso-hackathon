"""D2-B / WP4: hop dong goi service ghi phan hoi cua D1-B (WP6).

Doi 1 so huu kho tri thuc chuan va viec danh so revision. Tep nay CHI dinh nghia
cach doi 2 goi sang, cong voi mot ban gia lap de dung giao dien va test truoc khi
service that co. Khong co duong nao trong tep nay ghi vao kho chuan.

De xuat contract day du: docs/team2_feedback_contract.md (chua duoc doi 1 chot).
"""

from __future__ import annotations

from typing import Literal, Protocol

from knowflow_contracts.enums import FieldRole  # Strict.use_enum_values => nhan ve str
from knowflow_contracts.models import NonEmptyStr, Strict

from .browse import WorkflowBrowser, WorkflowNotFound


class FeedbackUnavailable(RuntimeError):
    """Chua co service ghi. KHONG duoc bat thanh mot lan luu gia."""


class FeedbackConflict(ValueError):
    """base_revision nguoi dung dang xem khong con la ban moi nhat."""

    def __init__(self, message: str, *, latest_revision: int, base_revision: int):
        super().__init__(message)
        self.latest_revision = latest_revision
        self.base_revision = base_revision


class Responder(Strict):
    """Nguoi tra loi tu khai. CHUA xac thuc: he thong khong co dang nhap."""

    actor_id: NonEmptyStr
    label: NonEmptyStr
    role: NonEmptyStr


class FeedbackRequest(Strict):
    mode: Literal["real", "synthetic"]
    dataset_split: Literal["dev"]
    workflow_id: NonEmptyStr
    base_revision: int
    step_id: NonEmptyStr
    target_field: FieldRole
    question_id: str | None = None
    answer_text: NonEmptyStr
    responder: Responder
    language: Literal["vi", "en"] = "vi"


class FeedbackService(Protocol):
    """Hai loi goi; `preview` khong duoc ghi gi."""

    def preview(self, request: FeedbackRequest) -> dict: ...

    def submit(self, request: FeedbackRequest) -> dict: ...


class StubFeedbackService:
    """Ban gia lap doc snapshot that nhung KHONG BAO GIO ghi.

    Dung de dung man Bo sung va kiem duong 409 truoc khi D1-B co service. `submit`
    mac dinh bao FeedbackUnavailable: mot lan luu gia con te hon khong co nut luu.
    `allow_submit` chi dung trong test, khong doc tu bien moi truong.
    """

    simulated = True

    def __init__(self, browser: WorkflowBrowser, *, allow_submit: bool = False):
        self.browser = browser
        self.allow_submit = allow_submit
        self.submitted: list[FeedbackRequest] = []

    # -- doc snapshot ---------------------------------------------------------

    def _latest(self, request: FeedbackRequest) -> tuple[dict, int]:
        """Doc dung ban snapshot ma UI dang xem.

        Giu nguyen dang dict cua WorkflowBrowser: payload do da luoc `asset_uri`
        de khong lo duong dan cuc bo, nen khong dung lai thanh `Workflow` duoc
        (V01 doi optional phai co mat va null). Stub chi can revision, step va
        question, khong can toan bo model.
        """
        catalog = self.browser.catalog(request.mode, request.dataset_split)
        revisions = [w["revision"] for w in catalog["workflows"]
                     if w["workflow_id"] == request.workflow_id]
        if not revisions:
            raise WorkflowNotFound("Workflow not in the active index")
        latest = max(revisions)
        data = self.browser.workflow(request.workflow_id, latest, request.mode,
                                     request.dataset_split, catalog["index_build_id"])
        return data["workflow"], latest

    def _checked(self, request: FeedbackRequest) -> dict:
        workflow, latest = self._latest(request)
        if request.base_revision != latest:
            raise FeedbackConflict(
                "Workflow da co revision moi hon ban dang xem",
                latest_revision=latest, base_revision=request.base_revision,
            )
        if not any(s["step_id"] == request.step_id for s in workflow["steps"]):
            raise WorkflowNotFound("Step not in this revision")
        if request.question_id and not any(q["question_id"] == request.question_id
                                           for q in workflow["questions"]):
            raise WorkflowNotFound("Question not in this revision")
        return workflow

    # -- hop dong -------------------------------------------------------------

    def preview(self, request: FeedbackRequest) -> dict:
        """Tra ve dung nhung gi SE duoc ghi. Khong ghi, khong doi active pointer."""
        workflow = self._checked(request)
        step = next(s for s in workflow["steps"] if s["step_id"] == request.step_id)
        before = step["fields"][request.target_field]
        source_id = f"SRC_EXPERT_{request.workflow_id}_{request.base_revision + 1:03d}"
        evidence_id = f"{request.workflow_id}_EV_NEW"
        claim_id = f"{request.workflow_id}_CL_NEW"

        warnings: list[str] = []
        if before["state"] == "present":
            warnings.append(
                f"Truong {request.target_field} da co {len(before['claim_ids'])} claim. "
                "D1-B chua chot day la bo sung hay xung dot (contract muc 4).")
        if request.language != workflow["language"]:
            warnings.append(
                f"Phan hoi tieng {request.language} tren workflow tieng {workflow['language']}: "
                "D-03 chua chot Claim.text moi viet bang tieng gi (contract muc 5.3).")

        return {
            "simulated": True,
            "mode": request.mode, "dataset_split": request.dataset_split,
            "workflow_id": workflow["workflow_id"],
            "base_revision": workflow["revision"], "next_revision": workflow["revision"] + 1,
            "conflict": None,
            "source": {
                "source_id": source_id, "source_kind": "expert_answer",
                "raw_text": request.answer_text,
                # V02: nguon real bat buoc co url hoac asset_uri, khong chi raw_text.
                "asset_uri": f"acquisition/feedback/{source_id}.json" if request.mode == "real" else None,
                "language": request.language,
            },
            "new_evidence": [{"evidence_id": evidence_id, "source_id": source_id, "modality": "text",
                              "locator": {"text_span": request.answer_text},
                              "quote": request.answer_text}],
            "new_claims": [{"claim_id": claim_id, "role": request.target_field,
                            "text": request.answer_text, "evidence_type": "stated",
                            "support_status": "supported",
                            # Co phan hoi KHONG phai la da kiem nguon (V07).
                            "source_review": "pending", "technical_review": "not_requested"}],
            "field_changes": [{"step_id": step["step_id"], "field": request.target_field,
                               "before": before,
                               "after": {"state": "present", "claim_ids": [claim_id]}}],
            "question_transition": ({"question_id": request.question_id, "from": "open",
                                     "to": "answered"} if request.question_id else None),
            "change_log": {"actor_id": request.responder.actor_id,
                           "reason": f"Bo sung {request.target_field} tu phan hoi.",
                           "previous_revision": workflow["revision"], "id_mapping": []},
            "responder_authenticated": False,
            "warnings": warnings,
        }

    def submit(self, request: FeedbackRequest) -> dict:
        self._checked(request)
        if not self.allow_submit:
            raise FeedbackUnavailable(
                "Service ghi cua doi 1 (D1-B / WP6) chua co. Doi 2 khong ghi thang vao "
                "kho chuan; xem docs/team2_feedback_contract.md.")
        self.submitted.append(request)
        return {"simulated": True, "workflow_id": request.workflow_id,
                "revision": request.base_revision + 1,
                "note": "Ban gia lap: khong co revision nao duoc ghi vao kho chuan."}
