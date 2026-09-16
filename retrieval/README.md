# D2-A — WP1/WP2: importer, lexical, vector và hybrid retrieval

**Tiếp nối WP3/API:** đã có generator + citation guard, `/v1/ask` và trang đọc
evidence tối thiểu. Cách chạy và giới hạn: [grounded QA pilot](../docs/team2_grounded_qa.md).

**WP4 đọc/lịch sử:** tự mở citation, duyệt Step/field/claim và so sánh revision với đúng
index lịch sử. Xem [WP4 reader](../docs/team2_wp4_reader.md). Phần ghi feedback chờ service đội 1.

Nhập bundle đội 1 bằng validator chung, lưu bản sao nguồn/snapshot bất biến và
dựng search records hai tầng Workflow/Step theo contract D-06. SQLite là lựa chọn
local cho bước đầu, chưa phải PostgreSQL/pgvector trong đề xuất của plan.

Chạy từ thư mục gốc repo trên PowerShell (không cần activate):

```powershell
.\.venv\Scripts\python.exe -m retrieval.importer import acquisition/export/haas_pilot_dev_bundle --db out/retrieval/real_dev.sqlite --source-type real --split dev
.\.venv\Scripts\python.exe -m retrieval.importer status --db out/retrieval/real_dev.sqlite
```

Có thể thay `.\.venv\Scripts\python.exe` bằng `uv run python`. Lần đầu trả
`status=imported`; chạy lại cùng nội dung trả `status=noop`, giữ `index_build_id`.
Bundle pilot hiện có 5 sources, 2 workflow, 20 step. Kết quả thực tế được in ra JSON.
Database đặt trong `out/` đã được gitignore.

Thử synthetic bằng database riêng:

```powershell
.\.venv\Scripts\python.exe -m retrieval.importer import data/fixtures/F01_complete --db out/retrieval/synthetic_dev.sqlite --source-type synthetic --split dev
```

## Quy tắc nhập và lưu

- Manifest khai báo đúng hai JSONL; checksum được kiểm trước khi parse nội dung.
  Sau đó dùng loader/rules của `knowflow_contracts` để kiểm schema, ID/reference,
  corpus/split, evidence và review; từ chối cả bundle nếu sai. Không sửa dữ liệu đầu vào.
- Một database thuộc duy nhất một `source_type` và `dataset_split`. Các tham số CLI
  này bắt buộc để tránh nhập nhầm corpus. Holdout chỉ nhập khi đến giai đoạn đã khóa.
- Cùng `(workflow_id, revision)` và hash: no-op; khác hash: lỗi V09. Giữ toàn bộ
  revision cũ. So sánh evidence giữa cả các lần nhập bằng validator chung.
- Source được giữ nguyên bản. Bước đầu từ chối source_id đã tồn tại nhưng payload
  khác, kể cả metadata; cần thống nhất chính sách version nguồn với D1-B trước khi
  hỗ trợ cập nhật trường hợp này. Không tự gán ID mới hay overwrite nguồn cũ.
- Mỗi bundle bổ sung vào kho; workflow vắng mặt trong bundle mới không bị xóa.
  Muốn rút workflow, nhận revision mới có `lifecycle=withdrawn`. Chọn latest trước
  khi lọc lifecycle, không quay về bản cũ. Kho vẫn giữ snapshot/bản build lịch sử.
- Snapshot, search records, manifest build và active pointer cùng một transaction.
  Lỗi ở bất kỳ bước nào rollback toàn bộ lần nhập; bản active trước đó vẫn dùng được.

## Đầu ra để nối WP2

Các bảng SQLite: `sources`, `snapshots`, `builds`, `search_records`, `imports`, `settings`.
Snapshot giữ nguyên claims, evidence, locator, field state, relation và review history.
Search records giữ context, claim text nguyên văn, attribution, scope và review flags.
Không dịch, không sinh thêm claim. Claim conflict/pending được giữ để WP2 phân loại.

```python
from retrieval.importer import read_active_records

manifest, records = read_active_records("out/retrieval/real_dev.sqlite")
# Một lần đọc nhất quán: manifest và records cùng index_build_id.
```

`index_build_id` phụ thuộc namespace, danh sách source/snapshot hash và cấu hình;
đổi thứ tự dòng JSONL không tạo build mới. Mỗi record ghi hash snapshot tương ứng.
Manifest lưu inventory và `text_template_version` để tái tạo.

