"""Benchmark integrity tests. Fixtures here are not quality measurements."""
from types import SimpleNamespace

import pytest

from scripts.benchmark_knowflow.baseline import TranscriptRAG, raw_chunks
from scripts.benchmark_knowflow.report import call_cost, costs, measured_sum, summarize
from scripts.benchmark_knowflow.review import import_reviews
from retrieval.indexing.search_index import digest


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
