# Contract: service ghi phản hồi (D1-B / WP6 ↔ đội 2)

**Trạng thái: đã chốt và đã triển khai (2026-09-22).** Đội 2 viết bản đề xuất này;
D1-B đã trả lời sáu câu ở mục 5 và cài đặt trong
[`acquisition/extraction/feedback_service.py`](../acquisition/extraction/feedback_service.py).
Các dấu ❓ cũ được thay bằng quyết định; chỗ nào cài khác đề xuất ban đầu thì ghi rõ lý do.

**Trạng thái G2:** phía đội 1 đã xong — `preview` và `submit` chạy được, có test trên
kho chuẩn thật. Còn lại để đóng cổng: đội 2 thay `StubFeedbackService` bằng adapter thật,
rồi hai đội chạy trọn vòng phản hồi → revision mới → import → reindex → hỏi lại (mục 7).

**Gọi như thế nào.** Hai hàm Python chạy chung tiến trình (mục 2 cho phép), không phải
HTTP riêng — pilot không cần thêm một server nữa:

```python
from acquisition.extraction.feedback_service import preview, submit, FeedbackError

body = preview(request_dict)                              # không ghi gì
done = submit({**request_dict, "confirm_base_revision": 1})
```

Mọi lỗi kế thừa `FeedbackError` và mang sẵn `.http_status` (404 / 409 / 422 / 429) để
đội 2 map thẳng sang response; `FeedbackConflict.conflict` và `FeedbackRejected.errors`
chứa phần thân đã mô tả ở mục 4.

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

**Bản cài đặt trả thêm bốn khoá** so với đề xuất trên:

| Khoá | Vì sao |
|---|---|
| `mode`, `dataset_split` | Để đội 2 kiểm namespace khớp trước khi hiển thị, không phải tin vào request của chính mình |
| `validation` | `{ok, errors, warnings}` từ **validator chung** chạy trên bundle sẽ xuất. Lỗi V0x và lỗi bất biến snapshot (D-02) lộ ra **trước** khi người dùng bấm Lưu, không phải sau |
| `responder_authenticated` | Luôn `false` — xem mục 5.1. UI phải nói rõ đây là tên tự khai |
| `question_transition.created_by_this_change` | `true` khi service tự tạo Question record cho một trường thiếu chưa ai hỏi (xem mục 5.6) |

`preview` **không sửa kho chuẩn**. Có một bundle được dựng trong thư mục tạm để chạy
validator; thư mục đó bị xoá ngay. Test `test_preview_does_not_touch_the_canonical_store`
hash toàn bộ `data/workflows`, `data/sources`, bundle dev và `acquisition/feedback`
trước/sau mỗi lời gọi và đòi giống hệt.

### `submit` — ghi thật

Cùng request, thêm `"confirm_base_revision": 1`. Trả về:

```json
{ "workflow_id": "REAL_WF_0001", "revision": 2, "supersedes_revision": 1,
  "created_source_id": "SRC_EXP_6CCA700A",
  "created_claim_ids": ["REAL_WF_0001_CL_040"],
  "created_evidence_ids": ["REAL_WF_0001_EV_037"],
  "bundle_export": "acquisition/export/haas_pilot_dev_bundle",
  "bundle_id": "BUNDLE_HAAS_SMTC_DEV_7ecc274c425b",
  "snapshot_path": "data/workflows/dev/REAL_WF_0001.r2.json",
  "asset_path": "acquisition/feedback/SRC_EXP_6CCA700A.json",
  "reindex_required": true, "review_required": true,
  "responder_authenticated": false, "warnings": [] }
```

**Đội 2 kéo, đội 1 không đẩy.** `bundle_export` + `bundle_id` để đội 2 biết import lại ở
đâu và phân biệt được build nào. Đội 1 không tự gọi sang importer của đội 2: ranh giới sở
hữu index là của đội 2, và một lần ghi KB không nên kéo theo một lần build có thể tính phí
embedding. `reindex_required: true` là lời nhắc rằng câu trả lời **chưa** đổi cho tới khi
đội 2 import và build lại.

`review_required: true` luôn đúng: claim mới là `pending`. Phản hồi làm tri thức **dày
thêm**, không làm nó **đúng thêm**.

