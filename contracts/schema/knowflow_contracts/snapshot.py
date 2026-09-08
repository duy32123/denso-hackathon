"""Hash noi dung snapshot: co so cho quy tac import lai (V09).

Import lai cung khoa (workflow_id, revision) va cung noi dung = no-op.
Cung khoa nhung khac noi dung = loi, khong overwrite. Importer cua doi 2 luu
hash nay canh (workflow_id, revision) de phan biet hai truong hop.
"""

from __future__ import annotations

import hashlib
import json

from .models import Workflow


def snapshot_content_hash(workflow: Workflow) -> str:
    payload = workflow.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReimportDecision(str):
    """Ket qua so sanh voi kho: 'new' | 'noop' | 'conflict'."""


def decide_reimport(existing_hash: str | None, incoming: Workflow) -> str:
    if existing_hash is None:
        return "new"
    return "noop" if existing_hash == snapshot_content_hash(incoming) else "conflict"
