"""knowflow_contracts - hop dong du lieu KnowFlow AI, Schema 1.0.0.

Package nay la NGUON SU THAT DUY NHAT cho ca doi 1 va doi 2. Exporter cua doi 1
va importer cua doi 2 phai import cung mot phien ban o day; khong ben nao viet
ban validator rieng.
"""

from __future__ import annotations

from .derive import derive_support_status
from .eligibility import answer_qualifier, claim_blockers, is_assertable
from .issues import CHECK_CODES, Issue, Report, Severity
from .loader import load_bundle, sha256_bytes, sha256_file
from .models import (
    SCHEMA_VERSION,
    AnswerResponse,
    Citation,
    Claim,
    Context,
    EntityRef,
    Evidence,
    EvidenceLink,
    FieldRef,
    Manifest,
    ParsedBundle,
    QueryRequest,
    Question,
    Relation,
    ReviewEvent,
    Source,
    Step,
    Workflow,
)
from .rules import check_bundle
from .snapshot import decide_reimport, snapshot_content_hash
from .validator import validate_bundle

__version__ = SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "CHECK_CODES",
    "AnswerResponse",
    "Citation",
    "Claim",
    "Context",
    "EntityRef",
    "Evidence",
    "EvidenceLink",
    "FieldRef",
    "Issue",
    "Manifest",
    "ParsedBundle",
    "QueryRequest",
    "Question",
    "Relation",
    "Report",
    "ReviewEvent",
    "Severity",
    "Source",
    "Step",
    "Workflow",
    "answer_qualifier",
    "check_bundle",
    "claim_blockers",
    "decide_reimport",
    "derive_support_status",
    "is_assertable",
    "load_bundle",
    "sha256_bytes",
    "sha256_file",
    "snapshot_content_hash",
    "validate_bundle",
]