Manifest importer vẫn ghi `index_kind=search-records`, `embedding_model=none`,
`embedding_version=not-built`: đây là bản record đầu vào. Chỉ mục retrieval có
manifest và active pointer riêng, được build từ chính phiên bản record này.

Chạy kiểm thử importer:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_importer.py
```

## Build và chạy retrieval

SDK Gemini là optional dependency. Nếu chưa cài:

```powershell
uv pip install -e ".[dev,retrieval]"
```

Đặt `GEMINI_API_KEY` trong `.env`. Build mặc định gửi search text đến Gemini để
tạo embedding; query vector/hybrid gửi câu hỏi để tạo query embedding, và câu hỏi
tiếng Việt được gửi thêm một lần để dịch (xem bên dưới). Lexical không tự gọi API.
Không log API key và không tự fallback sang vector giả hay câu chưa dịch khi API lỗi.
Lỗi 429 (giới hạn theo phút; bậc miễn phí của model dịch là 15 lần/phút) được thử lại
tối đa 3 lần theo `retryDelay` của server; đợi quá 65 giây (hết quota ngày) thì báo lỗi.

```powershell
.\.venv\Scripts\python.exe -m retrieval.retrieval build --db out/retrieval/real_dev.sqlite --mode real --split dev --embedding gemini
.\.venv\Scripts\python.exe -m retrieval.retrieval status --db out/retrieval/real_dev.sqlite --mode real --split dev
.\.venv\Scripts\python.exe -m retrieval.retrieval query "Bôi trơn con trượt của hốc dao trước khi lắp như thế nào?" --db out/retrieval/real_dev.sqlite --mode real --split dev --strategy hybrid --manufacturer Haas --subsystem SMTC --summary
```

Đổi `--strategy` thành `lexical`, `vector`, `hybrid` để chạy ba baseline với cùng
index và filter policy. Bỏ `--summary` để nhận đầy đủ claim/evidence package, các
cửa sổ timestamp, source locator, review flags, field state, questions và trace.
`--intent procedure` chọn một workflow rồi trả các Step đủ điều kiện theo thứ tự;
trace ghi Step bị bỏ vì thiếu claim đủ điều kiện. `--intent detail` lấy top-k Step.

Nếu chỉ muốn lexical offline, build với `--embedding none`. Index này không phục
vụ vector/hybrid; cần build lại với Gemini trước. Build cùng cấu hình và cùng
record build trả `noop` và không gọi embedding lại.

## Thuật toán và bộ lọc

- Lexical: BM25 thật (k1=1.2, b=0.75), tokenizer Unicode có bỏ dấu để hỗ trợ
  tiếng Việt không dấu. Giữ phủ định, đơn vị, chữ số và mã dạng `VF-2`. Record tiếng
  Anh được stem bằng Snowball (`rapids`/`rapid`, `rotating`/`rotate`); mã, số và tiếng
  Việt không bị stem.
- Câu hỏi tiếng Việt (có dấu hoặc không dấu) trên corpus tiếng Anh được dịch sang tiếng
  Anh bằng `gemini-3.5-flash-lite` (prompt `q2en-2`, temperature 0) **chỉ để tìm**: nhánh
  lexical và cổng liên quan dùng bản dịch, vector dùng câu gốc, claim/citation luôn lấy từ
  snapshot gốc (D-03). Bản dịch ghi ở `trace.query_translation`. Lexical-only không tự dịch;
  `--query-translation never` tắt dịch.
- Cổng liên quan (`--min-term-coverage`, mặc định 0.10): tỷ lệ từ nội dung của câu hỏi
  (trọng số IDF) có trong corpus đủ điều kiện sau bộ lọc context. Dưới ngưỡng thì trả
  `insufficient_evidence` trước khi gọi embedding. Câu tiếng Việt chưa dịch được thì bỏ qua
  cổng (`gate=skipped`) thay vì từ chối oan. Ngưỡng chọn trên real/dev (nhãn chưa người kiểm,
  15/09): mọi giá trị 0.10–0.15 cho 0/31 câu trả lời được bị loại và 13/19 câu ngoài phạm vi
  bị chặn; lấy đầu thấp vì từ chối oan không cứu lại được. Không dùng cosine làm cổng: câu
  cùng lĩnh vực mà KB không có vẫn đạt cosine cao hơn câu trả lời được. Câu dùng toàn từ chung
  ("level the machine") vẫn lọt, WP3 phải từ chối. Cần chỉnh lại khi corpus lớn hơn.
- Vector: `gemini-embedding-001`, 768 chiều mặc định, chuẩn hóa L2 và cosine
  chính xác trên tập đã lọc. SQLite lưu vector; chưa cần ANN/pgvector cho pilot.
  Tài liệu dùng `RETRIEVAL_DOCUMENT`, câu hỏi dùng `RETRIEVAL_QUERY` theo
  [Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings).
  Model phục vụ [hơn 100 ngôn ngữ](https://developers.googleblog.com/en/gemini-embedding-available-gemini-api/).
- Record dài được chia theo giới hạn 1800 UTF-8 bytes/đoạn rồi lấy trung bình
  vector đã chuẩn hóa, có trọng số theo chiều dài. Giữ toàn bộ text, không cắt bỏ
  phần cuối. Đây là lựa chọn ban đầu; cần đo tác động pooling trên dev.
- Hybrid: RRF với k=60, lexical top-20 + vector top-20, top-5 Step mặc định.
  `--candidate-k`, `--top-k`, `--min-cosine` là cấu hình thử nghiệm, chưa tối ưu.
  Điểm RRF/cosine không phải xác suất đúng hoặc độ có căn cứ của câu trả lời.
- Luồng hai tầng: lọc context → xếp hạng Workflow → chọn một Workflow/revision
  → xếp hạng Step trong Workflow đó. Không ghép các quy trình thành một quy trình mới.
- Mở rộng theo **quan hệ phụ thuộc** (`--neighbor-depth`, mặc định 1): từ Step đã khớp
  lấy thêm `requires` (điều kiện tiên quyết), `branch_if` (điểm rẽ nhánh chi phối Step đó,
  kèm `condition_claim_ids` nằm trên cạnh) và `corrects` (bản đính chính sau này).
  **Không** mở rộng theo `observed_next` hay `repeated_step`: thứ tự trong nguồn không
  phải quan hệ phụ thuộc (Schema 1.0.0 mục 6). Kết quả nằm ở khóa riêng `related_steps`
  và `related_claims` (`purpose=context_only`, `score=null`): `steps`, `claims` và `status`
  không đổi, nên một Step lân cận không bao giờ biến câu không trả lời được thành trả lời
  được. Mỗi claim lân cận được kiểm lại bằng `claim_blockers` theo review flags **của chính
  nó**, không kế thừa của Step đã khớp; claim đã là answer candidate không lặp lại ở đây.
  Step phụ thuộc nằm ngoài corpus đã lọc được ghi ở `trace.neighbors.unavailable_step_ids`,
  bị cắt vì `--max-related-steps` thì ghi ở `truncated_step_ids` — không biến mất im lặng.
  **WP3 chưa dùng `related_steps`:** dữ liệu đã có, generator chưa nối; cần đo trên dev trước.
- Corpus/split được kiểm trước khi đọc record/vector/snapshot. Sai namespace báo
  lỗi. Chỉ dùng latest active revision; nhập revision mới làm index cũ stale và query
  bị chặn cho đến khi build lại. Workflow withdrawn không quay về revision cũ.
- Hard filters: manufacturer, family, model, subsystem, task type và alarm code
  nếu có trong query context. Biết khác thì loại; thiếu metadata cần thiết thì
  `needs_clarification`. Nhận diện tên/model và alarm từ câu hỏi bằng luật bảo thủ;
  tên máy ngoài mẫu nhận diện cần truyền `--machine-model` rõ ràng.
- Alias có kiểm soát: `Haas`/`Haas Automation`, `SMTC`/`side-mount tool changer`.
  Mã alarm so khớp chính xác, không gộp `2066` với `2067` hoặc `20.66`.
  `--component` và `--symptom` là search hints; không dùng chúng để nới hard filters.
- `claim_blockers` được dùng trước khi dựng nội dung để xếp hạng và kiểm lại trước
  khi xuất claim. Pending real/inferred/unsupported/rejected không trở thành claim
  khẳng định. Conflict có index chẩn đoán riêng trong cùng corpus/context và được
  trả với `purpose=warning_only`, kèm cả hai phía, không dùng để đề xuất thao tác.
  Conflict chỉ được báo khi Step chứa nó lọt top-k cùng các Step trả lời; xếp riêng thì
  chỉ cần có một conflict trong corpus là câu nào cũng bị gắn `conflicting_sources`.
- Dedup claim theo workflow/revision/claim_id, lấy điểm max và giữ matched_step_ids.
  Giữ nguyên field missing, scope, attribution và loại relation trong snapshot.
- Cache truy vấn hiện tắt. Build manifest lưu namespace, base build, checksum,
  embedding/model/adapter/SDK version. Build lỗi giữ nguyên active index; importer
  thay đổi trong lúc gọi embedding thì từ chối activate kết quả đã cũ.

## Giao diện cho D2-B và kiểm thử

```python
from knowflow_contracts.models import QueryContext, QueryRequest
from retrieval.retrieval.engine import RetrievalConfig, retrieve

