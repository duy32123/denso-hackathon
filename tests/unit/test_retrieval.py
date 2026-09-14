"""WP2 contract gates and retrieval mechanics; dense test doubles are NOT eval results."""

import copy
import json
import sqlite3

import pytest

from conftest import FIXTURE_ROOT, REPO_ROOT, read_bundle, write_bundle
from knowflow_contracts.models import QueryContext, QueryRequest
from retrieval.importer import import_bundle
from retrieval.indexing.embeddings import EmbeddingError, GeminiEmbedder, chunk_text, unit_vector
from retrieval.indexing.search_index import RetrievalError, build_index, read_corpus, require_index
from retrieval.retrieval.engine import RetrievalConfig, retrieve
from retrieval.retrieval.ranking import bm25, rank, rrf, tokens
from retrieval.retrieval.__main__ import main


class TestEmbedder:
    """Tiny deterministic semantic stub, available only inside these tests."""
    __test__ = False
    config = {"provider": "test", "model": "test-semantic", "version": "1", "dimensions": 3}

    def __init__(self):
        self.calls = 0

    def documents(self, texts):
        self.calls += 1
        return [self._vector(text) for text in texts]

    def query(self, text):
        self.calls += 1
        return self._vector(text)

    def _vector(self, text):
        words = set(tokens(text))
        return unit_vector([float(bool(words & {"reset", "restore", "khoi"})),
                            float(bool(words & {"thao", "nap", "cover", "remove"})), 0.05], 3)


def prepare(tmp_path, bundle="F01_complete", embedder=None):
    data = read_bundle(FIXTURE_ROOT / bundle) if isinstance(bundle, str) else bundle
    path = write_bundle(tmp_path / "bundle", data)
    db = tmp_path / "store.sqlite"
    mode = data["manifest"]["source_type"]
    split = data["manifest"]["dataset_split"]
    import_bundle(path, db, source_type=mode, split=split)
    build_index(db, mode=mode, split=split, embedder=embedder)
    return db


def ask(db, question="thao nap che", *, strategy="lexical", mode="synthetic", split="dev",
        embedder=None, context=None, intent="detail"):
    return retrieve(db, QueryRequest(question=question, context=QueryContext(**(context or {})),
                                     mode=mode, dataset_split=split),
                    config=RetrievalConfig(strategy=strategy, intent=intent), embedder=embedder)


def test_bm25_preserves_codes_negation_and_ranks_matches():
    assert {"not", "2066", "vf-2", "thao"}.issubset(tokens("Do not remove 2066 VF-2; tháo"))
    scores = bm25("bolt", {"a": ["bolt"], "b": ["bolt", "bolt"], "c": ["oil"]})
    assert scores["b"] > scores["a"] > 0 and "c" not in scores
    assert bm25("unrelated", {"a": ["bolt"]}) == {}


def test_dense_ranking_and_rrf_are_distinct_from_lexical():
    docs = [{"id": "a", "tokens": ["remove"], "vector": [0., 1.]},
            {"id": "b", "tokens": ["restore"], "vector": [1., 0.]}]
    args = dict(candidate_k=20, min_cosine=.25, rrf_k=60)
    assert rank("remove", docs, None, strategy="lexical", **args)[0]["doc"]["id"] == "a"
    assert rank("remove", docs, [1., 0.], strategy="vector", **args)[0]["doc"]["id"] == "b"
    hybrid = rank("remove", docs, [1., 0.], strategy="hybrid", **args)
    assert {h["doc"]["id"] for h in hybrid} == {"a", "b"}
    scores = rrf([["a", "b"], ["b", "c"]])
    assert scores["b"] > scores["a"] > scores["c"]


