"""Sinh bo cau hoi synthetic co nhan ky vong (ke hoach doi 2 muc 1.5).

Chay: python scripts/build_synthetic_questions.py

Doc KB o data/synthetic_samples/serving va sinh cau hoi theo dung schema
EvalQuestion cua WP2, nen evaluator chay duoc ngay khong can code moi.

Nguyen tac cua bo nay:
  - Cau hoi la PARAPHRASE co dau, khong chep nguyen van claim (claim khong dau).
  - Gold suy ra tu chinh KB nen dung theo cau truc; mot unit liet ke MOI Step
    tuong duong, vi cung mot cau hanh dong xuat hien o nhieu workflow.
  - Chi lay claim con KHANG DINH duoc: latest revision, lifecycle active,
    support_status=supported. Claim conflict/insufficient khong bao gio lam gold.
  - Nhan van la `draft`: nguoi soan khong duoc tu kiem nhan cua chinh minh.

Bo nay chi de thu phan mem. So do tren day KHONG duoc bao cao chung voi real/dev.
"""

from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "contracts" / "schema"))
sys.path.insert(0, str(ROOT))

from build_synthetic_kb import (  # noqa: E402
    ACTIONS_VI, MANUFACTURER, MODEL_A, MODEL_B, TOPICS_MISSING, TOPICS_VI,
)
from retrieval.evaluation.harness import EvalQuestion  # noqa: E402

KB = ROOT / "data" / "synthetic_samples" / "serving"
OUT = Path(os.environ.get("KNOWFLOW_SYNTHETIC_QA_OUT")
           or ROOT / "data" / "eval" / "synthetic_dev.qa.v0.jsonl")
SEED = 20260918
LABELLER = "t"
SET_VERSION = "synthetic-qa-1.0.0"

# Corpus viet khong dau; cau hoi viet co dau. Day la mot phep thu that cho
# tokenizer bo dau cua WP2, khong phai tien ich trinh bay.
DISPLAY = {
    "bo loc khi": "bộ lọc khí",
    "cam bien vi tri": "cảm biến vị trí",
    "day dai": "dây đai",
    "khoang chua phoi": "khoang chứa phoi",
    "bu long chan de": "bu lông chân đế",
    "cum cap dao": "cụm cấp dao",
    "con truot": "con trượt",
    "duong khi nen": "đường khí nén",
    "o bi": "ổ bi",
    "mam cap": "mâm cặp",
}

QUESTION_FOR_ACTION = {
    ACTIONS_VI[0]: "Tháo nắp che {c} bằng cách nào?",
    ACTIONS_VI[1]: "Dùng gì để lau sạch bề mặt {c}?",
    ACTIONS_VI[2]: "Cần kiểm tra điều gì trên {c} trước khi lắp lại?",
    ACTIONS_VI[3]: "Khi lắp lại {c} thì căn cứ vào đâu để đặt đúng chiều?",
    ACTIONS_VI[4]: "Siết các vít quanh {c} theo thứ tự nào?",
    ACTIONS_VI[5]: "Sau khi lắp {c} xong thì cho máy chạy không tải bao lâu?",
    ACTIONS_VI[6]: "Trước khi chạm vào {c} cần làm gì?",
    ACTIONS_VI[7]: "Trước khi tháo {c} phải đánh dấu gì?",
}

