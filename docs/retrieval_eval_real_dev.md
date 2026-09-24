# Kết quả retrieval trên real/dev — 2026-09-22

> **Mốc lịch sử trên 52 câu, trước bản sửa alias SMTC.** File câu hỏi sau đó đã có thêm
> 14 câu (Q055–Q068, người kiểm duyệt 2026-09-24). [Bản sửa subsystem và phép đo đối chứng](retrieval_smtc_alias_fix.md)
> ghi kết quả mới cùng hồi quy Q046; không dùng các số dưới đây như số đo của mã hiện tại.

> Kết quả mới nhất cho cổng liên quan: [claim-coherence và đối chứng cache-only](retrieval_relevance_gate.md).

**Số đo đầu tiên được phép báo cáo.** Trước ngày này evaluator in cảnh báo
`not human-checked` và kế hoạch cấm báo cáo. Nhãn gold đã được người kiểm
(52/52, `reviewed_by=duy32123`), xem [worklist](gold_review_worklist_real_dev.md).

| | |
|---|---|
| Run | `EVAL_20260922T114433Z_3029b441` |
| Index | `IDX_SEARCH_b9c6c8a74f8b6171…` |
| Bundle | `BUNDLE_HAAS_SMTC_DEV_20382d7957b6` — 4 workflow, 38 Step |
| Bộ câu hỏi | `haas_real_dev.retrieval.v0.jsonl`, sha256 `4eb536aa4255e2bd…`, 52 câu |
| Embedding | `gemini-embedding-001`, 768 chiều |
| Dịch truy vấn | `gemini-3.5-flash-lite`, prompt `q2en-2` |
| Cổng liên quan | `min_term_coverage = 0.20` (hiệu chỉnh hôm nay, trước là 0.10) |

## Kết quả

| | lexical | vector | hybrid |
|---|---|---|---|
| **Recall@5** (n=27) | 0.889 | 0.889 | **0.926** |
| MRR@5 (n=27) | 0.728 | **0.870** | 0.840 |
| Hit@1 (n=27) | 0.593 | **0.852** | 0.778 |
| answer_coverage | 1.000 | 1.000 | 1.000 |
| wf_accuracy (n=31) | 0.903 | 0.903 | **0.935** |
| status accuracy (n=52) | 0.827 | 0.827 | 0.827 |
| — tìm được đúng (n=31) | 31/31 | 31/31 | 31/31 |
| — từ chối/hỏi lại đúng (n=21) | 12/21 | 12/21 | 12/21 |
| p50 / p95 (ms) | 976 / 1459 | 1386 / 1959 | 1379 / 1954 |

**Recall@5 đạt ngưỡng kế hoạch ≥0.85** (hybrid 0.926). Độ trễ **bao gồm lời gọi Gemini**;
lexical vẫn tốn ~1s vì câu tiếng Việt phải dịch.

> **`status accuracy` ở đây là chỉ số của tầng retrieval**, so với
> `expected_retrieval_status`. Ngưỡng ≥0.90 mà kế hoạch đội 2 đặt cho nhóm
> clarify/abstain/conflict là chỉ số **tầng câu trả lời**, so với `expected_status`, đo bằng
> `evaluation answers` qua đường phục vụ — **chưa chạy**. Hai số liên quan chặt (50/52 câu
> hai tầng kỳ vọng giống nhau) nhưng không được coi là một.

## Đọc kết quả

- **31/31 câu có đáp án đều được tìm ra** ở cả ba strategy, `missed` rỗng. Hệ thống
  **chưa từng từ chối oan** một câu trả lời được.
- **12/21 câu đáng bị từ chối thì bị từ chối đúng.** 9 câu ngoài phạm vi vẫn ra kết quả.
- Sai số đi **một chiều**, và là chiều an toàn hơn ở tầng retrieval: WP3 còn một cổng từ
  chối nữa phía sau, nên `false_retrieved` còn cứu được; từ chối oan thì không.

### Lỗi nằm ở cổng liên quan, không ở strategy

Cả ba strategy có **cùng `status_accuracy`, cùng số `false_retrieved`, cùng danh sách** — ở
cả ngưỡng cũ lẫn ngưỡng mới. Vấn đề từ chối nằm hoàn toàn ở cổng liên quan, không ở cách
xếp hạng. Đổi strategy không cứu được chỉ số này.

