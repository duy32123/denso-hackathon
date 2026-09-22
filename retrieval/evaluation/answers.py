"""WP3 answer evaluation: citation correctness, groundedness, abstain, leakage, cost.

Plan section 4 asks for two things this module keeps strictly apart.

What code can prove is proved on every answer: that a cited claim exists in the
chosen snapshot at the active revision, that its evidence links are `supported`
and openable, that the citation's review flags equal the snapshot's, that every
number in a sentence occurs in the evidence that sentence cites, and that no
answer crossed a corpus, model or workflow boundary. A failure here is a defect.

Whether a source really SUPPORTS a sentence in natural language is a human
judgement. The pipeline's own verifier is part of what is measured here and is
never allowed to grade itself, so the support-dependent rates stay null until a
human verdict file is supplied, and every report states how much was graded.

Runs the served path (`QAService`), not a reimplementation of it: the numbers
describe what `/v1/ask` does, including its retrieval config and index checks.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field, ValidationError

from knowflow_contracts.eligibility import claim_blockers
from knowflow_contracts.enums import QueryMode
from knowflow_contracts.models import AnswerResponse, Citation, NonEmptyStr, QueryRequest, Strict, Workflow
from retrieval.generation.engine import numbers
from retrieval.generation.evidence import EvidenceAccess
from retrieval.generation.gemini import GeminiAnswerModel
from retrieval.generation.service import QAService
from retrieval.indexing.embeddings import Embedder, GeminiEmbedder
from retrieval.indexing.search_index import digest, read_corpus, require_index
from retrieval.retrieval.context import context_gate
from retrieval.retrieval.engine import RetrievalConfig, retrieve
from retrieval.retrieval.query import GeminiTranslator, Translator

from .harness import (
    REPO_ROOT, EvaluationError, QueryCache, TranslationCache, check_gold, git_state, load_questions, mean, percentile,
)

ABSTAIN = ("needs_clarification", "insufficient_evidence", "conflicting_sources")


class Verdict(Strict):
    """One human judgement of one produced answer, pinned to that exact answer.

    `answer_sha256` makes a verdict unusable once the answer changes, so a rate can
    never be carried over from a different pipeline version by accident.
    """

    question_id: NonEmptyStr
    answer_sha256: NonEmptyStr
    reviewer_id: NonEmptyStr
    reviewed_at: str | None = None
    answers_question: bool
    citations_supported: list[bool] = Field(default_factory=list)
    note: str = ""


def answer_digest(answer: AnswerResponse) -> str:
    return digest([str(answer.status), answer.answer,
                   [c.model_dump(mode="json") for c in answer.citations]])


def load_verdicts(path: str | Path) -> dict[str, Verdict]:
    verdicts: dict[str, Verdict] = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            # `_`-prefixed keys are the reviewer's copy of the answer, not judgements.
            entry = {key: value for key, value in json.loads(line).items() if not key.startswith("_")}
            verdict = Verdict.model_validate(entry)
        except (ValidationError, ValueError) as exc:
            raise EvaluationError(f"{path}:{number}: {exc}") from None
        if verdict.question_id in verdicts:
            raise EvaluationError(f"{path}:{number}: duplicate verdict for {verdict.question_id}")
        verdicts[verdict.question_id] = verdict
    return verdicts


def check_citation(citation: Citation, corpus: dict, request: QueryRequest, access: EvidenceAccess) -> dict:
    """Mechanical citation checks. Codes name the defect, so a report is actionable."""
    ref, failures = citation.claim_ref, []
    row = {"claim_ref": ref.model_dump(mode="json"), "answer_span": citation.answer_span,
           "evidence_ids": list(citation.evidence_ids), "failures": failures}
    workflow: Workflow | None = corpus["workflows"].get(ref.workflow_id)
    if workflow is None:
        failures.append("workflow_not_in_active_index")
        return {**row, "valid": False}
    if (workflow.source_type, workflow.dataset_split) != (request.mode, request.dataset_split):
        failures.append("namespace_mismatch")
    if ref.entity_type != "claim":
        failures.append("not_a_claim_ref")
    # The index serves one active revision; a citation to any other cannot be opened from it.
    if ref.revision != workflow.revision:
        failures.append("not_the_active_revision")
    claim = next((c for c in workflow.claims if c.claim_id == ref.entity_id), None)
    if claim is None:
        failures.append("claim_not_in_snapshot")
        return {**row, "valid": False}
    if (str(citation.source_review) != str(claim.source_review)
            or str(citation.technical_review) != str(claim.technical_review)):
        failures.append("review_flags_differ_from_snapshot")
    if claim_blockers(claim, workflow, mode=QueryMode(request.mode),
                      is_latest_indexed_revision=ref.revision == workflow.revision):
        failures.append("claim_not_eligible")
    if not citation.evidence_ids:
        failures.append("no_evidence")
    if len(set(citation.evidence_ids)) != len(citation.evidence_ids):
        failures.append("duplicate_evidence_ids")
    supported = {link.evidence_id for link in claim.evidence_links if link.support_status == "supported"}
    by_id = {e.evidence_id: e for e in workflow.evidence}
    literal = []
    for evidence_id in citation.evidence_ids:
        if evidence_id not in supported:
            failures.append("evidence_link_not_supported")
            continue
        evidence = by_id.get(evidence_id)
        if evidence is None:
            failures.append("evidence_not_in_snapshot")
            continue
        source = corpus["sources"].get(evidence.source_id)
        if source is None or source.source_type != request.mode:
            failures.append("evidence_source_namespace")
            continue
        if not access.view(evidence, source).available:
            failures.append("evidence_not_openable")
            continue
        literal.append((evidence.quote or "") + " " + (evidence.observation_note or ""))
    if not numbers(citation.answer_span) <= numbers(" ".join(literal)):
        failures.append("number_not_in_cited_evidence")
    return {**row, "valid": not failures}


def check_grounding(answer: AnswerResponse) -> dict:
    """Structure only: every technical line of an answer must be a cited span.

    This is the denominator of groundedness, never the verdict. An uncited line is
    ungrounded for certain; a cited one is grounded only if a human says the source
    supports it.
    """
    if str(answer.status) != "answered":
        return {"technical_lines": 0, "uncited_lines": [], "grounded_ratio": None,
                "abstain_with_citations": bool(answer.citations)}
    lines = [line.strip() for line in answer.answer.splitlines() if line.strip()]
    spans = [c.answer_span.strip() for c in answer.citations if c.answer_span.strip()]
    uncited = [line for line in lines if not any(span in line for span in spans)]
    return {"technical_lines": len(lines), "uncited_lines": uncited,
            "grounded_ratio": (len(lines) - len(uncited)) / len(lines) if lines else None,
            "abstain_with_citations": False}


def check_leakage(question, answer: AnswerResponse, corpus: dict, request: QueryRequest) -> list[str]:
    """Corpus and model boundaries (plan section 5: zero failures in the required cases).

    Uses the same context gate as the retrieval hard filter, so an alias such as
    `Haas Automation` is not reported as a different machine.
    """
    codes = []
    keys = {(c.claim_ref.workflow_id, c.claim_ref.revision) for c in answer.citations}
    if len(keys) > 1:
        codes.append("spans_multiple_workflows")  # D-06: a procedure no source describes
    for ref in [c.claim_ref for c in answer.citations] + list(answer.unresolved_claim_refs):
        workflow = corpus["workflows"].get(ref.workflow_id)
        if workflow is None or (workflow.source_type, workflow.dataset_split) != (request.mode,
                                                                                 request.dataset_split):
            codes.append("corpus_mismatch")
    for workflow_id, _ in keys:
        workflow = corpus["workflows"].get(workflow_id)
        if workflow is not None:
            codes += [f"context_{field}_mismatch" for field in context_gate(workflow, question.context)[0]]
    return sorted(set(codes))


class CountingModel:
    """Attribute provider calls and tokens to one question; never alters the payloads."""

    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def draft(self, payload):
        self.calls += 1
        return self.inner.draft(payload)

    def verify(self, payload):
        self.calls += 1
        return self.inner.verify(payload)

    @property
    def usage(self) -> list[dict]:
        return list(getattr(self.inner, "usage", []))

    def close(self):
        self.inner.close()


def _tokens(usage: list[dict], field: str) -> int | None:
    """Zero when the model was never called; None when a call did not report the count.

    The difference matters: an abstain really does cost nothing, while a missing
    count must not be summed as 0 and passed off as a measured cost.
    """
    if not usage:
        return 0
    values = [call[field] for call in usage if call.get(field) is not None]
    return sum(values) if len(values) == len(usage) else None


def evaluate_one(question, answer: AnswerResponse, corpus: dict, request: QueryRequest,
                 access: EvidenceAccess, *, latency_ms: float, recorder: CountingModel) -> dict:
    status, expected = str(answer.status), str(question.expected_status)
    citations = [check_citation(c, corpus, request, access) for c in answer.citations]
    usage = recorder.usage
    return {
        "question_id": question.question_id, "category": question.category, "language": question.language,
        "labelled_intent": question.intent, "label_status": question.label.status,
        "expected_status": expected, "status": status, "status_ok": status == expected,
        # The two asymmetric errors: answering when the sources cannot carry it is the
        # dangerous one; refusing an answerable question is the one abstain rates hide.
        "false_answer": status == "answered" and expected in ABSTAIN,
        "false_abstention": expected == "answered" and status in ABSTAIN,
        "citations": citations, "citation_count": len(citations),
        "valid_citations": sum(c["valid"] for c in citations),
        "citation_failures": sorted({code for c in citations for code in c["failures"]}),
        "grounding": check_grounding(answer),
        "leakage": check_leakage(question, answer, corpus, request),
        "missing_context": list(answer.missing_context),
        "unresolved_claim_refs": [r.model_dump(mode="json") for r in answer.unresolved_claim_refs],
        "answer": answer.answer, "answer_sha256": answer_digest(answer),
        "index_build_id": answer.index_build_id,
        "latency_ms": round(latency_ms, 2), "provider_calls": recorder.calls,
        "input_tokens": _tokens(usage, "input_tokens"), "output_tokens": _tokens(usage, "output_tokens"),
        "total_tokens": _tokens(usage, "total_tokens"),
    }


def join_verdicts(rows: list[dict], verdicts: dict[str, Verdict]) -> dict:
    """Attach human verdicts, refusing any pinned to a different answer."""
    graded, stale, ungraded = [], [], []
    for row in rows:
        verdict = verdicts.get(row["question_id"])
        if verdict is None:
            row["verdict"] = None
            if row["status"] == "answered":
                ungraded.append(row["question_id"])
            continue
        if verdict.answer_sha256 != row["answer_sha256"]:
            row["verdict"] = "stale"
            stale.append(row["question_id"])
            continue
        if len(verdict.citations_supported) != row["citation_count"]:
            raise EvaluationError(
                f"{row['question_id']}: verdict grades {len(verdict.citations_supported)} citations, "
                f"the answer has {row['citation_count']}")
        row["verdict"] = verdict.model_dump(mode="json")
        graded.append(row["question_id"])
    return {"graded": graded, "stale": stale, "ungraded": ungraded}


def _human_rates(rows: list[dict]) -> dict:
    """The rates that need a human verdict; null while nothing is graded.

    A citation is correct only when code proved it valid AND a reviewer found the
    source supports the sentence: the mechanical pass is a floor, not the measure.
    """
    graded = [r for r in rows if isinstance(r.get("verdict"), dict)]
    if not graded:
        return {"citation_correctness": None, "answer_groundedness": None, "answers_question": None,
                "graded_questions": 0, "graded_citations": 0}
    correct, grounded = [], []
    for row in graded:
        flags = [citation["valid"] and supported for citation, supported
                 in zip(row["citations"], row["verdict"]["citations_supported"])]
        correct += flags
        lines = row["grounding"]["technical_lines"]
        if row["status"] == "answered" and lines:
            # One statement per line; a line can be carried by at most one citation.
            grounded.append(min(sum(flags), lines) / lines)
    answered = [r for r in graded if r["status"] == "answered"]
    return {"citation_correctness": mean(correct), "answer_groundedness": mean(grounded),
            "answers_question": mean(r["verdict"]["answers_question"] for r in answered),
            "graded_questions": len(graded), "graded_citations": len(correct)}


def summarize_answers(rows: list[dict], *, price: dict | None = None) -> dict:
    answered = [r for r in rows if r["status"] == "answered"]
    citations = [c for r in rows for c in r["citations"]]
    confusion: dict[str, Counter] = {}
    for row in rows:
        confusion.setdefault(row["expected_status"], Counter())[row["status"]] += 1
    tokens = {field: (sum(r[field] for r in rows if r[field] is not None)
                      if all(r[field] is not None for r in rows) and rows else None)
              for field in ("input_tokens", "output_tokens", "total_tokens")}
    cost = None
    if price and tokens["input_tokens"] is not None and tokens["output_tokens"] is not None:
        cost = round(tokens["input_tokens"] / 1e6 * price["input_per_million_usd"]
                     + tokens["output_tokens"] / 1e6 * price["output_per_million_usd"], 6)
    return {
        "questions": len(rows), "answered": len(answered),
        "status": {
            "accuracy": mean(r["status_ok"] for r in rows),
            "confusion": {expected: dict(counts) for expected, counts in sorted(confusion.items())},
            "false_answer": [r["question_id"] for r in rows if r["false_answer"]],
            "false_abstention": [r["question_id"] for r in rows if r["false_abstention"]],
            "by_expected": {expected: {"questions": sum(counts.values()),
                                       "accuracy": round(counts.get(expected, 0) / sum(counts.values()), 4)}
                            for expected, counts in sorted(confusion.items())},
        },
        "citations": {
            "citations": len(citations),
            "mechanically_valid": mean(c["valid"] for c in citations),
            "answers_without_citations": [r["question_id"] for r in answered if not r["citations"]],
            "failure_codes": dict(Counter(code for c in citations for code in c["failures"]).most_common()),
            "questions_with_invalid": [r["question_id"] for r in rows
                                       if any(not c["valid"] for c in r["citations"])],
        },
        "grounding": {
            "structural": mean(r["grounding"]["grounded_ratio"] for r in answered
                               if r["grounding"]["grounded_ratio"] is not None),
            "uncited_lines": {r["question_id"]: r["grounding"]["uncited_lines"]
                              for r in answered if r["grounding"]["uncited_lines"]},
            "abstain_with_citations": [r["question_id"] for r in rows
                                       if r["grounding"]["abstain_with_citations"]],
        },
        # Required to be zero. A non-empty list is a release blocker, not a metric.
        "leakage": {"questions": [r["question_id"] for r in rows if r["leakage"]],
                    "codes": dict(Counter(code for r in rows for code in r["leakage"]).most_common())},
        "human": _human_rates(rows),
        "latency_ms": {"p50": percentile([r["latency_ms"] for r in rows], .5),
                       "p95": percentile([r["latency_ms"] for r in rows], .95)},
        "cost": {"provider_calls": sum(r["provider_calls"] for r in rows), **tokens,
                 "usd_total": cost, "pricing": price,
                 "usd_per_question": round(cost / len(rows), 6) if cost is not None and rows else None},
    }


def evaluate_answers(db: str | Path, questions_path: str | Path, *, mode: str, split: str,
                     strategy: str = "hybrid", top_k: int = 5, candidate_k: int = 20,
                     min_cosine: float = .25, rrf_k: int = 60, min_term_coverage: float = .20,
                     translate: bool = True, embedder: Embedder | None = None,
                     query_cache: str | Path | None = None, translator: Translator | None = None,
                     translation_cache: str | Path | None = None, model_factory=GeminiAnswerModel,
                     model_name: str | None = None, verdicts_path: str | Path | None = None,
                     price: dict | None = None, repo_root: Path = REPO_ROOT,
                     relevance_policy: str = "claim_coherence") -> tuple[dict, list[dict]]:
    """Ask every question through the served QA path and score the answers."""
    if split != "dev":
        raise EvaluationError("QAService serves dev only; holdout stays locked until the D15 lock is lifted")
    config = RetrievalConfig(strategy=strategy, top_k=top_k, candidate_k=candidate_k, min_cosine=min_cosine,
                             rrf_k=rrf_k, min_term_coverage=min_term_coverage,
                             query_translation="auto" if translate else "never", relevance_policy=relevance_policy)
    questions, questions_sha256 = load_questions(questions_path)
    wrong = [q.question_id for q in questions if (q.source_type, q.dataset_split) != (mode, split)]
    if wrong:
        raise EvaluationError(f"Questions from another corpus/split: {', '.join(wrong)}")
    corpus = read_corpus(db, mode, split)
    manifest, _ = require_index(corpus)
    check_gold(questions, corpus["workflows"])
    owned_embedder = owned_translator = None
    if strategy != "lexical" and embedder is None:
        expected = manifest["embedding"]
        if expected is None:
            raise EvaluationError("Index has no vectors; rebuild with --embedding gemini or use lexical")
        if expected["provider"] != "gemini":
            raise EvaluationError("No query adapter for the indexed embedding provider")
        embedder = owned_embedder = GeminiEmbedder(expected["dimensions"])
    if translate and translator is None:
        translator = owned_translator = GeminiTranslator()
    cache = QueryCache(embedder, query_cache) if embedder else None
    translation = TranslationCache(translator, translation_cache) if translate else None

    def retriever(database, request, *, config=None):
        return retrieve(database, request, config=config, embedder=cache, translator=translation)

    recorders: list[CountingModel] = []

    def factory():
        recorder = CountingModel(model_factory())
        recorders.append(recorder)
        return recorder

    service = QAService({(mode, split): Path(db)}, repo_root=repo_root, config=config,
                        model_factory=factory, retriever=retriever)
    access = EvidenceAccess(repo_root)
    rows, served_errors = [], []
    try:
        for question in questions:
            request = QueryRequest(question=question.question, context=question.context,
                                   mode=mode, dataset_split=split)
            for reused_cache in (c for c in (cache, translation) if c):
                reused_cache.reused_ms = 0.0
            recorders.clear()
            start = time.perf_counter()
            try:
                answer = service.ask(request)
            except Exception as exc:  # a served error is a result to report, not a crashed run
                served_errors.append({"question_id": question.question_id, "error": type(exc).__name__})
                continue
            reused = sum(c.reused_ms for c in (cache, translation) if c)
            rows.append(evaluate_one(question, answer, read_corpus(db, mode, split), request, access,
                                     latency_ms=(time.perf_counter() - start) * 1000 + reused,
                                     recorder=recorders[-1]))
    finally:
        if owned_embedder:
            owned_embedder.close()
        if owned_translator:
            owned_translator.close()
    if not rows:
        raise EvaluationError("No question produced an answer; see the served errors")
    coverage = join_verdicts(rows, load_verdicts(verdicts_path) if verdicts_path else {})
    labels = Counter(q.label.status for q in questions)
    created = datetime.now(timezone.utc)
    report = {
        "run_id": f"ANS_{created:%Y%m%dT%H%M%SZ}_"
                  + digest([questions_sha256, manifest["index_build_id"], vars(config)])[:8],
        "created_at": created.isoformat(timespec="seconds"), "git": git_state(), "db": str(db),
        "source_type": mode, "dataset_split": split,
        "index_build_id": manifest["index_build_id"], "embedding": manifest["embedding"],
        "answer_model": model_name, "questions_path": str(questions_path),
        "questions_sha256": questions_sha256, "questions": len(questions),
        "gold_labels": {status: labels[status] for status in ("draft", "ai_reviewed", "reviewed")},
        "config": dict(vars(config)), "served_errors": served_errors,
        "verdicts_path": str(verdicts_path) if verdicts_path else None,
        "verdict_coverage": coverage,
        "summary": summarize_answers(rows, price=price),
    }
    warnings = []
    unchecked = labels["draft"] + labels["ai_reviewed"]
    if unchecked:
        warnings.append(f"{unchecked} gold labels are not human-checked (draft {labels['draft']}, "
                        f"AI-reviewed {labels['ai_reviewed']})")
    if coverage["ungraded"] or coverage["stale"]:
        warnings.append(f"{len(coverage['ungraded'])} answers ungraded, {len(coverage['stale'])} verdicts "
                        "stale: citation correctness and groundedness are NOT measured, and the pipeline's "
                        "own verifier does not count as a review")
    if served_errors:
        warnings.append(f"{len(served_errors)} questions returned a served error and are not scored")
    if warnings:
        report["warning"] = "; ".join(warnings) + " -- debugging only, do not report as results"
    return report, rows


def verdict_template(rows: list[dict], reviewer_id: str) -> str:
    """Skeleton verdict file: the hashes are filled in, the judgements are not.

    `_answer` and `_citations` are there for the reviewer to read; the loader ignores
    underscore fields, so a filled sheet stays one file.
    """
    lines = []
    for row in rows:
        lines.append(json.dumps({
            "question_id": row["question_id"], "answer_sha256": row["answer_sha256"],
            "reviewer_id": reviewer_id, "reviewed_at": None,
            "answers_question": None, "citations_supported": [None] * row["citation_count"],
            "note": "", "_question_status": row["status"], "_answer": row["answer"],
            "_citations": [{"answer_span": c["answer_span"], "claim_ref": c["claim_ref"],
                            "evidence_ids": c["evidence_ids"], "mechanical_failures": c["failures"]}
                           for c in row["citations"]],
        }, ensure_ascii=False))
    return "".join(line + "\n" for line in lines)


def format_answer_summary(report: dict) -> str:
    summary, labels = report["summary"], report["gold_labels"]
    status, human, cost = summary["status"], summary["human"], summary["cost"]

    def fmt(value) -> str:
        return "-" if value is None else f"{value:.3f}"

    # Six decimals: a per-run cost of a few cents must not round away to $0.00.
    usd = "-" if cost["usd_total"] is None else f"${cost['usd_total']:.6f}"
    lines = [
        f"{report['run_id']}  {report['source_type']}/{report['dataset_split']}  "
        f"index {report['index_build_id']}",
        f"questions {report['questions']} (answered {summary['answered']}); "
        f"strategy {report['config']['strategy']}; model {report['answer_model'] or 'unknown'}; "
        f"gold draft {labels['draft']} / ai {labels['ai_reviewed']} / reviewed {labels['reviewed']}",
    ]
    if "warning" in report:
        lines.append("WARNING: " + report["warning"])
    lines += [
        "",
        "-- proved by code ------------------------------------------------",
        f"status accuracy        {fmt(status['accuracy'])}",
        f"  false_answer         {status['false_answer'] or '[]'}",
        f"  false_abstention     {status['false_abstention'] or '[]'}",
        f"citations valid        {fmt(summary['citations']['mechanically_valid'])} "
        f"of {summary['citations']['citations']} citations",
        f"grounding (structure)  {fmt(summary['grounding']['structural'])}  "
        f"abstain_with_citations={summary['grounding']['abstain_with_citations'] or '[]'}",
        f"leakage                {len(summary['leakage']['questions'])} questions"
        + (f"  {summary['leakage']['codes']}" if summary["leakage"]["codes"] else ""),
        "",
        "-- needs a human verdict -----------------------------------------",
        f"citation correctness   {fmt(human['citation_correctness'])}",
        f"answer groundedness    {fmt(human['answer_groundedness'])}",
        f"answers the question   {fmt(human['answers_question'])}",
        f"  graded               {human['graded_questions']} questions "
        f"({human['graded_citations']} citations); ungraded "
        f"{len(report['verdict_coverage']['ungraded'])}, stale "
        f"{len(report['verdict_coverage']['stale'])}",
        "",
        f"latency p50 {summary['latency_ms']['p50']} ms   p95 {summary['latency_ms']['p95']} ms   "
        f"provider calls {cost['provider_calls']}",
        f"tokens in {cost['input_tokens']} out {cost['output_tokens']} total {cost['total_tokens']}   "
        f"cost {usd}",
    ]
    if summary["citations"]["failure_codes"]:
        lines.append("citation failures: " + json.dumps(summary["citations"]["failure_codes"],
                                                        ensure_ascii=False))
    return "\n".join(lines)
