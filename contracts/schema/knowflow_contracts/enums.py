"""Toan bo enum cua Schema 1.0.0.

Moi enum o day la nguon su that duy nhat cho ca hai doi. Doi ten hoac them
gia tri = doi hop dong => phai tang schema_version va viet migration.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """str + Enum de serialize thang ra JSON."""

    def __str__(self) -> str:  # pragma: no cover - tien ich hien thi
        return self.value


# --- Bundle -----------------------------------------------------------------


class SourceType(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class DatasetSplit(StrEnum):
    DEV = "dev"
    HOLDOUT = "holdout"


class Team(StrEnum):
    TEAM_1 = "team_1"
    TEAM_2 = "team_2"


# --- Source / Evidence ------------------------------------------------------


class SourceKind(StrEnum):
    OFFICIAL_SERVICE_VIDEO = "official_service_video"
    SERVICE_DOCUMENT = "service_document"
    EXPERT_ANSWER = "expert_answer"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class Modality(StrEnum):
    VISUAL = "visual"
    SPEECH = "speech"
    TEXT = "text"


class TranscriptOrigin(StrEnum):
    ASR = "asr"
    OFFICIAL_CAPTION = "official_caption"
    HUMAN = "human"
    NONE = "none"


# --- Workflow / Context -----------------------------------------------------


class Lifecycle(StrEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class TaskType(StrEnum):
    TROUBLESHOOTING = "troubleshooting"
    RECOVERY = "recovery"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    OTHER = "other"


class ProvenanceBasis(StrEnum):
    SOURCE = "source"
    CURATED = "curated"
    UNKNOWN = "unknown"


# --- Step / Claim -----------------------------------------------------------


class FieldState(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"


class FieldRole(StrEnum):
    """Bay khoa cua Step.fields."""

    CONTEXT = "context"
    OBSERVATION = "observation"
    ACTION = "action"
    RATIONALE = "rationale"
    CONDITION = "condition"
    OUTCOME = "outcome"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"


class ClaimRole(StrEnum):
    """Bay role cua Step + role rieng cho claim duoc Relation tham chieu."""

    CONTEXT = "context"
    OBSERVATION = "observation"
    ACTION = "action"
    RATIONALE = "rationale"
    CONDITION = "condition"
    OUTCOME = "outcome"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    RELATION = "relation"


FIELD_ROLES: tuple[str, ...] = tuple(r.value for r in FieldRole)


class EvidenceKind(StrEnum):
    """Gia tri cua Claim.evidence_type."""

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


class SourceReview(StrEnum):
    PENDING = "pending"
    SOURCE_CHECKED = "source_checked"
    REJECTED = "rejected"


class TechnicalReview(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    EXPERT_VALIDATED = "expert_validated"
    REJECTED = "rejected"


# --- Relation / Question / Review -------------------------------------------


class RelationType(StrEnum):
    OBSERVED_NEXT = "observed_next"
    REQUIRES = "requires"
    BRANCH_IF = "branch_if"
    REPEATED_STEP = "repeated_step"
    CORRECTS = "corrects"


class QuestionReason(StrEnum):
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"
    IDENTITY = "identity"
    UNALIGNED = "unaligned"


class QuestionStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReviewTargetType(StrEnum):
    CLAIM = "claim"
    RELATION = "relation"


class ReviewDimension(StrEnum):
    SOURCE = "source"
    TECHNICAL = "technical"


class ReviewDecision(StrEnum):
    SOURCE_CHECKED = "source_checked"
    EXPERT_VALIDATED = "expert_validated"
    REJECTED = "rejected"


# --- API --------------------------------------------------------------------


class QueryMode(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_SOURCES = "conflicting_sources"
