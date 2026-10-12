"""Explicit component identity, including wrong-component counterexamples."""
from retrieval.retrieval.components import requested_components, matching_steps
from test_relevance import corpus


def test_component_names_preserve_compounds_and_vietnamese_identity():
    assert requested_components("Nên bôi trơn con trượt hốc dao bằng gì?") == ["pocket_slider"]
    assert requested_components("boi tron con truot hoc dao bang gi") == ["pocket_slider"]
    assert requested_components("grease the double-arm slider") == ["double_arm_slider"]
    assert requested_components("grease the slider") == []  # unspecified: do not guess its component


def test_component_matches_cannot_use_metadata_or_excluded_claims():
    docs, workflows = corpus(("W1", "Lubrication", ["Grease the finger.", "Grease the pocket slider."]),
                             ("W2", "Way covers", ["Grease the guide rail."]))
    docs[0]["record"]["claim_ids"] = ["C0_0"]
    assert matching_steps(docs, workflows, ["pocket_slider"]) == []
    docs[0]["record"]["claim_ids"].append("C0_1")
    assert matching_steps(docs, workflows, ["pocket_slider"]) == [docs[0]]
