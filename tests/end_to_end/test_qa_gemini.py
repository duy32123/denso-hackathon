"""Opt-in live smoke: real local index + real Gemini + HTTP facade + evidence.

Costs provider calls; NEVER run automatically in CI or treat two questions as an
evaluation benchmark. Build the real/dev index first; no automatic KB/index writes.
"""

import os

import pytest
from fastapi.testclient import TestClient

from knowflow_contracts.models import AnswerResponse
from retrieval.api.app import create_app


@pytest.mark.skipif(os.getenv("KNOWFLOW_LIVE_QA_TEST") != "1", reason="Opt-in Gemini calls on local real/dev index")
@pytest.mark.parametrize("question,status", [
    ("Bôi trơn con trượt của hốc dao như thế nào?", "answered"),
    ("Loại mỡ và cấp NLGI nào được chỉ định để bôi trơn con trượt hốc dao?", "insufficient_evidence"),
])
def test_live_real_qa(question, status):
    with TestClient(create_app()) as client:
        response = client.post("/v1/ask", json={"question": question,
            "context": {"manufacturer": "Haas", "subsystem": "SMTC"}, "mode": "real", "dataset_split": "dev"})
        assert response.status_code == 200, response.text
        answer = AnswerResponse.model_validate(response.json())
        assert answer.status == status, answer.model_dump_json()
        if status == "answered":
            assert answer.citations
            for citation in answer.citations:
                assert citation.source_review == "source_checked"
                assert citation.answer_span in answer.answer
                ref = citation.claim_ref
                for eid in citation.evidence_ids:
                    url = f"/v1/evidence/{ref.workflow_id}/{ref.revision}/{eid}"
                    evidence = client.get(url, params={"mode": "real", "dataset_split": "dev", "index_build_id": answer.index_build_id})
                    assert evidence.status_code == 200 and evidence.json()["available"]
        else:
            assert answer.citations == []
