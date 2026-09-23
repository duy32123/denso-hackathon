# Kịch bản demo 5–7 phút

Theo kế hoạch đội 2 mục 6. Mỗi đoạn ghi rõ **đã chạy được** hay **còn rủi ro**, kèm
phương án dự phòng. Không đoạn nào được diễn như thể một thứ chưa làm đã làm xong.

## Trạng thái ngày 23/09

| Đoạn | Sẵn sàng? | Phụ thuộc |
|---|---|---|
| 1. Video thật → workflow | ✅ | — |
| 2. Citation → evidence riêng | ✅ | — |
| 3. Hỏi phần còn thiếu | ✅ | Khóa Gemini |
| 4. Phản hồi → revision mới | ✅ ghi được, **có điều kiện** | Service D1-B (#34) + adapter (#35). Không làm trên `REAL_WF_0001` — xem đoạn 4 |
| 5. Hỏi lại, thử sai model | ⚠️ | Câu hỏi lại **chưa thể** ra câu trả lời mới: chưa có công cụ source-review claim sinh từ phản hồi |
| 6. Kết quả thật và giới hạn | ✅ số retrieval | Nhãn real/dev đã người kiểm (52/52). Chưa có số đo câu trả lời/citation |

Ngày 23/09 đã chạy thử vòng phản hồi trên **một bản sao repo** (không đụng kho thật):
`preview` → `submit` ra revision mới đúng như contract. Hai điều phát hiện được ghi ở
đoạn 4 và đã báo đội 1.

## Chuẩn bị trước buổi demo

- [ ] `.env` có `GEMINI_API_KEY` trên máy trình diễn. Không có thì đoạn 3 và 5 không chạy.
- [ ] Import + build index real/dev từ bundle mới nhất; ghi lại `index_build_id` vào đây: `[ghi]`
- [ ] **Đo** thời gian xử lý video và thời gian trả lời thật trên máy trình diễn: `[đo trước demo]`.
      Kế hoạch mục 6: video xử lý trước thì phải nói rõ thời điểm xử lý và thời gian đã đo,
      **không trình diễn như realtime**.
- [ ] Chạy thử trọn kịch bản ít nhất một lần, chụp màn hình từng đoạn làm phương án dự phòng.
- [ ] Người nhập phản hồi ở đoạn 4 dùng **tên và vai trò thật** của mình.
- [ ] Không dùng `KNOWFLOW_FEEDBACK_STUB` khi trình diễn trừ khi nói rõ đó là bản mô phỏng.
- [ ] **Chạy demo trên một bản clone riêng**, không trên working copy đang phát triển. Lưu ở
      đoạn 4 ghi thật vào `data/workflows/dev/` và `acquisition/feedback/`; mỗi lần diễn tập
      tiêu một số revision. Không commit các tệp sinh ra khi diễn tập.
- [ ] Sau khi lưu ở đoạn 4 phải import + build lại index thì hỏi lại mới thấy revision mới
      (`reindex_required: true`). Build real với `--embedding gemini` tốn call embedding;
      đo trước thời gian bước này trên máy trình diễn: `[đo trước demo]`.

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

## Đoạn 4 — Bổ sung phản hồi thành revision mới (≈1,5 phút) ✅ có điều kiện

**Làm:** chọn `REAL_WF_0003` (bản mới nhất) → màn **Bổ sung** → Question
*"Why must all tools be removed from the arm before it can be rotated back to origin…"*
(`ST_005`, `rationale`) → nhập câu trả lời người trình diễn **thật sự biết**, tên và vai
trò thật → **Xem trước** → **Lưu**.

**Phải thấy:**

- Bản xem trước ghi claim mới `pending / not_requested`, dòng *"Danh tính người trả lời
  chưa được xác thực"*, và cảnh báo nếu phản hồi khác ngôn ngữ workflow.
- Sau khi lưu: revision mới (`r3`), revision cũ vẫn mở được. Lịch sử ghi người nhập kèm
  *"tự khai, chưa xác thực"*.

**Chứng minh:** tri thức được bổ sung **có nguồn** (Source `expert_answer` trỏ tới tệp
phản hồi nguyên văn) và **còn lịch sử**.

**Nói:** phản hồi chưa ai đối chiếu thì chỉ là `pending`. Hệ thống **không** coi đó là
chuyên gia xác nhận, và cũng chưa dùng nó để trả lời — xem đoạn 5.

**Không làm trên `REAL_WF_0001`.** Workflow này có sẵn một draft `r2` chưa promote (đang
chờ D1-C review keyframe). Lưu phản hồi trên base `r1` sẽ tạo `REAL_WF_0001.r2.json`; lần
sau promote draft `r2` sẽ **ghi đè không báo lỗi** lên revision phản hồi — mất claim, tệp
phản hồi thành mồ côi, và lần export kế tiếp dừng hẳn (`already published with different
content`), tức mọi lần lưu phản hồi sau đó đều hỏng. Đã tái hiện trên bản sao ngày 23/09
và báo đội 1.
`REAL_WF_0003` không có draft nào chưa promote.

**Dự phòng** (service lỗi hoặc máy trình diễn không ghi được): mở **Lịch sử revision** của
`B0_SRC_HAAS_0005 · r2` — `CL_020` đổi link `EV_019 → EV_033`; bấm "Xem r1" rồi mở lại
claim đó, citation cũ vẫn mở đúng bằng chứng cũ. Nói rõ đây là revision **sửa bằng
chứng**, không phải revision sinh từ phản hồi.

**Không được:** bấm lưu trên stub rồi trình bày như đã lưu; nhập phản hồi dưới danh nghĩa
chuyên gia DENSO.

## Đoạn 5 — Hỏi lại và thử sai model (≈1 phút) ⚠️

**Làm:**

1. (Nếu đã làm đoạn 4 và đã import + build lại) hỏi lại đúng câu ở đoạn 4. Index phục vụ
   `r3`, nhưng claim phản hồi còn `pending` nên **code loại nó khỏi ứng viên**
   (`claim_blockers`, `mode=real`) — đã kiểm trên bản sao ngày 23/09. Các claim đã kiểm
   khác của `ST_005` vẫn đi tới model, nên kỳ vọng `insufficient_evidence` là **do model
   nhận ra lý do không có**, không phải code bảo đảm: chạy thử câu này trước. Nói rõ: RAG
   đã thấy revision mới, nhưng phản hồi chưa được đối chiếu thì không được lên tiếng thay
   cho nguồn.
   **Chưa trình diễn được** bước "người kiểm nguồn duyệt → hỏi lại ra câu trả lời mới":
   `acquisition.extraction.review` chỉ đọc file draft, không mở được snapshot do phản hồi
   tạo ra (`KeyError: 'claims'`). Đã báo đội 1.
2. Hỏi *"How is the pocket slider lubricated?"* → câu trả lời có citation, mở được.
   Đã chạy live ngày 15/09 và trả `answered`.
3. Hỏi *"Can this procedure be used on a VF-2?"* (có sẵn trong ô chọn) → hệ thống không
   được suy rộng quy trình sang model mà nguồn không nêu.

**Chứng minh:** RAG trả lời có căn cứ, và có giới hạn áp dụng.

**Tiếng Việt:** đã kiểm với Gemini thật ngày 19/09 trên dữ liệu synthetic (#25): câu hỏi
tiếng Việt trên evidence tiếng Anh ra câu trả lời tiếng Việt 18/18 lần. Vẫn chạy thử một
câu tiếng Việt trên corpus thật trước buổi demo.

**Tùy chọn — alarm 2066:** hỏi *"Báo lỗi 2066 khi thay dao thì xử lý thế nào?"*.
`REAL_WF_0003` (phục hồi sau alarm 2066) đã review nguồn nên có thể trả lời được. **Chỉ
dùng nếu đã chạy thử trước.** Câu tương ứng trong bộ đánh giá (Q038) đã bị drop ở #36 vì
tiền đề cũ không còn đúng, nên không có nhãn để dẫn.

## Đoạn 6 — Kết quả thật và giới hạn (≈1 phút) ⚠️

**Nói đúng những gì có:**

- Corpus thật: 4 workflow từ video dịch vụ Haas về cụm thay dao SMTC, toàn bộ claim đã
  review nguồn.
- **Retrieval trên real/dev** (52 câu, nhãn đã người kiểm, [chi tiết](retrieval_relevance_gate.md)):
  hybrid Recall@5 **25/27** câu có đáp án (0.926), `false_retrieved` 0. Đây là **dev dùng
  để chỉnh cổng**, không phải holdout. Nói số đúng / tổng.
- **Chưa có số đo câu trả lời và citation trên dữ liệu thật** (mục tiêu ≥90% của kế hoạch).
  Có đường đo (`evaluation answers`) tách phần code chứng minh được khỏi phần cần người
  chấm, nhưng chưa chạy trên real.

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
