"""Pydantic models cho Schema 1.0.0 (KnowFlow AI).

Nguyen tac:
- extra="forbid" o moi model: khoa la bi chan ngay tang V01.
- Optional co nghia "co the null", KHONG co nghia "duoc bo khoa".
  Vi vay moi truong optional deu bat buoc co mat, kieu `X | None`.
- Model chi kiem tra cau truc/kieu/enum. Cac rang buoc lien thuc the
  (tham chieu, review, relation, corpus) nam o `rules.py`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .enums import (
    AnswerStatus,
    AttributionKind,
    ClaimRole,
    DatasetSplit,
    EvidenceKind,
    FieldState,
    Lifecycle,
    Modality,
    ProvenanceBasis,
    QueryMode,
    QuestionReason,
    QuestionStatus,
    RelationType,
    ReviewDecision,
    ReviewDimension,
    ReviewTargetType,
    ScopeLevel,
    SourceKind,
    SourceReview,
    SourceType,
    SupportStatus,
    TaskType,
    Team,
    TechnicalReview,
    TranscriptOrigin,
)

SCHEMA_VERSION = "1.0.0"

# RFC 3339. `_UTC` bat buoc offset Z hoac +00:00 (muc 1 cua Schema chung).
_RFC3339_UTC = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$"
_RFC3339_ANY = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
_SHA256 = r"^[0-9a-f]{64}$"
# D-03: ma ngon ngu BCP-47 rut gon, chu thuong o subtag dau ("vi", "en", "en-US").
_LANGUAGE = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"

Rfc3339Utc = Annotated[str, StringConstraints(pattern=_RFC3339_UTC)]
Rfc3339 = Annotated[str, StringConstraints(pattern=_RFC3339_ANY)]
Sha256 = Annotated[str, StringConstraints(pattern=_SHA256)]
LanguageCode = Annotated[str, StringConstraints(pattern=_LANGUAGE)]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class Strict(BaseModel):
    """Base chung: chan khoa la, serialize enum ra string."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


# --- Manifest ---------------------------------------------------------------


class FileEntry(Strict):
    path: NonEmptyStr
    sha256: Sha256
    record_count: int = Field(ge=0)


class Producer(Strict):
    team: Team
    pipeline_version: NonEmptyStr


class Manifest(Strict):
    schema_version: Literal["1.0.0"]
    bundle_id: NonEmptyStr
    source_type: SourceType
    dataset_split: DatasetSplit
    created_at: Rfc3339Utc
    files: list[FileEntry]
    producer: Producer


# --- Source -----------------------------------------------------------------


class Source(Strict):
    source_id: NonEmptyStr
    source_type: SourceType
    source_kind: SourceKind
    title: NonEmptyStr
    url: str | None
    asset_uri: str | None
    # D-03: ngon ngu THUC TE cua nguon, khong phai ngon ngu hien thi.
    language: LanguageCode | None
    duration_ms: int | None = Field(ge=0)
    publisher: str | None
    presenter: str | None
    presenter_role: str | None
    published_at: Rfc3339 | None
    retrieved_at: Rfc3339Utc
    raw_text: str | None
    content_sha256: Sha256 | None
    related_source_ids: list[str]
    access_note: str | None


# --- Evidence ---------------------------------------------------------------


class Locator(Strict):
    start_ms: int | None = Field(ge=0)
    end_ms: int | None = Field(ge=0)
    page: int | None = Field(ge=1)
    text_span: str | None


class Evidence(Strict):
    evidence_id: NonEmptyStr
    source_id: NonEmptyStr
    modality: Modality
    locator: Locator
    quote: str | None
    observation_note: str | None
    asset_uri: str | None
    transcript_origin: TranscriptOrigin
    parent_evidence_ids: list[str]


# --- Claim ------------------------------------------------------------------


class Attribution(Strict):
    actor_id: str | None
    label: str | None
    kind: AttributionKind


class Scope(Strict):
    level: ScopeLevel
    description: str


class EvidenceLink(Strict):
    evidence_id: NonEmptyStr
    support_status: SupportStatus
    explanation: str


class Claim(Strict):
    claim_id: NonEmptyStr
    text: NonEmptyStr
    role: ClaimRole
    evidence_type: EvidenceKind
    attribution: Attribution
    scope: Scope
    evidence_links: list[EvidenceLink]
    support_status: SupportStatus
    source_review: SourceReview
    technical_review: TechnicalReview
    conflicts_with: list[str]
    supersedes_claim_ids: list[str]


# --- Step -------------------------------------------------------------------


class FieldRef(Strict):
    """Lop noi giua Step va Claim. Khong sao chep text cua claim."""

    state: FieldState
    claim_ids: list[str]


class StepFields(Strict):
    """Dung bay khoa, khong hon khong kem."""

    context: FieldRef
    observation: FieldRef
    action: FieldRef
    rationale: FieldRef
    condition: FieldRef
    outcome: FieldRef
    acceptance_criteria: FieldRef