result = retrieve(
    "out/retrieval/real_dev.sqlite",
    QueryRequest(question="How is the pocket slider lubricated?", mode="real",
                 dataset_split="dev", context=QueryContext(manufacturer="Haas", subsystem="SMTC")),
    config=RetrievalConfig(strategy="hybrid"),
)
```

Đây là **retrieval result**, chưa phải `AnswerResponse` của `/v1/ask`.
`retrieved` nghĩa là tìm được claim candidates; D2-B còn phải kiểm câu khẳng định,
khả năng mở evidence và sinh câu trả lời theo WP3. Source URL/keyframe không được
truy cập mạng trong retrieval: `evidence_openability_checked=false`, từng evidence
có `access_status=not_checked`; không tự gọi citation là đã xác minh.

Các status khác: `needs_clarification`, `insufficient_evidence`, `conflicting_sources`.
Chưa triển khai reranker hay tự mở rộng Step lân cận. Answer generator và API nằm ở
`retrieval/generation` và `retrieval/api` (xem hướng dẫn ở đầu trang). Các relation
gốc được trả để phần tích hợp xử lý có căn cứ. Bộ unit tests dùng vector giả chỉ
để kiểm logic; không được dùng kết quả đó làm số đo chất lượng embedding thật.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_importer.py tests/unit/test_retrieval.py
```

