"""Feedback Loop & Expert Answer Ingestion Module (WP6 / Schema 1.0.0).

Enables the A2 feedback loop:
1. Receives human/expert answer to an open technical question (`QuestionRecord`).
2. Creates an immutable `expert_answer` Source record with verbatim quote & speaker attribution.
3. Updates the target question from `open` to `answered` or `resolved`.
4. Creates new atomic Claim & Evidence records linked to the new Source.
5. Advances workflow revision from N to N+1, setting `supersedes_revision=N` and logging the audit trail in `change_log`.
6. Validates the resulting snapshot against Schema 1.0.0.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:
    pass

from knowflow_contracts.enums import (
    AttributionKind,
    EvidenceKind,
    FieldState,
    Modality,
    QuestionStatus,
    ReviewDecision,
    ReviewDimension,
    ReviewTargetType,
    ScopeLevel,
    SourceKind,
    SourceType,
    SupportStatus,
    TechnicalReview,
    TranscriptOrigin,
)
from knowflow_contracts.models import Evidence, Source, Workflow

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "data" / "workflows"
SOURCES_FILE = REPO_ROOT / "data" / "sources" / "haas_pilot_sources.jsonl"

logger = logging.getLogger("feedback_loop")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_expert_answer_source(
    answer_text: str,
    expert_name: str,
    expert_role: str,
    source_id: str | None = None,
    language: str = "en",
    access_note: str | None = "Expert clarification via KnowFlow AI feedback loop",
    clock: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    """Creates a validated Schema 1.0.0 Source record of kind `expert_answer`."""
    raw_text = answer_text.strip()
    if not raw_text:
        raise ValueError("Câu trả lời của chuyên gia (answer_text) không được để trống.")
    if not expert_name.strip() or not expert_role.strip():
        raise ValueError("expert_name và expert_role bắt buộc phải được cung cấp.")

    digest = _sha256(raw_text)
    sid = source_id or f"SRC_EXP_{digest[:8].upper()}"

    record: dict[str, Any] = {
        "source_id": sid,
        "source_type": SourceType.REAL.value,
        "source_kind": SourceKind.EXPERT_ANSWER.value,
        "title": f"Expert clarification by {expert_name}",
        "url": None,
        "asset_uri": None,
        "language": language,
        "duration_ms": None,
        "publisher": "Haas Service & Operations Expert Network",
        "presenter": expert_name.strip(),
        "presenter_role": expert_role.strip(),
        "published_at": None,
        "retrieved_at": clock(),
        "raw_text": raw_text,
        "content_sha256": digest,
        "related_source_ids": [],
        "access_note": access_note,
    }

    # Validate against strict schema contract
    validated = Source.model_validate(record)
    return validated.model_dump(mode="json")


def apply_expert_feedback(
    snapshot: dict[str, Any],
    target_question_id: str,
    expert_name: str,
    expert_role: str,
    answer_text: str,
    target_step_id: str | None = None,
    target_field_role: str | None = None,
    resolution_status: str = "resolved",
    clock: Callable[[], str] = _utc_now,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Applies expert answer to a workflow snapshot:
    - Creates expert_answer Source record.
    - Transitions question status to 'answered' or 'resolved'.
    - Bumps revision to N+1 with supersedes_revision and change_log entry.
    - Adds new Evidence and Claim to the target step field.
    """
    if resolution_status not in ("answered", "resolved"):
        raise ValueError(f"resolution_status phải là 'answered' hoặc 'resolved', nhận được '{resolution_status}'")

    # 1. Locate target question
    questions = snapshot.get("questions", [])
    target_q = None
    for q in questions:
        if q.get("question_id") == target_question_id:
            target_q = q
            break

    if not target_q:
        raise ValueError(f"Không tìm thấy câu hỏi '{target_question_id}' trong workflow {snapshot.get('workflow_id')}")

    step_id = target_step_id or target_q.get("step_id")
    role_name = target_field_role or target_q.get("target_field")
    if not step_id or not role_name:
        raise ValueError("Không xác định được target_step_id hoặc target_field cho câu hỏi này.")

    # 2. Create Source record
    source_record = create_expert_answer_source(
        answer_text=answer_text,
        expert_name=expert_name,
        expert_role=expert_role,
        language=snapshot.get("language", "en"),
        clock=clock,
    )
    src_id = source_record["source_id"]

    # 3. Build new snapshot revision (Revision N+1)
    base_rev = snapshot["revision"]
    new_rev = base_rev + 1
    new_wf = copy.deepcopy(snapshot)
    new_wf["revision"] = new_rev
    new_wf["supersedes_revision"] = base_rev
    new_wf["created_at"] = clock()

    if src_id not in new_wf["source_ids"]:
        new_wf["source_ids"].append(src_id)

    # 4. Update question
    for q in new_wf["questions"]:
        if q.get("question_id") == target_question_id:
            q["status"] = QuestionStatus(resolution_status).value
            if src_id not in q.get("answer_source_ids", []):
                q.setdefault("answer_source_ids", []).append(src_id)
            q["resolution_note"] = f"Clarified by {expert_name} ({expert_role}): {answer_text.strip()}"

    # 5. Create new Evidence record
    new_ev_id = f"{new_wf['workflow_id']}_EV_{len(new_wf.get('evidence', [])) + 1:03d}"
    evidence_record = {
        "evidence_id": new_ev_id,
        "source_id": src_id,
        "modality": Modality.TEXT.value,
        "locator": {
            "start_ms": None,
            "end_ms": None,
            "page": None,
            "text_span": answer_text.strip(),
        },
        "quote": answer_text.strip(),
        "observation_note": None,
        "asset_uri": None,
        "transcript_origin": TranscriptOrigin.HUMAN.value,
        "parent_evidence_ids": [],
    }
    validated_ev = Evidence.model_validate(evidence_record)
    new_wf.setdefault("evidence", []).append(validated_ev.model_dump(mode="json"))

    # 6. Create new Claim record
    new_cl_id = f"{new_wf['workflow_id']}_CL_{len(new_wf.get('claims', [])) + 1:03d}"
    tech_decision = (
        TechnicalReview.EXPERT_VALIDATED.value
        if resolution_status == "resolved"
        else TechnicalReview.PENDING.value
    )
    claim_record = {
        "claim_id": new_cl_id,
        "text": answer_text.strip(),
        "role": role_name,
        "evidence_type": EvidenceKind.STATED.value,
        "attribution": {
            "actor_id": None,
            "label": expert_name,
            "kind": AttributionKind.SPEAKER.value,
        },
        "scope": {
            "level": ScopeLevel.CASE.value,
            "description": f"Clarified by {expert_name} for question {target_question_id}",
        },
        "evidence_links": [
            {
                "evidence_id": new_ev_id,
                "support_status": SupportStatus.SUPPORTED.value,
                "explanation": f"Expert clarification by {expert_name} ({expert_role})",
            }
        ],
        "support_status": SupportStatus.SUPPORTED.value,
        "source_review": "source_checked" if resolution_status == "resolved" else "pending",
        "technical_review": tech_decision,
        "conflicts_with": [],
        "supersedes_claim_ids": [],
    }
    new_wf.setdefault("claims", []).append(claim_record)

    # 7. Update target step field
    step_found = False
    for st in new_wf.get("steps", []):
        if st.get("step_id") == step_id:
            step_found = True
            fields = st.setdefault("fields", {})
            f_ref = fields.setdefault(role_name, {"state": "present", "claim_ids": []})
            f_ref["state"] = FieldState.PRESENT.value
            if new_cl_id not in f_ref.get("claim_ids", []):
                f_ref.setdefault("claim_ids", []).append(new_cl_id)
            break

    if not step_found:
        raise ValueError(f"Không tìm thấy step '{step_id}' trong workflow.")

    # 8. Add ReviewEvent if resolved
    if resolution_status == "resolved":
        new_rv_id = f"{new_wf['workflow_id']}_RV_{len(new_wf.get('review_events', [])) + 1:03d}"
        rev_event = {
            "review_id": new_rv_id,
            "target_type": ReviewTargetType.CLAIM.value,
            "target_id": new_cl_id,
            "dimension": ReviewDimension.TECHNICAL.value,
            "decision": ReviewDecision.EXPERT_VALIDATED.value,
            "reviewer_id": expert_name,
            "reviewer_role": expert_role,
            "reviewed_at": clock(),
            "note": f"Validated expert clarification for question {target_question_id}",
        }
        new_wf.setdefault("review_events", []).append(rev_event)

    # 9. Append change_log (Schema 1.0.0 ChangeEvent)
    change_entry = {
        "changed_at": clock(),
        "actor_id": expert_name,
        "reason": f"Resolved question {target_question_id} ({role_name}) via expert answer from {expert_name}",
        "previous_revision": base_rev,
        "id_mapping": [],
    }
    new_wf.setdefault("change_log", []).append(change_entry)

    # 10. Validate with Schema 1.0.0 Workflow model
    Workflow.model_validate(new_wf)
    return new_wf, source_record