# Cung linh vuc CNC nhung KB khong he co du lieu de tra loi.
# Cot thu hai la trang thai cua tang RETRIEVAL, tach khoi trang thai cau tra loi:
#   "retrieved"             chu the CO trong KB, chi rieng chi tiet duoc hoi la khong co
#                           => retrieval van phai tim ra Step de WP3 tu choi CO CAN CU
#   "insufficient_evidence" chu the khong he co trong KB => dung ra khong tim thay gi
# Quy tac nay la tieu chi nguoi kiem doi chieu duoc, khong phai ghi lai ket qua chay.
OUT_OF_SCOPE = [
    ("Loại mỡ bôi trơn nào được chỉ định cho cụm cấp dao?", "retrieved", "cum cap dao co trong KB"),
    ("Bao nhiêu giờ chạy máy thì phải bảo dưỡng cụm cấp dao một lần?", "retrieved", "cum cap dao co trong KB"),
    ("Khe hở cho phép giữa con trượt và thân hốc dao là bao nhiêu milimet?", "retrieved", "con truot co trong KB"),
    ("Mã phụ tùng của bộ lọc khí thay thế là gì?", "retrieved", "bo loc khi co trong KB"),
    ("Cấp NLGI của mỡ bôi trơn là bao nhiêu?", "insufficient_evidence", "KB khong noi gi ve mo"),
    ("Điện áp nguồn cấp cho tủ điện là bao nhiêu vôn?", "insufficient_evidence", "khong co tu dien"),
    ("Phần mềm điều khiển đang dùng phiên bản nào?", "insufficient_evidence", "khong co phan mem"),
    ("Nhiệt độ môi trường cho phép khi vận hành máy là bao nhiêu?", "insufficient_evidence", "khong co dieu kien moi truong"),
    ("Mã báo lỗi 3099 nghĩa là gì?", "insufficient_evidence", "KB chi co 2066/2067/20.66"),
    ("Quy trình thay pin bộ nhớ của bộ điều khiển thế nào?", "insufficient_evidence", "khong co pin bo nho"),
    ("Cách hiệu chỉnh trục C của máy ra sao?", "insufficient_evidence", "khong co truc C"),
    ("Thời gian bảo hành của cụm cấp dao là bao lâu?", "insufficient_evidence", "khong co thong tin bao hanh"),
]



def disp(comp: str) -> str:
    return DISPLAY.get(comp, comp)


# --- doc KB ------------------------------------------------------------------


def load_corpus() -> tuple[list[dict], dict[str, list[dict]]]:
    """Tra ve (workflow dang phuc vu, chi muc claim_text -> cac Step tuong duong)."""
    workflows = [json.loads(line) for line
                 in (KB / "workflows.jsonl").read_text(encoding="utf-8").splitlines()]
    latest: dict[str, int] = {}
    for wf in workflows:
        latest[wf["workflow_id"]] = max(latest.get(wf["workflow_id"], 0), wf["revision"])
    active = [wf for wf in workflows
              if wf["revision"] == latest[wf["workflow_id"]] and wf["lifecycle"] == "active"]

    index: dict[str, list[dict]] = defaultdict(list)
    for wf in active:
        assertable = {c["claim_id"]: c for c in wf["claims"]
                      if c["support_status"] == "supported" and not c["conflicts_with"]
                      and c["evidence_type"] != "inferred"}
        for step in wf["steps"]:
            for ref in step["fields"].values():
                for cid in ref["claim_ids"]:
                    claim = assertable.get(cid)
                    if claim is None:
                        continue
                    index[claim["text"]].append({
                        "workflow_id": wf["workflow_id"], "revision": wf["revision"],
                        "step_id": step["step_id"], "model": wf["context"]["machine_model"],
                        "title": wf["title"], "language": wf["language"],
                    })
    return active, index


def unit(refs: list[dict]) -> list[dict]:
    return [{"workflow_id": r["workflow_id"], "revision": r["revision"], "step_id": r["step_id"]}
            for r in refs]


# --- dung cau hoi ------------------------------------------------------------

QUESTION_FOR_ACTION_EN = {
    "remove the {comp} cover by hand": "How is the {c} cover removed?",
    "wipe the {comp} surface with a dry cloth": "What is used to wipe the {c} surface?",
    "refit the {comp} in the marked orientation": "How is the correct orientation found when refitting the {c}?",
    "tighten the screws around the {comp} in a cross pattern": "In what order are the screws around the {c} tightened?",
}


