"""Unit tests for KnowFlow AI extraction modules:
- schema_v1.py (Pydantic contracts for Schema 1.0.0)
- llm_adapters.py (Adapter Pattern for LLM providers)
- exporter.py (Schema 1.0.0 bundle exporter and SHA-256 sync verification)
- extraction_pipeline.py (End-to-end extraction pipeline)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Type
import pytest
from pydantic import BaseModel

from acquisition.extraction.schema_v1 import (
    FieldRole,
    FieldState,
    MANDATORY_FIELD_ROLES,
    QuestionRecord,
    StepRecord,
    WorkflowBundle,
    create_empty_step,
)
from acquisition.extraction.llm_adapters import (
    BaseLLMAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    get_llm_adapter,
)
from acquisition.extraction.exporter import (
    _ensure_context_provenance,
    _sanitize_evidence_spans,
    export_schema_v1_bundle,
    verify_bundle_integrity,
)
from acquisition.extraction.extraction_pipeline import run_extraction_pipeline


# ==============================================================================
# 1. Tests for schema_v1.py
# ==============================================================================

def test_schema_v1_mandatory_field_roles():
    """Confirms that Schema 1.0.0 defines exactly 7 mandatory technical roles."""
    expected = {
        "context",
        "observation",
        "action",
        "rationale",
        "condition",
        "outcome",
        "acceptance_criteria",
    }
    assert set(MANDATORY_FIELD_ROLES) == expected


def test_create_empty_step():
    """Checks create_empty_step initializes all 7 mandatory roles with MISSING state."""
    step = create_empty_step(step_id="ST_001", display_order=1, title="Initial Inspection")
    assert step.step_id == "ST_001"
    assert step.display_order == 1
    assert step.title == "Initial Inspection"
    assert len(step.fields) == 7
    roles = {f.role for f in step.fields}
    assert roles == set(MANDATORY_FIELD_ROLES)
    for f in step.fields:
        assert f.state == FieldState.MISSING
        assert f.claims == []


def test_step_normalization_from_dict():
    """Tests automatic normalization when LLM returns fields as a dict rather than a list."""
    raw_step = {
        "step_id": "ST_001",
        "display_order": 1,
        "title": "Stop spindle",
        "fields": {
            "action": {
                "state": "present",
                "claims": [{"text": "Press Emergency Stop button", "role": "action"}],
            },
            "observation": {
                "state": "present",
                "claims": [{"text": "Spindle comes to a complete stop", "role": "observation"}],
            },
        },
    }
    step = StepRecord.model_validate(raw_step)
    assert len(step.fields) == 7
    action_field = step.get_field(FieldRole.ACTION)
    assert action_field is not None
    assert action_field.state == FieldState.PRESENT
    assert len(action_field.claims) == 1
    assert action_field.claims[0].text == "Press Emergency Stop button"

    # Unprovided fields must default to MISSING
    rationale_field = step.get_field(FieldRole.RATIONALE)
    assert rationale_field is not None
    assert rationale_field.state == FieldState.MISSING


def test_question_record_string_coercion():
    """Tests that a raw string question from LLM is automatically coerced to QuestionRecord."""
    q = QuestionRecord.model_validate("What is the required torque for the pocket bolts?")
    assert q.question == "What is the required torque for the pocket bolts?"
    assert q.target_field == FieldRole.RATIONALE
    assert q.reason == "missing"
    assert q.status == "open"


def test_workflow_bundle_from_llm_json():
    """Tests parsing LLM output with Markdown code block wrappers."""
    raw_response = """```json
    {
        "schema_version": "1.0.0",
        "workflow_id": "REAL_WF_0001",
        "title": "Haas SMTC Pocket Replacement",
        "steps": [
            {
                "step_id": "ST_001",
                "display_order": 1,
                "title": "Power down machine",
                "fields": {
                    "action": {
                        "state": "present",
                        "claims": [
                            {
                                "text": "Switch off main breaker",
                                "role": "action",
                                "evidence_type": "stated",
                                "evidence": ["SRC_HAAS_0005:U0001"]
                            }
                        ]
                    }
                }
            }
        ]
    }
    ```"""
    bundle = WorkflowBundle.from_llm_json(raw_response)
    assert bundle.workflow_id == "REAL_WF_0001"
    assert len(bundle.steps) == 1
    step = bundle.steps[0]
    assert len(step.fields) == 7

    draft = bundle.to_draft_dict()
    assert isinstance(draft["steps"][0]["fields"], dict)
    action_claims = draft["steps"][0]["fields"]["action"]["claims"]
    assert len(action_claims) == 1
    # Evidence must be wrapped in nested list: [["SRC_HAAS_0005:U0001"]]
    assert action_claims[0]["evidence"] == [["SRC_HAAS_0005:U0001"]]


# ==============================================================================
# 2. Tests for llm_adapters.py (Adapter Pattern)
# ==============================================================================

class MockAdapter(BaseLLMAdapter):
    """Mock LLM adapter for deterministic offline testing."""
    def __init__(self, response_text: str):
        super().__init__(model="mock-v1", api_key="mock-key")
        self.response_text = response_text

    def generate_structured_output(
        self,
        prompt: str,
        schema_class: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
    ) -> str:
        return self.response_text


def test_base_adapter_cannot_be_instantiated_directly():
    """Verifies that BaseLLMAdapter enforces abstract method implementation."""
    with pytest.raises(TypeError):
        BaseLLMAdapter(model="test")  # type: ignore[abstract]


def test_mock_adapter_structured_output():
    """Verifies that custom adapter subclass behaves correctly."""
    mock_json = '{"schema_version": "1.0.0", "workflow_id": "TEST_001", "title": "Test", "steps": [{"step_id": "ST_001", "display_order": 1, "title": "T"}]}'
    adapter = MockAdapter(response_text=mock_json)
    output = adapter.generate_structured_output("test prompt")
    bundle = WorkflowBundle.from_llm_json(output)
    assert bundle.workflow_id == "TEST_001"


def test_get_llm_adapter_factory(monkeypatch):
    """Tests provider resolution via factory function."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    # Explicit provider
    gemini = get_llm_adapter(provider="gemini")
    assert isinstance(gemini, GeminiAdapter)

    openai_ad = get_llm_adapter(provider="openai")
    assert isinstance(openai_ad, OpenAIAdapter)

    # Heuristics based on model name
    by_model_gem = get_llm_adapter(model="gemini-2.5-flash")
    assert isinstance(by_model_gem, GeminiAdapter)

    by_model_gpt = get_llm_adapter(model="gpt-4o-mini")
    assert isinstance(by_model_gpt, OpenAIAdapter)


