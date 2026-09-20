# Đề xuất contract: service ghi phản hồi (D1-B / WP6 ↔ đội 2)

**Trạng thái: đề xuất, chưa chốt.** Đội 2 viết bản này để đội 1 sửa và chốt, không
phải để đội 1 làm theo nguyên văn. Mọi mục có dấu ❓ là chỗ cần đội 1 quyết.

**Vì sao gấp:** cổng G2 (`feedback tạo revision mới và cập nhật câu trả lời`) đến hạn
D10 và hiện chưa mở được — repo mới có CLI compile/review/promote, chưa có service để
giao diện gọi. Đội 2 **không** dựng nút lưu giả và **không** ghi thẳng vào kho chuẩn,
nên phần này đứng yên cho tới khi có service.

## 1. Ai làm gì

| | Sở hữu | Trách nhiệm |
|---|---|---|
| **D1-B / WP6** | Kho tri thức chuẩn, service ghi, đánh số revision | Nhận phản hồi → tạo `Source` + revision mới → validate → trả kết quả |
| **Đội 2** | UI nhập phản hồi, xem trước, hỏi lại sau khi lưu | Gọi service, hiển thị preview/lỗi, import lại và reindex |

Kế hoạch đội 2 mục "Phạm vi": *mọi sửa tri thức đi qua service đội 1; đội 2 được rebuild
search index từ snapshot, không sửa claim chuẩn để khớp câu trả lời.*

Kênh tích hợp là **D2-A** (`duy32123`) theo đúng phân công "D2-A là đầu mối tích hợp với D1-B".

## 2. Hai lời gọi

Đề xuất đội 1 cung cấp hai endpoint, hoặc hai hàm Python tương đương nếu chạy chung tiến
trình. Đội 2 sẽ bọc lại sau `/v1/feedback/*` của mình để giữ một origin cho trình duyệt
và để kiểm namespace trước khi chuyển tiếp.

### `preview` — không ghi gì

```json
{
  "workflow_id": "REAL_WF_0001",
  "base_revision": 1,
  "step_id": "REAL_WF_0001_ST_003",
  "target_field": "rationale",
  "question_id": "REAL_WF_0001_Q_001",
  "answer_text": "Phải tháo nắp che trước vì không nhìn được đường dây tín hiệu.",
  "responder": { "actor_id": "dpv137", "label": "Phạm Vũ Đăng", "role": "kỹ thuật viên bảo trì" },
  "language": "vi"
}
```

`question_id` có thể null khi người dùng bổ sung một trường còn thiếu mà chưa có
Question record. `answer_text` là **nguyên văn**, đội 2 không sửa, không tóm tắt.

Trả về đúng những gì sẽ được ghi, để người dùng đọc trước khi bấm lưu:

```json
{
  "base_revision": 1, "next_revision": 2, "conflict": null,
  "source": { "source_id": "SRC_EXPERT_0007", "source_kind": "expert_answer",
              "raw_text": "…nguyên văn…", "asset_uri": "acquisition/feedback/SRC_EXPERT_0007.json" },
  "new_evidence": [ { "evidence_id": "REAL_WF_0001_EV_041", "modality": "text",
                      "locator": { "text_span": "…" }, "quote": "…nguyên văn…" } ],
  "new_claims": [ { "claim_id": "REAL_WF_0001_CL_033", "role": "rationale", "text": "…",
                    "evidence_type": "stated", "support_status": "supported",
                    "source_review": "pending", "technical_review": "not_requested" } ],
  "field_changes": [ { "step_id": "REAL_WF_0001_ST_003", "field": "rationale",
                       "before": { "state": "missing", "claim_ids": [] },
                       "after": { "state": "present", "claim_ids": ["REAL_WF_0001_CL_033"] } } ],
  "question_transition": { "question_id": "REAL_WF_0001_Q_001",
                           "from": "open", "to": "answered" },
  "change_log": { "changed_at": "…Z", "actor_id": "dpv137",
                  "reason": "Bổ sung rationale từ phản hồi chuyên môn.",
                  "previous_revision": 1, "id_mapping": [] },
  "warnings": []
}
```

### `submit` — ghi thật

Cùng request, thêm `"confirm_base_revision": 1`. Trả về:

```json
{ "workflow_id": "REAL_WF_0001", "revision": 2,
  "created_source_id": "SRC_EXPERT_0007",
  "created_claim_ids": ["REAL_WF_0001_CL_033"],
  "created_evidence_ids": ["REAL_WF_0001_EV_041"],
  "bundle_export": "acquisition/export/haas_pilot_dev_bundle" }
```

`bundle_export` để đội 2 biết import lại ở đâu. ❓ Nếu đội 1 muốn tự đẩy thay vì để đội 2
kéo, nói rõ để đội 2 bỏ bước import thủ công.

## 3. Ràng buộc phải giữ — đây là phần quan trọng nhất

Những điểm dưới đây validator **đã** chặn; ghi ra để không phát hiện lúc submit lần đầu:

1. **`expert_answer` trong corpus real phải có `url` HOẶC `asset_uri`** — V02, ngoài
   `raw_text`. Không có đường dẫn truy cập được thì cả bundle bị từ chối. Đề xuất: ghi
   phản hồi thành tệp trong repo rồi đặt `asset_uri` trỏ vào đó. ❓ Đội 1 chốt vị trí và
   định dạng tệp.
