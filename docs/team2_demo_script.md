# Kịch bản demo 5–7 phút

Theo kế hoạch đội 2 mục 6. Mỗi đoạn ghi rõ **đã chạy được** hay **còn rủi ro**, kèm
phương án dự phòng. Không đoạn nào được diễn như thể một thứ chưa làm đã làm xong.

## Trạng thái ngày 19/09

| Đoạn | Sẵn sàng? | Phụ thuộc |
|---|---|---|
| 1. Video thật → workflow | ✅ | — |
| 2. Citation → evidence riêng | ✅ | — |
| 3. Hỏi phần còn thiếu | ✅ | Khóa Gemini |
| 4. Phản hồi → revision mới | ❌ **G2 chưa đóng** | Service ghi của D1-B / WP6 |
| 5. Hỏi lại, thử sai model | ⚠️ | Khóa Gemini; tiếng Việt chưa kiểm live |
| 6. Kết quả thật và giới hạn | ⚠️ | Nhãn gold chưa có người kiểm |

## Chuẩn bị trước buổi demo

- [ ] `.env` có `GEMINI_API_KEY` trên máy trình diễn. Không có thì đoạn 3 và 5 không chạy.
- [ ] Import + build index real/dev từ bundle mới nhất; ghi lại `index_build_id` vào đây: `[ghi]`
- [ ] **Đo** thời gian xử lý video và thời gian trả lời thật trên máy trình diễn: `[đo trước demo]`.
      Kế hoạch mục 6: video xử lý trước thì phải nói rõ thời điểm xử lý và thời gian đã đo,
      **không trình diễn như realtime**.
- [ ] Chạy thử trọn kịch bản ít nhất một lần, chụp màn hình từng đoạn làm phương án dự phòng.
- [ ] Người nhập phản hồi ở đoạn 4 dùng **tên và vai trò thật** của mình.
- [ ] Không dùng `KNOWFLOW_FEEDBACK_STUB` khi trình diễn trừ khi nói rõ đó là bản mô phỏng.

```powershell
.\.venv\Scripts\python.exe -m retrieval.importer import acquisition/export/haas_pilot_dev_bundle --db out/retrieval/real_dev.sqlite --source-type real --split dev
.\.venv\Scripts\python.exe -m retrieval.retrieval build --db out/retrieval/real_dev.sqlite --mode real --split dev --embedding gemini
.\.venv\Scripts\python.exe -m retrieval.api
```

---

## Đoạn 1 — Một video thật đã xử lý thành workflow (≈1 phút)

**Làm:** mở <http://127.0.0.1:8000>, chọn corpus "Nguồn thực · dev", chọn
`REAL_WF_0001 · r1` — *Replace a damaged pocket on a Haas side-mount tool changer (SMTC)*.

**Chứng minh:** A2 lấy tri thức **từ nguồn**, thành các bước rõ ràng. 11 bước, mỗi bước có
7 trường, mỗi claim có nguồn riêng.

**Nói:** nguồn là video dịch vụ công khai của Haas, dùng thay cho quy trình của chuyên gia
trong bản demo. Đây **không** phải bằng chứng về năng lực sửa máy hay hiệu quả tại DENSO.

## Đoạn 2 — Bấm từng phát biểu để xem đúng bằng chứng của nó (≈1 phút)

**Làm:** chọn `B0_SRC_HAAS_0005 · r2` → Step 6 → field `action` → claim `CL_020` → **Mở nguồn**.

**Phải thấy:** `EV_033`, đoạn 147.840–165.270 giây, câu có *"apply some grease"*.
Trạng thái `source_checked / not_requested`.

**Chứng minh:** citation hỗ trợ đúng từng phát biểu, không phải cả video.

**Nói:** `source_checked` nghĩa là **đã đối chiếu trung thực với nguồn**, không phải chuyên
gia đã xác nhận đúng kỹ thuật. Hai mức này tách riêng trong hệ thống.

## Đoạn 3 — Hỏi đúng phần nguồn không nói (≈1 phút)

**Làm:** hỏi *"Why is the main air disconnected at this point in the procedure?"*,
context Haas / SMTC.

**Vì sao chọn câu này:** đó là Question record **thật** đang mở trong `REAL_WF_0001`.
Người trong video làm thao tác đó nhưng không nói lý do.

**Chứng minh:** hệ thống nhận ra **chưa biết**, trả `insufficient_evidence`, không lấy
kiến thức chung của model để bịa lý do.

**Dự phòng** (nếu câu trên cho kết quả khác kỳ vọng): câu mẫu có sẵn trong ô chọn
*"Which grease grade / NLGI?"* — đã chạy live ngày 15/09 và trả đúng `insufficient_evidence`.

## Đoạn 4 — Bổ sung phản hồi thành revision mới (≈1,5 phút) ❌

**Kế hoạch muốn:** nhập phản hồi → lưu → xem revision mới → tri thức được bổ sung có
nguồn và còn lịch sử.

