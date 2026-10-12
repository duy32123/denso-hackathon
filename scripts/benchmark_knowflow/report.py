"""Aggregate journaled attempts, including errors, without rerunning any model."""
import csv
import json
from collections import Counter
from pathlib import Path

from retrieval.evaluation.harness import percentile
from retrieval.indexing.search_index import digest

ARMS = ("A_knowflow", "B_transcript_rag", "C_no_graph")
STAGES = ("embedding_index", "embedding_query", "translation", "answer_generation", "answer_verification")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def percent(value):
    return f"{value * 100:.2f}%" if value is not None else "null"


def measured_sum(values):
    values = list(values)
    return sum(values) if all(v is not None for v in values) else None


def call_cost(call, config):
    if not call.get("ok"):
        return None
    rate = config["pricing"].get(call["model"])
    if not rate or call.get("input_tokens") is None or rate["input_per_million"] is None:
        return None
    cost = call["input_tokens"] * rate["input_per_million"] / 1e6
    if call["operation"] == "generate_content":
        if call.get("billed_output_tokens") is None or rate["output_per_million"] is None:
            return None
        cost += call["billed_output_tokens"] * rate["output_per_million"] / 1e6
        cached = (call.get("usage_metadata") or {}).get("cached_content_token_count")
        if cached and rate.get("cached_input_per_million") is not None:
            cost -= cached * (rate["input_per_million"] - rate["cached_input_per_million"]) / 1e6
    return cost


def costs(calls, config):
    prices = [call_cost(call, config) for call in calls]
    return {"provider_calls": len(calls), "successful_calls": sum(bool(c.get("ok")) for c in calls),
            "failed_calls": sum(not c.get("ok") for c in calls),
            "input_tokens": measured_sum(c.get("input_tokens") for c in calls),
            "output_tokens": measured_sum(c.get("output_tokens") for c in calls),
            "billed_output_tokens": measured_sum(c.get("billed_output_tokens") for c in calls),
            "total_tokens": measured_sum(c.get("total_tokens") for c in calls),
            "known_input_tokens_subtotal": sum(c["input_tokens"] for c in calls if c.get("input_tokens") is not None),
            "known_output_tokens_subtotal": sum(c["output_tokens"] for c in calls if c.get("output_tokens") is not None),
            "usage_known_calls": sum(c.get("input_tokens") is not None and c.get("billed_output_tokens") is not None for c in calls),
            "standard_list_price_usd": measured_sum(prices),
            "known_list_price_subtotal_usd": sum(v for v in prices if v is not None),
            "unknown_cost_calls": sum(v is None for v in prices), "actual_invoice_usd": None}


def observed_retries(row):
    """Retries visible in SDK response hooks or repeated logical calls; network gaps stay explicit."""
    groups = {}
    for call in row["provider_calls"]:
        key = (call["stage"], call["operation"], call["input_sha256"])
        attempts = sum(e["call_id"] == call["call_id"] for e in row["http_attempts"])
        groups[key] = groups.get(key, 0) + max(1, attempts)
    return sum(max(0, n - 1) for n in groups.values())


def infer_guard(row):
    if row["http_status"] != 200:
        return "api_error"
    if row["status"] == "answered":
        return "accepted"
    retrieval = row.get("retrieval")
    if retrieval and retrieval["status"] != "retrieved":
        return "retrieval_" + retrieval["status"]
    if row.get("baseline_guard"):
        return row["baseline_guard"]
    drafts = [c for c in row["provider_calls"] if c["stage"] == "answer_generation" and c.get("ok")]
    verifies = [c for c in row["provider_calls"] if c["stage"] == "answer_verification" and c.get("ok")]
    if drafts:
        try:
            draft = json.loads(drafts[-1]["response_text"])
            if draft.get("status") != "answered" or not draft.get("statements"):
                return "draft_insufficient_evidence"
        except (TypeError, ValueError):
            return "invalid_draft_json"
    if verifies:
        try:
            verdict = json.loads(verifies[-1]["response_text"])
            if not verdict.get("answers_question") or not all(verdict.get("supported", [])):
                return "pipeline_verifier_rejected"
        except (TypeError, ValueError):
            return "invalid_verifier_json"
    return "mechanical_guard_or_procedure_coverage" if drafts else "no_eligible_generation_candidates"


