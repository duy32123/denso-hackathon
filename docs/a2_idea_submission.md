# KnowFlow AI — ý tưởng A2 và phạm vi demo

Chủ đề duy nhất: **A2 — Accumulate Master Know-How for AI to Learn**.

Tên ý tưởng: **KnowFlow AI — Xây dựng đồ thị tri thức kinh nghiệm chuyên gia từ video thao tác**.

Thông điệp: **Chuyển kinh nghiệm thành bộ nhớ tri thức dùng chung, giúp người học hiểu làm gì, khi nào, vì sao và kiểm chứng bằng gì.**

## 1. Vấn đề nhận thấy

Trong vận hành và bảo trì, người có kinh nghiệm nhận biết dấu hiệu bất thường, lựa chọn
thao tác theo tình trạng máy và điều chỉnh cách xử lý khi gặp ngoại lệ. Video lưu lại
quá trình thực hiện; tài liệu mô tả hướng dẫn. Phần lý do quyết định, điều kiện áp dụng
và tiêu chí xác nhận kết quả có thể còn nằm trong lời giải thích hoặc trao đổi cá nhân.

Người mới phải tìm nhiều nguồn, tự đối chiếu thiết bị và hỏi lại khi chưa rõ. Đơn vị
quản lý cũng khó biết kinh nghiệm nào đã được ghi nhận, nội dung nào còn thiếu và
phần nào cần cập nhật. Đây là giả thuyết nhu cầu cần xác minh với người dùng tại doanh
nghiệp; pilot hiện tại dùng nguồn kỹ thuật công khai Haas.

Bài toán đề xuất là **lưu giữ và chuyển giao kinh nghiệm bằng các bước, điều kiện,
lý do, quan hệ và bằng chứng có thể kiểm tra**, rồi tiếp tục thu thập phần còn thiếu.

## 2. Giải pháp đề xuất

KnowFlow AI xây dựng đồ thị tri thức quy trình từ video, tài liệu và phản hồi của
người có chuyên môn. Các bước liên kết với phát biểu về thao tác, dấu hiệu, điều kiện,
lý do và kết quả. Quan hệ giữa bước biểu diễn thứ tự được quan sát, điều kiện tiên
quyết, nhánh xử lý, lần lặp và đính chính khi nguồn có căn cứ.

Mỗi phát biểu và quan hệ dẫn tới đoạn lời nói có timestamp, khung hình hoặc đoạn tài
liệu. Người dùng có thể tìm theo tình huống và mở nguồn để đối chiếu. Phần chưa được
nguồn giải thích được giữ thành khoảng trống, gắn câu hỏi để thu thập bổ sung. Phản
hồi đi qua review và tạo phiên bản mới trước khi được dùng để trả lời.

**Mục đích:** lưu giữ kinh nghiệm, hỗ trợ đào tạo người mới, giảm công tìm và đối
chiếu nguồn, tập trung thời gian người có chuyên môn vào các câu hỏi cụ thể, và tạo
nền tảng tri thức tiếp tục được cập nhật.

**Công nghệ:** AI xử lý lời nói/hình ảnh/văn bản; LLM đề xuất claim và bước; đồ thị
quan hệ quy trình; truy xuất từ khóa và embedding kết hợp ngữ cảnh quan hệ; validator,
review, snapshot bất biến; giao diện web xem nguồn và bổ sung kinh nghiệm.

MVP dùng SQLite cho kho truy xuất local. Mở rộng hạ tầng và đồ thị thực thể xuyên
quy trình được lựa chọn sau khi đo nhu cầu pilot; cấu trúc hiện tại đã giữ ID, revision,
quan hệ và nguồn để hỗ trợ bước phát triển này.

**Đầu vào:** video thao tác, tài liệu bảo trì, metadata thiết bị, phản hồi nguyên văn
và quyết định review. Nguồn đầu tiên là Haas; pilot doanh nghiệp cần dữ liệu được phép
khai thác và người có chuyên môn tham gia.

**Đầu ra:** bản đồ bước/quan hệ có nguồn; câu trả lời theo tình huống kèm phạm vi áp
dụng; câu hỏi bổ sung; kho tri thức có trạng thái review và lịch sử. Tình huống kiểm
tra kiến thức cho đào tạo là phần dự kiến trong pilot tiếp theo.

