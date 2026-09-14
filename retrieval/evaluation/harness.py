"""WP2 retrieval evaluation: lexical, vector and hybrid on one KB and one filter policy.

Measures retrieval only (plan section 4). Questions whose expected ANSWER is an
abstain or a clarification stay out of the recall denominator and are reported
by status instead, so the system cannot look good by refusing. Gold labels that
no human has checked are flagged in every report; do not quote those numbers.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from knowflow_contracts.enums import AnswerStatus, DatasetSplit, SourceType
from knowflow_contracts.models import NonEmptyStr, QueryContext, QueryRequest, Strict
from retrieval.indexing.embeddings import Embedder, GeminiEmbedder
from retrieval.indexing.search_index import digest, read_corpus, require_index
from retrieval.retrieval.engine import RetrievalConfig, retrieve

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ("lexical", "vector", "hybrid")
RetrievalStatus = Literal["retrieved", "needs_clarification", "insufficient_evidence", "conflicting_sources"]
StepKey = tuple[str, int, str]


class EvaluationError(ValueError):
    pass


class StepRef(Strict):
    workflow_id: NonEmptyStr
    revision: int
    step_id: NonEmptyStr

    @property
    def key(self) -> StepKey:
        return (self.workflow_id, self.revision, self.step_id)


class WorkflowRef(Strict):
    workflow_id: NonEmptyStr
    revision: int


class Label(Strict):
    """Only status=reviewed is the human gold check (plan section 4).

    An AI pass is kept apart in the ai_* fields and never lifts the draft warning.
    """

    status: Literal["draft", "ai_reviewed", "reviewed"]
    labeled_by: NonEmptyStr
    reviewed_by: str | None = None
    note: str = ""
    reviewed_at: str | None = None
    review_note: str = ""
    ai_reviewed_by: str | None = None
    ai_reviewed_at: str | None = None
    ai_review_note: str = ""

    @model_validator(mode="after")
    def _reviewer_named(self) -> "Label":
        if self.status == "reviewed" and not self.reviewed_by:
            raise ValueError("label.status=reviewed requires reviewed_by")
        if self.status == "ai_reviewed" and not self.ai_reviewed_by:
            raise ValueError("label.status=ai_reviewed requires ai_reviewed_by")
        return self


class EvalQuestion(Strict):
    """One question; gold units list interchangeable Steps (any one counts)."""

    question_id: NonEmptyStr
    source_type: SourceType
    dataset_split: DatasetSplit
    language: Literal["vi", "en"]
    category: NonEmptyStr
    intent: Literal["detail", "procedure"]
    question: NonEmptyStr
    context: QueryContext
    expected_status: AnswerStatus  # answer level, for WP3 / end-to-end
    expected_retrieval_status: RetrievalStatus
    gold_units: list[list[StepRef]] = Field(default_factory=list)
    gold_workflows: list[WorkflowRef] = Field(default_factory=list)
    label: Label

    @model_validator(mode="after")
    def _gold_fits_expectation(self) -> "EvalQuestion":
        if any(not unit for unit in self.gold_units):
            raise ValueError("each gold unit lists at least one acceptable step")
        if self.expected_status == AnswerStatus.ANSWERED and self.expected_retrieval_status != "retrieved":
            raise ValueError("an answered question must expect expected_retrieval_status=retrieved")
        if self.scored and not self.gold_units:
            raise ValueError("answered detail question needs gold_units")
        if self.intent == "procedure" and self.expected_status == AnswerStatus.ANSWERED and not self.gold_workflows:
            raise ValueError("answered procedure question needs gold_workflows")
        if self.expected_retrieval_status != "retrieved" and (self.gold_units or self.gold_workflows):
            raise ValueError("gold refs require expected_retrieval_status=retrieved")
        return self

    @property
    def scored(self) -> bool:
        """In the Recall/MRR denominator: an expected answer with step-level gold."""
        return self.expected_status == AnswerStatus.ANSWERED and self.intent == "detail"

    @property
    def acceptable_workflows(self) -> set[tuple[str, int]]:
        refs = [*self.gold_workflows, *(ref for unit in self.gold_units for ref in unit)]
        return {(ref.workflow_id, ref.revision) for ref in refs}


class QueryCache:
    """Share one query embedding across vector/hybrid; config stays the adapter's."""

    def __init__(self, inner: Embedder):
        self.inner, self.calls, self._vectors = inner, 0, {}

    @property
    def config(self) -> dict:
        return self.inner.config

    def documents(self, texts: list[str]) -> list[list[float]]:
        raise EvaluationError("Evaluation never embeds documents")

    def query(self, text: str) -> list[float]:
        if text not in self._vectors:
            self._vectors[text] = self.inner.query(text)
            self.calls += 1
        return self._vectors[text]


