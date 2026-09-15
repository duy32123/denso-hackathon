"""Retrieval evaluation harness: metric rules and guards. Stub vectors are NOT results."""

import json

import pytest

from conftest import FIXTURE_ROOT, REPO_ROOT, read_bundle, write_bundle
from knowflow_contracts.models import Workflow
from retrieval.evaluation.__main__ import main
from retrieval.evaluation.harness import (
    EvalQuestion, EvaluationError, TranslationCache, check_gold, load_questions, run_evaluation, score_ranking,
)
from retrieval.importer import import_bundle
from retrieval.indexing.embeddings import unit_vector
from retrieval.indexing.search_index import build_index
from retrieval.retrieval.ranking import tokens

WF = "SYN_WF_0001"
REAL_QUESTIONS = REPO_ROOT / "data/eval/haas_real_dev.retrieval.v0.jsonl"


class StubEmbedder:
    __test__ = False
    config = {"provider": "test", "model": "stub", "version": "1", "dimensions": 3}

    def __init__(self):
        self.query_calls = 0

    def documents(self, texts):
        return [self._vector(text) for text in texts]

    def query(self, text):
        self.query_calls += 1
        return self._vector(text)

    def _vector(self, text):
        words = set(tokens(text))
        return unit_vector([float(bool(words & {"xoay", "lock"})), float(bool(words & {"mo", "nap"})), 0.05], 3)


def ref(step, revision=1):
    return {"workflow_id": WF, "revision": revision, "step_id": f"{WF}_{step}"}


def question(qid, text, *, status="answered", retrieval="retrieved", units=(), context=None, category="detail"):
    return {"question_id": qid, "source_type": "synthetic", "dataset_split": "dev", "language": "vi",
            "category": category, "intent": "detail", "question": text,
            "context": {"machine_model": "DEMO_TC_A"} if context is None else context,
            "expected_status": status, "expected_retrieval_status": retrieval,
            "gold_units": [list(unit) for unit in units], "label": {"status": "draft", "labeled_by": "test"}}


QUESTIONS = [
    question("Q1", "xoay chot khoa LOCK", units=[[ref("ST_001")]]),
    question("Q2", "quantum chromodynamics", status="insufficient_evidence",
             retrieval="insufficient_evidence", category="off_topic"),
    question("Q3", "xoay chot", status="needs_clarification", retrieval="needs_clarification",
             context={}, category="clarification"),
]


def setup(tmp_path, questions=QUESTIONS, embedder=None):
    db = tmp_path / "store.sqlite"
    bundle = write_bundle(tmp_path / "bundle", read_bundle(FIXTURE_ROOT / "F01_complete"))
    import_bundle(bundle, db, source_type="synthetic", split="dev")
    build_index(db, mode="synthetic", split="dev", embedder=embedder)
    path = tmp_path / "questions.jsonl"
    path.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questions), encoding="utf-8")
    return db, path


def test_score_ranking_counts_units_and_first_hit():
    a, b, c = ("W", 1, "A"), ("W", 1, "B"), ("V", 1, "C")
    # Unit 1 accepts A or its duplicate C; unit 2 needs B.
    assert score_ranking([("W", 1, "X"), c, ("W", 1, "Y")], [{a, c}, {b}], k=5) == {
        "recall": 0.5, "reciprocal_rank": 0.5, "first_relevant_rank": 2}
    assert score_ranking([a, b], [{b}], k=1)["recall"] == 0.0
    assert score_ranking([], [{a}], k=5) == {"recall": 0.0, "reciprocal_rank": 0.0, "first_relevant_rank": None}


def test_lexical_run_scores_answerable_and_reports_abstains_separately(tmp_path):
    db, path = setup(tmp_path)
    report, rows = run_evaluation(db, path, mode="synthetic", split="dev", strategies=["lexical"])
    summary = report["strategies"]["lexical"]
    assert summary["retrieval"]["questions"] == 1  # abstain/clarify stay out of the denominator
    assert summary["retrieval"]["recall_at_5"] == 1.0 and summary["retrieval"]["mrr_at_5"] == 1.0
    assert summary["status"]["accuracy"] == 1.0 and summary["status"]["false_retrieved"] == []
    assert {r["question_id"]: r["status"] for r in rows} == {
        "Q1": "retrieved", "Q2": "insufficient_evidence", "Q3": "needs_clarification"}
    assert report["gold_labels"] == {"draft": 3, "ai_reviewed": 0, "reviewed": 0} and "warning" in report
    assert report["query_embedding_calls"] == 0