## Hiệu chỉnh cổng liên quan

Quét ngưỡng trên **nhãn đã kiểm**, dùng cache nên **0 lời gọi API**:

| ngưỡng | từ chối đúng | tìm được đúng | status | false_retrieved | missed | R@5 |
|---|---|---|---|---|---|---|
| 0.00 | 2/21 | 31/31 | 0.635 | 19 | 0 | 0.926 |
| 0.05 | 7/21 | 31/31 | 0.731 | 14 | 0 | 0.926 |
| 0.10 *(cũ)* | 8/21 | 31/31 | 0.750 | 13 | 0 | 0.926 |
| 0.15 | 9/21 | 31/31 | 0.769 | 12 | 0 | 0.926 |
| **0.20 *(mới)*** | **12/21** | **31/31** | **0.827** | **9** | **0** | **0.926** |
| 0.25 | 14/21 | 29/31 | 0.827 | 7 | 2 | 0.889 |
| 0.30 | 15/21 | 29/31 | 0.846 | 6 | 2 | 0.889 |
| 0.35 | 17/21 | 29/31 | 0.885 | 4 | 2 | 0.889 |
| 0.40 | 18/21 | 28/31 | 0.885 | 3 | 3 | 0.852 |
| 0.50 | 21/21 | 25/31 | 0.885 | 0 | 6 | 0.778 |

**0.20 là điểm cuối cùng còn miễn phí.** Từ 0.10 lên 0.20: từ chối đúng 8 → 12 câu, mà
`missed` vẫn 0 và Recall@5 **không đổi**. Không có gì xấu đi.

Từ 0.25 trở lên, mỗi câu từ chối thêm phải đổi bằng một câu trả lời được. Muốn đạt từ chối
≥0.90 (tức ≥19/21) phải lên khoảng 0.45, và mất 3–6 câu có đáp án.

**Chọn 0.20** vì hai lý do:

1. Nó là cải thiện thuần — không đánh đổi gì.
2. Từ chối oan **không cứu lại được**, còn `false_retrieved` thì WP3 vẫn có cơ hội chặn.
   Đây cũng là nguyên tắc `retrieval/README.md` đã ghi từ đầu.

Chín câu còn lọt (`Q033`, `Q040`, `Q044`, `Q047`, `Q048`, `Q049`, `Q051`, `Q052`, `Q053`)
là việc của cổng từ chối ở WP3, hoặc cần một tín hiệu khác ngoài độ phủ từ vựng.

> Ngưỡng này phụ thuộc cỡ corpus. Thêm workflow là phải quét lại — quét tốn 0 API call khi
> cache còn.

### Hybrid hơn ở đâu, vector hơn ở đâu

Báo theo số tuyệt đối vì n nhỏ:

| | lexical | vector | hybrid |
|---|---|---|---|
| Recall@5 (trên 27) | 24 | 24 | **25** |
| Hit@1 (trên 27) | 16 | **23** | 21 |
| wf đúng (trên 31) | 28 | 28 | **29** |

- **Hybrid hơn vector đúng 1 câu** ở Recall@5 và 1 câu ở wf_accuracy. **Không đủ để kết luận
  hybrid tốt hơn** — đúng như kế hoạch dặn: "không dựa vài điểm phần trăm để tuyên bố hơn
  baseline chắc chắn".
- **Vector hơn lexical 7 câu ở Hit@1** (23 vs 16). Đây mới là khác biệt đáng kể: lexical tìm
  được nhưng xếp hạng kém hơn hẳn.
- Vector hơn hybrid 2 câu ở Hit@1 — hướng ngược với Recall: hybrid gộp thêm ứng viên lexical
  nên phủ rộng hơn nhưng đôi lúc đẩy đáp án đúng khỏi hạng 1.

**Giữ `hybrid` làm mặc định.** Phủ rộng nhất, và top-k mới là cái đi vào prompt chứ không
phải hạng 1. Nếu bộ câu hỏi lớn hơn mà vector vẫn dẫn Hit@1 thì cân nhắc lại.

### Dịch truy vấn là yếu tố lớn nhất