@pytest.mark.parametrize("strategy", ["lexical", "vector", "hybrid"])
def test_three_strategies_return_exact_snapshot_evidence(tmp_path, strategy):
    embedding = TestEmbedder()
    db = prepare(tmp_path, embedder=embedding)
    result = ask(db, strategy=strategy, embedder=embedding, context={"machine_model": "DEMO_TC_A"})
    assert result["status"] == "retrieved"
    assert result["steps"] and result["claims"]
    assert result["trace"]["cache"] == "disabled"
    assert result["evidence_openability_checked"] is False
    selected = result["selected_workflow"]
    for item in result["claims"]:
        assert item["claim_ref"]["workflow_id"] == selected["workflow_id"]
        assert item["claim_ref"]["revision"] == selected["revision"]
        assert item["claim_ref"]["entity_id"] == item["claim"]["claim_id"]
        assert item["evidence"]
        assert item["evidence"][0]["access_status"] == "not_checked"
    assert len({c["claim_ref"]["entity_id"] for c in result["claims"]}) == len(result["claims"])


@pytest.mark.parametrize("strategy", ["lexical", "vector", "hybrid"])
@pytest.mark.parametrize("wrong", ["mode", "split"])
def test_namespace_rejected_before_query_embedding(tmp_path, strategy, wrong):
    embedding = TestEmbedder()
    db = prepare(tmp_path, embedder=embedding)
    before = embedding.calls
    with pytest.raises(RetrievalError, match="Corpus/split"):
        ask(db, strategy=strategy, embedder=embedding,
            mode="real" if wrong == "mode" else "synthetic",
            split="holdout" if wrong == "split" else "dev")
    assert embedding.calls == before


@pytest.mark.parametrize("strategy", ["lexical", "vector", "hybrid"])
def test_model_filter_is_applied_before_all_ranking(tmp_path, strategy):
    embedding = TestEmbedder()
    db = prepare(tmp_path, "F04_model_mismatch", embedding)
    result = ask(db, "xoay chot", strategy=strategy, embedder=embedding,
                 context={"machine_model": "DEMO_TC_A"})
    assert result["status"] == "retrieved"
    assert {h["workflow_id"] for h in result["workflow_candidates"]} == {"SYN_WF_0004"}
    assert all(c["claim_ref"]["workflow_id"] == "SYN_WF_0004" for c in result["claims"])
    assert any(f["mismatches"] == ["machine_model"] for f in result["trace"]["filters"])


def test_model_detection_and_contradictory_context(tmp_path):
    db = prepare(tmp_path, "F04_model_mismatch")
    found = ask(db, "xoay chot DEMO_TC_A")
    assert found["status"] == "retrieved"
    assert found["selected_workflow"]["workflow_id"] == "SYN_WF_0004"
    mismatch = ask(db, "xoay chot DEMO_TC_A", context={"machine_model": "DEMO_TC_B"})
    assert mismatch["status"] == "needs_clarification" and mismatch["claims"] == []
    assert "machine_model" in mismatch["missing_context"]
    absent = ask(db, "xoay chot VF-99")
    assert absent["status"] == "insufficient_evidence"


@pytest.mark.parametrize("fixture", ["F03_model_unknown", "F04_model_mismatch"])
def test_missing_decisive_identity_clarifies_without_call(tmp_path, fixture):
    embedding = TestEmbedder()
    db = prepare(tmp_path, fixture, embedding)
    before = embedding.calls
    result = ask(db, "reset cum", strategy="hybrid", embedder=embedding)
    assert result["status"] == "needs_clarification"
    assert "machine_model" in result["missing_context"]
    assert result["claims"] == [] and embedding.calls == before


@pytest.mark.parametrize("field,actual,requested", [
    ("manufacturer", "Haas", "Other"), ("machine_family", "VF", "UMC"),
    ("subsystem", "SMTC", "umbrella"), ("task_type", "maintenance", "recovery"),
    ("alarm_codes", ["2066"], ["2067"]),
])
def test_context_mismatch_never_relaxes_filters(tmp_path, f01, field, actual, requested):
    wf = f01["workflows"][0]
    wf["context"][field] = actual
    wf["context"]["metadata_provenance"][field] = {"basis": "curated", "source_ids": [], "note": "test"}
    db = prepare(tmp_path, f01)
    result = ask(db, context={field: requested})
    assert result["status"] == "insufficient_evidence" and result["claims"] == []