# ==============================================================================
# 3. Tests for exporter.py & Evidence Span Sanitization
# ==============================================================================

def test_sanitize_evidence_spans_consecutive():
    """Candidate IDs in a span must be strictly consecutive; non-consecutive spans are split."""
    # Consecutive span [U0001, U0002] remains intact
    consecutive = [["SRC:U0001", "SRC:U0002"]]
    assert _sanitize_evidence_spans(consecutive) == [["SRC:U0001", "SRC:U0002"]]

    # Non-consecutive span [U0024, U0026] is split into [[U0024], [U0026]]
    non_consecutive = [["SRC:U0024", "SRC:U0026"]]
    sanitized = _sanitize_evidence_spans(non_consecutive)
    assert sanitized == [["SRC:U0024"], ["SRC:U0026"]]

    # String item is wrapped into singleton list
    single_str = ["SRC:U0005"]
    assert _sanitize_evidence_spans(single_str) == [["SRC:U0005"]]


def test_ensure_context_provenance():
    """Checks that all 8 metadata fields receive a valid provenance basis."""
    ctx = {
        "manufacturer": "Haas",
        "subsystem": "SMTC",
        "task_type": "maintenance",
        "symptoms": [],
        "alarm_codes": [],
        "components": ["pocket"],
    }
    enriched = _ensure_context_provenance(ctx, "SRC_HAAS_0005")
    prov = enriched["provenance"]
    assert len(prov) == 8
    assert prov["manufacturer"]["basis"] == "source"
    assert prov["manufacturer"]["source_ids"] == ["SRC_HAAS_0005"]
    assert prov["symptoms"]["basis"] == "unknown"


def test_export_bundle_and_verify_integrity(tmp_path: Path):
    """End-to-end test of export_schema_v1_bundle and verify_bundle_integrity."""
    bundle_data = {
        "schema_version": "1.0.0",
        "workflow_id": "TEST_WF_0001",
        "title": "Pocket replacement test",
        "source_ids": ["SRC_HAAS_0005"],
        "context": {
            "manufacturer": "Haas",
            "subsystem": "SMTC",
            "task_type": "maintenance",
            "symptoms": [],
            "alarm_codes": [],
            "components": [],
        },
        "steps": [
            {
                "step_id": "ST_001",
                "display_order": 1,
                "title": "Stop the carousel",
                "fields": {
                    "action": {
                        "state": "present",
                        "claims": [
                            {
                                "text": "Press emergency stop when the pocket aligns.",
                                "role": "action",
                                "evidence_type": "stated",
                                "evidence": [["SRC_HAAS_0005:U0001"]],
                                "explanation": "The technician explicitly tells the operator to press e-stop.",
                            }
                        ],
                    }
                },
            }
        ],
    }
    bundle = WorkflowBundle.model_validate(bundle_data)
    source_record = {
        "source_id": "SRC_HAAS_0005",
        "title": "Replace Damaged SMTC Pocket",
        "source_type": "real",
        "dataset_split": "dev",
        "language": "en",
        "duration_ms": 350000,
        "publisher": "Haas Automation, Inc.",
        "presenter": "Orville",
    }

    out_bundle_dir = tmp_path / "bundle_test"
    summary = export_schema_v1_bundle(
        bundle=bundle,
        source_record=source_record,
        out_dir=out_bundle_dir,
        compile_snapshot=True,
    )

    assert summary.validation_ok
    assert summary.manifest_path.is_file()
    assert summary.sources_path.is_file()
    assert summary.workflows_path.is_file()
    assert summary.lineage_path.is_file()

    # Verify SHA-256 synchronization and contract validity
    result = verify_bundle_integrity(out_bundle_dir)
    assert result["valid"] is True
    assert result["manifest_sync"] is True
    assert result["lineage_sync"] is True
    assert result["contract_ok"] is True
    assert result["errors_count"] == 0
    assert result["warnings_count"] == 0

    # Tamper detection test: corrupt workflows.jsonl
    (out_bundle_dir / "workflows.jsonl").write_bytes(b"tampered content\n")
    tampered_result = verify_bundle_integrity(out_bundle_dir)
    assert tampered_result["valid"] is False
    assert tampered_result["manifest_sync"] is False


# ==============================================================================
# 4. Tests for extraction_pipeline.py dry run
# ==============================================================================

def test_pipeline_dry_run():
    """Checks that the extraction pipeline runs in dry-run mode without external API calls."""
    bundle = run_extraction_pipeline(
        source_id="SRC_HAAS_0005",
        dry_run=True,
        export_bundle=False,
    )
    assert bundle.workflow_id == "B0_SRC_HAAS_0005"
    assert len(bundle.steps) == 1
    assert bundle.steps[0].display_order == 1
