"""Export source-first label review; never approve or change official labels."""
import argparse
import json
from pathlib import Path

from retrieval.evaluation.review import build_sheet, write_sheet, fingerprint, apply_sheet, read_sheet
from retrieval.generation.evidence import EvidenceAccess
from retrieval.indexing.search_index import read_corpus, digest
from scripts.benchmark_knowflow.audit import ROOT, sha_file

SOURCE_CHECKS = {
    32: ([], "Weather is outside this service corpus; check source titles and full transcripts, no CNC claim answers weather."),
    33: (["REAL_WF_0005_ST_002"], "Spindle lubrication pump oil is not spindle gearbox oil; do not transfer pump oil or its replacement advice to the gearbox."),
    34: ([], "No probe calibration on a Haas lathe in this corpus; milling/tool-changer service is a different procedure."),
    35: (["B0_SRC_HAAS_0005_ST_001", "REAL_WF_0001_ST_001"], "The supplied context explicitly names Mazak; all these source workflows are Haas. Keep the manufacturer hard filter, do not transfer the procedure across brands."),
    39: (["REAL_WF_0005_ST_004"], "The provided subsystem=SMTC excludes the new spindle workflow by hard context filter. Keep existing labels for this request; do not silently remove its context to match Q049."),
    40: (["REAL_WF_0005_ST_003"], "A hot spindle/oil troubleshooting passage does not provide a shift-start spindle warm-up routine."),
    41: (["REAL_WF_0008_ST_003"], "Use a refractometer to check coolant concentration is stated; no numeric percentage is specified."),
    42: (["REAL_WF_0006_ST_004"], "A ferrite filter on P39 is not a hydraulic oil filter on a lathe; inspect whole corpus for actual replacement instructions."),
    43: (["REAL_WF_0005_ST_004"], "Spindle balance/alignment is not leveling a relocated machine."),
    44: (["REAL_WF_0008_ST_006"], "Remove chips from linear guides is stated; chip conveyor maintenance is not stated."),
    45: (["REAL_WF_0007_ST_001"], "Incoming-power monitoring is not the control memory battery or its replacement."),
    46: (["REAL_WF_0005_ST_004"], "The source points to a separate spindle balancing video; it does not reproduce a spindle-runout measurement procedure with a dial indicator."),
    47: (["REAL_WF_0004_ST_002"], "Pocket air pressure/volume and kinked air lines are not an air-compressor filter replacement procedure."),
    48: (["REAL_WF_0003_ST_001"], "Tool-change recovery controls are not setting tool offsets; do not let generic control/tool words prove task coverage."),
    49: (["REAL_WF_0005_ST_004"], "The belt-driven condition and tension/cleanliness inspection are stated; a replacement procedure is missing. Related retrieval and answer completeness differ."),
    50: (["REAL_WF_0008_ST_003"], "The provided subsystem=SMTC excludes the new way-cover workflow by hard context filter. Keep existing labels for this request; do not silently remove its context to match Q041."),
    51: (["REAL_WF_0004_ST_002"], "Pocket/carousel inspection is for this side-mount tool changer, not carousel adjustment on an umbrella tool changer."),
    52: (["REAL_WF_0003_ST_007", "REAL_WF_0007_ST_004"], "Double-arm recovery to its home and diagnosing a brownout are not homing machine axes after power failure."),
    53: (["REAL_WF_0008_ST_006"], "Remove chips from linear guides is stated; chip conveyor maintenance is not stated."),
    54: ([], "No tool-length-offset setting with a probe in this source corpus; inspect complete transcripts to confirm absence."),
}


