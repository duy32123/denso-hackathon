"""Invariants for the D1-A keyframe-evidence-hardening ledgers
(data/keyframes/keyframe_{candidates,selections,replacements,review}.jsonl).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from acquisition.preprocessing import keyframes as kf

LEDGER_DIR = kf.REPO_ROOT / "data" / "keyframes"
HOLDOUT_SOURCE_IDS = {"SRC_HAAS_0006", "SRC_HAAS_0007"}
VALID_REVIEW_DECISIONS = {"accepted", "rejected", "replace", "needs_sequence", "needs_clip"}


def _rows(name: str) -> list[dict]:
    path = LEDGER_DIR / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("ledger", ["keyframe_candidates.jsonl", "keyframe_selections.jsonl", "keyframe_review.jsonl"])
def test_no_holdout_source_appears_in_any_ledger(ledger):
    for row in _rows(ledger):
        assert row.get("source_id") not in HOLDOUT_SOURCE_IDS, f"{ledger}: holdout source leaked into {row}"


def test_selections_ledger_retains_rejected_candidates_not_only_winners():
    selections = _rows("keyframe_selections.jsonl")
    verdicts = {row["verdict"] for row in selections}
    assert "reject" in verdicts or "replace" in verdicts, "expected at least one non-accepted verdict retained"
    assert any(v == "accepted" for v in verdicts), "expected accepted candidates retained too"


def test_every_replacement_names_a_previous_artifact_and_a_reason():
    for row in _rows("keyframe_replacements.jsonl"):
        assert row["previous_artifact_id"]
        assert row["rejection_reason"]
        assert row["original_timestamp_ms"] >= 0
        # replacement_artifact_id may be null (unresolved) but the key must be present
        assert "replacement_artifact_id" in row


def test_review_ledger_uses_only_valid_decisions():
    for row in _rows("keyframe_review.jsonl"):
        assert row["review_decision"] in VALID_REVIEW_DECISIONS, row


def test_review_ledger_marks_ai_review_as_not_human_signed_off():
    """This session's review was Claude Opus 5 reading pixels, not a human. That gap
    must be visible in the data, not silently implied as satisfied.
    """
    rows = _rows("keyframe_review.jsonl")
    assert rows
    for row in rows:
        assert row["reviewer_kind"] == "ai_vision_review"
        # A sign-off is a named person and a date, never a bare flag; the pilot rows have none yet.
        signoff = row["human_signoff"]
        assert signoff is None or (signoff["by"].strip() and signoff["at"].endswith("Z")), row


def test_keyframes_added_after_the_pilot_are_signed_off_by_a_person():
    later = [r for r in _rows("keyframe_review.jsonl") if r["source_id"] >= "SRC_HAAS_0008"]
    assert len(later) == 31
    for row in later:
        assert row["human_signoff"] and row["human_signoff"]["by"] != row["reviewer_id"], row


def test_every_selection_original_timestamp_is_within_its_source_duration():
    # Real ffprobe durations (ms) for the three dev sources, confirmed this session.
    durations_ms = {"SRC_HAAS_0001": 191291, "SRC_HAAS_0003": 360333, "SRC_HAAS_0005": 260894,
                    # ffprobe on the 1080p streams of the sources added 2026-10-12
                    "SRC_HAAS_0008": 86069, "SRC_HAAS_0009": 235485, "SRC_HAAS_0010": 90056,
                    "SRC_HAAS_0011": 181400, "SRC_HAAS_0012": 410476}
    for row in _rows("keyframe_selections.jsonl"):
        bound = durations_ms[row["source_id"]]
        assert 0 <= row["original_timestamp_ms"] < bound, row


def test_no_duplicate_source_and_timestamp_within_the_selections_ledger():
    seen = set()
    for row in _rows("keyframe_selections.jsonl"):
        key = (row["source_id"], row["original_timestamp_ms"])
        assert key not in seen, f"duplicate timestamp for {key}"
        seen.add(key)


def test_every_selected_keyframe_artifact_still_exists_and_matches_its_recorded_hash():
    """Missing-local-artifact and content-hash-mismatch guard for the selection ledger
    itself (not just the whole inventory, which test_keyframes.py already covers).
    """
    inventory = {row["artifact_id"]: row for row in kf.load_inventory().values() if row.get("artifact_type") == "keyframe"}
    id_by_source_ts = {(row["source_id"], row["original_start_ms"]): row for row in inventory.values()}
    for row in _rows("keyframe_selections.jsonl"):
        inv_row = id_by_source_ts.get((row["source_id"], row["original_timestamp_ms"]))
        assert inv_row is not None, f"no inventory row for {row['source_id']}@{row['original_timestamp_ms']}"
        path = kf.REPO_ROOT / inv_row["storage_uri"].split(" ")[0]
        assert path.is_file()
        assert kf.sha256_of(path) == inv_row["content_sha256"]


def test_every_keyframe_added_after_the_pilot_is_in_the_selection_and_review_ledgers():
    """The pilot frames were audited in one pass; later sources must not skip the ledgers."""
    later = {"SRC_HAAS_0008", "SRC_HAAS_0009", "SRC_HAAS_0010", "SRC_HAAS_0011", "SRC_HAAS_0012"}
    frames = {(r["source_id"], r["original_start_ms"]): r["artifact_id"] for r in kf.load_inventory().values()
              if r.get("artifact_type") == "keyframe" and r["source_id"] in later}
    assert frames
    selected = {(r["source_id"], r["original_timestamp_ms"]) for r in _rows("keyframe_selections.jsonl")}
    reviewed = {r["evidence_id"] for r in _rows("keyframe_review.jsonl")}
    assert set(frames) <= selected
    assert set(frames.values()) <= reviewed
