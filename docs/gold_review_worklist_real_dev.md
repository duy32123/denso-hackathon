# Kiểm nhãn gold real/dev — sàng lọc và kết quả

Sàng lọc tự động ngày 2026-09-22 trên corpus phục vụ hiện tại
(`BUNDLE_HAAS_SMTC_DEV_20382d7957b6`: 4 workflow, 38 Step).
Người soạn nhãn là `claude-draft` (AI), nên bất kỳ thành viên nào cũng đủ tư cách làm
người kiểm — không ai trong nhóm là tác giả nhãn.

## Đã kiểm xong — 2026-09-22

`duy32123` đã chạy `evaluation apply --reviewer-id duy32123` trên toàn bộ sheet.

| | Trước | Sau |
|---|---|---|
| Số câu | 54 | **52** |
| `reviewed` (người kiểm) | 0 | **52** |
| `draft` / `ai_reviewed` | 47 / 7 | 0 / 0 |

Hai câu bị **drop**: `Q038`, `Q036` (lý do ở mục A và B). Không câu nào bị `fix` — nghĩa là
**không có nhãn nào bị sửa cho khớp kết quả engine**.

Evaluator đã thôi in cảnh báo "not human-checked". Số đo từ nay **được phép báo cáo**, kèm
hai giới hạn bắt buộc nêu ở mục cuối: bộ câu hỏi chỉ phủ 20/38 Step, và `n` cho Recall/MRR
chỉ là 27 câu.

### Chính sách đã chốt kèm theo

**Metadata model rỗng (`machine_model = null`) ⇒ trả lời kèm phạm vi nguồn, không hỏi lại.**

Câu trả lời phải nói rõ nguồn không nêu model và đây là quy trình cho cụm SMTC. Áp dụng cho
cả nhóm `model_khong_ro` của bộ synthetic — nhưng lưu ý bộ đó **sinh ra từ
`scripts/build_synthetic_questions.py`** và CI so từng byte, nên sửa ở generator chứ không
sửa JSONL.

Chính sách này **không** áp cho ca mâu thuẫn model (câu hỏi nêu một model, context nêu model
khác — `Q037`): ca đó vẫn `needs_clarification`.

## Kết quả sàng lọc

Việc kiểm ít hơn lo ngại ban đầu. Nhưng lộ ra một vấn đề lớn hơn nhãn — xem mục cuối.

| Nhóm | Số câu | Kết quả |
|---|---|---|
| A. Nhãn đã lỗi thời | 1 | `Q038` → **drop** |
| B. Cần quyết định chính sách | 1 | `Q036` → **drop**, chính sách ghi ở trên |
| C. Xác nhận nhanh | 2 | `Q035`, `Q037` → `ok` |
| D. Còn lại | 50 | `ok` |

---

## A. Nhãn đã lỗi thời

### `HAAS_DEV_Q038` — "Báo lỗi 2066 khi thay dao thì xử lý thế nào?"

Nhãn cũ: `expected_status=insufficient_evidence`, không có gold. **Đã drop.**

**Lý do nhãn này sai:** ghi chú AI ngày 14/09 nói rõ căn cứ của nó —

> *"snapshot real/dev chỉ có hai workflow thay hốc dao, không có claim/quy trình xử lý alarm 2066"*

