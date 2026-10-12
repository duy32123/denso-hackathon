"""Three live API development checks; not the official 81-question benchmark."""
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from knowflow_contracts.models import QueryRequest
from retrieval.api.app import create_app
from retrieval.generation.service import QAService
from retrieval.retrieval.engine import RetrievalConfig
from scripts.benchmark_knowflow.__main__ import Retriever, compact_retrieval, measurement_files
from scripts.benchmark_knowflow.audit import ROOT, sha_file, git
from scripts.benchmark_knowflow.providers import Recorder, MeasuredEmbedder, MeasuredTranslator, MeasuredAnswerModel


def main():
    load_dotenv(ROOT / ".env")
    destination = ROOT / "benchmarks/diagnostics/20261012_live_fix_smoke"
    destination.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / "benchmarks/knowflow_expanded_dev/config.json").read_text(encoding="utf-8"))
    metadata = {"development_smoke_only": True, "official_benchmark": False, "negative_label_review_pending": True,
                "head": git("rev-parse", "HEAD"), "code_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): sha_file(p) for p in measurement_files()},
                "config": config, "questions_hash": sha_file(ROOT / config["questions"]), "holdout_opened": False}
    (destination / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    recorder = Recorder(destination / "provider_calls.jsonl")
    recorder.phase, recorder.arm = "development_smoke", "A_knowflow"
    embedder = MeasuredEmbedder(recorder)
    translator = MeasuredTranslator(recorder, config["translation_model"])
    payloads = []
    retriever = Retriever(embedder, translator)
    service = QAService({("real", "dev"): ROOT / "out/web/real_dev_4a18533.sqlite"}, repo_root=ROOT,
                        config=RetrievalConfig(**config["retrieval"]), retriever=retriever,
                        model_factory=lambda: MeasuredAnswerModel(recorder, config, payloads))
    questions = [json.loads(line) for line in (ROOT / config["questions"]).read_text(encoding="utf-8").splitlines()]
    try:
        with TestClient(create_app(service), raise_server_exceptions=False) as client:
            for q in questions:
                if q["question_id"] not in {"HAAS_DEV_Q015", "HAAS_DEV_Q031", "HAAS_DEV_Q069"}:
                    continue
                recorder.question_id = q["question_id"]
                begin = len(recorder.events)
                start = time.perf_counter()
                request = QueryRequest(question=q["question"], context=q["context"], mode="real", dataset_split="dev")
                response = client.post("/v1/ask", json=request.model_dump(mode="json"))
                row = {"question_id": q["question_id"], "question": q["question"], "http_status": response.status_code,
                       "response": response.json(), "latency_ms": (time.perf_counter()-start)*1000,
                       "retrieval": compact_retrieval(retriever.last), "provider_events": recorder.events[begin:],
                       "human_semantics": None, "included_in_official_results": False}
                with (destination / "rows.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False)+"\n")
                print(json.dumps({"qid": q["question_id"], "http": response.status_code, "status": row["response"].get("status"),
                                  "workflow": (retriever.last or {}).get("selected_workflow"), "latency_ms": row["latency_ms"]}), flush=True)
    finally:
        embedder.close()
        translator.close()


if __name__ == "__main__":
    main()
