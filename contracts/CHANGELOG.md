# Changelog hợp đồng dữ liệu

Mọi thay đổi hợp đồng phải: (1) sửa validator và fixture trước, (2) rồi mới cập nhật
producer của đội 1 / importer của đội 2, (3) trong cùng một mốc tích hợp.

---

## 1.0.0 — chưa ký nhận

Bản cài đặt đầu tiên của `01_Schema_chung_KnowFlow_AI.docx`. Gồm:

- `knowflow_contracts.models` — Pydantic models cho manifest, source, workflow snapshot,
  và hợp đồng API (`QueryRequest` / `AnswerResponse`). `extra="forbid"` ở mọi model.
- `knowflow_contracts.rules` — V01–V10.
- `knowflow_contracts.eligibility` — chính sách "claim nào được dùng để khẳng định" (mục 7).
- `knowflow_contracts.search` — hợp đồng search record (dẫn xuất, đội 2 sở hữu).
- `knowflow_contracts.retrieval_policy` — dedup claim và ràng buộc ghép quy trình.
- `data/fixtures/F01…F10` — 10 contract fixture, mỗi bộ kèm `expected.json`.

### Trạng thái ký nhận

| Vai trò | Người | Ngày | Ghi chú |
|---|---|---|---|
| Đầu mối đội 1 (D1-B) | _chưa_ | | |
| Đầu mối đội 2 (D2-A) | _chưa_ | | |

Ngày 2 theo kế hoạch: hai bên chạy cùng bộ fixture này rồi ký vào bảng trên.

---

## Quyết định D-01 … D-07 — **đã chốt 2026-09-09**

Bảy điểm bản DOCX chưa khép kín. Tất cả đã được chốt; phần nào ép được bằng code
thì đã ép, phần nào là kỷ luật vận hành thì ghi rõ ở đây.

### D-01 — Quy tắc dẫn xuất `Claim.support_status` — *tự động, V06 báo lỗi khi lệch*

`derive.derive_support_status`:

1. có cả `supported` lẫn `contradicted` → `ambiguous`
2. có `contradicted` → `contradicted`
3. có `ambiguous` → `ambiguous`
4. có `supported` → `supported`
5. còn lại (rỗng hoặc toàn `insufficient`) → `insufficient`

`conflicts_with` không rỗng thì không bao giờ được `supported` → hạ xuống `ambiguous`.
Không ai được tự đặt `supported` bằng tay.

### D-02 — Evidence bất biến trong một `workflow_id` — *V03 báo lỗi*

Cùng `workflow_id` + cùng `evidence_id` ⇒ nội dung phải giống hệt. Sửa evidence
(locator, quote, modality…) = **cấp `evidence_id` mới** + ghi `change_log.id_mapping`.
Lý do: citation đã phát hành ở revision cũ không được phép âm thầm trỏ sang nội dung khác.

### D-03 — Ngôn ngữ chéo — *V02 báo lỗi + `SearchText` ép truy vết bản dịch*

| Trường | Nghĩa |
|---|---|
| `Source.language` | ngôn ngữ **thực tế** của nguồn (`en`, `vi`) |
| `Workflow.language` | ngôn ngữ dùng để viết `Claim.text` |

- Video Haas tiếng Anh ⇒ `Claim.text` viết bằng **tiếng Anh**. Validator báo lỗi nếu
  `Workflow.language` không nằm trong tập ngôn ngữ của các nguồn nó dùng.
- `Evidence.quote` **luôn giữ nguyên văn**, không dịch.
- Câu trả lời cuối dùng ngôn ngữ của câu hỏi (thường là tiếng Việt).
- Đội 2 **bắt buộc dùng embedding đa ngữ**.
- Đội 2 được tạo bốn trường dẫn xuất, định nghĩa trong `search.SearchText`:
  `search_text_original`, `search_text_vi`, `translation_model`, `translation_version`.
  Có `search_text_vi` thì bắt buộc có cả model và version (bản dịch phải tái lập được).

Bốn trường này **chỉ nằm trong search index**: không ghi ngược vào Canonical KB,
không được trích dẫn như bằng chứng. Bản dịch dùng để **tìm**, không dùng để **trả lời**.

*Lý do không viết claim chuẩn bằng tiếng Việt:* bản dịch có thể làm sai thuật ngữ,
mã cảnh báo, hoặc mức độ chắc chắn của người nói.

### D-04 — `citations[].source_review` / `technical_review` là enum — *đã cài*

Siết từ `string` tự do thành `SourceReview` / `TechnicalReview`.

### D-05 — Dedup claim — *`retrieval_policy.dedup_claim_hits`*

Thứ tự pipeline:

