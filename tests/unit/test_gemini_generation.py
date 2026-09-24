"""Adapter boundary regressions without SDK installation, keys or network calls."""

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from retrieval.generation.gemini import GeminiAnswerModel, provider_schema
from retrieval.generation.models import AnswerDraft, GenerationError, InvalidGeneration


@pytest.fixture
def adapter(monkeypatch):
    calls = []
    state = {"response": '{"status":"insufficient_evidence","statements":[]}', "error": None, "errors": []}

    def send(**kwargs):
        calls.append(kwargs)
        if state["errors"]:
            raise state["errors"].pop(0)
        if state["error"]:
            raise state["error"]
        return SimpleNamespace(text=state["response"])

    client = SimpleNamespace(models=SimpleNamespace(generate_content=send), close=lambda: None)
    sdk = ModuleType("google.genai")
    sdk.Client = lambda **kwargs: client
    sdk.types = SimpleNamespace(HttpOptions=lambda **kw: kw, GenerateContentConfig=lambda **kw: kw,
                                AutomaticFunctionCallingConfig=lambda **kw: kw)
    google = ModuleType("google")
    google.genai = sdk
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", sdk)
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-not-a-real-key")
    return GeminiAnswerModel(), calls, state


def test_provider_schema_inlines_refs_without_sdk_schema_conversion(adapter):
    model, calls, _ = adapter
    assert model.draft({"question": "test"}).status == "insufficient_evidence"
    config = calls[0]["config"]
    assert "response_schema" not in config
    wire = config["response_json_schema"]
    assert wire == provider_schema(AnswerDraft)
    assert "$defs" not in wire and "additionalProperties" not in wire
    statement = wire["properties"]["statements"]["items"]
    assert set(statement["required"]) == {"text", "claim_ref", "evidence_ids"}
    assert statement["properties"]["claim_ref"]["properties"]["revision"] == {"type": "integer"}
    assert wire["properties"]["status"]["enum"] == ["answered", "insufficient_evidence"]
    assert config["automatic_function_calling"] == {"disable": True}
    model.close()


@pytest.mark.parametrize("response", ["not json", "", '{"status":"answered","statements":[],"extra":"bad"}'])
def test_malformed_provider_output_still_rejected_locally(adapter, response):
    model, _, state = adapter
    state["response"] = response
    with pytest.raises(InvalidGeneration):
        model.draft({"question": "test"})


def test_provider_exception_is_not_reflected_in_public_message(adapter):
    model, _, state = adapter
    state["error"] = RuntimeError("private-provider-details")
    with pytest.raises(GenerationError) as caught:
        model.draft({"question": "test"})
    assert "private-provider-details" not in str(caught.value)


def test_key_is_read_from_dotenv_when_the_environment_has_none(adapter, monkeypatch):
    """The embedder, translator and API app load .env themselves; an eval whose retrieval is fully cached
    reaches the answer model first and used to fail every question with 'not configured'."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: monkeypatch.setenv("GEMINI_API_KEY", "from-dotenv"))
    model = GeminiAnswerModel()
    assert model.draft({"question": "test"}).status == "insufficient_evidence"
    model.close()


def test_missing_key_everywhere_is_still_a_generic_configuration_error(adapter, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    with pytest.raises(GenerationError, match="not configured"):
        GeminiAnswerModel().draft({"question": "test"})


class ProviderError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def test_rate_limited_answer_call_waits_the_server_delay_then_succeeds(adapter):
    _, calls, state = adapter
    state["errors"] = [ProviderError(429, "RESOURCE_EXHAUSTED retryDelay: '2s'")]
    waits = []
    model = GeminiAnswerModel(sleep=waits.append)
    assert model.draft({"question": "test"}).status == "insufficient_evidence"
    assert len(calls) == 2 and waits == [3.0]
    model.close()


def test_persistent_rate_limit_still_ends_in_a_generic_generation_error(adapter):
    _, calls, state = adapter
    state["error"] = ProviderError(429, "quota key=private-provider-details")
    model = GeminiAnswerModel(sleep=lambda _: None)
    with pytest.raises(GenerationError) as caught:
        model.draft({"question": "test"})
    assert len(calls) == 4  # first call plus the helper's three retries
    assert "private-provider-details" not in str(caught.value)


def test_non_rate_limit_provider_error_is_not_retried(adapter):
    _, calls, state = adapter
    state["error"] = ProviderError(500, "internal")
    model = GeminiAnswerModel(sleep=lambda _: pytest.fail("must not wait"))
    with pytest.raises(GenerationError):
        model.draft({"question": "test"})
    assert len(calls) == 1


@pytest.mark.parametrize("invalid", ["text_length", "revision", "statement_count"])
def test_full_local_constraints_still_apply_after_wire_simplification(adapter, invalid):
    model, _, state = adapter
    statement = {"text": "A source statement", "claim_ref": {"workflow_id": "WF", "revision": 1,
                 "entity_type": "claim", "entity_id": "CL"}, "evidence_ids": ["EV"]}
    draft = {"status": "answered", "statements": [statement]}
    if invalid == "text_length":
        statement["text"] = "x" * 2001
    elif invalid == "revision":
        statement["claim_ref"]["revision"] = 0
    else:
        draft["statements"] *= 61
    state["response"] = json.dumps(draft)
    with pytest.raises(InvalidGeneration):
        model.draft({"question": "test"})
