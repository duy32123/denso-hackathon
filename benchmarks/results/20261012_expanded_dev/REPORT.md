**Review nhãn mở rộng chờ quyết định:** lượt đo giữ nguyên gold hiện có. Không đánh dấu đề xuất AI thành human-reviewed; không coi status match là chất lượng đáp án đã được người chấm. Kỳ vọng retrieval Q041/Q049 còn cần quyết định riêng; expected answer của chúng hiện là insufficient_evidence.

# KnowFlow: benchmark corpus mở rộng sau PR #53

Commit `d47308e959b1ced6841689cb5d6dacbfb1b5b42f`; 81 câu, 243/243 terminal rows.

Corpus real/dev: 9 workflow active, 67 Step, 303 claim, 15 relations; revision và review flags trong audit.json. Model trả lời/dịch `gemini-3.5-flash-lite`, embedding `gemini-embedding-001` (768 chiều). Không mở holdout, không cộng synthetic.

Gold có 56 câu expected answered; Recall/MRR dùng 52 câu answered/detail có gold Step, không chấm procedure bằng top-5. Status dùng tất cả 81 câu, gồm lỗi API.

## Kết quả theo cohort

| Cohort | Arm | Đúng status | Recall@5 / MRR@5 (n) | API lỗi | False answer / abstention |
|---|---|---:|---|---:|---:|
| all_81 | A_knowflow | 67/81 | 96.15% / 86.60% (52) | 2 | 0 / 12 |
| all_81 | B_transcript_rag | 67/81 | null / null (0) | 2 | 0 / 12 |
| all_81 | C_no_graph | 67/81 | 96.15% / 86.60% (52) | 0 | 0 / 14 |
| old_66 | A_knowflow | 53/66 | 94.59% / 83.87% (37) | 2 | 0 / 11 |
| old_66 | B_transcript_rag | 53/66 | null / null (0) | 1 | 0 / 12 |
| old_66 | C_no_graph | 53/66 | 94.59% / 83.87% (37) | 0 | 0 / 13 |
| new_15 | A_knowflow | 14/15 | 100.00% / 93.33% (15) | 0 | 0 / 1 |
| new_15 | B_transcript_rag | 14/15 | null / null (0) | 1 | 0 / 0 |
| new_15 | C_no_graph | 14/15 | 100.00% / 93.33% (15) | 0 | 0 / 1 |

## So sánh và lỗi cần xử lý

BM25 không dịch đã chạy lại trên chính corpus mở rộng: Recall@5 68.27%, MRR@5 61.38%, n=52. A có dịch/embedding/hybrid: 96.15% / 86.60%, n=52. Đây là thay đổi nhiều thành phần, không cô lập graph. [Đầu ra BM25 mới](offline_bm25_report.json); không sao chép mốc 58.1% từ corpus cũ.

So sánh mô tả với run 20261011 trên cùng 66 ID, giữ nguyên nhãn status. Corpus, bản dịch, pairing A/C và điều kiện API đã đổi, nên không quy chênh lệch cho riêng bản sửa.

| Arm | Status đúng run cũ → mới, n=66 | Recall@5 cũ → mới, n=37 | MRR@5 cũ → mới, n=37 |
|---|---:|---|---|
| A_knowflow | 49 → 53 | 94.59% → 94.59% | 86.58% → 83.87% |
| B_transcript_rag | 56 → 53 | null → null | null → null |
| C_no_graph | 48 → 53 | 94.59% → 94.59% | 87.93% → 83.87% |

Chi tiết từng câu cải thiện/hồi quy: [historical_comparison.csv](historical_comparison.csv). Chênh lệch ròng status đúng: {'A_knowflow': 4, 'B_transcript_rag': -3, 'C_no_graph': 5}. So sánh retrieval/MRR trong bảng; không chỉ chọn các câu cải thiện để báo.

Status đúng A/B/C: 67 / 67 / 67, mỗi arm n=81. Đây chưa phải độ đúng nghĩa của đáp án. A/C có 81 cặp cùng ứng viên, 0 hash mismatch; A thắng status 3 câu, C thắng 3. Có 49 câu đưa relations vào prompt. Trong 32 câu không có relations, đáp án đổi 8 câu; status đổi ở ['HAAS_DEV_Q029']. Những cặp không có cạnh giúp quan sát biến thiên generation ngoài can thiệp graph.

