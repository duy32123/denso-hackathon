"""WP3 answer evaluation rules. Stub model verdicts are NOT quality measurements."""

import copy
import json

import pytest

from conftest import FIXTURE_ROOT, REPO_ROOT, read_bundle, write_bundle
from knowflow_contracts.models import AnswerResponse, Citation, EntityRef, QueryContext, QueryRequest
from retrieval.evaluation.__main__ import main
from retrieval.evaluation.answers import (
    Verdict, answer_digest, check_citation, check_grounding, check_leakage, evaluate_answers, join_verdicts,
    load_verdicts, summarize_answers, verdict_template,
)
from retrieval.evaluation.harness import EvaluationError
from retrieval.generation.evidence import EvidenceAccess
from retrieval.generation.models import AnswerDraft, Verification
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index, read_corpus

WF = "SYN_WF_0001"
QUESTION = "Cách tháo nắp che?"


class StubModel:
    """One statement per question, built from the first eligible candidate."""

    def __init__(self, transform=None, verification=None, per_call=None):
        self.transform, self.verification = transform, verification
        # Recorded per call, like the real adapter: an abstain never reaches the model
        # and must therefore report zero tokens, not the tokens of some other question.
        self.per_call = {"input_tokens": 50, "output_tokens": 10, "total_tokens": 60} \
            if per_call is None else per_call
        self.usage, self.closed = [], False

    def draft(self, payload):
        self.usage.append(dict(self.per_call))
        item = payload["candidates"][0]
        draft = {"status": "answered", "statements": [{
            "text": item["claim"]["text"], "claim_ref": copy.deepcopy(item["claim_ref"]),
            "evidence_ids": [item["evidence"][0]["evidence"]["evidence_id"]]}]}
        if self.transform:
            self.transform(draft, payload)
        return AnswerDraft.model_validate(draft)

    def verify(self, payload):
        self.usage.append(dict(self.per_call))
        return self.verification or Verification(answers_question=True,
                                                 supported=[True] * len(payload["statements"]))

    def close(self):
        self.closed = True


def question(qid, text=QUESTION, *, status="answered", retrieval="retrieved", units=(), context=None,
             category="detail", intent="detail"):
    return {"question_id": qid, "source_type": "synthetic", "dataset_split": "dev", "language": "vi",
            "category": category, "intent": intent, "question": text,
            "context": {"machine_model": "DEMO_TC_A"} if context is None else context,
            "expected_status": status, "expected_retrieval_status": retrieval,
            "gold_units": [[{"workflow_id": WF, "revision": 1, "step_id": f"{WF}_{s}"}] for s in units],
            "label": {"status": "draft", "labeled_by": "test"}}


ANSWERABLE = question("Q1", units=["ST_001"])
OFF_TOPIC = question("Q2", "quantum chromodynamics", status="insufficient_evidence",
                     retrieval="insufficient_evidence", category="off_topic")


def setup(tmp_path, questions=(ANSWERABLE, OFF_TOPIC), bundle=None):
    db = tmp_path / "kb.sqlite"
    source = bundle or read_bundle(FIXTURE_ROOT / "F01_complete")
    import_bundle(write_bundle(tmp_path / "bundle", source), db, source_type="synthetic", split="dev")
    build_index(db, mode="synthetic", split="dev")
    path = tmp_path / "questions.jsonl"
    path.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questions), encoding="utf-8")
    return db, path


def run(tmp_path, questions=(ANSWERABLE, OFF_TOPIC), model=None, **kwargs):
    db, path = setup(tmp_path, questions)
    return evaluate_answers(db, path, mode="synthetic", split="dev", strategy="lexical", translate=False,
                            model_factory=lambda: model or StubModel(), model_name="stub",
                            repo_root=REPO_ROOT, **kwargs)


# --- the served run ---------------------------------------------------------


def test_run_scores_the_served_answer_and_keeps_abstains_apart(tmp_path):
    report, rows = run(tmp_path)
    summary = report["summary"]
    assert {r["question_id"]: r["status"] for r in rows} == {"Q1": "answered", "Q2": "insufficient_evidence"}
    assert summary["status"]["accuracy"] == 1.0
    assert summary["status"]["false_answer"] == [] and summary["status"]["false_abstention"] == []
    assert summary["citations"]["mechanically_valid"] == 1.0 and summary["citations"]["citations"] == 1
    assert summary["grounding"]["structural"] == 1.0
    assert summary["leakage"] == {"questions": [], "codes": {}}
    # Only Q1 reaches the model: retrieval abstains for Q2 before any provider call.
    assert summary["cost"]["provider_calls"] == 2  # draft + verify
    assert [r["provider_calls"] for r in rows] == [2, 0]
    assert report["config"]["strategy"] == "lexical" and report["answer_model"] == "stub"


