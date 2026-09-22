# Kết quả retrieval trên real/dev — 2026-09-22

**Số đo đầu tiên được phép báo cáo.** Trước ngày này evaluator in cảnh báo
`not human-checked` và kế hoạch cấm báo cáo. Nhãn gold đã được người kiểm
(52/52, `reviewed_by=duy32123`), xem [worklist](gold_review_worklist_real_dev.md).

| | |
|---|---|
| Run | `EVAL_20260922T112143Z_4c892771` |
| Index | `IDX_SEARCH_b9c6c8a74f8b6171…` |
| Bundle | `BUNDLE_HAAS_SMTC_DEV_20382d7957b6` — 4 workflow, 38 Step |
| Bộ câu hỏi | `haas_real_dev.retrieval.v0.jsonl`, sha256 `4eb536aa4255e2bd…`, 52 câu |
| Embedding | `gemini-embedding-001`, 768 chiều |
| Dịch truy vấn | `gemini-3.5-flash-lite`, prompt `q2en-2` |

## Kết quả

| | lexical | vector | hybrid | Ngưỡng kế hoạch |
|---|---|---|---|---|
| **Recall@5** (n=27) | 0.889 | 0.889 | **0.926** | ≥ 0.85 ✅ |
| MRR@5 (n=27) | 0.728 | **0.870** | 0.840 | theo dõi |
| Hit@1 (n=27) | 0.593 | **0.852** | 0.778 | — |
| answer_coverage | 1.000 | 1.000 | 1.000 | — |
| wf_accuracy (n=31) | 0.903 | 0.903 | **0.935** | — |
| **Trạng thái từ chối/hỏi lại** (n=21) | 0.381 | 0.381 | 0.381 | ≥ 0.90 ❌ |
| Trạng thái tìm được (n=31) | 1.000 | 1.000 | 1.000 | — |
| p50 / p95 (ms) | 1011 / 2157 | 1343 / 1921 | 1359 / 1907 | — |

Độ trễ **bao gồm lời gọi Gemini**; lexical vẫn tốn ~1s vì câu tiếng Việt phải dịch.

## Đọc kết quả

**Một chỉ số đạt, một chỉ số trượt xa.** Tìm thì tốt hơn ngưỡng; từ chối thì kém hơn
ngưỡng rất nhiều.

- **31/31 câu có đáp án đều được tìm ra** ở cả ba strategy, `missed` rỗng. Hệ thống
  **chưa từng từ chối oan** một câu trả lời được.
- **Chỉ 8/21 câu đáng bị từ chối thì bị từ chối đúng.** 13 câu ngoài phạm vi (dầu hộp số,
  dây đai trục chính, băng tải phoi, lọc khí nén, pin điều khiển, offset dao, homing trục,
  bộ thay dao ô…) vẫn ra kết quả.

**Sai số đi một chiều**, và đó là chiều an toàn hơn ở tầng retrieval — WP3 còn một cổng
từ chối nữa phía sau. Nhưng 0.381 so với ngưỡng 0.90 là khoảng cách không thể bỏ qua.

### Lỗi nằm ở cổng liên quan, không ở strategy

Cả ba strategy có **cùng `status_accuracy` 0.750, cùng 13 câu `false_retrieved`, cùng danh
sách**. Đây là bằng chứng dứt khoát: vấn đề từ chối nằm hoàn toàn ở cổng liên quan
(`--min-term-coverage`, mặc định 0.10), không ở cách xếp hạng. Đổi strategy sẽ không cứu
được chỉ số này; phải hiệu chỉnh ngưỡng.

Giờ mới hiệu chỉnh được: ngưỡng phải chỉnh **trên nhãn đã kiểm**. Nếu chỉnh trên nhãn cũ,
`Q038` (alarm 2066, nhãn cũ sai) sẽ bị tính là dương tính giả và kéo ngưỡng lên, gây từ
chối oan.

### Hybrid hơn ở đâu, vector hơn ở đâu

Báo theo số tuyệt đối vì n nhỏ:

| | lexical | vector | hybrid |
|---|---|---|---|
| Recall@5 (trên 27) | 24 | 24 | **25** |
| Hit@1 (trên 27) | 16 | **23** | 21 |
| wf đúng (trên 31) | 28 | 28 | **29** |

- **Hybrid hơn vector đúng 1 câu** ở Recall@5 và 1 câu ở wf_accuracy. **Không đủ để kết
  luận hybrid tốt hơn** — đúng như kế hoạch dặn: "không dựa vài điểm phần trăm để tuyên bố
  hơn baseline chắc chắn".