def load_questions(path: str | Path) -> tuple[list[EvalQuestion], str]:
    data = Path(path).read_bytes()
    questions = []
    for number, line in enumerate(data.decode("utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            questions.append(EvalQuestion.model_validate_json(line))
        except ValidationError as exc:
            raise EvaluationError(f"{path}:{number}: {exc}") from None
    if not questions:
        raise EvaluationError(f"{path}: no questions")
    duplicates = [qid for qid, n in Counter(q.question_id for q in questions).items() if n > 1]
    if duplicates:
        raise EvaluationError(f"duplicate question_id: {', '.join(duplicates)}")
    return questions, hashlib.sha256(data).hexdigest()


def check_gold(questions: list[EvalQuestion], workflows: dict) -> None:
    """Gold is pinned to a revision; after a new revision it is relabeled, not guessed."""
    stale = []
    for q in questions:
        for ref in (ref for unit in q.gold_units for ref in unit):
            wf = workflows.get(ref.workflow_id)
            if wf is None or wf.revision != ref.revision or ref.step_id not in {s.step_id for s in wf.steps}:
                stale.append(f"{q.question_id}: {ref.workflow_id}@r{ref.revision}/{ref.step_id}")
        for ref in q.gold_workflows:
            wf = workflows.get(ref.workflow_id)
            if wf is None or wf.revision != ref.revision:
                stale.append(f"{q.question_id}: {ref.workflow_id}@r{ref.revision}")
    if stale:
        raise EvaluationError(
            "Gold refs are not in the active corpus; relabel against current revisions:\n" + "\n".join(stale)
        )


def score_ranking(ranked: list[StepKey], units: list[set[StepKey]], k: int) -> dict:
    """Recall = share of gold units with an acceptable step in top-k; RR from the first hit."""
    top = ranked[:k]
    hits = [any(key in unit for unit in units) for key in top]
    first = hits.index(True) + 1 if any(hits) else None
    return {"recall": sum(any(key in unit for key in top) for unit in units) / len(units),
            "reciprocal_rank": 1 / first if first else 0.0, "first_relevant_rank": first}


def _evaluate_one(db, q: EvalQuestion, mode: str, split: str, config: RetrievalConfig,
                  embedder: QueryCache | None, index_build_id: str) -> dict:
    result = retrieve(db, QueryRequest(question=q.question, context=q.context, mode=mode, dataset_split=split),
                      config=config, embedder=embedder)
    if result["index_build_id"] != index_build_id:
        raise EvaluationError("Active index changed during evaluation; rerun")
    units = [{ref.key for ref in unit} for unit in q.gold_units]
    relevant = set().union(*units)
    selected = result["selected_workflow"]
    acceptable = q.acceptable_workflows
    row = {
        "question_id": q.question_id, "strategy": config.strategy, "category": q.category,
        "language": q.language, "intent": q.intent, "label_status": q.label.status,
        "expected_status": str(q.expected_status), "expected_retrieval_status": q.expected_retrieval_status,
        "status": result["status"], "status_ok": result["status"] == q.expected_retrieval_status,
        "scored": q.scored,
        "selected_workflow": [selected["workflow_id"], selected["revision"]] if selected else None,
        "workflow_ok": ((selected["workflow_id"], selected["revision"]) in acceptable if selected else False)
        if acceptable else None,
        "workflow_candidates": [{"workflow_id": w["workflow_id"], "score": w["score"]}
                                for w in result["workflow_candidates"]],
        "retrieved": [{"workflow_id": s["workflow_id"], "revision": s["revision"], "step_id": s["step_id"],
                       "score": s["score"], "lexical_score": s["lexical_score"], "vector_score": s["vector_score"],
                       "relevant": (s["workflow_id"], s["revision"], s["step_id"]) in relevant}
                      for s in result["steps"]],
        "missing_context": result["missing_context"],
        "claim_count": len(result["claims"]), "conflict_count": len(result["conflicts"]),
        "latency_ms": result["trace"]["latency_ms"], "embedding_calls": result["trace"]["embedding_calls"],
        "recall": None, "reciprocal_rank": None, "first_relevant_rank": None,
    }
    if q.scored:
        ranked = [(s["workflow_id"], s["revision"], s["step_id"]) for s in result["steps"]]
        row.update(score_ranking(ranked, units, config.top_k))
    return row


def _mean(values) -> float | None:
    values = [float(v) for v in values]
    return round(sum(values) / len(values), 4) if values else None


def _percentile(values: list[float], q: float) -> float | None:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else None


def _groups(rows: list[dict], field: str, k: int) -> dict:
    result = {}
    for value in sorted({r[field] for r in rows}):
        group = [r for r in rows if r[field] == value]
        result[value] = {"questions": len(group), "status_accuracy": _mean(r["status_ok"] for r in group),
                         f"recall_at_{k}": _mean(r["recall"] for r in group if r["scored"])}
    return result


def summarize(rows: list[dict], k: int) -> dict:
    scored = [r for r in rows if r["scored"]]
    routed = [r for r in rows if r["workflow_ok"] is not None]
    confusion: dict[str, Counter] = {}
    for r in rows:
        confusion.setdefault(r["expected_retrieval_status"], Counter())[r["status"]] += 1
    return {
        "questions": len(rows),
        "retrieval": {
            "questions": len(scored),
            f"recall_at_{k}": _mean(r["recall"] for r in scored),
            f"mrr_at_{k}": _mean(r["reciprocal_rank"] for r in scored),
            "hit_at_1": _mean(r["first_relevant_rank"] == 1 for r in scored),
            "answer_coverage": _mean(r["status"] == "retrieved" for r in scored),
            "incomplete_recall": [r["question_id"] for r in scored if r["recall"] < 1],
        },
        "workflow_selection": {
            "questions": len(routed), "accuracy": _mean(r["workflow_ok"] for r in routed),
            "selected": dict(Counter(r["selected_workflow"][0] for r in rows if r["selected_workflow"])),
        },
        "status": {
            "accuracy": _mean(r["status_ok"] for r in rows),
            "confusion": {expected: dict(counts) for expected, counts in sorted(confusion.items())},
            "false_retrieved": [r["question_id"] for r in rows
                                if r["status"] == "retrieved" and r["expected_retrieval_status"] != "retrieved"],
            "missed": [r["question_id"] for r in rows
                       if r["expected_retrieval_status"] == "retrieved" and r["status"] != "retrieved"],
            "wrong_status": [r["question_id"] for r in rows if not r["status_ok"]],
        },
        "by_category": _groups(rows, "category", k),
        "by_language": _groups(rows, "language", k),
        "latency_ms": {"p50": _percentile([r["latency_ms"] for r in rows], .5),
                       "p95": _percentile([r["latency_ms"] for r in rows], .95)},
        "embedding_calls": sum(r["embedding_calls"] for r in rows),
    }


def _git() -> dict:
    def run(*args: str) -> str | None:
        try:
            out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    status = run("status", "--porcelain")
    return {"commit": run("rev-parse", "HEAD"), "dirty": None if status is None else bool(status)}


def run_evaluation(db: str | Path, questions_path: str | Path, *, mode: str, split: str,
                   strategies=STRATEGIES, top_k: int = 5, candidate_k: int = 20, min_cosine: float = .25,
                   rrf_k: int = 60, embedder: Embedder | None = None,
                   allow_holdout: bool = False) -> tuple[dict, list[dict]]:
    """Run every question under every strategy against the SAME active index."""
    if split == "holdout" and not allow_holdout:
        raise EvaluationError("Holdout is evaluated once, after the D15 lock; pass allow_holdout explicitly")
    strategies = list(dict.fromkeys(strategies))
    settings = dict(top_k=top_k, candidate_k=candidate_k, min_cosine=min_cosine, rrf_k=rrf_k)
    for strategy in strategies:
        RetrievalConfig(strategy=strategy, **settings)  # reject bad config before any work
    questions, questions_sha256 = load_questions(questions_path)
    wrong = [q.question_id for q in questions if (q.source_type, q.dataset_split) != (mode, split)]
    if wrong:
        raise EvaluationError(f"Questions from another corpus/split: {', '.join(wrong)}")
    corpus = read_corpus(db, mode, split)
    manifest, _ = require_index(corpus)
    check_gold(questions, corpus["workflows"])
    owned = None
    if any(strategy != "lexical" for strategy in strategies):
        expected = manifest["embedding"]
        if expected is None:
            raise EvaluationError("Index has no vectors; rebuild with --embedding gemini or evaluate lexical only")
        if embedder is None:
            if expected["provider"] != "gemini":
                raise EvaluationError("No query adapter for the indexed embedding provider")
            embedder = owned = GeminiEmbedder(expected["dimensions"])
    cache = QueryCache(embedder) if embedder else None
    rows = []
    try:
        for strategy in strategies:
            for q in questions:
                config = RetrievalConfig(strategy=strategy, intent=q.intent, **settings)
                rows.append(_evaluate_one(db, q, mode, split, config, cache, manifest["index_build_id"]))
    finally:
        if owned:
            owned.close()
    labels = Counter(q.label.status for q in questions)
    config = {**settings, "strategies": strategies}
    created = datetime.now(timezone.utc)
    report = {
        "run_id": f"EVAL_{created:%Y%m%dT%H%M%SZ}_"
                  + digest([questions_sha256, manifest["index_build_id"], config])[:8],
        "created_at": created.isoformat(timespec="seconds"), "git": _git(), "db": str(db),
        "source_type": mode, "dataset_split": split,
        "index_build_id": manifest["index_build_id"], "record_build_id": manifest["record_build_id"],
        "embedding": manifest["embedding"],
        "questions_path": str(questions_path), "questions_sha256": questions_sha256,
        "questions": len(questions),
        "gold_labels": {status: labels[status] for status in ("draft", "ai_reviewed", "reviewed")},
        "config": config, "query_embedding_calls": cache.calls if cache else 0,
        "strategies": {s: summarize([r for r in rows if r["strategy"] == s], top_k) for s in strategies},
    }
    unchecked = labels["draft"] + labels["ai_reviewed"]
    if unchecked:
        report["warning"] = (f"{unchecked} gold labels are not human-checked (draft {labels['draft']}, "
                             f"AI-reviewed {labels['ai_reviewed']}): use for debugging only, do not report as results")
    return report, rows


def write_run(report: dict, rows: list[dict], out_dir: str | Path) -> Path:
    target = Path(out_dir) / report["run_id"]
    target.mkdir(parents=True, exist_ok=True)
    (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target / "rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                       encoding="utf-8")
    return target


def format_summary(report: dict) -> str:
    k = report["config"]["top_k"]

    def fmt(value) -> str:
        return "-" if value is None else f"{value:.3f}"

    labels = report["gold_labels"]
    lines = [
        f"{report['run_id']}  {report['source_type']}/{report['dataset_split']}  index {report['index_build_id']}",
        f"questions {report['questions']} (draft {labels['draft']}, ai_reviewed {labels['ai_reviewed']}, "
        f"reviewed {labels['reviewed']}); "
        f"query embedding calls {report['query_embedding_calls']}",
    ]
    if "warning" in report:
        lines.append("WARNING: " + report["warning"])
    lines += ["", f"{'strategy':<9}{'n':>4}{f'R@{k}':>8}{f'MRR@{k}':>8}{'Hit@1':>8}{'cover':>8}"
                  f"{'wf_acc':>8}{'status':>8}{'p50ms':>8}{'p95ms':>8}"]
    for name, s in report["strategies"].items():
        r = s["retrieval"]
        lines.append(f"{name:<9}{r['questions']:>4}{fmt(r[f'recall_at_{k}']):>8}{fmt(r[f'mrr_at_{k}']):>8}"
                     f"{fmt(r['hit_at_1']):>8}{fmt(r['answer_coverage']):>8}"
                     f"{fmt(s['workflow_selection']['accuracy']):>8}{fmt(s['status']['accuracy']):>8}"
                     f"{s['latency_ms']['p50']:>8}{s['latency_ms']['p95']:>8}")
    lines.append("")
    for name, s in report["strategies"].items():
        status = s["status"]
        lines.append(f"{name}: false_retrieved={status['false_retrieved']} missed={status['missed']} "
                     f"incomplete_recall={s['retrieval']['incomplete_recall']} "
                     f"selected={s['workflow_selection']['selected']}")
    return "\n".join(lines)
