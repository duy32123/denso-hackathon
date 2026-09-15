# D2-B WP3 + D2-A API: grounded QA pilot

Nhánh triển khai sau merge PR #13. Không thay Schema 1.0.0 và không chọn thay đội
chính sách bỏ/giữ B0 trong corpus. Bản sửa evidence B0 r2 ở cuối tài liệu đã được
người dùng source-review và cho phép đưa vào pipeline; không tự gán review của con người.

## Phần đã triển khai

- **D2-B / WP3:** `retrieval/generation/` nhận evidence package, tái kiểm eligibility
  theo contract chung, sinh statement có claim/evidence refs, kiểm citation bằng code,
  rồi gọi Gemini lần hai kiểm nghĩa và xem có thực sự trả lời câu hỏi hay không.
- **D2-A / tích hợp backend:** `retrieval/api/` phục vụ `POST /v1/ask` đúng
  `QueryRequest` / `AnswerResponse`, route DB cố định theo corpus/split, kiểm index
  trước/sau generation, endpoint mở evidence đúng workflow/revision/index build.
- **D2-B / WP4 đọc + D2-A API:** trang `/` hỏi–đáp, tự mở citation, trình đọc
  Step/field/claim, attribution/scope, Question/Relation records và lịch sử/diff revision.
  Evidence nằm cạnh workflow; chưa có UI ghi feedback vì thiếu service ghi của đội 1.
  Hướng dẫn: [WP4 reader](team2_wp4_reader.md).
- Test offline unit + integration đi qua bundle/import/index/retrieval/HTTP/evidence;
  hai live smoke opt-in ở `tests/end_to_end/test_qa_gemini.py` dùng Gemini thật.

## Chạy trên PowerShell

Từ gốc repo, không cần activate:

```powershell
uv pip install --python .venv/Scripts/python.exe -e ".[dev,api,retrieval]"
```

Đặt `GEMINI_API_KEY` trong `.env` (không commit khóa). Nếu chưa có index hoặc đã
nhận bundle mới, chạy import/build; các lệnh này cập nhật **DB local**, không sửa KB:

```powershell
.\.venv\Scripts\python.exe -m retrieval.importer import acquisition/export/haas_pilot_dev_bundle --db out/retrieval/real_dev.sqlite --source-type real --split dev
.\.venv\Scripts\python.exe -m retrieval.retrieval build --db out/retrieval/real_dev.sqlite --mode real --split dev --embedding gemini
.\.venv\Scripts\python.exe -m retrieval.api
```

Mở <http://127.0.0.1:8000>. OpenAPI: <http://127.0.0.1:8000/docs>.
Thử câu “Bôi trơn con trượt của hốc dao như thế nào?”, context Haas / SMTC;
không điền model máy nếu chưa biết. Câu “Loại mỡ và cấp NLGI nào được chỉ định?”
phải từ chối khi KB không có thông tin này.

HTTP ví dụ:

```powershell
$qaRequest = @{
  question = "Bôi trơn con trượt của hốc dao như thế nào?"
  context = @{ manufacturer = "Haas"; subsystem = "SMTC" }
  mode = "real"
  dataset_split = "dev"
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/ask -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($qaRequest))
```

Biến môi trường (đặt trước khi chạy server):

| Biến | Mặc định / ý nghĩa |
|---|---|
| `KNOWFLOW_REAL_DEV_DB` | `out/retrieval/real_dev.sqlite` |
| `KNOWFLOW_SYNTHETIC_DEV_DB` | Không bật; cần DB synthetic riêng nếu dùng |
| `KNOWFLOW_RETRIEVAL_STRATEGY` | `hybrid`; `lexical` dùng được index không vector, nhưng không tự dịch query |
| `KNOWFLOW_ANSWER_MODEL` | `gemini-3.5-flash-lite`; không nhận model từ HTTP request |
| `KNOWFLOW_REPO_ROOT` | Thư mục chạy; nơi đọc `.env` và keyframe |

API chỉ mở localhost; chưa có authentication/deployment công khai. Không bật CORS
mở. Giữ caption nội bộ pilot theo `Source.access_note`; không phân phối rộng corpus.

## Các cổng kiểm

