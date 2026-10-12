"""Coherent claim matches, identity/background separation, and procedure boundaries."""

from types import SimpleNamespace

from knowflow_contracts.models import QueryContext

from retrieval.retrieval.query import content_terms
from retrieval.retrieval.ranking import tokens
from retrieval.retrieval.relevance import claim_relevance


def corpus(*steps):
    """Each input is (workflow, title, claim texts). No model or network is involved."""
    docs, workflows = [], {}
    for n, (wid, title, texts) in enumerate(steps):
        claims = [SimpleNamespace(claim_id=f"C{n}_{i}", text=text) for i, text in enumerate(texts)]
        workflows.setdefault(wid, SimpleNamespace(claims=[])).claims.extend(claims)
        docs.append({"purpose": "answer", "tokens": tokens(title + " " + " ".join(texts), stem=True),
                     "record": {"workflow_id": wid, "revision": 1, "step_id": f"S{n}", "title": title,
                                "claim_ids": [c.claim_id for c in claims]}})
    return docs, workflows


def assess(question, data, *, intent="detail", context=None):
    return claim_relevance(content_terms(question, stem=True), *data, stem=True,
                           intent=intent, threshold=.2, context=context)


def test_detail_cannot_collect_terms_from_unrelated_steps_or_claims():
    separated_steps = corpus(("W1", "Inspection", ["Measure the gap"]),
                             ("W1", "Inspection", ["Clean the spindle"]))
    assert assess("Measure spindle runout", separated_steps)["gate"] == "rejected"
    separated_claims = corpus(("W1", "Inspection", ["Lubricate periodically", "Clean the spindle"]),
                              ("W1", "Other", ["Remove cover"]))
    assert assess("Clean the conveyor periodically", separated_claims)["gate"] == "rejected"


def test_context_and_scope_text_are_not_substitutes_for_claim_content():
    data = corpus(("W1", "Cover", ["Remove the bolt"]))
    data[0][0]["tokens"] += tokens("context: spindle runout; scope: spindle runout", stem=True)
    assert assess("spindle runout", data)["gate"] == "rejected"


def test_claims_excluded_from_index_projection_cannot_rescue_a_question():
    data = corpus(("W1", "Inspection", ["Remove cover", "Measure spindle runout"]))
    data[0][0]["record"]["claim_ids"] = ["C0_0"]  # second claim is in the snapshot, not the eligible index
    result = assess("Measure spindle runout", data)
    assert result["gate"] == "rejected"
    assert all(ref["claim_id"] != "C0_1" for ref in result["support_refs"])


def test_procedure_can_span_steps_of_one_workflow_but_not_different_workflows():
    data = corpus(("W1", "Inspection", ["Measure the gap"]), ("W1", "Completion", ["Clean the spindle"]))
    assert assess("Measure spindle runout", data)["gate"] == "rejected"
    assert assess("Measure spindle runout", data, intent="procedure")["gate"] == "passed"
    other = corpus(("W1", "Inspection", ["Measure the gap"]), ("W2", "Completion", ["Clean the spindle"]))
    assert assess("Measure spindle runout", other, intent="procedure")["gate"] == "rejected"


def test_conflicts_are_searchable_but_not_pooled_with_answer_claims():
    data = corpus(("W1", "Inspection", ["Measure the gap"]), ("W1", "Completion", ["Clean the spindle"]))
    data[0][1]["purpose"] = "conflict"
    assert assess("Measure spindle runout", data, intent="procedure")["gate"] == "rejected"
    conflict = corpus(("W1", "Inspection", ["Measure spindle runout"]))
    conflict[0][0]["purpose"] = "conflict"
    result = assess("Measure spindle runout", conflict)
    assert result["gate"] == "passed" and result["support_refs"][0]["purpose"] == "conflict"


def test_common_labels_cannot_hide_an_unknown_topic():
    data = corpus(*[(f"W{i}", "Haas tools", ["Inspect the machine"]) for i in range(4)])
    result = assess("Haas machine coolant", data)
    assert result["query_terms"] == ["coolant"]
    assert result["gate"] == "rejected"


def test_short_lookup_still_needs_an_actual_claim_match():
    data = corpus(("W1", "Inspection", ["Measure the gap"]))
    assert assess("gap", data)["gate"] == "passed"
    assert assess("coolant", data)["gate"] == "rejected"
    assert assess("What should I do?", data)["gate"] == "rejected"


def test_one_workflow_frequency_does_not_erase_its_topic():
    data = corpus(("W1", "Remove cover", ["Remove cover after locking"]),
                  ("W1", "Cover", ["Clean cover after removal"]))
    for doc in data[0]:
        doc["tokens"] += tokens("remove cover", stem=True)
    assert assess("Remove cover safely", data)["gate"] == "passed"


def test_hard_matched_alarm_is_not_required_to_be_repeated_in_a_claim():
    data = corpus(("W1", "Inspection", ["Remove cover"]))
    result = assess("Remove cover alarm 2066", data, context=QueryContext(alarm_codes=["2066"]))
    assert result["gate"] == "passed"
    assert "2066" in result["context_terms"]


def test_slider_alias_keeps_codes_and_snapshot_text_intact():
    data = corpus(("W1", "Lubrication", ["Lubricate the slider at alarm 2066"]))
    assert assess("Lubricate slide", data)["gate"] == "passed"
    assert assess("20.66", data)["gate"] == "rejected"
    assert data[1]["W1"].claims[0].text == "Lubricate the slider at alarm 2066"


def test_alarm_cause_lookup_needs_exact_code_in_eligible_claim():
    data = corpus(("W1", "Recovery", ["Alarm 626 occurs when the pocket fails to reach position."]))
    question = "According to the service video, when does alarm 626 occur?"
    result = assess(question, data, context=QueryContext(alarm_codes=["626"]))
    assert result["gate"] == "passed" and result["exact_alarm_lookup"]
    assert result["support_refs"][0]["claim_id"] == "C0_0"
    unrelated = corpus(("W1", "Alarm 626", ["Remove the cover."]))
    assert assess(question, unrelated, context=QueryContext(alarm_codes=["626"]))["gate"] == "rejected"
    assert assess(question, corpus(("W1", "Recovery", ["Alarm 627 occurs."])),
                  context=QueryContext(alarm_codes=["626"]))["gate"] == "rejected"
    assert assess("How to replace a conveyor for alarm 626?", data,
                  context=QueryContext(alarm_codes=["626"]))["gate"] == "rejected"


def test_alarm_exception_does_not_read_excluded_claims():
    data = corpus(("W1", "Recovery", ["Remove cover", "Alarm 626 occurs when the pocket fails."]))
    data[0][0]["record"]["claim_ids"] = ["C0_0"]
    result = assess("When does alarm 626 occur?", data, context=QueryContext(alarm_codes=["626"]))
    assert not result["exact_alarm_lookup"] and result["gate"] == "rejected"
