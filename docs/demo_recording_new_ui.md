# Kịch bản quay KnowFlow AI — hai giao diện sau PR #54

Thời lượng đề xuất: **5 phút 30 giây**. Một người thao tác, lời thuyết minh tiếng
Việt, phụ đề ngắn. Mã giao diện đối chiếu: `main@ca3b59a`.

Hai trang trong video:

- **Trang đọc và hỏi đáp:** `http://127.0.0.1:8000/`.
- **Không gian tri thức 3D:** `http://127.0.0.1:8000/space`.

## 1. Câu chuyện chính

**Một người bảo trì cần tìm lại kinh nghiệm về cụm thay dao: tìm thao tác, kiểm
nguồn, hiểu điều kiện áp dụng, và nhận ra phần vẫn cần hỏi người có chuyên môn.**

Đặt giá trị A2 vào những gì khán giả nhìn thấy: tri thức được tổ chức, mỗi phát
biểu truy được về nguồn, điều kiện được giữ riêng, phần thiếu có nơi thu thập
bổ sung, và mỗi lần sửa có lịch sử. Dùng graph làm cách giải thích cấu trúc và
đường truy xuất.

Kho demo hiện dùng nguồn công khai Haas. Hai trang chia sẻ cùng kho, không phải
hai sản phẩm riêng. Video không trình diễn bước tải video/trích xuất mới: quy
trình trong kho đã được xử lý trước.

## 2. Chuẩn bị khung hình

1. Mở hai tab theo thứ tự `/` rồi `/space`, tải lại bằng `Ctrl+F5` để nhận CSS/JS mới.
2. Chọn **Nguồn thực · dev** ở trang đọc và **Nguồn Haas · pilot** ở trang 3D.
3. Trang đọc: chọn **`B0_SRC_HAAS_0005 · r2`**, quy trình thay hốc dao.
4. Ô phạm vi hỏi đáp: **Haas / SMTC**, model máy để trống. Chọn quy trình ở thanh
   trên không tự giới hạn hỏi đáp vào workflow đó; bộ lọc thiết bị nằm trong form hỏi.
5. Trang 3D: kiểm tra **Tri thức thay đổi** đọc được **B0 r1 → r2**. Máy hiện tại
   đã mở được cả hai bản. Nếu máy quay khác thiếu index lịch sử, chuẩn bị theo
   [hướng dẫn 3D](a2_knowledge_space_3d.md), dùng database riêng.
6. Quay ở 1920×1080, con trỏ vừa đủ rõ. Giữ một mức zoom browser để chữ nguồn
   đọc được trong video; cuộn đến nội dung thay vì thu nhỏ toàn bộ trang.
7. Dùng `F11` để bỏ thanh browser khi bắt đầu cảnh. Trong trang 3D, bấm
   **Trình chiếu** để đồ thị và bảng giải thích chiếm khung hình.
8. Chuẩn bị sẵn ba câu hỏi ở mục 5 để dán; tránh gõ và sửa dài trong bản quay.
9. Chạy thử câu hỏi trước buổi quay bằng API thật, lưu thời điểm/cấu hình. Những
   kết quả benchmark cũ ở mục 5 là dữ liệu đối chiếu, không thay cho lượt chạy thử
   trên web. Key trong `.env`; không đưa cửa sổ IDE hoặc terminal vào video.

Giao diện đã mở thử để chốt kịch bản: chọn bước 6 và bằng chứng EV_033, xem graph
toàn cảnh, nhánh phục hồi 3 → 4 và so sánh B0 r1 → r2. Lượt xem UI không gọi model
sinh đáp án hoặc lưu phản hồi. Ảnh tham khảo local nằm ở `out/demo_plan/`.

## 3. Timeline bản quay chính

