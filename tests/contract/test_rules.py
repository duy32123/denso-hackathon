"""Negative tests: boi ban F01 mot cach co chu dich, doi dung ma V bat duoc.

Cac ca sai cau truc chi song o day, KHONG duoc nhap vao data/fixtures/
(bo fixture phuc vu phai luon hop le - muc 1 ke hoach doi 2).
"""

from __future__ import annotations

import copy

import pytest

from knowflow_contracts import validate_bundle


def codes(bundle_dir) -> list[str]:
    return validate_bundle(bundle_dir).error_codes


def first_claim(bundle: dict, claim_id: str) -> dict:
    for claim in bundle["workflows"][0]["claims"]:
        if claim["claim_id"] == claim_id:
            return claim
    raise AssertionError(claim_id)


def test_baseline_fixture_is_clean(f01, bundle_writer):
    assert validate_bundle(bundle_writer(f01)).ok


# --- V01 ---------------------------------------------------------------------


def test_v01_unknown_key_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["claims"][0]["confidence"] = 0.93
    assert "V01" in codes(bundle_writer(f01))


def test_v01_missing_optional_key_is_rejected(f01, bundle_writer):
    """Optional = co the null, KHONG phai duoc bo khoa."""
    del f01["workflows"][0]["context"]["machine_family"]
    assert "V01" in codes(bundle_writer(f01))


def test_v01_bad_enum_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["claims"][0]["evidence_type"] = "assumed"
    assert "V01" in codes(bundle_writer(f01))


def test_v01_non_utc_timestamp_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["created_at"] = "2026-09-08T00:00:00+07:00"
    assert "V01" in codes(bundle_writer(f01))


# --- V02 ---------------------------------------------------------------------


def test_v02_checksum_mismatch_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["title"] = "Doi noi dung ma khong cap nhat checksum"
    assert "V02" in codes(bundle_writer(f01, fix_checksums=False))


def test_v02_record_count_mismatch_is_rejected(f01, bundle_writer):
    path = bundle_writer(f01)
    manifest = path / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"record_count": 1', '"record_count": 2'), encoding="utf-8")
    assert "V02" in codes(path)


def test_v02_split_mismatch_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["dataset_split"] = "holdout"
    assert "V02" in codes(bundle_writer(f01))


# --- V03 ---------------------------------------------------------------------


def test_v03_orphan_claim_reference_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["steps"][0]["fields"]["action"]["claim_ids"] = ["SYN_WF_0001_CL_999"]
    assert "V03" in codes(bundle_writer(f01))


def test_v03_evidence_outside_workflow_sources_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["evidence"][0]["source_id"] = "SYN_SRC_9999"
    assert "V03" in codes(bundle_writer(f01))


def test_v03_evidence_must_not_change_across_revisions(f09, bundle_writer):
    """D-02: doi locator ma giu nguyen evidence_id lam citation cu tro sai cho."""
    rev2 = f09["workflows"][1]
    for ev in rev2["evidence"]:
        if ev["evidence_id"].endswith("_EV_001"):
            ev["locator"]["text_span"] = "Cau da bi sua lai."
    assert "V03" in codes(bundle_writer(f09))


def test_v03_provenance_source_basis_needs_source_ids(f01, bundle_writer):
    f01["workflows"][0]["context"]["metadata_provenance"]["machine_model"] = {
        "basis": "source",
        "source_ids": [],
        "note": None,
    }
    assert "V03" in codes(bundle_writer(f01))


def test_v03_provenance_unknown_with_value_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["context"]["metadata_provenance"]["machine_model"]["basis"] = "unknown"
    assert "V03" in codes(bundle_writer(f01))


# --- V04 ---------------------------------------------------------------------


def test_v04_reversed_time_window_is_rejected(f01, bundle_writer):
    loc = f01["workflows"][0]["evidence"][0]["locator"]
    loc["start_ms"], loc["end_ms"] = loc["end_ms"], loc["start_ms"]
    assert "V04" in codes(bundle_writer(f01))


def test_v04_end_beyond_duration_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["evidence"][0]["locator"]["end_ms"] = 10**9
    assert "V04" in codes(bundle_writer(f01))


def test_v04_locator_without_any_anchor_is_rejected(f01, bundle_writer):
    f01["workflows"][0]["evidence"][0]["locator"] = {"start_ms": None, "end_ms": None, "page": None, "text_span": None}
    assert "V04" in codes(bundle_writer(f01))


# --- V05 ---------------------------------------------------------------------


def test_v05_missing_state_must_have_no_claims(f01, bundle_writer):
    fields = f01["workflows"][0]["steps"][1]["fields"]
    fields["rationale"] = {"state": "missing", "claim_ids": ["SYN_WF_0001_CL_004"]}
    assert "V05" in codes(bundle_writer(f01))


def test_v05_present_state_must_have_claims(f01, bundle_writer):
    f01["workflows"][0]["steps"][0]["fields"]["rationale"] = {"state": "present", "claim_ids": []}
    assert "V05" in codes(bundle_writer(f01))


def test_v05_role_mismatch_is_rejected(f01, bundle_writer):
    """Claim rationale khong duoc gan vao field action."""
    step = f01["workflows"][0]["steps"][0]
    step["fields"]["action"]["claim_ids"] = ["SYN_WF_0001_CL_004"]
    assert "V05" in codes(bundle_writer(f01))


def test_v05_relation_claim_cannot_sit_in_a_field(f01, bundle_writer):
    step = f01["workflows"][0]["steps"][1]
    step["fields"]["outcome"] = {"state": "present", "claim_ids": ["SYN_WF_0001_CL_009"]}
    assert "V05" in codes(bundle_writer(f01))


