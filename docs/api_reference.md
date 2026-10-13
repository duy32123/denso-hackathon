# API, hỏi đáp và chính sách citation

Tham chiếu mã `retrieval/api/` và `retrieval/generation/` sau PR #54.
Hướng dẫn cài, chuẩn bị index và mở hai giao diện nằm ở
[README chính](../README.md#chay-web). Kịch bản thao tác nằm ở
[demo giao diện mới](demo_recording_new_ui.md).

## Cấu hình server

Đặt các biến trong terminal trước khi chạy `python -m retrieval.api`.

| Biến | Mặc định / ý nghĩa |
|---|---|
| `KNOWFLOW_REAL_DEV_DB` | `out/retrieval/real_dev.sqlite`; dùng đường dẫn database đã chuẩn bị |
| `KNOWFLOW_SYNTHETIC_DEV_DB` | Không bật; cần database synthetic riêng |
| `KNOWFLOW_RETRIEVAL_STRATEGY` | `hybrid`; index không có vector dùng `lexical` |
| `KNOWFLOW_ANSWER_MODEL` | `gemini-3.5-flash-lite`; model do server cấu hình |
| `KNOWFLOW_REPO_ROOT` | Thư mục chạy; nơi đọc `.env` và keyframe |
| `KNOWFLOW_FEEDBACK_STUB` | Mặc định tắt: dùng `RealFeedbackService`. `1` bật stub không ghi dữ liệu, chỉ phục vụ kiểm thử |

`GEMINI_API_KEY` đặt trong `.env`. Server mặc định bind `127.0.0.1`, port 8000;
có thể đổi bằng `--port 8001`. API hiện phục vụ `dev`, chưa có authentication cho
triển khai công khai. Phạm vi dữ liệu và quyền truy cập nguồn ghi tại
[data rights register](data_rights_register.md).

## Hỏi đáp và trace

| Route | Nội dung |
|---|---|
| `GET /v1/health` | Trạng thái dịch vụ |
| `POST /v1/ask` | `QueryRequest` → `AnswerResponse` qua `QAService` |
| `POST /v1/trace` | Lượt truy xuất với index neo, top-k 1–5, tùy chọn sinh đáp án; stream NDJSON |
| `GET /docs` | OpenAPI của server đang chạy |

Ví dụ PowerShell:

```powershell
$qaRequest = @{
  question = "Bôi trơn con trượt của hốc dao trước khi lắp như thế nào?"
  context = @{ manufacturer = "Haas"; subsystem = "SMTC" }
  mode = "real"
  dataset_split = "dev"
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/ask -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($qaRequest))
```

Hỏi “Loại mỡ và cấp NLGI nào được chỉ định?” để kiểm trường hợp thiếu nguồn;
không điền model máy khi chưa biết. Kết quả của một câu demo cần xem trong từng
lượt gọi; kết quả tổng thể nằm ở [benchmark](../benchmarks/results/20261012_expanded_dev/REPORT.md).

## Đọc workflow, bằng chứng và lịch sử

| Route | Tham số query |
|---|---|
| `GET /v1/workflows` | `mode`, `dataset_split`; trả index đang dùng |
| `GET /v1/workflows/{id}/{revision}` | Thêm `index_build_id` |
| `GET /v1/workflows/{id}/{revision}/history` | Thêm `index_build_id`; lịch sử và diff đến revision neo |
| `GET /v1/evidence/{workflow_id}/{revision}/{evidence_id}` | `mode`, `dataset_split`, `index_build_id` |
| Route evidence thêm `/asset` | Keyframe local hợp lệ |

Danh sách workflow đọc toàn index của corpus đang chọn; bộ lọc context của ô hỏi
đáp áp dụng trong `/v1/ask`. Snapshot đọc có thể chứa claim pending hoặc conflict;
việc nhìn thấy claim trên UI không xác nhận claim đủ điều kiện trả lời.

Citation và lịch sử luôn giữ workflow/revision/index. Bản cũ không tự nhảy sang
latest; bản chưa có index phù hợp không được giả mở bằng index hiện tại.
Speech/text mở excerpt đã lưu và locator; visual mở JPEG local trong thư mục
keyframe. Server không fetch URL tùy ý từ câu hỏi hoặc bundle. “Mở được” không
chứng minh video ngoài mạng còn phát được, hoặc phát biểu được nguồn hỗ trợ về nghĩa.

Ví dụ lịch sử: `B0_SRC_HAAS_0005 · r1 → r2`, claim `CL_020` đổi liên kết
`EV_019 → EV_033` để bao phủ đủ lời nói về grease. Xem
[hồ sơ review B0 r2](b0_wf0005_r2_review.md).

## Các cổng kiểm câu trả lời

1. `retrieved` chỉ là tìm được ứng viên. Thiếu bối cảnh, mâu thuẫn hoặc thiếu nguồn
   được giữ thành trạng thái phù hợp trước generation.
2. Claim phải thuộc đúng corpus/split, workflow/revision và thỏa `claim_blockers`.
   Review nguồn và xác nhận kỹ thuật giữ nguyên từ snapshot.
3. Generator chỉ dùng link `supported` với evidence mở được. Guard kiểm ID,
   revision, citation, số liệu và bước/thứ tự của câu trả lời quy trình.
4. Code chọn ngôn ngữ đáp án, truyền cho cả lượt sinh và lượt kiểm; claim/quote gốc
   giữ nguyên để đối chiếu.
5. Lượt kiểm nghĩa bằng Gemini nhận câu trả lời hiển thị và evidence đã cite cho
   từng statement. Không đạt thì từ chối; không lấy kiến thức chung bù phần thiếu.
6. Index thay đổi trong lúc xử lý bị chặn; không trả answer từ build stale.

LLM verifier là một thành phần pipeline, có thể sai. Nó không thay thế người
chấm benchmark và không nâng thành `human-reviewed` hay `expert_validated`.
Generator hiện nhận text claim/quote/observation note; chưa gửi pixel keyframe để
model đối chiếu ảnh.

## Phản hồi và revision

`POST /v1/feedback/preview` cho xem trước; `POST /v1/feedback/submit` ghi qua
service đội 1 và tạo revision mới. UI có service thật mặc định. Phản hồi chưa
review vẫn pending; review nguồn, export/import và rebuild index là các bước
riêng trước khi đưa nội dung mới vào câu trả lời.

Danh tính người phản hồi/reviewer phải là người thực; giữ bản cũ và technical review.
Chi tiết giao diện ghi: [feedback contract](team2_feedback_contract.md).
Demo đã quay dừng ở form bổ sung; không tạo phản hồi giả để diễn đạt kinh nghiệm chuyên gia.

## Lỗi và giới hạn

- HTTP: `422` request/namespace, `404` evidence/asset, `429` bận,
  `503` index/provider, `504` timeout; trace stream có sự kiện lỗi riêng.
- Mặc định request chờ tối đa 90 giây, tối đa hai job đồng thời.
  Thread/provider đã bắt đầu có thể tiếp tục sau timeout HTTP; slot giữ đến khi job kết thúc.
- Không cache answer. API lỗi không được thay bằng đáp án hoặc vector giả.
- Test double kiểm logic phần mềm; chất lượng, token và chi phí dùng lượt API thật.
  Các con số chưa biết và chấm nghĩa chưa hoàn thành phải để `null` trong báo cáo.