Điều tra các ca của riêng run này (AI, chưa có người chấm nghĩa):

| Ca | Quan sát và giới hạn |
|---|---|
| Q069 | A/B/C answered; A/C gold Step ở hạng 3. Cổng exact alarm lookup đã qua với claim đúng mã 626. Chấm nghĩa vẫn chờ người. |
| Q015 / Q031 | A/C chọn B0 r2 cho pocket slider. Q031 giữ insufficient_evidence cho câu hỏi loại mỡ; Q015 vẫn false abstention ở draft. Chọn đúng workflow chưa bảo đảm trả lời được. |
| Q012 / Q056 | A/C bị relevance gate từ chối: Q012 bản dịch dùng return, chỉ carousel khớp trong một claim; Q056 nhiều từ phụ/biến thể làm coverage=.1818 dưới .20. Không thay ngưỡng trong run. |
| Q083 | A/C draft dùng 21; quote viết twenty one. Guard số thấy 1032 nhưng không thấy 21, dừng trước verifier. B dùng chữ twenty one và answered. Ký hiệu tap 1032 cũng cần người đối chiếu nguồn. |
| Q041 / Q049 | A/C retrieval=retrieved, answer=insufficient_evidence. Gold retrieval hiện vẫn insufficient_evidence; đề xuất sửa đang chờ quyết định người kiểm. Hai câu không nằm trong mẫu số Recall/MRR. |
| Q039 / Q050 | Context SMTC được giữ; khác các câu Q049/Q041 context trống. Không bỏ filter để sửa nhãn theo prediction. |
| Q064 | A/C có keyframe annotation, B chỉ có transcript. Khác biệt phương thức dữ liệu cần được tách khỏi kết luận về graph. |
| Q005 / Q021 | Cần đối chiếu mức độ khẳng định nguyên nhân/điều kiện và phạm vi screw/screws; ID citation hợp lệ chưa chứng minh toàn bộ nghĩa. |

Nhận xét các ca trên có hash trong [ai_case_notes.jsonl](ai_case_notes.jsonl), không cộng vào human verdict.

Xem [human_review.csv](human_review.csv) và [hướng dẫn chấm](review_instructions.md).

## Phương pháp và nhãn

66 câu cũ, 15 câu mới (Q069–Q083) được báo riêng. 40 câu Vietnamese/hard draft tách file, không chạy/cộng vào kết quả này. Lượt này giữ nguyên 81 nhãn hiện có; 20 nhãn phủ định chưa có quyết định review trên corpus mở rộng để áp dụng. Người dùng báo đã kiểm nguồn và cung cấp GitHub duy32123; phiếu quyết định vẫn trống. Không có label_changes hoặc human approval mới. Xác nhận chạy được lưu riêng, không biến thành quyết định nhãn. Expected retrieval và expected answer là hai phép kiểm riêng; Recall/MRR chỉ chấm answered/detail có gold Step, không chấm raw chunks của B.

A/B dùng cùng nguồn, model, output/context budget, ngôn ngữ và chính sách nguồn/citation. B chunk corrected captions/Source.raw_text, không nhận Step/claim/relations/gold. A có annotation keyframe, metadata bước và hard filters; khác biệt này không thể quy hết cho graph.

A/C chạy QAService qua API; chỉ một retrieval thật mỗi câu được lưu với hash. C tái sử dụng đúng bản dịch/embedding/ứng viên trước khi bỏ relations/related_steps/related_claims. Không chạy lại retrieval để chọn kết quả đẹp hơn. Nếu retrieval lỗi, cả cặp giữ lỗi đó. Generation/verifier chạy độc lập, temperature=0 không bảo đảm tất định. Product chưa đưa related_claims vào generation candidates; phạm vi graph intervention hữu ích ở prompt là relations. C giữ nguyên claim đã chuẩn hóa kể cả nội dung nói về quan hệ: phép đo cô lập cạnh tường minh/mở rộng, không bỏ toàn bộ tác động của tiền xử lý tri thức.

