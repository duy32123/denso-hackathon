"""Unit tests for context_expansion.py (Baseline B2 / WP4 Context Window Expansion)."""
from __future__ import annotations

import pytest

from acquisition.extraction import evidence_pool as ep
from acquisition.extraction.context_expansion import (
    expand_step_context,
    get_adjacent_candidate_ids,
    parse_candidate_ordinal,
    scan_candidates_for_role,
)


@pytest.fixture
def mock_evidence_pool() -> dict[str, ep.Candidate]:
    """Provides a small synthetic evidence candidate pool for testing."""
    candidates = [
        ep.Candidate(
            candidate_id=f"SRC_HAAS_0005:U{i:04d}",
            source_id="SRC_HAAS_0005",
            kind="U",
            ordinal=i,
            modality="speech",
            start_ms=(i - 1) * 5000,
            end_ms=i * 5000,
            text={
                1: "Hello today we will replace a damaged pocket on the Haas tool changer.",
                2: "Set your rapids down to 25% and rotate to the pocket.",
                3: "Press E-stop because rotating at high speed might cause mechanical overtravel.",
                4: "Verify that the pocket slider is completely engaged before proceeding.",
                5: "Make sure the gap is within 0.020 inches.",
            }.get(i, f"Utterance text {i}"),
            transcript_origin="official_caption",
            parent_candidate_id=None,
            input_file="test_input.json",
            input_sha256="dummy_hash",
            text_span_unique=True,
        )
        for i in range(1, 6)
    ]
    return {c.candidate_id: c for c in candidates}


def test_parse_candidate_ordinal():
    """Tests parsing valid and invalid candidate IDs."""
    parsed = parse_candidate_ordinal("SRC_HAAS_0005:U0012")
    assert parsed == ("SRC_HAAS_0005", "U", 12)

    parsed_txt = parse_candidate_ordinal("SRC_HAAS_0002:T0007")
    assert parsed_txt == ("SRC_HAAS_0002", "T", 7)

    assert parse_candidate_ordinal("INVALID_STRING") is None


def test_get_adjacent_candidate_ids(mock_evidence_pool):
    """Tests finding candidate IDs within a given window."""
    adj = get_adjacent_candidate_ids(
        pool=mock_evidence_pool,
        source_id="SRC_HAAS_0005",
        kind="U",
        base_ordinals={2},
        window=1,
    )
    # Window ±1 of 2 is {1, 3} (excluding 2)
    assert set(adj) == {"SRC_HAAS_0005:U0001", "SRC_HAAS_0005:U0003"}


def test_scan_candidates_for_role(mock_evidence_pool):
    """Tests scanning candidates for rationale and condition keywords."""
    c3 = mock_evidence_pool["SRC_HAAS_0005:U0003"]
    matches_rat = scan_candidates_for_role([c3], "rationale")
    assert len(matches_rat) == 1
    assert matches_rat[0][1] == "because"

    c4 = mock_evidence_pool["SRC_HAAS_0005:U0004"]
    matches_cond = scan_candidates_for_role([c4], "condition")
    assert len(matches_cond) == 1
    assert matches_cond[0][1] == "before"


def test_expand_step_context_success(mock_evidence_pool):
    """Tests successful expansion when adjacent cue provides missing rationale."""
    step = {
        "step_id": "ST_001",
        "title": "Set rapids and press E-stop",
        "fields": {
            "action": [
                {
                    "text": "Set rapids down to 25%.",
                    "evidence": [["SRC_HAAS_0005:U0002"]],
                    "explanation": "Narrator states action",
                }
            ],
            "rationale": {"state": "missing", "claims": []},
            "condition": {"state": "missing", "claims": []},
        },
    }

    result = expand_step_context(step, pool=mock_evidence_pool, max_rounds=2, window_size=1)
    assert result.rounds_executed >= 1
    assert "rationale" in result.fields_augmented
    assert "SRC_HAAS_0005:U0003" in result.fields_augmented["rationale"]

    # Verify step field was updated
    assert step["fields"]["rationale"]["state"] == "present"
    assert len(step["fields"]["rationale"]["claims"]) >= 1
    assert "because" in step["fields"]["rationale"]["claims"][0]["text"]


def test_expand_step_context_max_rounds_budget(mock_evidence_pool):
    """Verifies that context expansion strictly halts at max_rounds (WP4 budget rule)."""
    step = {
        "step_id": "ST_002",
        "title": "Unobtainable rationale step",
        "fields": {
            "action": [
                {
                    "text": "Action from cue 1",
                    "evidence": [["SRC_HAAS_0005:U0001"]],
                }
            ],
            "rationale": {"state": "missing", "claims": []},
        },
    }

    result = expand_step_context(step, pool=mock_evidence_pool, max_rounds=2, window_size=1)
    # Must never exceed 2 rounds
    assert all(entry.round_number <= 2 for entry in result.audit_log)
