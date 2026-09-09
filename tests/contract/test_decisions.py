"""D-03 (ngon ngu cheo), D-05 (dedup claim), D-06 (index hai tang).

Ba quyet dinh nay chot ngay 2026-09-09; xem contracts/CHANGELOG.md.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from knowflow_contracts import (
    ClaimHit,
    IndexBuild,
    SearchMetadata,
    SearchText,
    StepSearchRecord,
    dedup_claim_hits,
    procedure_workflow_key,
    spans_multiple_workflows,
    validate_bundle,
)
from knowflow_contracts.models import Source, Workflow


# --- D-03: ngon ngu ----------------------------------------------------------


def test_d03_claim_language_must_match_source(f01, bundle_writer):
    """Nguon tieng Anh thi Claim.text phai tieng Anh, khong dich sang vi."""
    f01["sources"][0]["language"] = "en"
    report = validate_bundle(bundle_writer(f01))
    assert "V02" in report.error_codes
    assert any("D-03" in i.message for i in report.errors)


def test_d03_matching_language_passes(f01, bundle_writer):
    f01["sources"][0]["language"] = "en"
    f01["workflows"][0]["language"] = "en"
    assert validate_bundle(bundle_writer(f01)).ok


def test_d03_mixed_language_sources_warn(f01, bundle_writer):
    wf = f01["workflows"][0]
    extra = dict(f01["sources"][0], source_id="SYN_SRC_0001B", language="en")
    f01["sources"].append(extra)
    wf["source_ids"].append("SYN_SRC_0001B")
    report = validate_bundle(bundle_writer(f01))
    assert report.ok
    assert any(i.code == "V02" and "nhieu ngon ngu" in i.message for i in report.warnings)


@pytest.mark.parametrize("code", ["Vi", "vietnamese!", "v", "en_US", ""])
def test_d03_language_code_shape_is_enforced(f01, code):
    payload = dict(f01["workflows"][0], language=code)
    with pytest.raises(ValidationError):
        Workflow.model_validate(payload)


@pytest.mark.parametrize("code", ["vi", "en", "en-US", "vie"])
def test_d03_valid_language_codes(f01, code):
    Source.model_validate(dict(f01["sources"][0], language=code))


def test_d03_translated_search_text_must_be_traceable():
    """Ban dich chi de TIM, nhung van phai tai lap duoc."""
    with pytest.raises(ValidationError):
        SearchText(search_text_original="tighten the bolt", search_text_vi="siet bu long")

    ok = SearchText(
        search_text_original="tighten the bolt",
        search_text_vi="siet bu long",
        translation_model="demo-mt",
        translation_version="2026-09-01",
    )
    assert ok.search_text_vi == "siet bu long"


def test_d03_translation_metadata_without_translation_is_rejected():
    with pytest.raises(ValidationError):
        SearchText(search_text_original="x", translation_model="demo-mt", translation_version="1")


# --- D-05: dedup claim -------------------------------------------------------


def hit(wf: str, rev: int, claim: str, step: str, score: float) -> ClaimHit:
    return ClaimHit(workflow_id=wf, revision=rev, claim_id=claim, step_id=step, score=score)


def test_d05_same_claim_in_two_steps_appears_once():
    result = dedup_claim_hits([
        hit("WF_1", 1, "CL_001", "ST_001", 0.7),
        hit("WF_1", 1, "CL_001", "ST_002", 0.9),
    ])
    assert len(result) == 1
    assert result[0].matched_step_ids == ["ST_001", "ST_002"]


def test_d05_score_is_max_not_sum():
    """Lap lai o nhieu step khong lam claim dung hon."""
    result = dedup_claim_hits([
        hit("WF_1", 1, "CL_001", "ST_001", 0.4),
        hit("WF_1", 1, "CL_001", "ST_002", 0.4),
        hit("WF_1", 1, "CL_002", "ST_003", 0.6),
    ])
    assert [c.claim_id for c in result] == ["CL_002", "CL_001"]
    assert result[1].score == 0.4


def test_d05_same_claim_id_in_different_workflows_stays_separate():
    result = dedup_claim_hits([
        hit("WF_1", 1, "CL_001", "ST_001", 0.8),
        hit("WF_2", 1, "CL_001", "ST_001", 0.8),
    ])
    assert len(result) == 2


def test_d05_same_claim_id_across_revisions_stays_separate():
    result = dedup_claim_hits([
        hit("WF_1", 1, "CL_001", "ST_001", 0.8),
        hit("WF_1", 2, "CL_001", "ST_001", 0.8),
    ])
    assert len(result) == 2


def test_d05_identical_text_from_two_sources_is_not_merged():
    """Khong dedup theo noi dung: hai nguon doc lap phai giu rieng."""
    result = dedup_claim_hits([
        hit("WF_1", 1, "CL_001", "ST_001", 0.8),
        hit("WF_1", 1, "CL_002", "ST_001", 0.8),
    ])
    assert len(result) == 2


def test_d05_entity_ref_carries_revision():
    ref = dedup_claim_hits([hit("WF_1", 3, "CL_001", "ST_001", 0.5)])[0].entity_ref()
    assert (ref.workflow_id, ref.revision, ref.entity_type) == ("WF_1", 3, "claim")


# --- D-06: index hai tang ----------------------------------------------------


def test_d06_procedure_must_come_from_one_snapshot():
    same = dedup_claim_hits([
        hit("WF_1", 1, "CL_001", "ST_001", 0.9),
        hit("WF_1", 1, "CL_002", "ST_002", 0.8),
    ])
    assert procedure_workflow_key(same) == ("WF_1", 1)
    assert not spans_multiple_workflows(same)

    mixed = dedup_claim_hits([
        hit("WF_1", 1, "CL_001", "ST_001", 0.9),
        hit("WF_2", 1, "CL_001", "ST_001", 0.8),
    ])
    assert procedure_workflow_key(mixed) is None
    assert spans_multiple_workflows(mixed)


def test_d06_search_record_rejects_unknown_keys():
    """Tham so top-k la cau hinh retrieval, khong duoc nhet vao search record."""
    with pytest.raises(ValidationError):
        StepSearchRecord(
            workflow_id="WF_1", revision=1, source_type="real", dataset_split="dev",
            lifecycle="active", language="en", source_ids=[],
            metadata=SearchMetadata(
                manufacturer=None, machine_family=None, machine_model=None, subsystem=None,
                task_type=None, symptoms=[], alarm_codes=[], components=[],
            ),
            text=SearchText(search_text_original="x"),
            build=IndexBuild(
                index_build_id="b1", snapshot_hash="h1", embedding_model="m",
                embedding_version="1", text_template_version="1",
            ),
            step_id="ST_001", display_order=1, title="t", claim_ids=[], claim_review_flags=[],
            top_k=5,
        )
