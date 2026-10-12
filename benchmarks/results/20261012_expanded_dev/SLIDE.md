**Giới hạn:** giữ nguyên 81 nhãn hiện có; 20 nhãn phủ định chờ quyết định review trên corpus mới.

# Số liệu có thể đưa lên slide

- Corpus Haas real/dev mở rộng: 9 workflow; 81 câu có nhãn người kiểm, 243 terminal attempts A/B/C.
- KnowFlow Recall@5 96.15%, n=52; đây là retrieval, chưa chứng minh đáp án đúng.
- Status đúng A/B/C: 67 / 67 / 67 trên 81 câu/arm.
- 15 câu mới (đều tiếng Anh): A khớp status 14/15; Recall@5 100.00%, n=15.
- Citation A hợp lệ bằng code: 65/65; chưa chấm độ hỗ trợ nghĩa.
- A/C cùng ứng viên: 81 cặp; không mặc nhiên kết luận graph tốt hơn RAG.
- Known API subtotal của một QA A độc lập: $0.004910/câu; tổng phí và hóa đơn null vì thiếu usage/giá embedding, usage lần lỗi. Chưa gồm hosting/công chuyên gia.
- Chấm nghĩa chờ người đối chiếu nguồn; không dùng số liệu này cho giảm 30% thời gian hay ROI.
