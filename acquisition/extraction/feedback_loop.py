"""Feedback Loop & Expert Answer Ingestion Module (WP6 / Schema 1.0.0).

Enables the A2 feedback loop:
1. Receives human/expert answer to an open technical question (`QuestionRecord`).
2. Creates an immutable `expert_answer` Source record with verbatim quote & speaker attribution.
3. Updates the target question from `open` to `answered` or `resolved`.
4. Creates new atomic Claim & Evidence records linked to the new Source.
5. Advances workflow revision from N to N+1, setting `supersedes_revision=N` and logging the audit trail in `change_log`.
6. Validates the resulting snapshot against Schema 1.0.0.

Nhận phản hồi **không phải** là đã kiểm nguồn, càng không phải chuyên gia đã xác
nhận đúng kỹ thuật. Hệ thống chưa có đăng nhập: tên và vai trò người trả lời là
tự khai. Vì vậy claim sinh ra ở đây luôn `source_review=pending` và
`technical_review=not_requested`, và module này không bao giờ tự sinh ReviewEvent.
Muốn nâng lên `source_checked` / `expert_validated` thì phải qua
`acquisition.extraction.review`, có người kiểm thật và ReviewEvent nằm trong
chính revision đó (V07). Xem docs/team2_feedback_contract.md mục 3.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import re
import sys
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:
    pass

from knowflow_contracts import derive_support_status
from knowflow_contracts.enums import (
    AttributionKind,
    EvidenceKind,
    FieldState,
    Modality,
    QuestionStatus,
    ScopeLevel,
    SourceKind,
    SourceReview,
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


def _next_sequence_id(workflow_id: str, kind: str, existing_ids: Iterable[str]) -> str:
    """Cap ID moi = so thu tu lon nhat da dung + 1.

    Khong dung `len(...) + 1`: mot ban ghi bi bo di la ID moi trung ngay vao ID cu
    voi noi dung khac, tuc vi pham D-02 (evidence bat bien trong mot workflow_id)
    va bi V03 chan. Loi nay da xay ra o REAL_WF_0001.r2 (PR #16). Cung quy uoc voi
    `revisions.preserve_evidence_ids`.
    """
    pattern = re.compile(re.escape(workflow_id) + rf"_{kind}_(\d+)$")
    highest = max(
        (int(match[1]) for eid in existing_ids if (match := pattern.fullmatch(eid))),
        default=0,
    )
    return f"{workflow_id}_{kind}_{highest + 1:03d}"


def collect_reserved_ids(
    workflow_id: str,
    repo_root: Path = REPO_ROOT,
) -> set[str]:
    """Gom moi evidence/claim ID da duoc cap cho workflow nay tren dia.

    Snapshot goc chi thay revision cua chinh no, nhung D-02 rang buoc tren ca
    `workflow_id`: mot ID da dung o revision khac -- ke ca ban draft chua promote --
    khong duoc tro sang noi dung khac. Vi du that: `REAL_WF_0001.r1` co ID cao nhat
    la EV_035, nhung draft r2 da cap EV_036 cho mot keyframe.
    """
    reserved: set[str] = set()
    for path in sorted((repo_root / "data" / "workflows").rglob(f"{workflow_id}.r*.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning(f"Bỏ qua {path.name}: không đọc được để thu ID đã cấp.")
            continue
        reserved.update(ev.get("evidence_id", "") for ev in snapshot.get("evidence", []))
        reserved.update(cl.get("claim_id", "") for cl in snapshot.get("claims", []))
    reserved.discard("")
    return reserved


def feedback_asset_uri(source_id: str) -> str:
    """Duong dan tuong doi tu goc repo toi tep luu nguyen van phan hoi.

    V02: nguon real bat buoc co `url` hoac `asset_uri`, khong chi `raw_text`.
    Phan hoi khong co URL cong khai nen duoc ghi thanh tep trong repo.
    """
    return f"acquisition/feedback/{source_id}.json"


def create_expert_answer_source(
    answer_text: str,
    expert_name: str,
    expert_role: str,
    source_id: str | None = None,
    language: str = "en",
    access_note: str | None = "Expert clarification via KnowFlow AI feedback loop",
    clock: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    """Creates a validated Schema 1.0.0 Source record of kind `expert_answer`.

    `presenter` / `presenter_role` la **tu khai**: he thong chua co dang nhap nen
    khong duoc coi day la danh tinh da xac thuc. `asset_uri` tro toi tep phan hoi
    do `write_feedback_asset` ghi; thieu no thi V02 tu choi ca bundle.
    """
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
        "asset_uri": feedback_asset_uri(sid),
        "language": language,
        "duration_ms": None,
        "publisher": None,
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


def write_feedback_asset(
    source_record: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Ghi nguyen van phan hoi ra tep ma `Source.asset_uri` dang tro toi.

    Goi truoc khi export: `asset_uri` tro vao tep khong ton tai thi citation mo
    khong duoc, va doi 2 phai tu choi bao thu.
    """
    asset_uri = source_record.get("asset_uri")
    if not asset_uri:
        raise ValueError(f"Source {source_record.get('source_id')} khong co asset_uri de ghi.")
    target = repo_root / asset_uri
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_id": source_record["source_id"],
        "source_kind": source_record["source_kind"],
        "language": source_record["language"],
        "presenter": source_record["presenter"],
        "presenter_role": source_record["presenter_role"],
        "presenter_authenticated": False,
        "retrieved_at": source_record["retrieved_at"],
        "content_sha256": source_record["content_sha256"],
        "raw_text": source_record["raw_text"],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    logger.info(f"✅ Đã ghi nguyên văn phản hồi: {asset_uri}")
    return target


def apply_expert_feedback(
    snapshot: dict[str, Any],
    target_question_id: str,
    expert_name: str,
    expert_role: str,
    answer_text: str,
    target_step_id: str | None = None,
    target_field_role: str | None = None,
    resolution_status: str = "answered",
    reserved_ids: Iterable[str] | None = None,
    answer_language: str | None = None,
    clock: Callable[[], str] = _utc_now,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Applies expert answer to a workflow snapshot:
    - Creates expert_answer Source record.
    - Transitions question status to 'answered' or 'resolved'.
    - Bumps revision to N+1 with supersedes_revision and change_log entry.
    - Adds new Evidence and Claim to the target step field.

    Claim moi luon `pending` / `not_requested` va khong kem ReviewEvent, du
    `resolution_status` la gi. Trang thai cua Question va trang thai review cua
    claim la hai thu khac nhau: `resolved` chi noi cau hoi da duoc xu ly, khong
    noi rang co nguoi da doi chieu nguon hay xac nhan dung ky thuat.

    `reserved_ids`: ID da cap o cac revision khac cua chinh workflow nay (xem
    `collect_reserved_ids`). Truyen vao de ID moi khong dam vao ID da phat hanh.

    `answer_language`: ngon ngu **thuc te** cua phan hoi (D-03). Mac dinh lay theo
    workflow, nhung mot cau tra loi tieng Viet tren workflow tieng Anh la mot nguon
    tieng Viet -- ghi 'en' cho no la khai sai ngon ngu nguon.
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
        language=answer_language or snapshot.get("language", "en"),
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
    reserved = set(reserved_ids or ())
    new_ev_id = _next_sequence_id(
        new_wf["workflow_id"],
        "EV",
        reserved | {ev["evidence_id"] for ev in new_wf.get("evidence", [])},
    )
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
    new_cl_id = _next_sequence_id(
        new_wf["workflow_id"],
        "CL",
        reserved | {cl["claim_id"] for cl in new_wf.get("claims", [])},
    )
    evidence_links = [
        {
            "evidence_id": new_ev_id,
            "support_status": SupportStatus.SUPPORTED.value,
            "explanation": f"Expert clarification by {expert_name} ({expert_role})",
        }
    ]
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
        "evidence_links": evidence_links,
        # D-01: khong ai duoc tu dat support_status bang tay.
        "support_status": derive_support_status(evidence_links).value,
        # Co phan hoi KHONG phai la da kiem nguon, cang khong phai chuyen gia da
        # xac nhan. Nang len phai qua `acquisition.extraction.review`, co nguoi
        # kiem that va ReviewEvent trong chinh revision do (V07).
        "source_review": SourceReview.PENDING.value,
        "technical_review": TechnicalReview.NOT_REQUESTED.value,
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

    # 8. KHONG sinh ReviewEvent o day.
    # He thong chua co dang nhap: `expert_name` / `expert_role` la chu nguoi dung
    # tu go vao. Tu sinh ReviewEvent decision=expert_validated tu o text do la
    # bien mot loi khai thanh "chuyen gia da xac nhan" (bat bien so 3 cua du an).
    # Review that di qua `acquisition.extraction.review` voi nguoi kiem thuc su.

    # 9. Append change_log (Schema 1.0.0 ChangeEvent)
    change_entry = {
        "changed_at": clock(),
        "actor_id": expert_name,
        "reason": (
            f"Answered question {target_question_id} ({role_name}) from a self-reported "
            f"response by {expert_name} ({expert_role}); identity not authenticated, "
            "claim left pending source review"
        ),
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
    parser.add_argument(
        "--status",
        choices=["answered", "resolved"],
        default="answered",
        help=(
            "Trạng thái câu hỏi sau khi nạp. Mặc định 'answered'; chuyển 'resolved' là "
            "bước riêng sau khi nội dung đã được người kiểm (contract mục 3.6). "
            "Cả hai đều KHÔNG đổi trạng thái review của claim."
        ),
    )
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
        reserved_ids=collect_reserved_ids(snapshot_data["workflow_id"]),
    )

    # Save the verbatim response where Source.asset_uri points (V02)
    asset_path = write_feedback_asset(source_record)

    # Save new source record
    append_source_to_catalog(source_record)

    # Save new workflow revision
    out_dir = args.out_dir or args.workflow_path.parent
    out_file = out_dir / f"{new_snapshot['workflow_id']}.r{new_snapshot['revision']}.json"
    out_file.write_text(json.dumps(new_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("✅ Hoàn tất Feedback Loop!")
    print(f"   - Source mới:      {source_record['source_id']}")
    print(f"   - Nguyên văn:      {asset_path.relative_to(REPO_ROOT)}")
    print(f"   - Workflow mới:    {out_file.name} (Revision {new_snapshot['revision']}, supersedes r{new_snapshot['supersedes_revision']})")
    print(f"   - Câu hỏi {args.question_id} đã chuyển trạng thái: {args.status}")
    print("   - Claim mới:       source_review=pending, technical_review=not_requested.")
    print("     Danh tính người trả lời là tự khai, chưa xác thực. Cần người kiểm nguồn")
    print("     (acquisition.extraction.review) trước khi promote và export.")


if __name__ == "__main__":
    main()
