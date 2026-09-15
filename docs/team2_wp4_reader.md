# D2-B WP4 + D2-A — workflow, evidence và lịch sử (chỉ đọc)

Phần tiếp theo của `docs/03_Plan_doi_2_Synthetic_KB_RAG_LLM.docx`, mục 3 / WP4.
Không sửa Schema 1.0.0, không ghi KB/review và không tự đổi index khi xem bản cũ.
Lỗi ngôn ngữ đầu ra được tạm hoãn theo quyết định người dùng; demo hiện dùng câu hỏi tiếng Anh.

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

## Chưa làm: feedback và G2

Theo plan, **D1-B / WP6 sở hữu service ghi feedback và revision**; repo hiện mới có
CLI compile/review/promote và cơ chế revision sửa evidence. Chưa có service ghi feedback
để UI gọi, nên không dựng nút “lưu” giả hay ghi trực tiếp từ đội 2 vào kho chuẩn.

Phần tiếp theo cần chốt/triển khai với D1-B: nhận `base_revision`, danh tính/vai trò
người trả lời và nguyên văn phản hồi; preview; trả conflict nếu base đã thay đổi;
tạo `expert_answer` Source và revision mới qua service; claim mới chờ review, không tự
`expert_validated`; Question answered/resolved đúng quy trình. Sau đó đội 2 nối UI
với service và kiểm import/reindex/hỏi lại. **Chưa tuyên bố hoàn tất vòng feedback G2.**
