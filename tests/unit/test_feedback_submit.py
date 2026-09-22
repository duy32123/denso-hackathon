"""D1-B / WP6: loi goi `submit` cua service ghi phan hoi.

Chay tren mot **ban sao** kho chuan trong thu muc tam: test phai kiem duoc duong
ghi that ma khong duoc sua repo. `test_submit_writes_nothing_into_the_real_repo`
kiem lai chinh dieu do.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from acquisition.export.exporter import SPLITS
from acquisition.extraction import feedback_service as fs
from acquisition.extraction.feedback_service import (
    FeedbackBusy,
    FeedbackConflict,
    FeedbackRejected,
    preview,
    submit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

ASKED = {
    "mode": "real",
    "dataset_split": "dev",
    "workflow_id": "REAL_WF_0001",
    "base_revision": 1,
    "confirm_base_revision": 1,
    "step_id": "REAL_WF_0001_ST_001",
    "target_field": "rationale",
    "question_id": "REAL_WF_0001_Q_001",
    "answer_text": "Main air is disconnected so the carousel cannot index while hands are inside.",
    "responder": {"actor_id": "dpv137", "label": "Pham Vu Dang", "role": "ky thuat vien bao tri"},
    "language": "en",
}


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Ban sao day du cua kho chuan dev, tro moi duong dan sang thu muc tam."""
    root = tmp_path / "repo"
    (root / "data" / "workflows").mkdir(parents=True)
    (root / "data" / "sources").mkdir(parents=True)

    shutil.copytree(REPO_ROOT / "data/workflows/dev", root / "data/workflows/dev")
    shutil.copytree(REPO_ROOT / "data/workflows/drafts", root / "data/workflows/drafts")
    shutil.copyfile(
        REPO_ROOT / "data/sources/haas_pilot_sources.jsonl",
        root / "data/sources/haas_pilot_sources.jsonl",
    )
    out = root / "acquisition/export/haas_pilot_dev_bundle"
    shutil.copytree(REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle", out)

    monkeypatch.setitem(SPLITS["dev"], "sources", root / "data/sources/haas_pilot_sources.jsonl")
    monkeypatch.setitem(SPLITS["dev"], "snapshots", root / "data/workflows/dev")
    monkeypatch.setitem(SPLITS["dev"], "out", out)
    monkeypatch.setattr(fs, "REPO_ROOT", root)
    return root


def _request(**overrides) -> dict:
    return {**ASKED, **overrides}


# --- duong ghi thanh cong ------------------------------------------------------


def test_submit_writes_the_new_revision(store):
    result = submit(_request())

    assert result["workflow_id"] == "REAL_WF_0001"
    assert result["revision"] == 2
    assert result["supersedes_revision"] == 1
    assert len(result["created_claim_ids"]) == 1
    assert len(result["created_evidence_ids"]) == 1

    snapshot = json.loads((store / result["snapshot_path"]).read_text(encoding="utf-8"))
    assert snapshot["revision"] == 2
    assert snapshot["supersedes_revision"] == 1


def test_submit_writes_all_four_artifacts(store):
    """Snapshot, Source, tep nguyen van va bundle -- thieu mot cai la citation hong."""
    result = submit(_request())

    # 1. snapshot
    assert (store / result["snapshot_path"]).is_file()
    # 2. source trong catalog
    sources = [
        json.loads(line)
        for line in (store / "data/sources/haas_pilot_sources.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(s["source_id"] == result["created_source_id"] for s in sources)
    # 3. tep nguyen van ma asset_uri tro toi
    asset = store / result["asset_path"]
    assert asset.is_file()
    assert json.loads(asset.read_text(encoding="utf-8"))["raw_text"] == ASKED["answer_text"]
    # 4. bundle da xuat lai, co ban ghi r2
    workflows = (store / result["bundle_export"] / "workflows.jsonl").read_text(encoding="utf-8")
    assert any(
        json.loads(line)["revision"] == 2
        for line in workflows.splitlines()
        if line.strip() and json.loads(line)["workflow_id"] == "REAL_WF_0001"
    )


def test_submitted_claim_still_needs_a_human_source_review(store):
    """Phan hoi lam tri thuc DAY them, khong lam no DUNG them."""
    result = submit(_request())

    snapshot = json.loads((store / result["snapshot_path"]).read_text(encoding="utf-8"))
    claim = next(c for c in snapshot["claims"] if c["claim_id"] == result["created_claim_ids"][0])
    assert claim["source_review"] == "pending"
    assert claim["technical_review"] == "not_requested"
    assert result["review_required"] is True
    assert result["responder_authenticated"] is False


def test_submit_answers_the_open_question(store):
    result = submit(_request())

    snapshot = json.loads((store / result["snapshot_path"]).read_text(encoding="utf-8"))
    question = next(q for q in snapshot["questions"] if q["question_id"] == "REAL_WF_0001_Q_001")
    assert question["status"] == "answered"
    assert result["created_source_id"] in question["answer_source_ids"]


def test_r1_is_left_untouched(store):
    """Revision cu bat bien: citation da phat hanh van mo dung noi dung cu."""
    before = (store / "data/workflows/dev/REAL_WF_0001.r1.json").read_bytes()
    submit(_request())
    assert (store / "data/workflows/dev/REAL_WF_0001.r1.json").read_bytes() == before


def test_preview_then_submit_agree(store):
    """Nguoi dung ky vao ban preview nao thi nhan dung ban do."""
    asked = _request()
    seen = preview({k: v for k, v in asked.items() if k != "confirm_base_revision"})
    written = submit(asked)

    assert written["revision"] == seen["next_revision"]
    assert written["created_source_id"] == seen["source"]["source_id"]
    assert written["created_claim_ids"] == [c["claim_id"] for c in seen["new_claims"]]
    assert written["created_evidence_ids"] == [e["evidence_id"] for e in seen["new_evidence"]]


# --- khong ghi de, khong ghi nua voi -------------------------------------------


def test_second_submit_on_a_stale_base_is_a_conflict(store):
    """Gui lai ban cu sau khi da co r2: 409, khong ghi de r2."""
    submit(_request())
    r2_bytes = (store / "data/workflows/dev/REAL_WF_0001.r2.json").read_bytes()

    with pytest.raises(FeedbackConflict) as exc:
        submit(_request(answer_text="Mot cau tra loi khac han."))

    assert exc.value.conflict["latest_revision"] == 2
    assert (store / "data/workflows/dev/REAL_WF_0001.r2.json").read_bytes() == r2_bytes


def test_confirm_base_revision_must_match(store):
    with pytest.raises(FeedbackRejected):
        submit(_request(confirm_base_revision=2))
    assert not (store / "data/workflows/dev/REAL_WF_0001.r2.json").exists()


def test_a_held_lock_makes_submit_busy(store, monkeypatch):
    """Hai lan ghi dong thoi: lan sau doi roi bao ban, khong ghi de."""
    monkeypatch.setattr(fs, "LOCK_TIMEOUT_S", 0.1)
    lock = SPLITS["dev"]["snapshots"].parent / ".feedback.dev.lock"
    lock.write_text("held by another process\n", encoding="utf-8")
    try:
        with pytest.raises(FeedbackBusy):
            submit(_request())
    finally:
        lock.unlink()

    assert not (store / "data/workflows/dev/REAL_WF_0001.r2.json").exists()


def test_failed_export_rolls_everything_back(store, monkeypatch):
    """Hong o buoc cuoi thi khong de lai gi: khong snapshot, khong source, khong asset."""
    before_sources = (store / "data/sources/haas_pilot_sources.jsonl").read_bytes()
    before_bundle = (store / "acquisition/export/haas_pilot_dev_bundle/workflows.jsonl").read_bytes()

    def boom(**kwargs):
        raise RuntimeError("đĩa đầy")

    monkeypatch.setattr(fs, "export_bundle", boom)

    with pytest.raises(RuntimeError):
        submit(_request())

    assert not (store / "data/workflows/dev/REAL_WF_0001.r2.json").exists()
    assert (store / "data/sources/haas_pilot_sources.jsonl").read_bytes() == before_sources
    assert (store / "acquisition/export/haas_pilot_dev_bundle/workflows.jsonl").read_bytes() == before_bundle
    assert not (store / "acquisition/feedback").exists() or not list(
        (store / "acquisition/feedback").glob("*.json")
    )


def test_lock_is_released_after_a_failure(store):
    """Khoa phai nha ca khi hong, neu khong mot loi la khoa chet ca service."""
    real_export = fs.export_bundle

    def boom(**kwargs):
        raise RuntimeError("đĩa đầy")

    # Khong dung `monkeypatch.undo()`: no go ca patch cua fixture `store`, va lan
    # `submit` sau do se ghi thang vao repo that.
    fs.export_bundle = boom
    try:
        with pytest.raises(RuntimeError):
            submit(_request())
    finally:
        fs.export_bundle = real_export

    assert not (SPLITS["dev"]["snapshots"].parent / ".feedback.dev.lock").exists()
    # Khoa da nha thi lan sau ghi duoc binh thuong.
    assert submit(_request())["revision"] == 2


def test_invalid_bundle_creates_no_revision(store, monkeypatch):
    """Validator chan truoc khi ghi: khong co revision nao duoc tao."""
    from knowflow_contracts.issues import Report

    def failing(plan, split="dev", repo_root=None):
        report = Report(bundle_path="<preview>")
        report.error("V07", "claims[X]", "co tinh lam hong de kiem duong tu choi")
        return report

    monkeypatch.setattr(fs, "dry_validate", failing)

    with pytest.raises(FeedbackRejected) as exc:
        submit(_request())

    assert exc.value.http_status == 422
    assert any("V07" in e for e in exc.value.errors)
    assert not (store / "data/workflows/dev/REAL_WF_0001.r2.json").exists()


# --- rang buoc quan trong nhat -------------------------------------------------


def test_submit_writes_nothing_into_the_real_repo(store):
    """Bo test nay ghi that, nhung khong duoc cham vao repo."""
    watched = [
        REPO_ROOT / "data" / "workflows",
        REPO_ROOT / "data" / "sources",
        REPO_ROOT / "acquisition" / "export" / "haas_pilot_dev_bundle",
        REPO_ROOT / "acquisition" / "feedback",
    ]

    def fingerprint():
        prints = {}
        for root in watched:
            if not root.exists():
                prints[str(root)] = "<absent>"
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    prints[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return prints

    before = fingerprint()
    submit(_request())
    assert fingerprint() == before
