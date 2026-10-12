# Nội dung ngắn cho slide — pilot real/dev

**Kiểm chứng bằng model thật trên nguồn Haas, không dùng synthetic**

- 66 câu được người kiểm nhãn; 3 phương án, 198 lượt đã ghi. Snapshot, cấu hình, token và lỗi lưu để đối chiếu.
- KnowFlow hybrid + dịch: Recall@5 **94.59%, n=37**; BM25 không dịch chạy mới **58.11%, n=37**. Đây là đối chiếu cấu hình tổng hợp, chưa chứng minh đóng góp riêng của graph.
- Đúng status / 66: KnowFlow **49**, transcript RAG **56**, bỏ cạnh graph **48**. Không coi status match là độ đúng nghĩa của đáp án.
- Citation hợp lệ theo code A/B/C: 42/42, 64/64, 41/41. Đúng nghĩa và điều kiện đang chờ người chấm. Trả lời khi gold yêu cầu từ chối A/B/C: 1/0/1.
- KnowFlow p50 3.83s, p95 31.86s, n=66, gồm retry/lỗi. Lỗi HTTP toàn thí nghiệm: 6. Xem latency anomalies trong báo cáo; chưa chứng minh tốc độ hosting ổn định.
- Phần phí standard đã xác định của KnowFlow **$0.2316/66 task**, ~$0.00351/task. Chưa gồm embedding/fee chưa biết, server, preprocessing, expert labour; hóa đơn thực chưa biết.

Ghi chú presenter: đây là dev, một lượt đo. Không thay human review bằng verifier của model; không khẳng định ROI hoặc giảm 30% thời gian lao động. Bảng đầy đủ/dữ liệu gốc: REPORT.md, summary.csv, rows.jsonl, provider_calls.jsonl.