Đã smoke-test trên bundle real/dev `BUNDLE_HAAS_SMTC_DEV_e98521a7942a`:
22 record (2 Workflow, 20 Step), build Gemini 768 chiều qua 2 API calls. Câu hỏi
tiếng Việt trong ví dụ trên tìm được `B0_SRC_HAAS_0005_ST_006` ở top-1 trong cả
vector và hybrid. Đây là kiểm chứng tích hợp trên một câu hỏi, chưa phải benchmark
recall/precision; chưa chạy holdout. Gemini là model hosted: version lưu model ID,
adapter/SDK và output vector hash, không khẳng định pin được hash trọng số server.

## Đánh giá retrieval

`retrieval.evaluation` chạy lexical, vector và hybrid trên cùng index và cùng filter
policy, tính Recall@k, MRR@k, Hit@1, độ chính xác chọn workflow và status (gồm cả
câu phải từ chối). Bộ câu hỏi, quy tắc tính và cách kiểm nhãn: xem
[data/eval/README.md](../data/eval/README.md). Nhãn gold hiện mới được AI kiểm
(`ai_reviewed`), chưa có người kiểm; report giữ cảnh báo cho đến khi có người kiểm.

```powershell
.\.venv\Scripts\python.exe -m retrieval.evaluation run --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --mode real --split dev
.\.venv\Scripts\python.exe -m pytest tests/unit/test_evaluation.py
```

## Đánh giá câu trả lời

`retrieval.evaluation answers` chạy cùng bộ câu hỏi qua **đường phục vụ** `QAService`
(đường mà `/v1/ask` dùng, không phải bản dựng lại) rồi chấm ở mức câu trả lời:
citation correctness, answer groundedness, đúng/sai trạng thái từ chối — tách riêng
`false_answer` và `false_abstention` — rò rỉ corpus/model, latency và token/chi phí.

```powershell
.\.venv\Scripts\python.exe -m retrieval.evaluation answers --db out/retrieval/real_dev.sqlite --questions data/eval/haas_real_dev.retrieval.v0.jsonl --mode real --verdict-template <github-user>
.\.venv\Scripts\python.exe -m pytest tests/unit/test_evaluation_answers.py
```

Những gì code chứng minh được (claim có trong snapshot, đúng revision active, evidence
link `supported` và mở được, review flags khớp snapshot, số trong câu có trong evidence
được cite, không trộn corpus/workflow) được chấm trên mọi câu. Việc nguồn **có hỗ trợ**
phát biểu hay không là việc của người kiểm: `citation_correctness` và `answer_groundedness`
là `null` cho tới khi có file verdict, vì lượt kiểm nghĩa bằng LLM trong pipeline chính là
thứ đang bị đo và không được tự chấm mình. Cách kiểm và định dạng verdict:
[data/eval/README.md](../data/eval/README.md). Holdout bị chặn; đường phục vụ chỉ bật `dev`.
