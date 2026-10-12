"""Benchmark integrity tests. Fixtures here are not quality measurements."""
from types import SimpleNamespace

import pytest

from scripts.benchmark_knowflow.baseline import TranscriptRAG, raw_chunks
from scripts.benchmark_knowflow.report import call_cost, costs, measured_sum, summarize
from scripts.benchmark_knowflow.review import import_reviews
from retrieval.indexing.search_index import digest
from scripts.benchmark_knowflow.pairing import PairedRetrieval, without_graph, pre_graph_signature
from scripts.benchmark_knowflow.providers import Recorder
from knowflow_contracts.models import QueryRequest, QueryContext
from retrieval.retrieval.engine import RetrievalConfig
from retrieval.indexing.embeddings import EmbeddingError
from scripts.benchmark_knowflow.audit import verify_label_approval


def config():
    return {"baseline": {"chunk_words": 5, "overlap_words": 2}, "pricing": {
        "gemini-3.5-flash-lite": {"input_per_million": .3, "output_per_million": 2.5,
                                 "cached_input_per_million": .03},
        "gemini-embedding-001": {"input_per_million": None, "output_per_million": None}}}


def test_unknown_usage_and_embedding_price_propagate_null():
    known = {"ok": True, "operation": "generate_content", "model": "gemini-3.5-flash-lite",
             "input_tokens": 1000, "output_tokens": 100, "billed_output_tokens": 150,
             "total_tokens": 1150, "usage_metadata": None}
    missing = {"ok": True, "operation": "embed_content", "model": "gemini-embedding-001",
               "input_tokens": None, "output_tokens": None, "billed_output_tokens": None, "total_tokens": None}
    assert call_cost(known, config()) == pytest.approx(.0003 + .000375)
    assert call_cost(missing, config()) is None
    total = costs([known, missing], config())
    assert total["standard_list_price_usd"] is None
    assert total["known_list_price_subtotal_usd"] == pytest.approx(.000675)
    assert total["input_tokens"] is None
    assert costs([], config())["standard_list_price_usd"] == 0  # Provably no calls.
    assert measured_sum([1, None]) is None


def test_failed_provider_call_is_not_reported_as_free():
    failed = {"ok": False, "operation": "generate_content", "model": "gemini-3.5-flash-lite"}
    assert costs([failed], config())["standard_list_price_usd"] is None


def test_api_failure_remains_in_quality_and_latency_denominators():
    row = {"http_status": 503, "question_id": "error_question", "status": "error", "expected_status": "answered",
           "status_ok": False, "false_answer": False, "false_abstention": False, "retrieval_scored": True,
           "recall_at_5": 0, "reciprocal_rank_at_5": 0, "citation_checks": [], "provider_calls": [],
           "http_attempts": [], "latency_ms": 90001, "backoff_seconds": 65, "post_timeout_drain_ms": 100,
           "error_class": "GenerationError", "leakage": [], "arm": "A_knowflow"}
    result = summarize([row], config(), 1)
    assert result["status_accuracy"] == {"numerator": 0, "denominator": 1, "rate": 0}
    assert result["retrieval"]["denominator"] == 1
    assert result["retrieval"]["recall_at_5"] == 0
    assert result["latency_ms_all_attempts"]["p95"] == 90001
    assert result["api_errors"][0]["question_id"] == "error_question"


def test_raw_index_and_citations_use_exact_source_offsets_without_annotations(tmp_path):
    source = SimpleNamespace(source_id="SRC_TEST", title="Raw manual", url="https://example.org/source",
             source_kind="service_document", raw_text="one two three 25 five six seven eight nine ten", content_sha256="source_hash")
    streams, chunks = raw_chunks({source.source_id: source}, tmp_path, config())
    assert chunks and all("claim" not in chunk and "step" not in chunk and "workflow" not in chunk for chunk in chunks)
    for chunk in chunks:
        assert streams["SRC_TEST"]["text"][chunk["char_start"]:chunk["char_end"]] == chunk["text"]
    rag = TranscriptRAG(streams, chunks, config(), None, None, None)
    allowed = {c["id"]: c for c in chunks}
    good = rag.check_citation({"answer_span": "25", "chunk_ids": [chunks[0]["id"]]}, allowed)
    assert good["valid"]
    assert not rag.check_citation({"answer_span": "26", "chunk_ids": [chunks[0]["id"]]}, allowed)["valid"]
    corrupted = {**chunks[0], "text": "different"}
    assert not rag.check_citation({"answer_span": "one", "chunk_ids": [corrupted["id"]]}, {corrupted["id"]: corrupted})["valid"]