## 3. Quy trình trước và sau cải tiến

**Trước:** tìm video/tài liệu → xem nhiều đoạn → tự đối chiếu điều kiện → hỏi người
có kinh nghiệm → phần giải thích có thể tiếp tục nằm trong trao đổi cá nhân.

**Sau:** thu thập nguồn → AI đề xuất bước/claim/quan hệ → gắn bằng chứng → người kiểm
đối chiếu → khai thác bằng bản đồ và hỏi đáp → ghi câu hỏi thiếu → tiếp nhận phản hồi
→ review → tạo revision → cập nhật chỉ mục → tiếp tục tái sử dụng.

Thứ tự xuất hiện không tự chứng minh điều kiện tiên quyết. Mâu thuẫn, phạm vi chưa rõ
và phần thiếu được giữ để kiểm tra. Khi bổ sung phản hồi, revision đầu chứa claim
pending; review tạo revision kế tiếp. Nội dung được review vẫn giữ phạm vi của nguồn.

## 4. Hiệu quả hướng tới và cách đo

- Chuyển giao được cả thao tác và lý do lựa chọn trong phạm vi có bằng chứng.
- Tìm hướng dẫn theo thiết bị, dấu hiệu và điều kiện, mở được đúng nguồn.
- Thu thập kinh nghiệm có mục tiêu qua những câu hỏi còn thiếu.
- Tích lũy tri thức có lịch sử, đo được công sức review và cập nhật.

Pilot so sánh ba cách trên cùng nhiệm vụ: tra cứu video/tài liệu thông thường;
baseline RAG trên transcript; KnowFlow với claim, quan hệ và vòng bổ sung.
Đo thời gian tìm **đáp án đúng**, độ phủ trả lời, chất lượng citation, xử lý thiếu thông
tin, thời gian review và chi phí. Tách đầu ra tự động trước review và sau review.

