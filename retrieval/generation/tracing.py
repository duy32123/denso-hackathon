"""Public retrieval telemetry. No model thoughts, raw asset paths or credentials."""
from __future__ import annotations

from pydantic import Field

from knowflow_contracts.models import QueryRequest, Strict


class TraceRequest(Strict):
    query: QueryRequest
    index_build_id: str = Field(min_length=1, max_length=160)
    top_k: int = Field(default=1, ge=1, le=5)
    generate_answer: bool = False


class TraceCancelled(Exception):
    pass


def ref(workflow_id, revision, kind, entity_id=None, state="selected", **metadata):
    return {"workflow_id": workflow_id, "revision": revision, "kind": kind,
            "entity_id": entity_id or workflow_id, "state": state, **metadata}


def retrieval_stage(stage, result):
    """Copy only allowlisted facts at the moment the real retriever emits them."""
    refs, data = [], {}
    selected = result["selected_workflow"]
    if stage == "context":
        for item in result["trace"]["filters"]:
            refs.append(ref(item["workflow_id"], item["revision"], "workflow",
                            state="blocked" if item["mismatches"] or item["unknown_context"] else "candidate",
                            reasons=item["mismatches"] + item["unknown_context"]))
        data = {"context": result["context"], "missing_context": result["missing_context"]}
    elif stage == "relevance":
        data = {"gate": result["trace"]["relevance"]["gate"]}
    elif stage == "ranked":
        refs = [ref(w["workflow_id"], w["revision"], "workflow", state="selected" if w == selected else "candidate",
                    score=w["score"]) for w in result["workflow_candidates"]]
        data = {"strategy": result["trace"]["config"]["strategy"]}
    elif stage == "matched":
        refs = [ref(s["workflow_id"], s["revision"], "step", s["step_id"], score=s["score"])
                for s in result["steps"]]
        refs += [ref(c["claim_ref"]["workflow_id"], c["claim_ref"]["revision"], "claim",
                     c["claim_ref"]["entity_id"]) for c in result["claims"]]
        data = {"steps": len(result["steps"]), "claims": len(result["claims"])}
    elif stage == "expanded":
        for s in result["related_steps"]:
            refs.append(ref(s["workflow_id"], s["revision"], "step", s["step_id"], state="context", depth=s["depth"]))
            for relation in s["via"]:
                refs.append(ref(s["workflow_id"], s["revision"], "relation", relation["relation_id"], state="context",
                                traversal_from=relation["to_step_id"] if relation["relation_type"] != "corrects" else relation["from_step_id"],
                                traversal_to=s["step_id"]))
        refs += [ref(c["claim_ref"]["workflow_id"], c["claim_ref"]["revision"], "claim",
                     c["claim_ref"]["entity_id"], state="context") for c in result["related_claims"]]
        data = {"related_steps": len(result["related_steps"]), "neighbors": result["trace"]["neighbors"]}
    elif stage == "retrieval_complete":
        data = {"status": result["status"], "latency_ms": result["trace"]["latency_ms"],
                "missing_context": result["missing_context"]}
        if selected:
            refs = [ref(selected["workflow_id"], selected["revision"], "question", q["question_id"], state="gap")
                    for q in result["questions"] if q["status"] == "open"]
        for c in result["conflicts"]:
            r = c["claim_ref"]
            refs.append(ref(r["workflow_id"], r["revision"], "claim", r["entity_id"], state="blocked", reasons=["unresolved_conflict"]))
    elif stage == "started":
        data = {"strategy": result["trace"]["config"]["strategy"], "top_k": result["trace"]["config"]["top_k"]}
    return {"type": "stage", "stage": stage, "refs": refs, "data": data}
