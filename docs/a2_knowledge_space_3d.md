# Không gian tri thức 3D — KnowFlow AI

## Mở demo

Chạy server theo [chuẩn bị local](a2_knowledge_map_demo.md#chuẩn-bị-local), rồi mở
`http://127.0.0.1:8000/space`. Trang chính cũng có nút **Khám phá không gian tri thức 3D**.
Không gian đọc index hiện có, không gọi LLM. Three.js 0.186.0 được lưu trong repo;
không tải module, font hoặc tài nguyên từ CDN khi trình chiếu.

## Thao tác

- Kéo chuột hoặc một ngón tay để xoay; cuộn hoặc chụm hai ngón tay để zoom.
- Chọn nút trên không gian: sáng các liên kết liên quan, camera hướng tới nút,
  bảng bên phải mở nội dung, phạm vi và review. Khi chọn tri thức trong một quy trình,
  không gian tập trung vào cụm đó để dễ đọc; **Về toàn cảnh** mở lại các cụm.
- Tìm bằng nội dung, ID hoặc tên quy trình. Nút kết quả tìm kiếm dùng được bằng bàn phím.
- Bật/tắt từng loại nút qua chú giải. **Về toàn cảnh** trả camera về kho.
- **Tự xoay** bật/tắt chuyển động. Khi người dùng chọn hoặc kéo nút, tự xoay dừng.
- **Trình chiếu** mở toàn màn hình; **Esc** hoặc nút thoát đóng trình chiếu.
- Khi focus canvas: phím mũi tên xoay, `+`/`-` zoom, `Home` về toàn cảnh.
- Thiết lập giảm chuyển động của hệ điều hành được tôn trọng.

Nếu WebGL không dùng được, tìm kiếm, nội dung, tour và mở bằng chứng vẫn hoạt động;
giao diện hiện đường dẫn tới bản đồ quy trình.

## Câu chuyện trình chiếu khoảng 90 giây

1. **Toàn cảnh — 15 giây.** Bấm **Bắt đầu câu chuyện**, rồi **Trình chiếu**.
   “Đây là kho kinh nghiệm từ nguồn Haas. Mỗi cụm chứa một quy trình cùng các bước,
   phát biểu, bằng chứng và phần còn thiếu.”
2. **Quyết định — 20 giây.** Bấm **Tiếp**. Tour chọn quan hệ thật của
   `REAL_WF_0003 · r2`: bước 3 tới bước 4, nhánh có điều kiện.
   “Tri thức giữ điều kiện chuyển sang xử lý thủ công, cùng căn cứ trong nguồn.”
3. **Bằng chứng — 20 giây.** Bấm **Tiếp**, rồi **Mở bằng chứng** trong bảng bên phải.
   “Người học có thể đối chiếu phát biểu với đúng đoạn nguồn và phiên bản.”
4. **Thu nhận kinh nghiệm — 20 giây.** Bấm **Tiếp**. Tour chọn câu hỏi lý do của bước 5.
   “Phần chưa được giải thích trở thành câu hỏi cụ thể. Chuyên gia bổ sung; phản hồi
   đi qua review và tạo phiên bản mới.” Liên kết mở form đúng workflow/bước/trường.
5. **Kiểm duyệt — 15 giây.** Bấm **Tiếp**. Đọc số phát biểu đã đối chiếu nguồn
   và đã xác nhận chuyên môn, nói rõ pilot chưa có xác nhận kỹ thuật.

Trong màn hình trình chiếu có nút **Câu chuyện** để bắt đầu tour. Tour được tạo từ
những bản ghi hiện có trong corpus; không dựng câu trả lời mới hoặc điền phần thiếu.

## Đồ thị được dựng từ đâu?

Trang đọc danh sách workflow từ `/v1/workflows`, sau đó tải các snapshot cùng
`mode`, `dataset_split` và `index_build_id`. Chỉ khi tải đủ các snapshot của index
đang chọn, không gian mới được hiển thị. Đổi corpus hủy tải cũ và xóa nội dung cũ.

`space-graph.js` tạo nút kho, workflow, step, claim, relation, evidence, source và
question còn mở. ID của thực thể trong workflow bao gồm corpus, workflow và revision.
Source được dùng chung khi có cùng `source_id` trong corpus.

Các đường nối dựa trên tham chiếu có sẵn:

- Kho chứa workflow; workflow chứa step và sử dụng source.
- Step tham chiếu claim theo trường tri thức.
- Relation nối hai step, có claim làm căn cứ và claim điều kiện.
- Claim nối evidence; evidence nối source và evidence gốc khi có.
- Step nối câu hỏi còn mở về trường thiếu.
- Conflict và supersedes chỉ nối khi cả hai claim có trong snapshot được hiển thị.

**Kho pilot hiện tạo 331 nút, 480 liên kết bản ghi/nguồn, gồm 3 quan hệ giữa bước.**
480 đường nối không phải 480 quan hệ kỹ thuật mới phát hiện. Các số này phụ thuộc
index; giao diện tính lại từ dữ liệu khi tải. Hai workflow cùng bài thay pocket;
số cụm không đại diện cho số tình huống độc lập.

Vị trí cụm, khoảng cách, màu và hạt nền phục vụ trình bày. Chúng không biểu thị độ
tương đồng, độ đúng kỹ thuật hay quan hệ nhân quả. Phần nối các thực thể kỹ thuật
xuyên quy trình vẫn là kế hoạch phát triển; trang 3D không thay đổi contract hoặc KB.

## Kiểm tra

Kiểm tra Edge chạy WebGL bằng SwiftShader trong profile tạm, localhost, model hỏi
đáp giả lập. Bao gồm số nút so với snapshot, quan hệ có căn cứ, chọn nút bằng raycast,
kéo xoay/zoom, mở evidence đúng revision, tìm kiếm, bộ lọc, tour, trình chiếu,
liên kết tới feedback, đổi corpus, bố cục mobile và fallback khi WebGL bị tắt.

```powershell
$env:KNOWFLOW_BROWSER_TEST='1'
.\.venv\Scripts\python.exe -m pytest tests/end_to_end/test_wp4_browser_ui.py -q
```

Kiểm tra xác nhận chức năng; chưa đo FPS trên thiết bị trình chiếu thực tế, hiệu quả
đào tạo hoặc lợi ích truy xuất. Ảnh và báo cáo nằm trong `out/`, không được commit.

Kết quả 2026-10-10: kiểm tra Edge nêu trên passed; 20 test API hiện có passed.
Ảnh local: [toàn cảnh](../out/a2_knowledge_space_preview.png),
[nhánh quyết định và bằng chứng](../out/a2_knowledge_space_branch_preview.png).
Báo cáo Edge: `out/a2_knowledge_space_browser.xml`.