def test_report_warns_while_no_human_graded_the_answers(tmp_path):
    report, _ = run(tmp_path)
    human = report["summary"]["human"]
    assert human["citation_correctness"] is None and human["answer_groundedness"] is None
    assert report["verdict_coverage"]["ungraded"] == ["Q1"]  # only answered questions need a verdict
    assert "not human-checked" in report["warning"] and "do not report as results" in report["warning"]


def test_human_verdict_produces_the_support_dependent_rates(tmp_path):
    report, rows = run(tmp_path)
    path = tmp_path / "verdicts.jsonl"
    path.write_text(json.dumps({
        "question_id": "Q1", "answer_sha256": rows[0]["answer_sha256"], "reviewer_id": "reviewer",
        "answers_question": True, "citations_supported": [True]}) + "\n", encoding="utf-8")
    report, _ = run(tmp_path, verdicts_path=path)
    human = report["summary"]["human"]
    assert human["citation_correctness"] == 1.0 and human["answer_groundedness"] == 1.0
    assert human["answers_question"] == 1.0 and human["graded_citations"] == 1
    assert report["verdict_coverage"] == {"graded": ["Q1"], "stale": [], "ungraded": []}


def test_a_verdict_for_a_different_answer_is_stale_not_reused(tmp_path):
    _, rows = run(tmp_path)
    rows[0]["verdict"] = None
    verdict = Verdict(question_id="Q1", answer_sha256="0" * 64, reviewer_id="reviewer",
                      answers_question=True, citations_supported=[True])
    coverage = join_verdicts(rows, {"Q1": verdict})
    assert coverage["stale"] == ["Q1"] and rows[0]["verdict"] == "stale"
    assert summarize_answers(rows)["human"]["citation_correctness"] is None


def test_verdict_must_grade_every_citation_of_that_answer(tmp_path):
    _, rows = run(tmp_path)
    verdict = Verdict(question_id="Q1", answer_sha256=rows[0]["answer_sha256"], reviewer_id="reviewer",
                      answers_question=True, citations_supported=[])
    with pytest.raises(EvaluationError, match="grades 0 citations"):
        join_verdicts(rows, {"Q1": verdict})


