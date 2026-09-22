"""Unit tests for feedback_loop.py (WP6 / Expert Answer Ingestion)."""
from __future__ import annotations

import json

import pytest
from knowflow_contracts.enums import (
    QuestionStatus,
    SourceKind,
    SourceReview,
    SourceType,
    TechnicalReview,
)
from knowflow_contracts.models import Workflow

from acquisition.extraction.feedback_loop import (
    _next_sequence_id,
    apply_expert_feedback,
    collect_reserved_ids,
    create_expert_answer_source,
    feedback_asset_uri,
    write_feedback_asset,
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
    # V02: nguon real phai co url hoac asset_uri, khong chi raw_text.
    assert source["asset_uri"] == feedback_asset_uri(source["source_id"])
    # Khong bia ten to chuc dung sau mot o text nguoi dung tu go.
    assert source["publisher"] is None


def test_expert_answer_source_is_exportable_under_v02():
    """V02 tu choi ca bundle neu nguon real khong co duong dan truy cap nao."""
    source = create_expert_answer_source(
        answer_text="Air is disconnected so the carousel cannot index while hands are inside.",
        expert_name="Orville",
        expert_role="Senior CNC Tech",
    )
    assert source["url"] or source["asset_uri"]


def test_write_feedback_asset_creates_the_file_asset_uri_points_at(tmp_path):
    """asset_uri tro vao tep khong ton tai thi citation mo khong duoc."""
    source = create_expert_answer_source(
        answer_text="Lower rapids first.", expert_name="Orville", expert_role="Tech"
    )
    written = write_feedback_asset(source, repo_root=tmp_path)

    assert written == tmp_path / source["asset_uri"]
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["raw_text"] == "Lower rapids first."
    assert payload["content_sha256"] == source["content_sha256"]
    # He thong chua co dang nhap; tep phai noi ro dieu do.
    assert payload["presenter_authenticated"] is False


def test_next_sequence_id_uses_the_highest_suffix_not_the_count():
    """len()+1 se cap lai mot ID da mang noi dung khac -> D-02 / V03 (da xay ra o PR #16)."""
    # EV_002 da bi rut khoi ban ghi nhung ID cua no van da duoc phat hanh.
    existing = ["WF_X_EV_001", "WF_X_EV_003"]
    assert _next_sequence_id("WF_X", "EV", existing) == "WF_X_EV_004"
    assert _next_sequence_id("WF_X", "EV", []) == "WF_X_EV_001"
    # ID cua workflow khac khong duoc tinh vao bo dem.
    assert _next_sequence_id("WF_X", "EV", ["WF_Y_EV_009"]) == "WF_X_EV_001"


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
    # D-01: dan xuat tu evidence_links, khong dat tay.
    assert claim["support_status"] == "supported"

    # 6. Change log
    assert len(new_wf["change_log"]) == 1
    assert new_wf["change_log"][0]["previous_revision"] == 1
    assert new_wf["change_log"][0]["actor_id"] == "Orville"

    # 7. Overall schema validity
    validated = Workflow.model_validate(new_wf)
    assert validated.workflow_id == "TEST_WF_0001"
    assert validated.revision == 2


@pytest.mark.parametrize("status", ["answered", "resolved"])
def test_feedback_never_grants_review_status(sample_workflow_snapshot, status):
    """Bat bien so 3: phan hoi khong bao gio tu thanh review.

    He thong chua co dang nhap, `expert_name` la chu nguoi dung tu go. Bien no
    thanh expert_validated la bien mot o text thanh "chuyen gia da xac nhan".
    `resolved` chi noi cau hoi da duoc xu ly, khong noi ai da kiem nguon.
    """
    new_wf, _ = apply_expert_feedback(
        snapshot=sample_workflow_snapshot,
        target_question_id="TEST_WF_0001_Q_001",
        expert_name="Orville",
        expert_role="Haas Certified Technician",
        answer_text="Rapids are lowered to 25% to prevent rotational overrun.",
        resolution_status=status,
    )

    claim = new_wf["claims"][0]
    assert claim["source_review"] == SourceReview.PENDING.value
    assert claim["technical_review"] == TechnicalReview.NOT_REQUESTED.value
    # V07: khong ReviewEvent nao duoc sinh tu day, ke ca dimension=source.
    assert new_wf["review_events"] == []


def test_feedback_default_status_is_answered_not_resolved(sample_workflow_snapshot):
    """Contract muc 3.6: open -> answered; sang resolved la mot buoc rieng."""
    new_wf, _ = apply_expert_feedback(
        snapshot=sample_workflow_snapshot,
        target_question_id="TEST_WF_0001_Q_001",
        expert_name="Orville",
        expert_role="Haas Certified Technician",
        answer_text="Rapids are lowered to 25% to prevent rotational overrun.",
    )
    assert new_wf["questions"][0]["status"] == QuestionStatus.ANSWERED.value


def test_new_ids_do_not_reuse_retired_ids(sample_workflow_snapshot):
    """D-02: ID da phat hanh khong duoc tro sang noi dung khac."""
    snapshot = sample_workflow_snapshot
    # Mo phong mot revision da rut bot ban ghi: con 1 evidence nhung ID cao nhat la 003.
    snapshot["evidence"] = [
        {
            "evidence_id": "TEST_WF_0001_EV_003",
            "source_id": "SRC_HAAS_0005",
            "modality": "text",
            "locator": {"start_ms": None, "end_ms": None, "page": None, "text_span": "earlier excerpt"},
            "quote": "earlier excerpt",
            "observation_note": None,
            "asset_uri": None,
            "transcript_origin": "human",
            "parent_evidence_ids": [],
        }
    ]

    new_wf, _ = apply_expert_feedback(
        snapshot=snapshot,
        target_question_id="TEST_WF_0001_Q_001",
        expert_name="Orville",
        expert_role="Haas Certified Technician",
        answer_text="Rapids are lowered to 25% to prevent rotational overrun.",
    )

    new_ids = [ev["evidence_id"] for ev in new_wf["evidence"]]
    assert new_ids == ["TEST_WF_0001_EV_003", "TEST_WF_0001_EV_004"]
    assert len(set(new_ids)) == len(new_ids)


def test_reserved_ids_from_other_revisions_are_not_reused(sample_workflow_snapshot):
    """Ca that: REAL_WF_0001.r1 het o EV_035 nhung draft r2 da cap EV_036.

    Snapshot goc khong nhin thay revision khac, nen neu khong truyen reserved_ids
    thi feedback se cap lai dung ID do cho mot noi dung khac (D-02 / V03).
    """
    new_wf, _ = apply_expert_feedback(
        snapshot=sample_workflow_snapshot,
        target_question_id="TEST_WF_0001_Q_001",
        expert_name="Orville",
        expert_role="Haas Certified Technician",
        answer_text="Rapids are lowered to 25% to prevent rotational overrun.",
        reserved_ids={"TEST_WF_0001_EV_001", "TEST_WF_0001_CL_007"},
    )

    assert new_wf["evidence"][-1]["evidence_id"] == "TEST_WF_0001_EV_002"
    assert new_wf["claims"][-1]["claim_id"] == "TEST_WF_0001_CL_008"


def test_collect_reserved_ids_reads_every_revision_on_disk():
    """Gom ID tu ca dev/ lan drafts/, ke ca ban chua promote."""
    reserved = collect_reserved_ids("REAL_WF_0001")

    # r1 da promote het o EV_035; draft r2 chua promote da cap EV_036 (PR #16).
    assert "REAL_WF_0001_EV_035" in reserved
    assert "REAL_WF_0001_EV_036" in reserved
    # Khong lan sang workflow khac.
    assert not any(eid.startswith("REAL_WF_0002") for eid in reserved)
