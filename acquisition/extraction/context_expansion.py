"""Context Window Expansion Module for KnowFlow AI (Baseline B2 / WP4).

Expands evidence context around existing action/observation anchors by inspecting
adjacent transcript cues or guide lines from the evidence candidate pool.
Enforces the WP4 budget rule: maximum 2 expansion rounds per unit/step.
If evidence remains insufficient after 2 rounds, fields are honestly kept as
`missing` or `ambiguous` with an audit trail.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from acquisition.extraction.evidence_pool import Candidate, candidate_id

logger = logging.getLogger("context_expansion")

# Heuristic indicator keywords for technical fields
RATIONALE_INDICATORS = (
    "because", "so that", "in order to", "to prevent", "reason", "why",
    "will cause", "might cause", "otherwise", "avoid", "protect"
)
CONDITION_INDICATORS = (
    "if", "when", "once", "before", "after", "prior to", "until",
    "while", "as soon as", "unless", "provided that", "verify that"
)
ACCEPTANCE_INDICATORS = (
    "make sure", "ensure", "check that", "verify", "inspect", "measure",
    "should be", "must be", "gap", "clearance", "aligned", "flush"
)


@dataclass
class ExpansionRoundLog:
    round_number: int
    field_role: str
    previous_candidate_ids: list[str]
    expanded_candidate_ids: list[str]
    matched_keyword: str | None
    success: bool
    note: str


@dataclass
class ExpansionResult:
    step_id: str
    rounds_executed: int
    fields_augmented: dict[str, list[str]] = field(default_factory=dict)
    unresolved_fields: list[str] = field(default_factory=list)
    audit_log: list[ExpansionRoundLog] = field(default_factory=list)


def parse_candidate_ordinal(candidate_id: str) -> tuple[str, str, int] | None:
    """Parses 'SRC_HAAS_0005:U0012' into ('SRC_HAAS_0005', 'U', 12)."""
    match = re.match(r"^(?P<src>[^:]+):(?P<kind>[A-Z])(?P<ord>\d+)$", candidate_id)
    if not match:
        return None
    return match.group("src"), match.group("kind"), int(match.group("ord"))


def get_adjacent_candidate_ids(
    pool: dict[str, Candidate],
    source_id: str,
    kind: str,
    base_ordinals: set[int],
    window: int = 2,
) -> list[str]:
    """Finds candidate IDs within ±window of the base ordinals in the pool."""
    if not base_ordinals:
        return []

    min_ord = max(1, min(base_ordinals) - window)
    max_ord = max(base_ordinals) + window

    adjacent_ids = []
    for ord_val in range(min_ord, max_ord + 1):
        if ord_val in base_ordinals:
            continue
        cid = candidate_id(source_id, kind, ord_val)
        if cid in pool:
            adjacent_ids.append(cid)
    return adjacent_ids


def scan_candidates_for_role(
    candidates: list[Candidate],
    role: str,
) -> list[tuple[Candidate, str]]:
    """Scans candidates for indicator keywords matching the target role."""
    indicators: tuple[str, ...]
    if role == "rationale":
        indicators = RATIONALE_INDICATORS
    elif role == "condition":
        indicators = CONDITION_INDICATORS
    elif role == "acceptance_criteria":
        indicators = ACCEPTANCE_INDICATORS
    else:
        indicators = ()

    matches = []
    for c in candidates:
        text_lower = c.text.lower()
        for kw in indicators:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                matches.append((c, kw))
                break
    return matches


def expand_step_context(
    step_dict: dict[str, Any],
    pool: dict[str, Candidate],
    max_rounds: int = 2,
    window_size: int = 2,
) -> ExpansionResult:
    """Performs context expansion on a single step draft dictionary.

    Inspects missing or ambiguous fields (`rationale`, `condition`, `acceptance_criteria`).
    Queries adjacent cues (up to max_rounds iterations).
    """
    step_id = step_dict.get("step_id", "UNKNOWN_STEP")
    fields = step_dict.get("fields", {})
    result = ExpansionResult(step_id=step_id, rounds_executed=0)

    # 1. Identify existing candidate ordinals used in this step
    used_cids: set[str] = set()
    source_id: str | None = None
    kind: str | None = None
    ordinals: set[int] = set()

    for role, fval in fields.items():
        claims_list = []
        if isinstance(fval, list):
            claims_list = fval
        elif isinstance(fval, dict):
            claims_list = fval.get("claims", [])
        for cl in claims_list:
            ev_list = cl.get("evidence", [])
            for item in ev_list:
                if isinstance(item, list):
                    for cid in item:
                        if isinstance(cid, str):
                            used_cids.add(cid)
                            parsed = parse_candidate_ordinal(cid)
                            if parsed:
                                source_id, kind, ord_val = parsed
                                ordinals.add(ord_val)
                elif isinstance(item, str):
                    used_cids.add(item)
                    parsed = parse_candidate_ordinal(item)
                    if parsed:
                        source_id, kind, ord_val = parsed
                        ordinals.add(ord_val)

    if not source_id or not kind or not ordinals:
        logger.debug(f"{step_id}: Không tìm thấy anchor candidate ID để mở rộng ngữ cảnh.")
        return result

    # 2. Check which target roles need expansion
    target_roles = ["rationale", "condition", "acceptance_criteria"]
    roles_to_expand = []
    for r in target_roles:
        fval = fields.get(r)
        is_missing = False
        if fval == "missing" or fval is None or isinstance(fval, dict) and fval.get("state") in ("missing", "ambiguous") or isinstance(fval, list) and len(fval) == 0:
            is_missing = True

        if is_missing:
            roles_to_expand.append(r)

    if not roles_to_expand:
        logger.debug(f"{step_id}: Tất cả các trường mục tiêu đã có căn cứ.")
        return result

    # 3. Iterative expansion rounds (strictly <= max_rounds)
    current_ordinals = set(ordinals)
    for current_round in range(1, max_rounds + 1):
        result.rounds_executed = current_round
        round_window = window_size * current_round
        adjacent_cids = get_adjacent_candidate_ids(
            pool=pool,
            source_id=source_id,
            kind=kind,
            base_ordinals=current_ordinals,
            window=round_window,
        )
        candidates_to_check = [pool[cid] for cid in adjacent_cids if cid not in used_cids]

        newly_resolved_roles = []
        for role in roles_to_expand:
            matches = scan_candidates_for_role(candidates_to_check, role)
            if matches:
                matched_cand, matched_kw = matches[0]
                matched_cid = matched_cand.candidate_id
                used_cids.add(matched_cid)
                parsed = parse_candidate_ordinal(matched_cid)
                if parsed:
                    current_ordinals.add(parsed[2])

                # Augment step field
                claim_text = matched_cand.text.strip()
                new_claim = {
                    "text": claim_text,
                    "evidence_type": "stated",
                    "evidence": [[matched_cid]],
                    "explanation": f"Context expansion round {current_round} matched keyword '{matched_kw}' in adjacent cue {matched_cid}.",
                }

                if isinstance(fields.get(role), dict):
                    fields[role]["state"] = "present"
                    fields[role].setdefault("claims", []).append(new_claim)
                else:
                    fields[role] = [new_claim]

                result.fields_augmented.setdefault(role, []).append(matched_cid)
                newly_resolved_roles.append(role)
                result.audit_log.append(
                    ExpansionRoundLog(
                        round_number=current_round,
                        field_role=role,
                        previous_candidate_ids=[str(x) for x in sorted(ordinals)],
                        expanded_candidate_ids=[matched_cid],
                        matched_keyword=matched_kw,
                        success=True,
                        note=f"Đã tìm thấy căn cứ cho {role} tại {matched_cid} (từ khóa '{matched_kw}').",
                    )
                )
            else:
                result.audit_log.append(
                    ExpansionRoundLog(
                        round_number=current_round,
                        field_role=role,
                        previous_candidate_ids=[str(x) for x in sorted(ordinals)],
                        expanded_candidate_ids=[],
                        matched_keyword=None,
                        success=False,
                        note=f"Vòng {current_round} (window ±{round_window}): không tìm thấy từ khóa chỉ dẫn cho {role}.",
                    )
                )

        for r in newly_resolved_roles:
            roles_to_expand.remove(r)

        if not roles_to_expand:
            break

    result.unresolved_fields = roles_to_expand
    return result
