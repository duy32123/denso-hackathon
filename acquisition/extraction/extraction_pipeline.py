"""Extraction Pipeline for KnowFlow AI (Schema 1.0.0).

Reads transcript and metadata, calls an LLM or reuses a saved draft, then
normalizes, compiles and contract-validates the output before reporting success.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Setup repository root and module import path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

# Load .env file from repository root if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from acquisition.extraction.schema_v1 import (
    FieldState,
    WorkflowBundle,
)
from acquisition.extraction.exporter import (
    ExportSummary,
    export_schema_v1_bundle,
    prepare_draft,
    sha256_bytes,
    sha256_file,
)
from acquisition.extraction import compile_workflow as cw
from acquisition.extraction.llm_adapters import get_llm_adapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("extraction_pipeline")
PROMPT_VERSION = "b0-transcript-0.2.0"

# Silence noisy third-party libraries (Google GenAI AFC warnings, HTTP requests)
for noisy_name in ("google", "google_genai", "google.genai", "urllib3", "httpx", "httpcore"):
    logging.getLogger(noisy_name).setLevel(logging.ERROR)


def load_json(filepath: Path) -> Dict[str, Any]:
    """Loads a JSON file."""
    if not filepath.exists():
        raise FileNotFoundError(f"File không tồn tại: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_source_metadata(metadata_path: Path, source_id: str) -> Dict[str, Any]:
    """Finds and returns the metadata record for the given source_id from a JSONL file."""
    if not metadata_path.exists():
        raise FileNotFoundError(f"File metadata không tồn tại: {metadata_path}")
    with open(metadata_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("source_id") == source_id:
                return record
    raise ValueError(f"Không tìm thấy source_id '{source_id}' trong {metadata_path}.")


def _lineage_path(path: Path) -> str:
    """Use repo-relative paths when possible, absolute paths for external files."""
    resolved = path.resolve()
    return resolved.relative_to(REPO_ROOT).as_posix() if resolved.is_relative_to(REPO_ROOT) else str(resolved)


def format_transcript_with_pool_ids(utterances: list[dict], source_id: str) -> str:
    """Formats transcript utterances with standardized candidate pool IDs: [source_id:U0001]."""
    lines = []
    for i, u in enumerate(utterances):
        uid = f"{source_id}:U{i+1:04d}"
        start_ms = u.get("start_ms", 0)
        end_ms = u.get("end_ms", 0)
        text = u.get("text", "").strip()
        lines.append(f"[{uid}] ({start_ms} - {end_ms}): {text}")
    return "\n".join(lines)


def build_extraction_prompt(source_id: str, metadata: Dict[str, Any], formatted_transcript: str) -> str:
    """Builds the comprehensive technical extraction prompt adhering to Schema 1.0.0."""
    title = metadata.get("title", "Technical Procedure")
    publisher = metadata.get("publisher", "Haas Automation, Inc.")
    presenter = metadata.get("presenter", "Technician")

    prompt = f"""Bạn là một chuyên gia phân tích tài liệu kỹ thuật bảo trì thiết bị (Knowledge Extraction AI) của dự án KnowFlow AI.
Hãy đọc kỹ Metadata và Transcript bên dưới để trích xuất quy trình thành một đối tượng JSON tuân thủ nghiêm ngặt chuẩn Schema 1.0.0.

--- THÔNG TIN NGUỒN ---
Source ID: {source_id}
Tiêu đề: {title}
Nhà phát hành: {publisher}
Người thực hiện: {presenter}

--- TRANSCRIPT (Đã đánh mã Evidence Pool ID) ---
{formatted_transcript}

--- QUY TẮC TRÍCH XUẤT (Schema 1.0.0 Contract) ---
1. Định dạng JSON gốc (Root fields):
   - "schema_version": "1.0.0"
   - "workflow_id": "B0_{source_id}"
   - "revision": 1
   - "source_type": "real"
   - "dataset_split": "dev"
   - "title": "{title}"
   - "language": "en"
   - "source_ids": ["{source_id}"]
   - "context": {{
       "manufacturer": "Haas",
       "subsystem": "Side Mount Tool Changer (SMTC)",
       "task_type": "maintenance",
       "symptoms": [],
       "alarm_codes": [],
       "components": []
     }}
   - "steps": [ danh sách các StepRecord ]

