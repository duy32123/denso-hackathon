# Benchmark real/dev qua đường phục vụ KnowFlow

Đo commit sản phẩm `dfde6f43704b532053c74e09701d1e978d5d12f9`. Không chỉnh sản phẩm, corpus hoặc gold để cải thiện số đo. Không push; không mở nội dung holdout; không cộng synthetic vào mẫu số real.

## Phương án

- **A**: API `/v1/ask` → `QAService.ask` → retrieval hybrid, dịch thật, embedding thật, sinh và kiểm thật. Các adapter được bọc để ghi metadata; prompt, retry và kiểm citation của sản phẩm được giữ nguyên.
- **B**: RAG trên 3 corrected transcript + 2 `Source.raw_text`. Chunk 180 từ, overlap 30. Index/prompt không đọc workflow, step, claim hoặc gold. Cùng model, thuật toán hybrid, top-k, ngôn ngữ, giới hạn output/context và yêu cầu citation từ nguồn. Khác biệt preprocessing, relevance gate, routing và định dạng citation được báo riêng.
- **C**: Cùng index và nội dung A; tắt neighbor expansion và bỏ `relations` trước generation. Giữ text của relation claims để đúng yêu cầu giữ nguyên nội dung. Chỉ benchmark có adapter này; không sửa logic sản phẩm.

Các câu được shuffle bằng seed cố định và xoay thứ tự A/B/C. Không dùng cache câu hỏi/bản dịch, không tìm cấu hình tốt nhất trên bộ đang báo cáo. Mỗi HTTP attempt, lỗi và token được journal ngay khi hoàn tất. Không retry cả task để chọn đáp án tốt hơn; resume chỉ task chưa có dòng kết quả.

## Chạy

Key đặt trong `.env` hoặc biến môi trường. Không đưa key vào tham số CLI.

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow prepare --run-dir benchmarks/results/<NEW_RUN>
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow smoke --run-dir benchmarks/results/<NEW_RUN>
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow run --run-dir benchmarks/results/<NEW_RUN>
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow report --run-dir benchmarks/results/<NEW_RUN>
```

`prepare` xác thực bundle/gold/revision, lưu cấu hình và hash trước khi đo, chạy BM25 mới, rồi dựng index thật trong thư mục `out/benchmark_knowflow/<NEW_RUN>` riêng. Không ghi vào database demo hoặc canonical snapshots. `smoke` chạy 4 câu đã chọn trước trên cả 3 phương án, tách khỏi lượt 66 câu.

Trong sandbox chặn mạng, cần cho phép tiến trình benchmark gọi Gemini. TestClient đo API application và deadline thật, không đo mạng người dùng truy cập public hosting.

## Diễn giải

- Recall/MRR chỉ có gold phù hợp cho A/C: 37 câu answered/detail. Không tự biến gold Step thành gold raw chunk cho B.
- So status với gold là kiểm bằng code. Người chấm phải xác nhận đáp án có trả lời câu hỏi, đúng điều kiện và được nguồn hỗ trợ.
- Token thiếu, phí thiếu hoặc billing tier chưa biết = `null`. Chỉ phí các call không thực hiện mới có thể xác định là 0.
- Chi phí list-price quy đổi từ usage metadata tách embedding/dịch/draft/verify, index và smoke. Hóa đơn thực, hosting, preprocessing và công chuyên gia chưa đo.
- Nếu một HTTP request timeout, phí provider vẫn được ghi sau khi công việc đang chạy kết thúc; thời gian HTTP người dùng chờ và thời gian drain tách riêng.
- Kiểm bằng Gemini trong pipeline không phải benchmark human verdict. Các trường nghĩa để `null` tới khi nhóm chấm xong.

## Chấm nghĩa sau khi chạy

Điền bản sao `human_review.csv`; giữ hash, ghi rõ reviewer_kind human hoặc ai. Không lấy model đang tạo đáp án làm bằng chứng độc lập cho độ đúng. Lệnh import kiểm hash, số citation và chỉ tính human vào chỉ số người chấm:

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow.review --run-dir benchmarks/results/<RUN> --sheet <REVIEWED_CSV>
```

Report được tạo lại không ghi đè phiếu review đang điền. Kết quả mới nằm riêng trong `semantic_review_summary.json`; không ghi đè báo cáo bằng code hoặc nhãn eval.