A/C: {"paired_questions": 81, "left_only_status_correct": ["HAAS_DEV_Q005", "HAAS_DEV_Q026", "HAAS_DEV_Q029"], "right_only_status_correct": ["HAAS_DEV_Q028", "HAAS_DEV_Q062", "HAAS_DEV_Q066"], "answer_changed": ["HAAS_DEV_Q002", "HAAS_DEV_Q003", "HAAS_DEV_Q004", "HAAS_DEV_Q005", "HAAS_DEV_Q006", "HAAS_DEV_Q007", "HAAS_DEV_Q011", "HAAS_DEV_Q013", "HAAS_DEV_Q016", "HAAS_DEV_Q017", "HAAS_DEV_Q022", "HAAS_DEV_Q024", "HAAS_DEV_Q026", "HAAS_DEV_Q027", "HAAS_DEV_Q028", "HAAS_DEV_Q029", "HAAS_DEV_Q055", "HAAS_DEV_Q057", "HAAS_DEV_Q058", "HAAS_DEV_Q059", "HAAS_DEV_Q062", "HAAS_DEV_Q063", "HAAS_DEV_Q064", "HAAS_DEV_Q066", "HAAS_DEV_Q072", "HAAS_DEV_Q073", "HAAS_DEV_Q074", "HAAS_DEV_Q077", "HAAS_DEV_Q081"], "candidate_content_changed": [], "same_candidate_pairs": 81, "same_candidate_left_only_status_correct": ["HAAS_DEV_Q005", "HAAS_DEV_Q026", "HAAS_DEV_Q029"], "same_candidate_right_only_status_correct": ["HAAS_DEV_Q028", "HAAS_DEV_Q062", "HAAS_DEV_Q066"], "graph_exposed_questions": ["HAAS_DEV_Q004", "HAAS_DEV_Q005", "HAAS_DEV_Q007", "HAAS_DEV_Q008", "HAAS_DEV_Q009", "HAAS_DEV_Q010", "HAAS_DEV_Q016", "HAAS_DEV_Q022", "HAAS_DEV_Q024", "HAAS_DEV_Q025", "HAAS_DEV_Q026", "HAAS_DEV_Q028", "HAAS_DEV_Q030", "HAAS_DEV_Q040", "HAAS_DEV_Q041", "HAAS_DEV_Q042", "HAAS_DEV_Q044", "HAAS_DEV_Q048", "HAAS_DEV_Q049", "HAAS_DEV_Q052", "HAAS_DEV_Q053", "HAAS_DEV_Q055", "HAAS_DEV_Q057", "HAAS_DEV_Q058", "HAAS_DEV_Q059", "HAAS_DEV_Q060", "HAAS_DEV_Q061", "HAAS_DEV_Q062", "HAAS_DEV_Q063", "HAAS_DEV_Q064", "HAAS_DEV_Q065", "HAAS_DEV_Q066", "HAAS_DEV_Q067", "HAAS_DEV_Q068", "HAAS_DEV_Q069", "HAAS_DEV_Q070", "HAAS_DEV_Q071", "HAAS_DEV_Q072", "HAAS_DEV_Q073", "HAAS_DEV_Q074", "HAAS_DEV_Q075", "HAAS_DEV_Q076", "HAAS_DEV_Q077", "HAAS_DEV_Q078", "HAAS_DEV_Q079", "HAAS_DEV_Q080", "HAAS_DEV_Q081", "HAAS_DEV_Q082", "HAAS_DEV_Q083"], "pre_ablation_mismatches": []}

