# KnowFlow real/dev benchmark

## Phạm vi

Product commit `dfde6f43704b532053c74e09701d1e978d5d12f9`; nhánh benchmark riêng, chưa push. Questions=66; languages={'vi': 50, 'en': 16}; expected_status={'answered': 41, 'insufficient_evidence': 24, 'needs_clarification': 1}; reviewed={'reviewed': 66}.

A: QAService + API thật, hybrid + dịch + embedding + draft/verify. B: raw transcript/document RAG. C: cùng index/nội dung với A, neighbor_depth=0 và bỏ relations trong kết quả retrieval.

Benchmark dựng DB riêng với embedding thật, không sửa database demo/cấu hình/logic sản phẩm. Nếu có existing_serving_state.json, đó là bản đối chiếu chỉ đọc cấu hình hiện hành. Các số mô tả cấu hình benchmark đã khóa, không chứng minh default deployment hiện đã bật đầy đủ AI.

## Kết quả bằng code

| Arm | Hoàn tất | Đúng status / 66 | Recall@5 (n) | MRR@5 | Trả lời khi thiếu nguồn | Từ chối oan | Citation hợp lệ | p50 / p95 (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_knowflow | 65/66 | 49/66 | 0.9459 (37) | 0.8658 | 1 | 15 | 42/42 | 3.83 / 31.86 |
| B_transcript_rag | 64/66 | 56/66 | null — thiếu raw-chunk gold | null | 0 | 8 | 64/64 | 3.36 / 39.60 |
| C_no_graph | 63/66 | 48/66 | 0.9459 (37) | 0.8793 | 1 | 14 | 41/41 | 4.14 / 84.24 |

## Kết luận từ lượt đo

- Retrieval A: 94.59%, n=37; BM25 không dịch chạy mới: 58.11%, n=37; chênh khoảng 36.4845945945946 điểm phần trăm. Đây là đối chiếu cấu hình hybrid + embedding + dịch với lexical không dịch; không cô lập riêng embedding hoặc graph.
- Status A 49/66 (74.24%), B 56/66 (84.85%). Cặp A đúng/B sai: 3; B đúng/A sai: 10. Từ chối oan A/B: 15/8; lỗi API A/B: 1/2. Không đổi gold hoặc chọn lại response để đảo kết luận.
- A/C Recall@5: 94.59%/94.59%; MRR: 86.58%/87.93%. Status: 49/48. 54 cặp cùng nội dung ứng viên có số thắng status 3–3; 12 cặp khác ứng viên. Một lượt live có biến thiên preprocessing/model chưa chứng minh đóng góp nhân quả của cạnh graph.
- Trả lời khi gold yêu cầu từ chối A/B/C: 1/0/1; IDs lần lượt: ['HAAS_DEV_Q031'], [], ['HAAS_DEV_Q031']. Citation code hợp lệ không ngăn lỗi về nghĩa. Không trình bày thành zero hallucination hoặc độ đúng nghĩa 100%.
- Phần phí standard xác định được A/B/C: $0.231593/$0.107022/$0.254449. Tổng đầy đủ, trung bình đầy đủ, hóa đơn thực và chi phí expert đều null/chưa đo: chưa chứng minh tiết kiệm tổng chi phí hoặc ROI.
- Cần người chấm phiếu 198 dòng để kết luận answers_question, điều kiện và hỗ trợ về nghĩa. Chưa chứng minh hiệu quả tại DENSO, tiết kiệm 30% thời gian người dùng, hoặc ưu thế graph so với RAG.

Status match là đối chiếu nhãn trạng thái đã review; không phải điểm đúng nghĩa của đáp án. Recall/MRR chỉ dùng 37 câu answered/detail; lỗi API giữ trong mẫu số và tính recall=0 nếu retrieval chưa hoàn tất.

Latency đo từ POST /v1/ask qua FastAPI TestClient đến HTTP response, gồm backoff và deadline 90s; không gồm mạng Internet của BTC. Các tác vụ timeout vẫn được drain để không trộn telemetry; thời gian drain tách riêng. Lượt bị ngắt không có HTTP response/latency đầy đủ: giữ null, báo riêng ngoài mẫu latency các task kết thúc.

Recall là chỉ số thành phần retrieval, tách khỏi thành công HTTP/đáp án. Nếu retrieval đã hoàn tất nhưng generation timeout thì vẫn ghi recall thành phần và status=error. Không coi kết quả background sau deadline là đáp án người dùng đã nhận.

## Chi phí

Đơn giá standard `gemini-3.5-flash-lite`: $0.30/M input, $2.50/M output gồm thinking; nguồn https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite, tra 2026-10-11. Usage metadata là token thực provider báo; phí dưới đây là quy đổi list-price, không phải hóa đơn. Billing tier/credits và số tiền đã trừ: null.

Embedding-001 không trả token trong metadata ở preflight; bảng giá live hiện không có chính xác model này. Giá/token embedding chưa biết giữ null, không dùng giá Embedding 2 hoặc ước lượng ký tự. Tổng đầy đủ và trung bình đầy đủ giữ null khi có khoản chưa đo được.

| Arm | Embedding query | Dịch | Sinh | Kiểm | Subtotal đã biết (USD) | Tổng đầy đủ |
|---|---:|---:|---:|---:|---:|---:|
| A_knowflow | null | null | null | null | $0.231593 | null |
| B_transcript_rag | null | null | null | null | $0.107022 | null |
| C_no_graph | null | null | null | null | $0.254449 | null |

Xây index ban đầu và smoke nằm riêng trong summary.json; C dùng lại index A, không có lượt build độc lập. Phí các call của lượt interrupted cũng được cộng, không chỉ các dòng đáp án kết thúc. Chưa tính preprocessing/extraction, nhân công review/chuyên gia, lưu trữ, máy chủ, mạng và thuế.

## Công bằng và giới hạn

- A/B cùng 5 Source real/dev, model trả lời/dịch/embedding, ngôn ngữ, max output 12000, common payload guard 1MB, temperature 0 và yêu cầu source-only/citation/numbers/semantic verifier. Context không bị cắt để làm đẹp kết quả; chi phí đo cả metadata/prompt overhead.
- A dùng claim và step đã được người kiểm nguồn, workflow routing, identity/relevance gates; B dùng corrected captions và Source.raw_text, chunk 180 từ overlap 30, raw corpus term coverage. B không nhận nhãn bước, claim, relations hoặc gold trong index/prompt. Procedure B chọn một source bằng raw chunk score. Đây là khác biệt preprocessing và routing; A/B không cô lập riêng graph.
- A/C có cả observation_note của keyframe đã kiểm và kiểm độ đầy đủ/thứ tự procedure bằng step metadata. B là baseline văn bản, không có annotation hình ảnh hoặc step metadata; completion/order chỉ được model kiểm trên raw chunks. Không quy những khác biệt này cho cạnh đồ thị.
- Generation A/C đọc observation_note đã gán, không chạy model thị giác trực tiếp trên keyframe ở thời điểm hỏi. Code chỉ kiểm asset mở/giải mã được và ID/link hợp lệ. 134 claim active source_checked, toàn bộ technical_review=not_requested: chưa có xác nhận chuyên gia.
- Adapter embedding/dịch thật được giữ client giữa các câu như evaluator, không cache response; model draft/verify tạo client theo QAService. Default production retrieve tự tạo client embedding/dịch mỗi request. Latency benchmark với client giữ kết nối không chứng minh latency cold deployment; tất cả arm dùng cùng chính sách benchmark này.
- A/C giữ cùng nội dung index kể cả câu chữ relation claim trong text. C chỉ bỏ quan hệ có cấu trúc và mở rộng cạnh ở runtime; không sửa product hoặc corpus. Independent live translation/model calls có thể dao động dù temperature=0; xem paired_A_C và candidate_content_changed.
- Product hiện không đưa related_claims vào candidates của prompt generation; neighbor expansion vẫn xuất hiện ở trace/UI. Vì vậy chưa có cơ sở quy lợi ích đáp án cho mở rộng cạnh.
- Bộ dev đã được dùng để phát triển pipeline trước benchmark. Một lượt chạy, corpus nhỏ, không phải holdout hoặc triển khai DENSO. Không quét tham số, không mở holdout, không cộng synthetic.
- human_review.csv đang chờ người chấm: answers_question, conditions_correct, source_supported, citation_correctness đều null. Không chuyển latency thành thời gian lao động tiết kiệm/ROI.

## Lỗi và khác biệt ngôn ngữ

### A_knowflow

- vi: đúng status 35/50; false_answer ['HAAS_DEV_Q031']; false_abstention ['HAAS_DEV_Q028', 'HAAS_DEV_Q068', 'HAAS_DEV_Q058', 'HAAS_DEV_Q059', 'HAAS_DEV_Q007', 'HAAS_DEV_Q025', 'HAAS_DEV_Q012', 'HAAS_DEV_Q015', 'HAAS_DEV_Q060', 'HAAS_DEV_Q009', 'HAAS_DEV_Q014', 'HAAS_DEV_Q001', 'HAAS_DEV_Q018'].
- en: đúng status 14/16; false_answer []; false_abstention ['HAAS_DEV_Q029', 'HAAS_DEV_Q027'].
- API errors: [{"question_id": "HAAS_DEV_Q016", "http_status": 503, "error_class": "GenerationError", "latency_ms": 14298.396}]
- Retry quan sát được: 6; HTTP provider status: {'200': 167, '429': 6}; provider timeout: [].
- Latency max ms: 89019.215; anomalies giữ nguyên trong mẫu: [].
- Pipeline guard (diagnostic, không phải verdict nghĩa): {"retrieval_needs_clarification": 1, "retrieval_insufficient_evidence": 20, "accepted": 26, "mechanical_guard_or_procedure_coverage": 6, "draft_insufficient_evidence": 8, "pipeline_verifier_rejected": 4, "api_error": 1}

### B_transcript_rag

- vi: đúng status 40/50; false_answer []; false_abstention ['HAAS_DEV_Q028', 'HAAS_DEV_Q064', 'HAAS_DEV_Q059', 'HAAS_DEV_Q012', 'HAAS_DEV_Q015', 'HAAS_DEV_Q060', 'HAAS_DEV_Q009', 'HAAS_DEV_Q018'].
- en: đúng status 16/16; false_answer []; false_abstention [].
- API errors: [{"question_id": "HAAS_DEV_Q063", "http_status": 504, "error_class": null, "latency_ms": 90010.731}, {"question_id": "HAAS_DEV_Q017", "http_status": 504, "error_class": null, "latency_ms": 90014.916}]
- Retry quan sát được: 10; HTTP provider status: {'200': 204, '429': 10}; provider timeout: [].
- Latency max ms: 90014.916; anomalies giữ nguyên trong mẫu: [].
- Pipeline guard (diagnostic, không phải verdict nghĩa): {"retrieval_needs_clarification": 1, "draft_insufficient_evidence": 26, "accepted": 31, "InvalidGeneration: Wrong answer language": 1, "retrieval_insufficient_evidence": 4, "api_error": 2, "InvalidGeneration: Semantic check failed": 1}

### C_no_graph

- vi: đúng status 33/50; false_answer ['HAAS_DEV_Q031']; false_abstention ['HAAS_DEV_Q026', 'HAAS_DEV_Q068', 'HAAS_DEV_Q007', 'HAAS_DEV_Q025', 'HAAS_DEV_Q017', 'HAAS_DEV_Q056', 'HAAS_DEV_Q010', 'HAAS_DEV_Q015', 'HAAS_DEV_Q060', 'HAAS_DEV_Q009', 'HAAS_DEV_Q014', 'HAAS_DEV_Q001', 'HAAS_DEV_Q018'].
- en: đúng status 15/16; false_answer []; false_abstention ['HAAS_DEV_Q029'].
- API errors: [{"question_id": "HAAS_DEV_Q059", "http_status": 504, "error_class": null, "latency_ms": 90008.295}, {"question_id": "HAAS_DEV_Q012", "http_status": 504, "error_class": null, "latency_ms": 90008.079}, {"question_id": "HAAS_DEV_Q016", "http_status": 504, "error_class": "GenerationError", "latency_ms": 921754.993}]
- Retry quan sát được: 15; HTTP provider status: {'200': 164, '429': 15}; provider timeout: [].
- Latency max ms: 921754.993; anomalies giữ nguyên trong mẫu: [{"question_id": "HAAS_DEV_Q016", "latency_ms": 921754.993, "http_status": 504, "backoff_seconds": 88.0, "provider_call_elapsed_ms": 4742.6990000000005, "explanation": "Observed latency over twice configured API deadline; cause not established; retained in all metrics"}].
- Pipeline guard (diagnostic, không phải verdict nghĩa): {"retrieval_needs_clarification": 1, "retrieval_insufficient_evidence": 22, "mechanical_guard_or_procedure_coverage": 6, "accepted": 25, "draft_insufficient_evidence": 6, "api_error": 3, "pipeline_verifier_rejected": 3}

## Đối chứng

A/B: 66 cặp; A đúng/B sai ['HAAS_DEV_Q017', 'HAAS_DEV_Q063', 'HAAS_DEV_Q064']; B đúng/A sai ['HAAS_DEV_Q001', 'HAAS_DEV_Q007', 'HAAS_DEV_Q014', 'HAAS_DEV_Q016', 'HAAS_DEV_Q025', 'HAAS_DEV_Q027', 'HAAS_DEV_Q029', 'HAAS_DEV_Q031', 'HAAS_DEV_Q058', 'HAAS_DEV_Q068'].

A/C: 54 cặp cùng nội dung ứng viên; A đúng/C sai ['HAAS_DEV_Q010', 'HAAS_DEV_Q017', 'HAAS_DEV_Q026']; C đúng/A sai ['HAAS_DEV_Q027', 'HAAS_DEV_Q028', 'HAAS_DEV_Q058']. Cặp khác ứng viên: ['HAAS_DEV_Q007', 'HAAS_DEV_Q015', 'HAAS_DEV_Q018', 'HAAS_DEV_Q025', 'HAAS_DEV_Q043', 'HAAS_DEV_Q056', 'HAAS_DEV_Q060', 'HAAS_DEV_Q062', 'HAAS_DEV_Q063', 'HAAS_DEV_Q064', 'HAAS_DEV_Q066', 'HAAS_DEV_Q068'].

Danh sách và hash chi tiết trong summary.json. Hash A/B có schema citation khác nhau nên khác hash không phải bằng chứng khác về nghĩa.

Chênh status/wording trong một lượt chưa chứng minh hỗ trợ về nghĩa hoặc hiệu ứng nhân quả của graph. Không được dùng để khẳng định graph vượt RAG.

## Các lỗi cần người chấm đối chiếu

Các ví dụ cụ thể sau được Codex ghi nhận ở lượt gốc 20261011_real_dev. Khi chạy lượt mới phải đối chiếu rows.jsonl của lượt mới, không sao chép verdict hoặc coi các lỗi này đã tái hiện tự động.

- Q005/Q021: A/C tái sử dụng B0_CL_014 nói mounting screws; nguồn nói that screw. Lỗi corpus đã được docs/retrieval_eval_real_dev.md ghi nhận. ai_audit_notes.jsonl pin đáp án mới bằng hash, reviewer_kind=ai; không chuyển verdict cũ thành human verdict của lượt mới.
- Q031 là lỗi nguy hiểm theo gold: hỏi loại mỡ cho con trượt hốc dao, A/C trả Lithium Tacky Grease cho ngón kẹp/lò xo/vòng đệm của double arm. Citation hợp lệ về ID/link nhưng sai bộ phận cần trả lời; cả draft/verify đều để qua. B từ chối. Phải chấm nghĩa độc lập; không sửa gold hoặc corpus ở lượt này.
- Smoke Q001: bản dịch linear guide làm claim-coherence chỉ khớp lubric, thiếu min_matches=2; gate rejected dù corpus có bước bôi trơn. Đây là trace diagnostic, không phải điểm chất lượng dịch đã được người chấm.
- Smoke/full Q058 có thể khác status dù cùng corpus/config: model draft/verify không tất định tuyệt đối ở temperature=0. Giữ riêng cả hai lượt, không chọn đáp án đẹp hơn.
- Q064: A/C có visual observation_note đã kiểm, B chỉ có text. Phải ghi khác biệt modality/preprocessing khi trình bày đối chứng.
- 429 làm backoff hoặc timeout 504; p95 phản ánh điều kiện hạn mức của key khi chạy chung ba arm. Không suy ra p95 cho tài khoản/quy mô tải khác.
- C/Q016 có timeout sau khoảng 922s dù deadline cấu hình 90s; tổng thời gian provider calls và backoff dự kiến không giải thích hết khoảng trễ. Có lỗi ConnectError kế tiếp. Nguyên nhân scheduling/host/tool chưa xác định; giữ nguyên số đo, không cap xuống 90s hoặc loại khỏi p50/p95. Đây không phải bằng chứng latency hosting ổn định.

## Chạy lại

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow prepare --run-dir benchmarks/results/<NEW_RUN>
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow smoke --run-dir benchmarks/results/<NEW_RUN>
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow run --run-dir benchmarks/results/<NEW_RUN>
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow report --run-dir benchmarks/results/<NEW_RUN>
```

Key chỉ ở môi trường/.env. `run` resume chỉ những task chưa ghi journal, không sinh lại hoặc xóa lỗi cũ. `report` không gọi API và không ghi đè phiếu review đã có.

## Kiểm tra và nhật ký chuẩn bị

134 test evaluator/generation hiện có và 6 test integrity benchmark đã qua; XML lưu kèm. Lượt pytest đầu gặp lỗi quyền truy cập thư mục temp ngoài workspace; chạy lại với --basetemp dưới out/ đã qua, không sửa product để làm test pass.

Trước smoke, runner từng chặn do so manifest chứa trường return status của build_index với manifest lưu trong DB. Đã sửa duy nhất guard của benchmark, trước mọi câu smoke/full. frozen_config_before_guard_fix.json và freeze_amendments.json giữ bản ghi; config, gold, corpus và product không thay đổi. Lượt embedding build và BM25 ban đầu vẫn được giữ, không giấu phí.

Một lần ngắt công cụ/environment dừng process sau 107 rows, ở B/Q019. interruption_journal.json giữ các call chưa có kết quả HTTP. Chỉ resume task chưa có row; không chạy lại các đáp án hoàn tất hoặc lỗi HTTP để chọn kết quả đẹp hơn. Chi phí cộng cả call trước khi bị ngắt; latency của phần chưa hoàn tất là null.

artifact_verification.json kiểm hash câu trả lời, đủ task/review rows, journal call IDs, frozen files, key không lọt artifact và keyframe bytes khớp product commit. Các file không đọc nội dung holdout.

Config hash: `5d909552eb9c998567331167a833da1b81a63e357c7926add9ab9720f1b7caf3`. Questions hash: `0793aea3eaf00b12883ef5ad1e0d251c3d19d617ac2ac32c1a07bd22b293d7de`. Corpus files hash: `bf9752e17feee4e853a6536f7eb4cacadd9ed945812648a7d95fa9ed982a886a`.

audit.json lưu revisions/review trạng thái/dependencies; frozen_config.json lưu hash product và measurement code trước khi gọi API; provider_calls.jsonl lưu từng HTTP attempt và usage không chứa key; rows.jsonl lưu từng đáp án/citation/trace/lỗi.
