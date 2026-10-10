# Đường truy xuất trên đồ thị 3D

## Mở và trình diễn

Chuẩn bị database theo [hướng dẫn 3D](a2_knowledge_space_3d.md), chạy server với
`KNOWFLOW_RETRIEVAL_STRATEGY=lexical`, rồi mở `http://127.0.0.1:8000/space`.

1. Chọn **Đường truy xuất**, giữ câu hỏi mẫu **Nhánh phục hồi** và **Top 1**.
2. Bấm **Trình chiếu**, rồi **Chạy truy xuất**. Backend thực hiện một lượt tìm
   kiếm; đồ thị phát các sự kiện theo nhịp giãn để người xem quan sát được.
3. Đến **Theo quan hệ của bước**, tạm dừng. Mẫu này khớp bước 4 của
   `REAL_WF_0003 · r2`, rồi bổ sung bước 3 qua `branch_if`. Mở điều kiện và nguồn.
4. Tiếp tới **Kiểm tra bằng chứng** để thấy claim → evidence → source. Đọc các
   ứng viên đã mở được nguồn ở chặng cuối.
5. Có thể bật **Tạo câu trả lời AI sau truy xuất** và chạy lượt mới. Model soạn
   và kiểm tra trên chính kết quả của lượt đó. Chỉ sau các guard mới hiển thị câu
   trả lời/trích dẫn; các claim được trích dẫn giữ sáng ở trạng thái cuối.
6. Thử **Ngoài phạm vi** để thấy luồng dừng khi thiếu căn cứ. Các chặng khớp bước,
   mở rộng và trích dẫn không được thêm vào một lượt đã dừng sớm.

**Tạm dừng / ← / → / chọn chặng** đọc từng bước. **Phát lại** dùng sự kiện đã
nhận, không tìm lại và không gọi lại model. **Dừng lượt** hủy nhận dữ liệu và
dừng chuyển động; có thể đọc lại các chặng đã nhận. Tốc độ 1×/2×/4× chỉ điều chỉnh
nhịp trình chiếu. Thiết lập giảm chuyển động tắt các hạt chạy trên đường nối.

Lượt chỉ truy xuất với index lexical không cần Gemini key. Tùy chọn tạo câu trả
lời cần cấu hình model như [grounded QA](team2_grounded_qa.md). Vector/hybrid có
thể cần embedding/query translation theo cấu hình hiện có. Không tự đổi chiến
lược khi provider/index chưa sẵn sàng.

## Những gì người xem quan sát được

| Chặng | Sự kiện thực của hệ thống |
| --- | --- |
| Neo kho, kiểm tra ngữ cảnh/liên quan | Index đang dùng, filters và relevance gate của retriever |
| Chọn quy trình | Xếp hạng workflow thực; điểm xếp hạng không phải độ tin cậy kỹ thuật |
| Tìm bước/phát biểu | Kết quả top-k và claim vượt qua chính sách eligibility |
| Theo quan hệ | Bước được thêm qua requires/branch_if/corrects cùng điều kiện đã lưu |
| Kết quả và phần thiếu | Trạng thái retrieval, câu hỏi mở, mâu thuẫn nếu có |
| Kiểm tra bằng chứng | Đối chiếu snapshot và kiểm tra mở được evidence, riêng ứng viên/ngữ cảnh |
| Soạn/kiểm tra AI, trích dẫn | Thời điểm gọi draft/verify và các trích dẫn được guard chấp nhận |

Các sự kiện là telemetry của pipeline có thể quan sát. Chuyển động 3D mô phỏng
việc đi qua các liên kết để trình bày telemetry này. Suy nghĩ nội bộ của LLM không
được thu thập. Model generation hiện nhận evidence package có căn cứ; animation
không chứng minh model tự thực hiện tìm kiếm tự trị từng nút.

Mở rộng một tiên quyết có thể đi ngược hướng cạnh: bước 4 đang được tra cứu kéo
về điều kiện/bước 3. Hạt chuyển động thể hiện hướng **kiểm tra phụ thuộc**; hướng
và kiểu quan hệ trong KB giữ nguyên. Tất cả đoạn chuyển động phải có đường nối
thật giữa các đầu mút. Không nối vì hai bước gần nhau trong bố cục 3D.

**Top 1** là cấu hình của lượt trace để nhìn rõ bước khớp và phần được bổ sung;
có thể chọn Top 3/5. API hỏi đáp cũ giữ cấu hình hiện có. Thay đổi top-k sẽ tạo
một lượt truy xuất khác; không dùng số claim/đường nối làm điểm đánh giá hiệu quả.

Pilot hiện đối chiếu nguồn và xác nhận chuyên môn riêng; trace/semantic verifier
không tăng review flags hoặc chứng nhận an toàn thao tác trên máy.

## Triển khai và phạm vi

- `POST /v1/trace` nhận query theo contract hiện có, index của đồ thị, top-k từ
  1 đến 5 và tùy chọn generate. Trả NDJSON các sự kiện đã quan sát và kết quả cuối.
- Observer trong `retrieve` lấy trạng thái tại từng chặng. Không thay đổi kết quả
  truy xuất khi không có observer. Trace không ghi session hoặc KB.
- Mỗi sự kiện mang corpus/split/index. Bản không khớp đồ thị bị từ chối; backend
  kiểm tra index trước khi trả kết quả/trích dẫn. Đổi corpus/góc khám phá hủy
  stream và xóa nội dung, route, bộ đếm cùng timer cũ.
- Chỉ xuất các trường cho phép: refs, số lượng, score và trạng thái. Không xuất
  đường dẫn asset, raw source text, khóa API, prompt hoặc nội dung suy nghĩ model.
- Timeout/ngắt kết nối dừng quan sát. Một provider call đã bắt đầu có thể tiếp
  tục tới timeout của adapter; worker vẫn tính vào giới hạn job cho tới khi kết
  thúc. Hủy lượt không mở thêm generation sau các chặng đã bị hủy.
- Lỗi AI giữ các chặng truy xuất đã nhận và báo lỗi; không hiển thị câu trả lời
  hoặc trích dẫn giả. Khi WebGL không mở được, timeline và đọc bằng chứng vẫn dùng
  được; hạt chuyển động chỉ dành cho renderer 3D.

## Kiểm tra — 2026-10-10

33 test API/trace và 55 test truy xuất/mở rộng quan hệ passed. Edge localhost dùng
profile tạm, SwiftShader và model giả lập đã qua: stream thật, ánh xạ ID/cạnh,
hạt chuyển động, dừng/từng chặng/phát lại, trích dẫn đúng revision, mobile/fullscreen,
ngoài phạm vi và hủy stream khi đổi góc khám phá. Không gọi Gemini thật trong các
kiểm tra này; chưa đo hiệu quả trả lời hoặc hiệu quả đào tạo với người học.

Báo cáo local: `out/a2_route_api_tests.xml`, `out/a2_route_backend_tests.xml`
(lượt này 55 test truy xuất passed; test timeout trace đã sửa và qua ở báo cáo API),
`out/a2_route_browser_tests.xml`. Ảnh trình chiếu:
[đường truy xuất 3D](../out/a2_knowledge_space_route_preview.png). Artifact `out/`
không được commit.
