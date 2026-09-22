# Bộ câu hỏi đánh giá retrieval (WP2)

> Thư mục này có **hai bộ tách rời**. `haas_real_dev.retrieval.v0.jsonl` là dữ liệu
> **thật** — số đo trên nó mới là kết quả. `synthetic_dev.qa.v0.jsonl` là dữ liệu
> **mô phỏng** để thử phần mềm (xem cuối trang). Không bao giờ cộng hai mẫu số.

`haas_real_dev.retrieval.v0.jsonl`: **66 câu real/dev: 52 `reviewed`, 14 `draft`**.
52 câu cũ được người kiểm (`duy32123`, 2026-09-22); Q055–Q068 mới bổ sung vẫn giữ
trạng thái draft trong file, nên phép đo gộp chỉ dùng chẩn đoán, chưa phải kết quả công bố.
Xem [bản sửa alias SMTC và phép đo đối chứng](../../docs/retrieval_smtc_alias_fix.md).
Phần số đo/lượt kiểm bên dưới ghi lại **mốc 52 câu**. Soạn ban đầu 54 câu trên bundle
`BUNDLE_HAAS_SMTC_DEV_e98521a7942a`; `Q036` và `Q038` bị drop khi kiểm.
Corpus phục vụ hiện tại là `BUNDLE_HAAS_SMTC_DEV_20382d7957b6`: **B0 r2, REAL_WF_0001 r1,
REAL_WF_0002 r2, REAL_WF_0003 r2**. B0 r1 và r1 của 0002/0003 vẫn giữ để tra cứu lịch sử,
không phải revision active.
Q001–Q035, Q037 là bộ gốc; Q039–Q054 là câu phủ định bổ sung (cùng lĩnh vực CNC nhưng KB
không có), dùng để chỉnh ngưỡng từ chối.

Lượt kiểm và lý do từng quyết định: [gold review worklist](../../docs/gold_review_worklist_real_dev.md).
Số đo đầu tiên được phép báo cáo: [kết quả retrieval real/dev](../../docs/retrieval_eval_real_dev.md)
— hybrid Recall@5 **0.926** (ngưỡng kế hoạch ≥0.85), nhóm từ chối **12/21** sau khi hiệu
chỉnh cổng liên quan từ 0.10 lên **0.20**. Lưu ý ngưỡng ≥0.90 của kế hoạch là chỉ số **tầng
câu trả lời** (`expected_status`, đo bằng `evaluation answers`), không phải con số tầng
retrieval ở đây.

> **Giới hạn của mốc 52 câu phải nêu kèm số đo lịch sử.** Bộ câu hỏi khi đó chỉ phủ **20/38 Step** của corpus phục
> vụ: `REAL_WF_0002` và `REAL_WF_0003` **không có câu hỏi nào** nhắm tới, vì bộ này soạn khi
> corpus mới có hai workflow thay hốc dao. 18 Step của hai workflow đó hiện chỉ đóng vai
> nhiễu. Mẫu số Recall/MRR là **27 câu**, không phải 52.

