"""Synthetic KB (ke hoach doi 2 muc 1.4): coverage, tinh tai lap va negative test.

Bo nay KHONG do chat luong he thong. No chi kiem rang du lieu mo phong dung hop
dong, phu du cac nhom cua ma tran, va sinh lai duoc nguyen ven tu seed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from knowflow_contracts import validate_bundle

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "data" / "synthetic_samples"
SERVING = KB / "serving"
NEGATIVE = KB / "negative"
GENERATOR = ROOT / "scripts" / "build_synthetic_kb.py"


def workflows() -> list[dict]:
    return [json.loads(line) for line in (SERVING / "workflows.jsonl").read_text(encoding="utf-8").splitlines()]


def test_serving_bundle_is_valid():
    report = validate_bundle(SERVING)
    assert report.ok, "\n".join(str(i) for i in report.errors)


def test_serving_manifest_is_synthetic_dev():
    manifest = json.loads((SERVING / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_type"] == "synthetic"
    assert manifest["dataset_split"] == "dev"
    assert manifest["producer"]["team"] == "team_2"


@pytest.mark.parametrize("bundle_dir", sorted(p for p in NEGATIVE.iterdir() if p.is_dir()),
                         ids=lambda p: p.name)
def test_negative_bundle_is_rejected(bundle_dir: Path):
    """Bundle co y sai phai bi tu choi dung ma loi da ghi trong expected.json."""
    expected = json.loads((bundle_dir / "expected.json").read_text(encoding="utf-8"))["validator"]
    assert expected["outcome"] == "reject"
    report = validate_bundle(bundle_dir)
    assert not report.ok, "bundle negative nhung validator lai chap nhan"
    for code in expected["expected_error_codes"]:
        assert code in report.error_codes, f"thieu ma {code}; thuc te {report.error_codes}"


def test_negative_bundles_stay_out_of_serving():
    """Ke hoach muc 1: fixture co y sai khong duoc nhap vao KB phuc vu."""
    serving_ids = {wf["workflow_id"] for wf in workflows()}
    for bundle_dir in NEGATIVE.iterdir():
        if not bundle_dir.is_dir():
            continue
        broken = {json.loads(line)["workflow_id"]
                  for line in (bundle_dir / "workflows.jsonl").read_text(encoding="utf-8").splitlines()}
        assert not (broken & serving_ids)


def test_plan_size_limits():
    wfs = workflows()
    ids = {wf["workflow_id"] for wf in wfs}
    assert 30 <= len(ids) <= 50, f"ke hoach yeu cau 30-50 workflow, dang co {len(ids)}"
    for wf in wfs:
        assert 5 <= len(wf["steps"]) <= 12, f"{wf['workflow_id']} co {len(wf['steps'])} buoc"


def test_review_flags_stay_pending():
    """V07 da chan, nhung giu them mot cong ro rang: synthetic khong tu nhan da kiem."""
    for wf in workflows():
        for claim in wf["claims"]:
            assert claim["source_review"] == "pending"
            assert claim["technical_review"] == "not_requested"
        assert wf["review_events"] == []


def test_coverage_matrix():
    """Sau nhom cua ma tran deu phai co mat: khong sinh toan workflow sach."""
    wfs = workflows()
    steps_missing = Counter(
        role for wf in wfs for step in wf["steps"] for role, ref in step["fields"].items()
        if ref["state"] == "missing"
    )
    assert steps_missing["rationale"] and steps_missing["condition"] and steps_missing["acceptance_criteria"]
    assert sum(len(wf["questions"]) for wf in wfs) >= 10

    models = {str(wf["context"]["machine_model"]) for wf in wfs}
    assert {"DEMO_TC_A", "DEMO_TC_B", "None"} <= models, models

    assert any(claim["conflicts_with"] for wf in wfs for claim in wf["claims"])
    assert any(wf["revision"] == 2 and wf["supersedes_revision"] == 1 for wf in wfs)
    assert any(wf["lifecycle"] == "withdrawn" for wf in wfs)
    assert any(claim["support_status"] == "insufficient" for wf in wfs for claim in wf["claims"])

    relation_types = {rel["relation_type"] for wf in wfs for rel in wf["relations"]}
    assert {"branch_if", "repeated_step", "observed_next"} <= relation_types, relation_types

    assert {"vi", "en"} <= {wf["language"] for wf in wfs}
    alarms = {code for wf in wfs for code in wf["context"]["alarm_codes"]}
    assert {"2066", "2067", "20.66"} <= alarms, "can cac ma alarm gan giong nhau de kiem khong gop"

    modalities = {ev["modality"] for wf in wfs for ev in wf["evidence"]}
    assert {"speech", "visual", "text"} <= modalities, modalities


def test_english_workflow_language_matches_its_sources():
    """D-03: Claim.text viet bang ngon ngu cua nguon, khong dich sang tieng Viet."""
    sources = {json.loads(line)["source_id"]: json.loads(line)
               for line in (SERVING / "sources.jsonl").read_text(encoding="utf-8").splitlines()}
    for wf in workflows():
        langs = {sources[sid]["language"] for sid in wf["source_ids"]}
        assert wf["language"] in langs


def test_generator_json_matches_the_bundle():
    meta = json.loads((KB / "generator.json").read_text(encoding="utf-8"))
    wfs = workflows()
    assert meta["seed"] and meta["generator_version"] and meta["template_version"]
    assert meta["serving"]["workflow_records"] == len(wfs)
    assert meta["serving"]["workflow_ids"] == len({wf["workflow_id"] for wf in wfs})
    assert meta["serving"]["steps_total"] == sum(len(wf["steps"]) for wf in wfs)


def test_generator_is_reproducible(tmp_path: Path):
    """Cung seed phai cho ra dung tung byte: bundle la du lieu tai lap duoc."""
    env = {**os.environ, "KNOWFLOW_SYNTHETIC_OUT": str(tmp_path)}
    subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, env=env, check=True,
                   capture_output=True)
    for name in ("serving/manifest.json", "serving/sources.jsonl", "serving/workflows.jsonl"):
        assert (tmp_path / name).read_bytes() == (KB / name).read_bytes(), name
