"""D1-B / WP6: service ghi phản hồi — hai lời gọi `preview` và `submit`.

Đội 2 gọi sang để dựng màn Bổ sung: người dùng đọc **đúng những gì sẽ được ghi**
trước khi bấm lưu. Hợp đồng: `docs/team2_feedback_contract.md` mục 2.

`preview` **không sửa kho chuẩn**: không ghi snapshot, không ghi source, không đổi
bundle đã xuất. Nó có dựng một bundle trong thư mục tạm để chạy validator chung —
thư mục đó bị xoá ngay sau lời gọi.

`submit` ghi thật, dưới một khoá, và chỉ sau khi validator đã duyệt bundle sẽ xuất.
Hỏng ở bất kỳ bước nào thì hoàn tác toàn bộ: không để lại snapshot mồ côi, source
trỏ tới tệp không có, hay bundle nửa vời.

Preview và submit dùng chung `plan_feedback`, nên bản xem trước không thể lệch với
bản thật. Bước validate cũng đi qua đúng `export_bundle(check_only=True)` mà submit
sẽ dùng, nên lỗi V0x và lỗi bất biến snapshot (D-02) lộ ra **trước** khi ghi.

Ranh giới không được vượt:

- Claim sinh ra luôn `source_review=pending` / `technical_review=not_requested`.
  Xem `feedback_loop`: có phản hồi không phải là đã kiểm nguồn.
- Danh tính người trả lời là **tự khai** — hệ thống chưa có đăng nhập. Phản hồi
  trả `responder_authenticated: false` để UI nói rõ điều đó.
- Chỉ ghi được vào `real` / `dev`. Kho synthetic là dữ liệu dẫn xuất của đội 2;
  `holdout` bị khoá cho tới sau D15.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from knowflow_contracts.issues import Report
from knowflow_contracts.models import NonEmptyStr, Strict
from pydantic import field_validator

from acquisition.export.exporter import SPLITS, ExportError, export_bundle, load_snapshots
from acquisition.extraction.feedback_loop import (
    apply_expert_feedback,
    collect_reserved_ids,
    write_feedback_asset,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_TIMEOUT_S = 10.0


# --- loi ----------------------------------------------------------------------


class FeedbackError(Exception):
    """Goc chung; moi lop con mang mot ma HTTP de doi 2 map thang sang response."""

    http_status = 500


class FeedbackNotFound(FeedbackError):
    """workflow_id / step_id / question_id khong ton tai o revision dang xet."""

    http_status = 404


class FeedbackConflict(FeedbackError):
    """base_revision nguoi dung dang xem khong con la ban moi nhat."""

    http_status = 409

    def __init__(self, message: str, *, conflict: dict[str, Any]):
        super().__init__(message)
        self.conflict = conflict


class FeedbackRejected(FeedbackError):
    """Yeu cau hop le ve cu phap nhung khong duoc phep ghi, hoac se tao bundle hong."""

    http_status = 422

    def __init__(self, message: str, *, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class FeedbackBusy(FeedbackError):
    """Mot lan ghi khac dang chay. Thu lai, khong ghi de len no."""

    http_status = 429


# --- yeu cau ------------------------------------------------------------------


class Responder(Strict):
    """Nguoi tra loi tu khai. CHUA xac thuc: he thong khong co dang nhap."""

    actor_id: NonEmptyStr
    label: NonEmptyStr
    role: NonEmptyStr

    @field_validator("actor_id", "label", "role")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # `NonEmptyStr` chi chan chuoi rong; hop dong muc 4 doi vai tro that,
        # nen mot o toan khoang trang cung phai bi tu choi.
        if not value.strip():
            raise ValueError("không được để trống hoặc chỉ có khoảng trắng")
        return value


class FeedbackRequest(Strict):
    mode: Literal["real", "synthetic"]
    dataset_split: Literal["dev", "holdout"]
    workflow_id: NonEmptyStr
    base_revision: int
    step_id: NonEmptyStr
    target_field: Literal[
        "context",
        "observation",
        "action",
        "rationale",
        "condition",
        "outcome",
        "acceptance_criteria",
    ]
    question_id: str | None = None
    answer_text: NonEmptyStr
    responder: Responder
    language: Literal["vi", "en"] = "vi"


class FeedbackSubmitRequest(FeedbackRequest):
    """Cung yeu cau nhu preview, them mot xac nhan ro rang truoc khi ghi.

    `confirm_base_revision` phai bang `base_revision`: no la chu ky cua nguoi dung
    tren ban preview ho vua doc, khong phai mot truong copy thua.
    """

    confirm_base_revision: int


@dataclass
class FeedbackPlan:
    """Dung mot ban ke hoach cho ca preview lan submit."""

    base_snapshot: dict[str, Any]
    new_snapshot: dict[str, Any]
    source_record: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


# --- doc kho chuan ------------------------------------------------------------


def _snapshot_dir(split: str) -> Path:
    return SPLITS[split]["snapshots"]


def _revisions(workflow_id: str, split: str) -> dict[int, dict[str, Any]]:
    """Moi revision cua workflow trong kho chuan, theo so revision."""
    try:
        snapshots = load_snapshots(_snapshot_dir(split))
    except ExportError as exc:
        raise FeedbackRejected(f"Kho chuẩn đang hỏng, không đọc được: {exc}") from exc
    return {s["revision"]: s for s in snapshots if s["workflow_id"] == workflow_id}


def _changed_fields(base: dict[str, Any], latest: dict[str, Any]) -> list[str]:
    """Liet ke vung da doi giua hai revision, du de UI dung diff cho nguoi doc."""
    changed = []
    for key in ("title", "context", "steps", "claims", "evidence", "relations", "questions",
                "review_events", "lifecycle", "source_ids"):
        if base.get(key) != latest.get(key):
            changed.append(key)
    return changed


# --- lap ke hoach -------------------------------------------------------------


def plan_feedback(request: FeedbackRequest) -> FeedbackPlan:
    """Tinh ra revision N+1 se trong nhu the nao. Khong ghi gi.

    Nem `FeedbackNotFound` / `FeedbackConflict` / `FeedbackRejected` dung theo
    bang ca loi o muc 4 cua hop dong.
    """
    if request.mode != "real":
        raise FeedbackRejected(
            "Chỉ ghi được vào kho real. KB synthetic là dữ liệu dẫn xuất của đội 2, "
            "không phải kho tri thức chuẩn."
        )
    if request.dataset_split != "dev":
        raise FeedbackRejected(
            "Chỉ ghi được vào split dev. Holdout bị khoá cho tới sau khi khoá pipeline D15."
        )

    revisions = _revisions(request.workflow_id, request.dataset_split)
    if not revisions:
        raise FeedbackNotFound(f"Không có workflow '{request.workflow_id}' trong kho chuẩn.")

    latest_revision = max(revisions)
    latest = revisions[latest_revision]

    if request.base_revision > latest_revision:
        raise FeedbackRejected(
            f"base_revision={request.base_revision} lớn hơn revision mới nhất "
            f"({latest_revision}) — bản đang xem không đến từ kho này."
        )
    if request.base_revision != latest_revision:
        base = revisions.get(request.base_revision)
        last_change = (latest.get("change_log") or [{}])[-1]
        raise FeedbackConflict(
            f"Workflow đã có revision mới hơn bản bạn đang xem (r{request.base_revision} "
            f"→ r{latest_revision}).",
            conflict={
                "latest_revision": latest_revision,
                "changed_fields": _changed_fields(base, latest) if base else [],
                "changed_at": last_change.get("changed_at") or latest.get("created_at"),
                "actor_id": last_change.get("actor_id"),
            },
        )

    if not any(s["step_id"] == request.step_id for s in latest["steps"]):
        raise FeedbackNotFound(
            f"Không có step '{request.step_id}' trong {request.workflow_id}@r{latest_revision}."
        )

    question = None
    if request.question_id:
        question = next(
            (q for q in latest.get("questions", []) if q["question_id"] == request.question_id), None
        )
        if question is None:
            raise FeedbackNotFound(
                f"Không có question '{request.question_id}' trong "
                f"{request.workflow_id}@r{latest_revision}."
            )
        if question["status"] != "open":
            raise FeedbackRejected(
                f"Question '{request.question_id}' đang ở trạng thái '{question['status']}', "
                "không còn mở để nhận phản hồi."
            )
        if question["step_id"] != request.step_id or question["target_field"] != request.target_field:
            raise FeedbackRejected(
                f"Question '{request.question_id}' hỏi về "
                f"{question['step_id']}/{question['target_field']}, "
                f"không phải {request.step_id}/{request.target_field}."
            )

    warnings = _collect_warnings(request, latest)

    if question is not None:
        new_snapshot, source_record = apply_expert_feedback(
            snapshot=latest,
            target_question_id=request.question_id,
            expert_name=request.responder.label,
            expert_role=request.responder.role,
            answer_text=request.answer_text,
            target_step_id=request.step_id,
            target_field_role=request.target_field,
            reserved_ids=collect_reserved_ids(request.workflow_id, repo_root=REPO_ROOT),
            answer_language=request.language,
        )
    else:
        new_snapshot, source_record = _apply_without_question(request, latest)

    return FeedbackPlan(
        base_snapshot=latest,
        new_snapshot=new_snapshot,
        source_record=source_record,
        warnings=warnings,
    )


def _collect_warnings(request: FeedbackRequest, latest: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    step = next(s for s in latest["steps"] if s["step_id"] == request.step_id)
    before = step["fields"][request.target_field]
    if before["state"] == "present":
        warnings.append(
            f"Trường {request.target_field} đã có {len(before['claim_ids'])} claim. "
            "Phản hồi được thêm vào bên cạnh, không thay thế claim cũ."
        )

    if request.language != latest["language"]:
        warnings.append(
            f"Phản hồi tiếng '{request.language}' trên workflow tiếng '{latest['language']}'. "
            "Claim.text giữ nguyên văn, không dịch (D-03). Người kiểm nguồn cần xác nhận "
            "cách xử lý trước khi promote."
        )

    if request.question_id is None:
        warnings.append(
            "Không gắn với Question record nào: đây là bổ sung một trường còn thiếu, "
            "không phải trả lời một câu hỏi đang mở."
        )

    return warnings


def _apply_without_question(
    request: FeedbackRequest, latest: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bo sung mot truong con thieu khi chua co Question record.

    `apply_expert_feedback` doi mot question_id; o day khong co, nen tao mot
    Question record `answered` ngay trong revision moi de van truy duoc nguon goc
    cua claim, roi chay dung duong cu.
    """
    seeded = copy.deepcopy(latest)
    reserved = collect_reserved_ids(request.workflow_id, repo_root=REPO_ROOT)
    existing_q = {q["question_id"] for q in seeded.get("questions", [])}
    index = 1
    while f"{request.workflow_id}_Q_{index:03d}" in existing_q:
        index += 1
    question_id = f"{request.workflow_id}_Q_{index:03d}"

    seeded.setdefault("questions", []).append(
        {
            "question_id": question_id,
            "step_id": request.step_id,
            "target_field": request.target_field,
            "reason": "missing",
            "question": (
                f"Trường {request.target_field} của {request.step_id} chưa có trong nguồn; "
                "được bổ sung bằng phản hồi."
            ),
            "status": "open",
            "answer_source_ids": [],
            "resolution_note": None,
        }
    )

    return apply_expert_feedback(
        snapshot=seeded,
        target_question_id=question_id,
        expert_name=request.responder.label,
        expert_role=request.responder.role,
        answer_text=request.answer_text,
        target_step_id=request.step_id,
        target_field_role=request.target_field,
        reserved_ids=reserved,
        answer_language=request.language,
    )


