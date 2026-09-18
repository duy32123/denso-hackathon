# Synthetic KB — kế hoạch đội 2, mục 1.4

**Dữ liệu mô phỏng.** Thiết bị giả `DEMO_TC_A` / `DEMO_TC_B` của hãng giả `DemoWorks`.
Không có video thật, không có chuyên gia thật. Bộ này dùng để **phát triển và thử phần
mềm**; kết quả chạy trên nó **không** được dùng làm bằng chứng hệ thống đã hiểu video.
Số đo thật phải đo trên `real/dev` và báo riêng.

Sinh bằng `python scripts/build_synthetic_kb.py` — seed cố định, không gọi LLM.
CI chạy lại và so từng byte (`git diff --exit-code data/synthetic_samples`).

## Nội dung

| Thư mục | Dùng để |
|---|---|
| `serving/` | Bundle hợp lệ, **import được**: 40 workflow_id / 42 record / 45 source / 290 step |
| `negative/` | 4 bundle **cố ý sai** — chỉ chạy negative test, **không bao giờ import** |
| `generator.json` | seed, generator/template version, thống kê coverage |

```powershell
python -m retrieval.importer import data/synthetic_samples/serving --db out/retrieval/synthetic_dev.sqlite --source-type synthetic --split dev
python -m retrieval.retrieval build --db out/retrieval/synthetic_dev.sqlite --mode synthetic --split dev --embedding none
```

DB riêng cho namespace synthetic. Không import vào `real_dev.sqlite`: một DB một corpus.
`--embedding none` cho lexical offline; vector/hybrid cần build lại với Gemini.

## Ma trận coverage

| Nhóm | wf | Ca cố ý dựng |
|---|---|---|
| `thieu_thong_tin` | 8 | `rationale` / `condition` / `acceptance_criteria` state=`missing` + 20 Question record |
| `khac_thiet_bi` | 7 | Chủ đề gần trùng trên `DEMO_TC_A` vs `DEMO_TC_B`; 1 workflow `machine_model=null` |
| `nguon_phien_ban` | 7 | 3 conflict đối xứng, 2 workflow có r1→r2, 1 `lifecycle=withdrawn`, 1 claim `insufficient` |
| `quan_he_buoc` | 7 | `branch_if` (có condition), `repeated_step`, chuỗi `observed_next` |
| `ngon_ngu_tim_kiem` | 7 | 2 workflow tiếng Anh, alarm `2066` / `2067` / `20.66`, 2 bản ghi có lỗi ASR |
| `evidence` | 4 | 2 nguồn chỉ có văn bản (modality `text`, không timestamp), 2 nhiều quan sát hình ảnh |

Chống "synthetic quá sạch" (kế hoạch mục 6): `asr_noise()` làm dính từ trong
`Evidence.quote` giống lỗi nhận dạng — nhưng **không đụng vào chữ số và mã**, vì D-07
yêu cầu claim chứa mã/số phải có quote nguyên văn.

## Ranh giới đã giữ

- Mọi claim `source_review=pending`, `technical_review=not_requested`, `review_events` rỗng
  (V07 chặn, và `test_review_flags_stay_pending` kiểm lại lần nữa).
- `support_status` luôn do `derive_support_status` suy ra (D-01), không đặt tay.
- Workflow có conflict bị hạ xuống `ambiguous` nên **không khẳng định được**; retrieval vẫn
  phải tìm thấy để cảnh báo có dẫn nguồn.
- Nguồn chỉ có văn bản dùng modality `text` + `text_span`. Không gọi một timestamp giả là
  bằng chứng video.
- `language` của workflow luôn nằm trong tập ngôn ngữ của các nguồn nó dùng (D-03).

Ở `mode=synthetic`, `eligibility.claim_blockers` không xét `source_review`, nên claim
`pending` vẫn trả lời được — đó là lý do KB này dùng để thử WP3/WP4 mà không phải
giả nhãn review.

## Bundle negative

| Bundle | Hỏng gì | Mã lỗi |
|---|---|---|
| `N01_citation_khong_ton_tai` | `evidence_links` trỏ ra ngoài snapshot | V03 |
| `N02_claim_mo_coi` | claim không FieldRef nào tham chiếu | V05 |
| `N03_conflict_mot_chieu` | `conflicts_with` không đối xứng | V07 |
| `N04_review_gia` | tự nhận `source_checked`, không có ReviewEvent | V07 |

Kiểm: `pytest tests/unit/test_synthetic_kb.py`

## Chưa làm

Bộ 100–150 câu hỏi synthetic có nhãn kỳ vọng (kế hoạch mục 1.5) — giai đoạn kế tiếp,
sẽ nằm ở `data/eval/synthetic_dev.qa.v0.jsonl` theo đúng schema `EvalQuestion`.
Nhãn do người soạn vẫn là `draft` cho tới khi có **người khác** kiểm.
