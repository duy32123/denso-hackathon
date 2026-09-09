# contracts/ — hợp đồng dữ liệu Schema 1.0.0

Package `knowflow_contracts` là **nguồn sự thật duy nhất** cho cả hai đội.
Exporter của đội 1 và importer của đội 2 import cùng một phiên bản ở đây;
không đội nào viết bản validator riêng.

```
contracts/
  schema/knowflow_contracts/   # Pydantic models + V01-V10 + chính sách truy xuất
  json-schema/                 # SINH RA từ models, đừng sửa tay
  CHANGELOG.md                 # phiên bản + 7 quyết định D-01…D-07 (đã chốt 2026-09-09)
```

Ranh giới sở hữu: `models.py` là **Canonical KB** của đội 1. `search.py` và
`retrieval_policy.py` là **dữ liệu dẫn xuất** của đội 2 — sinh lại được từ snapshot,
không bao giờ ghi ngược vào KB, không bao giờ được trích dẫn như bằng chứng.

Ví dụ bundle nằm ở [`data/fixtures/`](../data/fixtures) (10 contract fixture),
sinh lại bằng `python scripts/build_fixtures.py`.

## Dùng như thế nào

```python
from knowflow_contracts import validate_bundle, claim_blockers, snapshot_content_hash

report = validate_bundle("data/fixtures/F01_complete")
if not report.ok:
    raise SystemExit("\n".join(str(i) for i in report.errors))   # từ chối nguyên gói
```

Đội 1 (exporter) — trước khi bàn giao:

```bash
knowflow-contracts validate out/bundle_real_dev -v
```

Đội 2 (importer) — thứ tự bắt buộc: checksum → schema → ID/reference → corpus/split →
staging → search records → build index → chuyển active index.
`decide_reimport(existing_hash, workflow)` trả `new` / `noop` / `conflict`;
`conflict` nghĩa là **cùng khóa khác nội dung ⇒ lỗi, không overwrite**.

Trước khi dùng một claim để khẳng định:

```python
blockers = claim_blockers(claim, workflow, mode=QueryMode.REAL, is_latest_indexed_revision=True)
```

`blockers` rỗng mới được khẳng định. Nếu không rỗng, hiển thị lý do cho người dùng
thay vì im lặng bỏ claim.

Trước khi dựng evidence package (D-05, D-06):

```python
from knowflow_contracts import dedup_claim_hits, spans_multiple_workflows

claims = dedup_claim_hits(hits)          # khóa (workflow_id, revision, claim_id), điểm = max
if spans_multiple_workflows(claims):     # không ghép nhiều quy trình thành một
    ...
```

## Sinh lại JSON Schema

```bash
knowflow-contracts export-json-schema contracts/json-schema
```

## Sửa hợp đồng

1. Sửa `models.py` / `rules.py`
2. Thêm hoặc sửa fixture + `expected.json`
3. Chạy `pytest`
4. Ghi vào `CHANGELOG.md`, đổi `schema_version` nếu đổi tên/kiểu/nghĩa trường hoặc enum
5. Báo cả hai đầu mối kèm migration — không sửa thầm vào đêm trước demo
