# Bộ câu hỏi đánh giá retrieval (WP2)

`haas_real_dev.retrieval.v0.jsonl`: 54 câu real/dev, soạn trên bundle
`BUNDLE_HAAS_SMTC_DEV_e98521a7942a` (`B0_SRC_HAAS_0005` r1 và `REAL_WF_0001` r1).
Từ PR #17 (18/09), bundle `BUNDLE_HAAS_SMTC_DEV_20382d7957b6` có `REAL_WF_0002` r2 và `REAL_WF_0003` r2 đã
`source_checked`, nên corpus real được phục vụ gồm **B0 r2, REAL_WF_0001 r1, REAL_WF_0002 r2,
REAL_WF_0003 r2**. B0 r1 và r1 của 0002/0003 vẫn giữ để tra cứu lịch sử, không phải revision
active. Nhãn **chưa được xem lại** cho corpus này (xem cảnh báo bên dưới), ví dụ
`HAAS_DEV_Q038` (alarm 2066) giờ có thể có quy trình ở `REAL_WF_0003`.
Q001–Q038 là bộ gốc; Q039–Q054 là câu phủ định bổ sung (cùng lĩnh vực CNC nhưng KB
không có), dùng để chỉnh ngưỡng từ chối.

> **Corpus đã đổi, nhãn chưa theo kịp (18/09).** PR #17 review xong `REAL_WF_0002/0003` nên
> corpus phục vụ giờ là **4 workflow / 38 Step** (trước là 2 / 20). Nhãn của bộ này vẫn soạn cho
> corpus cũ: `gold_workflows` chỉ có B0 và `REAL_WF_0001`, và nhiều câu phủ định Q039–Q054 có thể
> đã có đáp án. Đo lexical, không dịch, trên cùng bộ câu: `false_retrieved` 7 → 15, `wf_acc`
> 0.613 → 0.484, status 0.648 → 0.537. Phần lớn là do nhãn cũ, không phải retrieval kém đi.
> Evaluator **không tự phát hiện** câu vừa có đáp án (nó chỉ chặn ref sai revision), nên người kiểm
> phải xem lại cả câu phủ định và `gold_workflows` trên corpus mới trước khi báo bất kỳ số nào.

> **Chưa có người kiểm nhãn gold.** Q032–Q038 giữ lượt AI review (`ai_reviewed`).
> Q001–Q031 về `draft` sau khi chuyển B0 r1 sang r2; Q039–Q054 vẫn là bản nháp.
> Số đo chỉ dùng để debug pipeline,
> **không báo cáo như kết quả**. Evaluator in cảnh báo này cho đến khi mọi câu được người kiểm.

Bảo trì ref ngày 2026-09-15: đối chiếu xác nhận toàn bộ Step, nội dung/ID Claim và
context của B0 không đổi giữa r1/r2; chỉ cửa sổ evidence của CL_020 được mở rộng.
Chuyển ref B0 của 31 câu sang r2, giữ nguyên câu hỏi, gold Step ID và các trạng thái kỳ vọng.
Đây không phải lượt gán lại nhãn theo kết quả retrieval và không phải human review.
Note AI cũ vẫn lưu để đối chiếu r1; các câu bị ảnh hưởng chờ kiểm lại gold trên r2.
Review nguồn của `duy32123` không áp dụng cho nhãn eval. Cần xuất sheet mới sau thay đổi;
sheet cũ của những câu này có fingerprint không còn khớp. Evaluator vẫn từ chối ref stale,
không tự động ánh xạ revision trong lúc chấm điểm.

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

Đặc biệt chốt các câu có ghi chú "CẦN NGƯỜI CHỐT" (`HAAS_DEV_Q036`, `HAAS_DEV_Q038`): đó là quyết định
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

`B0_SRC_HAAS_0005` và `REAL_WF_0001` cùng lấy từ nguồn `SRC_HAAS_0005` và mô tả cùng một
quy trình, nên mỗi unit hiện có một Step ở mỗi workflow đó. `REAL_WF_0002` (mòn double arm) và
`REAL_WF_0003` (khôi phục sau alarm) là nguồn khác; nhãn hiện **chưa** liệt kê Step nào của chúng. Nếu đội 1 bỏ một workflow khỏi corpus phục vụ,
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

