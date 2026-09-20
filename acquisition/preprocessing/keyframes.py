"""Media inventory helpers shared by the compiler and the keyframe pipeline.

The compiler must never trust a keyframe's timestamp or identity from its filename
alone -- a file can be overwritten in place while keeping the same name. This module
is the single source of truth: every keyframe referenced by a draft is looked up by
its ``storage_uri`` in the media inventory and its bytes are re-hashed against the
recorded ``content_sha256`` before its ``original_start_ms`` is trusted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "acquisition" / "preprocessing" / "haas_d1a_media_inventory.jsonl"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inventory(path: Path = INVENTORY_PATH) -> dict[str, dict]:
    """Inventory rows keyed by storage_uri (a video row's trailing gitignore note,
    e.g. " (gitignored, not committed)", is stripped so the key is a bare path).
    """
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        uri = row["storage_uri"].split(" ")[0]
        rows[uri] = row
    return rows
