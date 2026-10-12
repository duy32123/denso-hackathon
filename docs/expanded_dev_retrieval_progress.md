# Retrieval sau PR #53 — tiến độ 2026-10-12

## Phạm vi và trạng thái

Làm trên nhánh `feature/a2-expanded-dev-retrieval`, xuất phát từ `main@4a18533`
(merge PR #53), không dùng feature branch 3D cũ. Khi bắt đầu working tree sạch.
Không sửa corpus, nhãn chính thức hoặc run `20261011_real_dev`. Không mở holdout.

Corpus active: 9 workflow / 67 Step. Bộ chính thức có 81 câu (50 Vi, 31 En),
66 câu cũ + 15 câu mới tiếng Anh; Recall/MRR chấm 52 answered/detail (37 cũ, 15 mới).
Nhãn 20 câu phủ định được người kiểm trên corpus cũ, cần xác nhận lại trên corpus
mở rộng trước benchmark chính thức. Không gọi các đề xuất của AI là review người.

## Nhãn và đối chiếu nguồn

[Phiếu nguồn](../data/eval/reviews/20261012_expanded/README.md) gồm inventory của
toàn bộ Step active, claim, locator, URL và lời nguồn đọc qua EvidenceAccess.
`negative_label_review.csv` có fingerprint, decision/note trống; nhóm đã nhận việc
điền phiếu và gửi tên người kiểm.

| Câu | Nguồn cần đọc | Nhận định AI chờ xác nhận |
|---|---|---|
| Q041 | REAL_WF_0008_ST_003, CL_008, EV_011, SRC_HAAS_0012 61.470–74.430s | Có kiểm coolant concentration bằng refractometer; không có phần trăm. Đề xuất retrieval=retrieved, answer=insufficient_evidence. |
| Q049 | REAL_WF_0005_ST_004, CL_027, EV_031, SRC_HAAS_0009 161.870–172.880s | Có điều kiện belt-driven và kiểm tension/cleanliness; không có trình tự thay đai. Đề xuất retrieval=retrieved, answer=insufficient_evidence. |
| Q039 / Q050 | Context chỉ định subsystem=SMTC | Nguồn spindle / way-cover trên không qua hard filter của request này; đề xuất giữ cả hai status insufficient_evidence. Không tự bỏ context. |

Người kiểm có thể bác bỏ các đề xuất. Việc tìm thấy Step liên quan không chứng minh
đủ nguồn để trả lời. Wrapper apply ghi diff, hash trước/sau và reviewer thật;
runner chặn trước khi tạo run/gọi API nếu chưa có `human_approval.json` hợp lệ.

## Bản sửa và nguyên nhân

- Q069: cổng cũ loại `alarm 626` vì đã hard-filter context, chỉ còn `occur` khớp
  nội dung trong một claim. Quy tắc mới cho tra nghĩa/nguyên nhân alarm khi mã
  chính xác và từ alarm có trong claim đủ điều kiện. Metadata hoặc claim bị loại
  không được cứu truy vấn; không mở ngoại lệ cho thao tác bất kỳ kèm mã alarm.
- Q015/Q031: ranking có thể chọn workflow khác đơn vị đã mở cổng. Bản dịch cũ còn
  làm pocket slider thành magazine slide guideway/linear guide, khiến mỡ của
  double-arm hoặc way-cover rail được trả nhầm. Danh tính bộ phận ghép được lấy
  từ câu gốc và bản dịch, kiểm trong heading + claim đủ điều kiện. Câu grease/
  lubrication còn phải có thao tác đó trên bộ phận; ranking và gate dùng cùng
  tập đã lọc. Procedure giữ toàn bộ Step của workflow được định danh.
- Glossary dịch `q2en-3` giữ pocket slider khác double-arm slider/way-cover rail.
  Source text, revision, number, gold và ngưỡng .20 giữ nguyên.

Đây là từ điển danh tính bộ phận có phạm vi hữu hạn, có thể từ chối oan cách gọi
chưa nhận diện hoặc câu so sánh nhiều bộ phận. Không tuyên bố giải quyết mọi lỗi
routing hoặc mọi ca ngoài phạm vi trên corpus lớn. Ví dụ truy vấn replace không
nêu lubrication vẫn có thể xếp quy trình alarm pocket phía trên replacement;
không có số đo API chứng minh sửa hết trường hợp này.

## Chẩn đoán offline: cùng corpus, cùng bản dịch đã gọi thật

[summary.json](../benchmarks/diagnostics/20261012_expanded_fixes_v2/summary.json),
[rows.jsonl](../benchmarks/diagnostics/20261012_expanded_fixes_v2/rows.jsonl).
So mã PR #53 với bản sửa trên cùng DB expanded; lexical, giữ bản dịch A từ run
API 20261011. 81/81 hoàn tất mỗi phía, 0 API calls mới, không dùng vector giả.
Đây không phải đo prompt dịch mới hoặc benchmark A/B/C và không là holdout.

| Chỉ số retrieval | PR #53 | Bản sửa | Mẫu số |
|---|---:|---:|---:|
| Recall@5 | 92.31% | 98.08% | 52 |
| MRR@5 | 0.8189 | 0.8638 | 52 |

Q001/Q015/Q069 từ không có gold hit thành có hit. Q031 route từ WF_0002 sang
B0 Step 6; Q015 từ WF_0008 sang B0 Step 6. Q014/Q019 giữ gold hit nhưng các
Step không đúng danh tính bộ phận bị lọc. Không có câu answered/detail tụt Recall
trong lượt này; **Q069 gold ở hạng 3**, không tự coi là hạng 1. Không chấm độ đúng
đáp án từ kết quả này; không báo điểm nhãn phủ định chưa xác nhận là thành tích.

## Smoke qua API thật: giữ nguyên cả lỗi còn lại

[Dữ liệu gốc](../benchmarks/diagnostics/20261012_live_fix_smoke/rows.jsonl),
provider calls/token/retry lưu kèm. QAService qua `/v1/ask`, hybrid, Gemini
embedding + dịch + draft/verify thật. Bộ nhỏ 3 câu, không cộng vào full run.

| Câu | HTTP / status | Workflow | Latency quan sát |
|---|---|---|---:|
| Q015 | 200 / insufficient_evidence | B0 r2, đúng pocket slider | 3.537s |
| Q031 | 200 / insufficient_evidence | B0 r2, đúng pocket slider | 2.867s |
| Q069 | 200 / answered | WF_0004 r1 | 4.024s |

Q015 **vẫn từ chối oan ở tầng draft** theo gold cũ (bằng gì → grease), dù chọn
đúng bộ phận. Q031 không lấy Lithium Tacky Grease/RED-i của bộ phận khác. Q069
trích CL_001/EV_002. Các nhận xét này là đối chiếu của AI, không human verdict.
Không sinh lại các câu để chọn đáp án tốt hơn. Các latency trên chỉ là 3 mẫu local,
không suy thành p95 hosting, thời gian người tiết kiệm hay hiệu quả DENSO.

## Câu nháp và đối chứng A/C

[40 câu nháp](../data/eval/haas_real_dev.expanded_vi_hard.draft.jsonl): 35 Vi, 5 En;
15 bản dịch câu mới + 25 ca điều kiện, thiếu số/thao tác, nhầm bộ phận, trình tự.
Có [phiếu review riêng](../data/eval/reviews/20261012_expanded/vi_hard_draft_review.csv),
0 human-reviewed, không cộng vào 81 hoặc các số báo cáo chính thức.

Runner v2 lưu một retrieval thật cho mỗi cặp A/C, copy cùng bản dịch/embedding/
context/ứng viên trước ablation. C bỏ đúng ba trường graph. Retrieval lỗi được
giữ cho cả cặp. API calls chung ghi dưới `AC_shared_retrieval`, tổng phí chỉ cộng
một lần. Hai generation/verifier độc lập có thể khác kết quả dù temperature=0.
Latency arm replay cần phân biệt HTTP quan sát với tổng thành phần tái dựng.
Không dùng replay làm bằng chứng C nhanh/rẻ hơn.
Timeout của arm replay bị trừ thời gian retrieval gốc khỏi deadline 90s, tránh
cho arm thứ hai thêm ngân sách sinh đáp án.

## Kiểm tra và bước còn lại

- Bộ đầy đủ: 916 tests collected, 911 passed, 3 skipped, 2 lỗi giả định đường dẫn
  temp của B0 extraction khi `--basetemp` nằm trong repository. Chạy lại 16 test
  B0 pipeline với temp mới ngoài repo: 16 passed, không sửa acquisition.
- Kiểm thử tập trung trước bổ sung kiểm chi phí và interruption: 64 passed; lượt cuối **66 passed**,
  gồm 11 test benchmark integrity. Stub chỉ dùng kiểm thử, không dùng làm chất lượng.
- Test API/corpus đều giữ namespace/review/revision gates. Không sửa gold cho khớp
  engine. Regression kiểm lookup alarm, code sai/claim bị loại, sai bộ phận,
  quá trình procedure đủ Step, A/C mutation isolation, shared error và ledger cost.

## Full API 81 × 3: đã hoàn thành, giữ nguyên nhãn

[Run 20261012](../benchmarks/results/20261012_expanded_dev/REPORT.md) đã hoàn thành
243/243 lượt, sau smoke 12/12 HTTP 200. Mã đo tại `d47308e`, dựa trên main PR #53;
không sử dụng nhánh 3D cũ. Mỗi cặp A/C tái dùng một retrieval thật, hash ứng viên
và bản dịch giống nhau ở 81/81 cặp. C bỏ đúng các trường cạnh/mở rộng; không bỏ
claim chuẩn hóa. Không mở holdout và không chạy lại câu lỗi để chọn kết quả.

Người dùng yêu cầu chạy, báo đã kiểm nguồn và cung cấp GitHub `duy32123`, nhưng
chưa gửi quyết định trong phiếu 20 nhãn. Run dùng `config_existing_labels.json`,
giữ nguyên hash gold `59af8902…`; 0 thay đổi nhãn, không tạo human approval mới.
Q041/Q049 retrieval=retrieved, answer=insufficient_evidence; hai status cần được
review riêng. Đề xuất AI không chuyển thành nhãn do người kiểm.

| Tập | Status đúng A/B/C | Recall@5 A/C (n) | MRR@5 A/C |
|---|---|---|---|
| 66 câu cũ | 53 / 53 / 53 trên 66 | 94.59% (37) | 83.87% |
| 15 câu mới, đều En | 14 / 14 / 14 trên 15 | 100% (15) | 93.33% |
| Toàn bộ 81 | 67 / 67 / 67 trên 81 | 96.15% (52) | 86.60% |

B chưa có raw-chunk gold do người kiểm: Recall/MRR=null. Cả ba trả answered ở
42/56 câu expected answered; đây chưa phải độ đúng nghĩa. Citation hợp lệ bằng
code A/B/C: 65/65, 90/90, 66/66. Có 4 timeout: A Q059/Q062, B Q001/Q074; provider
full run có 30 HTTP 429/retries quan sát. Lỗi giữ trong tất cả mẫu số status và
latency, không biến timeout thành false abstention. A có 12 false abstention,
B 12, C 14 theo gold hiện có; 0 false answer theo gold, không gọi là 0 hallucination.

So với run cũ trên cùng 66 ID: A 49→53, B 56→53, C 48→53 status đúng. A Recall
giữ nguyên 94.59%; MRR 86.58%→83.87%. Corpus, dịch, pairing và điều kiện API đã
đổi; đây là so sánh mô tả, không cô lập tác động bản sửa. A/C status thắng 3–3;
Q029 còn đổi status khi không có relations trong prompt, cho thấy biến thiên
generation ngoài graph. Chưa chứng minh graph hoặc KnowFlow vượt transcript RAG.

Q069 answered ở cả ba arm, gold ở hạng 3 trong A/C. Q015/Q031 chọn đúng pocket
slider B0 r2; Q031 không dùng sai loại mỡ bộ phận khác, Q015 vẫn từ chối oan ở
draft. Q012/Q056 còn vướng dịch/relevance gate. Q083 bị guard số vì `21` khác
`twenty one` trong quote. Các điều tra AI có hash, không phải human semantic verdict.

Subtotal API đã biết của toàn thí nghiệm **$0.976087**, riêng full QA **$0.937048**;
tổng phí và hóa đơn **null**. Known subtotal tham chiếu một QA độc lập A/B/C:
**$0.004910 / $0.001617 / $0.005095** trên mỗi câu planned; phần shared A/C chỉ
tính một lần trong tổng thí nghiệm. Thiếu embedding usage/rate, usage lần lỗi;
chưa gồm hosting, extraction/preprocessing, công chuyên gia. Index/smoke/probe
tách riêng. Batch index 32 gặp 429; đổi pacing/batch trước smoke/full và đóng
băng lại, giữ toàn bộ lỗi cũ, không đổi nội dung/model/gold/retrieval.

HTTP local p50/p95 A/B/C: 3.974/35.976s, 3.365/44.241s, 4.186/30.014s, n=81/arm,
gồm retry và lỗi. A/C có arm replay nên không dùng các chênh lệch này để đo lợi
ích graph; tổng thành phần tái dựng được lưu riêng, không phải hosting latency.

[JSONL gốc](../benchmarks/results/20261012_expanded_dev/rows.jsonl),
[CSV theo câu](../benchmarks/results/20261012_expanded_dev/per_question.csv),
[phiếu chấm nghĩa](../benchmarks/results/20261012_expanded_dev/human_review.csv),
[lệnh chạy lại](../benchmarks/knowflow_expanded_dev/README.md). Hash mã/corpus/gold,
revision và dependency versions được pin. Chấm nghĩa 0 người, các chỉ số nghĩa=null.

## Dùng được trên slide lúc này

“Kho tri thức demo: 9 workflow / 67 bước / 303 claim. Benchmark API thật 81 câu
× 3 cấu hình: KnowFlow Recall@5 96.15%, n=52; status khớp 67/81 ở cả A/B/C.
Nhãn giữ nguyên, 20 nhãn phủ định chờ quyết định review mở rộng; 40 câu khó nháp
tách riêng. Chấm nghĩa phải được thực hiện độc lập.”

Không tuyên bố graph vượt transcript RAG, giảm 30% thời gian hay ROI DENSO. Full
benchmark có dữ liệu thật, chi phí chỉ có subtotal đã biết, chấm nghĩa còn null. Run cũ giữ nguyên.

Smoke chẩn đoán 3 câu ở trên phát sinh 9 provider calls thật; phần giá standard đã biết **$0.008359**,
tổng đầy đủ **null** do embedding usage/rate chưa biết. Đây là phí của 3 câu smoke,
không phải phí trung bình benchmark 81 câu. Chi tiết và URL/ngày tra giá trong
[costs.json](../benchmarks/diagnostics/20261012_live_fix_smoke/costs.json).
