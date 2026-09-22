"""Conservative context extraction and hard metadata gates before ranking."""

import re
import unicodedata

from knowflow_contracts.models import QueryContext, Workflow
from .ranking import fold

SCALAR_FIELDS = ("manufacturer", "machine_family", "machine_model", "subsystem", "task_type")
# Controlled subsystem aliases, including the component-qualified label in TG0128.
# This changes identity comparison only: "double arm" stays in snapshots/search text.
# Do not use substring matching or discard arbitrary qualifiers (e.g. umbrella SMTC).
SMTC_ALIASES = frozenset({
    "smtc", "sidemounttoolchanger", "sidemounttoolchangersmtc",
    "smtcdoublearm", "sidemounttoolchangerdoublearm", "sidemounttoolchangersmtcdoublearm",
})
# VF/VM/UMC are unambiguous even as "VF 2"; short prefixes must touch the number
# ("ST-10", "EC400") so that "DC 24 V" or "st 2" are not read as machine models.
MODEL_PATTERN = re.compile(r"\b(?:vf|vm|umc)[- ]?\d+(?:ss|y|l)?\b|\b(?:st|ds|dt|dm|ec|tm)-?\d+(?:ss|y|l)?\b"
                           r"|\bdemo[_ -]tc[_ -][a-z0-9]+\b")
# Matched on the question WITH diacritics: "lỗi 2066" is an alarm, "lối"/"lời"/"lợi" are not.
ALARM_PATTERN = re.compile(r"(?<!\w)(?:alarm(?:\s+code)?|lỗi|loi|báo\s+động|bao\s+dong)(?:\s*[:#]\s*|\s+)"
                           r"(?:(?:số|so)\s+)?([a-z]*\d[\w.-]*)")


def normal(field: str, value: str) -> str:
    if field == "alarm_codes":
        return fold(value).strip()
    value = re.sub(r"[^a-z0-9]", "", fold(value))
    if field == "manufacturer" and value in ("haas", "haasautomation", "haasautomationinc"):
        return "haas"
    if field == "subsystem" and value in SMTC_ALIASES:
        return "smtc"
    return value


def resolve_context(question: str, provided: QueryContext, workflows: list[Workflow]) -> tuple[QueryContext, list[str], dict]:
    text = fold(question)
    detected: dict[str, list[str]] = {}
    models = MODEL_PATTERN.findall(text)
    if models:
        detected["machine_model"] = models
    # Match exact known model/family names, including synthetic fixture identities.
    for field in ("manufacturer", "machine_family", "machine_model", "subsystem"):
        for wf in workflows:
            value = getattr(wf.context, field)
            if value and re.search(r"(?<!\w)" + re.escape(fold(value)) + r"(?!\w)", text):
                detected.setdefault(field, []).append(value)
    if re.search(r"\bhaas\b", text):
        detected.setdefault("manufacturer", []).append("Haas")
    if re.search(r"\bsmtc\b|side[- ]mount tool changer", text):
        detected.setdefault("subsystem", []).append("SMTC")
    lowered = unicodedata.normalize("NFC", question).casefold()
    alarms = [code.rstrip(".-") for code in ALARM_PATTERN.findall(lowered)]
    merged = provided.model_dump()
    conflicts = []
    for field, values in detected.items():
        unique = {normal(field, value): value for value in values}
        explicit = merged[field]
        if len(unique) > 1 or (explicit and normal(field, explicit) not in unique):
            conflicts.append(field)
        elif not explicit:
            merged[field] = next(iter(unique.values()))
    if alarms:
        explicit_codes = {normal("alarm_codes", c) for c in merged["alarm_codes"]}
        if explicit_codes and explicit_codes != {normal("alarm_codes", c) for c in alarms}:
            conflicts.append("alarm_codes")
        elif not explicit_codes:
            merged["alarm_codes"] = list(dict.fromkeys(alarms))
    return QueryContext.model_validate(merged), sorted(set(conflicts)), detected


def context_gate(workflow: Workflow, context: QueryContext) -> tuple[list[str], list[str]]:
    mismatches, unknown = [], []
    for field in SCALAR_FIELDS:
        requested, actual = getattr(context, field), getattr(workflow.context, field)
        if requested:
            if not actual:
                unknown.append(field)
            elif normal(field, requested) != normal(field, actual):
                mismatches.append(field)
        elif field == "machine_model" and actual:
            unknown.append(field)  # model-specific procedure needs user identity
    if context.alarm_codes:
        actual = {normal("alarm_codes", c) for c in workflow.context.alarm_codes}
        if not actual:
            unknown.append("alarm_codes")
        elif not {normal("alarm_codes", c) for c in context.alarm_codes}.issubset(actual):
            mismatches.append("alarm_codes")
    if any(q.reason == "identity" and q.status in ("open", "answered") for q in workflow.questions):
        unknown.append("machine_model")
    return sorted(set(mismatches)), sorted(set(unknown))
