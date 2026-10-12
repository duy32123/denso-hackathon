"""Expanded-corpus reports with explicit cohorts and paired retrieval costs."""
import csv
import json
from pathlib import Path

from retrieval.evaluation.harness import percentile
from .audit import ROOT
from .report import (ARMS, STAGES, read_jsonl, summarize, paired, costs, call_cost,
                     csv_file, review_sources, percent)


def cohort(question_id):
    return "new_15" if 69 <= int(question_id.split("Q")[-1]) <= 83 else "old_66"


def accounting_calls(events):
    complete = {e["call_id"]: e for e in events if e["kind"] == "provider_call"}
    unfinished = [{**e, "kind": "unfinished_provider_accounting", "ok": False,
                   "error_class": "InterruptedUnfinishedCall", "http_code": None,
                   "usage_metadata": None, "elapsed_ms": None}
                  for e in events if e["kind"] == "provider_call_started" and e["call_id"] not in complete]
    return list(complete.values()) + unfinished, unfinished


def write(run_dir, frozen):
    config = frozen["config"]
    audit = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
    questions = read_jsonl(ROOT / config["questions"])
    rows = read_jsonl(run_dir / "rows.jsonl")
    events = read_jsonl(run_dir / "provider_calls.jsonl")
    calls, unfinished = accounting_calls(events)
    full = [c for c in calls if c["phase"] == "full"]
    groups = {"all_81": {q["question_id"] for q in questions},
              **{name: {q["question_id"] for q in questions if cohort(q["question_id"]) == name}
                 for name in ("old_66", "new_15")}}
    result = {"product_commit": frozen["product_commit"], "config_sha256": frozen["config_sha256"],
              "questions_sha256": audit["questions_sha256"], "corpus_sha256": audit["corpus_files_sha256"],
              "pricing": config["pricing"], "summaries": {}, "by_cohort": {}, "by_language": {},
              "semantic_review_status": "pending_human", "holdout_opened": False, "synthetic_included": False,
              "label_revalidation_pending": bool(config.get("label_revalidation_pending")),
              "unfinished_provider_calls": unfinished,
              "all_experiment_api_cost_including_index_smoke_interruption": costs(calls, config),
              "index_build_cost": {arm: costs([c for c in calls if c["phase"] == "preparation" and c["arm"] == arm], config) for arm in ARMS[:2]},
              "smoke_cost_separate": costs([c for c in calls if c["phase"] == "smoke"], config),
              "AC_shared_retrieval_cost": costs([c for c in full if c["arm"] == "AC_shared_retrieval"], config),
              "AC_shared_retrieval_cost_by_stage": {s: costs([c for c in full if c["arm"] == "AC_shared_retrieval" and c["stage"] == s], config) for s in STAGES},
              "missing_tasks": [{"arm": a, "question_id": q["question_id"]} for a in ARMS for q in questions
                                if not any(r["arm"] == a and r["question_id"] == q["question_id"] for r in rows)]}
    flat = []
    for name, ids in groups.items():
        result["by_cohort"][name] = {}
        for arm in ARMS:
            subset = [r for r in rows if r["arm"] == arm and r["question_id"] in ids]
            own = [c for c in full if c["arm"] == arm and c["question_id"] in ids]
            shared = [c for c in full if c["arm"] == "AC_shared_retrieval" and c["question_id"] in ids] if arm != ARMS[1] else []
            s = summarize(subset, config, len(ids))
            s["cost"] = costs(own, config)
            s["cost_by_stage"] = {stage: costs([c for c in own if c["stage"] == stage], config) for stage in STAGES}
            s["standalone_reference_cost_including_one_shared_retrieval"] = costs(own + shared, config)
            s["cost_interpretation"] = "own measured ledger; AC shared retrieval charged once separately; standalone reference is not additional actual expense"
            component_latency = [r["latency_ms_standalone_component_sum"] for r in subset]
            s["latency_ms_standalone_component_sum"] = {"p50": percentile(component_latency, .5), "p95": percentile(component_latency, .95),
                                                       "denominator": len(component_latency), "observed_end_to_end": False,
                                                       "note": "observed HTTP plus original shared retrieval when replayed; do not claim graph latency gain"}
            result["by_cohort"][name][arm] = s
            if name == "all_81":
                result["summaries"][arm] = s
            flat.append({"cohort": name, "arm": arm, "planned": len(ids), "recorded": len(subset), "completed": s["completed"],
                         "status_correct": s["status_accuracy"]["numerator"], "status_denominator": len(ids),
                         "status_accuracy": s["status_accuracy"]["rate"], "false_answer": len(s["false_answer"]),
                         "false_abstention": len(s["false_abstention"]), "api_errors": len(s["api_errors"]),
                         "recall_at_5": s["retrieval"]["recall_at_5"], "mrr_at_5": s["retrieval"]["mrr_at_5"],
                         "retrieval_denominator": s["retrieval"]["denominator"],
                         "valid_citations": s["citation_mechanical_validity"]["numerator"],
                         "citation_denominator": s["citation_mechanical_validity"]["denominator"],
                         "observed_http_p50_ms": s["latency_ms_all_attempts"]["p50"], "observed_http_p95_ms": s["latency_ms_all_attempts"]["p95"],
                         "standalone_component_sum_p50_ms": s["latency_ms_standalone_component_sum"]["p50"],
                         "standalone_component_sum_p95_ms": s["latency_ms_standalone_component_sum"]["p95"],
                         "api_cost_usd": s["cost"]["standard_list_price_usd"],
                         "known_cost_subtotal_usd": s["cost"]["known_list_price_subtotal_usd"], "human_semantic_reviewed": 0,
                         "source_supported": None, "conditions_correct": None})
    for arm in ARMS:
        result["by_language"][arm] = {lang: summarize([r for r in rows if r["arm"] == arm and r["language"] == lang], config,
                                   sum(q["language"] == lang for q in questions)) for lang in ("vi", "en")}
    result["paired_A_B"], result["paired_A_C"] = paired(rows, ARMS[0], ARMS[1]), paired(rows, ARMS[0], ARMS[2])
    pair_meta = {arm: {r["question_id"]: r.get("shared_retrieval") for r in rows if r["arm"] == arm} for arm in (ARMS[0], ARMS[2])}
    mismatches = [qid for qid in pair_meta[ARMS[0]].keys() & pair_meta[ARMS[2]].keys()
                  if not pair_meta[ARMS[0]][qid] or not pair_meta[ARMS[2]][qid] or any(
                      pair_meta[ARMS[0]][qid][key] != pair_meta[ARMS[2]][qid][key]
                      for key in ("key", "result_sha256", "pre_graph_sha256", "translation_sha256", "error_class"))]
    if mismatches:
        raise ValueError(f"A/C pre-ablation pairing mismatches: {mismatches}")
    result["paired_A_C"]["pre_ablation_mismatches"] = mismatches
    (run_dir / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_file(run_dir / "summary.csv", list(flat[0]), flat)
    per_question = []
    for r in rows:
        own = [c for c in full if c["arm"] == r["arm"] and c["question_id"] == r["question_id"]]
        expense = costs(own, config)
        per_question.append({**r, "cohort": cohort(r["question_id"]), "answer": r["response"].get("answer"),
                             "citations_json": json.dumps(r["response"].get("citations", []), ensure_ascii=False),
                             "api_cost_usd": expense["standard_list_price_usd"], "known_subtotal_usd": expense["known_list_price_subtotal_usd"],
                             "provider_call_count": len(own), "shared_provider_call_ids": json.dumps((r.get("shared_retrieval") or {}).get("provider_call_ids", [])),
                             **{k: expense[k] for k in ("input_tokens", "output_tokens", "total_tokens")}})
    csv_file(run_dir / "per_question.csv", ["cohort", "arm", "question_id", "question", "language", "expected_status", "expected_retrieval_status", "status", "http_status", "answer", "citations_json", "answer_sha256", "status_ok", "false_answer", "false_abstention", "recall_at_5", "reciprocal_rank_at_5", "latency_ms", "latency_ms_standalone_component_sum", "latency_interpretation", "model", "api_cost_usd", "known_subtotal_usd", "provider_call_count", "input_tokens", "output_tokens", "total_tokens", "shared_provider_call_ids"], per_question)
    csv_file(run_dir / "api_calls.csv", ["phase", "arm", "question_id", "call_id", "stage", "model", "operation", "started_at", "elapsed_ms", "ok", "http_code", "error_class", "input_tokens", "output_tokens", "billed_output_tokens", "total_tokens", "standard_list_price_usd", "input_sha256"], [{**c, "standard_list_price_usd": call_cost(c, config)} for c in calls])
    review = [{"arm": r["arm"], "question_id": r["question_id"], "answer_sha256": r["answer_sha256"],
               "question": r["question"], "expected_status": r["expected_status"], "status": r["status"], "answer": r["response"].get("answer"),
               "citations_json": json.dumps(r["response"].get("citations", []), ensure_ascii=False), "sources_json": json.dumps(review_sources(r), ensure_ascii=False),
               **{k: "" for k in ("reviewer_kind", "reviewer_id", "reviewed_at", "answers_question", "conditions_correct", "source_supported", "citations_supported_json", "note")}} for r in rows]
    review_path = run_dir / "human_review.csv"
    if not review_path.exists():
        if review:
            csv_file(review_path, list(review[0]), review)
    else:
        with review_path.open(encoding="utf-8-sig", newline="") as stream:
            existing = {(r["arm"], r["question_id"]): r for r in csv.DictReader(stream)}
        missing = []
        for r in review:
            old = existing.get((r["arm"], r["question_id"]))
            if old and old["answer_sha256"] != (r["answer_sha256"] or "null"):
                raise ValueError("Stale review hash; decisions preserved")
            if not old:
                missing.append(r)
        if missing:
            with review_path.open("a", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(missing[0]))
                writer.writerows(missing)
    (run_dir / "review_instructions.md").write_text("# Chấm nghĩa độc lập\n\nGiữ arm/question_id/answer_sha256. Điền reviewer_kind=human chỉ khi người thật đối chiếu toàn nguồn, câu hỏi và điều kiện. AI hỗ trợ ghi ai. Verifier trong pipeline không phải evaluator. Các cột answers_question/conditions_correct/source_supported là true/false; citations_supported_json có một true/false cho mỗi citation. Lỗi API không tự chuyển thành đáp án sai nghĩa. Không thay gold hay sinh lại đáp án.\n", encoding="utf-8")
    verdict_path = run_dir / "semantic_verdicts.jsonl"
    if not verdict_path.exists():
        verdict_path.write_text("", encoding="utf-8")
    semantic_path = run_dir / "semantic_review_summary.json"
    if not semantic_path.exists():
        from .review import import_reviews
        _, semantic_summary = import_reviews(rows, [])
        semantic_path.write_text(json.dumps(semantic_summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# KnowFlow: benchmark corpus mở rộng sau PR #53", "", f"Commit `{frozen['product_commit']}`; {len(questions)} câu, {len(rows)}/{len(questions)*3} terminal rows.", "",
             "## Kết quả theo cohort", "", "| Cohort | Arm | Đúng status | Recall@5 / MRR@5 (n) | API lỗi | False answer / abstention |", "|---|---|---:|---|---:|---:|"]
    for entry in flat:
        lines.append(f"| {entry['cohort']} | {entry['arm']} | {entry['status_correct']}/{entry['planned']} | {percent(entry['recall_at_5'])} / {percent(entry['mrr_at_5'])} ({entry['retrieval_denominator']}) | {entry['api_errors']} | {entry['false_answer']} / {entry['false_abstention']} |")
    lines += ["", "## Phương pháp và nhãn", "", "66 câu cũ, 15 câu mới (Q069–Q083) được báo riêng. 40 câu Vietnamese/hard draft tách file, không chạy/cộng vào kết quả này. Phiếu human review nhãn phủ định, hash trước/sau và label_changes.jsonl được pin trong cấu hình. Expected retrieval và expected answer là hai phép kiểm riêng; Recall/MRR chỉ chấm answered/detail có gold Step, không chấm raw chunks của B.", "",
              "A/B dùng cùng nguồn, model, output/context budget, ngôn ngữ và chính sách nguồn/citation. B chunk corrected captions/Source.raw_text, không nhận Step/claim/relations/gold. A có annotation keyframe, metadata bước và hard filters; khác biệt này không thể quy hết cho graph.", "",
              "A/C chạy QAService qua API; chỉ một retrieval thật mỗi câu được lưu với hash. C tái sử dụng đúng bản dịch/embedding/ứng viên trước khi bỏ relations/related_steps/related_claims. Không chạy lại retrieval để chọn kết quả đẹp hơn. Nếu retrieval lỗi, cả cặp giữ lỗi đó. Generation/verifier chạy độc lập, temperature=0 không bảo đảm tất định. Product chưa đưa related_claims vào generation candidates; phạm vi graph intervention hữu ích ở prompt là relations.", "",
              f"A/C: {json.dumps(result['paired_A_C'], ensure_ascii=False)}", "", f"A/B: {json.dumps(result['paired_A_B'], ensure_ascii=False)}", "",
              "## Latency và chi phí", "", "latency_ms là HTTP quan sát thật, bao gồm retry. Arm A/C replay trừ thời gian retrieval gốc khỏi timeout endpoint để giữ tổng deadline 90s như arm đầu/B; effective_api_timeout_seconds lưu từng câu. HTTP arm replay ngắn hơn về retrieval; không dùng chênh này để khẳng định graph tăng/giảm latency. latency_ms_standalone_component_sum cộng lại thời gian retrieval gốc cho arm replay: đây là tổng thành phần tái dựng, không phải latency toàn luồng quan sát trong deployment. p50/p95 của cả hai được báo riêng trong summary.csv, giữ lỗi/timeouts.", "",
              "Chi phí shared retrieval ghi một lần dưới AC_shared_retrieval, tách khỏi generation/verifier của A/C. standalone_reference_cost cộng shared retrieval cho mỗi arm chỉ để tham chiếu một tác vụ độc lập, không cộng hai lần vào chi phí thí nghiệm. Call mới có journal started trước khi gọi provider; started chưa có completion được giữ là InterruptedUnfinishedCall, token/cost/elapsed=null, không coi là miễn phí. Build index và smoke tách riêng. Token/giá/chi phí chưa biết là null; hóa đơn thực, server, extraction/preprocessing và công chuyên gia chưa đo. Giá standard là quy đổi từ usage, không phải hóa đơn.", "",
              f"Tổng known subtotal thí nghiệm: ${result['all_experiment_api_cost_including_index_smoke_interruption']['known_list_price_subtotal_usd']:.6f}; tổng đầy đủ {result['all_experiment_api_cost_including_index_smoke_interruption']['standard_list_price_usd']}.", "",
              f"Giá tra {config['pricing']['checked_date']}: [Gemini official pricing]({config['pricing'][config['answer_model']]['url']}). Exact embedding-001 rate chưa xác minh, giữ null.", "",
              "## Lỗi, ngôn ngữ và hồi quy", ""]
    for arm in ARMS:
        s = result["summaries"][arm]
        lines += [f"### {arm}", "", f"- API errors: {json.dumps(s['api_errors'], ensure_ascii=False)}", f"- False answer: {s['false_answer']}; false abstention: {s['false_abstention']}."]
        for lang in ("vi", "en"):
            ls = result["by_language"][arm][lang]
            lines.append(f"- {lang}: status {ls['status_accuracy']['numerator']}/{ls['planned_questions']}; lỗi API {len(ls['api_errors'])}.")
        lines.append("")
    lines += ["## Kết luận chưa chứng minh", "", "Code chỉ kiểm ID, revision, link, phạm vi và số trong citation. answers_question/conditions_correct/source_supported/citation correctness đang null, 0 người chấm; không dùng model verifier tự xác nhận. Một lượt A/C với ứng viên giống nhau vẫn chịu biến thiên sinh câu trả lời. Không khẳng định graph vượt RAG, không đổi latency thành thời gian người tiết kiệm, không khẳng định giảm 30% hoặc ROI DENSO. Lượt cũ khác corpus/prompt/pairing, không phải đối chứng causal cho bản sửa này.", "",
              "## Tái lập", "", "```powershell", ".\\.venv\\Scripts\\python.exe -m scripts.review_expanded_dev apply --reviewer-id <human-id>",
              *[f".\\.venv\\Scripts\\python.exe -m scripts.benchmark_knowflow {command} --config benchmarks/knowflow_expanded_dev/config.json --run-dir benchmarks/results/<NEW_RUN>" for command in ("prepare", "smoke", "run", "report")], "```", "",
              f"Config SHA {frozen['config_sha256']}; questions SHA {audit['questions_sha256']}; corpus SHA {audit['corpus_files_sha256']}. Dependency versions và active revisions trong audit.json. Lượt cũ giữ nguyên."]
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if config.get("label_revalidation_pending"):
        report_path = run_dir / "REPORT.md"
        text = report_path.read_text(encoding="utf-8")
        text = text.replace("Phiếu human review nhãn phủ định, hash trước/sau và label_changes.jsonl được pin trong cấu hình.",
                            "Lượt này giữ nguyên 81 nhãn hiện có; 20 nhãn phủ định chưa được người kiểm lại trên corpus mở rộng. Không có label_changes hoặc human approval mới. Xác nhận chạy của người dùng được lưu riêng, không phải review nguồn.")
        banner = "**Nhãn phủ định chưa tái kiểm:** người dùng cho phép chạy trên gold hiện có. Không đánh dấu đề xuất AI thành human-reviewed; không coi status match là chất lượng đáp án đã được người chấm. Kỳ vọng retrieval Q041/Q049 còn cần xác nhận nguồn; expected answer của chúng hiện là insufficient_evidence.\n\n"
        report_path.write_text(banner + text, encoding="utf-8")
    sa = result["summaries"][ARMS[0]]
    (run_dir / "SLIDE.md").write_text("# Số liệu có thể đưa lên slide\n\n"
        f"- Corpus Haas real/dev mở rộng: {len(audit['active_workflows'])} workflow; {len(questions)} câu có nhãn người kiểm, {len(rows)} terminal attempts A/B/C.\n"
        f"- KnowFlow Recall@5 {percent(sa['retrieval']['recall_at_5'])}, n={sa['retrieval']['denominator']}; đây là retrieval, chưa chứng minh đáp án đúng.\n"
        f"- Status đúng A/B/C: {' / '.join(str(result['summaries'][a]['status_accuracy']['numerator']) for a in ARMS)} trên {len(questions)} câu/arm.\n"
        f"- A/C cùng ứng viên: {result['paired_A_C']['same_candidate_pairs']} cặp; không mặc nhiên kết luận graph tốt hơn RAG.\n"
        "- Chấm nghĩa chờ người đối chiếu nguồn; không dùng số liệu này cho giảm 30% thời gian hay ROI.\n", encoding="utf-8")
    if config.get("label_revalidation_pending"):
        slide_path = run_dir / "SLIDE.md"
        slide_path.write_text("**Giới hạn:** giữ nguyên 81 nhãn hiện có; 20 nhãn phủ định chờ kiểm lại trên corpus mới.\n\n" + slide_path.read_text(encoding="utf-8"), encoding="utf-8")
    return result
