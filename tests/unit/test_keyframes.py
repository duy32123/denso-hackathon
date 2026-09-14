"""Tests for acquisition/preprocessing/keyframes.py: the media-inventory helpers the
compiler now trusts instead of a keyframe filename (see compile_workflow._keyframe_evidence).
"""
from __future__ import annotations

import json

import pytest

from acquisition.preprocessing import keyframes as kf


def test_load_inventory_keys_rows_by_bare_storage_uri(tmp_path):
    """A video row's storage_uri carries a trailing gitignore note the loader must strip
    so the key matches the plain relative path a draft's ``keyframe`` ref uses.
    """
    inv = tmp_path / "inv.jsonl"
    inv.write_text(
        json.dumps({"storage_uri": "data/media/x.mp4 (gitignored, not committed)", "content_sha256": "a" * 64})
        + "\n"
        + json.dumps({"storage_uri": "acquisition/preprocessing/keyframes/X/kf_0001000.jpg", "content_sha256": "b" * 64})
        + "\n",
        encoding="utf-8",
    )
    rows = kf.load_inventory(inv)
    assert set(rows) == {"data/media/x.mp4", "acquisition/preprocessing/keyframes/X/kf_0001000.jpg"}


def test_load_inventory_skips_blank_lines(tmp_path):
    inv = tmp_path / "inv.jsonl"
    inv.write_text('\n{"storage_uri": "a.jpg", "content_sha256": "c" * 64}\n\n'.replace('"c" * 64', '"' + "c" * 64 + '"'), encoding="utf-8")
    rows = kf.load_inventory(inv)
    assert list(rows) == ["a.jpg"]


def test_sha256_of_matches_hashlib(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    import hashlib
    assert kf.sha256_of(f) == hashlib.sha256(b"hello world").hexdigest()


def test_real_inventory_loads_and_every_committed_keyframe_hash_matches_its_file():
    """Guards the exact defect this hardening pass fixes: a keyframe file silently
    overwritten while its recorded hash stays stale would be caught here.
    """
    rows = kf.load_inventory()
    keyframe_rows = {uri: row for uri, row in rows.items() if row["artifact_type"] == "keyframe"}
    assert keyframe_rows, "expected at least one committed keyframe row"
    for uri, row in keyframe_rows.items():
        path = kf.REPO_ROOT / uri
        assert path.is_file(), f"{uri}: inventory row exists but file is missing"
        assert kf.sha256_of(path) == row["content_sha256"], f"{uri}: file bytes do not match recorded content_sha256"


@pytest.mark.parametrize("holdout_source_id", ["SRC_HAAS_0006", "SRC_HAAS_0007"])
def test_no_holdout_source_appears_in_the_keyframe_inventory(holdout_source_id):
    rows = kf.load_inventory()
    assert not any(row.get("source_id") == holdout_source_id for row in rows.values())
