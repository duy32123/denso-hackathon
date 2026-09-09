# KnowFlow AI — MVP A2

Biến video dịch vụ thành tri thức **kiểm tra được**: mỗi bước có claim, mỗi claim có
bằng chứng mở được, phần chưa biết được giữ lại và chuyển thành câu hỏi.

Tài liệu gốc nằm ở [docs/](docs): schema chung, kế hoạch đội 1 (video → kho tri thức),
kế hoạch đội 2 (synthetic KB → RAG → UI).

## Bắt đầu

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"

python scripts/build_fixtures.py          # sinh 10 contract fixture
pytest                                    # bộ contract tests dùng chung cho hai đội
knowflow-contracts validate data/fixtures/F01_complete -v
```

Không có `uv` thì dùng `python -m venv .venv` rồi `pip install -e ".[dev]"`.

## Bản đồ repo

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
