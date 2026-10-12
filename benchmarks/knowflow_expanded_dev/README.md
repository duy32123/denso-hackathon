# Benchmark sau PR #53

Cấu hình đề xuất `config.json`: 81 câu đã có review, corpus 9 workflow, không cộng
40 câu nháp Vietnamese/hard. Cấu hình này chưa được khóa vào run khi phiếu 20 nhãn
phủ định trên corpus mới chưa được người kiểm hoàn tất.

## Thứ tự chạy

1. Nhóm đọc nguồn ở `data/eval/reviews/20261012_expanded`, điền tất cả 20 dòng
   `negative_label_review.csv` bằng `ok/fix` và note dựa vào nguồn. Người kiểm
   khác người soạn nhãn. Không dùng prediction để quyết định gold.
2. Áp dụng bằng lệnh dưới với danh tính người thật. Wrapper dùng đường review
   đã có, giữ nhãn cũ/mới trong `label_changes.jsonl`, tạo `human_approval.json`
   gắn với hash câu hỏi và bundle. Nó không tự điền/duyệt phiếu.
3. Commit bản sửa và nhãn đã xác nhận trước `prepare`. Không đổi code/corpus/config
   sau `prepare`; không quét tham số hoặc chạy lại task lỗi để chọn đáp án đẹp hơn.
4. `prepare` tạo index Gemini mới và baseline từ transcript; `smoke` kiểm khả năng
   chạy API, không dùng điểm chất lượng làm gate; `run` chạy cả 81 × 3.

```powershell
.\.venv\Scripts\python.exe -m scripts.review_expanded_dev apply --reviewer-id <human-id>
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow prepare --config benchmarks/knowflow_expanded_dev/config.json --run-dir benchmarks/results/20261012_expanded_dev
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow smoke --run-dir benchmarks/results/20261012_expanded_dev
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow run --run-dir benchmarks/results/20261012_expanded_dev
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow report --run-dir benchmarks/results/20261012_expanded_dev
.\.venv\Scripts\python.exe -m scripts.benchmark_knowflow.verify_artifacts --run-dir benchmarks/results/20261012_expanded_dev
```

Mỗi lần đo độc lập dùng một tên thư mục mới. Key chỉ ở môi trường/.env.

## A/C cùng ứng viên

Một retrieval thật cho mỗi cặp, lưu toàn bộ kết quả và hash ở `shared_retrieval/`.
C nhận bản sao trước khi bỏ `relations`, `related_steps`, `related_claims`; không
đổi Step, claim, context, bản dịch hoặc embedding. A/C vẫn gọi QAService qua API
và chạy draft/verify độc lập. Retrieval lỗi được giữ ở cả hai arm, không retrial
riêng để cứu một arm. Bộ smoke và full tách cache theo phase.

Provider calls chung ghi một lần dưới `AC_shared_retrieval`. Chi phí generation/
verification của A/C tách khỏi phần chung. Tổng thí nghiệm cộng phần chung một lần;
standalone reference cộng một retrieval gốc/arm chỉ để tham khảo chi phí một tác vụ
độc lập, không phải hóa đơn mới. Không báo arm C miễn phí retrieval.

`latency_ms` là HTTP quan sát thật. Arm thứ hai dùng replay nên latency HTTP không
đủ để so hiệu ứng graph. `latency_ms_standalone_component_sum` cộng thời gian retrieval
gốc vào arm replay; đây là tổng thành phần tái dựng, không phải latency toàn luồng
deployment. Cả hai mẫu được báo rõ, không suy thành thời gian người tiết kiệm.
Timeout endpoint của arm replay bị trừ thời gian retrieval gốc khỏi tổng deadline
90s, giữ cùng ngân sách thời gian generation; không cho arm thứ hai thêm 90s sau
khi đã tái sử dụng retrieval. Mỗi row ghi `effective_api_timeout_seconds`.

## Báo cáo

`summary.csv/json`: 66 câu cũ, 15 câu mới, toàn bộ 81; Vi/En riêng; lỗi và mẫu số
riêng. B không có raw-chunk gold do người kiểm nên Recall/MRR B=null. Phiếu chấm
nghĩa pin hash đáp án; verifier nội bộ không phải người chấm. Phí index/smoke tách
QA. Usage/rate chưa biết=null, không gán 0.

Lượt cũ `benchmarks/results/20261011_real_dev` giữ nguyên. Tài liệu tiến độ:
[expanded_dev_retrieval_progress.md](../../docs/expanded_dev_retrieval_progress.md).
