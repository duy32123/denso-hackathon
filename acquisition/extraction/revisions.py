"""Evidence-only revisions: pin the base snapshot and never recycle evidence IDs.

This is deliberately NOT a general workflow merge. Changed/reordered steps or
claims require an explicit identity migration; positional IDs must not silently
change meaning. Compilation always produces fresh, unreviewed claims.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from pydantic import ValidationError

from knowflow_contracts.models import ChangeEvent, Workflow
from knowflow_contracts.snapshot import snapshot_content_hash


class RevisionError(ValueError):
    pass


def load_base(draft: dict, repo_root: Path) -> dict | None:
    revision = draft.get("revision")
    if type(revision) is not int or revision < 1:
        raise RevisionError("revision must be a positive integer")
    ref = draft.get("revision_base")
    if revision == 1:
        if ref is not None:
            raise RevisionError("revision 1 cannot have revision_base")
        return None
    if not isinstance(ref, dict) or set(ref) != {"path", "snapshot_sha256"}:
        raise RevisionError("revision > 1 requires revision_base with path and snapshot_sha256")
    if not isinstance(ref["path"], str) or not ref["path"]:
        raise RevisionError("revision_base.path must be a repo-relative snapshot path")
    if not isinstance(ref["snapshot_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", ref["snapshot_sha256"]):
        raise RevisionError("revision_base.snapshot_sha256 must be a canonical snapshot hash")
    root = repo_root.resolve()
    relative = Path(ref["path"])
    if relative.is_absolute() or ":" in ref["path"] or ref["path"].startswith(("/", "\\")):
        raise RevisionError("revision_base.path must be repo-relative")
    try:
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise RevisionError("revision_base.path escapes the repo")
        base = Workflow.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        if isinstance(exc, RevisionError):
            raise
        raise RevisionError("Cannot read a valid revision_base snapshot") from None
    if snapshot_content_hash(base) != ref["snapshot_sha256"]:
        raise RevisionError("revision_base snapshot hash mismatch; do not silently rebase a review draft")
    if (base.workflow_id != draft["workflow_id"] or base.dataset_split != draft["dataset_split"]
            or base.source_type != draft.get("source_type", "real") or base.lifecycle != "active"):
        raise RevisionError("revision_base workflow/corpus/split/lifecycle mismatch")
    if revision != base.revision + 1 or draft.get("supersedes_revision") != base.revision:
        raise RevisionError("revision must be base revision + 1, with matching supersedes_revision")
    return base.model_dump(mode="json")


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def legacy_replay_base(snapshot: dict, repo_root: Path) -> dict:
    """Replay an existing pre-revision_base draft byte-for-content, not edit it.

    REAL_WF_0001.r2 predates the pinned-base format. Keep it reproducible without
    migrating somebody else's review draft. Any content change must use an
    explicit revision_base; an existing filename alone is not a bypass.
    """
    message = ("revision > 1 requires revision_base with path and snapshot_sha256; "
               "legacy replay only permits the exact existing compiled snapshot")
    wf_id, split = snapshot["workflow_id"], snapshot["dataset_split"]
    if not all(re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in (wf_id, split)):
        raise RevisionError(message)
    root = repo_root.resolve() / "data/workflows"
    archived = root / "drafts" / f"{wf_id}.r{snapshot['revision']}.json"
    previous_revision = snapshot.get("supersedes_revision")
    if type(previous_revision) is not int or previous_revision != snapshot["revision"] - 1:
        raise RevisionError(message)
    previous = root / split / f"{wf_id}.r{previous_revision}.json"
    if not previous.is_file():
        previous = root / "drafts" / previous.name
    try:
        stored = Workflow.model_validate_json(archived.read_text(encoding="utf-8"))
        compiled = Workflow.model_validate(snapshot)
        base = Workflow.model_validate_json(previous.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RevisionError(message) from None
    if snapshot_content_hash(stored) != snapshot_content_hash(compiled):
        raise RevisionError(message)
    if (base.workflow_id, base.dataset_split, base.source_type, base.revision) != (
            wf_id, split, compiled.source_type, previous_revision):
        raise RevisionError("Legacy replay base namespace/revision mismatch")
    # Reproducibility is not approval: the shared base + candidate validator
    # still checks old evidence payloads before CLI writes or promotion.
    return base.model_dump(mode="json")


def _evidence_content(evidence: dict) -> str:
    return _canonical({key: value for key, value in evidence.items() if key != "evidence_id"})


def _claim_identity(claim: dict) -> dict:
    # Evidence and review may change; the actual claim and all structural IDs may not.
    excluded = {"evidence_links", "support_status", "source_review", "technical_review"}
    return {key: value for key, value in claim.items() if key not in excluded}


def preserve_evidence_ids(snapshot: dict, base: dict) -> dict:
    stable_fields = ("workflow_id", "source_type", "dataset_split", "title", "language", "lifecycle",
                     "source_ids", "context", "steps", "relations", "questions")
    for key in stable_fields:
        if snapshot[key] != base[key]:
            raise RevisionError(f"Evidence-only revision cannot change {key}; explicit identity migration required")
    if [_claim_identity(c) for c in snapshot["claims"]] != [_claim_identity(c) for c in base["claims"]]:
        raise RevisionError("Evidence-only revision cannot add/remove/reorder/reword claims; explicit identity migration required")
    changes = snapshot["change_log"]
    if (len(changes) != len(base["change_log"]) + 1 or changes[:-1] != base["change_log"]):
        raise RevisionError("Preserve base change_log and append exactly one change event")
    try:
        event = ChangeEvent.model_validate(changes[-1]).model_dump(mode="json")
    except ValidationError:
        raise RevisionError("Revision needs a valid change event with actor, time and reason") from None
    if event["previous_revision"] != base["revision"] or not event["reason"].strip():
        raise RevisionError("Change event must explain the change from the base revision")

    # Keep the complete previous evidence inventory, including now-unused entries.
    # This reserves retired IDs across r2 -> r3 too, with no hidden state/DB needed.
    result = copy.deepcopy(snapshot)
    inventory = copy.deepcopy(base["evidence"])
    old_ids = [ev["evidence_id"] for ev in inventory]
    if len(set(old_ids)) != len(old_ids):
        raise RevisionError("revision_base contains duplicate evidence IDs")
    by_content = {}
    for ev in inventory:
        content = _evidence_content(ev)
        if content in by_content:
            raise RevisionError("Ambiguous duplicate evidence content in revision_base")
        by_content[content] = ev["evidence_id"]
    pattern = re.compile(re.escape(base["workflow_id"]) + r"_EV_(\d+)$")
    counter = max((int(match[1]) for eid in old_ids if (match := pattern.fullmatch(eid))), default=0)
    remap = {}
    for ev in result["evidence"]:
        original_id = ev["evidence_id"]
        if any(parent not in remap for parent in ev["parent_evidence_ids"]):
            raise RevisionError("Evidence parents must be compiled before their children")
        ev["parent_evidence_ids"] = [remap[parent] for parent in ev["parent_evidence_ids"]]
        content = _evidence_content(ev)
        if content in by_content:
            eid = by_content[content]
        else:
            counter += 1
            eid = f"{base['workflow_id']}_EV_{counter:03d}"
            ev["evidence_id"] = eid
            inventory.append(ev)
            by_content[content] = eid
        remap[original_id] = eid
    result["evidence"] = inventory

    replacements: dict[str, set[str]] = {}
    for claim, old_claim in zip(result["claims"], base["claims"], strict=True):
        for link in claim["evidence_links"]:
            link["evidence_id"] = remap[link["evidence_id"]]
        old = {link["evidence_id"] for link in old_claim["evidence_links"]}
        new = {link["evidence_id"] for link in claim["evidence_links"]}
        for eid in old - new:
            replacements.setdefault(eid, set()).update(new - old)
        # Reviews are never carried from the base, even for unchanged claims.
        claim["source_review"] = "pending"
        claim["technical_review"] = "not_requested"
    mappings = [{"old_id": eid, "new_ids": sorted(ids)} for eid, ids in sorted(replacements.items())]
    if event["id_mapping"] and event["id_mapping"] != mappings:
        raise RevisionError("Declared id_mapping differs from compiled evidence changes")
    event["id_mapping"] = mappings
    result["change_log"] = copy.deepcopy(base["change_log"]) + [event]
    result["review_events"] = []
    return result