```
retrieve step → lấy claim được step tham chiếu → dedup claim → rerank
→ evidence package → LLM
```

- Khóa dedup là **`(workflow_id, revision, claim_id)`**. Không dùng riêng `claim_id`:
  `CL_001` tồn tại ở nhiều workflow và nhiều revision khác nhau.
- Claim xuất hiện ở nhiều step chỉ vào prompt **một lần**; giữ `matched_step_ids`.
- Điểm của claim = **điểm cao nhất** trong các step đã khớp, không cộng dồn — lặp lại
  không làm claim đúng hơn.
- **Không dedup theo nội dung văn bản.** Hai claim giống hệt câu chữ nhưng khác nguồn
  phải giữ riêng: đó có thể là hai nguồn xác nhận độc lập, hoặc hai nguồn mâu thuẫn.

### D-06 — Index hai tầng — *`search.WorkflowSearchRecord` / `StepSearchRecord`*

| Tầng | Nội dung | Mục đích |
|---|---|---|
| Workflow-level | tiêu đề, triệu chứng, alarm, model, subsystem, task type, tóm tắt claim | chọn đúng quy trình |
| Step-level | action, condition, rationale, outcome, acceptance criteria | tìm đúng chi tiết |

Luồng: câu hỏi + metadata → lọc mode/split/model/subsystem → workflow index → chọn
workflow → step index trong workflow đã chọn → lấy claim và evidence → dedup + rerank
→ trả lời kèm citation.

- Câu hỏi dạng "quy trình làm thế nào": chọn workflow trước, rồi lấy toàn bộ các bước
  hợp lệ theo đúng thứ tự.
- Câu hỏi cụ thể về một thao tác/lỗi: lấy step phù hợp và các step liên quan trực tiếp.
- **Không ghép step của nhiều workflow (hoặc nhiều revision) thành một quy trình mới** —
  `retrieval_policy.spans_multiple_workflows()` để chặn.
- Không trộn workflow của model máy khác.

Tham số top-k thuộc **cấu hình retrieval, không thuộc schema**; đội 2 chọn bằng benchmark
trên tập dev. `StepSearchRecord` dùng `extra="forbid"` nên top-k nhét vào record sẽ bị chặn.

### D-07 — Claim chứa mã/số phải có quote nguyên văn — *WARNING trong pilot*

Giữ ở mức cảnh báo (V06). Chỉ nâng thành error cho bundle `source_type=real` **sau khi**
kiểm tra ASR thực tế trên pilot. `knowflow-contracts validate --strict` coi warning là
thất bại, dùng khi muốn siết sớm ở CI của đội 1.

---

## Mã kiểm tra

| Mã | Nội dung | Ghi chú cài đặt |
|---|---|---|
| V01 | Schema / enum / khóa lạ / kiểu null | Pydantic `extra="forbid"`; optional = có mặt & null, không được bỏ khóa; timestamp phải RFC 3339 UTC; mã ngôn ngữ theo BCP-47 rút gọn |
| V02 | Checksum, số dòng, corpus (`source_type`, split, **ngôn ngữ**) | Nguồn real phải có `url` hoặc `asset_uri`; video real phải có `duration_ms`; `expert_answer`/`synthetic_fixture` phải có `raw_text`; D-03 |
| V03 | ID, revision, tham chiếu | Gồm `metadata_provenance` (basis=source phải có nguồn thật) và D-02 |
| V04 | Timestamp gốc và locator văn bản | `0 ≤ start_ms < end_ms ≤ duration_ms`; evidence video phải có mốc thời gian |
| V05 | `FieldRef.state` và claim role | `missing` ⇒ `[]`; claim mồ côi bị chặn; claim `role=relation` không được nằm trong FieldRef |
| V06 | Claim observed/stated và EvidenceLink | speech cần `quote`, visual cần `observation_note`; D-01; D-07 (warning) |
| V07 | Review và conflict | `source_checked`/`expert_validated` phải có ReviewEvent trong **chính revision này**; `conflicts_with` phải đối xứng; fixture synthetic luôn `pending`/`not_requested` |
| V08 | Relation / branch / repeated step | `branch_if` phải có condition; chỉ kiểm chu kỳ trên đồ thị `requires` |
| V09 | Import lại / sửa nội dung cùng revision | `snapshot_content_hash` + `decide_reimport` → `new` / `noop` / `conflict` |
| V10 | Nguồn/claim bị rút | latest revision `withdrawn` ⇒ warning: loại **toàn bộ** workflow khỏi RAG, không quay về revision cũ |

Validator chỉ xác nhận cấu trúc và tính nhất quán. **Đúng schema không chứng minh claim đúng** —
vẫn phải đối chiếu nguồn bằng người kiểm và đo grounded precision/recall riêng.
