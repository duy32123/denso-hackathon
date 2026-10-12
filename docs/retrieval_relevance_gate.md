# Cổng liên quan theo claim — 2026-09-22

Đã đổi mặc định từ `legacy_corpus` sang `claim_coherence`, sau bản sửa alias SMTC.
Trên **52 câu real/dev đã được người kiểm**, đối chứng cùng index và cache cho cả ba
chiến lược: `false_retrieved` **10 → 0**, `missed` **0 → 0**. Hybrid Recall@5 giữ
nguyên **0.9259**. Đây là kết quả trên **dev dùng để chỉnh cổng**, không phải holdout,
không chứng minh độ đúng của câu trả lời hoặc citation.

## Nguyên nhân

Cổng cũ tính coverage IDF bằng cách gom từ có mặt ở bất kỳ Step đủ điều kiện nào,
kể cả metadata, scope và tiêu đề workflow lặp lại. Q046 hỏi đo spindle runout bằng
dial indicator: các từ `measure`, `spindle`, `indic` xuất hiện rời rạc trong những
Step khác nhau, vẫn cho coverage khoảng 0.4732 dù không có quy trình được hỏi.
Stem `indic` còn có thể đến từ động từ “indicate”, không phải dụng cụ đo.

Chiều ngược lại, Q067 hỏi giới hạn của RECOVER và nơi liên hệ hỗ trợ. Cách diễn đạt
khác nguồn khiến coverage cũ chỉ khoảng 0.1891 và bị từ chối, dù `REAL_WF_0003_ST_009`
có nội dung liên quan. Tăng ngưỡng toàn corpus không giải quyết được cả hai phía.

## Quy tắc mới

Code: [relevance.py](../retrieval/retrieval/relevance.py), policy trace `claim-coherence-1`.

1. Namespace, revision, source review và hard context filter vẫn chạy trước cổng.
   Chỉ đọc claim ID đã được giữ trong projection của Step; claim bị loại/pending
   trong snapshot không được góp từ để cứu truy vấn.
2. Tách từ context đã được hard filter kiểm khỏi phần nội dung cần tìm. Khi có
   nhiều workflow, bỏ từ chữ xuất hiện trong **hơn 75%** Step đủ điều kiện; không
   bỏ số/mã theo tần suất. Nếu toàn bộ từ còn lại đều là từ nền, dùng lại tập đó.
   Không áp dụng loại từ nền theo tần suất khi chỉ có một workflow.
3. Giữ từ chưa biết trong mẫu số. Alias tiếng Anh `slider` → `slide` chỉ dùng tại
   cổng; không sửa nội dung nguồn, token ranking, số hoặc mã.
4. Với `detail`, đếm từ cùng xuất hiện trong **tiêu đề Step + một claim**. Không
   gom qua nhiều claim/Step. Với `procedure`, được gom qua các Step thuộc **một
   workflow**, nhưng tách nhóm claim trả lời và nhóm cảnh báo conflict.
5. Đơn vị khớp tốt nhất cần ít nhất **2 từ nội dung** (1 nếu truy vấn chỉ còn 1 từ)
   và tỷ lệ khớp **≥ 0.20**. Không đạt thì trả `insufficient_evidence` trước embedding.

Giá trị ngưỡng vẫn là 0.20 nhưng **đại lượng đã đổi**: tỷ lệ số từ khớp cục bộ,
không còn coverage IDF của hợp toàn corpus. Chỉ so sánh ngưỡng khi ghi kèm policy.
`--relevance-policy legacy_corpus` giữ nguyên baseline cũ; `--min-term-coverage 0`
tắt cả điều kiện tỷ lệ lẫn số từ tối thiểu. Câu tiếng Việt trên corpus tiếng Anh
chạy không dịch vẫn `gate=skipped`; lỗi provider không bị đổi thành kết quả từ chối.

`trace.relevance` ghi policy, đơn vị xét, từ context/từ nền đã bỏ, từ khớp và các
`support_refs`. Các ref này chỉ là **tín hiệu khớp từ**, không chứng minh entailment
hay đầy đủ câu trả lời. `unseen_terms` của policy mới là từ không khớp ở đơn vị tốt
nhất, không nhất thiết vắng trong cả corpus. `corpus_term_coverage` giữ số đo cũ.
Ranking không đổi và có thể chọn Step/workflow khác đơn vị làm cổng mở.

## Đối chứng trên engine thật

Run: `out/eval/GATE_20260922T152053Z/report.json`, chi tiết từng câu ở `rows.jsonl`
cùng thư mục. Cùng index `IDX_SEARCH_b9c6c8a74f8b61713283ee0f5cb366d4d3d4bdc30ae1bddd0a54a0590c429f4d`,
4 workflow / 38 Step. Không reindex, không sửa KB hoặc gold, không đụng holdout.

