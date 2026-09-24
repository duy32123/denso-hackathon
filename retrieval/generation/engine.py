"""Fail-closed citation guard plus a separate semantic check.

Code proves membership/revision/eligibility/openability, not natural-language
entailment. The model check is additional protection, NEVER human review.
"""

import re

from pydantic import ValidationError

from knowflow_contracts.eligibility import claim_blockers
from knowflow_contracts.enums import QueryMode
from knowflow_contracts.models import AnswerResponse, Citation, EntityRef, QueryRequest
from retrieval.indexing.search_index import RetrievalError
from retrieval.retrieval.query import looks_vietnamese

from .evidence import EvidenceAccess
from .models import AnswerDraft, AnswerModel, InvalidGeneration, Verification


def ref_key(ref: dict | EntityRef) -> tuple:
    if isinstance(ref, EntityRef):
        ref = ref.model_dump()
    return ref["workflow_id"], ref["revision"], ref["entity_type"], ref["entity_id"]


def fallback(request, result, status="insufficient_evidence", unresolved=()):
    vi = looks_vietnamese(request.question)
    messages = {
        "insufficient_evidence": ("Chưa đủ bằng chứng đã kiểm để trả lời câu hỏi này.",
                                  "There is insufficient checked evidence to answer this question."),
        "needs_clarification": ("Cần làm rõ ngữ cảnh trước khi trả lời.",
                                "Please clarify the context before an answer can be given."),
        "conflicting_sources": ("Nguồn có thông tin mâu thuẫn chưa được giải quyết; chưa thể đề xuất thao tác.",
                                "The sources contain unresolved conflicting claims; no action can be recommended."),
    }
    answer = messages[status][0 if vi else 1]
    if request.mode == "synthetic":
        answer = ("Dữ liệu mô phỏng — " if vi else "Synthetic data — ") + answer
    unique = {ref_key(ref): ref for ref in unresolved}
    return AnswerResponse(status=status, answer=answer, citations=[],
                          missing_context=result["missing_context"] if status == "needs_clarification" else [],
                          unresolved_claim_refs=list(unique.values()), index_build_id=result["index_build_id"])


def checked_candidates(request, result, corpus, access):
    """Rejoin to authoritative snapshots: never trust LLM/retrieval review flags."""
    candidates, unavailable = {}, []
    selected = result["selected_workflow"]
    for item in result["claims"]:
        ref = EntityRef.model_validate(item["claim_ref"])
        wf = corpus["workflows"].get(ref.workflow_id)
        if (not selected or wf is None or ref.entity_type != "claim"
                or ref.workflow_id != selected["workflow_id"] or ref.revision != selected["revision"]
                or wf.revision != ref.revision or (wf.source_type, wf.dataset_split) !=
                (request.mode, request.dataset_split) or item["purpose"] != "answer_candidate"):
            raise RetrievalError("Invalid candidate scope")
        claim = next((c for c in wf.claims if c.claim_id == ref.entity_id), None)
        if claim is None or claim.model_dump(mode="json") != item["claim"]:
            raise RetrievalError("Candidate differs from canonical snapshot")
        if claim_blockers(claim, wf, mode=QueryMode(request.mode), is_latest_indexed_revision=True):
            unavailable.append(ref)
            continue
        canonical_evidence = {e.evidence_id: e for e in wf.evidence}
        packaged = {e["evidence"]["evidence_id"] for e in item["evidence"]}
        evidence = []
        for link in claim.evidence_links:
            if link.support_status != "supported" or link.evidence_id not in packaged:
                continue
            ev = canonical_evidence[link.evidence_id]
            src = corpus["sources"][ev.source_id]
            if src.source_type != request.mode:
                raise RetrievalError("Evidence namespace mismatch")
            view = access.view(ev, src)
            if view.available:
                evidence.append({"evidence": ev.model_dump(mode="json"), "link": link.model_dump(mode="json"),
                                 "access_kind": view.kind, "source_id": src.source_id, "source_title": src.title})
        if not evidence:
            unavailable.append(ref)
            continue
        candidates[ref_key(ref)] = {"claim_ref": ref.model_dump(), "claim": claim.model_dump(mode="json"),
                                   "matched_step_ids": item["matched_step_ids"], "evidence": evidence}
    return candidates, unavailable


def numbers(text):
    return set(re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?:/\d+)?", text))


