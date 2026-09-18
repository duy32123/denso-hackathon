# Bộ câu hỏi đánh giá retrieval (WP2)

> Thư mục này có **hai bộ tách rời**. `haas_real_dev.retrieval.v0.jsonl` là dữ liệu
> **thật** — số đo trên nó mới là kết quả. `synthetic_dev.qa.v0.jsonl` là dữ liệu
> **mô phỏng** để thử phần mềm (xem cuối trang). Không bao giờ cộng hai mẫu số.

`haas_real_dev.retrieval.v0.jsonl`: 54 câu real/dev, soạn trên bundle
`BUNDLE_HAAS_SMTC_DEV_e98521a7942a` (`B0_SRC_HAAS_0005` r1 và `REAL_WF_0001` r1).
Bundle hiện tại `BUNDLE_HAAS_SMTC_DEV_4d433ec6bd90` có thêm `REAL_WF_0002/0003`, nhưng mọi
claim của hai workflow này còn `source_review=pending`, nên corpus real được phục vụ vẫn chỉ
gồm B0 r2 và REAL_WF_0001 r1. B0 r1 vẫn giữ để tra cứu lịch sử, không phải revision active.
Khi hai workflow này được review, cần xem lại nhãn: ví dụ Q038
(alarm 2066) sẽ có quy trình ở `REAL_WF_0003`.
Q001–Q038 là bộ gốc; Q039–Q054 là câu phủ định bổ sung (cùng lĩnh vực CNC nhưng KB
không có), dùng để chỉnh ngưỡng từ chối.

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


---

# Bộ câu hỏi synthetic (kế hoạch đội 2, mục 1.5)

`synthetic_dev.qa.v0.jsonl`: **120 câu** trên KB mô phỏng ở
[data/synthetic_samples/serving](../synthetic_samples/README.md). Sinh bằng
`python scripts/build_synthetic_questions.py` từ chính KB đó nên gold đúng theo cấu
trúc; CI sinh lại và so từng byte.

**Số đo trên bộ này không phải kết quả.** Nó để thử phần mềm và chỉnh ngưỡng, báo
riêng, không cộng vào mẫu số của real/dev. Nhãn đều là `draft` — người soạn không
được tự kiểm nhãn của chính mình.

| Nhóm | Câu | Kỳ vọng |
|---|---|---|
| `tra_loi_duoc` | 46 | `answered`, có gold Step |
| `thieu_evidence` | 20 | `insufficient_evidence` nhưng retrieval **vẫn phải** tìm ra Step để WP3 từ chối có căn cứ |
| `khong_co_dap_an` | 12 | KB không có dữ liệu; 4 câu chủ thể có trong KB → `retrieved`, 8 câu chủ thể không có → `insufficient_evidence` |
| `quy_trinh` | 12 | `answered` + `intent=procedure`, chấm bằng `gold_workflows` |
| `nguon_mau_thuan` | 9 | `conflicting_sources`, trưng cả hai nguồn |
| `corpus_tieng_anh` / `viet_hoi_anh` | 8 / 8 | Câu tiếng Anh và câu tiếng Việt trên cùng nội dung tiếng Anh |
| `thieu_boi_canh` | 3 | `needs_clarification`: `DEMO_TC_A` 10 Nm còn `DEMO_TC_B` 15 Nm |
| `model_khong_ro` | 2 | **CẦN NGƯỜI CHỐT**: nguồn không nêu model |

62 câu vào mẫu số Recall/MRR (`answered` + `intent=detail`). Câu từ chối, hỏi lại và
procedure chấm qua `status` và `wf_acc`.

```powershell
python -m retrieval.importer import data/synthetic_samples/serving --db out/retrieval/synthetic_dev.sqlite --source-type synthetic --split dev
python -m retrieval.retrieval build --db out/retrieval/synthetic_dev.sqlite --mode synthetic --split dev --embedding none
python -m retrieval.evaluation run --db out/retrieval/synthetic_dev.sqlite --questions data/eval/synthetic_dev.qa.v0.jsonl --mode synthetic --split dev --strategy lexical
```

## Quy tắc gán nhãn đã dùng

Ghi ra để người kiểm đối chiếu được, thay vì phải đoán ý người soạn:

- Gold chỉ lấy Step thuộc latest revision, `lifecycle=active`, claim `support_status=supported`
  và không có conflict. Workflow bị rút và revision cũ **không bao giờ** làm gold.
- Một unit liệt kê **mọi** Step tương đương — cùng một câu hành động xuất hiện ở nhiều
  workflow. Tìm được một Step là đủ.
- Câu có nêu `machine_model` thì gold không được trỏ sang máy khác.
- Câu hỏi là paraphrase có dấu; corpus viết không dấu. Test chặn việc chép nguyên văn claim.
- Nhóm `thieu_evidence` chỉ dùng chủ đề **riêng** của nhóm thiếu thông tin, để không có
  workflow nào khác giải thích hộ — nếu không thì câu "vì sao" đáng lẽ phải trả lời được.

## Điều cần người kiểm quyết định

1. `model_khong_ro` (2 câu): nguồn không nêu model. Coi metadata `null` là "chưa rõ nên
   hỏi lại" hay "vẫn dùng được" là **quyết định chính sách của đội**, không phải lỗi nhãn.
2. `khong_co_dap_an`: ranh giới "chủ thể có trong KB" do người soạn phân, cần xác nhận lại.
