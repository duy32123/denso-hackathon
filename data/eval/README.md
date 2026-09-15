# Bộ câu hỏi đánh giá retrieval (WP2)

`haas_real_dev.retrieval.v0.jsonl`: 54 câu real/dev, soạn trên bundle
`BUNDLE_HAAS_SMTC_DEV_e98521a7942a` (`B0_SRC_HAAS_0005` r1 và `REAL_WF_0001` r1).
Bundle hiện tại `BUNDLE_HAAS_SMTC_DEV_0209a847a66c` có thêm `REAL_WF_0002/0003`, nhưng mọi
claim của hai workflow này còn `source_review=pending`, nên corpus real được phục vụ vẫn chỉ
gồm hai workflow trên. Khi hai workflow này được review, cần xem lại nhãn: ví dụ Q038
(alarm 2066) sẽ có quy trình ở `REAL_WF_0003`.
Q001–Q038 là bộ gốc; Q039–Q054 là câu phủ định bổ sung (cùng lĩnh vực CNC nhưng KB
không có), dùng để chỉnh ngưỡng từ chối.

> **Chưa có người kiểm nhãn gold.** Q001–Q038 đã được AI (Codex) kiểm (`ai_reviewed`),
> Q039–Q054 còn là bản nháp (`draft`). Số đo chỉ dùng để debug pipeline,
> **không báo cáo như kết quả**. Evaluator in cảnh báo này cho đến khi mọi câu được người kiểm.

## Người kiểm cần làm

Người kiểm không được là người soạn nhãn. Không sửa JSONL bằng tay; dùng sheet:

```powershell
# 1. Xuất sheet: mỗi câu một dòng; cột gold hiện tiêu đề Step và nội dung claim
.\.venv\Scripts\python.exe -m retrieval.evaluation sheet --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl

# 2. Mở out/eval/haas_real_dev.retrieval.v0.sheet.csv bằng Excel hoặc Google Sheets,
#    điền cột decision:
#      ok    nhãn đúng
#      fix   đã sửa expected_status / expected_retrieval_status / gold_step_ids (bắt buộc ghi note)
#      drop  câu hỏi hỏng, bỏ khỏi bộ (bắt buộc ghi note)
#      (trống) chưa kiểm; có thể kiểm dần qua nhiều lần

# 3. Ghi kết quả vào file câu hỏi
.\.venv\Scripts\python.exe -m retrieval.evaluation apply --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --sheet out/eval/haas_real_dev.retrieval.v0.sheet.csv --reviewer-id <github-user>
```

Lượt kiểm bằng AI (ví dụ Codex) ghi bằng `--reviewer-kind ai --reviewer-id codex`:
nhãn thành `ai_reviewed`, lưu riêng ở `ai_reviewed_by`, `ai_reviewed_at`, `ai_review_note`.
Lượt này **không** tính là người kiểm (plan mục 4: gold do người kiểm, LLM chỉ hỗ trợ),
nên report vẫn in cảnh báo. Sheet xuất sau đó hiện ghi chú của AI trong cột `label_note`
để người kiểm đối chiếu nhanh. Lượt AI không được `drop` và không ghi đè nhãn người đã kiểm.

Cú pháp `gold_step_ids`: `|` ngăn các Step tương đương trong một unit, `;` ngăn các unit.
Ví dụ `B0_SRC_HAAS_0005_ST_006 | REAL_WF_0001_ST_007 ; B0_SRC_HAAS_0005_ST_007 | REAL_WF_0001_ST_007`.

| Cột | Sai nếu |
|---|---|
| `gold` | Step không chứa thông tin trả lời câu hỏi, hoặc còn Step khác cũng trả lời được mà chưa liệt kê. Xem các Step còn lại trong `data/workflows/dev/`. |
| `expected_retrieval_status` | Retrieval nên tìm Step liên quan mà nhãn ghi từ chối, hoặc ngược lại. |
| `expected_status` | Nguồn không đủ để trả lời mà nhãn vẫn ghi `answered`, hoặc ngược lại. Không dùng kiến thức riêng để bù chỗ nguồn thiếu. |