class Step(Strict):
    step_id: NonEmptyStr
    display_order: int = Field(ge=1)
    title: NonEmptyStr
    fields: StepFields


# --- Context ----------------------------------------------------------------


class ProvenanceEntry(Strict):
    basis: ProvenanceBasis
    source_ids: list[str]
    note: str | None


class MetadataProvenance(Strict):
    manufacturer: ProvenanceEntry
    machine_family: ProvenanceEntry
    machine_model: ProvenanceEntry
    subsystem: ProvenanceEntry
    task_type: ProvenanceEntry
    symptoms: ProvenanceEntry
    alarm_codes: ProvenanceEntry
    components: ProvenanceEntry


class Context(Strict):
    manufacturer: str | None
    machine_family: str | None
    machine_model: str | None
    subsystem: str | None
    task_type: TaskType | None
    symptoms: list[str]
    alarm_codes: list[str]
    components: list[str]
    metadata_provenance: MetadataProvenance


class QueryContext(Strict):
    """Context nguoi dung gui kem cau hoi: khong co metadata_provenance."""

    manufacturer: str | None = None
    machine_family: str | None = None
    machine_model: str | None = None
    subsystem: str | None = None
    task_type: TaskType | None = None
    symptoms: list[str] = Field(default_factory=list)
    alarm_codes: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)


# --- Relation / Question / History ------------------------------------------


class Relation(Strict):
    relation_id: NonEmptyStr
    from_step_id: NonEmptyStr
    to_step_id: NonEmptyStr
    relation_type: RelationType
    claim_ids: list[str] = Field(min_length=1)
    condition_claim_ids: list[str]


class Question(Strict):
    question_id: NonEmptyStr
    step_id: NonEmptyStr
    target_field: Literal[
        "context",
        "observation",
        "action",
        "rationale",
        "condition",
        "outcome",
        "acceptance_criteria",
    ]
    reason: QuestionReason
    question: NonEmptyStr
    status: QuestionStatus
    answer_source_ids: list[str]
    resolution_note: str | None


class ReviewEvent(Strict):
    review_id: NonEmptyStr
    target_type: ReviewTargetType
    target_id: NonEmptyStr
    dimension: ReviewDimension
    decision: ReviewDecision
    reviewer_id: NonEmptyStr
    reviewer_role: str
    reviewed_at: Rfc3339Utc
    note: str | None


class IdMapping(Strict):
    old_id: NonEmptyStr
    new_ids: list[str]


class ChangeEvent(Strict):
    changed_at: Rfc3339Utc
    actor_id: NonEmptyStr
    reason: NonEmptyStr
    previous_revision: int | None = Field(ge=1)
    id_mapping: list[IdMapping]


# --- Workflow snapshot ------------------------------------------------------


class Workflow(Strict):
    schema_version: Literal["1.0.0"]
    workflow_id: NonEmptyStr
    revision: int = Field(ge=1)
    source_type: SourceType
    dataset_split: DatasetSplit
    title: NonEmptyStr
    # D-03: ngon ngu dung de viet Claim.text. Video Haas tieng Anh => "en".
    # Evidence.quote luon giu nguyen van ngon ngu nguon, khong dich.
    language: LanguageCode
    created_at: Rfc3339Utc
    supersedes_revision: int | None = Field(ge=1)
    lifecycle: Lifecycle
    source_ids: list[str]
    context: Context
    steps: list[Step]
    claims: list[Claim]
    evidence: list[Evidence]
    relations: list[Relation]
    questions: list[Question]
    review_events: list[ReviewEvent]
    change_log: list[ChangeEvent]

    @property
    def key(self) -> tuple[str, int]:
        return (self.workflow_id, self.revision)


# --- API (muc 7) ------------------------------------------------------------


class EntityRef(Strict):
    workflow_id: NonEmptyStr
    revision: int = Field(ge=1)
    entity_type: NonEmptyStr
    entity_id: NonEmptyStr


class Citation(Strict):
    answer_span: str
    claim_ref: EntityRef
    evidence_ids: list[str]
    # D-04: chat hon ban DOCX (string tu do) -> enum, tranh troi gia tri.
    source_review: SourceReview
    technical_review: TechnicalReview


class QueryRequest(Strict):
    question: NonEmptyStr
    context: QueryContext
    mode: QueryMode
    dataset_split: DatasetSplit


class AnswerResponse(Strict):
    status: AnswerStatus
    answer: str
    citations: list[Citation]
    missing_context: list[str]
    unresolved_claim_refs: list[EntityRef]
    index_build_id: str


class ParsedBundle(Strict):
    """Ba tep cua mot ban giao, da parse."""

    manifest: Manifest
    sources: list[Source]
    workflows: list[Workflow]
