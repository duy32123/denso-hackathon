"""Bo cau hoi synthetic (ke hoach doi 2 muc 1.5): nhan co tu mau thuan khong.

Bo nay kiem TINH DUNG CUA NHAN, khong kiem chat luong retrieval. Gold phai tro
toi Step co that trong corpus dang phuc vu, va khong duoc tro vao claim da bi
rut, da bi thay the hay khong con khang dinh duoc.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import pytest

from retrieval.evaluation.harness import EvalQuestion

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "data" / "eval" / "synthetic_dev.qa.v0.jsonl"
KB = ROOT / "data" / "synthetic_samples" / "serving"
GENERATOR = ROOT / "scripts" / "build_synthetic_questions.py"


def fold(text: str) -> str:
    """Bo dau va chuan hoa de so cau hoi (co dau) voi claim (khong dau)."""
    stripped = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                       if unicodedata.category(c) != "Mn")
    return " ".join(stripped.replace("?", " ").replace(".", " ").replace(",", " ").split())


def rows() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines()]


def corpus() -> tuple[dict, dict]:
    """(Step dang phuc vu -> workflow, claim con khang dinh duoc theo Step)."""
    workflows = [json.loads(line) for line
                 in (KB / "workflows.jsonl").read_text(encoding="utf-8").splitlines()]
    latest: dict[str, int] = {}
    for wf in workflows:
        latest[wf["workflow_id"]] = max(latest.get(wf["workflow_id"], 0), wf["revision"])
    steps, assertable = {}, {}
    for wf in workflows:
        if wf["revision"] != latest[wf["workflow_id"]] or wf["lifecycle"] != "active":
            continue
        ok = {c["claim_id"] for c in wf["claims"]
              if c["support_status"] == "supported" and not c["conflicts_with"]}
        for step in wf["steps"]:
            key = (wf["workflow_id"], wf["revision"], step["step_id"])
            steps[key] = wf
            assertable[key] = {cid for ref in step["fields"].values()
                               for cid in ref["claim_ids"] if cid in ok}
    return steps, assertable


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["question_id"])
def test_every_question_validates(row: dict):
    EvalQuestion.model_validate(row)


def test_plan_size_and_namespace():
    data = rows()
    assert 100 <= len(data) <= 150, f"ke hoach muc 1.5 yeu cau 100-150 cau, dang co {len(data)}"
    assert all(r["source_type"] == "synthetic" and r["dataset_split"] == "dev" for r in data)
    assert len({r["question_id"] for r in data}) == len(data)
    # Cung mot cau hoi cho hai may khac nhau la hai ca hop le; trung ca cau hoi
    # lan model moi la trung that.
    pairs = [(r["question"], r["context"].get("machine_model")) for r in data]
    assert len(set(pairs)) == len(pairs), "co cau hoi trung ca noi dung lan model"


def test_nobody_has_reviewed_these_labels():
    """Nguoi soan khong duoc tu kiem nhan cua chinh minh (ke hoach muc 4)."""
    for row in rows():
        assert row["label"]["status"] == "draft"
        assert row["label"]["labeled_by"]
        assert not row["label"].get("reviewed_by")


def test_gold_points_at_servable_steps():
    steps, assertable = corpus()
    for row in rows():
        for unit in row["gold_units"]:
            for ref in unit:
                key = (ref["workflow_id"], ref["revision"], ref["step_id"])
                assert key in steps, f"{row['question_id']}: gold tro toi Step khong phuc vu {key}"
                if row["expected_status"] == "answered":
                    assert assertable[key], (
                        f"{row['question_id']}: gold tro toi Step khong con claim khang dinh duoc"
                    )
        for ref in row["gold_workflows"]:
            assert any(k[0] == ref["workflow_id"] and k[1] == ref["revision"] for k in steps), ref


def test_gold_respects_the_model_filter():
    """Cau hoi neu model thi gold khong duoc tro sang may khac."""
    steps, _ = corpus()
    for row in rows():
        model = row["context"].get("machine_model")
        if not model:
            continue
        for unit in row["gold_units"]:
            for ref in unit:
                wf = steps[(ref["workflow_id"], ref["revision"], ref["step_id"])]
                assert wf["context"]["machine_model"] in (model, None), (
                    f"{row['question_id']}: hoi {model} nhung gold o "
                    f"{wf['context']['machine_model']}"
                )


def test_questions_are_paraphrases_not_copies():
    """Ke hoach muc 1: cau hoi khong duoc chep nguyen van claim."""
    workflows = [json.loads(line) for line
                 in (KB / "workflows.jsonl").read_text(encoding="utf-8").splitlines()]
    claim_texts = {fold(c["text"]) for wf in workflows for c in wf["claims"]}
    for row in rows():
        asked = fold(row["question"])
        assert asked not in claim_texts
        assert not any(asked in text for text in claim_texts), row["question_id"]


def test_matrix_and_status_coverage():
    data = rows()
    categories = Counter(r["category"] for r in data)
    assert {"tra_loi_duoc", "thieu_evidence", "khong_co_dap_an", "nguon_mau_thuan",
            "thieu_boi_canh", "quy_trinh", "corpus_tieng_anh", "viet_hoi_anh",
            "model_khong_ro"} <= set(categories), categories

    statuses = Counter(r["expected_status"] for r in data)
    assert {"answered", "insufficient_evidence", "needs_clarification",
            "conflicting_sources"} <= set(statuses), statuses

    assert {"vi", "en"} <= {r["language"] for r in data}
    assert any(r["intent"] == "procedure" for r in data)
    # Cau tu choi / hoi lai khong duoc nam trong mau so Recall (ke hoach muc 4).
    scored = [r for r in data if r["expected_status"] == "answered" and r["intent"] == "detail"]
    assert all(r["gold_units"] for r in scored)
    assert 40 <= len(scored) <= len(data)


def test_refusals_carry_no_gold():
    for row in rows():
        if row["expected_retrieval_status"] != "retrieved":
            assert not row["gold_units"] and not row["gold_workflows"], row["question_id"]


def test_generator_is_reproducible(tmp_path: Path):
    out = tmp_path / "synthetic_dev.qa.v0.jsonl"
    env = {**os.environ, "KNOWFLOW_SYNTHETIC_QA_OUT": str(out)}
    subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, env=env, check=True,
                   capture_output=True)
    assert out.read_bytes() == QUESTIONS.read_bytes()
