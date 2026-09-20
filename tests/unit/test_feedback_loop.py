"""Unit tests for feedback_loop.py (WP6 / Expert Answer Ingestion)."""
from __future__ import annotations

import pytest
from knowflow_contracts.enums import (
    QuestionStatus,
    SourceKind,
    SourceType,
    TechnicalReview,
)
from knowflow_contracts.models import Workflow

from acquisition.extraction.feedback_loop import (
    apply_expert_feedback,
    create_expert_answer_source,
)


@pytest.fixture
def sample_workflow_snapshot() -> dict:
    """Provides a minimal valid Schema 1.0.0 workflow snapshot with an open question."""
    return {
        "schema_version": "1.0.0",
        "workflow_id": "TEST_WF_0001",
        "revision": 1,
        "source_type": "real",
        "dataset_split": "dev",
        "title": "Test Maintenance Procedure",
        "language": "en",
        "created_at": "2026-09-11T00:00:00Z",
        "supersedes_revision": None,
        "lifecycle": "active",
        "source_ids": ["SRC_HAAS_0005"],
        "context": {
            "manufacturer": "Haas",
            "machine_family": None,
            "machine_model": None,
            "subsystem": "Side Mount Tool Changer (SMTC)",
            "task_type": "maintenance",
            "symptoms": [],
            "alarm_codes": [],
            "components": [],
            "metadata_provenance": {
                "manufacturer": {"basis": "source", "source_ids": ["SRC_HAAS_0005"], "note": None},
                "machine_family": {"basis": "unknown", "source_ids": [], "note": None},
                "machine_model": {"basis": "unknown", "source_ids": [], "note": None},
                "subsystem": {"basis": "source", "source_ids": ["SRC_HAAS_0005"], "note": None},
                "task_type": {"basis": "curated", "source_ids": [], "note": None},
                "symptoms": {"basis": "unknown", "source_ids": [], "note": None},
                "alarm_codes": {"basis": "unknown", "source_ids": [], "note": None},
                "components": {"basis": "unknown", "source_ids": [], "note": None},
            },
        },
        "steps": [
            {
                "step_id": "TEST_WF_0001_ST_001",
                "display_order": 1,
                "title": "Initial position and stop",
                "fields": {
                    "context": {"state": "missing", "claim_ids": []},
                    "observation": {"state": "missing", "claim_ids": []},
                    "action": {"state": "missing", "claim_ids": []},
                    "rationale": {"state": "missing", "claim_ids": []},
                    "condition": {"state": "missing", "claim_ids": []},
                    "outcome": {"state": "missing", "claim_ids": []},
                    "acceptance_criteria": {"state": "missing", "claim_ids": []},
                },
            }
        ],
        "claims": [],
        "evidence": [],
        "relations": [],
        "questions": [
            {
                "question_id": "TEST_WF_0001_Q_001",
                "step_id": "TEST_WF_0001_ST_001",
                "target_field": "rationale",
                "reason": "missing",
                "question": "Why are rapids reduced to 25% before rotating to the damaged pocket?",
                "status": "open",
                "answer_source_ids": [],
                "resolution_note": None,
            }
        ],
        "review_events": [],
        "change_log": [],
    }


def test_create_expert_answer_source():
    """Tests creation and validation of an expert_answer Source record."""
    source = create_expert_answer_source(
        answer_text="Rapids are lowered to 25% to prevent rotational overrun.",
        expert_name="Orville",
        expert_role="Senior CNC Tech",
    )
    assert source["source_kind"] == SourceKind.EXPERT_ANSWER.value
    assert source["source_type"] == SourceType.REAL.value
    assert source["presenter"] == "Orville"
    assert source["presenter_role"] == "Senior CNC Tech"
    assert source["raw_text"] == "Rapids are lowered to 25% to prevent rotational overrun."
    assert source["content_sha256"] is not None


def test_create_expert_answer_source_validation_errors():
    """Confirms empty inputs raise ValueError."""
    with pytest.raises(ValueError, match="answer_text"):
        create_expert_answer_source("", expert_name="Orville", expert_role="Tech")
    with pytest.raises(ValueError, match="expert_name"):
        create_expert_answer_source("Some answer", expert_name="", expert_role="Tech")


def test_apply_expert_feedback_flow(sample_workflow_snapshot):
    """Tests applying an expert feedback answer: revision bump, question resolution, claim insertion."""
    new_wf, source_record = apply_expert_feedback(
        snapshot=sample_workflow_snapshot,
        target_question_id="TEST_WF_0001_Q_001",
        expert_name="Orville",
        expert_role="Haas Certified Technician",
        answer_text="Rapids are lowered to 25% to ensure precise stop position and prevent mechanical collision.",
        resolution_status="resolved",
    )

    # 1. Revision bumping and immutability
    assert new_wf["revision"] == 2
    assert new_wf["supersedes_revision"] == 1
    assert sample_workflow_snapshot["revision"] == 1  # Base snapshot remains untouched

    # 2. Source inclusion
    assert source_record["source_id"] in new_wf["source_ids"]

    # 3. Question transition
    q = new_wf["questions"][0]
    assert q["status"] == QuestionStatus.RESOLVED.value
    assert source_record["source_id"] in q["answer_source_ids"]
    assert "Orville" in q["resolution_note"]

    # 4. Target step field update
    step = new_wf["steps"][0]
    rat_field = step["fields"]["rationale"]
    assert rat_field["state"] == "present"
    assert len(rat_field["claim_ids"]) == 1
    new_cid = rat_field["claim_ids"][0]

    # 5. Claim validation
    claim = next(c for c in new_wf["claims"] if c["claim_id"] == new_cid)
    assert claim["role"] == "rationale"
    assert claim["attribution"]["label"] == "Orville"
    assert claim["support_status"] == "supported"
    assert claim["technical_review"] == TechnicalReview.EXPERT_VALIDATED.value

    # 6. Change log
    assert len(new_wf["change_log"]) == 1
    assert new_wf["change_log"][0]["previous_revision"] == 1
    assert new_wf["change_log"][0]["actor_id"] == "Orville"

    # 7. Overall schema validity
    validated = Workflow.model_validate(new_wf)
    assert validated.workflow_id == "TEST_WF_0001"
    assert validated.revision == 2