def generate_answer(request: QueryRequest, result: dict, corpus: dict, *,
                    model: AnswerModel, access: EvidenceAccess) -> AnswerResponse:
    manifest = corpus["index_manifest"]
    if ((result["source_type"], result["dataset_split"]) != (request.mode, request.dataset_split)
            or manifest is None or manifest["index_build_id"] != result["index_build_id"]
            or corpus["manifest"]["index_build_id"] != result["record_build_id"]):
        raise RetrievalError("Index changed or candidate namespace mismatch")
    if result["status"] != "retrieved":
        status = result["status"] if result["status"] in (
            "needs_clarification", "conflicting_sources") else "insufficient_evidence"
        # Conflicts are diagnostic references, never procedural instructions/citations.
        refs = [EntityRef.model_validate(c["claim_ref"]) for c in result["conflicts"]]
        return fallback(request, result, status, refs)
    candidates, unavailable = checked_candidates(request, result, corpus, access)
    procedure = result["trace"]["intent"] == "procedure"
    if not candidates or (procedure and (unavailable or result["trace"].get("omitted_step_ids"))):
        return fallback(request, result, unresolved=unavailable)
    # Ngon ngu cau tra loi do CODE quyet dinh, mot lan, roi dua xuong ca hai luot goi.
    # Truoc day moi luot tu doan: cau hoi tieng Viet + evidence tieng Anh thi luot soan
    # hay viet tieng Anh, luot kiem lai bat "sai ngon ngu" va vut ca cau tra loi dung.
    answer_language = "vi" if looks_vietnamese(request.question) else "en"
    payload = {"question": request.question, "answer_language": answer_language,
               "context": result["context"], "mode": request.mode,
               "intent": result["trace"]["intent"], "workflow": result["selected_workflow"],
               "steps": result["steps"], "relations": result["relations"], "questions": result["questions"],
               "candidates": list(candidates.values())}
    cited, checked_statements = [], []
    try:
        draft = AnswerDraft.model_validate(model.draft(payload))
        if draft.status != "answered" or not draft.statements:
            return fallback(request, result)
        for statement in draft.statements:
            item = candidates.get(ref_key(statement.claim_ref))
            if item is None or not statement.text.strip():
                raise InvalidGeneration("Unapproved claim reference")
            by_id = {e["evidence"]["evidence_id"]: e for e in item["evidence"]}
            if (len(set(statement.evidence_ids)) != len(statement.evidence_ids)
                    or not set(statement.evidence_ids) <= by_id.keys()):
                raise InvalidGeneration("Unapproved evidence reference")
            selected = [by_id[eid] for eid in statement.evidence_ids]
            literal = " ".join((e["evidence"]["quote"] or "") + " " +
                               (e["evidence"]["observation_note"] or "") for e in selected)
            if not numbers(statement.text) <= numbers(literal):
                raise InvalidGeneration("Number missing from cited evidence")
            cited.append(statement.claim_ref)
            checked_statements.append({"statement": statement.model_dump(mode="json"),
                                       "step_ids": item["matched_step_ids"],
                                       "claim": item["claim"], "evidence": selected})
        if procedure:
            covered = {sid for ref in cited for sid in candidates[ref_key(ref)]["matched_step_ids"]}
            if not {step["step_id"] for step in result["steps"]} <= covered:
                raise InvalidGeneration("Incomplete procedure")
            # Thu tu do code chung minh, khong giao cho luot kiem: tren Gemini that, quy trinh
            # bi dao nguoc van lot luot kiem 7/8 lan (prompt cu) va 3/8 (prompt moi).
            # Claim noi hai Step (relation) khong mang mot vi tri nen khong xet.
            order = {step["step_id"]: step["display_order"] for step in result["steps"]}
            positions = [order[ids[0]] for ids in (candidates[ref_key(ref)]["matched_step_ids"] for ref in cited)
                         if len(ids) == 1 and ids[0] in order]
            if positions != sorted(positions):
                raise InvalidGeneration("Procedure out of order")
        # Do NOT show the verifier unrelated claims that could rescue an invalid citation.
        # `answer` la dung cau tra loi nguoi dung se doc, theo dung thu tu. Thieu no, luot
        # kiem chi thay cac muc {statement, claim, evidence} roi rac va hay ket luan "khong
        # co cau tra loi" cho ca quy trinh day du, dung thu tu, moi cau deu supported.
        verification = Verification.model_validate(model.verify({
            "question": request.question, "answer_language": answer_language,
            "answer": [statement.text.strip() for statement in draft.statements],
            "context": result["context"], "intent": payload["intent"],
            "steps": result["steps"], "relations": result["relations"], "questions": result["questions"],
            "statements": checked_statements,
        }))
        if (not verification.answers_question or len(verification.supported) != len(draft.statements)
                or not all(verification.supported)):
            raise InvalidGeneration("Semantic check failed")
    except (InvalidGeneration, ValidationError):
        return fallback(request, result, unresolved=cited + unavailable)
    vi = answer_language == "vi"
    lines, citations = [], []
    for statement in draft.statements:
        claim = candidates[ref_key(statement.claim_ref)]["claim"]
        if request.mode == "synthetic":
            qualifier = "Dữ liệu mô phỏng" if vi else "Synthetic data"
        elif claim["technical_review"] == "expert_validated":
            qualifier = (("Chuyên gia xác nhận trong phạm vi: " if vi else "Expert validated within scope: ")
                         + claim["scope"]["description"])
        else:
            qualifier = ("Theo nguồn (chưa có xác nhận kỹ thuật)" if vi else
                         "According to the source (not technically validated)")
        lines.append(f"{qualifier}: {statement.text.strip()}")
        citations.append(Citation(answer_span=statement.text.strip(), claim_ref=statement.claim_ref,
                                  evidence_ids=statement.evidence_ids, source_review=claim["source_review"],
                                  technical_review=claim["technical_review"]))
    return AnswerResponse(status="answered", answer="\n\n".join(lines), citations=citations,
                          missing_context=[], unresolved_claim_refs=unavailable,
                          index_build_id=result["index_build_id"])
