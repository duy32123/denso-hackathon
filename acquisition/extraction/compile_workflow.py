"""Compile a workflow *draft* into a Schema 1.0.0 snapshot.

A draft says what the source supports, never how it is identified:

- claims point at evidence-pool candidate IDs (``SRC_HAAS_0005:U0012``) or at a
  keyframe, not at invented timestamps;
- the compiler, not the author, issues every nested ID (``_ST_``, ``_CL_``,
  ``_EV_``, ``_RL_``, ``_Q_``), builds Evidence from the pool, derives each
  claim's ``support_status`` with the shared D-01 rule and sets review states to
  pending / not_requested (only a human ReviewEvent may change them).

The same draft format is the target output of the B0 baseline, so manual and
model extraction are compiled, validated and compared the same way.

New evidence-only revisions pin a prior snapshot with ``revision_base`` and
preserve published evidence IDs. Changed steps/claims need a separate identity
migration. See ``docs/b0_wf0005_r2_review.md`` for the draft fields and review flow.

Draft shape (JSON)::

    {
      "workflow_id": "REAL_WF_0001", "revision": 1, "dataset_split": "dev",
      "title": "...", "language": "en", "created_at": "...Z",
      "source_ids": ["SRC_HAAS_0005"],
      "attribution": {"label": "Orville", "kind": "speaker"},     # default for claims
      "scope": "Pocket replacement shown in SRC_HAAS_0005",       # default claim scope
      "context": {"manufacturer": "...", ..., "provenance": {"manufacturer": {"basis": "source", "note": "..."}}},
      "steps": [
        {"title": "...",
         "fields": {"action": [CLAIM, ...], "outcome": {"state": "ambiguous", "claims": [CLAIM, ...]}},
         "questions": [{"target_field": "rationale", "reason": "missing", "question": "..."}]}
      ],
      "relations": [{"type": "requires", "from_step": 4, "to_step": 5, "claim": CLAIM}]
    }

    CLAIM = {"text": "...", "evidence_type": "stated",
             "evidence": [["SRC_HAAS_0005:U0003", "SRC_HAAS_0005:U0004"],
                          {"keyframe": "acquisition/.../kf_0142700.jpg", "source_id": "...",
                           "start_ms": 142680, "end_ms": 147840, "observation_note": "..."}],
             "explanation": "...", "attribution": {...}?, "scope": "..."?, "key": "..."?}

Fields not listed in a step are ``missing``. Usage::

    python -m acquisition.extraction.compile_workflow acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from knowflow_contracts import derive_support_status
from knowflow_contracts.enums import FIELD_ROLES

from acquisition.export import exporter
from acquisition.extraction import evidence_pool as ep
from acquisition.extraction import revisions
from acquisition.preprocessing import keyframes as kf

REPO_ROOT = Path(__file__).resolve().parents[2]
DRAFT_OUT = REPO_ROOT / "data" / "workflows" / "drafts"

_METADATA_KEYS = (
    "manufacturer", "machine_family", "machine_model", "subsystem", "task_type",
    "symptoms", "alarm_codes", "components",
)
_LIST_KEYS = {"symptoms", "alarm_codes", "components"}


class DraftError(ValueError):
    """The draft cannot become a correct snapshot."""


class _Compiler:
    def __init__(self, draft: dict, pool: dict[str, ep.Candidate]):
        self.draft = draft
        self.pool = pool
        self.wf_id = draft["workflow_id"]
        self.claims: list[dict] = []
        self.evidence: list[dict] = []
        self._evidence_ids: dict[tuple, str] = {}
        self._claim_keys: dict[str, dict] = {}
        # Loaded once (not per keyframe reference) and resolved against this module's
        # REPO_ROOT -- not keyframes.py's own default -- so a test (or a caller) that
        # points REPO_ROOT elsewhere gets a fully isolated inventory, never a silent
        # fallback to the real committed one.
        self._media_inventory = kf.load_inventory(REPO_ROOT / "acquisition" / "preprocessing" / "haas_d1a_media_inventory.jsonl")

    # --- ids -------------------------------------------------------------------

    def _nested(self, tag: str, n: int) -> str:
        return f"{self.wf_id}_{tag}_{n:03d}"

    # --- evidence ----------------------------------------------------------------

    def _evidence_for(self, ref) -> str:
        if isinstance(ref, list):
            return self._span_evidence(ref)
        if isinstance(ref, dict) and "keyframe" in ref:
            return self._keyframe_evidence(ref)
        raise DraftError(f"unknown evidence reference: {ref!r}")

    def _span_evidence(self, candidate_ids: list[str]) -> str:
        missing = [cid for cid in candidate_ids if cid not in self.pool]
        if missing:
            raise DraftError(f"unknown evidence-pool candidate(s): {', '.join(missing)}")
        sp = ep.span([self.pool[cid] for cid in candidate_ids])
        key = ("span", sp.candidate_ids)
        if key in self._evidence_ids:
            return self._evidence_ids[key]

        parents: tuple[str, ...] = ()
        raw = ep.raw_parent(sp, self.pool)
        if raw is not None:
            parents = (self._span_evidence(list(raw.candidate_ids)),)

        eid = self._nested("EV", len(self.evidence) + 1)
        self.evidence.append(ep.to_evidence(sp, eid, parent_evidence_ids=parents))
        self._evidence_ids[key] = eid
        return eid

    def _keyframe_evidence(self, ref: dict) -> str:
        path = REPO_ROOT / ref["keyframe"]
        if not path.is_file():
            raise DraftError(f"keyframe not found: {ref['keyframe']}")

        # Never trust the filename for identity or timestamp -- a file can be
        # overwritten in place while keeping its name. The media inventory,
        # verified by content hash, is the only source of truth for both.
        uri = Path(ref["keyframe"]).as_posix()
        row = self._media_inventory.get(uri)
        if row is None:
            raise DraftError(
                f"{path.name}: not recorded in the media inventory (no lineage) -- add a row to "
                "acquisition/preprocessing/haas_d1a_media_inventory.jsonl for this exact file "
                "(storage_uri, content_sha256, original_start_ms) before citing it as evidence"
            )
        actual_hash = kf.sha256_of(path)
        if actual_hash != row["content_sha256"]:
            raise DraftError(
                f"{path.name}: file content does not match its inventory content_sha256 "
                f"(got {actual_hash[:12]}, inventory says {row['content_sha256'][:12]}) -- "
                "possible silent overwrite; add a new artifact file + inventory row instead of "
                "replacing this file's bytes in place"
            )
        frame_ms = row["original_start_ms"]
        if not ref["start_ms"] <= frame_ms < ref["end_ms"]:
            raise DraftError(f"{path.name}: frame at {frame_ms} ms is outside [{ref['start_ms']}, {ref['end_ms']})")
        if not ref.get("observation_note"):
            raise DraftError(f"{path.name}: visual evidence needs an observation_note describing only what is visible")

        key = ("keyframe", uri, frame_ms)  # normalized path -- two spellings of the same file must dedupe
        if key in self._evidence_ids:
            return self._evidence_ids[key]
        pinned = ref.get("evidence_id")
        if pinned is not None:
            if pinned in {ev["evidence_id"] for ev in self.evidence}:
                raise DraftError(f"evidence_id already used in this compile: {pinned}")
            eid = pinned
        else:
            eid = self._nested("EV", len(self.evidence) + 1)
        self.evidence.append({
            "evidence_id": eid,
            "source_id": ref["source_id"],
            "modality": "visual",
            # A still frame is an instant, not the transcript-derived search window
            # (ref start_ms/end_ms) it was found within. V04 requires start_ms < end_ms
            # AND end_ms <= the source's duration_ms; ending the window *at* frame_ms
            # (rather than starting there) means end_ms can only exceed duration_ms if
            # frame_ms itself genuinely does -- a real error, not a boundary artifact.
            "locator": {"start_ms": max(0, frame_ms - 1), "end_ms": frame_ms if frame_ms > 0 else 1,
                        "page": None, "text_span": None},
            "quote": None,
            "observation_note": ref["observation_note"],
            "asset_uri": ref["keyframe"],
            "transcript_origin": "none",
            "parent_evidence_ids": [],
        })
        self._evidence_ids[key] = eid
        return eid

    # --- claims ------------------------------------------------------------------

    def _claim(self, spec: dict, role: str) -> str:
        if not spec.get("text"):
            raise DraftError(f"claim without text in role {role}")
        evidence_type = spec.get("evidence_type", "stated")
        if evidence_type != "inferred" and not spec.get("evidence"):
            raise DraftError(f"{evidence_type} claim needs evidence: {spec['text'][:60]}")

        links = []
        for ref in spec.get("evidence", []):
            explanation = spec.get("explanation")
            if isinstance(ref, dict) and ref.get("explanation"):
                explanation = ref["explanation"]
            if not explanation:
                raise DraftError(f"evidence link without explanation: {spec['text'][:60]}")
            links.append({"evidence_id": self._evidence_for(ref), "support_status": "supported", "explanation": explanation})

        cid = self._nested("CL", len(self.claims) + 1)
        attribution = {"actor_id": None, **self.draft.get("attribution", {}), **spec.get("attribution", {})}
        if evidence_type == "inferred":
            attribution["kind"] = "model"

        derived_status = derive_support_status(links).value if links else "insufficient"
        if evidence_type == "inferred" and derived_status == "supported":
            derived_status = "ambiguous"

        claim = {
            "claim_id": cid,
            "text": spec["text"],
            "role": role,
            "evidence_type": evidence_type,
            "attribution": {"actor_id": attribution.get("actor_id"), "label": attribution.get("label"), "kind": attribution["kind"]},
            "scope": {"level": "case", "description": spec.get("scope", self.draft["scope"])},
            "evidence_links": links,
            "support_status": derived_status,
            "source_review": "pending",
            "technical_review": "not_requested",
            "conflicts_with": [],
            "supersedes_claim_ids": [],
        }
        self.claims.append(claim)
        if spec.get("key"):
            self._claim_keys[spec["key"]] = claim
        return cid

    # --- structure ---------------------------------------------------------------

    def _fields(self, step: dict) -> dict:
        unknown = set(step.get("fields", {})) - set(FIELD_ROLES)
        if unknown:
            raise DraftError(f"step '{step['title']}': unknown field(s) {sorted(unknown)}")
        fields = {}
        for role in FIELD_ROLES:
            value = step.get("fields", {}).get(role, "missing")
            if value == "missing":
                fields[role] = {"state": "missing", "claim_ids": []}
            else:
                state = "present" if isinstance(value, list) else value["state"]
                specs = value if isinstance(value, list) else value["claims"]
                claim_ids = []
                for n, spec in enumerate(specs, 1):
                    try:
                        claim_ids.append(self._claim(spec, role))
                    except (DraftError, ep.PoolError) as exc:
                        raise DraftError(
                            f"step {step['title']!r}, field {role}, claim {n} "
                            f"({spec.get('text', '')!r}), evidence={spec.get('evidence')!r}: {exc}"
                        ) from exc
                fields[role] = {"state": state, "claim_ids": claim_ids}
        return fields

    def _context(self) -> dict:
        spec = self.draft["context"]
        provenance = spec.get("provenance", {})
        ctx: dict = {}
        prov: dict = {}
        for key in _METADATA_KEYS:
            value = spec.get(key, [] if key in _LIST_KEYS else None)
            ctx[key] = value
            empty = not value if key in _LIST_KEYS else value is None
            entry = provenance.get(key, {})
            basis = entry.get("basis", "unknown" if empty else None)
            if basis is None:
                raise DraftError(f"context.{key} has a value but no provenance basis (source or curated)")
            source_ids = entry.get("source_ids", self.draft["source_ids"] if basis == "source" else [])
            prov[key] = {"basis": basis, "source_ids": source_ids, "note": entry.get("note")}
        ctx["metadata_provenance"] = prov
        return ctx

    def compile(self) -> dict:
        d = self.draft
        steps: list[dict[str, Any]] = []
        questions: list[dict[str, Any]] = []
        for n, step in enumerate(d["steps"], start=1):
            step_id = self._nested("ST", n)
            steps.append({"step_id": step_id, "display_order": n, "title": step["title"], "fields": self._fields(step)})
            for q in step.get("questions", []):
                questions.append({
                    "question_id": self._nested("Q", len(questions) + 1),
                    "step_id": step_id,
                    "target_field": q["target_field"],
                    "reason": q["reason"],
                    "question": q["question"],
                    "status": q.get("status", "open"),
                    "answer_source_ids": q.get("answer_source_ids", []),
                    "resolution_note": q.get("resolution_note"),
                })

        relations = []
        for n, rel in enumerate(d.get("relations", []), start=1):
            for key in ("from_step", "to_step"):
                if not 1 <= rel[key] <= len(steps):
                    raise DraftError(f"relation {n}: {key}={rel[key]} is not a step number")
            conditions = []
            for key in rel.get("condition_keys", []):
                if key not in self._claim_keys or self._claim_keys[key]["role"] != "condition":
                    raise DraftError(f"relation {n}: condition key '{key}' is not a condition claim")
                conditions.append(self._claim_keys[key]["claim_id"])
            relations.append({
                "relation_id": self._nested("RL", n),
                "from_step_id": steps[rel["from_step"] - 1]["step_id"],
                "to_step_id": steps[rel["to_step"] - 1]["step_id"],
                "relation_type": rel["type"],
                "claim_ids": [self._claim(rel["claim"], "relation")],
                "condition_claim_ids": conditions,
            })

        return {
            "schema_version": "1.0.0",
            "workflow_id": self.wf_id,
            "revision": d["revision"],
            "source_type": "real",
            "dataset_split": d["dataset_split"],
            "title": d["title"],
            "language": d["language"],
            "created_at": d["created_at"],
            "supersedes_revision": d.get("supersedes_revision"),
            "lifecycle": "active",
            "source_ids": d["source_ids"],
            "context": self._context(),
            "steps": steps,
            "claims": self.claims,
            "evidence": self.evidence,
            "relations": relations,
            "questions": questions,
            "review_events": [],
            "change_log": d.get("change_log", []),
        }


def revision_base(draft: dict) -> dict | None:
    try:
        return revisions.load_base(draft, REPO_ROOT)
    except revisions.RevisionError as exc:
        raise DraftError(str(exc)) from None


def compile_draft(draft: dict, pool: dict[str, ep.Candidate] | None = None) -> dict:
    legacy = type(draft.get("revision")) is int and draft["revision"] > 1 and "revision_base" not in draft
    base = None if legacy else revision_base(draft)
    snapshot = _Compiler(draft, pool if pool is not None else ep.load_pool()).compile()
    try:
        if legacy:
            revisions.legacy_replay_base(snapshot, REPO_ROOT)
        elif base is not None:
            snapshot = revisions.preserve_evidence_ids(snapshot, base)
    except revisions.RevisionError as exc:
        raise DraftError(str(exc)) from None
    return snapshot


def check_snapshot(snapshot: dict, split: str = "dev", *, source_records: list[dict] | None = None,
                   previous_snapshots: list[dict] | None = None) -> exporter.ExportResult:
    """Validate using supplied Sources or the canonical split, without publishing files."""
    cfg = exporter.SPLITS[split]
    with tempfile.TemporaryDirectory(prefix="draft-check-") as tmp:
        snap_dir = Path(tmp) / "snapshots"
        snap_dir.mkdir()
        for previous in previous_snapshots or []:
            if (previous["workflow_id"], previous["revision"]) == (snapshot["workflow_id"], snapshot["revision"]):
                raise DraftError("Previous snapshot must not overwrite the revision being checked")
            write_snapshot(previous, snap_dir)
        write_snapshot(snapshot, snap_dir)
        sources_path = cfg["sources"]
        if source_records is not None:
            sources_path = Path(tmp) / "sources.jsonl"
            sources_path.write_text(
                "".join(json.dumps(source, ensure_ascii=False) + "\n" for source in source_records),
                encoding="utf-8", newline="\n",
            )
        return exporter.export_bundle(
            split=split, sources_path=Path(str(sources_path)), snapshot_dir=snap_dir,
            out_dir=Path(tmp) / "bundle", bundle_prefix="DRAFT_CHECK", check_only=True,
        )


def check_draft_snapshot(draft: dict, snapshot: dict) -> exporter.ExportResult:
    """Run shared validation over base + candidate together, including D-02/V03."""
    if draft["revision"] > 1 and "revision_base" not in draft:
        # Compare the fresh unreviewed compile, even when validating a reviewed
        # candidate during promotion. ReviewEvents do not change draft identity.
        try:
            compiled = _Compiler(draft, ep.load_pool()).compile()
            base = revisions.legacy_replay_base(compiled, REPO_ROOT)
        except revisions.RevisionError as exc:
            raise DraftError(str(exc)) from None
    else:
        base = revision_base(draft)
    return check_snapshot(snapshot, draft["dataset_split"], previous_snapshots=[base] if base else [])


def write_snapshot(snapshot: dict, out_dir: Path = DRAFT_OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{snapshot['workflow_id']}.r{snapshot['revision']}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compile_workflow", description=__doc__.split("\n\n")[0])
    parser.add_argument("draft", help="path to a *.draft.json file")
    parser.add_argument("--out", help="snapshot directory (default: data/workflows/drafts)")
    parser.add_argument("-v", "--verbose", action="store_true", help="also print validator warnings")
    args = parser.parse_args(argv)

    draft = json.loads(Path(args.draft).read_text(encoding="utf-8"))
    try:
        snapshot = compile_draft(draft)
    except (DraftError, ep.PoolError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    result = check_draft_snapshot(draft, snapshot)
    for issue in result.report.issues:
        if issue.severity == "error" or args.verbose:
            print(f"  {issue}")
    if not result.report.ok:
        print("REJECTED: snapshot not written", file=sys.stderr)
        return 1

    path = write_snapshot(snapshot, Path(args.out) if args.out else DRAFT_OUT)
    fields = [f for s in snapshot["steps"] for f in s["fields"].values()]
    present = sum(1 for f in fields if f["state"] != "missing")
    print(
        f"OK  {path.relative_to(REPO_ROOT).as_posix()}  steps={len(snapshot['steps'])} claims={len(snapshot['claims'])} "
        f"evidence={len(snapshot['evidence'])} questions={len(snapshot['questions'])} "
        f"fields present={present}/{len(fields)}  warnings={len(result.report.warnings)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