2. Cấu trúc mỗi phần tử trong "steps" (StepRecord):
   - "step_id": Mã định danh bước tuần tự, ví dụ "ST_001", "ST_002", v.v.
   - "display_order": Số nguyên thứ tự bước bắt đầu từ 1.
   - "title": Tiêu đề ngắn gọn tóm tắt hành động kỹ thuật của bước.
   - "fields": Danh sách bắt buộc 7 đối tượng FieldRef ứng với 7 roles chuẩn:
     ["context", "observation", "action", "rationale", "condition", "outcome", "acceptance_criteria"].
     Mỗi FieldRef gồm:
       * "role": Tên role (bắt buộc 1 trong 7 vai trò trên).
       * "state": "present" (nếu có căn cứ trong transcript), "missing" (nếu transcript không đề cập), hoặc "ambiguous".
       * "claims": Danh sách các ClaimRecord chi tiết nếu state = "present" (nếu state = "missing", claims để rỗng []).
         Mỗi ClaimRecord gồm:
           - "text": Phát biểu nguyên tử, rõ ràng, giữ trọn ý nghĩa kỹ thuật.
           - "role": Trùng với vai trò của field này (ví dụ "action").
           - "evidence_type": "stated" (lời nói trực tiếp), "observed" (quan sát hình ảnh), hoặc "inferred".
           - "evidence": Danh sách candidate pool ID từ transcript, ví dụ [["{source_id}:U0001", "{source_id}:U0002"]] (bọc trong list).
             Mỗi nhóm chỉ chứa các câu thoại liên tiếp của cùng nguồn. Nếu không liên tiếp, tách thành nhiều nhóm,
             ví dụ [["{source_id}:U0001"], ["{source_id}:U0003"]]. Không tự thêm câu ở giữa hoặc tạo ID không có trong transcript.
           - "explanation": Giải thích ngắn gọn tại sao câu thoại đó làm bằng chứng hỗ trợ cho claim.
   - "questions": Nếu các trường quan trọng (như rationale, condition, acceptance_criteria) bị missing hoặc ambiguous, tạo câu hỏi kỹ thuật trong danh sách này để kỹ sư rà soát.

3. YÊU CẦU ĐẦU RA:
   - Chỉ trả về duy nhất 1 JSON object hợp lệ.
   - Tuyệt đối không thêm text giải thích ngoài JSON, không bọc markdown backtick.