# --- kiem thu truoc khi ghi ---------------------------------------------------


def dry_validate(plan: FeedbackPlan, split: str = "dev", repo_root: Path = REPO_ROOT) -> Report:
    """Chay validator chung tren bundle **se** duoc xuat, khong ghi gi ra kho.

    Di qua dung `export_bundle(check_only=True)` ma submit se dung, nen bat duoc
    ca loi V0x lan loi bat bien snapshot da phat hanh (D-02).
    """
    config = SPLITS[split]
    sources_path: Path = config["sources"]
    new_workflow_id = plan.new_snapshot["workflow_id"]
    new_revision = plan.new_snapshot["revision"]

    with tempfile.TemporaryDirectory(prefix="feedback-preview-") as tmp:
        staging = Path(tmp)
        snapshot_dir = staging / "snapshots"
        snapshot_dir.mkdir()
        for snapshot in load_snapshots(config["snapshots"]):
            name = f"{snapshot['workflow_id']}.r{snapshot['revision']}.json"
            (snapshot_dir / name).write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        (snapshot_dir / f"{new_workflow_id}.r{new_revision}.json").write_text(
            json.dumps(plan.new_snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        sources = [
            json.loads(line)
            for line in sources_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not any(s["source_id"] == plan.source_record["source_id"] for s in sources):
            sources.append(plan.source_record)
        staged_sources = staging / "sources.jsonl"
        staged_sources.write_text(
            "".join(json.dumps(s, ensure_ascii=False, sort_keys=True) + "\n" for s in sources),
            encoding="utf-8",
            newline="\n",
        )

        result = export_bundle(
            split=split,
            sources_path=staged_sources,
            snapshot_dir=snapshot_dir,
            # Bundle that: de check_published_snapshots doi chieu voi ban da phat hanh.
            # check_only=True nen khong co gi duoc ghi vao day.
            out_dir=config["out"],
            bundle_prefix=config["bundle_prefix"],
            check_only=True,
        )
        return result.report


# --- ghi ----------------------------------------------------------------------


@contextmanager
def _store_lock(split: str, timeout: float = LOCK_TIMEOUT_S):
    """Khoa ghi cho kho chuan cua mot split.

    Khong co khoa thi hai lan submit cung doc duoc latest=r1 roi cung ghi
    `<wf>.r2.json`: ban sau de len ban truoc, mat mot revision ma khong ai biet.
    409 chi dung khi viec doc-roi-ghi la lien mach, nen kiem lai latest phai nam
    **trong** khoa nay.
    """
    lock_path = SPLITS[split]["snapshots"].parent / f".feedback.{split}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            handle = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise FeedbackBusy(
                    "Một lần ghi phản hồi khác đang chạy. Thử lại sau vài giây."
                ) from None
            time.sleep(0.05)
    try:
        os.write(handle, f"{os.getpid()}\n".encode())
        os.close(handle)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


@dataclass
class _Rollback:
    """Hoan tac moi thu da ghi neu mot buoc sau that bai.

    Mot lan submit hong phai khong de lai gi: khong snapshot mo coi, khong source
    tro toi tep khong ton tai, khong bundle nua voi.
    """

    created_files: list[Path] = field(default_factory=list)
    restored_bytes: list[tuple[Path, bytes]] = field(default_factory=list)

    def track_new(self, path: Path) -> None:
        self.created_files.append(path)

    def track_existing(self, path: Path) -> None:
        self.restored_bytes.append((path, path.read_bytes()))

    def undo(self) -> None:
        for path, body in reversed(self.restored_bytes):
            path.write_bytes(body)
        for path in reversed(self.created_files):
            path.unlink(missing_ok=True)


def _write_snapshot_exclusively(snapshot: dict[str, Any], split: str) -> Path:
    """Ghi snapshot moi, tu choi neu tep da ton tai.

    `O_EXCL` la chot cuoi ben duoi khoa: mot revision da co tren dia khong bao gio
    bi ghi de, ke ca khi logic ben tren sai.
    """
    name = f"{snapshot['workflow_id']}.r{snapshot['revision']}.json"
    path = SPLITS[split]["snapshots"] / name
    body = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise FeedbackConflict(
            f"{name} đã tồn tại trong kho chuẩn; revision này vừa được ghi bởi một lần khác.",
            conflict={"latest_revision": snapshot["revision"], "changed_fields": [],
                      "changed_at": None, "actor_id": None},
        ) from None
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
    return path


def _append_source(source_record: dict[str, Any], split: str, rollback: _Rollback) -> bool:
    """Them Source moi vao cuoi tep nguon chuan. Tra ve True neu co ghi."""
    path: Path = SPLITS[split]["sources"]
    existing = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for record in existing:
        if record["source_id"] != source_record["source_id"]:
            continue
        if record != source_record:
            raise FeedbackRejected(
                f"Source {source_record['source_id']} đã tồn tại với nội dung khác. "
                "Nguồn là bất biến; không ghi đè."
            )
        return False

    rollback.track_existing(path)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(source_record, ensure_ascii=False, sort_keys=True) + "\n")
    return True


# --- hop dong -----------------------------------------------------------------


def preview(request: FeedbackRequest | dict[str, Any]) -> dict[str, Any]:
    """Tra ve dung nhung gi SE duoc ghi. Khong sua kho chuan.

    Hop dong: docs/team2_feedback_contract.md muc 2.
    """
    if isinstance(request, dict):
        request = FeedbackRequest.model_validate(request)

    plan = plan_feedback(request)
    report = dry_validate(plan, split=request.dataset_split)

    base = plan.base_snapshot
    new = plan.new_snapshot
    step = next(s for s in base["steps"] if s["step_id"] == request.step_id)
    new_step = next(s for s in new["steps"] if s["step_id"] == request.step_id)

    known_evidence = {e["evidence_id"] for e in base.get("evidence", [])}
    known_claims = {c["claim_id"] for c in base.get("claims", [])}
    known_questions = {q["question_id"] for q in base.get("questions", [])}

    new_evidence = [e for e in new["evidence"] if e["evidence_id"] not in known_evidence]
    new_claims = [c for c in new["claims"] if c["claim_id"] not in known_claims]

    transition = None
    for question in new.get("questions", []):
        before = next(
            (q for q in base.get("questions", []) if q["question_id"] == question["question_id"]),
            None,
        )
        if before is None and question["question_id"] not in known_questions:
            transition = {
                "question_id": question["question_id"],
                "from": None,
                "to": question["status"],
                "created_by_this_change": True,
            }
        elif before is not None and before["status"] != question["status"]:
            transition = {
                "question_id": question["question_id"],
                "from": before["status"],
                "to": question["status"],
                "created_by_this_change": False,
            }

    return {
        "mode": request.mode,
        "dataset_split": request.dataset_split,
        "workflow_id": new["workflow_id"],
        "base_revision": base["revision"],
        "next_revision": new["revision"],
        "conflict": None,
        "source": {
            "source_id": plan.source_record["source_id"],
            "source_kind": plan.source_record["source_kind"],
            "language": plan.source_record["language"],
            "raw_text": plan.source_record["raw_text"],
            "asset_uri": plan.source_record["asset_uri"],
        },
        "new_evidence": new_evidence,
        "new_claims": new_claims,
        "field_changes": [
            {
                "step_id": request.step_id,
                "field": request.target_field,
                "before": step["fields"][request.target_field],
                "after": new_step["fields"][request.target_field],
            }
        ],
        "question_transition": transition,
        "change_log": new["change_log"][-1],
        # He thong chua co dang nhap: UI phai noi ro ten/vai tro la tu khai.
        "responder_authenticated": False,
        "validation": {
            "ok": report.ok,
            "errors": [str(i) for i in report.errors],
            "warnings": [str(i) for i in report.warnings],
        },
        "warnings": plan.warnings,
    }


def submit(request: FeedbackSubmitRequest | dict[str, Any]) -> dict[str, Any]:
    """Ghi thật: revision N+1 + Source + tệp nguyên văn + bundle đã xuất.

    Hợp đồng: docs/team2_feedback_contract.md mục 2. Thứ tự và bảo đảm:

    1. Mọi thứ nằm trong khoá ghi, và `plan_feedback` chạy **lại** bên trong khoá —
       preview của người dùng có thể đã cũ vài phút.
    2. Validator chạy **trước** khi ghi bất cứ thứ gì. Bundle hỏng thì không có
       revision nào được tạo, trả 422 kèm danh sách mã V0x.
    3. Bước nào lỗi thì hoàn tác toàn bộ những gì lần gọi này đã ghi.
    4. Claim mới vẫn `pending`: cần người kiểm nguồn trước khi coi là tri thức
       đã đối chiếu. Phản hồi làm tri thức **dày thêm**, không làm nó **đúng thêm**.
    """
    if isinstance(request, dict):
        request = FeedbackSubmitRequest.model_validate(request)

    if request.confirm_base_revision != request.base_revision:
        raise FeedbackRejected(
            f"confirm_base_revision={request.confirm_base_revision} không khớp "
            f"base_revision={request.base_revision}: bản xem trước và bản lưu không cùng gốc."
        )

    split = request.dataset_split

    with _store_lock(split):
        # Đọc lại kho bên trong khoá: preview người dùng đang xem có thể đã cũ.
        plan = plan_feedback(request)

        report = dry_validate(plan, split=split)
        if not report.ok:
            raise FeedbackRejected(
                "Bundle sau khi ghi sẽ không qua validator; không tạo revision nào.",
                errors=[str(issue) for issue in report.errors],
            )

        rollback = _Rollback()
        try:
            asset_path = write_feedback_asset(plan.source_record, repo_root=REPO_ROOT)
            rollback.track_new(asset_path)

            _append_source(plan.source_record, split, rollback)

            snapshot_path = _write_snapshot_exclusively(plan.new_snapshot, split)
            rollback.track_new(snapshot_path)

            config = SPLITS[split]
            result = export_bundle(
                split=split,
                sources_path=config["sources"],
                snapshot_dir=config["snapshots"],
                out_dir=config["out"],
                bundle_prefix=config["bundle_prefix"],
            )
            if not result.report.ok:
                raise FeedbackRejected(
                    "Export bundle thất bại sau khi ghi; đã hoàn tác.",
                    errors=[str(issue) for issue in result.report.errors],
                )
        except ExportError as exc:
            rollback.undo()
            raise FeedbackRejected(f"Export bundle bị từ chối: {exc}") from exc
        except Exception:
            rollback.undo()
            raise

    base = plan.base_snapshot
    new = plan.new_snapshot
    known_evidence = {e["evidence_id"] for e in base.get("evidence", [])}
    known_claims = {c["claim_id"] for c in base.get("claims", [])}

    return {
        "workflow_id": new["workflow_id"],
        "revision": new["revision"],
        "supersedes_revision": new["supersedes_revision"],
        "created_source_id": plan.source_record["source_id"],
        "created_claim_ids": [c["claim_id"] for c in new["claims"] if c["claim_id"] not in known_claims],
        "created_evidence_ids": [
            e["evidence_id"] for e in new["evidence"] if e["evidence_id"] not in known_evidence
        ],
        "bundle_export": str(SPLITS[split]["out"].relative_to(REPO_ROOT)).replace("\\", "/"),
        "bundle_id": result.bundle_id,
        "snapshot_path": str(snapshot_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "asset_path": plan.source_record["asset_uri"],
        # Đội 2 phải import lại và build index mới thì câu trả lời mới đổi.
        "reindex_required": True,
        "responder_authenticated": False,
        # Người kiểm nguồn vẫn còn nợ: claim mới chưa được đối chiếu.
        "review_required": True,
        "warnings": plan.warnings,
    }