- **Vector hơn lexical 7 câu ở Hit@1** (23 vs 16). Đây mới là khác biệt đáng kể: lexical
  tìm được nhưng xếp hạng kém hơn hẳn.
- Vector hơn hybrid 2 câu ở Hit@1. Hướng ngược với Recall — hybrid gộp thêm ứng viên lexical
  nên phủ rộng hơn nhưng đẩy đáp án đúng khỏi hạng 1 đôi lúc.

**Chưa đổi strategy mặc định.** `hybrid` vẫn hợp lý (phủ rộng nhất, và top-k mới là cái đi
vào prompt chứ không phải hạng 1). Nếu sau này đo trên bộ lớn hơn mà vector vẫn dẫn Hit@1
thì cân nhắc lại.

### Dịch truy vấn là yếu tố lớn nhất

Đo lexical **không dịch** trên cùng 52 câu đã kiểm: **Recall@5 = 0.556**. Bật dịch:
**0.889**. Chênh **9 câu trên 27**.

(Lượt không dịch chạy trên index dựng với `--embedding none`, nên `index_build_id` khác;
xếp hạng lexical là BM25 trên cùng 42 record nên vẫn so sánh được.)

37/52 câu là tiếng Việt còn corpus là tiếng Anh, nên đây là kết quả dễ hiểu — nhưng nó nói
rõ: **nhánh dịch là thành phần không được tắt**, và một lỗi ở đó tốn nhiều hơn bất kỳ lựa
chọn strategy nào.

### Theo nhóm câu hỏi (Recall@5)

| Nhóm | n | lexical | vector | hybrid |
|---|---|---|---|---|
| `detail` | 18 | 0.944 | 0.944 | **1.000** |
| `multi_unit` | 2 | 1.000 | 1.000 | 1.000 |
| `no_diacritics` | 4 | 0.750 | **0.500** | 0.750 |
| `paraphrase` | 3 | 0.667 | **1.000** | 0.667 |

n từ 2–4 nên chỉ là chỉ dấu. Hai hướng đáng theo dõi khi có thêm câu hỏi: vector **kém**
với tiếng Việt không dấu, và vector **tốt** với paraphrase. Cả hai đều khớp trực giác về
embedding, nhưng chưa đủ mẫu để khẳng định.

## Giới hạn phải nêu kèm mọi con số

1. **Bộ câu hỏi chỉ phủ 20/38 Step.** `REAL_WF_0002` và `REAL_WF_0003` không có câu hỏi nào;
   18 Step của chúng hiện chỉ đóng vai nhiễu. Recall/MRR ở đây là chỉ số của **2 trong 4
   workflow**, không phải của cả corpus.
2. **Mẫu số nhỏ**: 27 câu cho Recall/MRR, 21 câu cho nhóm từ chối, 31 cho wf_accuracy.
   Chênh 1 câu = 3.7 điểm phần trăm.
3. **Một nguồn, một cụm máy.** Ba video Haas về SMTC. Không suy rộng sang máy khác, hãng
   khác, hay môi trường DENSO.
4. **Chưa đo trên holdout.** Bundle holdout có 2 nguồn, 0 workflow.
5. **Đây là chỉ số retrieval, không phải chất lượng câu trả lời.** `citation_correctness` và
   `answer_groundedness` vẫn `null` cho tới khi có người điền verdict
   (`evaluation answers --verdict-template`).

## Chạy lại

```powershell
.\.venv\Scripts\python.exe -m retrieval.retrieval build --db out/retrieval/real_dev.sqlite --mode real --split dev --embedding gemini
.\.venv\Scripts\python.exe -m retrieval.evaluation run --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --mode real --split dev
```

Cần `GEMINI_API_KEY` trong `.env`. Lượt này tốn 44 call embedding + 35 call dịch, có gặp
429 hai lần và tự retry theo `retryDelay`. Query embedding và bản dịch được cache ở
`out/eval/query_embeddings.jsonl` / `query_translations.jsonl`, nên chạy lại hoặc thử ngưỡng
khác không tốn thêm call.

## Việc tiếp theo

- [ ] **Hiệu chỉnh `--min-term-coverage`** trên nhãn đã kiểm — đây là việc duy nhất sửa được
      chỉ số 0.381. Quét ngưỡng dùng cache, không tốn API.
- [ ] Soạn 10–14 câu cho `WF_0002`/`WF_0003` để bộ câu hỏi phủ hết corpus.
- [ ] Người kiểm điền verdict để có `citation_correctness` / `answer_groundedness`.
