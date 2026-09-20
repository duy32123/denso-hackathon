# D2-B WP4 + D2-A — workflow, evidence và lịch sử (chỉ đọc)

Phần tiếp theo của `docs/03_Plan_doi_2_Synthetic_KB_RAG_LLM.docx`, mục 3 / WP4.
Không sửa Schema 1.0.0, không ghi KB/review và không tự đổi index khi xem bản cũ.
Ngôn ngữ câu trả lời nay do code quyết định (xem mục 5 của [grounded QA](team2_grounded_qa.md)); **chưa kiểm lại với Gemini thật**, nên demo vẫn nên chuẩn bị sẵn câu hỏi tiếng Anh làm phương án dự phòng.

## Đã triển khai

- Danh sách workflow thuộc index của đúng corpus/split; không trộn real/synthetic.
- Màn Step → bảy field → claim → evidence. Hiện field state, claim nguyên văn,
  support/review flags, attribution, scope, relation và conflict chưa giải quyết.
- Citation đầu tiên của câu trả lời tự mở. Khung evidence nằm cạnh workflow và giữ
  vị trí khi cuộn trên desktop; mobile chuyển sang một cột. Phân biệt nguồn mở từ
  câu trả lời với nguồn người dùng tự chọn khi duyệt workflow.
- Hiện transcript/text đã lưu hoặc keyframe có thật, locator và nguồn. Không tự
  phát clip, không khẳng định video ngoài mạng đã được kiểm khả năng phát.
- Hiện Question records và tình trạng missing; không tự viết lời giải cho phần thiếu.
- Lịch sử tới revision đang xem, so sánh với `supersedes_revision`: claim/field/Step,
  evidence, Question, Relation thay đổi; change log, id_mapping và người kiểm.
- Chọn r1/r2 dùng đúng index lịch sử tương ứng. Revision chưa từng có index được
  ghi rõ, không giả dùng index hiện tại để mở citation cũ. Xem lịch sử không promote
  bản cũ, không đổi active pointer và không thay câu trả lời đang có.
- Lỗi dữ liệu/index chưa sẵn sàng, corpus chưa bật và phản hồi đến muộn sau đổi corpus
  được xử lý rõ. Mọi text nguồn/model được render bằng `textContent`, không dùng HTML từ nguồn.

## Chạy thử

Nếu server cũ còn chạy: Ctrl+C tại terminal đó, rồi khởi động lại để nạp API mới.

```powershell
.\.venv\Scripts\python.exe -m retrieval.api
```

Mở <http://127.0.0.1:8000>, Ctrl+F5 để tải lại JavaScript/CSS.

1. Chọn real/dev, Haas / SMTC. Câu mặc định: `How is the pocket slider lubricated?`.
   Sau khi trả lời, citation đầu tiên mở tự động, giữ nguyên `source_checked / not_requested`.
2. Ở danh sách workflow, chọn `B0_SRC_HAAS_0005 · r2`. Mở Step 6 → action → `CL_020`
   → Mở nguồn. Phải thấy `EV_033`, đoạn 147.840–165.270 giây và câu có `apply some grease`.
3. Phần lịch sử r2 phải chỉ ra `CL_020` đổi link `EV_019 → EV_033`. Bấm “Xem r1”,
   mở lại claim đó: phải dùng evidence/index của r1, không tự nhảy về r2.
4. Chọn `REAL_WF_0001` để xem các Question records về phần chưa biết và Relation records.
5. Dùng câu mẫu loại mỡ/NLGI để kiểm abstain; câu mẫu VF-2 để kiểm thiếu bối cảnh áp dụng.
   Các câu này không được coi là benchmark. Synthetic chỉ dùng khi có DB synthetic riêng;
   nhãn mô phỏng luôn hiện, không có đường link giả phát video.

Danh sách workflow là trình đọc toàn index, **không lọc theo context trong ô hỏi đáp**.
Các bộ lọc context và eligibility của `/v1/ask` vẫn giữ nguyên. Snapshot đọc có thể chứa
claim pending/rejected/conflict: việc thấy claim trên màn hình không xác nhận nó đủ điều kiện trả lời.

## API đọc

| Route | Tham số | Ý nghĩa |
|---|---|---|
| `GET /v1/workflows` | `mode`, `dataset_split` | Workflow của active retrieval index; trả `index_build_id`. |
| `GET /v1/workflows/{id}/{revision}` | thêm `index_build_id` | Snapshot thuộc chính index đó, nguồn rút gọn; không trả `Source.raw_text` hay đường dẫn asset local. |
| `GET /v1/workflows/{id}/{revision}/history` | thêm `index_build_id` | Lịch sử đến revision neo; diff từ snapshot đã lưu và index dùng để xem từng bản. |