A/B: {"paired_questions": 81, "left_only_status_correct": ["HAAS_DEV_Q001", "HAAS_DEV_Q004", "HAAS_DEV_Q011", "HAAS_DEV_Q016", "HAAS_DEV_Q021", "HAAS_DEV_Q064", "HAAS_DEV_Q074"], "right_only_status_correct": ["HAAS_DEV_Q010", "HAAS_DEV_Q028", "HAAS_DEV_Q056", "HAAS_DEV_Q062", "HAAS_DEV_Q066", "HAAS_DEV_Q068", "HAAS_DEV_Q083"], "answer_changed": ["HAAS_DEV_Q001", "HAAS_DEV_Q002", "HAAS_DEV_Q003", "HAAS_DEV_Q004", "HAAS_DEV_Q005", "HAAS_DEV_Q006", "HAAS_DEV_Q007", "HAAS_DEV_Q008", "HAAS_DEV_Q009", "HAAS_DEV_Q010", "HAAS_DEV_Q011", "HAAS_DEV_Q012", "HAAS_DEV_Q013", "HAAS_DEV_Q014", "HAAS_DEV_Q015", "HAAS_DEV_Q016", "HAAS_DEV_Q017", "HAAS_DEV_Q018", "HAAS_DEV_Q019", "HAAS_DEV_Q020", "HAAS_DEV_Q021", "HAAS_DEV_Q022", "HAAS_DEV_Q023", "HAAS_DEV_Q024", "HAAS_DEV_Q025", "HAAS_DEV_Q026", "HAAS_DEV_Q027", "HAAS_DEV_Q028", "HAAS_DEV_Q029", "HAAS_DEV_Q030", "HAAS_DEV_Q031", "HAAS_DEV_Q032", "HAAS_DEV_Q033", "HAAS_DEV_Q034", "HAAS_DEV_Q035", "HAAS_DEV_Q037", "HAAS_DEV_Q039", "HAAS_DEV_Q040", "HAAS_DEV_Q041", "HAAS_DEV_Q042", "HAAS_DEV_Q043", "HAAS_DEV_Q044", "HAAS_DEV_Q045", "HAAS_DEV_Q046", "HAAS_DEV_Q047", "HAAS_DEV_Q048", "HAAS_DEV_Q049", "HAAS_DEV_Q050", "HAAS_DEV_Q051", "HAAS_DEV_Q052", "HAAS_DEV_Q053", "HAAS_DEV_Q054", "HAAS_DEV_Q055", "HAAS_DEV_Q056", "HAAS_DEV_Q057", "HAAS_DEV_Q058", "HAAS_DEV_Q059", "HAAS_DEV_Q060", "HAAS_DEV_Q061", "HAAS_DEV_Q062", "HAAS_DEV_Q063", "HAAS_DEV_Q064", "HAAS_DEV_Q065", "HAAS_DEV_Q066", "HAAS_DEV_Q067", "HAAS_DEV_Q068", "HAAS_DEV_Q069", "HAAS_DEV_Q070", "HAAS_DEV_Q071", "HAAS_DEV_Q072", "HAAS_DEV_Q073", "HAAS_DEV_Q074", "HAAS_DEV_Q075", "HAAS_DEV_Q076", "HAAS_DEV_Q077", "HAAS_DEV_Q078", "HAAS_DEV_Q079", "HAAS_DEV_Q080", "HAAS_DEV_Q081", "HAAS_DEV_Q082", "HAAS_DEV_Q083"], "candidate_content_changed": null, "same_candidate_pairs": null, "same_candidate_left_only_status_correct": null, "same_candidate_right_only_status_correct": null, "graph_exposed_questions": ["HAAS_DEV_Q004", "HAAS_DEV_Q005", "HAAS_DEV_Q007", "HAAS_DEV_Q008", "HAAS_DEV_Q009", "HAAS_DEV_Q010", "HAAS_DEV_Q016", "HAAS_DEV_Q022", "HAAS_DEV_Q024", "HAAS_DEV_Q025", "HAAS_DEV_Q026", "HAAS_DEV_Q028", "HAAS_DEV_Q030", "HAAS_DEV_Q040", "HAAS_DEV_Q041", "HAAS_DEV_Q042", "HAAS_DEV_Q044", "HAAS_DEV_Q048", "HAAS_DEV_Q049", "HAAS_DEV_Q052", "HAAS_DEV_Q053", "HAAS_DEV_Q055", "HAAS_DEV_Q057", "HAAS_DEV_Q058", "HAAS_DEV_Q059", "HAAS_DEV_Q060", "HAAS_DEV_Q061", "HAAS_DEV_Q062", "HAAS_DEV_Q063", "HAAS_DEV_Q064", "HAAS_DEV_Q065", "HAAS_DEV_Q066", "HAAS_DEV_Q067", "HAAS_DEV_Q068", "HAAS_DEV_Q069", "HAAS_DEV_Q070", "HAAS_DEV_Q071", "HAAS_DEV_Q072", "HAAS_DEV_Q073", "HAAS_DEV_Q074", "HAAS_DEV_Q075", "HAAS_DEV_Q076", "HAAS_DEV_Q077", "HAAS_DEV_Q078", "HAAS_DEV_Q079", "HAAS_DEV_Q080", "HAAS_DEV_Q081", "HAAS_DEV_Q082", "HAAS_DEV_Q083"]}

## Latency và chi phí

