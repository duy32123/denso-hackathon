"""Source-authored Vietnamese/contrast cases, kept outside official 81 questions."""
import copy
import json
from pathlib import Path
from retrieval.evaluation.harness import load_questions, check_gold
from retrieval.evaluation.review import build_sheet, write_sheet
from retrieval.indexing.search_index import read_corpus

TRANSLATIONS = [
    "Theo video dịch vụ, alarm 626 xuất hiện khi nào?",
    "Khi xử lý alarm 626, kiểm tra công tắc tiệm cận báo hốc dao lên hoặc xuống bằng cách nào?",
    "Nếu vẫn còn alarm 626 sau các bước kiểm tra thì tôi nên làm gì?",
    "Nguồn nêu các loại dầu hiện hành nào để thay dầu trong bơm bôi trơn trục chính đời cũ?",
    "Nguyên nhân phổ biến nhất khiến trục chính chạy nóng là gì?",
    "Dao bị kẹt trong trục chính: trục chính có thường là nguyên nhân không, và cần xem xét gì?",
    "Điều gì kích hoạt alarm 254 spindle motor overheat?",
    "Trên máy phay đứng, quạt trục chính phải đưa không khí theo hướng nào?",
    "Trên máy có bộ điều khiển next-gen, cáp nối P39 cần có gì?",
    "Alarm 9973 cho biết bo I/O đã thấy trạng thái tiếp điểm nào?",
    "Sau khi tắt máy để kiểm tra alarm 9973, phải chờ dấu hiệu nào trước khi tiếp tục?",
    "Khi alarm 9973 xuất hiện dai dẳng, máy cần bổ sung gì ở đường nguồn điện vào?",
    "Ngay khi tấm che ray way cover bắt đầu kêu lách tách thì nên làm gì?",
    "Nếu gia công không dùng tưới nguội tràn, cần bôi trơn các way cover thế nào?",
    "Lắp way cover trục X kiểu mới lên máy đời cũ cần mũi khoan và tarô nào?",
]
# Five cases per workflow: conditions, missing numbers, component contrasts,
# ordering, and one English hard case. Labels are proposals, not human gold.
HARD = [
    (4, 2, "Theo nguồn alarm 626, khi nào mới thực hiện nhánh kiểm tra sau recovery và các lần thay dao thử?", "condition", "answered"),
    (4, 2, "Trong video alarm 626, áp suất khí tối thiểu chính xác là bao nhiêu bar?", "missing_numeric", "insufficient_evidence"),
    (4, 3, "Video alarm 626 yêu cầu chạm tua vít vào mặt công tắc báo hốc dao; có phải công tắc phải đổi trạng thái không?", "component_contrast", "answered"),
    (4, 1, "Theo video alarm 626, bấm recovery trước hay ra lệnh thay dao nhiều lần trước?", "sequence", "answered"),
    (4, 2, "For alarm 626, does this source specify the exact minimum air flow in litres per minute?", "missing_numeric", "insufficient_evidence"),
    (5, 4, "Khi trục chính có tiếng ồn hoặc rung, việc kiểm độ căng đai áp dụng cho loại truyền động nào?", "condition", "answered"),
    (5, 4, "Video chẩn đoán trục chính nêu độ võng dây đai chính xác bao nhiêu mm?", "missing_numeric", "insufficient_evidence"),
    (5, 3, "Theo video chẩn đoán trục chính chạy nóng, vấn đề thường là quá nhiều hay quá ít dầu tới trục chính?", "component_contrast", "answered"),
    (5, 6, "Nếu hỏng vấu truyền động do lỗi orientation, phải sửa orientation trước hay thay trục chính trước?", "sequence", "answered"),
    (5, 4, "Does this spindle troubleshooting video give the steps for replacing the drive belt, rather than inspecting its tension?", "missing_procedure", "insufficient_evidence"),
    (6, 4, "Với alarm 254, kiểm cáp P39 và ferrite filter áp dụng cho loại bộ điều khiển nào?", "condition", "answered"),
    (6, 1, "Video alarm 254 nêu ngưỡng nhiệt độ kích hoạt cảm biến chính xác bao nhiêu độ C?", "missing_numeric", "insufficient_evidence"),
    (6, 3, "Với alarm 254 trên máy phay ngang, quạt thổi khí ra phía sau đầu trục chính hay phía trên như máy phay đứng?", "component_contrast", "answered"),
    (6, 3, "Trong video alarm 254, quạt cần bật trước hay ngay khi trục chính bắt đầu quay?", "sequence", "answered"),
    (6, 1, "Does alarm 254 in this source concern the spindle motor temperature sensor or the tool-pocket position switches?", "component_contrast", "answered"),
    (7, 5, "Với alarm 9973 chỉ lưu trong history, không hiện màn hình và không dừng máy, nguồn hướng dẫn gì?", "condition", "answered"),
    (7, 2, "Video alarm 9973 yêu cầu chờ chính xác bao nhiêu giây sau tắt nguồn trước khi tháo nắp?", "missing_numeric", "insufficient_evidence"),
    (7, 4, "Với alarm 9973 dai dẳng, nguồn có yêu cầu thay bo I/O hoặc cụm Wye-Delta không?", "component_contrast", "answered"),
    (7, 2, "Theo video alarm 9973, tháo nắp trước hay chờ đèn cảnh báo vector drive tắt trước?", "sequence", "answered"),
    (7, 5, "Should power monitoring be enabled on a machine without Wye-Delta auxiliary contacts and the extra cable?", "condition", "answered"),
    (8, 3, "Trong vận hành bình thường có coolant, way cover được bôi trơn bởi gì; khi cắt không flood cooling thì cần làm gì?", "condition", "answered"),
    (8, 3, "Video way cover quy định nồng độ coolant chính xác bao nhiêu phần trăm?", "missing_numeric", "insufficient_evidence"),
    (8, 6, "Mỡ red-eye trên thanh dẫn way cover trong video có phải là chỉ dẫn chọn mỡ cho con trượt hốc dao không?", "component_contrast", "insufficient_evidence"),
    (8, 4, "Với wiper kiểu mới, nguồn hướng dẫn tháo vít Phillips trước hay gỡ retaining strip khỏi standoffs trước?", "sequence", "answered"),
    (8, 5, "For old-style way covers, does the source use a mallet to seat the wiper or the new-style standoff retaining strip?", "component_contrast", "answered"),
]