## Đánh giá câu trả lời (WP3)

`retrieval.evaluation answers` chạy **đúng đường phục vụ** (`QAService`, cùng đường mà
`/v1/ask` dùng) trên chính bộ câu hỏi này, rồi chấm ở mức câu trả lời. Dùng lại
`expected_status` đã có, nên không cần bộ câu hỏi thứ hai.

```powershell
.\.venv\Scripts\python.exe -m retrieval.evaluation answers --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --mode real --verdict-template <github-user>
```

Kết quả vào `out/eval/<run_id>/report.json` + `rows.jsonl`, giống lệnh `run`.
Query embedding và bản dịch dùng chung cache với `run`. Holdout bị chặn: đường phục vụ
hiện chỉ bật `dev`.

### Hai nhóm chỉ số tách bạch

**Code chứng minh được** — chạy trên mọi câu trả lời, sai là lỗi phần mềm:

| Chỉ số | Nội dung |
|---|---|
| `status.accuracy` | `status` so với `expected_status`, kèm confusion matrix theo nhóm |
| `status.false_answer` | Trả lời khi nguồn không đủ. **Lỗi nguy hiểm nhất**, liệt kê từng câu |
| `status.false_abstention` | Từ chối câu trả lời được — lỗi mà tỷ lệ abstain cao che mất |
| `citations.mechanically_valid` | Claim có trong snapshot, đúng revision active, đủ điều kiện, evidence link `supported` và mở được, review flags khớp snapshot, mọi con số trong câu có trong evidence được cite |
| `grounding.structural` | Tỷ lệ dòng kỹ thuật có citation. Dòng không citation là **chắc chắn** không có căn cứ |
| `grounding.abstain_with_citations` | Câu từ chối mà vẫn kèm citation |
| `leakage` | Trộn corpus, ghép nhiều workflow (D-06), khác model đã biết. **Phải bằng 0** |
| `latency_ms`, `cost` | p50/p95, số lần gọi provider, token do provider báo |

Mã lỗi citation được liệt kê tên (`not_the_active_revision`, `evidence_not_openable`,
`number_not_in_cited_evidence`, …) để sửa được, không chỉ ra một con số.

**Cần người kiểm** — `null` cho đến khi có file verdict:

| Chỉ số | Mục tiêu plan |
|---|---|
| `citation_correctness` | ≥ 90% real/dev — code chứng minh hợp lệ **và** người kiểm xác nhận nguồn hỗ trợ đúng phát biểu gắn nó |
| `answer_groundedness` | ≥ 90% real/dev |
| `answers_question` | Câu trả lời có thực sự trả lời câu hỏi |

Lượt kiểm nghĩa bằng LLM trong pipeline **là thứ đang bị đo**, không được tự chấm mình.
Tỷ lệ mechanical là **sàn**: nó chỉ có thể giảm khi người kiểm vào, không bao giờ tăng.

### Người kiểm câu trả lời cần làm

1. Chạy lệnh trên với `--verdict-template <github-user>` → `out/eval/<run_id>/verdicts.template.jsonl`.
   Mỗi dòng đã điền sẵn `answer_sha256`, kèm `_answer` và `_citations` để đọc.
2. Điền `answers_question` (true/false) và `citations_supported` (mỗi citation một boolean:
   nguồn được cite **có** hỗ trợ đúng phát biểu đó không). Các khóa bắt đầu bằng `_` được bỏ qua.
3. Chạy lại với `--verdicts <file đã điền>`.

Verdict gắn chặt với `answer_sha256`. Câu trả lời đổi (đổi prompt, model, index, corpus)
thì verdict cũ thành `stale` và bị loại, không được cộng sang bản mới. Verdict chấm thiếu
hoặc thừa citation so với câu trả lời thì bị từ chối cả file.

### Chi phí

`--price-input` và `--price-output` (USD trên một triệu token) phải cho **cả hai** thì mới
tính tiền; thiếu một cái thì `usd_total` là `null`. Không hardcode bảng giá vào repo — giá
đổi và một con số sai còn tệ hơn không có. Nếu provider không báo token thì token và chi phí
là `null`, **không phải 0**.