**Bằng chứng hiện có:** bundle dev có 3 video và 2 tài liệu Haas; latest active gồm
4 workflow, 38 bước, 134 claim, 10 câu hỏi mở. Hai workflow cùng bài thay pocket,
nên số này không đại diện cho 4 tình huống độc lập. Toàn bộ technical_review hiện là
not_requested. Báo cáo 66 câu có người chấm thuộc một phiên bản trước các sửa mới nhất:
49/66 đúng trạng thái, trả lời 24/41 câu có thể trả lời, 35/40 citation đúng. Xem
[báo cáo gốc và giới hạn](retrieval_eval_real_dev.md#tầng-câu-trả-lời-có-human-verdict--2026-09-24).

Các mức giảm thời gian hoặc công sức là mục tiêu thử nghiệm; chưa có số đo để đưa
thành kết quả đạt được. Bản đồ mới là phần trình bày tri thức; lợi ích truy xuất của
đồ thị cần được đánh giá qua baseline và ablation trong pilot.

## 5. Giá trị khác biệt của ý tưởng

**Quan hệ có căn cứ:** thao tác gắn với điều kiện, nhánh xử lý và kết quả, cùng
phát biểu giải thích quan hệ để người duyệt kiểm tra.

**Bằng chứng theo từng phát biểu:** người học mở được câu nói, khung hình hoặc đoạn
tài liệu hỗ trợ đúng nội dung đang xem.

**Khoảng trống tạo vòng thu thập kinh nghiệm:** phần chưa biết chuyển thành câu hỏi
gắn bước và trường thiếu; phản hồi trở thành nguồn mới có thể tiếp tục review.

**Cập nhật có lịch sử và phạm vi:** tri thức mới giữ người cung cấp, revision, trạng
thái review và giới hạn thiết bị. Người dùng xem lại bản cũ và phần đã đính chính.

Đồ thị và RAG là công nghệ nền đã có nghiên cứu. Phần ứng dụng nhóm phát triển là vòng
thu nhận kinh nghiệm bảo trì có căn cứ, thu thập phần thiếu và cập nhật có kiểm duyệt.
Hướng tham khảo về đồ thị và truy xuất video đa phương thức là
[VideoRAG của Ren và cộng sự](https://arxiv.org/abs/2502.01549), với
[mã nghiên cứu HKUDS](https://github.com/HKUDS/VideoRAG). Tên VideoRAG được dùng cho
nhiều công trình; hai link này xác định cụ thể công trình tham khảo. MVP hiện tại dùng
pipeline riêng của KnowFlow; mức cải thiện của VideoRAG không phải kết quả của nhóm.

## 6. Kế hoạch sáu tuần từ MVP hiện có

Lịch bắt đầu khi đã chốt phạm vi, quyền khai thác dữ liệu và người kiểm chuyên môn.

| Tuần | Công việc | Đầu ra kiểm được |
|---|---|---|
| 1 | Chọn một nhóm thiết bị, khảo sát người dùng và thu nguồn | Tình huống, tiêu chí nguồn, người review, nhiệm vụ đánh giá |
| 2 | Chuẩn hóa claim/quan hệ; mở rộng đồ thị theo nguồn | Bản đồ cùng bằng chứng; log missing/conflict và đối chiếu mẫu |
| 3 | Hoàn thiện vòng hỏi–phản hồi–review–revision | Một ca trọn vòng và thời gian cập nhật; lịch sử còn mở được |
| 4 | Đánh giá truy xuất có quan hệ so với transcript RAG | Bộ câu hỏi, raw output, cấu hình và kết quả từng baseline |
| 5 | Dùng thử trên các nhiệm vụ tương đương | Thời gian tìm đúng, chất lượng, công review và chi phí |
| 6 | Sửa lỗi, diễn tập và tổng hợp | Demo, báo cáo kết quả/giới hạn và kế hoạch mở rộng |

Sau pilot, mở rộng nguồn/quy trình và phân quyền theo nhu cầu doanh nghiệp. Đồ thị
liên kết thực thể giữa nhiều workflow cần contract, đối chiếu phạm vi và đánh giá riêng.

## Phạm vi dùng trong hồ sơ và demo

| Nội dung | Trạng thái có thể trình bày |
|---|---|
| Claim/evidence, bảy trường tri thức, review, snapshot, hỏi đáp, lịch sử | Có trong MVP |
| Bản đồ Step–Relation và bốn nhóm làm gì/khi nào/vì sao/kiểm chứng | Đã bổ sung vào giao diện từ snapshot thật, xem [kịch bản](a2_knowledge_map_demo.md) |
| Không gian 3D liên kết quy trình/bước/phát biểu/bằng chứng/câu hỏi | Có trong demo; tìm, chọn nút, mở nguồn và tour trình chiếu, xem [phạm vi](a2_knowledge_space_3d.md) |
| Khám phá tình huống và đối chiếu phiên bản trong 3D | Có trong demo; đường nhánh từ Relation đã lưu, diff theo ID, bằng chứng đúng revision/index; ví dụ lịch sử sửa căn cứ nguồn, chưa phải kinh nghiệm mới từ chuyên gia |
| Trình diễn đường truy xuất và trích dẫn trên đồ thị | Có trong demo; telemetry thực từ retriever, chuyển động trình chiếu, top-k và phần mở rộng rõ ràng; AI dùng chính evidence package của lượt đó, không hiển thị suy nghĩ nội bộ LLM |
| Chọn câu hỏi thiếu để mở form bổ sung đúng bước/trường | Có trong giao diện; lưu đi qua service feedback hiện có |
| Truy xuất lexical/vector/hybrid và mở rộng ngữ cảnh qua requires/branch_if/corrects | Có trong retrieval hiện tại; vẫn trong một workflow/revision |
| Đồ thị thực thể thiết bị/công cụ và liên kết xuyên workflow | Hướng phát triển, cần review/migration và đo riêng |
| Tự động hiểu toàn bộ video, xác nhận kỹ thuật, giảm thời gian/downtime tại DENSO | Chưa có bằng chứng để khẳng định |
| Bộ kiểm tra năng lực học viên và triển khai doanh nghiệp | Đầu ra đề xuất sau pilot |

Nội dung trên có thể điền vào các mục tương ứng của PPTX BTC. Hồ sơ đội thi, thông
tin liên hệ và tình trạng thương mại hóa cần thành viên cung cấp theo thực tế.
