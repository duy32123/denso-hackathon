# Demo bản đồ tri thức — phục vụ ý tưởng A2

Mục tiêu: cho thấy tri thức có quan hệ, có bằng chứng và có phần thiếu để thu thập
kinh nghiệm. Phần bản đồ đọc snapshot hiện có, không gọi LLM để tạo thêm quan hệ.
Nội dung nguồn vẫn giữ nguyên ngôn ngữ tiếng Anh để đối chiếu.

Bản trình chiếu 3D tại `/space`: [thao tác, câu chuyện 90 giây và phạm vi đồ thị](a2_knowledge_space_3d.md).

## Chuẩn bị local

Từ gốc repo:

```powershell
uv pip install --python .venv/Scripts/python.exe -e ".[dev,api,retrieval]"
.\.venv\Scripts\python.exe -m retrieval.importer import acquisition/export/haas_pilot_dev_bundle --db out/retrieval/real_dev.sqlite --source-type real --split dev
.\.venv\Scripts\python.exe -m retrieval.retrieval build --db out/retrieval/real_dev.sqlite --mode real --split dev --embedding none
.\.venv\Scripts\python.exe -m retrieval.api
```

Mở `http://127.0.0.1:8000`. Đọc bản đồ, claim, bằng chứng và lịch sử chạy trên index
local; phần này không cần Gemini key. Chức năng hỏi đáp cần cấu hình LLM và index
phù hợp theo [grounded QA](team2_grounded_qa.md).

## Kịch bản khoảng ba phút

1. **Bộ nhớ kinh nghiệm.** Chọn `REAL_WF_0003 · r2` ở Bản đồ tri thức quy trình.
   Giới thiệu nguồn Haas đã xử lý trước, bước và review nguồn. Model máy chưa được xác
   định; chưa có expert validation. Đây là ví dụ minh họa thu nhận tri thức.
2. **Nhánh quyết định.** Bấm nút `3 → 4 · Nhánh có điều kiện`. Mở điều kiện chuyển
   bước và căn cứ quan hệ. Bấm Mở bằng chứng để xem lời nói nguồn. Nhấn mạnh khác
   biệt giữa thứ tự các bước và nhánh có điều kiện được nguồn nêu.
3. **Bốn câu hỏi người học cần.** Bấm bước 5 trên sơ đồ. Đọc Làm gì, Khi nào, Vì sao,
   Kiểm chứng bằng gì. Thao tác có claim; lý do bị giữ thiếu. Mỗi phát biểu giữ phạm vi,
   attribution và hai chiều review; mỗi nút bằng chứng mở đúng revision/index.
4. **Khoảng trống dẫn tới thu thập kinh nghiệm.** Ở câu hỏi lý do của bước 5, bấm
   Bổ sung cho câu hỏi này. Form chọn đúng `Q_001`, `ST_005`, `rationale`. Nội dung
   bổ sung cần người trả lời thật và người kiểm khác. Preview là bước đọc trước khi lưu.
5. **Tri thức tiếp tục được cập nhật.** Mở lịch sử và giải thích đường đã có:
   phản hồi tạo revision pending → người kiểm đối chiếu → revision đã review → export,
   import/reindex → hỏi lại. Nếu thực hiện ghi khi diễn tập, dùng bản sao repo. Đánh giá
   khả năng chạy trọn vòng này riêng với phần đọc bản đồ.

Để đối chứng cách vẽ, chọn `B0_SRC_HAAS_0005`: snapshot này có bước nhưng không có
Relation record. Bản đồ sẽ không thêm mũi tên. Chọn quy trình hoặc revision khác
phải vẽ lại từ snapshot tương ứng; đổi corpus xóa bản đồ cũ.

## Nội dung dùng khi thuyết trình

“KnowFlow tổ chức kinh nghiệm thành bước, điều kiện, lý do và bằng chứng. Phần chưa
được nguồn giải thích được giữ thành câu hỏi để thu thập bổ sung. Người học tra cứu
có căn cứ; người có chuyên môn tập trung bổ sung và duyệt phần còn thiếu.”

“Bản demo đã có đồ thị bước–quan hệ và liên kết claim–evidence. Đồ thị thực thể thiết
bị/công cụ xuyên quy trình là phần mở rộng dự kiến. Pilot tiếp theo đo giá trị của
quan hệ và vòng bổ sung so với RAG trên transcript.”

Tham khảo [nội dung sáu mục của hồ sơ](a2_idea_submission.md). Hiệu quả định lượng
và khả năng áp dụng ở doanh nghiệp được đo trong kế hoạch sáu tuần.

## Kiểm tra bản demo — 2026-10-10

- Bộ test dự án: 833 passed, 2 skipped; hai test gọi Gemini thật chưa chạy.
- Kiểm tra Edge sau chỉnh sửa cuối: bản đồ, quan hệ có điều kiện, mở đúng evidence,
  chọn câu hỏi thiếu, đổi corpus và bố cục desktop/mobile đều qua.
- Ảnh xem trước local: [bản đồ tri thức](../out/a2_knowledge_map_preview.png).
- Báo cáo local: `out/a2_knowledge_map_tests.xml` và
  `out/a2_knowledge_map_browser.xml`. Các artifact trong `out/` không được commit.

Các kiểm tra này xác nhận chức năng phần mềm; chưa đo hiệu quả đào tạo, lợi ích
truy xuất của đồ thị hoặc độ đúng kỹ thuật với chuyên gia doanh nghiệp.