def test_vector_and_hybrid_share_one_query_embedding(tmp_path):
    stub = StubEmbedder()
    db, path = setup(tmp_path, embedder=stub)
    report, rows = run_evaluation(db, path, mode="synthetic", split="dev",
                                  strategies=["vector", "hybrid"], embedder=stub)
    assert sum(r["embedding_calls"] for r in rows if r["strategy"] == "hybrid") == 0
    assert stub.query_calls == report["query_embedding_calls"] == sum(r["embedding_calls"] for r in rows)
    assert stub.query_calls == 1  # Q2 fails the relevance gate, Q3 needs clarification: neither embeds


def test_disk_query_cache_reuses_vectors_across_runs(tmp_path):
    stub = StubEmbedder()
    db, path = setup(tmp_path, embedder=stub)
    cache = tmp_path / "query_cache.jsonl"
    first, _ = run_evaluation(db, path, mode="synthetic", split="dev", strategies=["vector"],
                              embedder=stub, query_cache=cache)
    assert stub.query_calls == first["query_embedding_calls"] == 1
    second, rows = run_evaluation(db, path, mode="synthetic", split="dev", strategies=["vector"],
                                  embedder=stub, query_cache=cache)
    assert stub.query_calls == 1 and second["query_embedding_calls"] == 0
    assert first["strategies"]["vector"]["retrieval"] == second["strategies"]["vector"]["retrieval"]
    assert all(r["latency_ms"] >= r["engine_latency_ms"] for r in rows)
    assert any(r["embedding_reused"] for r in rows)


def test_translation_cache_reuses_across_runs(tmp_path):
    class Upper:
        config = {"provider": "test", "model": "upper", "prompt_version": "1"}
        calls = 0

        def to_english(self, text):
            Upper.calls += 1
            return text.upper()

    path = tmp_path / "translations.jsonl"
    assert TranslationCache(Upper(), path).to_english("xin chào") == "XIN CHÀO"
    second = TranslationCache(Upper(), path)
    assert second.to_english("xin chào") == "XIN CHÀO"
    assert Upper.calls == 1 and second.calls == 0


def test_stale_gold_is_rejected_before_retrieval(tmp_path):
    db, path = setup(tmp_path, [question("Q1", "xoay chot", units=[[ref("ST_001", revision=2)]])])
    with pytest.raises(EvaluationError, match="relabel"):
        run_evaluation(db, path, mode="synthetic", split="dev", strategies=["lexical"])


def test_corpus_split_and_holdout_guards(tmp_path):
    db, path = setup(tmp_path)
    with pytest.raises(EvaluationError, match="another corpus"):
        run_evaluation(db, path, mode="real", split="dev", strategies=["lexical"])
    with pytest.raises(EvaluationError, match="Holdout"):
        run_evaluation(db, path, mode="synthetic", split="holdout", strategies=["lexical"])


@pytest.mark.parametrize("bad", [
    {"gold_units": []},                                        # answerable detail without gold
    {"expected_retrieval_status": "insufficient_evidence"},    # answered yet expects abstain
    {"gold_units": [[]]},                                      # empty unit
    {"label": {"status": "reviewed", "labeled_by": "test"}},  # reviewed without reviewer
])
def test_question_schema_rejects_inconsistent_gold(bad):
    raw = {**question("Q1", "xoay chot", units=[[ref("ST_001")]]), **bad}
    with pytest.raises(ValueError):
        EvalQuestion.model_validate_json(json.dumps(raw))


def test_cli_writes_report_and_rows(tmp_path, capsys):
    db, path = setup(tmp_path)
    out = tmp_path / "eval"
    assert main(["run", "--db", str(db), "--questions", str(path), "--mode", "synthetic", "--split", "dev",
                 "--strategy", "lexical", "--out", str(out)]) == 0
    assert "WARNING" in capsys.readouterr().out
    run_dir = next(out.iterdir())
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["strategies"]["lexical"]["retrieval"]["recall_at_5"] == 1.0
    assert len((run_dir / "rows.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_real_dev_question_set_matches_exported_bundle():
    questions, _ = load_questions(REAL_QUESTIONS)
    assert all((q.source_type, q.dataset_split) == ("real", "dev") for q in questions)
    workflows = {}
    lines = (REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle/workflows.jsonl").read_text(encoding="utf-8")
    for line in lines.splitlines():
        if line.strip():
            wf = Workflow.model_validate_json(line)
            if wf.workflow_id not in workflows or wf.revision > workflows[wf.workflow_id].revision:
                workflows[wf.workflow_id] = wf
    check_gold(questions, workflows)