Đo lexical **không dịch** trên cùng 52 câu đã kiểm: **Recall@5 = 0.556**. Bật dịch:
**0.889**. Chênh **9 câu trên 27** — gấp 9 lần khoảng cách hybrid/vector.

(Lượt không dịch chạy trên index dựng với `--embedding none` nên `index_build_id` khác; xếp
hạng lexical là BM25 trên cùng 42 record nên vẫn so sánh được.)

37/52 câu là tiếng Việt trên corpus tiếng Anh, nên kết quả dễ hiểu — nhưng nó nói rõ nhánh
dịch là thành phần không được tắt, và một lỗi ở đó tốn nhiều hơn bất kỳ tinh chỉnh xếp hạng
nào.

Phân tích theo ngôn ngữ (hybrid, ngưỡng 0.10) cho thấy tiếng Việt **không** phải nguồn lỗi:
trong nhóm đáng lẽ phải từ chối, tiếng Việt sai 8/16 (50%) còn tiếng Anh sai 5/7 (71%).

### Theo nhóm câu hỏi (Recall@5)

| Nhóm | n | lexical | vector | hybrid |
|---|---|---|---|---|
| `detail` | 18 | 0.944 | 0.944 | **1.000** |
| `multi_unit` | 2 | 1.000 | 1.000 | 1.000 |
| `no_diacritics` | 4 | 0.750 | **0.500** | 0.750 |
| `paraphrase` | 3 | 0.667 | **1.000** | 0.667 |

n từ 2–4 nên chỉ là chỉ dấu. Hai hướng đáng theo dõi khi có thêm câu hỏi: vector **kém** với
tiếng Việt không dấu, **tốt** với paraphrase. Cả hai khớp trực giác về embedding, nhưng chưa
đủ mẫu để khẳng định.

## Giới hạn phải nêu kèm mọi con số

1. **Bộ câu hỏi chỉ phủ 20/38 Step.** `REAL_WF_0002` và `REAL_WF_0003` không có câu hỏi nào;
   18 Step của chúng hiện chỉ đóng vai nhiễu. Recall/MRR ở đây là chỉ số của **2 trong 4
   workflow**, không phải của cả corpus.
2. **Mẫu số nhỏ**: 27 câu cho Recall/MRR, 21 cho nhóm từ chối, 31 cho wf_accuracy. Chênh 1
   câu = 3.7 điểm phần trăm.
3. **Ngưỡng 0.20 hiệu chỉnh trên chính 52 câu này.** Không có tập riêng để chọn tham số, nên
   con số sau hiệu chỉnh lạc quan hơn thực tế. Holdout còn nguyên, chưa động tới.
4. **Một nguồn, một cụm máy.** Ba video Haas về SMTC. Không suy rộng sang máy khác, hãng
   khác, hay môi trường DENSO.
5. **Đây là chỉ số retrieval, không phải chất lượng câu trả lời.** `citation_correctness` và
   `answer_groundedness` vẫn `null` cho tới khi có người điền verdict
   (`evaluation answers --verdict-template`).

## Chạy lại

```powershell
.\.venv\Scripts\python.exe -m retrieval.retrieval build --db out/retrieval/real_dev.sqlite --mode real --split dev --embedding gemini
.\.venv\Scripts\python.exe -m retrieval.evaluation run --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --mode real --split dev
```

Cần `GEMINI_API_KEY` trong `.env`. Lượt đo gốc tốn 44 call embedding + 35 call dịch, gặp 429
hai lần và tự retry. Kết quả được cache ở `out/eval/query_embeddings.jsonl` /
`query_translations.jsonl`, nên chạy lại hoặc quét ngưỡng khác **không tốn thêm call**.

## Việc tiếp theo

- [x] Soạn 14 câu cho `WF_0002`/`WF_0003` (Q055–Q068) để bộ câu hỏi phủ hết corpus;
      người kiểm `quyhienln` duyệt 2026-09-24 (14 `ok`).
- [ ] Quét lại ngưỡng cổng liên quan trên đủ 66 câu, vì nó phụ thuộc cỡ corpus.
- [ ] Chạy `evaluation answers` để có chỉ số tầng câu trả lời, nơi ngưỡng ≥0.90 thực sự áp.
- [ ] Người kiểm điền verdict để có `citation_correctness` / `answer_groundedness`.