**Hiện chưa làm được.** Service ghi của đội 1 chưa có nên vòng này chưa đóng (G2).
Có hai cách trình bày trung thực, chọn tùy tình trạng lúc demo:

**A — Nếu service của D1-B đã xong và đã chạy thử trọn vòng:** làm trực tiếp trên
`REAL_WF_0001`, trả lời Question *"Why is the main air disconnected…"* bằng một câu người
trình diễn thật sự biết. Ghi tên và vai trò thật. Revision mới vẫn là `pending` — **không**
nói là chuyên gia đã xác nhận.

**B — Nếu chưa** (mặc định):

1. Mở phần **Lịch sử revision** của `B0_SRC_HAAS_0005 · r2`: `CL_020` đổi link
   `EV_019 → EV_033`. Bấm "Xem r1", mở lại claim đó — citation cũ vẫn mở đúng bằng
   chứng cũ, không tự nhảy sang bản mới.
2. **Nói rõ:** đây là revision **sửa bằng chứng**, có người kiểm, chứ **không** phải revision
   sinh từ phản hồi. Nó cho thấy cơ chế revision bất biến và lịch sử hoạt động; vòng phản
   hồi thì chưa.
3. Tùy chọn: chiếu màn **Bổ sung** chạy bằng stub, cho thấy bản xem trước và nút Lưu
   **bị tắt**. Phải nói ngay: *đây là bản mô phỏng, service ghi của đội 1 chưa có*.

**Không được:** bấm lưu trên stub rồi trình bày như đã lưu; nhập phản hồi dưới danh nghĩa
chuyên gia DENSO.

## Đoạn 5 — Hỏi lại và thử sai model (≈1 phút) ⚠️

**Làm:**

1. Hỏi *"How is the pocket slider lubricated?"* → câu trả lời có citation, mở được.
   Đã chạy live ngày 15/09 và trả `answered`.
2. Hỏi *"Can this procedure be used on a VF-2?"* (có sẵn trong ô chọn) → hệ thống không
   được suy rộng quy trình sang model mà nguồn không nêu.

**Chứng minh:** RAG trả lời có căn cứ, và có giới hạn áp dụng.

**Rủi ro tiếng Việt:** ngôn ngữ câu trả lời đã được sửa ở code ngày 19/09 nhưng
**chưa kiểm lại với Gemini thật**. Chạy thử bằng tiếng Việt trước buổi demo; nếu chưa ổn
thì trình diễn bằng tiếng Anh như kế hoạch cũ.

**Tùy chọn — alarm 2066:** hỏi *"Báo lỗi 2066 khi thay dao thì xử lý thế nào?"*.
`REAL_WF_0003` (phục hồi sau alarm 2066) vừa được review nguồn xong nên giờ có thể trả lời
được. **Chỉ dùng nếu đã chạy thử trước** — nhãn đánh giá của câu này vẫn đang chờ người chốt.

## Đoạn 6 — Kết quả thật và giới hạn (≈1 phút) ⚠️

**Nói đúng những gì có:**

- Corpus thật: 4 workflow từ video dịch vụ Haas về cụm thay dao SMTC, toàn bộ claim đã
  review nguồn.
- **Chưa có số đo chất lượng chính thức trên dữ liệu thật.** 54 câu đánh giá real/dev chưa
  có người kiểm nhãn gold, nên không báo cáo Recall hay độ chính xác như kết quả.
- Có đường đo câu trả lời (`evaluation answers`) tách phần code chứng minh được khỏi phần
  cần người chấm.

**Không được:** dùng số trên bộ synthetic làm bằng chứng hệ thống hiểu video. Bộ synthetic
chỉ để thử phần mềm; nếu nhắc tới thì phải nói đúng như vậy.

**Nếu kịp có số đo đã người kiểm:** ghi số đúng / tổng, không chỉ phần trăm, và nói phạm vi
nguồn. Với vài chục câu, không tuyên bố hơn baseline chỉ vì chênh vài điểm phần trăm.

## Kết thúc — một câu hệ thống không trả lời được

Kế hoạch yêu cầu kết thúc bằng một câu hệ thống **chưa đủ dữ liệu** để trả lời, với bằng
chứng và giới hạn rõ ràng. Dùng lại Question thật ở đoạn 3, hoặc *"What air pressure range
counts as correct for the tool changer?"* — Question đang mở trong `REAL_WF_0003`.

**Câu chốt gợi ý:** hệ thống biết phần nào nó biết, chỉ được nguồn nào, và biết dừng ở chỗ
nguồn dừng. Phần còn thiếu trở thành câu hỏi cho người có chuyên môn — không thành câu
trả lời bịa.

## Những câu không được nói

- "Chuyên gia đã xác nhận" — chưa có claim nào `expert_validated`.
- "Hệ thống xử lý video realtime" — video được xử lý trước.
- Bất kỳ con số chất lượng nào chưa có người kiểm nhãn.
- "Hệ thống hiểu mọi loại máy" — pilot chỉ có cụm SMTC của Haas.
- "Đã lưu phản hồi" khi service ghi chưa có.
