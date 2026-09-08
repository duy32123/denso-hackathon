"""Chay validator tren 10 contract fixture va doi chieu expected.json.

Day la bo test ma ca hai doi phai chay truoc moi lan doi hop dong.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowflow_contracts import validate_bundle

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "data" / "fixtures"

FIXTURE_DIRS = sorted(p for p in FIXTURE_ROOT.iterdir() if p.is_dir())


def test_fixture_set_is_complete():
    """Bo contract fixture toi thieu: 10 ca (muc 8 cua Schema chung)."""
    assert len(FIXTURE_DIRS) == 10, [p.name for p in FIXTURE_DIRS]


@pytest.mark.parametrize("bundle_dir", FIXTURE_DIRS, ids=lambda p: p.name)
def test_fixture_matches_expected(bundle_dir: Path):
    expected = json.loads((bundle_dir / "expected.json").read_text(encoding="utf-8"))["validator"]
    report = validate_bundle(bundle_dir)

    if expected["outcome"] == "accept":
        assert report.ok, "\n".join(str(i) for i in report.errors)
    else:
        assert not report.ok, "fixture negative nhung validator lai chap nhan"
        for code in expected["expected_error_codes"]:
            assert code in report.error_codes, (
                f"thieu ma {code}; thuc te {report.error_codes}\n"
                + "\n".join(str(i) for i in report.errors)
            )


@pytest.mark.parametrize("bundle_dir", FIXTURE_DIRS, ids=lambda p: p.name)
def test_expected_file_is_reviewable(bundle_dir: Path):
    """expected.json phai co nguoi chot y nghia, khong chi la output cua code."""
    expected = json.loads((bundle_dir / "expected.json").read_text(encoding="utf-8"))
    assert expected["fixture_id"] == bundle_dir.name
    assert expected["purpose"].strip()
    for case in expected.get("rag", []):
        assert case["expected_status"] in {
            "answered",
            "needs_clarification",
            "insufficient_evidence",
            "conflicting_sources",
        }


def test_no_synthetic_fixture_claims_expert_review():
    """Fixture luon source_review=pending / technical_review=not_requested."""
    for bundle_dir in FIXTURE_DIRS:
        for line in (bundle_dir / "workflows.jsonl").read_text(encoding="utf-8").splitlines():
            wf = json.loads(line)
            if wf["source_type"] != "synthetic":
                continue
            for claim in wf["claims"]:
                assert claim["source_review"] == "pending", (bundle_dir.name, claim["claim_id"])
                assert claim["technical_review"] == "not_requested", (bundle_dir.name, claim["claim_id"])
