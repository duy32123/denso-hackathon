# KnowFlow AI — MVP A2

Biến video dịch vụ thành tri thức **kiểm tra được**: mỗi bước có claim, mỗi claim có
bằng chứng mở được, phần chưa biết được giữ lại và chuyển thành câu hỏi.

Tài liệu gốc nằm ở [docs/](docs): schema chung, kế hoạch đội 1 (video → kho tri thức),
kế hoạch đội 2 (synthetic KB → RAG → UI).

Hướng trình bày A2: [ý tưởng và kế hoạch sáu tuần](docs/a2_idea_submission.md),
[demo bản đồ tri thức](docs/a2_knowledge_map_demo.md). Giao diện có bản đồ Step–Relation,
bốn nhóm “làm gì / khi nào / vì sao / kiểm chứng” và chuyển câu hỏi thiếu sang form bổ sung.

**Không gian tri thức 3D:** mở `/space` trên server local để xoay, zoom, chọn nút,
mở bằng chứng và trình chiếu câu chuyện. Xem [hướng dẫn và phạm vi](docs/a2_knowledge_space_3d.md).
Chọn **Theo tình huống** để theo nhánh có điều kiện, hoặc **Tri thức thay đổi**
để đối chiếu các phiên bản và mở bằng chứng trước/sau. Chuẩn bị index lịch sử bằng
`python -m scripts.prepare_knowledge_space` theo hướng dẫn trên.
**Đường truy xuất** phát trace thực của backend trên đồ thị, có xem từng chặng,
phát lại và tùy chọn tạo câu trả lời AI. Xem [kịch bản demo](docs/a2_retrieval_route_demo.md).

## Bắt đầu

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"

python scripts/build_fixtures.py          # sinh 10 contract fixture
pytest                                    # bộ contract tests dùng chung cho hai đội
knowflow-contracts validate data/fixtures/F01_complete -v
```

Không có `uv` thì dùng `python -m venv .venv` rồi `pip install -e ".[dev]"`.

## Chạy B0 và xử lý lại draft

PowerShell không bắt buộc activate môi trường; có thể dùng `uv run python` hoặc
`.\.venv\Scripts\python.exe`. Chạy từ thư mục gốc repo:

```powershell
uv run python -m acquisition.extraction.extraction_pipeline --source-id SRC_HAAS_0005 --dry-run
```

Chạy thật cần SDK của provider và API key trong `.env`. Để xử lý lại draft đã có
mà không gọi API, dùng `--from-draft`:

```powershell
uv run python -m acquisition.extraction.extraction_pipeline --source-id SRC_HAAS_0005 --from-draft data/workflows/drafts/SRC_HAAS_0005.test.draft.json --output data/workflows/drafts/SRC_HAAS_0005.test.normalized.draft.json --bundle-dir data/workflows/drafts/bundle_SRC_HAAS_0005_test --verbose
uv run python -m acquisition.extraction.compile_workflow data/workflows/drafts/SRC_HAAS_0005.test.normalized.draft.json
uv run knowflow-contracts validate data/workflows/drafts/bundle_SRC_HAAS_0005_test -v
```

Pipeline giữ JSON trước chuẩn hóa cạnh output với hậu tố `.raw.json`, tách các
evidence span không liên tiếp rồi compile và validate trước khi ghi draft.
Lỗi compile/contract sẽ dừng chương trình với exit code 1, giữ bản thô để kiểm tra;
không thay draft hoặc bundle hiện có bằng kết quả lỗi. `--no-bundle` vẫn kiểm tra
compile và contract. Đường dẫn tương đối và tuyệt đối đều được hỗ trợ.

`--from-draft` giữ file đầu vào; nếu bỏ `--output`, tạo file `.normalized.draft.json`
riêng. Provider/model của bản cũ chỉ được ghi vào lineage nếu người chạy truyền
`--provider`/`--model` và được đánh dấu `user_supplied`; không gán phiên bản prompt
hiện tại cho bản cũ. Bundle B0 thử nghiệm vẫn có claims `source_review=pending`;
cần review trước khi promote và bàn giao qua `acquisition.export.exporter`.

## Bản đồ repo

D2-A xem [retrieval/README.md](retrieval/README.md): importer bundle, snapshot theo
revision, search records và truy xuất BM25/vector/hybrid với bộ lọc context.
Có lệnh build embedding Gemini và query trên bundle thật; chưa có answer generator/UI.

| Thư mục | Chủ | Nội dung |
|---|---|---|
| [contracts/](contracts) | hai đội | Schema 1.0.0: models, validator V01–V10, chính sách truy xuất. **Nguồn sự thật duy nhất.** |
| [data/fixtures/](data/fixtures) | hai đội | 10 contract fixture + `expected.json` do người kiểm chốt |
| [acquisition/](acquisition) | đội 1 | catalog, tiền xử lý media/ASR, extraction, review, exporter |
| [retrieval/](retrieval) | đội 2 | importer, indexing, retrieval, generation, evaluation |
| [apps/](apps) | đội 2 | UI hỏi đáp và UI review |
| [tests/](tests) | hai đội | contract / integration / end-to-end |

## Bất biến của hệ thống

Bốn điều dưới đây không được vi phạm ở bất kỳ tầng nào — validator chặn hầu hết,
phần còn lại là kỷ luật của người viết code:

1. **Không biết phải biểu diễn được.** Thiếu dữ liệu nằm ở `FieldRef.state`, không tạo
   claim giả để lấp cột. Không bao giờ dùng kiến thức nền của LLM để điền `rationale`.
2. **Không trộn corpus.** `real` không đọc `synthetic` ở bất kỳ bước nào — kể cả fallback,
   cache hay neighbor expansion. Cache key phải chứa `mode`, `split`, `index_build_id`.
3. **Hai mức kiểm tra là khác nhau.** `source_checked` = trung thực với nguồn.
   `expert_validated` = đúng kỹ thuật trong phạm vi được nêu. Video của kênh chính hãng
   **không** tự động là `expert_validated`.
4. **Phiên bản bất biến.** Câu trả lời giữ `workflow_id`, `revision`, `claim_id`, `evidence_id`.
   Cùng khóa khác nội dung là lỗi, không phải overwrite.

Trạng thái hợp đồng và bảy quyết định D-01…D-07 (đã chốt 2026-09-09): [contracts/CHANGELOG.md](contracts/CHANGELOG.md).