def review_fixture(kind):
    response = {"status": "answered", "answer": "A source-only answer", "citations": []}
    hashed = digest([response["status"], response["answer"], response["citations"]])
    row = {"arm": "A_knowflow", "question_id": "Q1", "http_status": 200,
           "answer_sha256": hashed, "response": response, "status": "answered", "citation_checks": []}
    verdict = {"arm": "A_knowflow", "question_id": "Q1", "answer_sha256": hashed,
               "reviewer_kind": kind, "reviewer_id": "reviewer", "reviewed_at": "2026-10-11",
               "answers_question": "true", "conditions_correct": "true", "source_supported": "true",
               "citations_supported_json": "[]"}
    return row, verdict


def test_ai_verdict_never_counts_as_human_review():
    row, verdict = review_fixture("ai")
    _, summary = import_reviews([row], [verdict])
    assert summary["A_knowflow"]["human_reviewed_questions"] == 0
    assert summary["A_knowflow"]["answers_question"]["rate"] is None
    assert summary["A_knowflow"]["ai_assisted_reviewed_questions"] == 1


def test_stale_and_tampered_review_hashes_are_rejected():
    row, verdict = review_fixture("human")
    verdict["answer_sha256"] = "stale"
    with pytest.raises(ValueError, match="hash"):
        import_reviews([row], [verdict])
    row, verdict = review_fixture("human")
    row["response"]["answer"] = "Changed answer"
    with pytest.raises(ValueError, match="hash"):
        import_reviews([row], [verdict])


def test_ac_replays_exact_candidates_and_translation_before_dropping_graph(tmp_path):
    recorder = Recorder(tmp_path / "provider.jsonl")
    recorder.phase, recorder.question_id, recorder.arm = "full", "Q1", "A_knowflow"
    calls = []
    def live(db, query, config):
        calls.append(query.question)
        return {"status": "retrieved", "claims": [{"text": "original"}], "steps": ["S1"],
                "relations": ["R1"], "related_steps": ["S2"], "related_claims": ["C2"],
                "trace": {"query_translation": {"text": "A real-provider translation"}}}
    pair = PairedRetrieval(tmp_path / "pair", recorder, live, "corpus-sha")
    query = QueryRequest(question="A question", context=QueryContext(), mode="real", dataset_split="dev")
    a = pair.get("unused", query, RetrievalConfig())
    a["claims"][0]["text"] = "consumer mutation"
    recorder.arm = "C_no_graph"
    c_raw = pair.get("unused", query, RetrievalConfig())
    c = without_graph(c_raw)
    assert calls == ["A question"] and pair.last_metadata["replayed"]
    assert c["claims"][0]["text"] == "original"
    assert c["relations"] == c["related_steps"] == c["related_claims"] == []
    assert pre_graph_signature(c_raw) == pre_graph_signature(c)
    assert c["trace"]["query_translation"]["text"] == "A real-provider translation"
    with pytest.raises(ValueError, match="changed"):
        pair.get("unused", query.model_copy(update={"question": "Changed"}), RetrievalConfig())


def test_shared_retrieval_error_is_retained_for_both_arms_without_retry(tmp_path):
    recorder = Recorder(tmp_path / "provider.jsonl")
    recorder.phase, recorder.question_id, recorder.arm = "full", "Q1", "A_knowflow"
    calls = []
    def failed(db, query, config):
        calls.append(query.question)
        raise EmbeddingError("Provider failed")
    pair = PairedRetrieval(tmp_path / "pair", recorder, failed, "corpus-sha")
    query = QueryRequest(question="A question", context=QueryContext(), mode="real", dataset_split="dev")
    for arm in ("A_knowflow", "C_no_graph"):
        recorder.arm = arm
        with pytest.raises(EmbeddingError, match="Shared real"):
            pair.get("unused", query, RetrievalConfig())
    assert len(calls) == 1 and pair.last_metadata["error_class"] == "EmbeddingError"


def test_official_expanded_run_requires_actual_human_label_approval(tmp_path, monkeypatch):
    import json
    import scripts.benchmark_knowflow.audit as audit_module
    monkeypatch.setattr(audit_module, "ROOT", tmp_path)
    config = {"expanded_label_review": "approval.json", "questions": "q.jsonl", "bundle": "bundle"}
    with pytest.raises(ValueError, match="completed human review"):
        verify_label_approval(config)
    (tmp_path / "approval.json").write_text(json.dumps({"reviewer_kind": "ai", "reviewer_id": "codex"}))
    with pytest.raises(ValueError, match="require human review"):
        verify_label_approval(config)