| Thời gian | Màn hình và thao tác | Nội dung khán giả cần thấy |
|---|---|---|
| 00:00–00:15 | `/space` → **Toàn cảnh** → **Trình chiếu**. Xoay nhẹ một lần, dừng ở góc dễ đọc. | Tên KnowFlow, các cụm quy trình, bộ đếm kho tri thức. |
| 00:15–00:40 | Chuyển sang `/`, giữ tên workflow B0 r2 và kho real/dev trong khung. | Vấn đề A2 và nguồn demo đã xử lý trước. |
| 00:40–01:10 | Tab **01 Bản đồ tri thức** → bước **6**. Cuộn tới bốn nhóm Làm gì / Khi nào / Vì sao / Kiểm chứng. | Tri thức có cấu trúc và phần chưa biết được giữ thiếu. |
| 01:10–01:45 | Tab **02 Hỏi theo tình huống** → hỏi câu A ở mục 5 → bấm citation. | Câu trả lời tiếng Việt và bằng chứng gốc ngay cạnh nhau. |
| 01:45–02:45 | `/space` → **04 Đường truy xuất** → câu A, **Top 5**, bật tạo câu trả lời AI → **Chạy truy xuất**. Dừng/xem từng chặng khi cần. | Ngữ cảnh, ứng viên, claim, nguồn và citation qua các sự kiện backend. |
| 02:45–03:15 | **02 Theo tình huống** → nhánh `REAL_WF_0003` automatic recovery thất bại → mở nguồn điều kiện. | Cạnh có điều kiện, bước 3 → 4; thao tác phụ thuộc tình huống trong nguồn. |
| 03:15–03:45 | Trở lại `/`, tab hỏi đáp → câu B ở mục 5. | Nguồn nói bôi mỡ nhưng không nêu loại mỡ; hệ thống có thể dừng vì thiếu căn cứ. |
| 03:45–04:15 | Chọn `REAL_WF_0003 · r2`, tab bản đồ → bước **5** → câu hỏi thiếu rationale → **Bổ sung cho câu hỏi này**. | Form gắn đúng workflow, bước, trường và câu hỏi; nơi thu thập lời người có chuyên môn. |
| 04:15–04:55 | `/space` → **03 Tri thức thay đổi** → B0 r1 → r2 → **Chỉ phần thay đổi** → nút claim thay đổi → nguồn trước/sau. | Nội dung claim còn đó, bằng chứng đã được sửa; revision cũ vẫn đọc được. |
| 04:55–05:15 | Thẻ kết quả tĩnh theo mục 6. | Có phép đo A/B/C, mẫu số rõ và giới hạn đã công bố. |
| 05:15–05:30 | Quay lại graph toàn cảnh, dừng chuyển động, để logo và thông điệp kết. | Ghi nhận → kiểm nguồn → sử dụng → bổ sung → theo dõi thay đổi. |

## 4. Thao tác và lời thuyết minh từng cảnh

### Cảnh mở — 00:00–00:15

**Thao tác:** cho graph xuất hiện trọn khung hình trước, xoay chậm trong khoảng
3–4 giây rồi bấm **Dừng xoay**. Không dành cả đoạn để bay quanh đồ thị.

**Nói:**

> “Đây là KnowFlow AI: kho kinh nghiệm kỹ thuật có bằng chứng. Mỗi cụm chứa một
> quy trình, các bước, phát biểu và nguồn để người sử dụng có thể kiểm lại.”

**Chữ trên video:** `KnowFlow AI · A2 · Kinh nghiệm có bằng chứng`.

### Từ video đến tri thức đọc được — 00:15–01:10

**Thao tác:** chọn B0 r2, bấm bước 6: *Inspect Components and Lubricate Pocket
Slider*. Cuộn xuống vùng chi tiết để thấy các nhóm tri thức và nhãn thiếu.
Chỉ một bước đủ để giải thích cấu trúc; không mở lần lượt cả chín bước.

**Nói:**

> “Kinh nghiệm bảo trì thường nằm trong video, hướng dẫn và lời người thực hiện.
> Khi cần một chi tiết, người mới phải tìm lại và kiểm xem nó áp dụng lúc nào.
> Trong pilot này, chúng tôi đã xử lý trước nguồn Haas thành kho tri thức.
> Một bước giữ riêng thao tác, điều kiện, lý do và bằng chứng. Phần nguồn không
> nêu vẫn được đánh dấu thiếu để tiếp tục thu thập.”

**Chữ trên video:** `Thao tác · Điều kiện · Lý do · Bằng chứng`.

Workflow B0 hiện hiển thị **9 bước, 0 quan hệ giữa bước, 47 trường thiếu/cần làm
rõ và 0 Question record mở**. Các trường thiếu chưa đều có câu hỏi thu thập.
Không đọc “0 câu hỏi mở” thành “đã biết hết”. Không gọi thứ tự hiển thị bước là
cạnh phụ thuộc: workflow này chưa có Relation giữa bước.

### Hỏi rồi kiểm nguồn — 01:10–01:45