"""
    return prompt


def run_extraction_pipeline(
    source_id: str = "SRC_HAAS_0005",
    transcript_path: Optional[Path] = None,
    metadata_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    bundle_dir: Optional[Path] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    export_bundle: bool = True,
    dry_run: bool = False,
    from_draft: Optional[Path] = None,
) -> WorkflowBundle:
    """Executes the end-to-end extraction pipeline:
    1. Reads transcript & metadata.
    2. Calls LLM via Adapter Pattern (Gemini, OpenAI, DeepSeek, LiteLLM).
    3. Saves raw output, normalizes evidence, compiles and validates the snapshot.
    4. Exports the bundle and saves the same normalized draft for standalone review.
    With from_draft, no LLM adapter is instantiated and the input is preserved.
    """
    # Resolve paths
    if from_draft and dry_run:
        raise ValueError("Không kết hợp --from-draft với --dry-run.")
    saved_draft = Path(from_draft).resolve() if from_draft else None
    transcript_file = (transcript_path or (
        REPO_ROOT / "acquisition" / "preprocessing" / "transcripts" / source_id / "corrected.json"
    )).resolve()
    metadata_file = (metadata_path or (REPO_ROOT / "data" / "sources" / "haas_pilot_sources.jsonl")).resolve()
    default_output = (
        saved_draft.with_name(f"{saved_draft.stem.removesuffix('.draft')}.normalized.draft.json")
        if saved_draft else REPO_ROOT / "data" / "workflows" / "drafts" / f"{source_id}.draft.json"
    )
    output_file = (output_path or default_output).resolve()
    raw_path = output_file.with_suffix(".raw.json")
    if saved_draft in (output_file, raw_path):
        raise ValueError("--output phải khác --from-draft để giữ nguyên bản đầu vào.")
    default_bundle = (
        output_file.parent / f"bundle_{output_file.stem.removesuffix('.draft')}"
        if saved_draft else REPO_ROOT / "data" / "workflows" / "drafts" / f"bundle_{source_id}"
    )
    target_bundle_dir = (bundle_dir or default_bundle).resolve()

    logger.info(f"🚀 Bắt đầu trích xuất quy trình cho {source_id} (Provider: {provider or 'auto'}, Model: {model or 'default'})...")
    logger.debug(f"Transcript: {transcript_file}")
    logger.debug(f"Metadata:   {metadata_file}")
    logger.debug(f"Draft Out:  {output_file}")
    if export_bundle:
        logger.debug(f"Bundle Out: {target_bundle_dir}")

    # 1. Load inputs
    transcript_data = load_json(transcript_file)
    utterances = transcript_data.get("utterances", [])
    logger.debug(f"Đã nạp {len(utterances)} câu thoại (utterances) từ transcript.")

    metadata = load_source_metadata(metadata_file, source_id)
    logger.debug(f"Đã nạp metadata: '{metadata.get('title', 'Unknown')}'")

    formatted_transcript = format_transcript_with_pool_ids(utterances, source_id)
    prompt = build_extraction_prompt(source_id, metadata, formatted_transcript)

    if dry_run:
        logger.info(f"[DRY-RUN] Nạp dữ liệu và tạo prompt thành công ({len(prompt)} ký tự).")
        logger.debug(f"[DRY-RUN] Prompt preview:\n{prompt[:500]}...\n")
        from acquisition.extraction.schema_v1 import create_empty_step
        return WorkflowBundle(
            workflow_id=f"B0_{source_id}",
            title=metadata.get("title", "Dry Run Workflow"),
            steps=[create_empty_step("ST_001", 1, "Dry Run Placeholder Step")]
        )

    # 2. Acquire JSON, optionally reusing an existing response without API access.
    if saved_draft:
        raw_json_output = saved_draft.read_text(encoding="utf-8")
        run_lineage = {
            "mode": "from_draft",
            "input_draft": _lineage_path(saved_draft),
            "input_draft_sha256": sha256_file(saved_draft),
            "provider": provider,
            "model": model,
            "model_provenance": "user_supplied" if provider or model else "unknown",
        }
        logger.info(f"Đọc lại draft {saved_draft.name}; không gọi LLM API.")
    else:
        adapter = get_llm_adapter(provider=provider, model=model)
        logger.debug(f"Đang gửi request tới {adapter.__class__.__name__} (Model: {adapter.model})...")
        system_prompt = "You are a precise technical data extraction engine that outputs valid JSON only adhering to Schema 1.0.0."
        try:
            raw_json_output = adapter.generate_structured_output(
                prompt=prompt,
                schema_class=WorkflowBundle,
                system_instruction=system_prompt,
            )
        except Exception as err:
            raise RuntimeError(f"Lỗi khi gọi {adapter.__class__.__name__}: {err}") from err
        run_lineage = {
            "mode": "llm",
            "provider": adapter.__class__.__name__,
            "model": adapter.model,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "system_prompt_sha256": sha256_bytes(system_prompt.encode("utf-8")),
        }

    # Preserve exact input even if Pydantic, compilation or export fails later.
    output_file.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_json_output, encoding="utf-8", newline="\n")
    logger.info(f"Đã giữ bản thô: {raw_path}")

    # 4. Validate output with Pydantic Schema 1.0.0
    logger.debug("Đang kiểm thực kết quả trả về bằng Pydantic models (schema_v1)...")
    try:
        bundle = WorkflowBundle.from_llm_json(raw_json_output)
        if bundle.source_ids and bundle.source_ids != [source_id]:
            raise ValueError(f"source_ids {bundle.source_ids} không khớp --source-id {source_id}.")
        draft_dict = prepare_draft(bundle, metadata)
        snapshot = cw.compile_draft(draft_dict)
        # The export branch validates against its actual Source record in staging.
        # Draft-only runs validate against the same supplied Source metadata.
        if not export_bundle:
            result = cw.check_snapshot(snapshot, draft_dict["dataset_split"], source_records=[metadata])
            if not result.report.ok:
                raise ValueError("\n".join(str(issue) for issue in result.report.errors))
            for issue in result.report.warnings:
                logger.warning(str(issue))
        logger.debug(f"Compile thành công! Workflow: {bundle.workflow_id}, Tổng số bước: {len(bundle.steps)}")
        for step in bundle.steps:
            present_roles = [f.role for f in step.fields if f.state == FieldState.PRESENT]
            logger.debug(f"   - Bước {step.display_order} [{step.step_id}]: '{step.title}' (Fields: {', '.join(present_roles)})")
    except Exception as val_err:
        raise ValueError(f"Draft không hợp lệ: {val_err}. Bản thô: {raw_path}") from val_err

    # 6. Export Schema 1.0.0 hand-off bundle
    if export_bundle:
        lineage_meta = {
            **run_lineage,
            "source_id": source_id,
            "transcript_file": _lineage_path(transcript_file),
            "transcript_sha256": sha256_file(transcript_file),
            "metadata_file": _lineage_path(metadata_file),
            "metadata_sha256": sha256_file(metadata_file),
            "draft_output": _lineage_path(output_file),
            "raw_output": _lineage_path(raw_path),
            "raw_sha256": sha256_file(raw_path),
        }
        summary: ExportSummary = export_schema_v1_bundle(
            bundle=bundle,
            source_record=metadata,
            out_dir=target_bundle_dir,
            pipeline_lineage=lineage_meta,
            compile_snapshot=True,
        )
        logger.debug(f"Chi tiết Bundle {summary.bundle_id}:")
        logger.debug(f"   - Manifest:  {summary.manifest_path.name}")
        logger.debug(f"   - Sources:   {summary.sources_path.name} ({summary.counts.get('sources')} records)")
        logger.debug(f"   - Workflows: {summary.workflows_path.name} ({summary.counts.get('workflows')} records, {summary.counts.get('claims')} claims)")
        logger.debug(f"   - Lineage:   {summary.lineage_path.name} (SHA: {summary.checksums.get('lineage.json', '')[:12]}...)")

    # Save exactly the draft compiled above, after all required checks have passed.
    output_file.write_text(json.dumps(draft_dict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    logger.info(f"📄 Đã lưu Draft JSON: {output_file.name} ({len(bundle.steps)} bước)")
    logger.info(f"🎉 Hoàn tất quy trình trích xuất cho {source_id}!")
    return bundle


def main():
    parser = argparse.ArgumentParser(
        description="KnowFlow AI - Pipeline trích xuất quy trình từ video transcript bằng Adapter Pattern (Schema 1.0.0)."
    )
    parser.add_argument(
        "--source-id",
        type=str,
        default="SRC_HAAS_0005",
        help="Mã định danh video/nguồn (mặc định: SRC_HAAS_0005)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=["gemini", "openai", "deepseek", "litellm"],
        help="LLM Provider sử dụng (gemini, openai, deepseek, litellm). Mặc định: tự động phát hiện qua model hoặc biến LLM_PROVIDER.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Tên mô hình LLM (mặc định: gemini-3.6-flash cho Gemini, gpt-4o cho OpenAI, deepseek-chat cho DeepSeek)",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        default=None,
        help="Đường dẫn file transcript corrected.json",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=None,
        help="Đường dẫn file metadata sources.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Đường dẫn file draft JSON đầu ra (mặc định lưu tại data/workflows/drafts/{source_id}.draft.json)",
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=None,
        help="Thư mục xuất Bundle Schema 1.0.0 (mặc định: data/workflows/drafts/bundle_{source_id})",
    )
    parser.add_argument(
        "--from-draft",
        type=Path,
        help="Đọc draft đã lưu, chuẩn hóa và compile/export lại mà không gọi LLM. Mặc định tạo file .normalized.draft.json riêng.",
    )
    parser.add_argument(
        "--no-bundle",
        action="store_true",
        help="Bỏ qua bước xuất Bundle Schema 1.0.0 (chỉ ghi file draft)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy thử nghiệm kiểm tra nạp dữ liệu và cấu hình mà không gọi API tốn chi phí",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Bật chế độ hiển thị chi tiết (DEBUG level), bao gồm cấu trúc từng bước và cảnh báo hợp đồng",
    )

    args = parser.parse_args()

    # Configure dynamic log level
    target_level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger().setLevel(target_level)
    logger.setLevel(target_level)
    logging.getLogger("extraction_exporter").setLevel(target_level)
    logging.getLogger("llm_adapters").setLevel(target_level)

    try:
        run_extraction_pipeline(
            source_id=args.source_id,
            transcript_path=args.transcript,
            metadata_path=args.metadata,
            output_path=args.output,
            bundle_dir=args.bundle_dir,
            provider=args.provider,
            model=args.model,
            export_bundle=not args.no_bundle,
            dry_run=args.dry_run,
            from_draft=args.from_draft,
        )
    except (ValueError, OSError, RuntimeError, ImportError) as err:
        logger.error(f"❌ {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
