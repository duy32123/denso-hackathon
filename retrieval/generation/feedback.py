"""D2-B / WP4 + D2-A: hop dong goi service ghi phan hoi cua D1-B (WP6).

Doi 1 so huu kho tri thuc chuan va viec danh so revision. Tep nay dinh nghia cach
doi 2 goi sang: `FeedbackService` la protocol chung, `StubFeedbackService` la ban
gia lap khong bao gio ghi (dung khi chua cau hinh service that hoac khi dung tap
duot UI ma khong muon dung vao kho chuan), `RealFeedbackService` la adapter goi
thang sang `acquisition.extraction.feedback_service` -- ham Python chay chung
tien trinh, dung nhu contract da chot cho phep (khong can HTTP server rieng).

Contract day du va sau cau hoi da duoc doi 1 tra loi: docs/team2_feedback_contract.md.
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


class FeedbackInvalid(ValueError):
    """Yeu cau hop le ve cu phap nhung khong duoc phep ghi.

    Vi du: bundle sau khi ghi se khong qua validator chung (ma V0x nam trong
    `.errors`), corpus/split bi khoa (synthetic, holdout), hoac question khong
    con o trang thai open. Khac voi loi 422 chung cua FastAPI (schema request sai
    kieu): day la loi nghiep vu, va nguoi dung can doc duoc ly do that.
    """

    def __init__(self, message: str, *, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class FeedbackBusy(RuntimeError):
    """Mot lan ghi khac cua doi 1 dang chay. Thu lai sau, khong ghi de len no."""


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
                "Phan hoi duoc them vao ben canh, khong thay the (contract muc 5.6).")
        if request.language != workflow["language"]:
            warnings.append(
                f"Phan hoi tieng {request.language} tren workflow tieng {workflow['language']}: "
                "Claim.text giu nguyen van, khong dich; nguoi kiem nguon can xac nhan "
                "truoc khi promote (D-03, contract muc 5.3).")

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


class RealFeedbackService:
    """Adapter goi sang service ghi that cua doi 1 (`acquisition.extraction.feedback_service`).

    D1-B so huu kho chuan; adapter nay chi doi request/exception sang loai cua
    doi 2, de app.py va phan con lai cua retrieval/ khong bao gio phai biet ve
    module acquisition.*. Khong tu sua, khong suy dien lai bat ky gia tri nao
    D1-B tra ve -- xem docs/team2_feedback_contract.md.

    Import module cua doi 1 trong `__init__` chu khong o dau tep: acquisition/ va
    retrieval/ la hai package doc lap trong cung repo (chua tung import lan nhau
    truoc PR nay), nen chi lay phu thuoc luc thuc su can, khong phai lay theo
    thu tu nap module.
    """

    def __init__(self):
        from acquisition.extraction import feedback_service as _writer

        self._writer = _writer

    def _payload(self, request: FeedbackRequest) -> dict:
        return {
            "mode": request.mode,
            "dataset_split": request.dataset_split,
            "workflow_id": request.workflow_id,
            "base_revision": request.base_revision,
            "step_id": request.step_id,
            "target_field": request.target_field,
            "question_id": request.question_id,
            "answer_text": request.answer_text,
            "responder": {
                "actor_id": request.responder.actor_id,
                "label": request.responder.label,
                "role": request.responder.role,
            },
            "language": request.language,
        }

    def _reraise(self, exc: Exception, *, base_revision: int):
        """Dich loi typed cua D1-B sang loai cua doi 2. Loai khong nhan duoc thi giu nguyen."""
        w = self._writer
        if isinstance(exc, w.FeedbackNotFound):
            raise WorkflowNotFound(str(exc)) from exc
        if isinstance(exc, w.FeedbackConflict):
            # D1-B tra them changed_fields/changed_at/actor_id trong .conflict;
            # hop dong hien tai cua doi 2 (va feedback.js) chi doc hai truong nay.
            raise FeedbackConflict(
                str(exc),
                latest_revision=exc.conflict["latest_revision"],
                base_revision=base_revision,
            ) from exc
        if isinstance(exc, w.FeedbackBusy):
            raise FeedbackBusy(str(exc)) from exc
        if isinstance(exc, w.FeedbackRejected):
            raise FeedbackInvalid(str(exc), errors=exc.errors) from exc
        # D1-B them mot loai FeedbackError moi ma doi 2 chua biet: khong nuot lang le.
        raise exc

    def preview(self, request: FeedbackRequest) -> dict:
        """Khong ghi gi -- xem `acquisition.extraction.feedback_service.preview`."""
        try:
            return self._writer.preview(self._payload(request))
        except self._writer.FeedbackError as exc:
            self._reraise(exc, base_revision=request.base_revision)

    def submit(self, request: FeedbackRequest) -> dict:
        """Ghi that.

        `confirm_base_revision`: chu ky cua nguoi dung tren dung ban preview ho
        vua doc (contract muc 2). Man Bo sung luon goi preview roi moi bat nut
        Luu tren dung workflow/base_revision do, nen `request.base_revision` tai
        thoi diem submit CHINH LA gia tri da duoc xac nhan qua thao tac do -- gan
        no vao day khong bo qua buoc xac nhan, no ghi lai dung buoc UI da lam.
        """
        payload = {**self._payload(request), "confirm_base_revision": request.base_revision}
        try:
            return self._writer.submit(payload)
        except self._writer.FeedbackError as exc:
            self._reraise(exc, base_revision=request.base_revision)
