# Sửa alias subsystem SMTC — 2026-09-22

> Báo cáo này giữ kết quả tại mốc sửa alias, trước khi đổi cổng liên quan.
> [Bản sửa cổng và phép đo đối chứng tiếp theo](retrieval_relevance_gate.md) xử lý hồi quy
> Q046 và kiểm tra lại Q067; không dùng các bảng dưới đây như số đo của cổng hiện tại.

Đã sửa lỗi loại `REAL_WF_0002` trước khi xếp hạng. Đây là lỗi so khớp metadata,
không phải bằng chứng rằng phải thay nguồn video hoặc tự điền model máy còn thiếu.

## Nguyên nhân và phạm vi sửa

Query dùng `context.subsystem="SMTC"`. Workflow `REAL_WF_0002.r2` ghi
`side-mount tool changer (SMTC), double arm`. Hàm `normal()` cũ chuẩn hóa hai chuỗi
thành `smtc` và `sidemounttoolchangersmtcdoublearm`, nên `context_gate()` báo
`mismatches=["subsystem"]`. Workflow đúng bị loại trước cả relevance gate và ranking.
Vì vậy, `term_coverage > 0.20` ở workflow còn lại không chứng minh gold được đem ra xếp hạng.

[context.py](../retrieval/retrieval/context.py) bổ sung allowlist cho ba cách viết
SMTC có hậu tố `double arm`, bên cạnh ba alias cũ. Cùng một phép chuẩn hóa được dùng
cho trích xuất context và so sánh hard filter, tránh báo mâu thuẫn khi câu hỏi nhắc
cả tên đầy đủ lẫn chữ viết tắt.

- Không dùng substring matching và không bỏ hậu tố tùy ý. `umbrella SMTC`, `double arm`
  đứng riêng và biến thể không biết vẫn không được đồng nhất với SMTC.
- Không sửa snapshot, index, claim, source review, model máy hoặc gold label. Thông tin
  `double arm` trong nguồn/index được giữ nguyên; không có migration sang field `components`.
- Không nới gate manufacturer/model/alarm, không đổi ranking hoặc ngưỡng 0.20.
- Không đụng holdout. File 66 câu của người dùng giữ nguyên toàn bộ byte, SHA-256:
  `304735bac82b2227dd81c635bf911a9ee4fc1a0193d3c326482edca95c64d95a`.

## Kiểm chứng đường chạy thật

So sánh với `EVAL_20260922T123627Z_5bfa4eab`, cùng index
`IDX_SEARCH_b9c6c8a74f8b61713283ee0f5cb366d4d3d4bdc30ae1bddd0a54a0590c429f4d`,
cùng câu hỏi, cấu hình và cache dịch/vector Gemini thật. Không dùng vector giả để đo chất lượng.

| Câu | Hybrid trước sửa | Hybrid sau sửa |
|---|---|---|
| Q055–Q058 | `REAL_WF_0003`, Recall@5 mỗi câu = 0 | `REAL_WF_0002`, Recall@5 mỗi câu = 1, gold ở top-1 |
| Q060, procedure | `B0_SRC_HAAS_0005` | `REAL_WF_0002`, lấy đủ 9 Step |
| Q061, hỏi phần nguồn không đủ bằng chứng | `REAL_WF_0001` | `REAL_WF_0002`; vẫn cần tầng trả lời từ chối |

**Q059 được kiểm riêng, chưa có số đo hybrid đầy đủ.** Sau sửa, workflow có metadata
alarm 11.103/11.108/11.994 qua được context gate. Test offline với câu tiếng Việt gốc
và bản dịch stub trả về `REAL_WF_0002_ST_009` ở top-1, không còn hỏi lại alarm.
Đây là kiểm logic, không thay thế lượt đo có dịch/embedding thật.

Q059 không có cache vì bản cũ dừng trước bước dịch. Sau khi người dùng cho phép gửi
riêng câu này tới Gemini, thử bổ sung cache vẫn gặp lỗi dịch vụ HTTP 503/504.
Không đổi model, không dùng bản dịch thủ công làm cache Gemini và không âm thầm bỏ
dịch. Vì vậy báo cáo chẩn đoán bỏ qua Q059 ở cả ba strategy, ghi rõ lý do thiếu cache.
Parser hiện chỉ trích ra 11.103 từ danh sách này; bản sửa **không** giải quyết tổng quát
việc trích nhiều mã hoặc phân biệt câu tra cứu với câu chẩn đoán máy.