def main():
    path = Path("data/eval/haas_real_dev.expanded_vi_hard.draft.jsonl")
    if path.exists():
        raise ValueError("Draft exists; preserve edits and review decisions")
    official = [json.loads(line) for line in Path("data/eval/haas_real_dev.retrieval.v0.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = []
    for original, translation in zip(official[-15:], TRANSLATIONS, strict=True):
        draft = copy.deepcopy(original)
        draft.update(question_id=f"HAAS_DRAFT_VI_{original['question_id'].split('Q')[-1]}", question=translation,
                     language="vi", category="translated_expanded_workflow")
        draft["label"] = {"status": "draft", "labeled_by": "codex-draft", "note":
                          f"AI translation of {original['question_id']}; English human review does not approve this translation. Independently check component identity, answer status and source."}
        rows.append(draft)
    for index, (wf, step, text, category, expected) in enumerate(HARD, 1):
        wid = f"REAL_WF_{wf:04d}"
        rows.append({"question_id": f"HAAS_DRAFT_HARD_{index:03d}", "question": text,
                     "source_type": "real", "dataset_split": "dev", "language": "en" if index % 5 == 0 else "vi",
                     "category": category, "intent": "detail", "context": {},
                     "expected_status": expected, "expected_retrieval_status": "retrieved",
                     "gold_units": [[{"workflow_id": wid, "revision": 1, "step_id": f"{wid}_ST_{step:03d}"}]],
                     "gold_workflows": [], "label": {"status": "draft", "labeled_by": "codex-draft",
                     "note": "Source-authored before running this question. All labels are AI proposals. Missing numeric/procedure and cross-component requests require independent source review; do not count in official metrics."}})
    path.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in rows), encoding="utf-8")
    db = Path("out/web/real_dev_4a18533.sqlite")
    questions, _ = load_questions(path)
    check_gold(questions, read_corpus(db, "real", "dev")["workflows"])
    write_sheet(build_sheet(db, path), Path("data/eval/reviews/20261012_expanded/vi_hard_draft_review.csv"))
    print(json.dumps({"draft_questions": len(rows), "human_reviewed": 0, "official_questions_unchanged": len(official)}))


if __name__ == "__main__":
    main()