**Thao tác:** tab **02 Hỏi theo tình huống**, dán câu A, bấm **Hỏi**. Khi có câu
trả lời, bấm citation dưới đáp án để bảng **Bằng chứng gốc** bên phải cập nhật.
Dừng hình 3–4 giây ở quote và timestamp.

**Nói:**

> “Tôi hỏi bằng tiếng Việt: bôi trơn con trượt của hốc dao như thế nào?
> Câu trả lời dẫn đến một phát biểu cụ thể. Bấm vào đây, tôi xem được đoạn gốc
> và thời điểm trong nguồn. Đã đối chiếu nguồn và được chuyên gia xác nhận kỹ
> thuật là hai trạng thái riêng.”

**Điểm đối chiếu đã mở được:** claim `B0_SRC_HAAS_0005_CL_020`, evidence `EV_033`,
**147,840–165,270 giây**, quote có đoạn “with the pocket slider we'll apply some
grease”. Hiện là `source_checked / not_requested`. Chọn citation thực của lượt
quay; nếu model dùng claim khác, mở đúng citation đó, không đổi nguồn để khớp
kịch bản. Tab **03 Chi tiết & nguồn** có thể mở cùng claim nếu cần một cảnh đọc
nguồn độc lập; khi đó giới thiệu đúng là nguồn của claim đang duyệt.

### Quan sát đường truy xuất — 01:45–02:45

**Thao tác:** sang `/space`, chọn **04 Đường truy xuất**, dán câu A.
Chọn **Top 5** và bật **Tạo câu trả lời AI sau truy xuất**. Bấm **Chạy truy xuất**.
Nhịp **2×** phù hợp để xem trọn lượt; chọn lại từng chặng để giải thích.

Giữ hai thời điểm trên khung hình:

1. Chặng **Kiểm tra bằng chứng**: các liên kết claim → evidence → source.
2. Câu trả lời/citation cuối, nếu lượt đó vượt qua các kiểm tra.

**Nói:**

> “Ở đây chúng tôi trình bày những chặng truy xuất có thể quan sát: kiểm phạm vi,
> chọn ứng viên, tìm phát biểu và mở nguồn. Nút sáng lấy từ sự kiện backend;
> chuyển động được giãn để người xem theo dõi. AI tạo câu trả lời từ gói bằng
> chứng của lượt này, và citation được kiểm trước khi hiển thị.”

**Chữ trên video:** `Trace backend thật · Chuyển động phục vụ trình bày`.

Đây là **lượt truy xuất mới**, không mặc định là phát lại câu trả lời ở trang
trước. Trang 3D không có đầy đủ form phạm vi giống trang đọc; Top 5 cũng là thiết
lập riêng của trace. Không khẳng định hai lượt có ứng viên hoàn toàn giống nhau.
Nếu không có bước bổ sung theo cạnh, giữ nguyên thông báo đó. Với B0, đường
claim/evidence/source đã thể hiện được truy xuất; phần cạnh có điều kiện được
minh họa ở cảnh tiếp theo.

**Phát lại** dùng các sự kiện đã nhận, không gọi lại model. Nếu dùng để quay
lại góc đẹp, ghi rõ `Phát lại trace của lượt vừa thực hiện`. Không giới thiệu
animation là suy nghĩ nội bộ hoặc khả năng model tự đi tìm từng nút.

### Điều kiện khiến quy trình đổi nhánh — 02:45–03:15

**Thao tác:** chọn **02 Theo tình huống**, chọn lựa chọn bắt đầu bằng
`REAL_WF_0003` nói về automatic recovery không thành công. Bấm **Xem đường tri
thức**, chọn điều kiện và **Mở bằng chứng** ở bảng phải.

**Nói:**

> “Kinh nghiệm còn chứa điều kiện để chuyển cách xử lý. Ví dụ ở quy trình phục
> hồi cụm thay dao, nguồn mô tả chuyển sang nhánh thủ công khi phục hồi tự động
> không thành công. Điều kiện, căn cứ và hai bước liên quan được lưu cùng nhau,
> và tôi có thể mở nguồn của chính điều kiện này.”

**Phải thấy:** `REAL_WF_0003 · r2`, quan hệ `branch_if`, bước **3 → 4**. Đây là
nhánh trong nguồn, không phải hệ thống đã đọc telemetry máy và xác định tình
trạng thực tế. Cạnh có điều kiện khác các liên kết bản ghi/bằng chứng của graph.

