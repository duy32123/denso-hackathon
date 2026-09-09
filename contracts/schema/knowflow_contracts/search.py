"""Search record: du lieu DAN XUAT do doi 2 sinh ra (D-03 + D-06).

Hai dieu phai giu bang ky luat, khong chi bang code:

1. Moi thu trong file nay la dan xuat tu snapshot. Khong bao gio ghi nguoc vao
   Canonical KB cua doi 1, va khong bao gio duoc trich dan nhu bang chung.
   `search_text_vi` la ban dich may - dung de TIM, khong dung de TRA LOI.
   Citation luon tro ve claim_id/evidence_id trong snapshot goc.
2. Index hai tang (D-06): WorkflowSearchRecord de chon dung quy trinh,
   StepSearchRecord de tim dung chi tiet. Khong ghep step cua nhieu workflow
   thanh mot quy trinh moi.

Tham so top-k KHONG nam o day: do la cau hinh retrieval, doi 2 chon bang
benchmark tren tap dev.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .enums import (
    DatasetSplit,
    EvidenceKind,
    Lifecycle,
    SourceReview,
    SourceType,
    SupportStatus,
    TaskType,
    TechnicalReview,
)
from .models import LanguageCode, NonEmptyStr, Strict


class SearchText(Strict):
    """Van ban dung de danh chi muc.

    `search_text_original` dung ngon ngu cua workflow (Workflow.language).
    `search_text_vi` chi co khi doi 2 dich sang tieng Viet de ho tro truy xuat
    cheo ngon ngu; da dich thi bat buoc ghi lai model va version da dich.
    """

    search_text_original: NonEmptyStr
    search_text_vi: str | None = None
    translation_model: str | None = None
    translation_version: str | None = None

    @model_validator(mode="after")
    def _translation_is_traceable(self) -> "SearchText":
        if self.search_text_vi is not None and not (self.translation_model and self.translation_version):
            raise ValueError(
                "search_text_vi bat buoc kem translation_model va translation_version "
                "(ban dich phai tai lap duoc; D-03)"
            )
        if self.search_text_vi is None and (self.translation_model or self.translation_version):
            raise ValueError("co translation_model/version nhung khong co search_text_vi")
        return self


class IndexBuild(Strict):
    """Dau vet de tai lap mot lan build index."""

    index_build_id: NonEmptyStr
    snapshot_hash: NonEmptyStr
    embedding_model: NonEmptyStr
    embedding_version: NonEmptyStr
    text_template_version: NonEmptyStr


class SearchMetadata(Strict):
    """Metadata dung de LOC truoc khi truy xuat (muc 7)."""

    manufacturer: str | None
    machine_family: str | None
    machine_model: str | None
    subsystem: str | None
    task_type: TaskType | None
    symptoms: list[str]
    alarm_codes: list[str]
    components: list[str]


class ClaimReviewFlag(Strict):
    """Trang thai cua mot claim, sao chep vao index de loc ma khong phai join."""

    claim_id: NonEmptyStr
    evidence_type: EvidenceKind
    support_status: SupportStatus
    source_review: SourceReview
    technical_review: TechnicalReview
    has_unresolved_conflict: bool


class _SearchRecordBase(Strict):
    workflow_id: NonEmptyStr
    revision: int
    source_type: SourceType
    dataset_split: DatasetSplit
    lifecycle: Lifecycle
    language: LanguageCode
    source_ids: list[str]
    metadata: SearchMetadata
    text: SearchText
    build: IndexBuild


class WorkflowSearchRecord(_SearchRecordBase):
    """Tang 1: chon dung quy trinh."""

    record_type: Literal["workflow"] = "workflow"
    title: NonEmptyStr
    step_count: int
    claim_review_flags: list[ClaimReviewFlag]


class StepSearchRecord(_SearchRecordBase):
    """Tang 2: tim dung chi tiet trong mot quy trinh."""

    record_type: Literal["step"] = "step"
    step_id: NonEmptyStr
    display_order: int
    title: NonEmptyStr
    claim_ids: list[str]
    claim_review_flags: list[ClaimReviewFlag]