def test_verdict_template_pins_the_answer_and_leaves_judgements_blank(tmp_path):
    _, rows = run(tmp_path)
    entries = [json.loads(line) for line in verdict_template(rows, "reviewer").splitlines()]
    assert [e["question_id"] for e in entries] == ["Q1", "Q2"]
    assert entries[0]["answer_sha256"] == rows[0]["answer_sha256"]
    assert entries[0]["answers_question"] is None and entries[0]["citations_supported"] == [None]
    assert entries[0]["_citations"][0]["claim_ref"]["workflow_id"] == WF
    path = tmp_path / "t.jsonl"
    path.write_text("".join(json.dumps({**e, "answers_question": True,
                                        "citations_supported": [True] * len(e["citations_supported"])},
                                       ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    assert set(load_verdicts(path)) == {"Q1", "Q2"}  # underscore fields are ignored by the loader


def test_duplicate_verdicts_are_refused(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    entry = json.dumps({"question_id": "Q1", "answer_sha256": "a", "reviewer_id": "r",
                        "answers_question": True, "citations_supported": []})
    path.write_text(entry + "\n" + entry + "\n", encoding="utf-8")
    with pytest.raises(EvaluationError, match="duplicate verdict"):
        load_verdicts(path)


# --- the asymmetric status errors -------------------------------------------


def test_false_answer_and_false_abstention_are_named_separately(tmp_path):
    rows = [{**base, **extra} for base, extra in (
        (_row("Q1"), {"expected_status": "insufficient_evidence", "status": "answered"}),
        (_row("Q2"), {"expected_status": "answered", "status": "insufficient_evidence"}),
    )]
    for row in rows:
        row["status_ok"] = row["status"] == row["expected_status"]
        row["false_answer"] = row["status"] == "answered" and row["expected_status"] != "answered"
        row["false_abstention"] = row["expected_status"] == "answered" and row["status"] != "answered"
    summary = summarize_answers(rows)
    assert summary["status"]["false_answer"] == ["Q1"] and summary["status"]["false_abstention"] == ["Q2"]
    assert summary["status"]["accuracy"] == 0.0


def _row(qid, **extra):
    return {"question_id": qid, "category": "detail", "language": "vi", "labelled_intent": "detail",
            "label_status": "draft", "expected_status": "answered", "status": "answered", "status_ok": True,
            "false_answer": False, "false_abstention": False, "citations": [], "citation_count": 0,
            "valid_citations": 0, "citation_failures": [], "leakage": [], "missing_context": [],
            "unresolved_claim_refs": [], "answer": "", "answer_sha256": "x", "index_build_id": "i",
            "latency_ms": 1.0, "provider_calls": 2, "input_tokens": None, "output_tokens": None,
            "total_tokens": None, "verdict": None,
            "grounding": {"technical_lines": 0, "uncited_lines": [], "grounded_ratio": None,
                          "abstain_with_citations": False}, **extra}


# --- citation checks --------------------------------------------------------


@pytest.fixture
def served(tmp_path):
    db, _ = setup(tmp_path, [ANSWERABLE])
    corpus = read_corpus(db, "synthetic", "dev")
    request = QueryRequest(question=QUESTION, context=QueryContext(machine_model="DEMO_TC_A"),
                           mode="synthetic", dataset_split="dev")
    workflow = corpus["workflows"][WF]
    claim = next(c for c in workflow.claims
                 if any(link.support_status == "supported" for link in c.evidence_links))
    evidence_id = next(link.evidence_id for link in claim.evidence_links
                       if link.support_status == "supported")
    citation = Citation(answer_span=claim.text, evidence_ids=[evidence_id],
                        claim_ref=EntityRef(workflow_id=WF, revision=workflow.revision,
                                            entity_type="claim", entity_id=claim.claim_id),
                        source_review=claim.source_review, technical_review=claim.technical_review)
    return corpus, request, citation, EvidenceAccess(REPO_ROOT)


def test_a_well_formed_citation_passes_every_mechanical_check(served):
    corpus, request, citation, access = served
    assert check_citation(citation, corpus, request, access) == {
        "claim_ref": citation.claim_ref.model_dump(mode="json"), "answer_span": citation.answer_span,
        "evidence_ids": citation.evidence_ids, "failures": [], "valid": True}


@pytest.mark.parametrize("mutate,code", [
    (lambda c: c.model_copy(update={"claim_ref": c.claim_ref.model_copy(update={"entity_id": "CL_999"})}),
     "claim_not_in_snapshot"),
    (lambda c: c.model_copy(update={"claim_ref": c.claim_ref.model_copy(update={"workflow_id": "NOPE"})}),
     "workflow_not_in_active_index"),
    (lambda c: c.model_copy(update={"claim_ref": c.claim_ref.model_copy(update={"revision": 7})}),
     "not_the_active_revision"),
    (lambda c: c.model_copy(update={"evidence_ids": ["EV_DOES_NOT_EXIST"]}), "evidence_link_not_supported"),
    (lambda c: c.model_copy(update={"evidence_ids": []}), "no_evidence"),
    (lambda c: c.model_copy(update={"technical_review": "expert_validated"}),
     "review_flags_differ_from_snapshot"),
    (lambda c: c.model_copy(update={"answer_span": c.answer_span + " siết 45 Nm"}),
     "number_not_in_cited_evidence"),
])
def test_each_citation_defect_is_named(served, mutate, code):
    corpus, request, citation, access = served
    result = check_citation(mutate(citation), corpus, request, access)
    assert result["valid"] is False and code in result["failures"]


def test_a_duplicated_evidence_id_is_caught(served):
    corpus, request, citation, access = served
    doubled = citation.model_copy(update={"evidence_ids": citation.evidence_ids * 2})
    assert "duplicate_evidence_ids" in check_citation(doubled, corpus, request, access)["failures"]


# --- grounding and leakage --------------------------------------------------


def test_uncited_lines_are_ungrounded_and_abstains_must_not_cite(served):
    _, _, citation, _ = served
    answer = AnswerResponse(status="answered", answer=f"A: {citation.answer_span}\n\nB: uncited sentence.",
                            citations=[citation], missing_context=[], unresolved_claim_refs=[],
                            index_build_id="IDX")
    grounding = check_grounding(answer)
    assert grounding["technical_lines"] == 2 and grounding["grounded_ratio"] == 0.5
    assert grounding["uncited_lines"] == ["B: uncited sentence."]
    abstained = answer.model_copy(update={"status": "insufficient_evidence"})
    assert check_grounding(abstained)["abstain_with_citations"] is True


def test_leakage_flags_a_cited_workflow_for_another_machine(served):
    corpus, request, citation, _ = served
    answer = AnswerResponse(status="answered", answer=citation.answer_span, citations=[citation],
                            missing_context=[], unresolved_claim_refs=[], index_build_id="IDX")

    class Q:
        context = QueryContext(machine_model="VF-2")

    assert check_leakage(Q(), answer, corpus, request) == ["context_machine_model_mismatch"]

    class Same:
        context = QueryContext(machine_model="DEMO_TC_A")

    assert check_leakage(Same(), answer, corpus, request) == []


def test_leakage_flags_an_answer_built_from_two_workflows(served):
    corpus, request, citation, _ = served
    other = citation.model_copy(update={
        "claim_ref": citation.claim_ref.model_copy(update={"workflow_id": "OTHER_WF", "revision": 1})})
    answer = AnswerResponse(status="answered", answer="x", citations=[citation, other],
                            missing_context=[], unresolved_claim_refs=[], index_build_id="IDX")

    class Q:
        context = QueryContext(machine_model="DEMO_TC_A")

    assert check_leakage(Q(), answer, corpus, request) == ["corpus_mismatch", "spans_multiple_workflows"]


# --- cost and guards --------------------------------------------------------


def test_tokens_and_cost_come_from_the_provider_and_need_both_prices(tmp_path):
    price = {"input_per_million_usd": 10.0, "output_per_million_usd": 40.0}
    report, _ = run(tmp_path, questions=[ANSWERABLE], price=price)
    cost = report["summary"]["cost"]
    assert cost["input_tokens"] == 100 and cost["output_tokens"] == 20 and cost["total_tokens"] == 120
    assert cost["usd_total"] == round(100 / 1e6 * 10 + 20 / 1e6 * 40, 6)
    assert cost["usd_per_question"] == cost["usd_total"]
    without, _ = run(tmp_path, questions=[ANSWERABLE])
    assert without["summary"]["cost"]["usd_total"] is None


def test_an_abstain_costs_zero_tokens_not_the_tokens_of_another_question(tmp_path):
    _, rows = run(tmp_path)
    answered, abstained = rows
    assert answered["provider_calls"] == 2 and answered["total_tokens"] == 120
    assert abstained["provider_calls"] == 0 and abstained["total_tokens"] == 0
    report, _ = run(tmp_path, price={"input_per_million_usd": 10.0, "output_per_million_usd": 40.0})
    assert report["summary"]["cost"]["total_tokens"] == 120  # the abstain adds nothing, and hides nothing


def test_a_provider_without_token_counts_reports_null_not_zero(tmp_path):
    report, _ = run(tmp_path, questions=[ANSWERABLE], model=StubModel(per_call={}),
                    price={"input_per_million_usd": 1.0, "output_per_million_usd": 1.0})
    cost = report["summary"]["cost"]
    assert cost["provider_calls"] == 2  # the model WAS called; the counts are simply unknown
    assert cost["input_tokens"] is None and cost["total_tokens"] is None and cost["usd_total"] is None


def test_corpus_split_and_holdout_guards(tmp_path):
    db, path = setup(tmp_path)
    with pytest.raises(EvaluationError, match="another corpus"):
        evaluate_answers(db, path, mode="real", split="dev", strategy="lexical", translate=False,
                         model_factory=StubModel, repo_root=REPO_ROOT)
    with pytest.raises(EvaluationError, match="holdout stays locked"):
        evaluate_answers(db, path, mode="synthetic", split="holdout", strategy="lexical", translate=False,
                         model_factory=StubModel, repo_root=REPO_ROOT)


def test_a_provider_crash_is_reported_not_scored_as_an_abstain(tmp_path):
    """A dead provider must not be laundered into a well-behaved refusal."""

    class Broken(StubModel):
        def draft(self, payload):
            raise RuntimeError("provider down")

    report, rows = run(tmp_path, model=Broken())
    assert [r["question_id"] for r in rows] == ["Q2"]  # Q2 abstains before the model is called
    assert report["served_errors"] == [{"question_id": "Q1", "error": "RuntimeError"}]
    assert report["summary"]["status"]["false_abstention"] == []
    assert "1 questions returned a served error" in report["warning"]


def test_cli_writes_report_rows_and_verdict_template(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("retrieval.evaluation.__main__.GeminiAnswerModel", lambda *a, **k: StubModel())
    db, path = setup(tmp_path)
    out = tmp_path / "eval"
    assert main(["answers", "--db", str(db), "--questions", str(path), "--mode", "synthetic",
                 "--strategy", "lexical", "--no-translation", "--out", str(out),
                 "--verdict-template", "reviewer"]) == 0
    printed = capsys.readouterr().out
    assert "WARNING" in printed and "needs a human verdict" in printed
    run_dir = next(out.iterdir())
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["status"]["accuracy"] == 1.0
    assert len((run_dir / "rows.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert len((run_dir / "verdicts.template.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_cli_refuses_one_sided_pricing(tmp_path, capsys):
    db, path = setup(tmp_path)
    assert main(["answers", "--db", str(db), "--questions", str(path), "--mode", "synthetic",
                 "--price-input", "1.0"]) == 1
    assert "both --price-input and --price-output" in capsys.readouterr().err


def test_answer_digest_changes_with_the_answer(served):
    _, _, citation, _ = served
    answer = AnswerResponse(status="answered", answer="text", citations=[citation], missing_context=[],
                            unresolved_claim_refs=[], index_build_id="IDX")
    assert answer_digest(answer) != answer_digest(answer.model_copy(update={"answer": "text."}))
    assert answer_digest(answer) != answer_digest(answer.model_copy(update={"citations": []}))