latency_ms là thời gian HTTP local qua FastAPI TestClient và QAService thật, bao gồm API Gemini/retry; không gồm browser/đường truyền tới hosting. Arm A/C replay trừ thời gian retrieval gốc khỏi timeout endpoint để giữ tổng deadline 90s như arm đầu/B; effective_api_timeout_seconds lưu từng câu. HTTP arm replay ngắn hơn về retrieval; không dùng chênh này để khẳng định graph tăng/giảm latency. latency_ms_standalone_component_sum cộng lại thời gian retrieval gốc cho arm replay: đây là tổng thành phần tái dựng, không phải latency toàn luồng quan sát trong deployment. p50/p95 của cả hai được báo riêng trong summary.csv, giữ lỗi/timeouts.

Chi phí shared retrieval ghi một lần dưới AC_shared_retrieval, tách khỏi generation/verifier của A/C. standalone_reference_cost cộng shared retrieval cho mỗi arm chỉ để tham chiếu một tác vụ độc lập, không cộng hai lần vào chi phí thí nghiệm. Call mới có journal started trước khi gọi provider; started chưa có completion được giữ là InterruptedUnfinishedCall, token/cost/elapsed=null, không coi là miễn phí. Build index và smoke tách riêng. Token/giá/chi phí chưa biết là null; hóa đơn thực, server, extraction/preprocessing và công chuyên gia chưa đo. Giá standard là quy đổi từ usage, không phải hóa đơn.

Tổng known subtotal thí nghiệm: $0.976087; tổng đầy đủ null.

Giá tra 2026-10-12: [Gemini official pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite). Exact embedding-001 rate chưa xác minh, giữ null.

| Arm | HTTP p50 / p95 (s) | Tổng thành phần p50 / p95 (s) | Known QA USD, tham chiếu độc lập | Known USD / câu | Phí QA đầy đủ |
|---|---:|---:|---:|---:|---|
| A_knowflow | 3.974 / 35.976 | 5.045 / 37.614 | 0.397676 | 0.004910 | null |
| B_transcript_rag | 3.365 / 44.241 | 3.365 / 44.241 | 0.131014 | 0.001617 | null |
| C_no_graph | 4.186 / 30.014 | 4.890 / 34.502 | 0.412658 | 0.005095 | null |

Phí trong bảng là subtotal đã biết; không phải tổng phí hoặc hóa đơn. Cột tham chiếu độc lập của A/C tính một retrieval cho mỗi câu; không cộng hai cột này để tính phí thí nghiệm.

| Hạng mục | Calls | Token tổng | Known USD | Phí đầy đủ USD |
|---|---:|---:|---:|---|
| full: embedding_index | 0 | 0 | 0.000000 | 0 |
| full: embedding_query | 145 | null | null | null |
| full: translation | 101 | null | 0.008588 | null |
| full: answer_generation | 225 | null | 0.795072 | null |
| full: answer_verification | 146 | null | 0.133388 | null |
| index: A_knowflow | 56 | null | null | null |
| index: B_transcript_rag | 13 | null | null | null |
| smoke (riêng) | 31 | null | 0.039036 | null |
| availability probe (riêng) | 2 | null | 0.000004 | null |

Full run có 617 logical provider calls, 617 HTTP attempts quan sát; HTTP status {'200': 587, '429': 30}; 30 retries quan sát. Transport log không quan sát được mọi lỗi mạng nên số attempts không biết giữ null. Lỗi provider chưa biết usage không được tính là miễn phí.

Build index lần đầu batch 32 đã thất bại vì 429; journal và cấu hình trước điều chỉnh được giữ nguyên. Trước smoke/full, chỉ đổi batching index thành 4 và pacing 1 giây, đóng băng lại tại commit trên. Không đổi nội dung chunk, embedding model/dimensions, gold hay tham số retrieval. Xem freeze_amendments.json và preparation_status_before_index_pacing.json; thời gian phần chuẩn bị thất bại không đo đủ, giữ null.

## Lỗi, ngôn ngữ và hồi quy

### A_knowflow

- HTTP 200: 79/81; answered khi gold answered: 42/56 (không phải độ đúng nghĩa).
- Citation hợp lệ bằng code: 65/65; độ hỗ trợ nghĩa vẫn null.
- API errors: [{"question_id": "HAAS_DEV_Q062", "http_status": 504, "error_class": null, "latency_ms": 87761.025}, {"question_id": "HAAS_DEV_Q059", "http_status": 504, "error_class": null, "latency_ms": 88394.187}]
- False answer: []; false abstention: ['HAAS_DEV_Q012', 'HAAS_DEV_Q056', 'HAAS_DEV_Q068', 'HAAS_DEV_Q025', 'HAAS_DEV_Q083', 'HAAS_DEV_Q028', 'HAAS_DEV_Q066', 'HAAS_DEV_Q060', 'HAAS_DEV_Q018', 'HAAS_DEV_Q015', 'HAAS_DEV_Q010', 'HAAS_DEV_Q009'].
- vi: status 37/50; lỗi API 2.
- en: status 30/31; lỗi API 0.