### Bảo đảm khi ghi

1. Toàn bộ nằm trong một khoá ghi, và kho được **đọc lại bên trong khoá** — preview người
   dùng đang xem có thể đã cũ vài phút.
2. Validator chạy **trước** khi ghi. Bundle hỏng thì không revision nào được tạo.
3. Hỏng ở bước nào cũng hoàn tác toàn bộ: không snapshot mồ côi, không Source trỏ tới tệp
   không tồn tại, không bundle nửa vời.
4. Tệp snapshot được tạo bằng `O_EXCL`: một revision đã có trên đĩa không bao giờ bị ghi đè,
   kể cả khi logic bên trên sai.

## 3. Ràng buộc phải giữ — đây là phần quan trọng nhất

Những điểm dưới đây validator **đã** chặn; ghi ra để không phát hiện lúc submit lần đầu:

1. **`expert_answer` trong corpus real phải có `url` HOẶC `asset_uri`** — V02, ngoài
   `raw_text`. Không có đường dẫn truy cập được thì cả bundle bị từ chối.
   **Đã chốt:** service ghi phản hồi thành `acquisition/feedback/<source_id>.json` và
   đặt `asset_uri` trỏ vào đó. Tệp giữ `raw_text` nguyên văn, `content_sha256`,
   `presenter` / `presenter_role` và `presenter_authenticated: false`. Service ghi tệp
   này, đội 2 không ghi.
2. **Claim mới luôn `source_review=pending`, `technical_review=not_requested`.** Có phản
   hồi **không** phải là đã kiểm nguồn, càng không phải chuyên gia xác nhận. Muốn lên
   `source_checked` thì phải có `ReviewEvent` trong **chính revision đó** (V07).
3. **`support_status` không được đặt tay** — luôn suy ra từ `evidence_links` bằng
   `derive_support_status` (D-01).
4. **Evidence bất biến** — sửa nội dung một `evidence_id` đã phát hành là cấp ID mới và
   ghi `change_log.id_mapping` (D-02). Citation cũ không được âm thầm trỏ sang nội dung khác.
5. **`Claim.text` viết bằng ngôn ngữ của nguồn**; `Evidence.quote` giữ nguyên văn, không
   dịch (D-03). Phản hồi tiếng Việt cho workflow tiếng Anh: xem mục 5.3.
6. **Question chuyển `open → answered`**, kèm `answer_source_ids`. Sang `resolved` là một
   bước **riêng** sau khi có người kiểm, không tự động.
   **Đã sửa trong code:** mặc định của `feedback_loop` trước đây là `resolved` và nó kéo
   theo `technical_review=expert_validated`; nay mặc định là `answered`, và trạng thái
   Question hoàn toàn không còn ảnh hưởng tới trạng thái review của claim.
7. **Revision cũ giữ nguyên**, không xoá, không sửa tại chỗ.
8. **`Source.language` là ngôn ngữ thực tế của phản hồi**, không phải ngôn ngữ của
   workflow (D-03). Một câu trả lời tiếng Việt trên workflow tiếng Anh là một nguồn
   tiếng Việt; ghi `en` cho nó là khai sai ngôn ngữ nguồn. Workflow vẫn hợp lệ vì V02
   chỉ đòi `Workflow.language` nằm trong tập ngôn ngữ của các nguồn nó dùng.
9. **ID mới không đâm vào ID đã phát hành ở revision khác**, kể cả bản draft chưa promote.
   Service quét mọi `<workflow_id>.r*.json` trên đĩa trước khi cấp ID. Ca thật đang có:
   `REAL_WF_0001.r1` hết ở `EV_035` nhưng draft `r2` đã chiếm `EV_036`, nên phản hồi được
   cấp `EV_037`.

## 4. Ca lỗi