def test_expanded_report_cohorts_and_shared_cost_are_not_double_counted(tmp_path, monkeypatch):
    import json
    import scripts.benchmark_knowflow.expanded_report as expanded
    monkeypatch.setattr(expanded, "ROOT", tmp_path)
    cfg = config() | {"questions": "q.jsonl", "answer_model": "gemini-3.5-flash-lite", "execution": {},
                      "pricing": config()["pricing"] | {"checked_date": "2026-10-12"}}
    cfg["pricing"]["gemini-3.5-flash-lite"]["url"] = "https://ai.google.dev/gemini-api/docs/pricing"
    questions = [{"question_id": "HAAS_DEV_Q001", "language": "vi"}, {"question_id": "HAAS_DEV_Q069", "language": "en"}]
    (tmp_path / "q.jsonl").write_text("".join(json.dumps(q)+"\n" for q in questions))
    (tmp_path / "audit.json").write_text(json.dumps({"questions_sha256": "q-sha", "corpus_files_sha256": "c-sha", "active_workflows": []}))
    pair_meta = {"key": "same", "result_sha256": "same", "pre_graph_sha256": "same", "translation_sha256": "same", "error_class": None}
    rows = []
    for arm in expanded.ARMS:
        for q in questions:
            body = {"status": "insufficient_evidence", "answer": "Source incomplete", "citations": []}
            rows.append({"arm": arm, "question_id": q["question_id"], "question": "Fixture, not a quality result", "language": q["language"],
                "expected_status": "insufficient_evidence", "expected_retrieval_status": "retrieved", "http_status": 200,
                "status": body["status"], "response": body, "answer_sha256": digest([body["status"], body["answer"], body["citations"]]),
                "status_ok": True, "false_answer": False, "false_abstention": False, "retrieval_scored": False,
                "citation_checks": [], "provider_calls": [], "http_attempts": [], "latency_ms": 50,
                "latency_ms_standalone_component_sum": 60, "backoff_seconds": 0, "post_timeout_drain_ms": 0,
                "error_class": None, "leakage": [], "retrieval": None, "shared_retrieval": pair_meta if arm != expanded.ARMS[1] else None})
    (tmp_path / "rows.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
    shared = {"kind": "provider_call", "phase": "full", "arm": "AC_shared_retrieval", "question_id": "HAAS_DEV_Q001",
              "call_id": "one", "stage": "translation", "ok": True, "operation": "generate_content", "model": "gemini-3.5-flash-lite",
              "input_tokens": 1000, "output_tokens": 100, "billed_output_tokens": 100, "total_tokens": 1100}
    (tmp_path / "provider_calls.jsonl").write_text(json.dumps(shared)+"\n")
    summary = expanded.write(tmp_path, {"config": cfg, "product_commit": "fixture", "config_sha256": "cfg"})
    assert summary["by_cohort"]["old_66"]["A_knowflow"]["planned_questions"] == 1
    assert summary["by_cohort"]["new_15"]["A_knowflow"]["planned_questions"] == 1
    assert summary["AC_shared_retrieval_cost"]["provider_calls"] == 1
    assert summary["all_experiment_api_cost_including_index_smoke_interruption"]["provider_calls"] == 1
    assert summary["summaries"]["A_knowflow"]["cost"]["provider_calls"] == 0
    assert summary["summaries"]["C_no_graph"]["standalone_reference_cost_including_one_shared_retrieval"]["provider_calls"] == 1
    assert summary["summaries"]["A_knowflow"]["human_semantics"]["source_supported"] is None


def test_interrupted_call_start_retains_unknown_expense():
    from scripts.benchmark_knowflow.expanded_report import accounting_calls
    started = {"kind": "provider_call_started", "call_id": "one", "model": "gemini-3.5-flash-lite", "operation": "generate_content"}
    all_calls, unfinished = accounting_calls([started])
    assert len(all_calls) == len(unfinished) == 1
    assert costs(all_calls, config())["standard_list_price_usd"] is None
    assert unfinished[0]["elapsed_ms"] is None
    completed = {**started, "kind": "provider_call", "ok": False}
    assert accounting_calls([started, completed]) == ([completed], [])


def test_execution_approval_does_not_become_human_source_review(tmp_path, monkeypatch):
    import json
    import scripts.benchmark_knowflow.audit as audit_module
    monkeypatch.setattr(audit_module, "ROOT", tmp_path)
    (tmp_path / "q.jsonl").write_text("existing gold")
    cfg = {"questions": "q.jsonl", "label_revalidation_pending": True, "execution_authorization": "authorization.json"}
    authorization = {"kind": "user_execution_authorization", "human_source_review": False,
                     "questions_sha256": audit_module.sha_file(tmp_path / "q.jsonl")}
    (tmp_path / "authorization.json").write_text(json.dumps(authorization))
    verify_label_approval(cfg)
    with pytest.raises(ValueError, match="cannot be marked"):
        verify_label_approval(cfg | {"expanded_label_review": "fake_human_review.json"})
    (tmp_path / "q.jsonl").write_text("gold was edited")
    with pytest.raises(ValueError, match="Missing authorization"):
        verify_label_approval(cfg)