### Câu hỏi nguồn chưa trả lời được — 03:15–03:45

**Thao tác:** trở lại trang đọc, dán câu B, giữ Haas/SMTC và model trống.
Để thông báo thiếu bằng chứng hiện rõ.

**Nói:**

> “Tiếp theo tôi hỏi loại mỡ nên dùng. Nguồn vừa rồi nói thao tác bôi mỡ nhưng
> không cho thông số loại mỡ. Nếu chưa đủ bằng chứng, hệ thống giữ phần này là
> chưa biết. Đây là phần kinh nghiệm cần tiếp tục hỏi người có chuyên môn.”

**Chữ trên video:** `Có thao tác bôi mỡ ≠ Có thông số loại mỡ`.

Không nói “không có dữ liệu gì”: có nguồn liên quan nhưng nguồn không đủ trả
lời câu hỏi cụ thể. Nếu AI trả lời khác kỳ vọng, kiểm citation và ghi nhận
kết quả thật; không đổi gold hay ghép một đáp án đã lưu thành đáp án live.

### Nơi thu thập phần kinh nghiệm còn thiếu — 03:45–04:15

**Thao tác:** chọn `REAL_WF_0003 · r2`, tab **01 Bản đồ tri thức**, bước **5**.
Tìm câu hỏi lý do phải bỏ dụng cụ khỏi tay đôi trước khi đưa về vị trí gốc.
Bấm **Bổ sung cho câu hỏi này**; UI tự chuyển sang **04 Bổ sung phần thiếu**.
Cho người xem thấy câu hỏi, bước và trường `rationale` đã được điền đúng.

**Nói:**

> “Đây là một câu hỏi còn mở khác đã được ghi trong kho. Người có chuyên môn
> có nơi bổ sung lời giải thích, gắn đúng bước và đúng câu hỏi. Phản hồi có
> trạng thái review riêng trước khi trở thành căn cứ trả lời.”

**Phải thấy:** `REAL_WF_0003_Q_001`, `ST_005`, `rationale`. B0 không có Question
record mở cho loại mỡ; đừng dựng cảnh click một câu hỏi không tồn tại ở B0.

Bản quay chính dừng ở form thu thập nếu chưa có lời phản hồi thật. Không soạn
thay một lý do kỹ thuật rồi gắn danh nghĩa chuyên gia. **Xem trước** hoặc **Lưu**
chỉ thêm vào cảnh nếu đã chuẩn bị nguyên văn phản hồi và danh tính/vai trò thật
theo mục 7. Form hiện chưa xác thực danh tính người trả lời.

### Một thay đổi vẫn truy được về hai phiên bản — 04:15–04:55

**Thao tác:** `/space` → **03 Tri thức thay đổi** → chọn B0 r1 → r2 → đánh dấu
**Chỉ phần thay đổi**. Chọn claim thay đổi, mở nguồn **Bản trước / Bản sau**.
Có thể kết hợp tab **05 Lịch sử revision** ở trang đọc nếu cần xem nhật ký;
giữ cảnh so sánh 3D làm phần chính.

**Nói:**

> “Tri thức cũng cần được sửa và kiểm lại. Ở lịch sử đã có này, phát biểu bôi
> trơn được giữ, nhưng liên kết bằng chứng được chỉnh sang đoạn phù hợp.
> Tôi xem được nguồn trước và sau; citation vẫn gắn với phiên bản cụ thể.
> Đây là cơ sở để theo dõi chất lượng kho khi kinh nghiệm được bổ sung.”

**Phải thấy:** `CL_020`, link `EV_019 → EV_033`, r1 → r2. Graph local hiện báo
**1 nút thêm, 1 nút đổi, 0 bỏ**; đây là số nút của phép so sánh, không phải số
tri thức đã được chuyên gia duyệt. Revision này **đã tồn tại**, không được mô
tả là kết quả của form chưa lưu ở cảnh trước.

### Kết quả và kết — 04:55–05:30

**Thao tác:** chèn thẻ số liệu theo mục 6, rồi về graph toàn cảnh, dừng xoay.

**Nói:**

> “Chúng tôi đã chạy 81 câu qua API thật ở ba cấu hình đối chứng, giữ cả lỗi
> và các trường hợp từ chối. KnowFlow đạt Recall@5 96,15% trên 52 câu có gold
> bước. Đây là kết quả truy xuất; chất lượng hỗ trợ về nghĩa còn cần chấm
> độc lập, và lượt đo chưa chứng minh graph vượt RAG.
>
> Mục tiêu của KnowFlow là tích lũy kinh nghiệm có nguồn, có điều kiện và có
> lịch sử, để người tiếp theo có thể tìm, kiểm và tiếp tục bổ sung.”

