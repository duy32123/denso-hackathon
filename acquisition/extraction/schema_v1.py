"""Schema 1.0.0 Pydantic models for KnowFlow AI.

Provides standard validation contracts for LLM extraction and workflow compilation:
- FieldRef: Reference linking Step to Claims with FieldState across 7 mandatory roles.
- StepRecord: Represents a step with an ordered list of FieldRefs and associated metadata.
- WorkflowBundle: Full Schema 1.0.0 workflow bundle container for LLM output validation.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"

# --- Enums (Schema 1.0.0 Single Source of Truth) -----------------------------

class StrEnum(str, Enum):
    """String enum for direct serialization to JSON."""
    def __str__(self) -> str:
        return self.value


class SourceType(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class DatasetSplit(StrEnum):
    DEV = "dev"
    HOLDOUT = "holdout"


class FieldRole(StrEnum):
    """7 core roles of Step.fields in Schema 1.0.0."""
    CONTEXT = "context"
    OBSERVATION = "observation"
    ACTION = "action"
    RATIONALE = "rationale"
    CONDITION = "condition"
    OUTCOME = "outcome"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"


MANDATORY_FIELD_ROLES: tuple[str, ...] = tuple(r.value for r in FieldRole)


class FieldState(StrEnum):
    """State of a step field in Schema 1.0.0."""
    PRESENT = "present"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"


class ClaimRole(StrEnum):
    """Claim role: 7 step roles + relation."""
    CONTEXT = "context"
    OBSERVATION = "observation"
    ACTION = "action"
    RATIONALE = "rationale"
    CONDITION = "condition"
    OUTCOME = "outcome"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    RELATION = "relation"


class EvidenceKind(StrEnum):
    OBSERVED = "observed"
    STATED = "stated"
    INFERRED = "inferred"


class AttributionKind(StrEnum):
    SPEAKER = "speaker"
    OBSERVER = "observer"
    DOCUMENT = "document"
    MODEL = "model"


class ScopeLevel(StrEnum):
    CASE = "case"
    SOURCE_GENERAL = "source_general"
    EXPERT_DEFINED = "expert_defined"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"
    AMBIGUOUS = "ambiguous"


class TaskType(StrEnum):
    TROUBLESHOOTING = "troubleshooting"
    RECOVERY = "recovery"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    OTHER = "other"


# --- Common Primitives -------------------------------------------------------

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class StrictModel(BaseModel):
    """Base model: forbids extra fields, serializes enums as strings."""
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        populate_by_name=True,
    )


class FlexibleModel(BaseModel):
    """Tolerant model for LLM outputs: allows extra metadata during raw ingestion."""
    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
        populate_by_name=True,
    )


# --- Attribution & Scope -----------------------------------------------------

class AttributionRecord(FlexibleModel):
    actor_id: str | None = None
    label: str | None = "Orville"
    kind: AttributionKind = AttributionKind.SPEAKER


class ScopeRecord(FlexibleModel):
    level: ScopeLevel = ScopeLevel.CASE
    description: str = Field(default="", description="Mô tả phạm vi áp dụng")

    @model_validator(mode="before")
    @classmethod
    def _coerce_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"level": ScopeLevel.CASE, "description": data}
        return data


# --- Claim & Evidence Reference ---------------------------------------------

class EvidenceReference(FlexibleModel):
    """Represents evidence candidates from transcript pool or keyframes."""
    pool_ids: list[str] = Field(
        default_factory=list,
        description="Candidate IDs from evidence pool, e.g. ['SRC_HAAS_0005:U0001']"
    )
    explanation: str | None = Field(
        default=None,
        description="Giải thích ngắn gọn lý do bằng chứng hỗ trợ claim"
    )


class ClaimRecord(FlexibleModel):
    """Claim representation in draft or snapshot."""
    claim_id: str | None = Field(default=None, description="Mã claim, vd: REAL_WF_0001_CL_001")
    text: NonEmptyStr = Field(..., description="Phát biểu nguyên tử, giữ nguyên ý nghĩa kỹ thuật")
    role: ClaimRole = Field(default=ClaimRole.ACTION, description="Role tương ứng của claim")
    evidence_type: EvidenceKind = Field(default=EvidenceKind.STATED)
    attribution: AttributionRecord | None = None
    scope: ScopeRecord | None = None
    evidence: list[str | list[str] | dict[str, Any]] = Field(
        default_factory=list,
        description="Candidate pool IDs, ví dụ: [['SRC_HAAS_0005:U0001']]"
    )
    explanation: str | None = None
    support_status: SupportStatus | None = None

    @field_validator("support_status", mode="before")
    @classmethod
    def _validate_support_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("ungrounded", "unsupported"):
                return SupportStatus.INSUFFICIENT
            if v_lower in ("supported", "insufficient", "contradicted", "ambiguous"):
                return SupportStatus(v_lower)
        return v

    @model_validator(mode="after")
    def _enforce_evidence_guardrails(self) -> ClaimRecord:
        # If no evidence and not inferred, support_status must be INSUFFICIENT
        has_ev = bool(self.evidence and any(bool(e) for e in self.evidence))
        if not has_ev and self.evidence_type != EvidenceKind.INFERRED:
            self.support_status = SupportStatus.INSUFFICIENT
        return self


# --- FieldRef & StepRecord ---------------------------------------------------

class FieldRef(FlexibleModel):
    """Hợp đồng liên kết giữa Step và Claim theo Schema 1.0.0.

    Mỗi FieldRef đại diện cho 1 trong 7 vai trò kỹ thuật của Step:
    context, observation, action, rationale, condition, outcome, acceptance_criteria.
    """
    role: FieldRole = Field(
        ...,
        description="1 trong 7 vai trò chuẩn của Schema 1.0.0"
    )
    state: FieldState = Field(
        default=FieldState.PRESENT,
        description="Trạng thái của trường: present, missing, ambiguous, not_applicable"
    )
    claim_ids: list[str] = Field(
        default_factory=list,
        description="Danh sách ID của các claim thuộc trường này"
    )
    claims: list[ClaimRecord] = Field(
        default_factory=list,
        description="Danh sách claim chi tiết do LLM sinh ra trong giai đoạn trích xuất"
    )
    description: str | None = Field(
        default=None,
        description="Ghi chú hoặc tóm tắt nhanh nội dung của trường"
    )

    @field_validator("state", mode="before")
    @classmethod
    def _validate_state(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("present", "missing", "ambiguous", "not_applicable"):
                return v_lower
        return v


class QuestionRecord(FlexibleModel):
    """Câu hỏi bổ sung khi phát hiện thiếu hụt dữ liệu (missing/ambiguous)."""
    question_id: str | None = None
    step_id: str | None = None
    target_field: FieldRole = Field(default=FieldRole.RATIONALE)
    reason: Literal["missing", "ambiguous", "conflict", "identity", "unaligned", "other"] = "missing"
    question: NonEmptyStr = Field(..., description="Nội dung câu hỏi kỹ thuật cần giải đáp")
    status: Literal["open", "answered", "resolved", "dismissed", "waived"] = "open"
    answer_source_ids: list[str] = Field(default_factory=list)
    resolution_note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {
                "question": data,
                "target_field": FieldRole.RATIONALE,
                "reason": "missing",
            }
        if isinstance(data, dict):
            if "question" not in data or not data["question"]:
                for alt_key in ("text", "question_text", "content", "prompt"):
                    if data.get(alt_key):
                        data["question"] = data.pop(alt_key)
                        break
        return data


class StepRecord(FlexibleModel):
    """Biểu diễn một bước thực hiện trong quy trình bảo trì/vận hành (Schema 1.0.0).

    Đảm bảo mỗi Step có danh sách FieldRef và các trường dữ liệu bắt buộc.
    """
    step_id: NonEmptyStr = Field(
        ...,
        description="Mã định danh duy nhất của bước (vd: REAL_WF_0001_ST_001 hoặc ST_001)"
    )
    display_order: int = Field(
        ...,
        ge=1,
        description="Thứ tự hiển thị của bước (bắt đầu từ 1)"
    )
    title: NonEmptyStr = Field(
        ...,
        description="Tiêu đề ngắn gọn mô tả hành động chính của bước"
    )
    fields: list[FieldRef] = Field(
        default_factory=list,
        description="Danh sách các FieldRef chuẩn tương ứng với 7 roles kỹ thuật của Schema 1.0.0"
    )
    questions: list[QuestionRecord] = Field(
        default_factory=list,
        description="Các câu hỏi làm rõ cho các trường missing hoặc ambiguous"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        """Tự động chuyển đổi nếu LLM trả về `fields` dạng Dict thay vì List."""
        if not isinstance(data, dict):
            return data

        fields_raw = data.get("fields")
        if isinstance(fields_raw, dict):
            normalized_list: list[dict[str, Any]] = []
            for role_name in MANDATORY_FIELD_ROLES:
                field_val = fields_raw.get(role_name)
                if field_val is None:
                    normalized_list.append({
                        "role": role_name,
                        "state": FieldState.MISSING,
                        "claim_ids": [],
                        "claims": []
                    })
                elif isinstance(field_val, dict):
                    item = dict(field_val)
                    item.setdefault("role", role_name)
                    normalized_list.append(item)
                elif isinstance(field_val, list):
                    normalized_list.append({
                        "role": role_name,
                        "state": FieldState.PRESENT if field_val else FieldState.MISSING,
                        "claims": field_val,
                        "claim_ids": []
                    })
            data["fields"] = normalized_list
        return data

    @model_validator(mode="after")
    def _auto_generate_questions_for_missing_fields(self) -> StepRecord:
        """Tự động sinh QuestionRecord cho các trường missing hoặc ambiguous nếu chưa có câu hỏi."""
        self.ensure_mandatory_roles()
        existing_targets = {
            q.target_field.value if hasattr(q.target_field, "value") else str(q.target_field)
            for q in self.questions
        }
        for f in self.fields:
            role_str = f.role.value if hasattr(f.role, "value") else str(f.role)
            is_missing_or_ambig = f.state in (FieldState.MISSING, "missing", FieldState.AMBIGUOUS, "ambiguous")
            if is_missing_or_ambig and role_str not in existing_targets:
                reason_str: Literal["missing", "ambiguous"] = (
                    "missing" if f.state in (FieldState.MISSING, "missing") else "ambiguous"
                )
                self.questions.append(
                    QuestionRecord(
                        question_id=f"Q_{self.step_id}_{role_str}",
                        step_id=self.step_id,
                        target_field=FieldRole(role_str),
                        reason=reason_str,
                        question=f"What is the {role_str} for step '{self.title}'? The source does not provide explicit detail.",
                        status="open",
                    )
                )
        return self

    def get_field(self, role: FieldRole | str) -> FieldRef | None:
        """Lấy nhanh FieldRef theo role."""
        target_role = role.value if isinstance(role, FieldRole) else str(role)
        for f in self.fields:
            if f.role == target_role:
                return f
        return None

    def ensure_mandatory_roles(self) -> None:
        """Đảm bảo danh sách fields có đủ 7 roles chuẩn của Schema 1.0.0."""
        existing_roles = {f.role for f in self.fields}
        for role_name in MANDATORY_FIELD_ROLES:
            if role_name not in existing_roles:
                self.fields.append(
                    FieldRef(
                        role=FieldRole(role_name),
                        state=FieldState.MISSING,
                        claim_ids=[],
                        claims=[]
                    )
                )


# --- Context & Relation ------------------------------------------------------

class ContextRecord(FlexibleModel):
    """Thông tin ngữ cảnh thiết bị và tác vụ."""
    manufacturer: str | None = "Haas"
    machine_family: str | None = None
    machine_model: str | None = None
    subsystem: str | None = "Side Mount Tool Changer (SMTC)"
    task_type: TaskType | None = TaskType.MAINTENANCE
    symptoms: list[str] = Field(default_factory=list)
    alarm_codes: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] | None = Field(
        default=None,
        description="Thông tin căn cứ (provenance) cho metadata máy móc"
    )


class RelationRecord(FlexibleModel):
    """Quan hệ phụ thuộc giữa các bước."""
    relation_id: str | None = None
    from_step: int | str = Field(..., description="Step bắt đầu hoặc display_order")
    to_step: int | str = Field(..., description="Step đích hoặc display_order")
    type: Literal["requires", "alternative", "recovers_from", "precedes"] = "requires"
    claim: ClaimRecord | None = None
    claim_ids: list[str] = Field(default_factory=list)


# --- WorkflowBundle (Hợp đồng xác thực toàn diện) ---------------------------

class WorkflowBundle(FlexibleModel):
    """Hợp đồng dữ liệu hoàn chỉnh cho Quy trình trích xuất KnowFlow AI (Schema 1.0.0).

    Sử dụng làm bộ lọc và kiểm tra tính hợp lệ (validation contract) cho đầu ra của LLM.
    """
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    workflow_id: NonEmptyStr = Field(..., description="Mã định danh quy trình (vd: REAL_WF_0001)")
    revision: int = Field(default=1, ge=1)
    source_type: SourceType = Field(default=SourceType.REAL)
    dataset_split: DatasetSplit = Field(default=DatasetSplit.DEV)
    title: NonEmptyStr = Field(..., description="Tiêu đề quy trình")
    language: str = Field(default="en", description="Mã ngôn ngữ ISO / BCP-47")
    created_at: str | None = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="Thời gian tạo chuẩn RFC3339 UTC"
    )
    source_ids: list[str] = Field(
        default_factory=list,
        description="Danh sách nguồn dữ liệu tham chiếu (vd: ['SRC_HAAS_0005'])"
    )
    context: ContextRecord = Field(
        default_factory=ContextRecord,
        description="Thông tin máy móc, lỗi, hệ thống"
    )
    steps: list[StepRecord] = Field(
        ...,
        min_length=1,
        description="Danh sách các bước thực hiện tuần tự, mỗi bước chứa danh sách FieldRef"
    )
    claims: list[ClaimRecord] = Field(
        default_factory=list,
        description="Danh sách các claim ở cấp workflow"
    )
    relations: list[RelationRecord] = Field(
        default_factory=list,
        description="Các mối quan hệ phụ thuộc giữa các bước"
    )
    questions: list[QuestionRecord] = Field(
        default_factory=list,
        description="Tổng hợp câu hỏi kỹ thuật còn mở trong quy trình"
    )

    @field_validator("steps")
    @classmethod
    def _validate_display_orders(cls, steps: list[StepRecord]) -> list[StepRecord]:
        """Xác nhận thứ tự các bước hợp lệ."""
        if not steps:
            raise ValueError("Quy trình phải có ít nhất một StepRecord.")
        for s in steps:
            s.ensure_mandatory_roles()
        return steps

    @classmethod
    def from_llm_json(cls, json_text: str) -> WorkflowBundle:
        """Parse và validate trực tiếp chuỗi JSON trả về từ LLM."""
        clean_text = json_text.strip()
        if "```" in clean_text:
            m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", clean_text)
            if m:
                clean_text = m.group(1).strip()
            else:
                lines = clean_text.splitlines()
                if lines and lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                clean_text = "\n".join(lines).strip()

        data = json.loads(clean_text)
        return cls.model_validate(data)

    def to_draft_dict(self) -> dict[str, Any]:
        """Xuất ra dict tương thích trực tiếp với trình biên dịch compile_workflow."""
        data = self.model_dump(mode="json", exclude_none=True)
        # 1. Format root attribution & scope if missing
        if "attribution" not in data:
            data["attribution"] = {"label": "Orville", "kind": "speaker"}
        if "scope" not in data:
            data["scope"] = f"Procedure described in {self.workflow_id}"
        elif isinstance(data["scope"], dict):
            data["scope"] = data["scope"].get("description", "")

        # 2. Format step fields to role dict and format nested claim evidence
        for step in data.get("steps", []):
            raw_fields = step.get("fields")
            if isinstance(raw_fields, list):
                fields_dict = {}
                for f in raw_fields:
                    role = f.get("role")
                    if not role:
                        continue
                    f_clean = {k: v for k, v in f.items() if k != "role"}
                    # Clean and wrap claim evidence into nested arrays if needed
                    for claim in f_clean.get("claims", []):
                        if isinstance(claim.get("scope"), dict):
                            claim["scope"] = claim["scope"].get("description", "")
                        ev = claim.get("evidence")
                        if isinstance(ev, list) and ev and isinstance(ev[0], str):
                            claim["evidence"] = [ev]
                    fields_dict[role] = f_clean
                step["fields"] = fields_dict
            elif isinstance(raw_fields, dict):
                for f_val in raw_fields.values():
                    if isinstance(f_val, dict):
                        for claim in f_val.get("claims", []):
                            if isinstance(claim.get("scope"), dict):
                                claim["scope"] = claim["scope"].get("description", "")
                            ev = claim.get("evidence")
                            if isinstance(ev, list) and ev and isinstance(ev[0], str):
                                claim["evidence"] = [ev]
        return data


# --- Factory helpers ---------------------------------------------------------

def create_empty_step(step_id: str, display_order: int, title: str) -> StepRecord:
    """Khởi tạo một StepRecord mới với đủ 7 FieldRef mặc định có trạng thái MISSING."""
    step = StepRecord(
        step_id=step_id,
        display_order=display_order,
        title=title,
        fields=[
            FieldRef(role=FieldRole(r), state=FieldState.MISSING)
            for r in MANDATORY_FIELD_ROLES
        ]
    )
    return step