Cả sheet bị từ chối nếu có một dòng lỗi: câu hỏi đã đổi sau khi xuất sheet, `fix`/`drop`
thiếu note, `step_id` không tồn tại, nhãn mâu thuẫn, hoặc người kiểm trùng người soạn.
Sheet là file tạm trong `out/` (gitignore); bản ghi chính thức là file JSONL, cần commit.

Đặc biệt chốt các câu có ghi chú "CẦN NGƯỜI CHỐT" (Q036, Q038): đó là quyết định
chính sách, không phải lỗi nhãn.

Không tạo câu holdout trước khi khóa pipeline D15; không chỉnh tham số trên holdout.

## Trường dữ liệu

| Trường | Ý nghĩa |
|---|---|
| `question_id`, `source_type`, `dataset_split` | Phải khớp namespace của DB đang đánh giá. |
| `language`, `category`, `intent` | Để báo cáo theo nhóm. `intent=procedure` chấm chọn workflow, không tính Recall/MRR. |
| `context` | `QueryContext` gửi kèm câu hỏi, giống API. |
| `expected_status` | Trạng thái **câu trả lời** (`AnswerStatus`), dành cho WP3 và end-to-end. |
| `expected_retrieval_status` | Trạng thái mà **tầng retrieval** nên trả. Ví dụ, câu hỏi về mô-men siết: câu trả lời phải là `insufficient_evidence`, nhưng retrieval vẫn nên tìm Step liên quan (`retrieved`) để WP3 từ chối có căn cứ. |
| `gold_units` | Danh sách các "đơn vị thông tin cần tìm". Mỗi unit liệt kê mọi Step tương đương; tìm được một Step là đủ. |
| `gold_workflows` | Workflow chấp nhận được cho câu `procedure`. |
| `label` | `draft` / `reviewed`, người gán nhãn, người kiểm, ghi chú. |

Hai workflow hiện tại cùng lấy từ nguồn `SRC_HAAS_0005` và mô tả cùng một quy trình,
nên mỗi unit có một Step ở mỗi workflow. Nếu đội 1 bỏ một workflow khỏi corpus phục vụ,
evaluator sẽ báo gold "stale" và cần gán lại.

Gold gắn với `(workflow_id, revision, step_id)`. Khi có revision mới, evaluator dừng
và liệt kê các ref cần gán lại; không tự đoán Step tương ứng.

## Cách tính

- **Recall@k**: tỷ lệ gold unit tìm được trong top-k Step, lấy trung bình theo câu (macro).
- **MRR@k**: nghịch đảo thứ hạng của Step đúng đầu tiên; không có trong top-k thì tính 0.
- **Hit@1**, **answer coverage**: tỷ lệ câu có Step đúng ở hạng 1, và tỷ lệ câu trả `retrieved`.
- Mẫu số Recall/MRR chỉ gồm câu `expected_status=answered` và `intent=detail` (plan mục 4).
  Câu từ chối, hỏi lại hoặc procedure được chấm qua `status` (confusion matrix,
  `false_retrieved`, `missed`) và `wf_acc` (chọn đúng workflow).

## Chạy

```powershell
.\.venv\Scripts\python.exe -m retrieval.evaluation run --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --mode real --split dev
```

Mặc định chạy cả `lexical`, `vector`, `hybrid` trên cùng index, cùng filter policy và
cùng bản dịch câu hỏi. Query embedding và bản dịch được cache ở
`out/eval/query_embeddings.jsonl` và `out/eval/query_translations.jsonl` (khóa theo cấu hình
model và nguyên văn câu), nên chạy lại hoặc thử ngưỡng khác (`--min-term-coverage`) không tốn
API. Khi dùng cache, latency vẫn cộng thời gian API gốc; thời gian đợi 429 không được tính.
`--no-translation` để đo khi không dịch.
Kết quả ghi vào `out/eval/<run_id>/report.json` (kèm git commit, index build,
embedding config và sha256 của bộ câu hỏi) và `rows.jsonl` (từng câu, từng strategy).