def summarize(rows, config, planned):
    answers = [r for r in rows if r["http_status"] == 200]
    citations = [c for r in rows for c in r["citation_checks"]]
    scored = [r for r in rows if r["retrieval_scored"]]
    calls = [call for row in rows for call in row["provider_calls"]]
    http = [event for row in rows for event in row["http_attempts"]]
    confusion = {}
    for row in rows:
        confusion.setdefault(row["expected_status"], Counter())[row["status"]] += 1
    latency = [r["latency_ms"] for r in rows]
    return {"planned_questions": planned, "recorded_questions": len(rows), "completed": len(answers),
            "not_recorded": planned - len(rows),
            "status_accuracy": ratio(sum(r["status_ok"] for r in rows), planned),
            "answered": sum(r["status"] == "answered" for r in rows),
            "answerable_status_coverage": ratio(sum(r["status"] == "answered" and r["expected_status"] == "answered" for r in rows),
                                                 sum(r["expected_status"] == "answered" for r in rows)),
            "false_answer": [r["question_id"] for r in rows if r["false_answer"]],
            "false_abstention": [r["question_id"] for r in rows if r["false_abstention"]],
            "confusion": {key: dict(value) for key, value in confusion.items()},
            "api_errors": [{"question_id": r["question_id"], "http_status": r["http_status"],
                            "error_class": r["error_class"], "latency_ms": r["latency_ms"]} for r in rows if r["http_status"] != 200],
            "retrieval": {"denominator": len(scored), "gold_kind": "human_reviewed_step_units" if scored else None,
                          "recall_at_5": sum(r["recall_at_5"] for r in scored) / len(scored) if scored else None,
                          "mrr_at_5": sum(r["reciprocal_rank_at_5"] for r in scored) / len(scored) if scored else None,
                          "baseline_limitation": "No human-reviewed raw-chunk gold; Step gold cannot score raw chunks" if rows and rows[0]["arm"] == ARMS[1] else None},
            "citation_mechanical_validity": ratio(sum(c["valid"] for c in citations), len(citations)),
            "citation_failure_codes": dict(Counter(code for c in citations for code in c["failures"])),
            "human_semantics": {"reviewed_questions": 0, "answers_question": None, "conditions_correct": None,
                                "source_supported": None, "citation_correctness": None},
            "latency_ms_all_attempts": {"p50": percentile(latency, .5), "p95": percentile(latency, .95),
                                        "denominator": len(latency), "includes_backoff": True},
            "latency_max_ms": max(latency) if latency else None,
            "latency_anomalies": [{"question_id": r["question_id"], "latency_ms": r["latency_ms"],
                "http_status": r["http_status"], "backoff_seconds": r["backoff_seconds"],
                "provider_call_elapsed_ms": sum(c["elapsed_ms"] for c in r["provider_calls"]),
                "explanation": "Observed latency over twice configured API deadline; cause not established; retained in all metrics"}
                for r in rows if r["latency_ms"] > 2 * config.get("execution", {}).get("api_timeout_seconds", 90) * 1000],
            "latency_ms_successful": {"p50": percentile([r["latency_ms"] for r in answers], .5),
                                      "p95": percentile([r["latency_ms"] for r in answers], .95), "denominator": len(answers)},
            "http_attempts": len(http), "http_status_counts": dict(Counter(str(e["status_code"]) for e in http)),
            "observed_retries": sum(observed_retries(r) for r in rows),
            "provider_timeouts": [{"question_id": r["question_id"], "call_id": c["call_id"], "stage": c["stage"]}
                                   for r in rows for c in r["provider_calls"] if "timeout" in (c.get("error_class") or "").casefold()],
            "backoff_seconds": sum(r["backoff_seconds"] for r in rows),
            "post_timeout_drain_ms": sum(r["post_timeout_drain_ms"] for r in rows if r["http_status"] == 504),
            "pipeline_guard_counts": dict(Counter(infer_guard(r) for r in rows)),
            "leakage": [{"question_id": r["question_id"], "codes": r["leakage"]} for r in rows if r["leakage"]],
            "cost": costs(calls, config),
            "cost_by_stage": {stage: costs([c for c in calls if c["stage"] == stage], config) for stage in STAGES},
            "known_list_price_usd_per_planned_task": sum(v for c in calls if (v := call_cost(c, config)) is not None) / planned if planned else None,
            "total_api_usd_per_planned_task": measured_sum(call_cost(c, config) for c in calls) / planned
                                               if planned and all(call_cost(c, config) is not None for c in calls) else None}


def candidate_signature(row):
    result = row.get("retrieval")
    if not result or "chunks" in result:
        return None
    # Exclude graph fields and unstable timings/scores; preserve ranked order and content.
    return digest({"status": result["status"], "selected": result["selected_workflow"]["workflow_id"] if result["selected_workflow"] else None,
                   "steps": [(s["workflow_id"], s["revision"], s["step_id"]) for s in result["steps"]],
                   "claims": [(c["claim_ref"], c["text"], c["matched_step_ids"]) for c in result["claims"]],
                   "context": result["context"], "missing_context": result["missing_context"]})


def paired(rows, left, right):
    a = {r["question_id"]: r for r in rows if r["arm"] == left}
    b = {r["question_id"]: r for r in rows if r["arm"] == right}
    common = sorted(a.keys() & b.keys())
    candidates_same = [q for q in common if candidate_signature(a[q]) is not None
                       and candidate_signature(a[q]) == candidate_signature(b[q])]
    return {"paired_questions": len(common),
            "left_only_status_correct": [q for q in common if a[q]["status_ok"] and not b[q]["status_ok"]],
            "right_only_status_correct": [q for q in common if b[q]["status_ok"] and not a[q]["status_ok"]],
            "answer_changed": [q for q in common if a[q]["answer_sha256"] != b[q]["answer_sha256"]],
            "candidate_content_changed": [q for q in common if candidate_signature(a[q]) != candidate_signature(b[q])]
                                          if right == ARMS[2] else None,
            "same_candidate_pairs": len(candidates_same) if right == ARMS[2] else None,
            "same_candidate_left_only_status_correct": [q for q in candidates_same if a[q]["status_ok"] and not b[q]["status_ok"]]
                                                        if right == ARMS[2] else None,
            "same_candidate_right_only_status_correct": [q for q in candidates_same if b[q]["status_ok"] and not a[q]["status_ok"]]
                                                         if right == ARMS[2] else None,
            "graph_exposed_questions": [q for q in common if (a[q].get("retrieval") or {}).get("relations")]
                                          if left == ARMS[0] else None}


def csv_file(path, columns, entries):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for entry in entries:
            # Explicit null is distinct from zero in exported CSVs.
            writer.writerow({key: "null" if entry.get(key) is None else entry.get(key) for key in columns})


def review_sources(row):
    if row["arm"] == ARMS[1]:
        return [chunk for c in row["citation_checks"] for chunk in c.get("source_chunks", [])]
    claims = {c["claim_ref"]["entity_id"]: c for c in (row.get("retrieval") or {}).get("claims", [])}
    sources = []
    for citation in row["citation_checks"]:
        claim = claims.get(citation["claim_ref"]["entity_id"])
        if claim:
            sources.append({"claim_ref": claim["claim_ref"], "claim_text": claim["text"],
                            "evidence": [e for e in claim["evidence"] if e["evidence"]["evidence_id"] in citation["evidence_ids"]]})
    return sources