> **Corpus đã đổi (18/09): phần lớn chỗ tụt là lỗi retrieval, không phải do nhãn.** PR #17 đưa
> `REAL_WF_0002/0003` vào corpus phục vụ (**4 workflow / 38 Step**, trước là 2 / 20). Đo lexical,
> không dịch, trên cùng bộ câu: 18/54 câu đổi kết quả, `false_retrieved` 7 → 15. Bản ghi trước
> (PR #18) ghi rằng phần lớn là do nhãn cũ; **nhận định đó sai**. Tách ra thì:
> - **Routing nghiêng về `REAL_WF_0003`**: các câu thay pocket (Q008, Q013, Q019, Q029) bị đưa
>   sang quy trình khôi phục sau alarm. Đã sửa một phần bằng `best_step` (xem `retrieval/README.md`);
>   Q008 và Q013 vẫn sai.
> - **Cổng liên quan quá lỏng khi corpus lớn**: các câu ngoài phạm vi như băng tải phoi, lọc máy nén
>   khí, dây đai trục chính, lọc thủy lực máy tiện (Q042, Q044, Q047, Q049, Q053…) giờ có kết quả.
>   **Chưa sửa**; ngưỡng 0.10 cần hiệu chỉnh lại.
> - **Nhãn thật sự lỗi thời**: lượt kiểm 22/09 xác nhận **đúng một câu** — `HAAS_DEV_Q038`
>   (alarm 2066), nay đã drop. Lo ngại "gold thiếu Step của `REAL_WF_0002/0003`" **không xảy
>   ra**: cả 31 câu có gold đều hỏi về thay hốc dao, không câu nào thuộc địa hạt hai workflow
>   đó. Vấn đề thật là ngược lại — hai workflow ấy **không có câu hỏi nào** (xem giới hạn
>   20/38 Step ở đầu trang).
>
> Evaluator **không tự phát hiện** câu vừa có đáp án (nó chỉ chặn ref sai revision), nên việc
> rà lại phải làm bằng người — đã làm ngày 22/09.
>
> **Thứ tự việc:** kiểm nhãn phải xong **trước** khi hiệu chỉnh ngưỡng cổng liên quan. Nếu
> chỉnh trên nhãn cũ, `Q038` bị tính là dương tính giả và sẽ kéo ngưỡng lên, làm hệ thống từ
> chối oan. Sau lượt kiểm, `false_retrieved` còn **14 câu** và đều là lỗi ngưỡng thật.

> **Đã có người kiểm (2026-09-22).** 52/52 câu `status=reviewed`, `reviewed_by=duy32123`.
> Người soạn nhãn là `claude-draft` (AI) nên người kiểm không trùng người soạn. Không câu nào
> bị `fix`: **không có nhãn nào bị sửa cho khớp kết quả engine**. Evaluator đã thôi in cảnh
> báo "not human-checked", nên số đo được phép báo cáo — kèm giới hạn 20/38 Step ở trên.

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

Hai câu từng ghi "CẦN NGƯỜI CHỐT" (`HAAS_DEV_Q036`, `HAAS_DEV_Q038`) đã được xử lý trong
lượt kiểm 22/09: cả hai bị drop, lý do ghi ở
[worklist](../../docs/gold_review_worklist_real_dev.md).

**Chính sách đã chốt kèm theo:** metadata model rỗng (`machine_model = null`) ⇒ **trả lời kèm
phạm vi nguồn**, không hỏi lại. Không áp cho ca mâu thuẫn model (`Q037`), ca đó vẫn
`needs_clarification`.

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

---

# Bộ câu hỏi synthetic (kế hoạch đội 2, mục 1.5)

`synthetic_dev.qa.v0.jsonl`: **116 câu** trên KB mô phỏng ở
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
| `quy_trinh` | 8 | `answered` + `intent=procedure`, chấm bằng `gold_workflows`; chỉ hỏi khi mọi workflow ứng viên đều sạch |
| `nguon_mau_thuan` | 9 | `conflicting_sources`, trưng cả hai nguồn |
| `corpus_tieng_anh` / `viet_hoi_anh` | 8 / 8 | Câu tiếng Anh và câu tiếng Việt trên cùng nội dung tiếng Anh |
| `thieu_boi_canh` | 3 | `needs_clarification`: `DEMO_TC_A` 10 Nm còn `DEMO_TC_B` 15 Nm |
| `model_khong_ro` | 2 | Chính sách đã chốt 22/09: `null` ⇒ trả lời kèm phạm vi. Bộ này **sinh từ generator**, cần sửa `scripts/build_synthetic_questions.py` chứ không sửa JSONL |

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
- `quy_trinh` chỉ hỏi cặp (chủ đề, model) mà **mọi** workflow khớp đều không có conflict
  và mọi claim `supported`. Nếu retrieval chọn trúng bản có nguồn mâu thuẫn thì từ chối
  mới là đúng, nên nhãn `answered` ở đó sẽ phạt câu trả lời đúng.
- Các bước của một workflow theo thứ tự hợp lý (ngắt nguồn → đánh dấu → tháo → … →
  chạy thử) và luôn có bước làm đúng việc tên chủ đề nói. Trước bản này các bước bị xáo
  trộn và không bước nào "bôi trơn" trong quy trình "bôi trơn", nên người kiểm (và cả
  model) chấm đúng là câu trả lời không trả lời câu hỏi.

## Điều cần người kiểm quyết định

1. `model_khong_ro` (2 câu): nguồn không nêu model. Coi metadata `null` là "chưa rõ nên
   hỏi lại" hay "vẫn dùng được" là **quyết định chính sách của đội**, không phải lỗi nhãn.
2. `khong_co_dap_an`: ranh giới "chủ thể có trong KB" do người soạn phân, cần xác nhận lại.
