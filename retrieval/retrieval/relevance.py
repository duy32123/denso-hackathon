"""Lexical relevance prefilter; passing does not prove the source answers a question.

Details need co-occurring terms in a Step heading and ONE eligible claim. Procedure
summaries may span Steps of one workflow. Repeated context/scope text helps ranking,
but cannot itself establish relevance.
"""

from collections import Counter

from .ranking import tokens

POLICY_VERSION = "claim-coherence-2"
BACKGROUND_RATIO = .75
MIN_MATCHES = 2
# Both noun forms appear in reviewed dev queries for the sliding component.
# Search-only: keep snapshot text, ranking tokens, numbers and codes unchanged.
TERM_ALIASES = {"slider": "slide"}


def _terms(words, *, stem):
    return {TERM_ALIASES.get(t, t) if stem else t for t in words}


def claim_relevance(terms, docs, workflows, *, stem: bool, intent: str, threshold: float,
                    context=None, protected_terms=()) -> dict:
    """`docs` must already be namespace/context/review filtered Step documents.

    Only claim IDs retained in each index projection may contribute, including
    conflict diagnostics. Never pull extra pending claims from the snapshot.
    """
    query = _terms(terms, stem=stem)
    resolved = set()
    if context is not None:
        # Hard identity constraints have already been verified against metadata.
        # Do not require a claim to repeat the user's model or alarm code as well.
        for field in ("manufacturer", "machine_family", "machine_model", "subsystem", "task_type"):
            value = getattr(context, field)
            if value:
                resolved.update(_terms(tokens(value, stem=stem), stem=stem))
        if context.alarm_codes:
            resolved.update(_terms(tokens(" ".join(context.alarm_codes), stem=stem), stem=stem))
            resolved.update(_terms(tokens("alarm code loi", stem=stem), stem=stem))
    ignored_context = query & resolved
    query -= resolved
    df = Counter(t for doc in docs for t in _terms(doc["tokens"], stem=stem))
    diverse = len({doc["record"]["workflow_id"] for doc in docs}) > 1
    # Frequency within one workflow does not tell topic words from boilerplate.
    # Codes/numbers retain their exact identity even when repeated in metadata.
    protected = _terms(protected_terms, stem=stem)
    background = {t for t in query if diverse and t.isalpha() and t not in protected
                  and df[t] > BACKGROUND_RATIO * len(docs)}
    # Keep unknown terms in the denominator. If everything is background, still
    # demand matches in actual title/claim text.
    focused = query - background or query
    ignored = query - focused
    claim_maps = {wid: {c.claim_id: c for c in wf.claims} for wid, wf in workflows.items()}
    units, procedures = [], {}
    for doc in docs:
        record = doc["record"]
        wid = record["workflow_id"]
        heading = _terms(tokens(record["title"], stem=stem), stem=stem)
        for cid in record["claim_ids"]:
            claim_words = _terms(tokens(claim_maps[wid][cid].text, stem=stem), stem=stem)
            words = heading | claim_words
            ref = {"workflow_id": wid, "revision": record["revision"], "step_id": record["step_id"],
                   "claim_id": cid, "purpose": doc["purpose"]}
            if intent == "procedure":
                # Warning-only conflicts cannot lend support to an assertable procedure.
                group = procedures.setdefault((wid, doc["purpose"]), {"words": set(), "refs": []})
                group["words"].update(words)
                group["refs"].append(ref)
            else:
                units.append({"words": words, "claim_words": claim_words, "refs": [ref]})
    if intent == "procedure":
        units = list(procedures.values())
    # Ties follow the index's deterministic document/claim order.
    best = max(units, key=lambda u: len(focused & u["words"]), default={"words": set(), "refs": []})
    matched = focused & best["words"]
    coverage = len(matched) / len(focused) if focused else 0.0
    required = min(MIN_MATCHES, len(focused))
    passes = bool(focused) and len(matched) >= required and coverage >= threshold
    # A request explicitly naming an alarm can look up its definition even when
    # boilerplate leaves fewer than two content matches. Metadata alone cannot
    # open this path: the exact code and 'alarm' must occur in an eligible claim.
    # The later answer guard still decides whether that source answers the query.
    code_units = []
    if intent == "detail" and context is not None and context.alarm_codes:
        codes = _terms(tokens(" ".join(context.alarm_codes), stem=stem), stem=stem)
        requested_codes = codes & _terms(terms, stem=stem)
        lookup_terms = _terms(tokens("occur cause trigger mean meaning definition", stem=stem), stem=stem)
        # This exception is for code definition/cause lookup, not arbitrary tasks
        # merely accompanied by an alarm code.
        if requested_codes and focused & lookup_terms:
            code_units = [u for u in units if requested_codes <= u.get("claim_words", set())
                          and "alarm" in u.get("claim_words", set())]
    if code_units:
        best = max(code_units, key=lambda u: len(focused & u["words"]))
        matched = focused & best["words"]
        coverage = len(matched) / len(focused) if focused else 0.0
        passes = True
    return {
        "policy": POLICY_VERSION, "unit": "workflow" if intent == "procedure" else "claim",
        "background_ratio": BACKGROUND_RATIO, "ignored_terms": sorted(ignored),
        "context_terms": sorted(ignored_context),
        "protected_component_terms": sorted(protected),
        "query_terms": sorted(focused), "matched_terms": sorted(matched),
        "unseen_terms": sorted(focused - best["words"]), "min_matches": required,
        "term_coverage": round(coverage, 4), "min_term_coverage": threshold,
        "support_refs": best["refs"], "gate": "passed" if passes else "rejected",
        "exact_alarm_lookup": bool(code_units),
    }