1. `retrieved` không có nghĩa `answered`. Needs-clarification / conflict / no-evidence
   trả ngay, không gọi answer model. Conflict chỉ có unresolved refs, không đề xuất thao tác.
2. Claim phải đúng một workflow/revision được chọn, latest active, đúng namespace,
   thỏa `claim_blockers`; giữ nguyên source/technical review từ snapshot.
3. Chỉ link `supported` có evidence mở được mới đưa vào generator. ID tự sinh,
   số liệu không nằm trong quote/observation đã cite, citation rỗng, procedure thiếu
   bước đều bị chặn. Không âm thầm bỏ bước rồi trình bày như quy trình đầy đủ.
4. Lượt kiểm nghĩa chỉ nhận claim/evidence **đã cite cho từng statement**, không
   được dùng claim lân cận để cứu một citation sai. Nếu có statement không đạt, toàn
   bộ câu trả lời chuyển `insufficient_evidence`. Không tự fallback ra kiến thức chung.
5. Prompt yêu cầu cùng ngôn ngữ câu hỏi nhưng thực tế chưa bảo đảm trả tiếng Việt;
   người dùng chọn demo bằng tiếng Anh và tạm hoãn lỗi này. Claim/quote gốc không dịch.
   Chỉ source_checked phải ghi “Theo nguồn (chưa có xác nhận kỹ thuật)” (hoặc tương đương
   tiếng Anh); synthetic luôn ghi dữ liệu mô phỏng. Không tự nâng technical review.
6. Index đổi khi đang trả lời → 503 để thử lại; không trả answer từ build stale.
   Citation cũ vẫn mở đúng snapshot cũ qua `index_build_id`, không tự nhảy latest.

Adapter gửi schema cấu trúc inline qua `response_json_schema`: endpoint live từ
chối `additional_properties` do đường `response_schema` của SDK tạo ra, và cũng
từ chối schema Pydantic đầy đủ. `provider_schema()` chỉ gửi type/properties/required/
items/enum. **Toàn bộ** giới hạn độ dài, số phần tử, revision và `extra=forbid` vẫn
được Pydantic kiểm sau phản hồi; không bỏ các cổng claim/evidence hay kiểm nghĩa.

`GET /v1/evidence/{workflow_id}/{revision}/{evidence_id}` yêu cầu query params
`mode`, `dataset_split`, `index_build_id`; thêm `/asset` để mở keyframe.
Chỉ đọc ảnh trong `acquisition/preprocessing/keyframes/`, kiểm ảnh giải mã được,
chặn path traversal/URL asset. Server không fetch URL từ bundle hoặc câu hỏi.

**“Mở được” có phạm vi rõ ràng:** speech/text mở excerpt gốc đã lưu, đối chiếu với
`Source.raw_text` và locator; visual mở keyframe local. Synthetic mở text mô phỏng,
không tạo video giả. `external_video_checked=false`: chưa kiểm video ngoài mạng
còn phát được. Bản transcript sửa chưa khớp raw_text hoặc ảnh chưa tải sẽ bị từ chối
bảo thủ; đội 1 cần cung cấp artifact tương ứng, không sửa quote để vượt cổng.

Generator nhận claim/quote/observation note và metadata dạng text, **chưa gửi pixel
keyframe vào LLM**. Mở được keyframe không có nghĩa model đã đối chiếu nội dung ảnh.

Lỗi HTTP có mã an toàn: 422 request/namespace; 404 evidence/asset; 429 đang bận;
503 index/provider; 504 timeout. Một request tối đa 90 giây và hai request đang chạy.
Timeout HTTP không giết thread/provider đang chạy: slot chỉ được nhả khi việc đó
kết thúc, để không tạo vô hạn request tính phí. Mỗi generation call timeout 30 giây.
Retrieval giữ retry policy WP2 hiện tại. Không cache answer.

## Kiểm thử và giới hạn

```powershell
.\.venv\Scripts\python.exe -m pytest
# Opt-in: gọi Gemini thật, cần index real/dev đã build, có thể tính phí.
$env:KNOWFLOW_LIVE_QA_TEST = "1"
.\.venv\Scripts\python.exe -m pytest tests/end_to_end/test_qa_gemini.py -v
Remove-Item Env:\KNOWFLOW_LIVE_QA_TEST
```

