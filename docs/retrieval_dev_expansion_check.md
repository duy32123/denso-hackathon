# Đo lại retrieval sau khi mở rộng real/dev — 2026-10-12

Corpus real/dev tăng từ 4 lên 9 workflow đang phục vụ (thêm `REAL_WF_0004`–`REAL_WF_0008`,
xem [handoff mục 19](haas_d1a_to_d1b_handoff.md)). Trang cổng liên quan đã ghi sẵn rằng
heuristic này phụ thuộc corpus và phải kiểm lại khi thêm nguồn; đây là lượt kiểm đó.

**Tóm tắt:** phần tìm đúng không tụt, phần từ chối tụt rõ. Chưa sửa cổng, lý do ở cuối trang.

## Cách đo

- Cùng file câu hỏi, cùng mã nguồn, hai kho tạm dựng từ bundle cũ (`main`,
  `BUNDLE_HAAS_SMTC_DEV_20382d7957b6`) và bundle mới. Không đụng kho đang phục vụ ở `out/`.
- Chiến lược **lexical**, bản dịch lấy từ cache sẵn có: **0 lượt gọi dịch, 0 lượt gọi embedding**.
- **Chưa đo vector/hybrid**: dựng index Gemini bị giới hạn quota (HTTP 429) trong phiên này.
  Cổng liên quan chạy trước embedding nên số câu lọt cổng không phụ thuộc chiến lược, nhưng
  Recall/MRR của hybrid trên corpus mới vẫn là việc còn nợ.

## 66 câu đã được người kiểm

| Chỉ số (lexical) | Bundle cũ | Bundle mới |
|---|---:|---:|
| Status accuracy, mẫu số 66 | 0.9848 | 0.8636 |
| `false_retrieved` | 1 (Q040) | **9** |
| `missed` | 0 | 0 |
| Recall@5, mẫu số 37 | 0.9459 | 0.9459 |
| MRR@5 | 0.7680 | 0.7815 |
| Hit@1 | 0.6486 | 0.6757 |
| Workflow accuracy, mẫu số 45 | 0.9333 | 0.9333 |

Tám câu ngoài phạm vi mới lọt cổng: Q041, Q042, Q044, Q048, Q049, Q051, Q052, Q053.

**Nguyên nhân.** Quy tắc 2 của cổng bỏ các từ xuất hiện trong hơn 75% Step. Khi corpus chỉ
có SMTC, các từ chung như `tool`, `changer`, `carousel`, `machine` vượt 75% nên bị bỏ. Corpus
giờ có thêm trục chính, nguồn điện và tấm che, các từ đó tụt dưới 75% và được tính là từ nội
dung; hai từ chung khớp trong một claim là đủ qua cổng (ví dụ Q051 khớp `carousel`, `changer`,
`tool`; Q052 khớp `home`, `machine`).

**Nhãn cần người kiểm lại trước khi chỉnh cổng** (đúng thứ tự việc đã ghi ở
[data/eval/README.md](../data/eval/README.md): kiểm nhãn xong mới chỉnh ngưỡng):

| Câu | Vì sao cần xem lại |
|---|---|
| Q041 nồng độ dung dịch làm mát | `REAL_WF_0008` bước 3 có nói phải kiểm nồng độ bằng khúc xạ kế, nhưng không nêu con số. Tầng retrieval tìm thấy nội dung liên quan là hợp lý; tầng trả lời vẫn phải từ chối. |
| Q049 thay dây đai trục chính | `REAL_WF_0005` bước 4 nói kiểm độ căng đai, không nói thay đai. Tương tự Q041. |
| Q044, Q053 băng tải phoi | `REAL_WF_0008` có nói dọn phoi khỏi ray dẫn hướng; không có băng tải phoi. Vẫn là ngoài phạm vi. |
| Q042, Q048, Q051, Q052 | Khớp từ chung, corpus không có nội dung được hỏi. Vẫn là ngoài phạm vi. |

Q015 và Q031 (mỡ bôi trơn con trượt hốc dao) giờ bị đưa sang `REAL_WF_0008` (mỡ red-eye của
tấm che) thay vì `REAL_WF_0003`. Trước và sau đều chọn sai workflow nên workflow accuracy
không đổi, nhưng kiểu sai đã khác.

## 15 câu cho năm workflow mới

`HAAS_DEV_Q069`–`Q083`, ba câu mỗi workflow, tiếng Anh, `labeled_by=claude-draft`. Nhãn
được soạn từ snapshot **trước khi** chạy engine và không sửa theo kết quả. `quyhienln` đã
kiểm ngày 2026-10-12 (`label.status=reviewed`); người kiểm không trùng người soạn.

Trên bundle mới (lexical): 14/15 có kết quả, **13/15 đúng Step ở hạng 1**, Q070 ở hạng 4.
Q069 ("According to the service video, when does alarm 626 occur?") bị cổng từ chối: `alarm
626` được tính là context đã khớp, phần còn lại của câu chỉ còn một từ nội dung. Đây là một
lần trượt thật của engine, giữ nguyên nhãn.

Cả 81 câu: Recall@5 0.9423 (mẫu số 52), MRR@5 0.8109, Hit@1 0.7308, status accuracy 0.8765.
Lượt đo này chạy khi 15 câu mới còn là nháp; nhãn không đổi sau khi kiểm nên con số giữ nguyên,
nhưng đây mới là lexical. Số báo cáo chính thức cần lượt hybrid còn nợ bên dưới.

## Đã thử và không dùng

Thay "tỷ lệ Step" bằng "tỷ lệ workflow" khi xác định từ nền (ngưỡng 0.4 đến 0.7), đo trên
cả hai bundle: Recall@5 tụt còn 0.76–0.84 và 5–11 câu có đáp án bị từ chối, trong khi vẫn
còn 5–8 câu ngoài phạm vi lọt cổng. Kém hơn hiện trạng nên không đưa vào mã.

Coverage của câu có đáp án (thấp nhất 0.22 với 2 từ khớp) và câu ngoài phạm vi (0.40–0.75)
chồng lên nhau, nên chỉnh ngưỡng tỷ lệ cũng không tách được hai nhóm.

## Việc còn lại

- [x] Người kiểm 15 câu mới (`quyhienln`, 2026-10-12).
- [ ] Người kiểm lại 20 câu phủ định trên corpus mới (ít nhất Q041, Q049).
- [ ] Sau đó mới hiệu chỉnh cổng liên quan; cần một tín hiệu khác ngoài tỷ lệ từ khớp.
- [ ] Dựng lại index Gemini và đo vector/hybrid khi có quota.
- [ ] Nhập bundle mới vào kho phục vụ (`out/retrieval/real_dev.sqlite`) khi nhóm quyết định
      đưa năm workflow mới ra demo; hiện kho đó vẫn là bundle cũ.