2. **Claim mới luôn `source_review=pending`, `technical_review=not_requested`.** Có phản
   hồi **không** phải là đã kiểm nguồn, càng không phải chuyên gia xác nhận. Muốn lên
   `source_checked` thì phải có `ReviewEvent` trong **chính revision đó** (V07).
3. **`support_status` không được đặt tay** — luôn suy ra từ `evidence_links` bằng
   `derive_support_status` (D-01).
4. **Evidence bất biến** — sửa nội dung một `evidence_id` đã phát hành là cấp ID mới và
   ghi `change_log.id_mapping` (D-02). Citation cũ không được âm thầm trỏ sang nội dung khác.
5. **`Claim.text` viết bằng ngôn ngữ của nguồn**; `Evidence.quote` giữ nguyên văn, không
   dịch (D-03). Phản hồi tiếng Việt cho một workflow tiếng Anh ❓ — xem mục 5.
6. **Question chuyển `open → answered`**, kèm `answer_source_ids`. Sang `resolved` là một
   bước **riêng** sau khi có người kiểm, không tự động.
7. **Revision cũ giữ nguyên**, không xoá, không sửa tại chỗ.

## 4. Ca lỗi

| Tình huống | Mã | Đội 2 hiển thị |
|---|---|---|
| `base_revision` không còn là latest | **409** + `conflict: {latest_revision, changed_fields, changed_at, actor_id}` | Diff giữa bản người dùng đang xem và bản mới, buộc tải lại. Không ghi đè |
| `workflow_id`/`step_id`/`question_id` không tồn tại | 404 | Dữ liệu đã đổi, tải lại |
| `target_field` đã có claim | 409 hoặc 422 ❓ | Đội 1 chốt: bổ sung thêm claim hay coi là xung đột |
| Bundle sau khi ghi không qua validator | 422 + danh sách mã V0x | Không tạo revision; trả nguyên lỗi để sửa |
| Thiếu `responder.role` | 422 | Bắt buộc nhập vai trò thật |

Không trả stack trace, token hay cấu hình model ra luồng sản phẩm.

## 5. Câu hỏi cần đội 1 trả lời

1. **Danh tính người trả lời** — lấy từ đâu? Hiện chưa có đăng nhập. Tạm thời người dùng
   tự nhập `actor_id` + `role`? Nếu vậy thì `actor_id` **không** được coi là đã xác thực,
   và UI phải nói rõ điều đó.
2. **`asset_uri` cho phản hồi** — vị trí, định dạng, ai ghi tệp.
3. **Phản hồi tiếng Việt trên workflow tiếng Anh** — D-03 nói `Workflow.language` phải
   nằm trong tập ngôn ngữ các nguồn. Thêm một nguồn tiếng Việt vào workflow tiếng Anh
   thì hợp lệ, nhưng `Claim.text` mới viết bằng tiếng gì? Đề xuất: đúng ngôn ngữ của
   phản hồi, và đánh dấu để UI hiển thị lẫn ngôn ngữ.
4. **Ai được ghi** — có giới hạn theo người/vai trò không, hay ai mở được UI cũng ghi được.
5. **Đồng thời** — hai người cùng sửa một workflow thì khoá kiểu gì, hay chỉ dựa vào 409.
6. **`target_field` đã có claim** — bổ sung hay xung đột (mục 4).

## 6. Đội 2 đã chuẩn bị sẵn gì

Để khi service xong chỉ phải thay adapter, không phải viết lại giao diện:

- `retrieval/generation/feedback.py` — `FeedbackService` protocol đúng hai lời gọi trên,
  cùng một `StubFeedbackService` chạy trong bộ nhớ **chỉ dùng cho test và dev**.
- Màn Bổ sung trong UI: danh sách Question đang `open`, ô nguyên văn phản hồi, ô người
  trả lời + vai trò, khối preview, nút Lưu.
- Khi chưa cấu hình service thật, nút Lưu **tắt** và hiện rõ "service ghi của đội 1 chưa
  sẵn sàng". Không có nút giả.
- Ca lỗi 409 `base_revision` đã dựng sẵn ở UI — đây là ca lỗi thứ 5/5 mà kế hoạch mục 3
  bắt buộc phải hiển thị được.

Stub **không phải** G2. Vòng phản hồi chỉ được coi là đóng khi chạy qua service thật,
import lại, reindex và hỏi lại cho ra câu trả lời mới có citation mở được.

## 7. Thứ tự đề xuất

1. Đội 1 sửa/chốt bản này, trả lời 6 câu ở mục 5.
2. Đội 1 làm `preview` trước — không ghi gì nên rủi ro thấp, mà đội 2 nối UI được ngay.
3. Đội 1 làm `submit` + validate + export bundle.
4. Đội 2 thay stub bằng adapter thật, chạy thử trọn vòng trên `REAL_WF_0001`.
5. Hai đội cùng chạy: phản hồi → revision mới → import → reindex → hỏi lại → citation mở
   đúng bản mới, bản cũ vẫn mở được bằng `index_build_id` cũ. Đó mới là G2.