Unit/integration dùng model double **chỉ để kiểm logic**; live smoke hai câu không
phải benchmark. Lượt kiểm nghĩa LLM có thể sai, không phải bằng chứng entailment
toán học hay review của người/chuyên gia. Cần người kiểm câu trả lời/citation thực
trước khi chốt G1. Gold retrieval vẫn chưa được coi là human-reviewed.

Kết quả ngày 2026-09-15, sau khi người dùng cấp phép và cập nhật khóa local:

- Offline: **429 passed, 2 skipped** (hai live smoke là opt-in).
- Gemini live: **1 passed, 1 failed**, model `gemini-3.5-flash-lite`, retrieval hybrid.
  Report local: `out/eval/qa_live_smoke.xml` (gitignored).
- Câu hỏi loại mỡ/cấp NLGI trả `insufficient_evidence` đúng kỳ vọng.
- Câu hỏi cách bôi trơn con trượt cũng trả `insufficient_evidence`, khác kỳ vọng
  `answered`. Chẩn đoán thấy `B0_SRC_HAAS_0005_CL_020` (“Apply grease to the pocket
  slider.”) chỉ liên kết `B0_SRC_HAAS_0005_EV_019`, 147840–153660 ms. Quote dừng
  tại “we'll apply some”, chưa có phần nói về grease, dù link đang `supported`
  và claim `source_checked`. Một lượt chẩn đoán còn sinh draft tiếng Anh cho câu
  hỏi tiếng Việt; verifier trả `answers_question=false`, `supported=[false]`.
  Lượt chạy cuối vẫn abstain; không coi live flow trả lời được đã đạt G1.
- Index: `IDX_SEARCH_ee4a9fd09a27a1f5c08412a2bf35078daae1c1a055dc383c5abe02fd65ee5494`.

Cần đội 1 kiểm lại cửa sổ/link evidence của claim B0 và xuất revision đã review
đúng quy tắc bất biến, đồng thời chốt B0/REAL trong corpus phục vụ. Không sửa KB,
review flags hoặc nới verifier trong lần smoke này. Cần chạy lại live sau khi dữ
liệu được sửa; kết quả này không phải benchmark chất lượng hay review của người.

Còn lại: review thủ công G1 và nhãn eval; chốt corpus phục vụ B0/REAL; mở rộng eval
answer/citation và đo latency/cost; service ghi feedback D1-B/WP6 rồi nối WP4; mở rộng
retrieval lân cận/reranker khi có số đo. WP4 reader đã có browser smoke với Edge và model
giả; không thay thế kiểm câu trả lời thật hay đánh giá G1 của con người.

Tham khảo implementation: [Gemini structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/).

## Bản sửa evidence B0 r2 đã review và kiểm thử live

Đã chuẩn bị draft và snapshot nháp `B0_SRC_HAAS_0005.r2`, ghép `U0020 + U0021`
cho `CL_020` thành evidence mới `EV_033`; toàn bộ evidence r1 giữ nguyên ID/nội dung.
`duy32123` xác nhận kiểm xong; đã ghi 33/33 source_checked, promote và export/validate
bundle `BUNDLE_HAAS_SMTC_DEV_4d433ec6bd90`. Giữ nguyên r1, technical review và citation guard.
Sau khi người dùng cho phép gửi search text tới Gemini, đã import và build index mới:
`IDX_SEARCH_aca88334c758fbdfe8b092c513ffe7d9ef4a4d3dc93e163f783b32f14135f6ae`.

Lượt live tiếp theo: **2 passed** (`out/eval/qa_live_smoke_r2.xml`). Câu bôi trơn trả
`answered` với citation mở được; câu thiếu thông tin loại mỡ/NLGI trả `insufficient_evidence`.
Kết quả 1 pass/1 fail ở phần trước là lịch sử trước khi sửa evidence. Hai câu này vẫn
không phải benchmark và không thay thế kiểm UI/G1 của người dùng.

Gold retrieval: chỉ chuyển các ref B0 sang r2 sau khi đối chiếu Step/Claim/context;
31 câu bị ảnh hưởng trở lại draft chờ kiểm gold. Không lấy review nguồn làm review gold.
Chi tiết và bản ghi: [B0 r2 review](b0_wf0005_r2_review.md).
