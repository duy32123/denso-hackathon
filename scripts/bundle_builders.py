"""Bo dung record Schema 1.0.0 dung chung cho cac trinh sinh bundle.

Tach ra tu scripts/build_fixtures.py de scripts/build_synthetic_kb.py dung lai
cung mot cach dung manifest/source/workflow: checksum va record_count luon khop
noi dung that, khoa JSON sort on dinh, tep bundle luon LF.

Tep nay chi chua ham dung, khong chua noi dung cua bat ky bundle nao.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "contracts" / "schema"))

from knowflow_contracts.derive import derive_support_status  # noqa: E402

TS = "2026-09-08T00:00:00Z"
FIXTURE_NOTE = "Chi dung test phan mem"

FIELD_ROLES = (
    "context",
    "observation",
    "action",
    "rationale",
    "condition",
    "outcome",
    "acceptance_criteria",
)
PROV_KEYS = (
    "manufacturer",
    "machine_family",
    "machine_model",
    "subsystem",
    "task_type",
    "symptoms",
    "alarm_codes",
    "components",
)


# --- helper dung record ------------------------------------------------------


def prov(basis: str = "unknown", source_ids=(), note=None) -> dict:
    return {"basis": basis, "source_ids": list(source_ids), "note": note}


def make_context(**over) -> dict:
    ctx = {
        "manufacturer": None,
        "machine_family": None,
        "machine_model": None,
        "subsystem": None,
        "task_type": None,
        "symptoms": [],
        "alarm_codes": [],
        "components": [],
    }
    provenance = {k: prov() for k in PROV_KEYS}
    for key, value in over.items():
        if key == "provenance":
            provenance.update(value)
        else:
            ctx[key] = value
    for key in PROV_KEYS:
        value = ctx[key]
        empty = value is None if key not in ("symptoms", "alarm_codes", "components") else not value
        if not empty and provenance[key]["basis"] == "unknown":
            provenance[key] = prov("curated", note="Nhan phan loai cua fixture, khong phai phat bieu chuyen gia")
    ctx["metadata_provenance"] = provenance
    return ctx


def fref(state: str = "missing", claim_ids=()) -> dict:
    return {"state": state, "claim_ids": list(claim_ids)}


def make_step(step_id: str, order: int, title: str, **fields) -> dict:
    resolved = {role: fref() for role in FIELD_ROLES}
    for role, value in fields.items():
        resolved[role] = value if isinstance(value, dict) else fref("present", value)
    return {"step_id": step_id, "display_order": order, "title": title, "fields": resolved}


def make_source(
    source_id: str,
    *,
    source_type: str = "synthetic",
    source_kind: str = "synthetic_fixture",
    title: str,
    raw_text: str | None = "Van ban mo phong.",
    duration_ms: int | None = None,
    url: str | None = None,
    presenter: str | None = "Nhan vat mo phong",
    language: str = "vi",
) -> dict:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "source_kind": source_kind,
        "title": title,
        "url": url,
        "asset_uri": None,
        "language": language,
        "duration_ms": duration_ms,
        "publisher": None,
        "presenter": presenter,
        "presenter_role": None,
        "published_at": None,
        "retrieved_at": TS,
        "raw_text": raw_text,
        "content_sha256": None,
        "related_source_ids": [],
        "access_note": FIXTURE_NOTE,
    }


def make_evidence(
    evidence_id: str,
    source_id: str,
    *,
    modality: str = "text",
    quote: str | None = None,
    observation_note: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    text_span: str | None = None,
    page: int | None = None,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "modality": modality,
        "locator": {"start_ms": start_ms, "end_ms": end_ms, "page": page, "text_span": text_span},
        "quote": quote,
        "observation_note": observation_note,
        "asset_uri": None,
        "transcript_origin": "none",
        "parent_evidence_ids": [],
    }


def make_claim(
    claim_id: str,
    text: str,
    role: str,
    evidence_ids=(),
    *,
    evidence_type: str = "stated",
    link_status: str = "supported",
    explanation: str = "Cau mo phong truc tiep neu noi dung nay.",
    conflicts_with=(),
    attribution_kind: str | None = None,
    scope_description: str = "Chi trong fixture nay",
    support_status: str | None = None,
) -> dict:
    links = [
        {"evidence_id": eid, "support_status": link_status, "explanation": explanation}
        for eid in evidence_ids
    ]
    kind = attribution_kind or {"observed": "observer", "inferred": "model"}.get(evidence_type, "speaker")
    derived = derive_support_status(links, has_unresolved_conflict=bool(conflicts_with))
    return {
        "claim_id": claim_id,
        "text": text,
        "role": role,
        "evidence_type": evidence_type,
        "attribution": {"actor_id": None, "label": "Nhan vat mo phong", "kind": kind},
        "scope": {"level": "case", "description": scope_description},
        "evidence_links": links,
        "support_status": support_status or derived.value,
        "source_review": "pending",
        "technical_review": "not_requested",
        "conflicts_with": list(conflicts_with),
        "supersedes_claim_ids": [],
    }


def make_question(
    question_id: str, step_id: str, target_field: str, reason: str, question: str, *, status: str = "open",
    answer_source_ids=(), resolution_note: str | None = None,
) -> dict:
    return {
        "question_id": question_id,
        "step_id": step_id,
        "target_field": target_field,
        "reason": reason,
        "question": question,
        "status": status,
        "answer_source_ids": list(answer_source_ids),
        "resolution_note": resolution_note,
    }


def make_workflow(
    workflow_id: str,
    *,
    title: str,
    source_ids,
    context: dict,
    steps,
    claims,
    evidence,
    revision: int = 1,
    supersedes_revision: int | None = None,
    language: str = "vi",
    source_type: str = "synthetic",
    dataset_split: str = "dev",
    lifecycle: str = "active",
    relations=(),
    questions=(),
    review_events=(),
    change_log=(),
) -> dict:
    return {
        "schema_version": "1.0.0",
        "workflow_id": workflow_id,
        "revision": revision,
        "source_type": source_type,
        "dataset_split": dataset_split,
        "title": title,
        "language": language,
        "created_at": TS,
        "supersedes_revision": supersedes_revision,
        "lifecycle": lifecycle,
        "source_ids": list(source_ids),
        "context": context,
        "steps": list(steps),
        "claims": list(claims),
        "evidence": list(evidence),
        "relations": list(relations),
        "questions": list(questions),
        "review_events": list(review_events),
        "change_log": list(change_log),
    }


def make_relation(relation_id, from_step, to_step, relation_type, claim_ids, condition_claim_ids=()) -> dict:
    return {
        "relation_id": relation_id,
        "from_step_id": from_step,
        "to_step_id": to_step,
        "relation_type": relation_type,
        "claim_ids": list(claim_ids),
        "condition_claim_ids": list(condition_claim_ids),
    }


# --- ghi bundle --------------------------------------------------------------


def write_bundle(
    bundle_dir: str,
    *,
    root: Path,
    sources,
    workflows,
    expected: dict | None = None,
    source_type: str = "synthetic",
    dataset_split: str = "dev",
    team: str = "team_2",
    bundle_id: str | None = None,
    pipeline_version: str = "fixtures-1.0.0",
    created_at: str = TS,
) -> Path:
    target = root / bundle_dir
    target.mkdir(parents=True, exist_ok=True)

    def dump_jsonl(name: str, records) -> tuple[str, int]:
        text = "".join(
            json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for rec in records
        )
        data = text.encode("utf-8")
        (target / name).write_bytes(data)
        return hashlib.sha256(data).hexdigest(), len(records)

    sources_sha, sources_n = dump_jsonl("sources.jsonl", sources)
    workflows_sha, workflows_n = dump_jsonl("workflows.jsonl", workflows)

    manifest = {
        "schema_version": "1.0.0",
        "bundle_id": bundle_id or f"BUNDLE_{bundle_dir}",
        "source_type": source_type,
        "dataset_split": dataset_split,
        "created_at": created_at,
        "files": [
            {"path": "sources.jsonl", "sha256": sources_sha, "record_count": sources_n},
            {"path": "workflows.jsonl", "sha256": workflows_sha, "record_count": workflows_n},
        ],
        "producer": {"team": team, "pipeline_version": pipeline_version},
    }
    # newline="\n": tep bundle luon LF. Checksum tinh tren byte, nen eol la mot phan
    # cua hop dong chu khong phai chi tiet trinh bay (xem .gitattributes).
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if expected is not None:
        (target / "expected.json").write_text(
            json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    return target


def rag(question: str, expected_status: str, **kw) -> dict:
    case = {"question": question, "mode": kw.pop("mode", "synthetic"), "expected_status": expected_status}
    case.update(kw)
    return case
