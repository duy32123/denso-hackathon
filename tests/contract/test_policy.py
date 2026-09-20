"""D-01 (dan xuat support_status) va chinh sach truy xuat muc 7."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from knowflow_contracts import (
    answer_qualifier,
    claim_blockers,
    derive_support_status,
    is_assertable,
)
from knowflow_contracts.enums import QueryMode, SupportStatus
from knowflow_contracts.models import Claim, Workflow

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "data" / "fixtures"


def link(status: str) -> dict:
    return {"evidence_id": "EV", "support_status": status, "explanation": "x"}


@pytest.mark.parametrize(
    ("links", "conflict", "expected"),
    [
        ([], False, SupportStatus.INSUFFICIENT),
        ([link("supported")], False, SupportStatus.SUPPORTED),
        ([link("supported"), link("supported")], False, SupportStatus.SUPPORTED),
        ([link("supported"), link("insufficient")], False, SupportStatus.SUPPORTED),
        ([link("insufficient")], False, SupportStatus.INSUFFICIENT),
        ([link("contradicted")], False, SupportStatus.CONTRADICTED),
        ([link("supported"), link("contradicted")], False, SupportStatus.AMBIGUOUS),
        ([link("ambiguous")], False, SupportStatus.AMBIGUOUS),
        ([link("supported")], True, SupportStatus.AMBIGUOUS),
    ],
)
def test_derive_support_status(links, conflict, expected):
    assert derive_support_status(links, has_unresolved_conflict=conflict) == expected


def load_workflow(fixture: str, index: int = 0) -> Workflow:
    line = (FIXTURE_ROOT / fixture / "workflows.jsonl").read_text(encoding="utf-8").splitlines()[index]
    return Workflow.model_validate(json.loads(line))


def claim_of(wf: Workflow, claim_id: str) -> Claim:
    return next(c for c in wf.claims if c.claim_id == claim_id)


def test_synthetic_claims_are_never_assertable_in_real_mode():
    wf = load_workflow("F01_complete")
    for claim in wf.claims:
        blockers = claim_blockers(claim, wf, mode=QueryMode.REAL, is_latest_indexed_revision=True)
        assert "mode=real khong duoc doc corpus synthetic" in blockers


def test_synthetic_mode_allows_pending_review():
    wf = load_workflow("F01_complete")
    claim = claim_of(wf, "SYN_WF_0001_CL_003")
    assert is_assertable(claim, wf, mode=QueryMode.SYNTHETIC, is_latest_indexed_revision=True)


def test_conflicting_claims_are_blocked():
    wf = load_workflow("F06_conflict")
    claim = claim_of(wf, "SYN_WF_0007_CL_001")
    blockers = claim_blockers(claim, wf, mode=QueryMode.SYNTHETIC, is_latest_indexed_revision=True)
    assert "con conflict chua giai quyet" in blockers


def test_stale_revision_is_blocked():
    wf = load_workflow("F09_revision_update", index=0)
    claim = wf.claims[0]
    blockers = claim_blockers(claim, wf, mode=QueryMode.SYNTHETIC, is_latest_indexed_revision=False)
    assert "khong phai latest revision da index hoan chinh" in blockers


def test_unopenable_evidence_blocks_assertion():
    wf = load_workflow("F01_complete")
    claim = claim_of(wf, "SYN_WF_0001_CL_003")
    blockers = claim_blockers(
        claim, wf, mode=QueryMode.SYNTHETIC, is_latest_indexed_revision=True, evidence_openable=False
    )
    assert "evidence khong mo duoc" in blockers


def test_pending_claim_has_no_expert_qualifier():
    wf = load_workflow("F09_revision_update", index=1)
    claim = claim_of(wf, "SYN_WF_0010_CL_002")
    assert answer_qualifier(claim) is None, "phan hoi don thuan khong tao ra xac nhan chuyen mon"
