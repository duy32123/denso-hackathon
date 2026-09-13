"""Extraction Pipeline for KnowFlow AI (Schema 1.0.0).

Reads transcript and metadata, queries OpenAI LLM API (v1+), validates the response
using Pydantic models from schema_v1.py (FieldRef, StepRecord, WorkflowBundle),
and saves the validated draft to `data/workflows/drafts/`.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

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


# Load .env file from repository root
load_dotenv(REPO_ROOT / ".env")

from acquisition.extraction.schema_v1 import (
    FieldState,
    WorkflowBundle,
)
from acquisition.extraction.exporter import (
    ExportSummary,
    export_schema_v1_bundle,
    sha256_file,
)
from acquisition.extraction.llm_adapters import get_llm_adapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("extraction_pipeline")

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
    logger.warning(f"Không tìm thấy source_id '{source_id}' trong {metadata_path}. Sử dụng metadata rỗng.")
    return {"source_id": source_id, "title": "Unknown Title"}


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
) -> WorkflowBundle:
    """Executes the end-to-end extraction pipeline:
    1. Reads transcript & metadata.
    2. Calls LLM via Adapter Pattern (Gemini, OpenAI, DeepSeek, LiteLLM).
    3. Validates with Pydantic Schema 1.0.0 (WorkflowBundle).
    4. Writes validated draft to data/workflows/drafts/.
    5. Exports Schema 1.0.0 hand-off bundle (manifest, sources, workflows, lineage).
    """
    # Resolve paths
    transcript_file = transcript_path or (
        REPO_ROOT / "acquisition" / "preprocessing" / "transcripts" / source_id / "corrected.json"
    )
    metadata_file = metadata_path or (REPO_ROOT / "data" / "sources" / "haas_pilot_sources.jsonl")
    output_file = output_path or (REPO_ROOT / "data" / "workflows" / "drafts" / f"{source_id}.draft.json")
    target_bundle_dir = bundle_dir or (REPO_ROOT / "data" / "workflows" / "drafts" / f"bundle_{source_id}")

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

    # 2. Instantiate LLM Adapter via Factory
    try:
        adapter = get_llm_adapter(provider=provider, model=model)
    except Exception as err:
        logger.error(f"❌ Lỗi cấu hình LLM Adapter: {err}")
        sys.exit(1)

    # 3. Call LLM Adapter to generate structured output
    logger.debug(f"Đang gửi request tới {adapter.__class__.__name__} (Model: {adapter.model})...")
    system_prompt = (
        "You are a precise technical data extraction engine that outputs valid JSON only adhering to Schema 1.0.0."
    )
    try:
        raw_json_output = adapter.generate_structured_output(
            prompt=prompt,
            schema_class=WorkflowBundle,
            system_instruction=system_prompt,
        )
        logger.debug(f"Đã nhận phản hồi từ {adapter.__class__.__name__} thành công.")
    except Exception as e:
        logger.error(f"❌ Lỗi khi gọi {adapter.__class__.__name__}: {e}")
        sys.exit(1)

    # 4. Validate output with Pydantic Schema 1.0.0
    logger.debug("Đang kiểm thực kết quả trả về bằng Pydantic models (schema_v1)...")
    try:
        bundle = WorkflowBundle.from_llm_json(raw_json_output)
        logger.debug(f"Kiểm thực thành công! Workflow: {bundle.workflow_id}, Tổng số bước: {len(bundle.steps)}")
        for step in bundle.steps:
            present_roles = [f.role for f in step.fields if f.state == FieldState.PRESENT]
            logger.debug(f"   - Bước {step.display_order} [{step.step_id}]: '{step.title}' (Fields: {', '.join(present_roles)})")
    except Exception as val_err:
        logger.error(f"❌ Lỗi kiểm thực Schema 1.0.0 cho dữ liệu từ LLM: {val_err}")
        # Lưu file debug nếu lỗi schema để tiện phân tích
        debug_path = output_file.with_suffix(".raw_error.json")
        with open(debug_path, "w", encoding="utf-8") as df:
            df.write(raw_json_output)
        logger.warning(f"Đã lưu phản hồi thô gặp lỗi tại: {debug_path}")
        sys.exit(1)

    # 5. Write validated output to destination
    output_file.parent.mkdir(parents=True, exist_ok=True)
    draft_dict = bundle.to_draft_dict()
    with open(output_file, "w", encoding="utf-8") as out_f:
        json.dump(draft_dict, out_f, indent=2, ensure_ascii=False)
    logger.info(f"📄 Đã lưu Draft JSON: {output_file.name} ({len(bundle.steps)} bước)")

    # 6. Export Schema 1.0.0 hand-off bundle
    if export_bundle:
        lineage_meta = {
            "provider": adapter.__class__.__name__,
            "model": adapter.model,
            "source_id": source_id,
            "transcript_file": str(transcript_file.relative_to(REPO_ROOT)),
            "transcript_sha256": sha256_file(transcript_file),
            "metadata_file": str(metadata_file.relative_to(REPO_ROOT)),
            "metadata_sha256": sha256_file(metadata_file),
            "draft_output": str(output_file.relative_to(REPO_ROOT)),
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
    )


if __name__ == "__main__":
    main()
