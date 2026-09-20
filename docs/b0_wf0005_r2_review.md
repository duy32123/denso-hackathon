# B0_SRC_HAAS_0005 r2 — đã review, promote và kiểm thử live

Ngày chuẩn bị: 2026-09-15. Người soạn bản sửa: `codex` (AI), **không phải người source-review**.

## Trạng thái

- Draft: [B0_SRC_HAAS_0005.r2.draft.json](../acquisition/extraction/drafts/B0_SRC_HAAS_0005.r2.draft.json).
- Snapshot nháp đã compile: [B0_SRC_HAAS_0005.r2.json](../data/workflows/drafts/B0_SRC_HAAS_0005.r2.json).
- Phiếu Excel/CSV local: `acquisition/extraction/reviews/B0_SRC_HAAS_0005.r2.sheet.csv` (gitignored).
- Người kiểm `duy32123` xác nhận đã kiểm xong, bao gồm claim bôi mỡ và `CL_033`.
  Đã ghi [review r2](../acquisition/extraction/reviews/B0_SRC_HAAS_0005.r2.review.json):
  **33/33 source_checked, 0 pending/rejected/stale**; technical review vẫn `not_requested`.
- `CL_033` đã được người kiểm điền nhưng lệch sang cột cuối CSV. Do file gốc đang bị khóa,
  giữ nguyên file đó và dùng bản local `B0_SRC_HAAS_0005.r2.normalized.sheet.csv` để đưa
  quyết định về đúng cột; note ghi rõ việc chuẩn hóa. Không tự source-review thay người kiểm.
- Đã promote [snapshot dev r2](../data/workflows/dev/B0_SRC_HAAS_0005.r2.json), export và validate
  bundle `BUNDLE_HAAS_SMTC_DEV_4d433ec6bd90`: 5 sources, 5 snapshots (4 workflow ID),
  47 steps, 167 claims, 168 evidence. Snapshot nháp vẫn pending; bản dev có review events.
- Đã import và build Gemini sau khi người dùng cho phép rõ việc gửi search text tới Gemini.
  Index: `IDX_SEARCH_aca88334c758fbdfe8b092c513ffe7d9ef4a4d3dc93e163f783b32f14135f6ae`.
- Live smoke: **2 passed**. Câu bôi trơn trả `answered` với citation source_checked mở được;
  câu loại mỡ/NLGI trả `insufficient_evidence`. Report local: `out/eval/qa_live_smoke_r2.xml`.
  Đây là hai smoke test qua HTTP facade với Gemini thật, không phải benchmark hay browser test.
- R1 và review r1 vẫn nguyên trạng; không nới citation guard. Giữ cả B0 và REAL trong corpus.
- Hồi quy offline sau cập nhật: **462 passed** (loại riêng file live đã chạy ở trên).
  Test importer đếm latest-active thay vì cộng cả các revision lịch sử; validator không bị nới.
- Gold retrieval của 31 câu trỏ B0 r1 đã chuyển ref sang r2 sau khi kiểm Step/Claim/context
  không đổi. Nhãn kỳ vọng và Step ID giữ nguyên; các câu đó về `draft` để kiểm gold cho r2.
  Xác nhận nguồn của `duy32123` không được dùng làm xác nhận nhãn gold.

## Thay đổi cần kiểm

Chỉ `B0_SRC_HAAS_0005_CL_020` đổi fingerprint nội dung review. Nội dung claim giữ nguyên:
`Apply grease to the pocket slider.`

R1 liên kết `EV_019`, chỉ có cue `SRC_HAAS_0005:U0020`, 147840–153660 ms.
Quote dừng ở `we'll apply some`, thiếu từ chỉ vật liệu bôi trơn.

R2 liên kết **`B0_SRC_HAAS_0005_EV_033`**, ghép hai cue raw liên tiếp `U0020` và `U0021`,
147840–165270 ms (**2:27.840–2:45.270**). Quote là nguyên văn hai cue, có đoạn
`we'll apply some grease in there`. Không thêm loại mỡ, cấp NLGI, lượng mỡ hoặc yêu cầu kỹ thuật.

Compiler giữ nguyên toàn bộ 32 evidence r1, kể cả `EV_019` nay không được claim này dùng;
thêm `EV_033`, ghi `change_log.id_mapping: EV_019 -> EV_033`. ID Step/Claim và nội dung
32 claim còn lại không thay đổi. Không sửa quote/locator dưới ID cũ.

## Quy trình review đã sử dụng (tham khảo)

