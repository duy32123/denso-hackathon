# Đối chiếu nhãn trên corpus sau PR #53

Đây là phiếu chờ người kiểm. AI không thay nhãn chính thức và không đánh dấu human-reviewed.

1. Đọc `source_inventory.json`: claim, revision, evidence, lời nguồn và URL. Với nhận định nguồn không đủ, đối chiếu cả transcript gốc tương ứng; không chỉ đọc một đoạn đã chọn.
2. Đọc `ai_proposals.jsonl`. Q041 có nguồn kiểm nồng độ nhưng không nêu phần trăm; Q049 có nguồn kiểm dây đai nhưng không có trình tự thay. AI đề xuất retrieval=retrieved, answer=insufficient_evidence cho hai câu này. Q039/Q050 chỉ định subsystem=SMTC, hard filter loại hai workflow mới tương ứng nên đề xuất giữ nhãn; không bỏ context. Người kiểm có thể bác bỏ.
3. Điền `negative_label_review.csv`: `decision=ok/fix`, hai status riêng, gold_step_ids và note. Hai đề xuất trên dùng lần lượt REAL_WF_0008_ST_003 / REAL_WF_0005_ST_004; decision/note hiện để trống. Nếu cần drop, nhóm phải chốt lại phạm vi 81 câu trước khi chạy.
4. Người kiểm thật, khác người soạn, phải xác nhận tất cả dòng trước khi khóa bộ 81 câu cho benchmark. Ghi danh tính và thời điểm; không dùng kết quả engine để phê duyệt gold.

Áp dụng bằng đường review có sẵn (đổi DB nếu chạy ở máy khác):

```powershell
.\.venv\Scripts\python.exe -m scripts.review_expanded_dev apply --db out/web/real_dev_4a18533.sqlite --reviewer-id <github-user>
```

Sau khi áp dụng: lưu diff nhãn và hash cũ/mới, xuất sheet mới, khóa cấu hình; không mở holdout.
