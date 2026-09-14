"""Conservative context extraction and hard metadata gates before ranking."""

import re

from knowflow_contracts.models import QueryContext, Workflow
from .ranking import fold

SCALAR_FIELDS = ("manufacturer", "machine_family", "machine_model", "subsystem", "task_type")


def normal(field: str, value: str) -> str:
    if field == "alarm_codes":
        return fold(value).strip()
    value = re.sub(r"[^a-z0-9]", "", fold(value))
    if field == "manufacturer" and value in ("haas", "haasautomation", "haasautomationinc"):
        return "haas"
    if field == "subsystem" and value in ("smtc", "sidemounttoolchanger", "sidemounttoolchangersmtc"):
        return "smtc"
    return value


def resolve_context(question: str, provided: QueryContext, workflows: list[Workflow]) -> tuple[QueryContext, list[str], dict]:
    text = fold(question)
    detected: dict[str, list[str]] = {}
    models = re.findall(r"\b(?:vf|vm|st|umc|dt|dm|ec|dc)[- ]?\d+(?:ss|y|l)?\b|\bdemo[_ -]tc[_ -][a-z0-9]+\b", text)
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
    alarms = re.findall(r"(?:alarm(?: code)?|ma loi|loi|bao dong)\s*[:#]?\s*([a-z]*\d[\w.-]*)", text)
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