Lượt review này đã ghi và promote xong. Không chạy lại `apply` chỉ để xác nhận trạng thái;
dùng `status` để tránh tạo thêm session trùng. Phần dưới mô tả cách kiểm cho lần sau.

1. Mở CSV bằng Excel, bật Wrap Text. Tìm `B0_SRC_HAAS_0005_CL_020`, field `action`, Step 6.
2. Mở URL ở cột `watch`; nghe/đọc toàn bộ đoạn 2:27.840–2:45.270 và ngữ cảnh xung quanh.
   Kiểm tra rằng lời nói thực sự hỗ trợ bôi mỡ vào pocket slider, không chỉ một bộ phận khác.
   Nếu nguồn không đủ rõ, để pending hoặc chọn rejected kèm lý do; không xác nhận chỉ vì compiler pass.
3. Đối chiếu 32 claim còn lại với review r1 và nguồn. Có thể dùng review cũ làm tài liệu
   đối chiếu phần không đổi; hệ thống hiện lưu quyết định theo revision nên vẫn cần xác nhận
   của người kiểm cho r2, không tự sao chép chữ ký review r1.
4. Điền `decision` bằng **`source_checked`** hoặc **`rejected`**; rejected bắt buộc có `note`.
   Chưa kiểm thì để trống. Đây là sheet claim-review, không dùng `ok/fix/drop` của sheet eval.
   `source_checked` chỉ xác nhận đúng nguồn, không thay thế xác nhận kỹ thuật của chuyên gia.
5. Lưu CSV rồi ghi quyết định bằng danh tính thật của người kiểm:

```powershell
$draftPath = "acquisition/extraction/drafts/B0_SRC_HAAS_0005.r2.draft.json"
$sheetPath = "acquisition/extraction/reviews/B0_SRC_HAAS_0005.r2.sheet.csv"
.\.venv\Scripts\python.exe -m acquisition.extraction.review apply $draftPath $sheetPath --reviewer-id YOUR_GITHUB_USER --reviewer-role "D1-C annotation/QA"
.\.venv\Scripts\python.exe -m acquisition.extraction.review status $draftPath
```

Thay `YOUR_GITHUB_USER` bằng người thực sự kiểm. Không dùng `codex` hay `--allow-self-review`.
Không chạy lại lệnh `sheet` sau khi điền vì lệnh đó tạo lại phiếu trống.
Bản ghi cần commit sau khi kiểm là `acquisition/extraction/reviews/B0_SRC_HAAS_0005.r2.review.json`,
không phải CSV local.

Sau khi đủ 33/33 source_checked, không rejected/stale: người phụ trách mới promote,
export/validate bundle, import và rebuild index rồi chạy lại live câu hỏi bôi trơn.
Không dùng `--allow-incomplete` để vượt bước kiểm. Nếu sửa draft sau review, cần xuất phiếu
mới và kiểm lại phần thay đổi; fingerprint cũ không còn hợp lệ.

## Cơ chế revision và kiểm thử

`revision_base` trong draft trỏ tới `data/workflows/dev/B0_SRC_HAAS_0005.r1.json`,
với hash canonical của `Workflow` (không phải hash byte của file, để không phụ thuộc CRLF):
`0c0455591f5db02032ba9dbaa13e92b7f93a2e134bde7a2a61131ec65bcfd69b`.

Compiler hỗ trợ bản sửa **chỉ thay evidence**: bắt buộc pin base, revision nối tiếp,
giữ lịch sử và thêm một change event. Evidence có payload khác được cấp ID mới;
evidence cũ được giữ để không tái sử dụng ID ở r3 trở đi. Thay nội dung/thứ tự Claim,
Step hoặc cấu trúc workflow bị từ chối, cần cơ chế migration riêng. Trạng thái review luôn reset.
CLI compile và promote kiểm base cùng candidate bằng validator dùng chung, bao gồm V03.

Riêng draft cũ chưa có `revision_base` chỉ được tái lập nếu khớp nguyên trạng snapshot nháp
đã lưu; không cho sửa ngầm. Test phát hiện `REAL_WF_0001.r2` hiện có `REAL_WF_0001_EV_019`
đổi locator từ 142680–147840 sang 142699–142700 ms so với r1 đã promote, vẫn giữ ID cũ.
Cổng kiểm liên revision sẽ chặn bản đó; **chưa sửa draft của đội 1 trong công việc B0 này**.

Test hồi quy: `tests/unit/test_revision_compiler.py`, kèm test compiler và review hiện có.
Các test kiểm logic/nguồn transcript đã lưu, không thay thế việc người kiểm mở video gốc.