def test_alarm_detection_not_fuzzy_matching(tmp_path, f01):
    wf = f01["workflows"][0]
    wf["context"]["alarm_codes"] = ["2066"]
    wf["context"]["metadata_provenance"]["alarm_codes"] = {"basis": "curated", "source_ids": [], "note": "test"}
    db = prepare(tmp_path, f01)
    assert ask(db, "thao nap alarm 2066", context={"machine_model": "DEMO_TC_A"})["status"] == "retrieved"
    assert ask(db, "thao nap alarm 2067")["status"] == "insufficient_evidence"
    assert ask(db, "thao nap", context={"alarm_codes": ["20.66"]})["status"] == "insufficient_evidence"


def test_conflicts_are_reported_but_not_assertable(tmp_path):
    db = prepare(tmp_path, "F06_conflict")
    result = ask(db, "den bao sau reset")
    assert result["status"] == "conflicting_sources"
    assert len(result["conflicts"]) == 2
    conflict_ids = {c["claim_ref"]["entity_id"] for c in result["conflicts"]}
    assert not conflict_ids & {c["claim_ref"]["entity_id"] for c in result["claims"]}
    assert all(c["purpose"] == "warning_only" and c["evidence"] for c in result["conflicts"])


def test_pending_real_claims_not_ranked_as_answers(tmp_path):
    raw = read_bundle(REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle")
    for wf in raw["workflows"]:
        for claim in wf["claims"]:
            claim["source_review"] = "pending"
        wf["review_events"] = []
    db = prepare(tmp_path, raw)
    result = ask(db, "tool pocket replacement", mode="real")
    assert result["claims"] == [] and result["status"] == "insufficient_evidence"
    assert require_index(read_corpus(db, "real", "dev"))[1] == []


def test_missing_rationale_remains_missing(tmp_path):
    db = prepare(tmp_path, "F02_rationale_missing")
    result = ask(db, "dat hai mau canh nhau")
    assert result["steps"][0]["fields"]["rationale"] == {"state": "missing", "claim_ids": []}
    assert all(c["claim"]["role"] != "rationale" for c in result["claims"])
    assert result["questions"]


def test_procedure_keeps_one_workflow_and_original_order(tmp_path):
    db = prepare(tmp_path, "F07_repeated_step")
    result = ask(db, "thu lai", intent="procedure")
    assert result["status"] == "retrieved"
    assert len({s["workflow_id"] for s in result["steps"]}) == 1
    assert [s["display_order"] for s in result["steps"]] == sorted(s["display_order"] for s in result["steps"])
    assert len({c["claim_ref"]["entity_id"] for c in result["claims"]}) == len(result["claims"])


def test_revision_update_invalidates_index_and_withdrawal_cannot_resurrect(tmp_path, f09):
    old = copy.deepcopy(f09)
    old["workflows"] = old["workflows"][:1]
    db = prepare(tmp_path, old)
    initial = ask(db)["index_build_id"]
    import_bundle(write_bundle(tmp_path / "r2", f09), db, source_type="synthetic", split="dev")
    with pytest.raises(RetrievalError, match="stale"):
        ask(db)
    build_index(db, mode="synthetic", split="dev")
    result = ask(db)
    assert result["index_build_id"] != initial
    assert {c["claim_ref"]["revision"] for c in result["claims"]} == {2}
    withdrawn = copy.deepcopy(f09)
    wf = withdrawn["workflows"][-1]
    wf.update(revision=3, supersedes_revision=2, lifecycle="withdrawn")
    wf["change_log"].append({"changed_at": "2026-09-14T00:00:00Z", "actor_id": "test",
                             "reason": "withdraw", "previous_revision": 2, "id_mapping": []})
    withdrawn["workflows"] = [wf]
    import_bundle(write_bundle(tmp_path / "r3", withdrawn), db, source_type="synthetic", split="dev")
    build_index(db, mode="synthetic", split="dev")
    assert ask(db)["claims"] == []
    import_bundle(tmp_path / "bundle", db, source_type="synthetic", split="dev")
    assert ask(db)["claims"] == []


def test_embedding_build_noop_and_no_silent_vector_fallback(tmp_path):
    embedding = TestEmbedder()
    db = prepare(tmp_path, embedder=embedding)
    before = embedding.calls
    assert build_index(db, mode="synthetic", split="dev", embedder=embedding)["status"] == "noop"
    assert embedding.calls == before
    build_index(db, mode="synthetic", split="dev")
    with pytest.raises(RetrievalError, match="no vectors"):
        ask(db, strategy="hybrid", embedder=embedding, context={"machine_model": "DEMO_TC_A"})


@pytest.mark.parametrize("bad", [[0, 0, 0], [float("nan"), 1, 0], [1, 0], [float("inf"), 0, 1]])
def test_invalid_vectors_leave_previous_active_build(tmp_path, bad):
    db = prepare(tmp_path)
    initial = require_index(read_corpus(db, "synthetic", "dev"))[0]["index_build_id"]
    embedding = TestEmbedder()
    embedding.documents = lambda texts: [bad for _ in texts]
    with pytest.raises(EmbeddingError):
        build_index(db, mode="synthetic", split="dev", embedder=embedding)
    assert require_index(read_corpus(db, "synthetic", "dev"))[0]["index_build_id"] == initial


def test_query_embedding_config_must_match_index(tmp_path):
    db = prepare(tmp_path, embedder=TestEmbedder())
    wrong = TestEmbedder()
    wrong.config = {**wrong.config, "version": "2"}
    with pytest.raises(RetrievalError, match="configuration mismatch"):
        ask(db, strategy="vector", embedder=wrong, context={"machine_model": "DEMO_TC_A"})
    assert wrong.calls == 0


def test_index_corruption_is_not_served(tmp_path):
    db = prepare(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM retrieval_documents WHERE document_id=(SELECT document_id FROM retrieval_documents LIMIT 1)")
    with pytest.raises(RetrievalError, match="checksum/count"):
        ask(db)


def test_index_build_rejects_concurrent_import(tmp_path, f09):
    old = copy.deepcopy(f09)
    old["workflows"] = old["workflows"][:1]
    db = prepare(tmp_path, old)
    before = require_index(read_corpus(db, "synthetic", "dev"))[0]["index_build_id"]
    embedding = TestEmbedder()
    real_documents = embedding.documents

    def advance(texts):
        import_bundle(write_bundle(tmp_path / "new", f09), db, source_type="synthetic", split="dev")
        return real_documents(texts)

    embedding.documents = advance
    with pytest.raises(RetrievalError, match="changed during"):
        build_index(db, mode="synthetic", split="dev", embedder=embedding)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT value FROM settings WHERE key='active_retrieval_build'").fetchone()[0] == before


def test_cli_lexical_build_query_status(tmp_path, capsys):
    db = prepare(tmp_path)
    common = ["--db", str(db), "--mode", "synthetic", "--split", "dev"]
    assert main(["build", *common, "--embedding", "none"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "noop"
    assert main(["query", "thao nap", *common, "--strategy", "lexical", "--machine-model", "DEMO_TC_A"]) == 0
    assert json.loads(capsys.readouterr().out)["claims"]
    assert main(["status", *common]) == 0
    assert json.loads(capsys.readouterr().out)["lexical"] == "BM25"


def test_blank_query_rejected(tmp_path):
    db = prepare(tmp_path)
    with pytest.raises(ValueError, match="blank"):
        ask(db, "   ")


def test_multilingual_chunks_preserve_entire_input_and_byte_bound():
    original = "Tháo nắp máy: giữ nguyên phủ định, điều kiện và đơn vị. 日本語\n" * 200
    chunks = chunk_text(original)
    assert "".join(chunks) == original
    assert all(len(c.encode("utf-8")) <= 1800 for c in chunks)


def test_document_chunk_pooling_normalizes_and_never_drops_tail(monkeypatch):
    embedder = GeminiEmbedder(768)
    seen = []

    def fake_embed(texts, task):
        seen.extend(texts)
        assert task == "RETRIEVAL_DOCUMENT"
        return [[1.0] + [0.0] * 767 for _ in texts]

    monkeypatch.setattr(embedder, "_embed", fake_embed)
    text = "condition must not be lost " * 500 + "END-OF-DOCUMENT"
    result = embedder.documents([text])
    assert "".join(seen) == text
    assert len(result) == 1 and result[0] == [1.0] + [0.0] * 767