| Tình huống | Mã | Đội 2 hiển thị |
|---|---|---|
| `base_revision` không còn là latest | **409** + `conflict: {latest_revision, changed_fields, changed_at, actor_id}` | Diff giữa bản người dùng đang xem và bản mới, buộc tải lại. Không ghi đè |
| `workflow_id`/`step_id`/`question_id` không tồn tại | 404 | Dữ liệu đã đổi, tải lại |
| `target_field` đã có claim | **không phải lỗi** — xem mục 5.6 | Preview kèm warning "đã có N claim, phản hồi được thêm vào bên cạnh" |
| Bundle sau khi ghi không qua validator | 422 + danh sách mã V0x trong `.errors` | Không tạo revision; trả nguyên lỗi để sửa |
| Thiếu `responder.role`, hoặc chỉ toàn khoảng trắng | 422 | Bắt buộc nhập vai trò thật |
| `confirm_base_revision` ≠ `base_revision` | 422 | Bản xem trước và bản lưu không cùng gốc; tải lại preview |
| Một lần ghi khác đang chạy | **429** | "Đang bận, thử lại sau vài giây". Không ghi đè. Khoá cũ hơn 5 phút (tiến trình bị kill) tự hết hạn |
| `answer_text` y hệt một phản hồi đã lưu | 422, báo ngay từ `preview` | `source_id` băm theo nguyên văn nên hai câu y hệt trùng nguồn; người dùng ghi rõ hơn câu trả lời |
| `mode=synthetic`, hoặc `dataset_split=holdout` | 422 | Không ghi được: KB synthetic là dữ liệu dẫn xuất của đội 2; holdout khoá tới sau D15 |
| Question đã `answered`/`resolved`, hoặc hỏi về step/field khác | 422 | Câu hỏi không còn mở, hoặc người dùng đính câu trả lời vào sai chỗ |

Không trả stack trace, token hay cấu hình model ra luồng sản phẩm.

## 5. Sáu câu hỏi — D1-B trả lời (2026-09-22)

**5.1 Danh tính người trả lời.** Tự nhập `actor_id` + `label` + `role`, cả ba bắt buộc
và không được toàn khoảng trắng. Hệ thống **không có đăng nhập**, nên `actor_id` không
bao giờ được coi là đã xác thực: `preview` và `submit` đều trả `responder_authenticated:
false`, và tệp phản hồi ghi `presenter_authenticated: false`. **UI phải hiện rõ điều này**
cạnh ô nhập và trong lịch sử revision. Không bao giờ hiển thị người trả lời như một
chuyên gia đã được xác nhận.

**5.2 `asset_uri`.** `acquisition/feedback/<source_id>.json`, do service đội 1 ghi
(mục 3.1). Đội 2 không tạo tệp này.

**5.3 Phản hồi tiếng Việt trên workflow tiếng Anh.** `Claim.text` giữ **nguyên văn** phản
hồi, không dịch. Lý do: D-03 cấm dùng bản dịch để trả lời — dịch có thể làm sai thuật ngữ,
mã lỗi hoặc mức độ chắc chắn — nên máy dịch sang tiếng Anh để "cho khớp `Workflow.language`"
là đúng hình thức mà sai nội dung. `Source.language` ghi đúng ngôn ngữ phản hồi (mục 3.8).

Chỗ này **cố tình để lệch nhẹ với D-03**: `Workflow.language` vẫn là `en` trong khi một
claim viết tiếng Việt. Preview trả warning nêu rõ, và người kiểm nguồn phải xử lý trước
khi promote — dịch có kiểm soát, hoặc tách workflow, hoặc chấp nhận và ghi vào báo cáo.
Đây là quyết định có chủ đích, không phải sơ suất; nếu nhóm muốn siết thì cách đúng là
**từ chối** phản hồi khác ngôn ngữ, không phải dịch tự động.

**5.4 Ai được ghi.** Pilot không giới hạn: ai mở được UI thì ghi được. Không có đăng nhập
thì mọi "giới hạn theo vai trò" chỉ là ô text tự khai, tức bảo mật giả. Cái thật sự bảo vệ
được là **truy vết**: mỗi revision ghi `change_log.actor_id`, và mọi claim mới đều `pending`
nên không có gì đi thẳng vào câu trả lời mà không qua người kiểm nguồn. Chỉ ghi được vào
`real`/`dev`; `synthetic` và `holdout` bị chặn.

