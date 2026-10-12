"""Search-only component identity constraints from explicit compound names.

Names are matched in eligible Step headings and claim text, never repeated workflow
metadata. A lubrication fact about a way-cover rail cannot answer a pocket-slider
question. This lexicon is explicit, versioned, and is not inferred from eval gold.
"""
import re

from .ranking import fold, tokens

VERSION = "component-identity-1"
COMPONENT_TERMS = {"pocket_slider": "pocket slider", "double_arm_slider": "double arm slider",
                   "way_cover": "way cover"}
PATTERNS = {
    "pocket_slider": (
        r"\bpocket(?:\s+\w+){0,2}\s+slid(?:e|er)\b",
        r"\bslid(?:e|er)(?:\s+\w+){0,3}\s+pocket\b",
        r"\bcon truot(?: cua)?(?:\s+cua)? hoc dao\b",
    ),
    "double_arm_slider": (
        r"\bdouble[- ]arm(?:\s+\w+){0,4}\s+slid(?:e|er)\b",
        r"\bslid(?:e|er)(?:\s+\w+){0,4}\s+double[- ]arm\b",
        r"\bcon truot(?:\s+\w+){0,3}\s+tay doi\b",
    ),
    "way_cover": (r"\bway[- ]covers?\b", r"\btam che(?:\s+\w+){0,2}\s+(?:truc|ray)\b"),
}


def requested_components(*texts):
    return sorted({name for name, patterns in PATTERNS.items()
                   if any(re.search(pattern, fold(text)) for text in texts for pattern in patterns)})


def matching_steps(docs, workflows, names, *, action_terms=()):
    """Every requested component must occur in one eligible heading/claim unit.

    Only run on English documents. Do not pool words across unrelated claims or
    count claims removed by review/context/namespace filters.
    """
    maps = {wid: {c.claim_id: c for c in wf.claims} for wid, wf in workflows.items()}
    kept = []
    for doc in docs:
        record = doc["record"]
        units = [record["title"] + " " + maps[record["workflow_id"]][cid].text
                 for cid in record["claim_ids"]]
        if all(any(name in requested_components(unit) and
                   (not action_terms or set(tokens(unit, stem=True)) & set(action_terms))
                   for unit in units) for name in names):
            kept.append(doc)
    return kept