## Đối chứng cùng 65 câu có cache

Artifact local (không commit vì `out/` được ignore):
`out/eval/DIAG_20260922T142029Z_smtc_alias_cache_only/report.json` và
`out/eval/DIAG_20260922T142029Z_smtc_alias_cache_only/rows.jsonl`.
Report chứa cấu hình, hash bộ câu hỏi, index ID, danh sách bỏ qua, thay đổi từng câu
và số đo tách riêng nhóm `reviewed`. Lượt replay gọi API **0 lần**; `out/` không được commit.

**Chỉ là số đo chẩn đoán:** 65 câu này gồm 52 reviewed + 13 draft; Q059 draft bị loại
khỏi **cả mẫu trước và sau**. Không so số 65 câu này trực tiếp với số tổng 66 câu cũ.
Mẫu số Recall/MRR = 36; workflow accuracy = 44; status = 65.

| Strategy | Recall@5 trước → sau | Workflow accuracy trước → sau | Status accuracy trước → sau |
|---|---|---|---|
| lexical | 0.7778 → 0.8889 | 0.7727 → 0.8864 | 0.8462 → 0.8308 |
| vector | 0.7778 → 0.8889 | 0.7727 → 0.8864 | 0.8462 → 0.8308 |
| hybrid | 0.8056 → 0.9167 | 0.7955 → 0.9318 | 0.8462 → 0.8308 |

### Tác động lên 52 câu đã được người kiểm

Recall/MRR/Hit@1 và workflow accuracy không đổi ở cả ba strategy. Riêng hybrid:
Recall@5 vẫn 0.9259 (n=27), workflow accuracy vẫn 0.9355 (n=31).
Nhưng status accuracy giảm **0.8269 → 0.8077** (n=52), do `false_retrieved` tăng
**9 → 10**. Không có câu answered nào trong 52 câu bị từ chối mới (`missed=[]`).

## Vấn đề còn lại — không che hồi quy

- **Q046, hồi quy mới:** “Đo độ đảo trục chính bằng đồng hồ so thế nào?” ngoài phạm vi
  nguồn, nhưng `term_coverage` tăng **0.1038 → 0.4732** khi 9 Step của WF0002 được đưa
  lại vào corpus đủ điều kiện. Cả ba strategy nay trả `retrieved`; hybrid chọn WF0003.
  Gate hiện đếm từ trên toàn corpus đã lọc, chưa chứng minh workflow/Step được chọn
  có đủ bằng chứng. Đây là lý do status accuracy giảm dù routing WF0002 đã đúng.
- **Q067, lỗi đã có:** câu hỏi giới hạn của RECOVER vẫn bị từ chối; coverage tăng
  **0.0748 → 0.1891** nhưng còn dưới 0.20. Không hạ ngưỡng theo một câu draft.
- Q061/Q065 là ca expected answer `insufficient_evidence` nhưng expected retrieval
  `retrieved`. Không coi việc tìm được Step là đã kiểm chứng tầng trả lời từ chối đúng;
  lượt này chưa chạy answer generation.

Việc tiếp theo: đo đủ Q059 khi dịch vụ hoạt động lại; xử lý cổng liên quan bằng phép
đo riêng trên nhãn đã kiểm, theo dõi đồng thời Q046 và Q067. Không đổi gold để khớp engine.

## Kiểm thử

20 ca bổ sung trong [test_context.py](../tests/unit/test_context.py) và
[test_query.py](../tests/unit/test_query.py): alias có kiểm soát, biến thể bị chặn,
tên đầy đủ không tạo conflict giả, vẫn hỏi model khi thiếu, năm ca routing WF0002
và Q059 tra bảng alarm. Các probe lexical/stub đều offline, chỉ kiểm logic.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_context.py tests/unit/test_query.py tests/unit/test_retrieval.py
.\.venv\Scripts\python.exe -m pytest
```

Kết quả: **102 passed** cho nhóm liên quan; toàn suite **744 passed, 3 skipped**
(hai cảnh báo deprecation từ dependency). `git diff --check` sạch.
Không cần rebuild index cho bản sửa chỉ ở query-side normalization này.