**5.5 Đồng thời.** Khoá ghi + 409, **không phải chỉ 409**. Đề xuất ban đầu của D1-B là chỉ
dựa 409 cho gọn; nhìn lại thì sai: hai lần submit cùng đọc `latest=r1` rồi cùng ghi
`REAL_WF_0001.r2.json`, bản sau đè bản trước và mất một revision mà không ai biết. 409 chỉ
đúng khi đọc-rồi-ghi là liền mạch, nên kho được đọc lại **bên trong** khoá. Thêm `O_EXCL`
trên tệp snapshot làm chốt cuối. Chờ khoá quá 10 giây thì trả 429.

**5.6 `target_field` đã có claim.** **Bổ sung**, không phải xung đột. Hai nguồn cùng nói về
một trường là chuyện bình thường — có thể là hai nguồn xác nhận độc lập, có thể là hai nguồn
mâu thuẫn, và cả hai trường hợp đều phải giữ riêng chứ không được để một bên biến mất
(D-05 cấm dedup theo nội dung). Claim mới được thêm vào `claim_ids`, claim cũ giữ nguyên.
Preview trả warning để người dùng biết mình đang thêm chứ không thay.

Nếu phản hồi thật sự **mâu thuẫn** với claim cũ thì đó là việc của người kiểm nguồn: đặt
`conflicts_with` đối xứng, và D-01 sẽ tự hạ `support_status` xuống `ambiguous`. Service
không tự đoán mâu thuẫn từ văn bản.

**Chưa có Question record?** `question_id` để `null`; service tự tạo một Question rồi
chuyển `answered` ngay trong revision đó, để claim vẫn truy được nguồn gốc thay vì xuất
hiện không rõ từ đâu. Preview đánh dấu `created_by_this_change: true`.

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

**Khác biệt cần chỉnh khi nối adapter:** `FeedbackRequest` của đội 2 dùng
`dataset_split: Literal["dev"]`, bản đội 1 nhận cả `"holdout"` rồi **từ chối bằng 422** —
để thông báo nói rõ "holdout khoá tới sau D15" thay vì báo lỗi schema khó hiểu. Còn lại
hai model trùng trường và trùng nghĩa.

## 7. Thứ tự — trạng thái 2026-09-23

1. ✅ Đội 1 chốt bản này, trả lời 6 câu ở mục 5.
2. ✅ `preview` — không ghi gì, có validator chạy trước.
3. ✅ `submit` + validate + export bundle, có khoá và hoàn tác.
4. ✅ **Đội 2 thay stub bằng adapter thật** (`retrieval/generation/feedback.py:RealFeedbackService`,
   mặc định từ commit `6179a36`; `KNOWFLOW_FEEDBACK_STUB=1` mới dùng lại stub).
   `REAL_WF_0001_Q_001` (rationale của `ST_001` — "vì sao ngắt khí nén ở bước này") là ca đã dùng để kiểm thử.
5. ✅ Hai đội cùng chạy: phản hồi → revision mới → import → reindex → hỏi lại → citation mở
   đúng bản mới, bản cũ vẫn mở được bằng `index_build_id` cũ. Vòng này được khoá lại bằng
   `tests/integration/test_feedback_real.py` (submit → import_bundle → build_index → QAService
   thấy revision/claim/question mới, bản cũ giữ nguyên byte). Đó là G2.

Nhắc cho bước 4–5: sau `submit`, câu trả lời **chưa** đổi cho tới khi đội 2 import và build
lại index (`reindex_required: true`). Và claim mới vẫn `pending`, nên ở `mode=real` nó chưa
đủ điều kiện để khẳng định — `claim_blockers` sẽ chặn. Muốn demo đoạn 4 cho ra câu trả lời
mới thì **phải có người kiểm nguồn** claim đó trước (`acquisition.extraction.review`).
Đây là thiết kế, không phải lỗi: phản hồi chưa ai đối chiếu thì không được lên tiếng thay
cho nguồn.

## 8. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_feedback_service.py tests/unit/test_feedback_submit.py tests/unit/test_feedback_loop.py
```

Test `submit` chạy trên một **bản sao** kho chuẩn trong thư mục tạm.
`test_submit_writes_nothing_into_the_real_repo` hash repo trước/sau để chắc bộ test ghi
thật nhưng không chạm vào `data/workflows`, `data/sources` hay bundle đã xuất.