class Builder:
    def __init__(self, active: list[dict], index: dict[str, list[dict]]):
        self.active = active
        self.index = index
        self.rows: list[dict] = []
        self.asked: set[tuple[str, str | None]] = set()
        self.rng = random.Random(SEED)

    def add(self, *, question: str, category: str, intent: str, expected_status: str,
            retrieval_status: str, context: dict, gold_units=(), gold_workflows=(),
            language: str = "vi", note: str = "") -> None:
        row = {
            "question_id": f"SQ_{len(self.rows) + 1:03d}",
            "source_type": "synthetic", "dataset_split": "dev", "language": language,
            "category": category, "intent": intent, "question": question, "context": context,
            "expected_status": expected_status, "expected_retrieval_status": retrieval_status,
            "gold_units": [list(u) for u in gold_units], "gold_workflows": list(gold_workflows),
            "label": {"status": "draft", "labeled_by": LABELLER,
                      "note": note or "Sinh tu chinh KB synthetic; cho nguoi khac kiem."},
        }
        EvalQuestion.model_validate(row)          # chan nhan tu mau thuan ngay tai cho
        key = (question, context.get("machine_model"))
        if key in self.asked:
            # Cung cau hoi cung may nhung hai gold khac nhau = mot trong hai thieu Step.
            # Bao loi thay vi de lot vao bo cau hoi.
            raise ValueError(f"cau hoi trung: {question!r} tren {key[1]}")
        self.asked.add(key)
        self.rows.append(row)

    def count(self, category: str) -> int:
        return sum(1 for r in self.rows if r["category"] == category)

    # -- 1. tra loi duoc, hoi chi tiet mot thao tac ---------------------------
    def answered_actions(self, limit: int) -> None:
        candidates = []
        null_texts = {c["text"] for wf in self.active if wf["context"]["machine_model"] is None
                      for c in wf["claims"]}
        for template, ask in QUESTION_FOR_ACTION.items():
            for topic in TOPICS_VI:
                text = f"Nguoi noi cho biet {template.format(comp=topic[2])}."
                refs = self.index.get(text, [])
                if not refs or text in null_texts:
                    continue                      # bo ca dinh toi workflow khong ro model
                # sorted: lap qua set thi thu tu doi theo PYTHONHASHSEED => het tai lap
                for model in sorted({r["model"] for r in refs if r["model"]}):
                    same = [r for r in refs if r["model"] == model]
                    candidates.append((ask.format(c=disp(topic[2])), topic, model, same))
        self.rng.shuffle(candidates)
        taken = 0
        for question, topic, model, refs in candidates:
            if taken >= limit:
                break
            if (question, model) in self.asked:
                continue      # nhom song ngu da hoi cau nay voi gold day du hon
            taken += 1
            self.add(question=question, category="tra_loi_duoc", intent="detail",
                     expected_status="answered", retrieval_status="retrieved",
                     context={"manufacturer": MANUFACTURER, "machine_model": model,
                              "subsystem": "tool_changer", "components": [topic[3]]},
                     gold_units=[unit(refs)])

    # -- 2. cung cau hoi, khac model => khac dap an --------------------------
    def torque_pairs(self) -> None:
        for topic in TOPICS_VI[:3]:
            comp = topic[2]
            for model in (MODEL_A, MODEL_B):
                text = next((t for t in self.index
                             if t.startswith(f"Nguoi noi cho biet siet {comp} den")
                             and t.endswith(f"tren {model}.")), None)
                if text is None:
                    continue
                self.add(question=f"Trên {model}, siết {disp(comp)} đến bao nhiêu Nm?",
                         category="tra_loi_duoc", intent="detail", expected_status="answered",
                         retrieval_status="retrieved",
                         context={"manufacturer": MANUFACTURER, "machine_model": model,
                                  "subsystem": "tool_changer"},
                         gold_units=[unit(self.index[text])],
                         note="Con so khac nhau giua hai model; day la ban co model nen tra loi duoc.")
            # cung cau hoi nhung KHONG neu model: du kien quyet dinh bi thieu
            self.add(question=f"Siết {disp(comp)} đến bao nhiêu Nm?",
                     category="thieu_boi_canh", intent="detail",
                     expected_status="needs_clarification", retrieval_status="needs_clarification",
                     context={"manufacturer": MANUFACTURER, "subsystem": "tool_changer"},
                     note=f"{MODEL_A} va {MODEL_B} co tri so khac nhau nen phai hoi lai model.")

    # -- 3. nguon that su thieu phan ly do ------------------------------------
    def missing_rationale(self, limit: int) -> None:
        added = 0
        for wf in self.active:
            if added >= limit or not wf["workflow_id"].startswith("SYN_KB_MISS"):
                continue
            model = wf["context"]["machine_model"]
            comp = next((t[2] for t in (*TOPICS_VI, *TOPICS_MISSING)
                         if t[1] in wf["title"]), None)
            if comp is None:
                continue
            # Chi hoi khi KHONG workflow nao cung pham vi model co rationale cho comp do:
            # neu noi khac da giai thich thi cau tra loi dung phai la answered.
            elsewhere = any(
                c["role"] == "rationale" and comp in c["text"]
                for other in self.active if other["context"]["machine_model"] in (model, None)
                for c in other["claims"]
            )
            if elsewhere:
                continue
            claims = {c["claim_id"]: c for c in wf["claims"]}
            for step in wf["steps"]:
                if added >= limit or step["fields"]["rationale"]["state"] != "missing":
                    continue
                action_ids = step["fields"]["action"]["claim_ids"]
                if not action_ids:
                    continue
                act = claims[action_ids[0]]["text"].replace("Nguoi noi cho biet ", "").rstrip(".")
                self.add(question=f"Vì sao phải {act}?", category="thieu_evidence", intent="detail",
                         expected_status="insufficient_evidence", retrieval_status="retrieved",
                         context={"manufacturer": MANUFACTURER, "machine_model": model,
                                  "subsystem": "tool_changer"},
                         gold_units=[unit([{"workflow_id": wf["workflow_id"],
                                            "revision": wf["revision"], "step_id": step["step_id"]}])],
                         note="Nguon neu thao tac nhung khong neu ly do: retrieval van phai tim ra "
                              "Step de WP3 tu choi CO CAN CU, khong phai im lang.")
                added += 1

    # -- 4. hoi ngoai pham vi KB ---------------------------------------------
    def out_of_scope(self) -> None:
        for question, retrieval_status, why in OUT_OF_SCOPE:
            self.add(question=question, category="khong_co_dap_an", intent="detail",
                     expected_status="insufficient_evidence",
                     retrieval_status=retrieval_status,
                     context={"manufacturer": MANUFACTURER, "machine_model": MODEL_A,
                              "subsystem": "tool_changer"},
                     note=f"KB khong co du lieu tra loi ({why}). Co neu model de phep tu choi la vi "
                          "thieu NOI DUNG, khong phai vi thieu metadata.")

    # -- 5. hai nguon noi khac nhau -------------------------------------------
    def conflicts(self) -> None:
        for wf in self.active:
            pairs = [c for c in wf["claims"] if c["conflicts_with"]]
            if not pairs:
                continue
            comp = next((t[2] for t in TOPICS_VI if t[2] in pairs[0]["text"]), None)
            if comp is None:
                continue
            for question in (f"Siết {disp(comp)} bao nhiêu vòng?",
                             f"Số vòng siết {disp(comp)} là bao nhiêu?",
                             f"Khi lắp {disp(comp)} thì vặn mấy vòng là đủ?"):
                self.add(question=question, category="nguon_mau_thuan",
                         intent="detail", expected_status="conflicting_sources",
                         retrieval_status="conflicting_sources",
                         context={"manufacturer": MANUFACTURER,
                                  "machine_model": wf["context"]["machine_model"],
                                  "subsystem": "tool_changer"},
                         note="Hai nguon noi bon vong va sau vong: phai trung ca hai, khong duoc "
                              "am tham chon mot ben va khong duoc de xuat thao tac.")

    # -- 6. hoi ca quy trinh --------------------------------------------------
    def procedures(self, limit: int) -> None:
        seen: set[tuple[str, str]] = set()
        for wf in self.active:
            if len(seen) >= limit:
                break
            topic = next((t for t in TOPICS_VI if t[1] in wf["title"]), None)
            model = wf["context"]["machine_model"]
            if topic is None or model is None or (topic[0], model) in seen:
                continue
            seen.add((topic[0], model))
            # Nhieu workflow cung mo ta mot quy trinh tren cung model: chap nhan bat ky ban nao.
            acceptable = [{"workflow_id": o["workflow_id"], "revision": o["revision"]}
                          for o in self.active
                          if topic[1] in o["title"] and o["context"]["machine_model"] == model]
            self.add(question=f"Quy trình {topic[1].lower()} trên {model} gồm những bước nào?",
                     category="quy_trinh", intent="procedure", expected_status="answered",
                     retrieval_status="retrieved",
                     context={"manufacturer": MANUFACTURER, "machine_model": model,
                              "subsystem": "tool_changer"},
                     gold_workflows=acceptable,
                     note="Chon dung mot workflow roi tra cac buoc theo thu tu; khong duoc ghep "
                          "buoc cua nhieu quy trinh thanh mot.")

    # -- 7. corpus tieng Anh va cau hoi tieng Viet tren do --------------------
    # Bang tuong duong duoc viet ra de nguoi kiem doi chieu duoc, khong suy doan ngam.
    ALIGN = ((0, 0), (1, 1))            # (chi so TOPICS_EN, chi so TOPICS_VI)
    ALIGN_ACT = ((0, 0), (1, 1), (2, 3), (3, 4))   # (chi so ACTIONS_EN, chi so ACTIONS_VI)

    def cross_language(self) -> None:
        from build_synthetic_kb import ACTIONS_EN, TOPICS_EN

        for en_i, vi_i in self.ALIGN:
            en_topic, vi_topic = TOPICS_EN[en_i], TOPICS_VI[vi_i]
            for a_en, a_vi in self.ALIGN_ACT:
                en_text = f"The speaker says to {ACTIONS_EN[a_en].format(comp=en_topic[2])}."
                en_refs = self.index.get(en_text, [])
                if not en_refs:
                    continue
                vi_text = f"Nguoi noi cho biet {ACTIONS_VI[a_vi].format(comp=vi_topic[2])}."
                vi_refs = self.index.get(vi_text, [])

                model = en_refs[0]["model"]
                same_model = [r for r in en_refs + vi_refs if r["model"] in (model, None)]
                self.add(question=QUESTION_FOR_ACTION_EN[ACTIONS_EN[a_en]].format(c=en_topic[2]),
                         category="corpus_tieng_anh", intent="detail", expected_status="answered",
                         retrieval_status="retrieved", language="en",
                         context={"manufacturer": MANUFACTURER, "machine_model": model,
                                  "subsystem": "tool_changer"},
                         gold_units=[unit([r for r in en_refs if r["model"] in (model, None)])],
                         note="Claim tieng Anh giu nguyen ngon ngu nguon (D-03).")

                # Cau hoi tieng Viet, noi dung nam o corpus tieng Anh: mot unit gom ca hai
                # ban vi tim duoc ban nao cung la tra loi duoc cho nguoi hoi.
                self.add(question=QUESTION_FOR_ACTION[ACTIONS_VI[a_vi]].format(c=disp(vi_topic[2])),
                         category="viet_hoi_anh", intent="detail", expected_status="answered",
                         retrieval_status="retrieved",
                         context={"manufacturer": MANUFACTURER, "machine_model": model,
                                  "subsystem": "tool_changer"},
                         gold_units=[unit(same_model)],
                         note="Can dich cau hoi sang tieng Anh de tim; bang tuong duong VI-EN o "
                              "Builder.ALIGN. Claim/quote giu nguyen van, khong dich (D-03).")

    # -- 8. model khong ro: quyet dinh chinh sach, khong phai loi nhan --------
    def unknown_model(self) -> None:
        wf = next((w for w in self.active if w["context"]["machine_model"] is None), None)
        if wf is None:
            return
        topic = next((t for t in TOPICS_VI if t[1] in wf["title"]), None)
        for question in (f"Siết {disp(topic[2])} theo thứ tự nào?",
                         f"Quy trình thay {disp(topic[2])} áp dụng cho model nào?"):
            self.add(question=question, category="model_khong_ro", intent="detail",
                     expected_status="needs_clarification", retrieval_status="needs_clarification",
                     context={"manufacturer": MANUFACTURER, "subsystem": "tool_changer"},
                     note="CAN NGUOI CHOT: nguon khong neu model. Coi metadata null la 'chua ro nen "
                          "hoi lai' hay 'van dung duoc' la quyet dinh chinh sach cua doi, "
                          "khong phai loi gan nhan.")


def main() -> int:
    active, index = load_corpus()
    b = Builder(active, index)
    b.cross_language()          # chay truoc: gold cua no gom ca ban tieng Viet lan tieng Anh
    b.answered_actions(limit=40)
    b.torque_pairs()
    b.missing_rationale(limit=20)
    b.out_of_scope()
    b.conflicts()
    b.procedures(limit=12)
    b.unknown_model()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in b.rows),
                   encoding="utf-8", newline="\n")

    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in b.rows:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
        by_status[row["expected_status"]] = by_status.get(row["expected_status"], 0) + 1
    scored = sum(1 for r in b.rows if r["expected_status"] == "answered" and r["intent"] == "detail")
    print(f"{len(b.rows)} cau -> {OUT}")
    print("  theo nhom:  " + ", ".join(f"{k}={v}" for k, v in sorted(by_category.items())))
    print("  theo status:" + ", ".join(f" {k}={v}" for k, v in sorted(by_status.items())))
    print(f"  vao mau so Recall/MRR: {scored}")
    if not 100 <= len(b.rows) <= 150:
        print(f"  CANH BAO: ke hoach muc 1.5 yeu cau 100-150 cau, dang co {len(b.rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