### B_transcript_rag

- HTTP 200: 79/81; answered khi gold answered: 42/56 (không phải độ đúng nghĩa).
- Citation hợp lệ bằng code: 90/90; độ hỗ trợ nghĩa vẫn null.
- API errors: [{"question_id": "HAAS_DEV_Q074", "http_status": 504, "error_class": null, "latency_ms": 90013.405}, {"question_id": "HAAS_DEV_Q001", "http_status": 504, "error_class": null, "latency_ms": 90006.731}]
- False answer: []; false abstention: ['HAAS_DEV_Q012', 'HAAS_DEV_Q016', 'HAAS_DEV_Q004', 'HAAS_DEV_Q025', 'HAAS_DEV_Q011', 'HAAS_DEV_Q064', 'HAAS_DEV_Q021', 'HAAS_DEV_Q060', 'HAAS_DEV_Q018', 'HAAS_DEV_Q059', 'HAAS_DEV_Q015', 'HAAS_DEV_Q009'].
- vi: status 38/50; lỗi API 1.
- en: status 29/31; lỗi API 1.

### C_no_graph

- HTTP 200: 81/81; answered khi gold answered: 42/56 (không phải độ đúng nghĩa).
- Citation hợp lệ bằng code: 66/66; độ hỗ trợ nghĩa vẫn null.
- API errors: []
- False answer: []; false abstention: ['HAAS_DEV_Q012', 'HAAS_DEV_Q056', 'HAAS_DEV_Q068', 'HAAS_DEV_Q025', 'HAAS_DEV_Q083', 'HAAS_DEV_Q060', 'HAAS_DEV_Q026', 'HAAS_DEV_Q005', 'HAAS_DEV_Q018', 'HAAS_DEV_Q059', 'HAAS_DEV_Q015', 'HAAS_DEV_Q010', 'HAAS_DEV_Q029', 'HAAS_DEV_Q009'].
- vi: status 38/50; lỗi API 0.
- en: status 29/31; lỗi API 0.

## Kết luận chưa chứng minh

Code chỉ kiểm ID, revision, link, phạm vi và số trong citation. answers_question/conditions_correct/source_supported/citation correctness đang null, 0 người chấm; không dùng model verifier tự xác nhận. Một lượt A/C với ứng viên giống nhau vẫn chịu biến thiên sinh câu trả lời. Không khẳng định graph vượt RAG, không đổi latency thành thời gian người tiết kiệm, không khẳng định giảm 30% hoặc ROI DENSO. Lượt cũ khác corpus/prompt/pairing, không phải đối chứng causal cho bản sửa này.

## Tái lập

```powershell
$benchmarkRunDir = 'benchmarks/results/20261012_expanded_repeat_v1'  # tên mới, không ghi đè run đã đo
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow prepare --config benchmarks/knowflow_expanded_dev/config_existing_labels.json --run-dir $benchmarkRunDir
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow smoke --config benchmarks/knowflow_expanded_dev/config_existing_labels.json --run-dir $benchmarkRunDir
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow run --config benchmarks/knowflow_expanded_dev/config_existing_labels.json --run-dir $benchmarkRunDir
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow report --config benchmarks/knowflow_expanded_dev/config_existing_labels.json --run-dir $benchmarkRunDir
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow.expanded_analysis --run-dir $benchmarkRunDir
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow.verify_artifacts --run-dir $benchmarkRunDir
```

Config SHA 689a612491ec9682303d178c18584769f6ccc54627b06a33a6bc7ef15adc6be5; questions SHA 59af8902bad10c266e5d6718963cd5bd5d70d7c62d1ffeef6b8b703382b945a4; corpus SHA 6b8d5b79c332e70bd20ea05480a3f5a825f72234ef1ee692fda311034ac5228e. Dependency versions và active revisions trong audit.json. Lượt cũ giữ nguyên.
