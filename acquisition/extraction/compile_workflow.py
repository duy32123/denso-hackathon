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
        frame_ms = int(path.stem.split("_")[-1])
        if not ref["start_ms"] <= frame_ms < ref["end_ms"]:
            raise DraftError(f"{path.name}: frame at {frame_ms} ms is outside [{ref['start_ms']}, {ref['end_ms']})")
        if not ref.get("observation_note"):
            raise DraftError(f"{path.name}: visual evidence needs an observation_note describing only what is visible")

        key = ("keyframe", ref["keyframe"], ref["start_ms"], ref["end_ms"])
        if key in self._evidence_ids:
            return self._evidence_ids[key]
        eid = self._nested("EV", len(self.evidence) + 1)
        self.evidence.append({
            "evidence_id": eid,
            "source_id": ref["source_id"],
            "modality": "visual",
            "locator": {"start_ms": ref["start_ms"], "end_ms": ref["end_ms"], "page": None, "text_span": None},
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
            elif isinstance(value, list):
                fields[role] = {"state": "present", "claim_ids": [self._claim(c, role) for c in value]}
            else:
                fields[role] = {"state": value["state"], "claim_ids": [self._claim(c, role) for c in value["claims"]]}
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


def compile_draft(draft: dict, pool: dict[str, ep.Candidate] | None = None) -> dict:
    return _Compiler(draft, pool if pool is not None else ep.load_pool()).compile()


def check_snapshot(snapshot: dict, split: str = "dev") -> exporter.ExportResult:
    """Validate the snapshot inside a would-be bundle with the real Source file. Writes nothing."""
    cfg = exporter.SPLITS[split]
    with tempfile.TemporaryDirectory(prefix="draft-check-") as tmp:
        snap_dir = Path(tmp) / "snapshots"
        snap_dir.mkdir()
        write_snapshot(snapshot, snap_dir)
        return exporter.export_bundle(
            split=split, sources_path=Path(str(cfg["sources"])), snapshot_dir=snap_dir,
            out_dir=Path(tmp) / "bundle", bundle_prefix="DRAFT_CHECK", check_only=True,
        )


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

    result = check_snapshot(snapshot, draft["dataset_split"])
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