Câu đó **đúng lúc viết**, nhưng sai từ 18/09 (PR #17) khi `REAL_WF_0002/0003` vào corpus
phục vụ. `REAL_WF_0003` giờ có:

- `title`: *Recover a Haas SMTC after a tool changer alarm*
- `context.alarm_codes`: `['2066']`
- `symptoms`: `['tool changer alarm', '2066 tool changer home position fault']`
- Claim nguyên văn: *"The alarm screen displays '2066 TOOL CHANGER HOME POSITION FAULT'
  in a red banner…"* và chuỗi RECOVER → automatic recovery → manual recovery.

**Quyết định: drop, không đổi nhãn sang `answered`.** Câu này được soạn làm câu phủ định
để chỉnh ngưỡng từ chối; nay KB trả lời được thì nó không còn phục vụ mục đích đó. Đổi nhãn
cho khớp cái engine vừa tìm thấy là đúng kiểu lỗi `data/eval/README.md` cảnh báo. Thay bằng
câu đúng dạng cho `REAL_WF_0003` trong lô bổ sung.

---

## B. Cần quyết định chính sách

### `HAAS_DEV_Q036` — "Thay hốc dao cho máy VF-2 như thế nào?" (context rỗng)

Nhãn: `needs_clarification`. Ghi chú gốc đã đánh dấu **CẦN NGƯỜI CHỐT**.

Đây không phải lỗi nhãn mà là lựa chọn của đội: KB **không ghi** model áp dụng
(`machine_model` là `null` ở cả hai workflow thay hốc dao).

**Chính sách đã chốt: trả lời kèm phạm vi nguồn** (xem mục đầu trang).

**Nhưng Q036 vẫn bị drop**, vì lý do cấu trúc chứ không phải chính sách: nó có
`intent=detail` trong khi câu hỏi là dạng quy trình, mà `EvalQuestion` bắt câu
`answered` + `detail` phải có `gold_units` mức Step; sheet lại không sửa được `intent` hay
`gold_workflows`. Theo chính sách mới, Q036 cũng thành bản trùng của `Q028` kèm tên model,
không còn test được hành vi hỏi-lại như mục đích gốc. Lô bổ sung sẽ có câu
`intent=procedure` thay thế.

---

## C. Nên xác nhận nhanh

### `HAAS_DEV_Q035` — context `manufacturer: Mazak`
Nhãn `insufficient_evidence` **đúng**: hard filter loại cả hai workflow Haas, và không
được chuyển quy trình giữa hãng. Đã đánh `ok`.

### `HAAS_DEV_Q037` — câu hỏi nêu VF-2, context nêu UMC-750
Nhãn `needs_clarification` **đúng**: hai model mâu thuẫn, phải làm rõ trước khi truy xuất.
Khác hẳn ca `null` của Q036, nên chính sách mới không áp vào đây. Đã đánh `ok`.

---

## D. 50 câu còn lại — đã đánh `ok`

Đã đối chiếu từng câu với nội dung 4 workflow:

- **31 câu có gold** (`Q001`–`Q031`): đều hỏi về **thay hốc dao**, gold trỏ đúng
  `B0_SRC_HAAS_0005` + `REAL_WF_0001`. 29 câu dùng `gold_units` (chi tiết), 2 câu dùng
  `gold_workflows` (`Q028`, `Q029` — câu quy trình). Không câu nào thuộc địa hạt
  `REAL_WF_0002` (mòn double arm) hay `REAL_WF_0003` (phục hồi sau alarm), nên **gold không
  bị thiếu Step** — đây là lo ngại chính trong `data/eval/README.md`, kiểm xong thấy không
  xảy ra.
- **19 câu phủ định còn lại**: dầu hộp số, hiệu chuẩn probe, dây đai trục chính, dung dịch
  làm mát, lọc thủy lực, cân máy, băng tải phoi, pin bộ điều khiển, độ đảo trục chính, lọc
  khí nén, offset dao, homing trục, bộ thay dao ô (umbrella). Không chủ đề nào nằm trong 4
  workflow SMTC. Nhãn `insufficient_evidence` đúng.

> `Q051` ("adjust the carousel on an umbrella tool changer") đáng liếc qua: `REAL_WF_0003`
> có `carousel` trong `components`, nhưng đó là carousel của SMTC, khác cơ cấu umbrella.
> Nguồn umbrella (`SRC_HAAS_0006`) nằm ở **holdout**, chưa vào corpus phục vụ. Nhãn đúng.

**15 câu bị `false_retrieved`** trong lần đo lexical gần nhất: `Q033`, `Q038`, `Q039`,
`Q040`, `Q042`–`Q047`, `Q049`, `Q051`–`Q054`. **14 trong số đó không phải lỗi nhãn** — đó là
cổng liên quan quá lỏng sau khi corpus lên 4 workflow, đúng như `retrieval/README.md` đã ghi
ngày 18/09. Sửa ngưỡng, đừng sửa nhãn cho khớp engine.

Ngoại lệ duy nhất là **`Q038`**: ở đây retrieval tìm thấy `REAL_WF_0003` là **đúng**, và
chính nhãn mới sai (mục A). Đây là lý do phải kiểm nhãn *trước* khi chỉnh ngưỡng — nếu
hiệu chỉnh trên nhãn cũ, `Q038` sẽ kéo ngưỡng lên và làm hệ thống từ chối oan.

---

## Vấn đề lớn hơn nhãn: bộ câu hỏi chỉ phủ một nửa corpus

| Workflow | Step có ít nhất một câu hỏi |
|---|---|
| `B0_SRC_HAAS_0005` | 9/9 |
| `REAL_WF_0001` | 11/11 |
| `REAL_WF_0002` | **0/9** |
| `REAL_WF_0003` | **0/9** |
| **Tổng** | **20/38** |

Bộ 54 câu được soạn khi corpus chỉ có 2 workflow thay hốc dao. Từ 18/09 corpus có thêm 18
Step mà **không câu hỏi nào nhắm tới**. Hệ quả:

1. `Recall@5` / `MRR@5` chỉ đo trên 2 trong 4 workflow — không phải chỉ số của cả corpus.
2. 18 Step của `WF_0002/0003` hiện chỉ đóng vai **nhiễu**, làm chỉ số xấu đi mà không bao
   giờ có cơ hội được tính là đúng. Một phần "sụt" hôm 18/09 đến từ đây.
3. Bất kỳ con số nào báo cáo đều phải kèm câu "bộ câu hỏi phủ 20/38 Step".

**Việc tiếp theo:** soạn thêm khoảng 10–14 câu cho `WF_0002` (chẩn đoán
mòn double arm: khe hở finger–flange, căn chỉnh bằng shim, alarm servo 11.103/11.108/11.994)
và `WF_0003` (phục hồi sau alarm 2066). Người soạn phải khác người kiểm.

---

## Cách chạy

```powershell
# 1. Dựng index (lexical, không gọi API)
.\.venv\Scripts\python.exe -m retrieval.importer import acquisition/export/haas_pilot_dev_bundle --db out/retrieval/real_dev.sqlite --source-type real --split dev
.\.venv\Scripts\python.exe -m retrieval.retrieval build --db out/retrieval/real_dev.sqlite --mode real --split dev --embedding none

# 2. Xuất sheet
.\.venv\Scripts\python.exe -m retrieval.evaluation sheet --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl

# 3. Mở out/eval/haas_real_dev.retrieval.v0.sheet.csv, điền cột `decision`:
#      ok | fix | drop      (fix/drop bắt buộc ghi `note`)

# 4. Ghi lại
.\.venv\Scripts\python.exe -m retrieval.evaluation apply --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --sheet out/eval/haas_real_dev.retrieval.v0.sheet.csv --reviewer-id <github-user>
```

Cả sheet bị từ chối nếu một dòng lỗi: `fix`/`drop` thiếu note, `step_id` không tồn tại,
nhãn mâu thuẫn, hoặc người kiểm trùng người soạn. Sheet là file tạm trong `out/`
(gitignore); bản ghi chính thức là JSONL, cần commit.