Evidence/asset tiếp tục dùng các route `/v1/evidence/...` hiện có. Namespace được kiểm
trước khi đọc. Query có thể bị chặn khi index stale nhưng view của index lịch sử hợp lệ
vẫn mở được. API chỉ localhost, chưa có auth/deployment công khai.

## Kiểm thử

- `tests/integration/test_workflow_browser.py`: namespace, revision/index membership,
  snapshot/history chỉ đọc, diff B0 r2, không nâng review flags, không làm mất câu hỏi/conflict.
- `tests/end_to_end/test_wp4_browser_ui.py`: Edge headless với profile tạm riêng,
  model giả và DB tạm; hỏi tiếng Anh, tự mở evidence, đọc field/claim, chuyển r2/r1,
  sidebar sticky, đổi corpus và loại phản hồi cũ đến muộn. Không gọi Gemini.

```powershell
# Offline, không chạy các smoke gọi Gemini.
.\.venv\Scripts\python.exe -m pytest --ignore=tests/end_to_end/test_qa_gemini.py

# Windows có Edge + websockets (đã có qua extra retrieval trong môi trường này).
$env:KNOWFLOW_BROWSER_TEST = "1"
.\.venv\Scripts\python.exe -m pytest tests/end_to_end/test_wp4_browser_ui.py -v -s
Remove-Item Env:\KNOWFLOW_BROWSER_TEST
```

Browser test kiểm phần mềm bằng model giả, không chứng minh chất lượng trả lời của Gemini.
Không cần API key để kiểm các màn đọc. Lượt triển khai WP4 này không gọi lại Gemini,
không rebuild DB phục vụ và không sửa snapshot r1/r2 hay nhãn review/gold.

## Màn Bổ sung — chạy trên stub, chưa đóng G2

**D1-B / WP6 sở hữu service ghi feedback và revision.** Repo mới có CLI compile/review/
promote, chưa có service để UI gọi. Đội 2 vì vậy dựng sẵn đường gọi và giao diện, nhưng
**không** ghi thẳng vào kho chuẩn và **không** có nút lưu giả.

Đề xuất contract đã gửi đội 1: [team2_feedback_contract.md](team2_feedback_contract.md).

Đã có:

- `POST /v1/feedback/preview` và `POST /v1/feedback/submit` đúng hai lời gọi trong contract.
- `retrieval/generation/feedback.py`: `FeedbackService` protocol + `StubFeedbackService`.
  Stub đọc snapshot **thật** để dựng bản xem trước đúng, nhưng không có đường nào ghi;
  `submit` báo 503 trừ khi `allow_submit=True` — cờ đó chỉ dùng trong test, không đọc từ env.
- Màn Bổ sung: chọn câu hỏi còn mở (tự điền step/field), nguyên văn phản hồi, người trả
  lời + vai trò, khối xem trước, nút Lưu.
- **Nút Lưu bật theo dữ liệu, không theo cờ cứng**: preview trả `simulated=true` thì nút
  vẫn tắt kèm lý do. Chỉ service thật mới bật được nút.
- Bản xem trước hiện rõ claim mới là `source_review=pending` / `technical_review=not_requested`,
  và ghi "danh tính người trả lời chưa được xác thực" — có phản hồi không phải là đã kiểm.
- **Ca lỗi thứ 5/5** của kế hoạch mục 3: `base_revision` cũ trả **409** kèm revision mới
  nhất, UI buộc tải lại, không ghi đè.

Chạy thử:

```powershell
$env:KNOWFLOW_FEEDBACK_STUB = "1"
.\.venv\Scripts\python.exe -m retrieval.api
Remove-Item Env:\KNOWFLOW_FEEDBACK_STUB
```

Mặc định **tắt**. Không bật stub thì cả hai endpoint trả 503 `feedback_unavailable`.

Kiểm: `tests/integration/test_feedback.py` (8 ca, mọi đường đều assert database không
đổi một byte). Ca giao diện nằm trong `tests/end_to_end/test_wp4_browser_ui.py`, cần
Windows + Edge — **chưa chạy được trên máy Linux hiện tại**.

### Còn lại để đóng G2

Stub **không phải** G2. Vòng phản hồi chỉ đóng khi: đội 1 chốt contract và làm service →
đội 2 thay stub bằng adapter thật → chạy trọn vòng phản hồi → revision mới → import →
reindex → hỏi lại ra câu trả lời mới, citation mở được, bản cũ vẫn mở bằng `index_build_id`
cũ. Trước khi có đủ chuỗi đó, **không được tuyên bố hoàn tất vòng feedback**.