**Chữ kết:** `Ghi nhận → Kiểm nguồn → Sử dụng → Bổ sung → Theo dõi thay đổi`.

## 5. Ba câu hỏi để sao chép

### A — cảnh hỏi đáp và trace chính

```text
Bôi trơn con trượt của hốc dao trước khi lắp như thế nào?
```

Q001 trong benchmark 20261012: A trả `answered`, citation `CL_020 / EV_033`, B0
r2. Đây là dữ liệu đã có để chọn ca trình diễn; một lượt model mới vẫn có thể khác.

### B — cảnh nguồn không đủ thông số

```text
Nên dùng loại mỡ bôi trơn nào cho con trượt hốc dao?
```

Q031 trong benchmark: A/B/C đều trả `insufficient_evidence`; A/C chọn B0 r2.
Không dùng Q015 “bằng gì” thay câu hỏi A: Q015 còn bị từ chối oan ở tầng draft.

### C — nhánh phụ nếu muốn quay thêm đoạn điều kiện/trace

```text
What should I do if automatic recovery fails?
```

Câu mẫu **Nhánh phục hồi** của `/space`. **Top 1** dùng để quan sát rõ bước khớp
và bước bổ sung theo quan hệ. Câu này nằm trong kịch bản trace cũ, không phải
số đo đáp án của bộ benchmark 81 câu; chỉ dùng cảnh hỏi AI sau khi đã chạy thử.
Xem [cách hoạt động trace](a2_knowledge_space_3d.md#đường-truy-xuất).

## 6. Thẻ kết quả cuối video

Nội dung chính trên một thẻ, khoảng 20 giây:

```text
KnowFlow AI — Pilot trên nguồn Haas

9 workflow · 67 bước · 303 phát biểu
81 câu × 3 cấu hình · API thật · 243 lượt đã ghi nhận
KnowFlow Recall@5: 96,15% — n=52 câu answered/detail có gold bước
Status khớp nhãn: A / B / C đều 67/81

Real/dev; giữ nguyên nhãn hiện có.
20 nhãn phủ định chờ quyết định review trên corpus mở rộng.
Chấm nghĩa: chưa có người chấm. Chưa chứng minh graph vượt RAG.
```

Lời thuyết minh không cần đọc hết footnote; phụ đề phải còn đủ thời gian để đọc.
Gắn link báo cáo ở mô tả video hoặc màn kết:

[Báo cáo trên main](https://github.com/duy32123/denso-hackathon/blob/main/benchmarks/results/20261012_expanded_dev/REPORT.md).

Nếu thêm thẻ chi phí ở bản dài: known subtotal toàn thí nghiệm **$0,976087**,
đầy đủ/hóa đơn **null**; thiếu usage/giá embedding và usage của lần lỗi. Chưa
gồm hosting/công chuyên gia. Không dùng subtotal làm tổng phí sản phẩm.

Chi tiết phạm vi graph đã mở trên máy: **775 nút, 1178 liên kết bản ghi/nguồn,
15 Relation giữa bước**, 334 Evidence record, 36 Question mở. Không gọi toàn
bộ 1178 liên kết là quan hệ kỹ thuật suy ra tự động. Chọn 9 workflow/67 bước/
303 claim làm số chính; các số node/link là cấu trúc hiển thị.

## 7. Đoạn lưu phản hồi thật — tùy chọn cho bản dài

Chỉ dùng nếu nhóm có nguyên văn phản hồi thật cho câu hỏi đã chọn. Quay trên bản
sao dự án/database dành cho demo vì service ghi sẽ tạo file revision và phản hồi.

1. Ghi người trả lời, tên hiển thị và vai trò thật; không tự nhận chuyên gia DENSO.
2. Nhập nguyên văn, bấm **Xem trước thay đổi**. Quay rõ claim mới còn `pending`.
3. Bấm **Lưu revision mới** khi service thật sẵn sàng. Chỉ nói đã lưu sau khi UI
   có kết quả thành công; không dùng stub làm cảnh ghi thật.
4. Lưu kết quả revision/source ID; import và dựng lại index trên bản demo để
   trang đọc/3D thấy bản mới. Đoạn chờ được rút ngắn có nhãn biên tập.
5. Giới thiệu đúng: có revision mới, nhưng phản hồi chưa review không được tự
   nâng thành tri thức kỹ thuật đã xác nhận hoặc đáp án mới đã đáng tin.

Luồng duyệt nguồn cho snapshot sinh từ feedback chưa được xác nhận đầy đủ ở
kịch bản này. Không viết cảnh “lưu lời chuyên gia → AI lập tức học và trả lời
đúng” nếu chưa kiểm chứng đoạn đó. Cảnh lịch sử B0 r1 → r2 vẫn dùng được độc lập
và không được nhận là lịch sử do lần feedback này tạo ra.

## 8. Nhịp quay và biên tập

- Dùng chuyển cảnh theo nhiệm vụ: “Tìm thao tác”, “Kiểm nguồn”, “Xem trace”,
  “Điều kiện”, “Phần thiếu”, “Lịch sử”. Không dựng thành chuyến tham quan menu.
- Một lần click → giữ khung 2–4 giây để người xem đọc. Trỏ chuột vào nội dung
  đang nói, rồi đưa ra vùng trống. Giữ quote/timestamp đủ lớn.
- Cảnh graph: góc toàn cảnh ngắn, sau đó tập trung một đường hoặc nhánh.
  Dừng xoay khi đọc nguồn. Không đánh giá chất lượng từ số hạt hoặc khoảng cách nút.
- Có thể rút ngắn thời gian nhập/chờ API. Gắn nhãn `Đã rút ngắn thời gian chờ`;
  không giới thiệu thời lượng clip cắt là latency thực.
- Nếu 429/timeout xuất hiện: giữ bản ghi gốc. Có thể quay lại một take khác,
  nhưng video demo là take trình diễn được chọn, không thay bất kỳ kết quả
  benchmark nào. Nếu dùng ảnh/kết quả lưu sẵn, ghi rõ `Kết quả đã ghi trước`.
- Nếu chỉ truy xuất mà không bật tạo câu trả lời AI: nói “tìm nguồn”, không
  nói đã có câu trả lời model trong lượt đó.
- Dùng phụ đề tiếng Việt cho source tiếng Anh. Phụ đề diễn giải không thay
  quote gốc trên UI hoặc được coi là nhãn do người kiểm.

## 9. Bản rút gọn 3 phút

| Thời gian | Cảnh |
|---|---|
| 00:00–00:20 | Graph mở + vấn đề A2, nguồn Haas đã xử lý trước. |
| 00:20–01:00 | Trang đọc: câu A → citation → quote/timestamp. |
| 01:00–01:45 | 3D trace: câu A → nguồn → đáp án, nêu rõ telemetry backend. |
| 01:45–02:05 | Một nhánh có điều kiện thật, 3 → 4. |
| 02:05–02:30 | Câu B thiếu thông số; form câu hỏi mở nếu đủ thời gian. |
| 02:30–02:45 | Revision B0 r1 → r2, hai nguồn. |
| 02:45–03:00 | Số liệu có phạm vi + câu kết. |

## 10. Tình trạng kiểm tra trước khi quay

- [x] Main mới sau PR #54; các nhãn tab và màu giao diện đã đối chiếu bằng browser.
- [x] Hai trang local trả HTTP 200, kho 9 workflow đã tải được.
- [x] B0 r2 bước 6, CL_020/EV_033 và timestamp đã mở được.
- [x] Nhánh WF_0003 3 → 4 và lịch sử B0 r1 → r2 đã mở được.
- [x] Ca A/B có đầu ra API thật lưu trong benchmark cũ; số liệu kết dựa trên báo cáo đó.
- [ ] Chạy thử hỏi đáp/trace qua giao diện với API thật vào ngày quay; ghi nhận kết quả.
- [ ] Thu tiếng, kiểm cỡ chữ/khung hình và xem lại file video xuất.
- [ ] Nếu thêm cảnh lưu: chuẩn bị lời phản hồi thật và kiểm luồng trên bản demo riêng.

Kịch bản này chưa phải video đã quay và chưa xác nhận mọi kết quả AI live của
buổi quay. [Báo cáo benchmark](../benchmarks/results/20261012_expanded_dev/REPORT.md)
và [phiếu chấm nghĩa](../benchmarks/results/20261012_expanded_dev/human_review.csv)
giữ vai trò riêng với video trình diễn.
