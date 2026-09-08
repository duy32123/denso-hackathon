"""Tien ich dung chung cho contract tests."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "data" / "fixtures"


def read_bundle(bundle_dir: Path) -> dict:
    """Doc bundle thanh dict thuan de test co the boi ban co chu dich."""
    return {
        "manifest": json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8")),
        "sources": [json.loads(l) for l in (bundle_dir / "sources.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()],
        "workflows": [json.loads(l) for l in (bundle_dir / "workflows.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()],
    }


def write_bundle(target: Path, bundle: dict, *, fix_checksums: bool = True) -> Path:
    """Ghi bundle ra dia. fix_checksums=False de test truong hop checksum lech."""
    target.mkdir(parents=True, exist_ok=True)
    manifest = copy.deepcopy(bundle["manifest"])

    for name, key in (("sources.jsonl", "sources"), ("workflows.jsonl", "workflows")):
        text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in bundle[key])
        data = text.encode("utf-8")
        (target / name).write_bytes(data)
        if fix_checksums:
            for entry in manifest["files"]:
                if entry["path"] == name:
                    entry["sha256"] = hashlib.sha256(data).hexdigest()
                    entry["record_count"] = len(bundle[key])

    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


@pytest.fixture
def f01() -> dict:
    return read_bundle(FIXTURE_ROOT / "F01_complete")


@pytest.fixture
def f09() -> dict:
    return read_bundle(FIXTURE_ROOT / "F09_revision_update")


@pytest.fixture
def bundle_writer(tmp_path: Path):
    def _write(bundle: dict, *, fix_checksums: bool = True) -> Path:
        return write_bundle(tmp_path / "bundle", bundle, fix_checksums=fix_checksums)

    return _write