def export(db, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "negative_label_review.csv").exists():
        raise ValueError("Review packet already exists; preserve people's decisions and use a new destination")
    questions_path = ROOT / "data/eval/haas_real_dev.retrieval.v0.jsonl"
    questions = [json.loads(line) for line in questions_path.read_text(encoding="utf-8").splitlines()]
    negatives = [q for q in questions if q["expected_retrieval_status"] == "insufficient_evidence"]
    corpus = read_corpus(db, "real", "dev")
    access = EvidenceAccess(ROOT)
    inventory = []
    for wf in corpus["workflows"].values():
        claims = {c.claim_id: c for c in wf.claims}
        evidence = {e.evidence_id: e for e in wf.evidence}
        for step in wf.steps:
            entries = []
            for field, value in step.fields.model_dump().items():
                for cid in value["claim_ids"]:
                    claim = claims[cid]
                    spans = []
                    for link in claim.evidence_links:
                        ev = evidence[link.evidence_id]
                        src = corpus["sources"][ev.source_id]
                        view = access.view(ev, src)
                        spans.append({"evidence": ev.model_dump(mode="json"), "source_id": src.source_id,
                                      "source_url": src.url, "raw_text": view.text,
                                      "available": view.available})
                    entries.append({"field": field, "claim": claim.model_dump(mode="json"), "spans": spans})
            inventory.append({"workflow_id": wf.workflow_id, "revision": wf.revision,
                              "step_id": step.step_id, "title": step.title, "entries": entries})
    write_sheet([r for r in build_sheet(db, questions_path) if r["question_id"] in
                 {q["question_id"] for q in negatives}], destination / "negative_label_review.csv")
    (destination / "source_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    proposals = []
    for q in negatives:
        number = int(q["question_id"].split("Q")[-1])
        step = ("REAL_WF_0008_ST_003" if number == 41 else
                "REAL_WF_0005_ST_004" if number == 49 else None)
        closest, reason = SOURCE_CHECKS[number]
        proposals.append({"question_id": q["question_id"], "question": q["question"],
                          "fingerprint": fingerprint(q), "original": q,
                          "proposed_expected_status": q["expected_status"],
                          "proposed_expected_retrieval_status": "retrieved" if step else q["expected_retrieval_status"],
                          "candidate_step_id": step, "reviewer_kind": "ai", "human_reviewed": False,
                          "closest_source_step_ids": closest, "reason": reason,
                          "absence_requires_full_source_review": True})
    (destination / "ai_proposals.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in proposals), encoding="utf-8")
    metadata = {"question_file_sha256": sha_file(questions_path), "source_inventory_sha256": sha_file(destination / "source_inventory.json"),
                "reviewed_negatives_on_expanded_corpus": 0, "pending_questions": [q["question_id"] for q in negatives],
                "active_revisions": {wid: w.revision for wid, w in corpus["workflows"].items()},
                "official_gold_changed": False, "holdout_opened": False}
    (destination / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "README.md").write_text("""# Đối chiếu nhãn trên corpus sau PR #53

Đây là phiếu chờ người kiểm. AI không thay nhãn chính thức và không đánh dấu human-reviewed.

1. Đọc `source_inventory.json`: claim, revision, evidence, lời nguồn và URL. Với nhận định nguồn không đủ, đối chiếu cả transcript gốc tương ứng; không chỉ đọc một đoạn đã chọn.
2. Đọc `ai_proposals.jsonl`. Q041 có nguồn kiểm nồng độ nhưng không nêu phần trăm; Q049 có nguồn kiểm dây đai nhưng không có trình tự thay. AI đề xuất retrieval=retrieved, answer=insufficient_evidence cho hai câu này. Q039/Q050 chỉ định subsystem=SMTC, hard filter loại hai workflow mới tương ứng nên đề xuất giữ nhãn; không bỏ context. Người kiểm có thể bác bỏ.
3. Điền `negative_label_review.csv`: `decision=ok/fix`, hai status riêng, gold_step_ids và note. Hai đề xuất trên dùng lần lượt REAL_WF_0008_ST_003 / REAL_WF_0005_ST_004; decision/note hiện để trống. Nếu cần drop, nhóm phải chốt lại phạm vi 81 câu trước khi chạy.
4. Người kiểm thật, khác người soạn, phải xác nhận tất cả dòng trước khi khóa bộ 81 câu cho benchmark. Ghi danh tính và thời điểm; không dùng kết quả engine để phê duyệt gold.

Áp dụng bằng đường review có sẵn (đổi DB nếu chạy ở máy khác):

```powershell
.\\.venv\\Scripts\\python.exe -m scripts.review_expanded_dev apply --db out/web/real_dev_4a18533.sqlite --reviewer-id <github-user>
```

Sau khi áp dụng: lưu diff nhãn và hash cũ/mới, xuất sheet mới, khóa cấu hình; không mở holdout.
""", encoding="utf-8")
    return metadata


def apply(db, destination, reviewer):
    """Apply decisions explicitly submitted by a named human, with corpus guard."""
    if not reviewer or reviewer.lower() in {"codex", "claude", "ai", "codex-draft", "claude-draft"}:
        raise ValueError("Name the real independent human reviewer")
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    path = ROOT / "data/eval/haas_real_dev.retrieval.v0.jsonl"
    if sha_file(path) != manifest["question_file_sha256"]:
        raise ValueError("Questions changed since packet export")
    rows = read_sheet(destination / "negative_label_review.csv")
    if {r["question_id"] for r in rows} != set(manifest["pending_questions"]) or any(
            r["decision"] not in {"ok", "fix"} or not r["note"] for r in rows):
        raise ValueError("All 20 negative labels need ok/fix and a source-based note; dropping changes the 81-question scope")
    before = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    result = apply_sheet(db, path, destination / "negative_label_review.csv", reviewer_id=reviewer, reviewer_kind="human")
    after = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    changes = [{"question_id": old["question_id"], "before": old, "after": new}
               for old, new in zip(before, after, strict=True) if old != new]
    (destination / "label_changes.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in changes), encoding="utf-8")
    approval = {"reviewer_kind": "human", "reviewer_id": reviewer, "apply_result": result,
                "questions_sha256_before": manifest["question_file_sha256"], "questions_sha256_after": sha_file(path),
                "bundle_manifest_sha256": sha_file(ROOT / "acquisition/export/haas_pilot_dev_bundle/manifest.json"),
                "pending_questions": [], "questions": len(after), "changed_label_records": len(changes)}
    (destination / "human_approval.json").write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return approval


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="export", choices=["export", "apply"])
    parser.add_argument("--reviewer-id")
    parser.add_argument("--db", default="out/web/real_dev_4a18533.sqlite")
    parser.add_argument("--destination", default="data/eval/reviews/20261012_expanded")
    args = parser.parse_args()
    print(json.dumps(export(Path(args.db), Path(args.destination)) if args.command == "export" else
                     apply(Path(args.db), Path(args.destination), args.reviewer_id)))