def append_source_to_catalog(source_record: dict[str, Any], sources_path: Path = SOURCES_FILE) -> None:
    """Appends the newly created Source record to sources.jsonl if not already present."""
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    if sources_path.is_file():
        for line in sources_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing_ids.add(json.loads(line).get("source_id"))

    if source_record["source_id"] in existing_ids:
        logger.debug(f"Source {source_record['source_id']} đã có trong {sources_path.name}.")
        return

    jsonl_line = json.dumps(source_record, ensure_ascii=False, sort_keys=True) + "\n"
    with open(sources_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(jsonl_line)
    logger.info(f"✅ Đã ghi nhận Source mới: {source_record['source_id']} -> {sources_path.name}")


def main():
    parser = argparse.ArgumentParser(
        description="KnowFlow AI - Feedback Loop: nạp phản hồi chuyên gia, nâng revision workflow N+1."
    )
    parser.add_argument("--workflow-path", type=Path, required=True, help="Đường dẫn tới file workflow snapshot (.json)")
    parser.add_argument("--question-id", type=str, required=True, help="Mã định danh câu hỏi cần giải quyết (Question ID)")
    parser.add_argument("--answer", type=str, required=True, help="Nội dung câu trả lời chuyên môn")
    parser.add_argument("--expert-name", type=str, required=True, help="Tên chuyên gia trả lời")
    parser.add_argument("--expert-role", type=str, required=True, help="Vai trò chuyên gia (vd: Haas Senior Certified Technician)")
    parser.add_argument("--target-step", type=str, default=None, help="Mã bước (nếu câu hỏi chưa liên kết step_id)")
    parser.add_argument("--target-field", type=str, default=None, help="Tên vai trò trường (rationale, condition, ...)")
    parser.add_argument("--status", choices=["answered", "resolved"], default="resolved", help="Trạng thái câu hỏi sau khi nạp")
    parser.add_argument("--out-dir", type=Path, default=None, help="Thư mục lưu snapshot mới (mặc định lưu cùng thư mục với file gốc)")

    args = parser.parse_args()

    snapshot_data = json.loads(args.workflow_path.read_text(encoding="utf-8"))
    new_snapshot, source_record = apply_expert_feedback(
        snapshot=snapshot_data,
        target_question_id=args.question_id,
        expert_name=args.expert_name,
        expert_role=args.expert_role,
        answer_text=args.answer,
        target_step_id=args.target_step,
        target_field_role=args.target_field,
        resolution_status=args.status,
    )

    # Save new source record
    append_source_to_catalog(source_record)

    # Save new workflow revision
    out_dir = args.out_dir or args.workflow_path.parent
    out_file = out_dir / f"{new_snapshot['workflow_id']}.r{new_snapshot['revision']}.json"
    out_file.write_text(json.dumps(new_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("✅ Hoàn tất Feedback Loop!")
    print(f"   - Source mới:      {source_record['source_id']}")
    print(f"   - Workflow mới:    {out_file.name} (Revision {new_snapshot['revision']}, supersedes r{new_snapshot['supersedes_revision']})")
    print(f"   - Câu hỏi {args.question_id} đã chuyển trạng thái: {args.status}")


if __name__ == "__main__":
    main()