### 52 câu đã được người kiểm

| Chỉ số | Cổng cũ | Cổng mới |
|---|---:|---:|
| Status accuracy — cả ba chiến lược, mẫu số 52 | 0.8077 | 1.0000 |
| `false_retrieved` — cả ba chiến lược | 10 | 0 |
| `missed` — cả ba chiến lược | 0 | 0 |
| Lexical Recall@5 — mẫu số 27 | 0.8889 | 0.8889 |
| Vector Recall@5 — mẫu số 27 | 0.8889 | 0.8889 |
| Hybrid Recall@5 — mẫu số 27 | 0.9259 | 0.9259 |
| Hybrid workflow accuracy — mẫu số 31 | 0.9355 | 0.9355 |

10 câu hết trả kết quả ngoài phạm vi: Q033, Q040, Q044, Q046, Q047, Q048, Q049,
Q051, Q052, Q053. Giữ được cả 31 câu cần retrieval; 21 câu còn lại ra đúng trạng
thái kỳ vọng. Không suy ra toàn bộ ranking hoặc tầng trả lời đã đúng từ status 100%.

### Nhóm mở rộng: chỉ dùng chẩn đoán

File có 66 câu, gồm 52 `reviewed` và 14 `draft`. Script **không gọi API** và chỉ so
sánh giao các câu hoàn tất ở cả hai policy cho từng chiến lược:

| Chiến lược | Câu so sánh | Thiếu cache, loại ở cả hai phía | Recall@5 cũ → mới |
|---|---:|---|---:|
| Lexical | 65 | Q059: bản dịch | 0.8889 → 0.9167 |
| Vector | 64 | Q059: bản dịch; Q067: embedding | 0.9143 → 0.9143 |
| Hybrid | 64 | Q059: bản dịch; Q067: embedding | 0.9429 → 0.9429 |

Q067 mới được kiểm thực tế bằng **lexical**: hết bị cổng từ chối, chọn WF_0003 và
ST_009 nằm ở hạng 4 trong top-5. Chưa đo được Q067 vector/hybrid; không dùng cache
giả hoặc bản dịch tự viết thay provider. Q059 có regression test dùng translator
stub, nhưng không tính đó là một lượt benchmark Gemini. Không gọi đây là phép đo
đầy đủ 66 câu; không so trực tiếp số hybrid 64 câu với báo cáo cũ có mẫu số khác.

SHA-256 file câu hỏi giữ nguyên:
`304735bac82b2227dd81c635bf911a9ee4fc1a0193d3c326482edca95c64d95a`.
Lượt đối chứng ghi **0 embedding calls, 0 translation calls**. Báo cáo có cấu hình,
hash mã nguồn tại lúc chạy, danh sách cache miss và nhóm `reviewed_only` riêng.

## Kiểm thử và tái lập

```powershell
# Chỉ dùng cache hiện có; thiếu cache được ghi thành skip, không gửi dữ liệu ra ngoài.
.\.venv\Scripts\python.exe -m scripts.compare_relevance_gates

# Kiểm thử cổng, engine và evaluator, không cần API thật.
.\.venv\Scripts\python.exe -m pytest tests/unit/test_relevance.py tests/unit/test_query.py tests/unit/test_retrieval.py tests/unit/test_evaluation.py tests/unit/test_evaluation_answers.py
```

Lượt kiểm thử tập trung: **136 passed**. Toàn bộ suite: **785 passed, 3 skipped**,
2 cảnh báo deprecation từ dependency. Test bổ sung kiểm tra không gom từ rời rạc,
không dùng metadata/pending claim làm bằng chứng, biên workflow/conflict, mã alarm,
truy vấn ngắn, alias slider/slide và từ chối trước khi gọi embedding ở cả ba strategy.

Lượt kiểm lại sau khi thêm năm workflow (2026-10-12): [đo lại sau khi mở rộng](retrieval_dev_expansion_check.md).

Đây vẫn là heuristic phụ thuộc corpus. Cần kiểm lại khi thêm nguồn và đánh giá
riêng trên tập độc lập sau khi khóa pipeline. Việc D2-A review 14 nhãn
draft (Q055–Q068) đã xong ngày 2026-09-24 (`quyhienln`, 14 `ok`); số đo trong trang này vẫn
là trên tập trước lượt kiểm đó. Tầng câu trả lời đã có lượt đo với human verdict (2026-09-24), kèm các
giới hạn phải nêu theo: xem [kết quả retrieval real/dev](retrieval_eval_real_dev.md).
