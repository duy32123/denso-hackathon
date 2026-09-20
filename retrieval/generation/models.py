"""Private LLM wire format. Public output stays contract AnswerResponse 1.0.0."""

from typing import Literal, Protocol

from pydantic import Field

from knowflow_contracts.models import EntityRef, Strict


class Statement(Strict):
    text: str = Field(min_length=1, max_length=2000)
    claim_ref: EntityRef
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class AnswerDraft(Strict):
    status: Literal["answered", "insufficient_evidence"]
    statements: list[Statement] = Field(max_length=60)


class Verification(Strict):
    answers_question: bool
    supported: list[bool]


class GenerationError(RuntimeError):
    """Provider unavailable; no SDK messages/credentials in the public error."""


class InvalidGeneration(ValueError):
    """Unusable structured output: fail closed, not a retry with weaker policy."""


class AnswerModel(Protocol):
    def draft(self, payload: dict) -> AnswerDraft: ...
    def verify(self, payload: dict) -> Verification: ...
    def close(self) -> None: ...