def write_report(run_dir):
    frozen = json.loads((run_dir / "frozen_config.json").read_text(encoding="utf-8"))
    config = frozen["config"]
    if config.get("benchmark_version") == "2.0.0":
        from .expanded_report import write
        return write(run_dir, frozen)
    audit = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
    rows = read_jsonl(run_dir / "rows.jsonl")
    events = read_jsonl(run_dir / "provider_calls.jsonl")
    summaries = {arm: summarize([r for r in rows if r["arm"] == arm], config, audit["questions"]) for arm in ARMS}
    full_calls = [e for e in events if e["kind"] == "provider_call" and e["phase"] == "full"]
    used_call_ids = {c["call_id"] for r in rows for c in r["provider_calls"]}
    interrupted_calls = [c for c in full_calls if c["call_id"] not in used_call_ids]
    interruption_path = run_dir / "interruption_journal.json"
    interruption = json.loads(interruption_path.read_text(encoding="utf-8")) if interruption_path.exists() else None
    # Quality denominators count planned tasks; expense includes interrupted calls too.
    for arm, s in summaries.items():
        arm_calls = [c for c in full_calls if c["arm"] == arm]
        s["cost"] = costs(arm_calls, config)
        s["cost_by_stage"] = {stage: costs([c for c in arm_calls if c["stage"] == stage], config) for stage in STAGES}
        s["known_list_price_usd_per_planned_task"] = s["cost"]["known_list_price_subtotal_usd"] / audit["questions"]
        s["total_api_usd_per_planned_task"] = s["cost"]["standard_list_price_usd"] / audit["questions"] if s["cost"]["standard_list_price_usd"] is not None else None
        s["interrupted_provider_call_ids"] = [c["call_id"] for c in interrupted_calls if c["arm"] == arm]
        s["unmeasured_interrupted_latency_ms"] = None if interruption and interruption["unfinished_task"]["arm"] == arm else 0
    index_calls = [e for e in events if e["kind"] == "provider_call" and e["phase"] == "preparation"]
    smoke_calls = [e for e in events if e["kind"] == "provider_call" and e["phase"] == "smoke"]
    preflight_path = run_dir / "provider_preflight.json"
    preflight_calls = []
    if preflight_path.exists():
        for model, probe in json.loads(preflight_path.read_text(encoding="utf-8")).items():
            usage = probe.get("usage") or {}
            total, inputs = usage.get("total_token_count"), usage.get("prompt_token_count")
            preflight_calls.append({"ok": probe.get("ok"), "model": model,
                "operation": "embed_content" if "embedding" in model else "generate_content",
                "input_tokens": inputs, "output_tokens": usage.get("candidates_token_count"),
                "billed_output_tokens": total-inputs if total is not None and inputs is not None else None,
                "total_tokens": total, "usage_metadata": usage})
    result = {"product_commit": frozen["product_commit"], "config_sha256": frozen["config_sha256"],
              "questions_sha256": audit["questions_sha256"], "corpus_sha256": audit["corpus_files_sha256"],
              "summaries": summaries, "paired_A_B": paired(rows, ARMS[0], ARMS[1]),
              "paired_A_C": paired(rows, ARMS[0], ARMS[2]),
              "index_build_cost": {arm: costs([c for c in index_calls if c["arm"] == arm], config) for arm in ARMS[:2]},
              "smoke_cost_separate": costs(smoke_calls, config), "pricing": config["pricing"],
              "provider_availability_probe_cost_separate": costs(preflight_calls, config),
              "all_experiment_api_cost_including_index_smoke_probe_interruption": costs(index_calls + smoke_calls + full_calls + preflight_calls, config),
              "missing_tasks": [{"arm": arm, "question_id": q["question_id"]} for arm in ARMS
                 for q in read_jsonl(Path(config["questions"]))
                 if not any(r["question_id"] == q["question_id"] and r["arm"] == arm for r in rows)],
              "semantic_review_status": "pending_human", "synthetic_included": False, "holdout_opened": False,
              "interruption_journal": interruption,
              "interrupted_calls_cost_included": [c["call_id"] for c in interrupted_calls]}
    result["by_language"] = {arm: {language: summarize([r for r in rows if r["arm"] == arm and r["language"] == language],
                              config, audit["languages"][language]) for language in ("vi", "en")} for arm in ARMS}
    question_language = {q["question_id"]: q["language"] for q in read_jsonl(Path(config["questions"]))}
    for arm in ARMS:
        for language in ("vi", "en"):
            language_calls = [c for c in full_calls if c["arm"] == arm and question_language[c["question_id"]] == language]
            language_summary = result["by_language"][arm][language]
            language_summary["cost"] = costs(language_calls, config)
            language_summary["cost_by_stage"] = {stage: costs([c for c in language_calls if c["stage"] == stage], config) for stage in STAGES}
            language_summary["known_list_price_usd_per_planned_task"] = language_summary["cost"]["known_list_price_subtotal_usd"] / audit["languages"][language]
    (run_dir / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    flat = []
    for arm, s in summaries.items():
        flat.append({"arm": arm, "planned": s["planned_questions"], "completed": s["completed"],
                     "api_errors": len(s["api_errors"]), "status_correct": s["status_accuracy"]["numerator"],
                     "status_denominator": s["status_accuracy"]["denominator"], "status_accuracy": s["status_accuracy"]["rate"],
                     "answered": s["answered"], "false_answer": len(s["false_answer"]), "false_abstention": len(s["false_abstention"]),
                     "recall_at_5": s["retrieval"]["recall_at_5"], "mrr_at_5": s["retrieval"]["mrr_at_5"],
                     "retrieval_denominator": s["retrieval"]["denominator"],
                     "valid_citations": s["citation_mechanical_validity"]["numerator"],
                     "citation_denominator": s["citation_mechanical_validity"]["denominator"],
                     "latency_p50_ms": s["latency_ms_all_attempts"]["p50"], "latency_p95_ms": s["latency_ms_all_attempts"]["p95"],
                     "latency_denominator": s["latency_ms_all_attempts"]["denominator"],
                     "api_cost_usd": s["cost"]["standard_list_price_usd"],
                     "known_cost_subtotal_usd": s["cost"]["known_list_price_subtotal_usd"],
                     "known_usd_per_task": s["known_list_price_usd_per_planned_task"],
                     "api_usd_per_task": s["total_api_usd_per_planned_task"], "human_semantic_reviewed": 0})
    csv_file(run_dir / "summary.csv", list(flat[0]), flat)
    calls_by_task = {(arm, qid): [c for c in full_calls if c["arm"] == arm and c["question_id"] == qid]
                     for arm, qid in {(r["arm"], r["question_id"]) for r in rows}}
    csv_file(run_dir / "per_question.csv", ["arm", "question_id", "question", "language", "expected_status", "status",
             "http_status", "status_ok", "false_answer", "false_abstention", "recall_at_5", "reciprocal_rank_at_5",
             "latency_ms", "backoff_seconds", "model", "answer_sha256", "api_cost_usd", "known_subtotal_usd", "provider_call_count",
             "observed_retry_count", "embedding_calls", "translation_calls", "generation_calls", "verification_calls",
             "input_tokens", "output_tokens", "total_tokens", "interrupted_prior_provider_calls",
             "latency_total_including_interruption_ms"],
             [{**r, "api_cost_usd": costs(calls_by_task[(r["arm"], r["question_id"])], config)["standard_list_price_usd"],
               "known_subtotal_usd": costs(calls_by_task[(r["arm"], r["question_id"])], config)["known_list_price_subtotal_usd"],
               "provider_call_count": len(calls_by_task[(r["arm"], r["question_id"])]), "observed_retry_count": observed_retries(r),
               "embedding_calls": sum(c["stage"] == "embedding_query" for c in calls_by_task[(r["arm"], r["question_id"])]),
               "translation_calls": sum(c["stage"] == "translation" for c in calls_by_task[(r["arm"], r["question_id"])]),
               "generation_calls": sum(c["stage"] == "answer_generation" for c in calls_by_task[(r["arm"], r["question_id"])]),
               "verification_calls": sum(c["stage"] == "answer_verification" for c in calls_by_task[(r["arm"], r["question_id"])]),
               "interrupted_prior_provider_calls": len(calls_by_task[(r["arm"], r["question_id"])])-len(r["provider_calls"]),
               "latency_total_including_interruption_ms": r["latency_ms"] if len(calls_by_task[(r["arm"], r["question_id"])]) == len(r["provider_calls"]) else None,
               **{field: costs(calls_by_task[(r["arm"], r["question_id"])], config)[field] for field in ("input_tokens", "output_tokens", "total_tokens")}} for r in rows])
    all_calls = [e for e in events if e["kind"] == "provider_call"]
    csv_file(run_dir / "api_calls.csv", ["phase", "arm", "question_id", "call_id", "stage", "model", "operation",
             "started_at", "elapsed_ms", "ok", "http_code", "error_class", "input_tokens", "output_tokens",
             "billed_output_tokens", "total_tokens", "standard_list_price_usd", "input_sha256"],
             [{**c, "standard_list_price_usd": call_cost(c, config)} for c in all_calls])
    review_columns = ["arm", "question_id", "answer_sha256", "question", "expected_status", "status", "answer",
                      "citations_json", "sources_json", "reviewer_kind", "reviewer_id", "reviewed_at",
                      "answers_question", "conditions_correct", "source_supported", "citations_supported_json", "note"]
    review = [{"arm": r["arm"], "question_id": r["question_id"], "answer_sha256": r["answer_sha256"],
               "question": r["question"], "expected_status": r["expected_status"], "status": r["status"],
               "answer": r["response"].get("answer"), "citations_json": json.dumps(r["response"].get("citations", []), ensure_ascii=False),
               "sources_json": json.dumps(review_sources(r), ensure_ascii=False), "reviewer_kind": "", "reviewer_id": "",
               "reviewed_at": "", "answers_question": "", "conditions_correct": "", "source_supported": "",
               "citations_supported_json": "", "note": ""} for r in rows]
    review_path = run_dir / "human_review.csv"
    if not review_path.exists():
        csv_file(review_path, review_columns, review)
    elif review:
        # A report may be viewed mid-run. Append new tasks, preserve every existing verdict.
        with review_path.open(encoding="utf-8-sig", newline="") as stream:
            existing = list(csv.DictReader(stream))
        keys = {(r["arm"], r["question_id"]): r for r in existing}
        with review_path.open("a", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=review_columns)
            for r in review:
                key = (r["arm"], r["question_id"])
                if key not in keys:
                    writer.writerow({k: "null" if v is None else v for k, v in r.items()})
                elif keys[key]["answer_sha256"] != (r["answer_sha256"] or "null"):
                    raise ValueError("Review template has a stale hash; existing verdicts preserved")
    (run_dir / "review_instructions.md").write_text(
        "# Chấm nghĩa độc lập\n\nKhông sửa gold hoặc sinh lại đáp án. Đối chiếu `rows.jsonl`, câu hỏi, điều kiện và nguồn nguyên bản.\n\n"
        "- Mỗi verdict phải giữ `arm`, `question_id`, `answer_sha256`; đáp án đổi thì verdict stale.\n"
        "- Điền `reviewer_kind=human` chỉ khi người thật tự đối chiếu nguồn. AI hỗ trợ phải ghi `ai`, tách riêng.\n"
        "- Điền reviewer, thời điểm, answers_question / conditions_correct / source_supported bằng true hoặc false.\n"
        "- citations_supported_json là mảng true/false có đúng số phần tử và thứ tự citation; điền note cho lỗi.\n"
        "- Xem file transcript/source ở audit.json và mốc thời gian hoặc char offset trong sources_json; không chỉ đọc claim.\n"
        "- Bước verify bằng Gemini là bộ phận hệ thống đang đo, không được tính làm người chấm.\n"
        "- Citation hợp lệ theo code không chứng minh câu trả lời được nguồn hỗ trợ về nghĩa.\n"
        "- Với lỗi API, không chấm nghĩa một đáp án không tồn tại; giữ lỗi trong mẫu số 66.\n",
        encoding="utf-8")
    lines = ["# KnowFlow real/dev benchmark", "", "## Phạm vi", "",
             f"Product commit `{frozen['product_commit']}`; nhánh benchmark riêng, chưa push. Questions={audit['questions']}; languages={audit['languages']}; expected_status={audit['expected_status']}; reviewed={audit['labels']}.",
             "", "A: QAService + API thật, hybrid + dịch + embedding + draft/verify. B: raw transcript/document RAG. C: cùng index/nội dung với A, neighbor_depth=0 và bỏ relations trong kết quả retrieval.",
             "", "Benchmark dựng DB riêng với embedding thật, không sửa database demo/cấu hình/logic sản phẩm. Nếu có existing_serving_state.json, đó là bản đối chiếu chỉ đọc cấu hình hiện hành. Các số mô tả cấu hình benchmark đã khóa, không chứng minh default deployment hiện đã bật đầy đủ AI.",
             "", "## Kết quả bằng code", "",
             "| Arm | Hoàn tất | Đúng status / 66 | Recall@5 (n) | MRR@5 | Trả lời khi thiếu nguồn | Từ chối oan | Citation hợp lệ | p50 / p95 (s) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, s in summaries.items():
        retrieval = s["retrieval"]
        recall = f"{retrieval['recall_at_5']:.4f} ({retrieval['denominator']})" if retrieval["recall_at_5"] is not None else "null — thiếu raw-chunk gold"
        mrr = f"{retrieval['mrr_at_5']:.4f}" if retrieval["mrr_at_5"] is not None else "null"
        latency = s["latency_ms_all_attempts"]
        lat = f"{latency['p50']/1000:.2f} / {latency['p95']/1000:.2f}" if latency["p50"] is not None else "null"
        cites = s["citation_mechanical_validity"]
        lines.append(f"| {arm} | {s['completed']}/66 | {s['status_accuracy']['numerator']}/66 | {recall} | {mrr} | {len(s['false_answer'])} | {len(s['false_abstention'])} | {cites['numerator']}/{cites['denominator']} | {lat} |")
    offline = json.loads((run_dir / "offline_bm25_report.json").read_text(encoding="utf-8"))["strategies"]["lexical"]["retrieval"]
    sa, sb, sc = [summaries[arm] for arm in ARMS]
    ab, ac = result["paired_A_B"], result["paired_A_C"]
    recall_gain = (sa["retrieval"]["recall_at_5"] - offline["recall_at_5"]) * 100 if sa["retrieval"]["recall_at_5"] is not None else None
    lines += ["", "## Kết luận từ lượt đo", "",
              f"- Retrieval A: {percent(sa['retrieval']['recall_at_5'])}, n={sa['retrieval']['denominator']}; BM25 không dịch chạy mới: {percent(offline['recall_at_5'])}, n={offline['questions']}; chênh khoảng {recall_gain} điểm phần trăm. Đây là đối chiếu cấu hình hybrid + embedding + dịch với lexical không dịch; không cô lập riêng embedding hoặc graph.",
              f"- Status A {sa['status_accuracy']['numerator']}/{sa['planned_questions']} ({percent(sa['status_accuracy']['rate'])}), B {sb['status_accuracy']['numerator']}/{sb['planned_questions']} ({percent(sb['status_accuracy']['rate'])}). Cặp A đúng/B sai: {len(ab['left_only_status_correct'])}; B đúng/A sai: {len(ab['right_only_status_correct'])}. Từ chối oan A/B: {len(sa['false_abstention'])}/{len(sb['false_abstention'])}; lỗi API A/B: {len(sa['api_errors'])}/{len(sb['api_errors'])}. Không đổi gold hoặc chọn lại response để đảo kết luận.",
              f"- A/C Recall@5: {percent(sa['retrieval']['recall_at_5'])}/{percent(sc['retrieval']['recall_at_5'])}; MRR: {percent(sa['retrieval']['mrr_at_5'])}/{percent(sc['retrieval']['mrr_at_5'])}. Status: {sa['status_accuracy']['numerator']}/{sc['status_accuracy']['numerator']}. {ac['same_candidate_pairs']} cặp cùng nội dung ứng viên có số thắng status {len(ac['same_candidate_left_only_status_correct'])}–{len(ac['same_candidate_right_only_status_correct'])}; {len(ac['candidate_content_changed'])} cặp khác ứng viên. Một lượt live có biến thiên preprocessing/model chưa chứng minh đóng góp nhân quả của cạnh graph.",
              f"- Trả lời khi gold yêu cầu từ chối A/B/C: {len(sa['false_answer'])}/{len(sb['false_answer'])}/{len(sc['false_answer'])}; IDs lần lượt: {sa['false_answer']}, {sb['false_answer']}, {sc['false_answer']}. Citation code hợp lệ không ngăn lỗi về nghĩa. Không trình bày thành zero hallucination hoặc độ đúng nghĩa 100%.",
              f"- Phần phí standard xác định được A/B/C: ${sa['cost']['known_list_price_subtotal_usd']:.6f}/${sb['cost']['known_list_price_subtotal_usd']:.6f}/${sc['cost']['known_list_price_subtotal_usd']:.6f}. Tổng đầy đủ, trung bình đầy đủ, hóa đơn thực và chi phí expert đều null/chưa đo: chưa chứng minh tiết kiệm tổng chi phí hoặc ROI.",
              f"- Cần người chấm phiếu {len(rows)} dòng để kết luận answers_question, điều kiện và hỗ trợ về nghĩa. Chưa chứng minh hiệu quả tại DENSO, tiết kiệm 30% thời gian người dùng, hoặc ưu thế graph so với RAG."]
    lines += ["", "Status match là đối chiếu nhãn trạng thái đã review; không phải điểm đúng nghĩa của đáp án. Recall/MRR chỉ dùng 37 câu answered/detail; lỗi API giữ trong mẫu số và tính recall=0 nếu retrieval chưa hoàn tất.",
              "", "Latency đo từ POST /v1/ask qua FastAPI TestClient đến HTTP response, gồm backoff và deadline 90s; không gồm mạng Internet của BTC. Các tác vụ timeout vẫn được drain để không trộn telemetry; thời gian drain tách riêng. Lượt bị ngắt không có HTTP response/latency đầy đủ: giữ null, báo riêng ngoài mẫu latency các task kết thúc.",
              "", "Recall là chỉ số thành phần retrieval, tách khỏi thành công HTTP/đáp án. Nếu retrieval đã hoàn tất nhưng generation timeout thì vẫn ghi recall thành phần và status=error. Không coi kết quả background sau deadline là đáp án người dùng đã nhận.",
              "", "## Chi phí", "",
              "Đơn giá standard `gemini-3.5-flash-lite`: $0.30/M input, $2.50/M output gồm thinking; nguồn https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite, tra 2026-10-11. Usage metadata là token thực provider báo; phí dưới đây là quy đổi list-price, không phải hóa đơn. Billing tier/credits và số tiền đã trừ: null.",
              "", "Embedding-001 không trả token trong metadata ở preflight; bảng giá live hiện không có chính xác model này. Giá/token embedding chưa biết giữ null, không dùng giá Embedding 2 hoặc ước lượng ký tự. Tổng đầy đủ và trung bình đầy đủ giữ null khi có khoản chưa đo được.",
              "", "| Arm | Embedding query | Dịch | Sinh | Kiểm | Subtotal đã biết (USD) | Tổng đầy đủ |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for arm, s in summaries.items():
        fields = []
        for stage in STAGES[1:]:
            val = s["cost_by_stage"][stage]["standard_list_price_usd"]
            fields.append(f"${val:.6f}" if val is not None else "null")
        total_text = "null" if s["cost"]["standard_list_price_usd"] is None else f"${s['cost']['standard_list_price_usd']:.6f}"
        lines.append(f"| {arm} | {' | '.join(fields)} | ${s['cost']['known_list_price_subtotal_usd']:.6f} | {total_text} |")
    lines += ["", "Xây index ban đầu và smoke nằm riêng trong summary.json; C dùng lại index A, không có lượt build độc lập. Phí các call của lượt interrupted cũng được cộng, không chỉ các dòng đáp án kết thúc. Chưa tính preprocessing/extraction, nhân công review/chuyên gia, lưu trữ, máy chủ, mạng và thuế.",
              "", "## Công bằng và giới hạn", "",
              "- A/B cùng 5 Source real/dev, model trả lời/dịch/embedding, ngôn ngữ, max output 12000, common payload guard 1MB, temperature 0 và yêu cầu source-only/citation/numbers/semantic verifier. Context không bị cắt để làm đẹp kết quả; chi phí đo cả metadata/prompt overhead.",
              "- A dùng claim và step đã được người kiểm nguồn, workflow routing, identity/relevance gates; B dùng corrected captions và Source.raw_text, chunk 180 từ overlap 30, raw corpus term coverage. B không nhận nhãn bước, claim, relations hoặc gold trong index/prompt. Procedure B chọn một source bằng raw chunk score. Đây là khác biệt preprocessing và routing; A/B không cô lập riêng graph.",
              "- A/C có cả observation_note của keyframe đã kiểm và kiểm độ đầy đủ/thứ tự procedure bằng step metadata. B là baseline văn bản, không có annotation hình ảnh hoặc step metadata; completion/order chỉ được model kiểm trên raw chunks. Không quy những khác biệt này cho cạnh đồ thị.",
              "- Generation A/C đọc observation_note đã gán, không chạy model thị giác trực tiếp trên keyframe ở thời điểm hỏi. Code chỉ kiểm asset mở/giải mã được và ID/link hợp lệ. 134 claim active source_checked, toàn bộ technical_review=not_requested: chưa có xác nhận chuyên gia.",
              "- Adapter embedding/dịch thật được giữ client giữa các câu như evaluator, không cache response; model draft/verify tạo client theo QAService. Default production retrieve tự tạo client embedding/dịch mỗi request. Latency benchmark với client giữ kết nối không chứng minh latency cold deployment; tất cả arm dùng cùng chính sách benchmark này.",
              "- A/C giữ cùng nội dung index kể cả câu chữ relation claim trong text. C chỉ bỏ quan hệ có cấu trúc và mở rộng cạnh ở runtime; không sửa product hoặc corpus. Independent live translation/model calls có thể dao động dù temperature=0; xem paired_A_C và candidate_content_changed.",
              "- Product hiện không đưa related_claims vào candidates của prompt generation; neighbor expansion vẫn xuất hiện ở trace/UI. Vì vậy chưa có cơ sở quy lợi ích đáp án cho mở rộng cạnh.",
              "- Bộ dev đã được dùng để phát triển pipeline trước benchmark. Một lượt chạy, corpus nhỏ, không phải holdout hoặc triển khai DENSO. Không quét tham số, không mở holdout, không cộng synthetic.",
              "- human_review.csv đang chờ người chấm: answers_question, conditions_correct, source_supported, citation_correctness đều null. Không chuyển latency thành thời gian lao động tiết kiệm/ROI.",
              "", "## Lỗi và khác biệt ngôn ngữ", ""]
    for arm in ARMS:
        lines += [f"### {arm}", ""]
        for language in ("vi", "en"):
            subset = [r for r in rows if r["arm"] == arm and r["language"] == language]
            lines.append(f"- {language}: đúng status {sum(r['status_ok'] for r in subset)}/{len(subset)}; false_answer {[r['question_id'] for r in subset if r['false_answer']]}; false_abstention {[r['question_id'] for r in subset if r['false_abstention']]}.")
        lines.append(f"- API errors: {json.dumps(summaries[arm]['api_errors'], ensure_ascii=False)}")
        lines.append(f"- Retry quan sát được: {summaries[arm]['observed_retries']}; HTTP provider status: {summaries[arm]['http_status_counts']}; provider timeout: {summaries[arm]['provider_timeouts']}.")
        lines.append(f"- Latency max ms: {summaries[arm]['latency_max_ms']}; anomalies giữ nguyên trong mẫu: {json.dumps(summaries[arm]['latency_anomalies'], ensure_ascii=False)}.")
        lines.append(f"- Pipeline guard (diagnostic, không phải verdict nghĩa): {json.dumps(summaries[arm]['pipeline_guard_counts'], ensure_ascii=False)}")
        lines.append("")
    lines += ["## Đối chứng", "", f"A/B: {ab['paired_questions']} cặp; A đúng/B sai {ab['left_only_status_correct']}; B đúng/A sai {ab['right_only_status_correct']}.", "",
              f"A/C: {ac['same_candidate_pairs']} cặp cùng nội dung ứng viên; A đúng/C sai {ac['same_candidate_left_only_status_correct']}; C đúng/A sai {ac['same_candidate_right_only_status_correct']}. Cặp khác ứng viên: {ac['candidate_content_changed']}.", "",
              "Danh sách và hash chi tiết trong summary.json. Hash A/B có schema citation khác nhau nên khác hash không phải bằng chứng khác về nghĩa.", "",
              "Chênh status/wording trong một lượt chưa chứng minh hỗ trợ về nghĩa hoặc hiệu ứng nhân quả của graph. Không được dùng để khẳng định graph vượt RAG.",
              "", "## Các lỗi cần người chấm đối chiếu", "",
              "Các ví dụ cụ thể sau được Codex ghi nhận ở lượt gốc 20261011_real_dev. Khi chạy lượt mới phải đối chiếu rows.jsonl của lượt mới, không sao chép verdict hoặc coi các lỗi này đã tái hiện tự động.", "",
              "- Q005/Q021: A/C tái sử dụng B0_CL_014 nói mounting screws; nguồn nói that screw. Lỗi corpus đã được docs/retrieval_eval_real_dev.md ghi nhận. ai_audit_notes.jsonl pin đáp án mới bằng hash, reviewer_kind=ai; không chuyển verdict cũ thành human verdict của lượt mới.",
              "- Q031 là lỗi nguy hiểm theo gold: hỏi loại mỡ cho con trượt hốc dao, A/C trả Lithium Tacky Grease cho ngón kẹp/lò xo/vòng đệm của double arm. Citation hợp lệ về ID/link nhưng sai bộ phận cần trả lời; cả draft/verify đều để qua. B từ chối. Phải chấm nghĩa độc lập; không sửa gold hoặc corpus ở lượt này.",
              "- Smoke Q001: bản dịch linear guide làm claim-coherence chỉ khớp lubric, thiếu min_matches=2; gate rejected dù corpus có bước bôi trơn. Đây là trace diagnostic, không phải điểm chất lượng dịch đã được người chấm.",
              "- Smoke/full Q058 có thể khác status dù cùng corpus/config: model draft/verify không tất định tuyệt đối ở temperature=0. Giữ riêng cả hai lượt, không chọn đáp án đẹp hơn.",
              "- Q064: A/C có visual observation_note đã kiểm, B chỉ có text. Phải ghi khác biệt modality/preprocessing khi trình bày đối chứng.",
              "- 429 làm backoff hoặc timeout 504; p95 phản ánh điều kiện hạn mức của key khi chạy chung ba arm. Không suy ra p95 cho tài khoản/quy mô tải khác.",
              "- C/Q016 có timeout sau khoảng 922s dù deadline cấu hình 90s; tổng thời gian provider calls và backoff dự kiến không giải thích hết khoảng trễ. Có lỗi ConnectError kế tiếp. Nguyên nhân scheduling/host/tool chưa xác định; giữ nguyên số đo, không cap xuống 90s hoặc loại khỏi p50/p95. Đây không phải bằng chứng latency hosting ổn định.",
              "", "## Chạy lại", "", "```powershell",
              ".\\.venv\\Scripts\\python.exe -m scripts.benchmark_knowflow prepare --run-dir benchmarks/results/<NEW_RUN>",
              ".\\.venv\\Scripts\\python.exe -m scripts.benchmark_knowflow smoke --run-dir benchmarks/results/<NEW_RUN>",
              ".\\.venv\\Scripts\\python.exe -m scripts.benchmark_knowflow run --run-dir benchmarks/results/<NEW_RUN>",
              ".\\.venv\\Scripts\\python.exe -m scripts.benchmark_knowflow report --run-dir benchmarks/results/<NEW_RUN>", "```", "",
              "Key chỉ ở môi trường/.env. `run` resume chỉ những task chưa ghi journal, không sinh lại hoặc xóa lỗi cũ. `report` không gọi API và không ghi đè phiếu review đã có.",
              "", "## Kiểm tra và nhật ký chuẩn bị", "",
              "134 test evaluator/generation hiện có và 6 test integrity benchmark đã qua; XML lưu kèm. Lượt pytest đầu gặp lỗi quyền truy cập thư mục temp ngoài workspace; chạy lại với --basetemp dưới out/ đã qua, không sửa product để làm test pass.",
              "", "Trước smoke, runner từng chặn do so manifest chứa trường return status của build_index với manifest lưu trong DB. Đã sửa duy nhất guard của benchmark, trước mọi câu smoke/full. frozen_config_before_guard_fix.json và freeze_amendments.json giữ bản ghi; config, gold, corpus và product không thay đổi. Lượt embedding build và BM25 ban đầu vẫn được giữ, không giấu phí.",
              "", "Một lần ngắt công cụ/environment dừng process sau 107 rows, ở B/Q019. interruption_journal.json giữ các call chưa có kết quả HTTP. Chỉ resume task chưa có row; không chạy lại các đáp án hoàn tất hoặc lỗi HTTP để chọn kết quả đẹp hơn. Chi phí cộng cả call trước khi bị ngắt; latency của phần chưa hoàn tất là null.",
              "", "artifact_verification.json kiểm hash câu trả lời, đủ task/review rows, journal call IDs, frozen files, key không lọt artifact và keyframe bytes khớp product commit. Các file không đọc nội dung holdout.",
              "", f"Config hash: `{frozen['config_sha256']}`. Questions hash: `{audit['questions_sha256']}`. Corpus files hash: `{audit['corpus_files_sha256']}`.",
              "", "audit.json lưu revisions/review trạng thái/dependencies; frozen_config.json lưu hash product và measurement code trước khi gọi API; provider_calls.jsonl lưu từng HTTP attempt và usage không chứa key; rows.jsonl lưu từng đáp án/citation/trace/lỗi."]
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    latency_a = sa["latency_ms_all_attempts"]
    latency_text = f"p50 {latency_a['p50']/1000:.2f}s, p95 {latency_a['p95']/1000:.2f}s" if latency_a["p50"] is not None else "latency null"
    slide = ["# Nội dung ngắn cho slide — pilot real/dev", "",
        "**Kiểm chứng bằng model thật trên nguồn Haas, không dùng synthetic**", "",
        f"- {audit['questions']} câu được người kiểm nhãn; 3 phương án, {len(rows)} lượt đã ghi. Snapshot, cấu hình, token và lỗi lưu để đối chiếu.",
        f"- KnowFlow hybrid + dịch: Recall@5 **{percent(sa['retrieval']['recall_at_5'])}, n={sa['retrieval']['denominator']}**; BM25 không dịch chạy mới **{percent(offline['recall_at_5'])}, n={offline['questions']}**. Đây là đối chiếu cấu hình tổng hợp, chưa chứng minh đóng góp riêng của graph.",
        f"- Đúng status / {audit['questions']}: KnowFlow **{sa['status_accuracy']['numerator']}**, transcript RAG **{sb['status_accuracy']['numerator']}**, bỏ cạnh graph **{sc['status_accuracy']['numerator']}**. Không coi status match là độ đúng nghĩa của đáp án.",
        f"- Citation hợp lệ theo code A/B/C: {sa['citation_mechanical_validity']['numerator']}/{sa['citation_mechanical_validity']['denominator']}, {sb['citation_mechanical_validity']['numerator']}/{sb['citation_mechanical_validity']['denominator']}, {sc['citation_mechanical_validity']['numerator']}/{sc['citation_mechanical_validity']['denominator']}. Đúng nghĩa và điều kiện đang chờ người chấm. Trả lời khi gold yêu cầu từ chối A/B/C: {len(sa['false_answer'])}/{len(sb['false_answer'])}/{len(sc['false_answer'])}.",
        f"- KnowFlow {latency_text}, n={latency_a['denominator']}, gồm retry/lỗi. Lỗi HTTP toàn thí nghiệm: {sum(len(s['api_errors']) for s in summaries.values())}. Xem latency anomalies trong báo cáo; chưa chứng minh tốc độ hosting ổn định.",
        f"- Phần phí standard đã xác định của KnowFlow **${sa['cost']['known_list_price_subtotal_usd']:.4f}/{sa['planned_questions']} task**, ~${sa['known_list_price_usd_per_planned_task']:.5f}/task. Chưa gồm embedding/fee chưa biết, server, preprocessing, expert labour; hóa đơn thực chưa biết.",
        "", "Ghi chú presenter: đây là dev, một lượt đo. Không thay human review bằng verifier của model; không khẳng định ROI hoặc giảm 30% thời gian lao động. Bảng đầy đủ/dữ liệu gốc: REPORT.md, summary.csv, rows.jsonl, provider_calls.jsonl."]
    (run_dir / "SLIDE.md").write_text("\n".join(slide) + "\n", encoding="utf-8")
    print(json.dumps({arm: {"completed": s["completed"], "status_correct": s["status_accuracy"]["numerator"],
                           "recall_at_5": s["retrieval"]["recall_at_5"], "p95_ms": s["latency_ms_all_attempts"]["p95"],
                           "known_usd": s["cost"]["known_list_price_subtotal_usd"]} for arm, s in summaries.items()}))
