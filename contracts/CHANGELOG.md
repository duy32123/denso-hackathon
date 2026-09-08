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
- `data/fixtures/F01…F10` — 10 contract fixture, mỗi bộ kèm `expected.json`.

### Trạng thái ký nhận

| Vai trò | Người | Ngày | Ghi chú |
|---|---|---|---|
| Đầu mối đội 1 (D1-B) | _chưa_ | | |
| Đầu mối đội 2 (D2-A) | _chưa_ | | |

Ngày 2 theo kế hoạch: hai bên chạy cùng bộ fixture này rồi ký vào bảng trên.

---

## Quyết định phải chốt trước khi ký (D-01 … D-07)

Bảy điểm dưới đây là chỗ bản DOCX chưa khép kín. Mỗi điểm đã có một lựa chọn được
cài sẵn trong code để không ai bị chặn; **nếu hai đội chốt khác đi thì sửa ở đây trước,
rồi mới sửa validator.**

### D-01 — Quy tắc dẫn xuất `Claim.support_status` *(đã cài, V06 báo lỗi khi lệch)*

DOCX chỉ nói đây là "đánh giá tổng hợp". Không có quy tắc thì hai đội sẽ tính khác nhau
và validator không bắt được. Quy tắc đang dùng (`derive.derive_support_status`):

1. có cả `supported` lẫn `contradicted` → `ambiguous`
2. có `contradicted` → `contradicted`
3. có `ambiguous` → `ambiguous`
4. có `supported` → `supported`
5. còn lại (rỗng hoặc toàn `insufficient`) → `insufficient`

Cộng thêm: `conflicts_with` không rỗng thì không bao giờ được `supported` → hạ xuống `ambiguous`.

*Nếu nhóm muốn để người kiểm tự đặt giá trị:* đổi V06 từ error thành warning và ghi lý do ở đây.

### D-02 — Evidence bất biến trong một `workflow_id` *(đã cài, V03 báo lỗi)*

`Source` bất biến, nhưng `evidence[]` nằm *trong* snapshot. Nếu revision 2 giữ nguyên
`EV_001` mà đổi `locator`/`quote`, mọi citation đã phát hành ở revision 1 sẽ trỏ sai chỗ.
Quy tắc: cùng `workflow_id` + cùng `evidence_id` ⇒ nội dung phải giống hệt. Đổi nội dung
= cấp `evidence_id` mới + ghi `change_log.id_mapping`.

### D-03 — Ngôn ngữ chéo *(CHƯA cài — cần quyết định của cả hai đội)*

Nguồn Haas là tiếng Anh; câu hỏi và demo tiếng Việt. Schema 1.0.0 chỉ có `language` ở
mức workflow/source, không có ở claim/evidence. Hệ quả cụ thể: **lexical retrieval
(Postgres full-text / trigram) gần như vô dụng cho query `vi` trên tài liệu `en`.**

Cần chốt ngày 1:
- Embedding phải là model đa ngữ (không phải model chỉ tiếng Anh).
- `quote` luôn giữ nguyên văn ngôn ngữ nguồn; `claim.text` viết bằng ngôn ngữ nào?
- Nếu dựng `search_text` song ngữ: đó là **dữ liệu dẫn xuất của đội 2**, không phải claim mới,
  không được ghi ngược vào kho chuẩn.

### D-04 — `citations[].source_review` / `technical_review` là enum *(đã cài)*

DOCX để hai trường này là `string` tự do trong `AnswerResponse`. Đã siết thành enum
(`SourceReview` / `TechnicalReview`) để giá trị không trôi giữa hai đội.

### D-05 — Dedup claim ở tầng truy xuất *(CHƯA cài — thuộc đội 2)*

Một claim được phép dùng ở nhiều step (mục 3). Đơn vị index lại là Step ⇒ cùng một claim
sẽ xuất hiện nhiều lần trong top-k. Evidence package phải dedup theo `claim_id` trước khi
đưa vào prompt, nếu không LLM sẽ tưởng có nhiều nguồn độc lập cùng nói một điều.

### D-06 — Đơn vị index *(CHƯA cài — thuộc đội 2)*

Step là đơn vị index (kế hoạch đội 2, WP1), nhưng câu hỏi người dùng thường ở mức
triệu chứng/workflow. Với workflow 5–12 bước, `Recall@5` ở mức step là mục tiêu căng.
Cân nhắc index hai mức (step + workflow-level text dựng từ context và claim) và đo cả hai
trước khi khóa pipeline ở D15.

### D-07 — Claim chứa mã/số phải có quote nguyên văn *(đã cài ở mức WARNING, V06)*

ASR sai chính xác ở nhóm token nguy hiểm nhất: alarm code, part number, đơn vị, phủ định.
Hiện là cảnh báo. Đề nghị nâng lên error cho bundle `source_type=real` sau khi đo trên pilot.

---

## Mã kiểm tra

| Mã | Nội dung | Ghi chú cài đặt |
|---|---|---|
| V01 | Schema / enum / khóa lạ / kiểu null | Pydantic `extra="forbid"`; optional = có mặt & null, không được bỏ khóa; timestamp phải RFC 3339 UTC |
| V02 | Checksum, số dòng, `source_type`, split | Gồm cả: nguồn real phải có `url` hoặc `asset_uri`; video real phải có `duration_ms`; `expert_answer`/`synthetic_fixture` phải có `raw_text` |
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
