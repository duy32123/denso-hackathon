"""Chinh sach truy xuat (muc 7): claim nao duoc dung de KHANG DINH.

Ham nay thuoc lop hop dong chung: doi 1 dung de bao cao claim chua du dieu
kien, doi 2 dung ngay truoc khi dung evidence package. Hai ben khong duoc
cai dat hai ban rieng.

Tra ve danh sach ly do bi loai (rong = du dieu kien). Luon tra ly do de UI
noi duoc "vi sao khong tra loi", thay vi im lang bo claim.
"""

from __future__ import annotations

from .enums import (
    EvidenceKind,
    Lifecycle,
    QueryMode,
    SourceReview,
    SourceType,
    SupportStatus,
    TechnicalReview,
)
from .models import Claim, Workflow


def claim_blockers(
    claim: Claim,
    workflow: Workflow,
    *,
    mode: QueryMode,
    is_latest_indexed_revision: bool,
    evidence_openable: bool = True,
) -> list[str]:
    """Ly do khien claim khong duoc dung de khang dinh, theo `mode`."""
    reasons: list[str] = []

    if not is_latest_indexed_revision:
        reasons.append("khong phai latest revision da index hoan chinh")
    if Lifecycle(workflow.lifecycle) is not Lifecycle.ACTIVE:
        reasons.append("workflow lifecycle=withdrawn")
    if not evidence_openable:
        reasons.append("evidence khong mo duoc")
    if claim.conflicts_with:
        reasons.append("con conflict chua giai quyet")

    wf_source_type = SourceType(workflow.source_type)
    if mode is QueryMode.REAL:
        if wf_source_type is not SourceType.REAL:
            reasons.append("mode=real khong duoc doc corpus synthetic")
        if EvidenceKind(claim.evidence_type) is EvidenceKind.INFERRED:
            reasons.append("claim inferred chua duoc xac nhan")
        if SupportStatus(claim.support_status) is not SupportStatus.SUPPORTED:
            reasons.append(f"support_status={claim.support_status}")
        if SourceReview(claim.source_review) is not SourceReview.SOURCE_CHECKED:
            reasons.append(f"source_review={claim.source_review}")
        if TechnicalReview(claim.technical_review) is TechnicalReview.REJECTED:
            reasons.append("technical_review=rejected")
    else:
        # Namespace synthetic: chi de thu phan mem. source_review van pending.
        if wf_source_type is not SourceType.SYNTHETIC:
            reasons.append("mode=synthetic chi doc corpus synthetic")
        if EvidenceKind(claim.evidence_type) is EvidenceKind.INFERRED:
            reasons.append("claim inferred chua duoc xac nhan")
        if SupportStatus(claim.support_status) is not SupportStatus.SUPPORTED:
            reasons.append(f"support_status={claim.support_status}")

    return reasons


def is_assertable(claim: Claim, workflow: Workflow, **kwargs) -> bool:
    return not claim_blockers(claim, workflow, **kwargs)


def answer_qualifier(claim: Claim) -> str | None:
    """Cach dien dat bat buoc kem theo claim (muc 7).

    Claim moi chi source_checked phai duoc noi la "Theo nguon...", khong duoc
    trinh bay nhu ket luan ky thuat. expert_validated van bi gioi han boi scope.
    """
    if TechnicalReview(claim.technical_review) is TechnicalReview.EXPERT_VALIDATED:
        return f"Chuyen gia xac nhan trong pham vi: {claim.scope.description}"
    if SourceReview(claim.source_review) is SourceReview.SOURCE_CHECKED:
        return "Theo nguon (chua co xac nhan ky thuat)"
    return None
