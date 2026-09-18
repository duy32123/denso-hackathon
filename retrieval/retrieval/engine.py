"""WP2 retrieval API: candidates/evidence for D2-B, not a generated answer."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from knowflow_contracts.eligibility import claim_blockers
from knowflow_contracts.enums import QueryMode
from knowflow_contracts.models import QueryRequest
from knowflow_contracts.retrieval_policy import ClaimHit, dedup_claim_hits
from retrieval.indexing.embeddings import Embedder, GeminiEmbedder, unit_vector
from retrieval.indexing.search_index import RetrievalError, read_corpus, require_index
from .context import context_gate, resolve_context
from .query import GeminiTranslator, Translator, content_terms, looks_vietnamese, term_coverage
from .ranking import fold, rank

# WP2 step 5. Which relation makes a neighbouring Step part of a correct answer, and
# which end of that relation the matched Step sits on:
#   requires   -- `to` needs `from`, so a matched `to` pulls in its prerequisite.
#   branch_if  -- reaching `to` is gated by the condition on the edge from `from`.
#   corrects   -- `to` corrects `from`, so a matched `from` must not be served alone.
# `observed_next` and `repeated_step` are deliberately absent: order in the source is
# not a dependency (Schema 1.0.0, section 6: "khong suy requires tu thu tu thoi gian"),
# and a repetition adds no condition the answer would otherwise miss.
DEPENDENCY_RELATIONS = {"requires": "to", "branch_if": "to", "corrects": "from"}


@dataclass(frozen=True)
class RetrievalConfig:
    strategy: str = "hybrid"
    top_k: int = 5
    candidate_k: int = 20
    rrf_k: int = 60
    min_cosine: float = .25
    intent: str = "auto"
    # Chosen on real/dev (labels not human-checked, 2026-09-15): any value in 0.10-0.15 rejected
    # 0/31 answerable and 13/19 out-of-scope questions; the low end, since a false rejection
    # cannot be recovered downstream. Recalibrate when the corpus grows.
    min_term_coverage: float = .10
    query_translation: str = "auto"
    # Neighbour expansion is additive: it never changes `steps`, `claims` or `status`.
    # Depth 1 is the conservative starting point, not a measured optimum.
    neighbor_depth: int = 1
    max_related_steps: int = 5
    # "best_step" scores a workflow by its best assertable Step across the filtered corpus;
    # "record" ranks the workflow-level records. best_step was >= record on every lexical
    # metric on real/dev with both the 2- and 4-workflow corpora (2026-09-18, labels not
    # human-checked); hybrid is unmeasured. Not a tuned optimum.
    workflow_routing: str = "best_step"

    def __post_init__(self):
        if self.strategy not in ("lexical", "vector", "hybrid"):
            raise ValueError("strategy must be lexical, vector or hybrid")
        if not 1 <= self.top_k <= self.candidate_k <= 100 or self.rrf_k < 1:
            raise ValueError("Require 1 <= top_k <= candidate_k <= 100 and rrf_k >= 1")
        if not 0 <= self.min_cosine <= 1 or self.intent not in ("auto", "detail", "procedure"):
            raise ValueError("Invalid min_cosine or intent")
        if not 0 <= self.min_term_coverage <= 1 or self.query_translation not in ("auto", "never"):
            raise ValueError("Invalid min_term_coverage or query_translation")
        if not 0 <= self.neighbor_depth <= 3 or not 0 <= self.max_related_steps <= 20:
            raise ValueError("Require 0 <= neighbor_depth <= 3 and 0 <= max_related_steps <= 20")
        if self.workflow_routing not in ("record", "best_step"):
            raise ValueError("workflow_routing must be record or best_step")


def retrieve(db: str | Path, request: QueryRequest, *, config: RetrievalConfig | None = None,
             embedder: Embedder | None = None, translator: Translator | None = None) -> dict:
    start = time.perf_counter()
    config = config or RetrievalConfig()
    if not request.question.strip():
        raise ValueError("Question must not be blank")
    corpus = read_corpus(db, str(request.mode), str(request.dataset_split))
    manifest, docs = require_index(corpus)
    context, contradictions, detected = resolve_context(
        request.question, request.context, list(corpus["workflows"].values()),
    )
    intent = config.intent
    if intent == "auto":
        intent = "procedure" if any(p in fold(request.question) for p in
                                     ("quy trinh", "cac buoc", "all steps", "procedure", "step by step")) else "detail"
    result = {
        "status": "insufficient_evidence", "index_build_id": manifest["index_build_id"],
        "record_build_id": manifest["record_build_id"], "source_type": str(request.mode),
        "dataset_split": str(request.dataset_split), "context": context.model_dump(mode="json"),
        "missing_context": [], "selected_workflow": None, "workflow_candidates": [],
        "steps": [], "claims": [], "conflicts": [], "blocked_claims": [], "questions": [],
        "relations": [], "related_steps": [], "related_claims": [],
        "evidence_openability_checked": False,
        "trace": {"config": asdict(config), "intent": intent, "detected_context": detected,
                  "filters": [], "workflow_ranking": [], "step_ranking": [],
                  "embedding_calls": 0, "cache": "disabled"},
    }

    def finish(status=None):
        if status:
            result["status"] = status
        result["trace"]["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return result

    if contradictions:
        result["missing_context"] = contradictions
        result["trace"]["context_error"] = "question and supplied context disagree, or multiple identities were named"
        return finish("needs_clarification")
    allowed, unknown = set(), set()
    for wf in corpus["workflows"].values():
        mismatches, missing = context_gate(wf, context)
        result["trace"]["filters"].append({
            "workflow_id": wf.workflow_id, "revision": wf.revision,
            "mismatches": mismatches, "unknown_context": missing,
        })
        if not mismatches and not missing:
            allowed.add(wf.workflow_id)
        elif not mismatches:
            unknown.update(missing)
    if not allowed:
        result["missing_context"] = sorted(unknown)
        return finish("needs_clarification" if unknown else "insufficient_evidence")
    # All ranking statistics, cosine scoring, fusion and conflict lookups share this set.
    docs = [d for d in docs if d["record"]["workflow_id"] in allowed
            and d["record"]["source_type"] == request.mode
            and d["record"]["dataset_split"] == request.dataset_split
            and d["record"]["revision"] == corpus["workflows"][d["record"]["workflow_id"]].revision
            and d["record"]["lifecycle"] == "active"]
    result["trace"]["eligible_documents"] = len(docs)
    if not docs:
        return finish()
    query_text = request.question
    # Soft symptoms/components are search hints; they never relax hard identity gates.
    hints = context.symptoms + context.components
    if hints:
        query_text += "\n" + "; ".join(hints)
    # Lexical text in the corpus language. Translation is for SEARCH only (contract D-03);
    # dense retrieval keeps the original question. Lexical-only never calls an API itself.
    lexical_text, translation = query_text, None
    english_corpus = {d["record"]["language"] for d in docs} == {"en"}
    vietnamese = english_corpus and looks_vietnamese(query_text)
    if vietnamese and config.query_translation == "auto":
        owned_translator = translator is None and config.strategy != "lexical"
        if owned_translator:
            translator = GeminiTranslator()
        if translator is not None:
            try:
                lexical_text = translator.to_english(query_text)
            finally:
                if owned_translator:
                    translator.close()
            translation = {"text": lexical_text, **translator.config}
    result["trace"]["query_translation"] = translation
    # Coverage counts conflict diagnostics too: a question about a contested fact must reach
    # the conflict lookup instead of being rejected as out of scope.
    step_docs = [d for d in docs if d["record"]["record_type"] == "step"]
    coverage, unseen = term_coverage(content_terms(lexical_text, stem=english_corpus), step_docs)
    gate = ("skipped" if vietnamese and translation is None
            else "rejected" if coverage < config.min_term_coverage else "passed")
    result["trace"]["relevance"] = {"term_coverage": round(coverage, 4), "unseen_terms": unseen,
                                    "min_term_coverage": config.min_term_coverage, "gate": gate}
    if gate == "rejected":
        return finish("insufficient_evidence")  # before any embedding call
    query_vector = None
    if config.strategy != "lexical":
        expected = manifest["embedding"]
        if expected is None:
            raise RetrievalError("Index has no vectors; rebuild with --embedding gemini or use --strategy lexical")
        owned = embedder is None
        if owned:
            if expected["provider"] != "gemini":
                raise RetrievalError("No configured query adapter for the indexed embedding provider")
            embedder = GeminiEmbedder(expected["dimensions"])
        try:
            if embedder.config != expected:
                raise RetrievalError("Query/index embedding configuration mismatch; rebuild or use matching adapter")
            before = getattr(embedder, "calls", 0)
            query_vector = unit_vector(embedder.query(query_text), expected["dimensions"])
            result["trace"]["embedding_calls"] = getattr(embedder, "calls", before + 1) - before
        finally:
            if owned:
                embedder.close()

    def ranked(items):
        return rank(lexical_text, items, query_vector, strategy=config.strategy, stem=english_corpus,
                    candidate_k=config.candidate_k, min_cosine=config.min_cosine, rrf_k=config.rrf_k)

    def rank_trace(items):
        return [{"document_id": h["doc"]["id"], "purpose": h["doc"]["purpose"],
                 "score": h["score"], "lexical_score": h["lexical_score"], "vector_score": h["vector_score"]}
                for h in items]

    if config.workflow_routing == "best_step":
        # Score each workflow by its best-matching assertable Step across the filtered corpus.
        # Ranking the workflow records directly gives BM25 only one document per workflow,
        # so IDF is decided by a handful of documents and the longest record wins by
        # containing incidental words ("step", "lubricate"). Steps give dozens of documents.
        workflow_docs = {d["record"]["workflow_id"]: d for d in docs if d["record"]["record_type"] == "workflow"}
        best: dict[str, dict] = {}
        routing_steps: dict[str, str] = {}
        for hit in ranked([d for d in docs if d["record"]["record_type"] == "step" and d["purpose"] == "answer"]):
            workflow_id = hit["doc"]["record"]["workflow_id"]
            if workflow_id not in best and workflow_id in workflow_docs:
                best[workflow_id] = {**hit, "doc": workflow_docs[workflow_id]}
                routing_steps[workflow_id] = hit["doc"]["record"]["step_id"]
        workflows = sorted(best.values(), key=lambda h: -h["score"])
        result["trace"]["routing_steps"] = routing_steps
    else:
        workflows = ranked([d for d in docs if d["record"]["record_type"] == "workflow"])
    result["trace"]["workflow_ranking"] = rank_trace(workflows)
    seen = set()
    for hit in workflows:
        record = hit["doc"]["record"]
        if record["workflow_id"] not in seen:
            seen.add(record["workflow_id"])
            result["workflow_candidates"].append({
                "workflow_id": record["workflow_id"], "revision": record["revision"],
                "title": record["title"], "score": hit["score"],
            })
    if not result["workflow_candidates"]:
        return finish()
    selected = result["workflow_candidates"][0]
    result["selected_workflow"] = selected
    if len(result["workflow_candidates"]) > 1:
        # Same scale as the strategy's score; a near-zero margin means the pick is arbitrary.
        result["trace"]["workflow_margin"] = selected["score"] - result["workflow_candidates"][1]["score"]
    wf = corpus["workflows"][selected["workflow_id"]]
    within_workflow = [d for d in docs if d["record"]["record_type"] == "step"
                       and d["record"]["workflow_id"] == wf.workflow_id]
    step_hits = ranked([d for d in within_workflow if d["purpose"] == "answer"])
    result["trace"]["step_ranking"] = rank_trace(step_hits)
    if intent == "procedure":
        scores = {h["doc"]["id"]: h for h in step_hits}
        # Entire selected workflow only, with gaps/relation semantics still explicit.
        step_hits = [scores.get(d["id"], {"doc": d, "score": selected["score"],
                                         "lexical_score": None, "vector_score": None})
                     for d in sorted(within_workflow, key=lambda d: d["record"]["display_order"])
                     if d["purpose"] == "answer"]
    else:
        step_hits = step_hits[:config.top_k]
    claim_hits = []
    for hit in step_hits:
        record = hit["doc"]["record"]
        step = next(s for s in wf.steps if s.step_id == record["step_id"])
        result["steps"].append({
            "workflow_id": wf.workflow_id, "revision": wf.revision,
            "step_id": step.step_id, "display_order": step.display_order, "title": step.title,
            "fields": step.fields.model_dump(mode="json"), "claim_ids": record["claim_ids"],
            "score": hit["score"], "lexical_score": hit["lexical_score"], "vector_score": hit["vector_score"],
        })
        claim_hits.extend(ClaimHit(wf.workflow_id, wf.revision, cid, step.step_id, hit["score"])
                          for cid in record["claim_ids"])

    def package(workflow, cid, matched_steps, score, purpose):
        claim = next(c for c in workflow.claims if c.claim_id == cid)
        evidence = {e.evidence_id: e for e in workflow.evidence}
        items = []
        for link in claim.evidence_links:
            ev = evidence[link.evidence_id]
            src = corpus["sources"][ev.source_id]
            items.append({"evidence": ev.model_dump(mode="json"), "link": link.model_dump(mode="json"),
                          "source": src.model_dump(mode="json"), "access_status": "not_checked"})
        return {"claim_ref": {"workflow_id": workflow.workflow_id, "revision": workflow.revision,
                              "entity_type": "claim", "entity_id": cid},
                "claim": claim.model_dump(mode="json"), "matched_step_ids": matched_steps,
                "score": score, "purpose": purpose, "evidence": items}

    for hit in dedup_claim_hits(claim_hits):
        claim = next(c for c in wf.claims if c.claim_id == hit.claim_id)
        reasons = claim_blockers(claim, wf, mode=QueryMode(request.mode), is_latest_indexed_revision=True)
        if not reasons:
            result["claims"].append(package(wf, hit.claim_id, hit.matched_step_ids, hit.score, "answer_candidate"))
    # WP2 step 5: the Steps a correct answer depends on -- a prerequisite, the branch point
    # whose condition gates a matched Step, a later Step that corrects one. They travel in
    # their own keys: `steps`, `claims` and `status` are untouched, so a neighbour can never
    # turn an unanswerable question into an answered one, and each neighbour claim is
    # re-checked against its OWN review flags instead of inheriting the matched Step's.
    eligible_steps = {d["record"]["step_id"]: d["record"] for d in within_workflow if d["purpose"] == "answer"}
    matched_ids = {s["step_id"] for s in result["steps"]}
    related: dict[str, dict] = {}
    unavailable: set[str] = set()
    frontier, reached = set(matched_ids), set(matched_ids)
    for depth in range(1, config.neighbor_depth + 1):
        found: dict[str, list] = {}
        for rel in wf.relations:
            anchor_end = DEPENDENCY_RELATIONS.get(str(rel.relation_type))
            if anchor_end is None:
                continue
            anchor, other = ((rel.to_step_id, rel.from_step_id) if anchor_end == "to"
                             else (rel.from_step_id, rel.to_step_id))
            if anchor not in frontier or other in reached:
                continue
            if other not in eligible_steps:
                # Present in the workflow but not in the filtered corpus. Say so; a
                # dependency that silently vanishes is exactly what must not happen.
                unavailable.add(other)
                continue
            found.setdefault(other, []).append(rel)
        if not found:
            break
        for step_id, relations in found.items():
            related[step_id] = {"depth": depth, "relations": relations}
        reached |= set(found)
        frontier = set(found)
    order = {s.step_id: s.display_order for s in wf.steps}
    # Nearest dependency first, then source order; deterministic under the cap.
    ranked_related = sorted(related, key=lambda sid: (related[sid]["depth"], order.get(sid, 0), sid))
    chosen = set(ranked_related[:config.max_related_steps])
    # A claim already offered as an answer candidate is not repeated here: one claim, one
    # purpose, so WP3 cannot read the same evidence as both the answer and its context.
    packaged_related = {c["claim_ref"]["entity_id"] for c in result["claims"]}
    for step_id in sorted(chosen, key=lambda sid: order.get(sid, 0)):
        record, info = eligible_steps[step_id], related[step_id]
        step = next(s for s in wf.steps if s.step_id == step_id)
        result["related_steps"].append({
            "workflow_id": wf.workflow_id, "revision": wf.revision, "step_id": step_id,
            "display_order": step.display_order, "title": step.title,
            "fields": step.fields.model_dump(mode="json"), "claim_ids": record["claim_ids"],
            "depth": info["depth"],
            "via": [{"relation_id": r.relation_id, "relation_type": str(r.relation_type),
                     "from_step_id": r.from_step_id, "to_step_id": r.to_step_id,
                     "condition_claim_ids": r.condition_claim_ids} for r in info["relations"]],
        })
        # The condition of a branch_if lives on the edge, not in the Step: without it the
        # neighbour reads as an unconditional instruction.
        condition_ids = [cid for r in info["relations"] for cid in r.condition_claim_ids]
        for cid in list(record["claim_ids"]) + condition_ids:
            if cid in packaged_related:
                continue
            claim = next((c for c in wf.claims if c.claim_id == cid), None)
            if claim is None or claim_blockers(claim, wf, mode=QueryMode(request.mode),
                                               is_latest_indexed_revision=True):
                continue  # already listed in blocked_claims; never asserted from here
            packaged_related.add(cid)
            # No score: these were not ranked against the question, they were reached.
            result["related_claims"].append(package(wf, cid, [step_id], None, "context_only"))
    result["trace"]["neighbors"] = {
        "depth": config.neighbor_depth, "relations": sorted(DEPENDENCY_RELATIONS),
        "unavailable_step_ids": sorted(unavailable),
        "truncated_step_ids": sorted(set(ranked_related) - chosen),
    }
    # Separate lookup across the SAME filtered corpus, so conflicts cannot disappear
    # merely because they were excluded from assertable search text.
    # Conflict diagnostics compete with assertable steps of the same filtered corpus and are
    # reported only inside the top-k; ranked alone, any conflict would flag every query.
    competing = ranked([d for d in docs if d["record"]["record_type"] == "step"])[:config.top_k]
    conflict_hits = [hit for hit in competing if hit["doc"]["purpose"] == "conflict"]
    result["trace"]["conflict_ranking"] = rank_trace(conflict_hits)
    conflict_keys = set()
    for hit in conflict_hits:
        record = hit["doc"]["record"]
        other = corpus["workflows"][record["workflow_id"]]
        claims = {c.claim_id: c for c in other.claims}
        ids = set(record["claim_ids"])
        ids.update(cid for selected_id in list(ids) for cid in claims[selected_id].conflicts_with)
        for cid in sorted(ids):
            key = (other.workflow_id, other.revision, cid)
            if key not in conflict_keys:
                conflict_keys.add(key)
                result["conflicts"].append(package(other, cid, [record["step_id"]], hit["score"], "warning_only"))
    for claim in wf.claims:
        blockers = claim_blockers(claim, wf, mode=QueryMode(request.mode), is_latest_indexed_revision=True)
        if blockers:
            result["blocked_claims"].append({"workflow_id": wf.workflow_id, "revision": wf.revision,
                                             "claim_id": claim.claim_id, "reasons": blockers})
    step_ids = {s["step_id"] for s in result["steps"]}
    result["questions"] = [q.model_dump(mode="json") for q in wf.questions if q.step_id in step_ids]
    result["relations"] = [r.model_dump(mode="json") for r in wf.relations
                           if r.from_step_id in step_ids or r.to_step_id in step_ids]
    if intent == "procedure":
        result["trace"]["omitted_step_ids"] = [s.step_id for s in wf.steps if s.step_id not in step_ids]
    return finish("conflicting_sources" if result["conflicts"] else
                  "retrieved" if result["claims"] else "insufficient_evidence")