def test_v05_orphan_claim_is_rejected(f01, bundle_writer):
    wf = f01["workflows"][0]
    wf["claims"].append(copy.deepcopy(wf["claims"][0]) | {"claim_id": "SYN_WF_0001_CL_100"})
    assert "V05" in codes(bundle_writer(f01))


# --- V06 ---------------------------------------------------------------------


def test_v06_stated_claim_needs_evidence_link(f01, bundle_writer):
    first_claim(f01, "SYN_WF_0001_CL_004")["evidence_links"] = []
    first_claim(f01, "SYN_WF_0001_CL_004")["support_status"] = "insufficient"
    assert "V06" in codes(bundle_writer(f01))


def test_v06_support_status_must_follow_derivation_rule(f01, bundle_writer):
    """D-01: khong ai duoc tu dat supported khi link chua du."""
    claim = first_claim(f01, "SYN_WF_0001_CL_004")
    claim["evidence_links"][0]["support_status"] = "insufficient"
    assert "V06" in codes(bundle_writer(f01))


def test_v06_speech_evidence_needs_quote(f01, bundle_writer):
    for ev in f01["workflows"][0]["evidence"]:
        if ev["modality"] == "speech":
            ev["quote"] = None
            break
    assert "V06" in codes(bundle_writer(f01))


def test_v06_visual_evidence_needs_observation_note(f01, bundle_writer):
    for ev in f01["workflows"][0]["evidence"]:
        if ev["modality"] == "visual":
            ev["observation_note"] = None
            break
    assert "V06" in codes(bundle_writer(f01))


# --- V07 ---------------------------------------------------------------------


def test_v07_source_checked_needs_review_event(f01, bundle_writer):
    first_claim(f01, "SYN_WF_0001_CL_001")["source_review"] = "source_checked"
    assert "V07" in codes(bundle_writer(f01))


def test_v07_expert_validated_cannot_be_self_granted(f01, bundle_writer):
    first_claim(f01, "SYN_WF_0001_CL_001")["technical_review"] = "expert_validated"
    assert "V07" in codes(bundle_writer(f01))


def test_v07_conflict_must_be_symmetric(f01, bundle_writer):
    first_claim(f01, "SYN_WF_0001_CL_006")["conflicts_with"] = ["SYN_WF_0001_CL_002"]
    assert "V07" in codes(bundle_writer(f01))


def test_v07_unresolved_conflict_cannot_be_supported(f01, bundle_writer):
    a = first_claim(f01, "SYN_WF_0001_CL_006")
    b = first_claim(f01, "SYN_WF_0001_CL_002")
    a["conflicts_with"] = [b["claim_id"]]
    b["conflicts_with"] = [a["claim_id"]]
    report = validate_bundle(bundle_writer(f01))
    assert "V07" in report.error_codes or "V06" in report.error_codes


# --- V08 ---------------------------------------------------------------------


def test_v08_branch_if_needs_condition(f01, bundle_writer):
    f01["workflows"][0]["relations"][0]["relation_type"] = "branch_if"
    assert "V08" in codes(bundle_writer(f01))


def test_v08_relation_claim_must_have_relation_role(f01, bundle_writer):
    f01["workflows"][0]["relations"][0]["claim_ids"] = ["SYN_WF_0001_CL_003"]
    assert "V08" in codes(bundle_writer(f01))


def test_v08_requires_cycle_is_rejected(f01, bundle_writer):
    wf = f01["workflows"][0]
    wf["relations"][0]["relation_type"] = "requires"
    wf["relations"].append(
        {
            "relation_id": "SYN_WF_0001_RL_002",
            "from_step_id": "SYN_WF_0001_ST_002",
            "to_step_id": "SYN_WF_0001_ST_001",
            "relation_type": "requires",
            "claim_ids": ["SYN_WF_0001_CL_009"],
            "condition_claim_ids": [],
        }
    )
    assert "V08" in codes(bundle_writer(f01))


# --- V09 ---------------------------------------------------------------------


def test_v09_duplicate_snapshot_key_is_rejected(f01, bundle_writer):
    f01["workflows"].append(copy.deepcopy(f01["workflows"][0]))
    assert "V09" in codes(bundle_writer(f01))


def test_v09_revision_two_needs_change_log(f09, bundle_writer):
    f09["workflows"][1]["change_log"] = []
    assert "V09" in codes(bundle_writer(f09))


def test_v09_first_revision_cannot_supersede(f01, bundle_writer):
    f01["workflows"][0]["supersedes_revision"] = 1
    assert "V09" in codes(bundle_writer(f01))


@pytest.mark.parametrize("expected", ["noop", "conflict", "new"])
def test_v09_reimport_decision(f01, expected):
    from knowflow_contracts import decide_reimport, snapshot_content_hash
    from knowflow_contracts.models import Workflow

    wf = Workflow.model_validate(f01["workflows"][0])
    if expected == "noop":
        assert decide_reimport(snapshot_content_hash(wf), wf) == "noop"
    elif expected == "conflict":
        assert decide_reimport("0" * 64, wf) == "conflict"
    else:
        assert decide_reimport(None, wf) == "new"


# --- V10 ---------------------------------------------------------------------


def test_v10_withdrawn_latest_revision_is_flagged(f09, bundle_writer):
    f09["workflows"][1]["lifecycle"] = "withdrawn"
    report = validate_bundle(bundle_writer(f09))
    assert any(i.code == "V10" for i in report.warnings)
