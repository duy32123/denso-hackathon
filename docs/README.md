# Tài liệu KnowFlow AI

## Đọc để đánh giá dự án

1. [Ý tưởng A2](a2_idea_submission.md): bài toán, giải pháp, điểm khác biệt và kế hoạch.
2. [Kịch bản hai giao diện](demo_recording_new_ui.md): luồng sử dụng sau PR #54.
3. [Graph 3D và trace](a2_knowledge_space_3d.md): cấu trúc, thao tác và phạm vi hiện tại.
4. [Benchmark 81 câu](../benchmarks/results/20261012_expanded_dev/REPORT.md): A/B/C,
   mẫu số, latency, chi phí, lỗi và các kết luận chưa được chứng minh.
5. [Chạy web](../README.md#chay-web) và [tham chiếu API](api_reference.md).

## Hợp đồng, dữ liệu và hồ sơ review

- [Schema và validator](../contracts/README.md), [lịch sử hợp đồng](../contracts/CHANGELOG.md).
- [Quyền sử dụng và truy cập nguồn](data_rights_register.md),
  [bàn giao nguồn Haas](haas_d1a_to_d1b_handoff.md), [kiểm chất lượng nguồn](haas_d1a_quality_report.md).
- Keyframe: [phương pháp chọn](keyframe_selection_method.md),
  [khả năng công cụ](keyframe_capability_audit.md), [calibration](keyframe_calibration_report.md),
  [đối chiếu từng frame](keyframe_evidence_review.md).
- [Review sửa bằng chứng B0 r2](b0_wf0005_r2_review.md),
  [hướng dẫn kiểm nhãn](../data/eval/README.md),
  [phiếu 20 câu phủ định trên corpus mở rộng](../data/eval/reviews/20261012_expanded/README.md).
- [Hợp đồng feedback đang triển khai](team2_feedback_contract.md).

Các hồ sơ này lưu căn cứ và quyết định từng thời điểm. Nhãn review nguồn, nhãn gold
và chấm nghĩa đáp án có phạm vi riêng; không dùng thay cho nhau.

## Kết quả và chẩn đoán theo thời điểm

- [Run 20261012 — corpus mở rộng](../benchmarks/knowflow_expanded_dev/README.md),
  [tiến độ và phân tích lỗi](expanded_dev_retrieval_progress.md).
- [Run 20261011 — 66 câu](../benchmarks/results/20261011_real_dev/REPORT.md):
  giữ nguyên đầu ra, cấu hình và hash của lượt đo cũ.
- [Retrieval tháng 9](retrieval_eval_real_dev.md), [cổng liên quan](retrieval_relevance_gate.md),
  [alias SMTC](retrieval_smtc_alias_fix.md), [kiểm tra sau mở rộng](retrieval_dev_expansion_check.md).
- Worklist cũ: [gold real/dev](gold_review_worklist_real_dev.md),
  [sàng lọc nguồn WF_0002/WF_0003](review_worklist_real_wf_0002_0003.md).
  Đây là hồ sơ lịch sử; trạng thái hiện tại phải đối chiếu dữ liệu canonical và ledger review.

## Tài liệu lập kế hoạch gốc

Bản Word giữ kế hoạch và phân công ban đầu; tiến độ và corpus hiện tại nằm ở các
tài liệu phía trên.

- [Schema chung](01_Schema_chung_KnowFlow_AI.docx).
- [Đội 1: video, metadata và kho tri thức](02_Plan_doi_1_Video_Metadata_Knowledge_Base.docx).
- [Đội 2: synthetic, RAG và giao diện](03_Plan_doi_2_Synthetic_KB_RAG_LLM.docx).
- [Quy tắc Git/GitHub](../04_Quy_tac_Git_GitHub_KnowFlow_AI.docx).
- [Kế hoạch MVP bốn tuần ban đầu](../KnowFlow_AI_Ke_hoach_A2_4_tuan.docx).
