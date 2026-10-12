"""python -m scripts.benchmark_knowflow prepare|smoke|run|report --run-dir PATH."""
import argparse
import asyncio
import json
import os
import random
import threading
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from knowflow_contracts.models import AnswerResponse, QueryRequest
from retrieval.api.app import create_app
from retrieval.evaluation.answers import answer_digest, check_citation, check_grounding, check_leakage
from retrieval.evaluation.harness import load_questions, run_evaluation, score_ranking
from retrieval.generation.evidence import EvidenceAccess
from retrieval.generation.service import QAService
from retrieval.indexing.embeddings import RATE_LIMIT_WAITED
from retrieval.indexing.search_index import build_index, digest, read_corpus, require_index
from retrieval.retrieval.engine import RetrievalConfig, retrieve

from .audit import ROOT, audit, sha_file, verify_label_approval
from .baseline import TranscriptRAG, build_raw_index, public_chunk, RAW_DRAFT_POLICY, RAW_VERIFY_POLICY
from .providers import MeasuredAnswerModel, MeasuredEmbedder, MeasuredTranslator, IndexEmbedder, Recorder, now
from .pairing import PairedRetrieval, without_graph

ARMS = ("A_knowflow", "B_transcript_rag", "C_no_graph")


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def measurement_files():
    return [*sorted((ROOT / "retrieval").rglob("*.py")),
            *sorted((ROOT / "contracts/schema/knowflow_contracts").rglob("*.py")),
            *[ROOT / f"scripts/benchmark_knowflow/{f}.py" for f in
              ("__main__", "audit", "baseline", "providers", "pairing", "resume_preparation")], ROOT / "pyproject.toml"]


def freeze(config, run_dir, audit_result):
    data = {"frozen_at": now(), "config": config, "config_sha256": digest(config),
            "measurement_code_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha_file(p)
                                        for p in measurement_files()},
            "input_files": audit_result["input_files"], "product_commit": audit_result["git"]["head"],
            "baseline_policy_hashes": {"draft": digest(RAW_DRAFT_POLICY), "verify": digest(RAW_VERIFY_POLICY)}}
    save(run_dir / "frozen_config.json", data)
    return data


def verify_freeze(run_dir):
    frozen = json.loads((run_dir / "frozen_config.json").read_text(encoding="utf-8"))
    if digest(frozen["config"]) != frozen["config_sha256"]:
        raise ValueError("Frozen configuration changed")
    for group in ("measurement_code_sha256", "input_files"):
        for name, expected in frozen[group].items():
            if sha_file(ROOT / name) != expected:
                raise ValueError(f"Frozen file changed: {name}")
    return frozen["config"]


def prepare(config, run_dir):
    verify_label_approval(config)  # before creating a run or making any provider call
    run_dir.mkdir(parents=True, exist_ok=False)
    work = ROOT / "out/benchmark_knowflow" / run_dir.name
    work.mkdir(parents=True, exist_ok=False)
    db = work / "real_dev.sqlite"
    metadata = audit(config, db)
    save(run_dir / "audit.json", metadata)
    freeze(config, run_dir, metadata)
    save(run_dir / "working_paths.json", {"db": str(db.relative_to(ROOT)).replace("\\", "/"),
                                          "raw_index": str((work / "raw_index.json").relative_to(ROOT)).replace("\\", "/")})
    # Fresh offline reproduction, before replacing this benchmark-only index with real vectors.
    lexical_manifest = build_index(db, mode="real", split="dev")
    offline_report, offline_rows = run_evaluation(db, ROOT / config["questions"], mode="real", split="dev",
                                                strategies=["lexical"], translate=False)
    save(run_dir / "offline_bm25_report.json", offline_report)
    for row in offline_rows:
        append(run_dir / "offline_bm25_rows.jsonl", row)
    print(json.dumps({"audit_questions": metadata["questions"], "gold_review": metadata["labels"],
                      "active_workflows": metadata["active_workflows"],
                      "offline_bm25": offline_report["strategies"]["lexical"]["retrieval"]}), flush=True)
    recorder = Recorder(run_dir / "provider_calls.jsonl")
    embedder = IndexEmbedder(recorder, config["embedding_dimensions"],
                            **config.get("index_pacing", {}))
    start = time.perf_counter()
    try:
        recorder.arm = "A_knowflow"
        manifest = build_index(db, mode="real", split="dev", embedder=embedder)
        structured_ms = (time.perf_counter() - start) * 1000
        corpus = read_corpus(db, "real", "dev")
        recorder.arm = "B_transcript_rag"
        start = time.perf_counter()
        streams, chunks = build_raw_index(corpus["sources"], ROOT, config, embedder)
        raw_ms = (time.perf_counter() - start) * 1000
        raw_index = {"streams": streams, "chunks": chunks, "embedding": embedder.config}
        save(work / "raw_index.json", raw_index)
        for chunk in chunks:
            append(run_dir / "raw_source_chunks.jsonl", public_chunk(chunk))
        save(run_dir / "index_manifest.json", {"structured": manifest,
             "structured_index_latency_ms": structured_ms, "raw_index_latency_ms": raw_ms,
             "raw_chunks": len(chunks), "raw_index_sha256": sha_file(work / "raw_index.json"),
             "raw_chunk_projection_sha256": sha_file(run_dir / "raw_source_chunks.jsonl"),
             "ablation": ("A/C replay one persisted real retrieval with identical translations and candidates before C drops graph fields"
                          if config["execution"].get("paired_ac_retrieval") else
                          "C shares A's exact immutable index; neighbor_depth=0 and relations removed after retrieval"),
             "lexical_manifest": lexical_manifest, "raw_preprocessing": config["baseline"]})
        save(run_dir / "preparation_status.json", {"ok": True, "finished_at": now()})
        print(json.dumps({"prepared": True, "structured_documents": manifest.get("record_count"),
                          "raw_chunks": len(chunks), "index_build_id": manifest["index_build_id"]}), flush=True)
    except Exception as exc:
        save(run_dir / "preparation_status.json", {"ok": False, "error_class": type(exc).__name__,
                                                   "finished_at": now(), "no_fake_fallback": True})
        print(json.dumps({"prepared": False, "error_class": type(exc).__name__}), flush=True)
        raise SystemExit(2) from None
    finally:
        embedder.close()


class ObservedService(QAService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.finished, self.last_error = threading.Event(), None

    def ask(self, request):
        try:
            return super().ask(request)
        except Exception as exc:
            self.last_error = type(exc).__name__
            raise
        finally:
            self.finished.set()


class Retriever:
    def __init__(self, embedder, translator, no_graph=False, paired=None):
        self.embedder, self.translator, self.no_graph = embedder, translator, no_graph
        self.last = None
        self.paired, self.pair_metadata = paired, None

    def __call__(self, db, request, *, config=None):
        if self.no_graph and self.paired is None:
            config = replace(config, neighbor_depth=0)
        try:
            result = (self.paired.get(db, request, config) if self.paired else
                      retrieve(db, request, config=config, embedder=self.embedder, translator=self.translator))
        finally:
            self.pair_metadata = self.paired.last_metadata if self.paired else None
        if self.no_graph:
            result = without_graph(result)
        self.last = result
        return result


def compact_retrieval(result):
    if result is None:
        return None
    if "chunks" in result:
        return result
    output = {k: v for k, v in result.items() if k not in ("claims", "related_claims", "conflicts")}
    for key in ("claims", "related_claims", "conflicts"):
        output[key] = [{"claim_ref": c["claim_ref"], "text": c["claim"]["text"],
                        "matched_step_ids": c["matched_step_ids"], "purpose": c["purpose"],
                        "source_review": c["claim"]["source_review"], "technical_review": c["claim"]["technical_review"],
                        "evidence": [{"evidence": e["evidence"], "link": e["link"], "source_id": e["source"]["source_id"]}
                                     for e in c["evidence"]]} for c in result[key]]
    return output


def baseline_app(service, done, error_info, timeout):
    app = FastAPI()

    def invoke(query):
        try:
            return service.ask(query)
        except Exception as exc:
            error_info["class"] = type(exc).__name__
            raise
        finally:
            done.set()

    @app.post("/v1/ask")
    async def ask(query: QueryRequest):
        if (str(query.mode), str(query.dataset_split)) != ("real", "dev"):
            return JSONResponse(status_code=422, content={"error": {"code": "namespace_unavailable"}})
        task = asyncio.create_task(asyncio.to_thread(invoke, query))
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout)
        except (TimeoutError, asyncio.TimeoutError):
            return JSONResponse(status_code=504, content={"error": {"code": "query_timeout"}})
        except Exception:
            return JSONResponse(status_code=503, content={"error": {"code": "provider_or_baseline_error"}})

    return app


def run_questions(run_dir, phase):
    config = verify_freeze(run_dir)
    if phase == "full" and not json.loads((run_dir / "smoke_status.json").read_text(encoding="utf-8"))["passed"]:
        raise ValueError("Full run requires a successful smoke test")
    paths = json.loads((run_dir / "working_paths.json").read_text(encoding="utf-8"))
    db = ROOT / paths["db"]
    corpus = read_corpus(db, "real", "dev")
    index = json.loads((run_dir / "index_manifest.json").read_text(encoding="utf-8"))
    if require_index(corpus)[0] != {k: v for k, v in index["structured"].items() if k != "status"}:
        raise ValueError("Benchmark structured index changed")
    if sha_file(ROOT / paths["raw_index"]) != index["raw_index_sha256"]:
        raise ValueError("Baseline index changed")
    raw_index = json.loads((ROOT / paths["raw_index"]).read_text(encoding="utf-8"))
    questions, _ = load_questions(ROOT / config["questions"])
    if phase == "smoke":
        lookup = {q.question_id: q for q in questions}
        questions = [lookup[qid] for qid in config["execution"]["smoke_question_ids"]]
    else:
        random.Random(config["execution"]["seed"]).shuffle(questions)
    order = [(question.question_id, ARMS[(i + shift) % len(ARMS)])
             for i, question in enumerate(questions) for shift in range(len(ARMS))]
    save(run_dir / f"{phase}_execution_order.json", order)
    output = run_dir / ("rows.jsonl" if phase == "full" else "smoke_rows.jsonl")
    previous = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    completed = {(r["question_id"], r["arm"]) for r in previous}
    if len(completed) != len(previous):
        raise ValueError("Duplicate rows in existing journal")
    recorder = Recorder(run_dir / "provider_calls.jsonl")
    # Preserve monotonically unique call IDs on resume, without reusing provider responses.
    if recorder.path.exists():
        recorder.events = [json.loads(line) for line in recorder.path.read_text(encoding="utf-8").splitlines()]
    recorder.phase = phase
    embedder = MeasuredEmbedder(recorder, config["embedding_dimensions"])
    translator = MeasuredTranslator(recorder, config["translation_model"])
    payloads = []
    factory = lambda: MeasuredAnswerModel(recorder, config, payloads)
    paired = (PairedRetrieval(run_dir / "shared_retrieval", recorder,
              lambda db, request, config: retrieve(db, request, config=config, embedder=embedder, translator=translator),
              index["structured"]["documents_sha256"]) if config["execution"].get("paired_ac_retrieval") else None)
    retrievers, services, clients, done, errors = {}, {}, {}, {}, {}
    for arm in (ARMS[0], ARMS[2]):
        retrievers[arm] = Retriever(embedder, translator, no_graph=arm == ARMS[2], paired=paired)
        services[arm] = ObservedService({("real", "dev"): db}, repo_root=ROOT,
                 config=RetrievalConfig(**config["retrieval"]), model_factory=factory, retriever=retrievers[arm])
        done[arm] = services[arm].finished
        clients[arm] = TestClient(create_app(services[arm], timeout_seconds=config["execution"]["api_timeout_seconds"]),
                                  raise_server_exceptions=False)
    services[ARMS[1]] = TranscriptRAG(raw_index["streams"], raw_index["chunks"], config, embedder, translator, factory)
    done[ARMS[1]], errors[ARMS[1]] = threading.Event(), {}
    clients[ARMS[1]] = TestClient(baseline_app(services[ARMS[1]], done[ARMS[1]], errors[ARMS[1]],
                             config["execution"]["api_timeout_seconds"]), raise_server_exceptions=False)
    for client in clients.values():
        client.__enter__()
    access = EvidenceAccess(ROOT)
    try:
        for question in questions:
            for qid, arm in [item for item in order if item[0] == question.question_id]:
                if (qid, arm) in completed:
                    continue
                recorder.arm, recorder.question_id = arm, qid
                effective_timeout = config["execution"]["api_timeout_seconds"]
                if paired and arm in retrievers:
                    # A replay cannot add generation time beyond the same total
                    # deadline. Charge the original retrieval time to this arm.
                    replay_path = run_dir / "shared_retrieval" / f"{phase}_{qid}.json"
                    if replay_path.exists():
                        saved_pair = json.loads(replay_path.read_text(encoding="utf-8"))
                        effective_timeout = max(.001, effective_timeout - saved_pair["latency_ms"] / 1000)
                    clients[arm].__exit__(None, None, None)
                    clients[arm] = TestClient(create_app(services[arm], timeout_seconds=effective_timeout),
                                             raise_server_exceptions=False)
                    clients[arm].__enter__()
                payloads.clear()
                done[arm].clear()
                if arm in retrievers:
                    retrievers[arm].last = None
                    retrievers[arm].pair_metadata = None
                    services[arm].last_error = None
                else:
                    services[arm].last_retrieval, services[arm].last_guard = None, None
                    errors[arm].clear()
                request = QueryRequest(question=question.question, context=question.context, mode="real", dataset_split="dev")
                start_events, start_backoff = len(recorder.events), RATE_LIMIT_WAITED["seconds"]
                started_at, start = now(), time.perf_counter()
                response = clients[arm].post("/v1/ask", json=request.model_dump(mode="json"))
                latency = (time.perf_counter() - start) * 1000
                # The actual HTTP deadline may expire while its shielded product work finishes.
                # Drain before another question so telemetry is never attributed to the wrong row.
                drain_start = time.perf_counter()
                while not done[arm].wait(1):
                    if time.perf_counter() - drain_start > 600:
                        raise RuntimeError("Provider work did not drain; journal contains unfinished question")
                drain_ms = (time.perf_counter() - drain_start) * 1000
                events = recorder.events[start_events:]
                calls = [e for e in events if e["kind"] == "provider_call" and e["arm"] == arm]
                call_ids = {e["call_id"] for e in calls}
                pair_meta = retrievers[arm].pair_metadata if arm in retrievers else None
                body = response.json()
                result = retrievers[arm].last if arm in retrievers else services[arm].last_retrieval
                row = {"phase": phase, "arm": arm, "question_id": qid, "question": question.question,
                       "language": question.language, "category": question.category, "labelled_intent": question.intent,
                       "context": request.context.model_dump(mode="json"), "expected_status": str(question.expected_status),
                       "expected_retrieval_status": question.expected_retrieval_status, "label_status": question.label.status,
                       "started_at": started_at, "finished_at": now(), "http_status": response.status_code,
                       "status": body.get("status", "error"), "response": body,
                       "latency_ms": round(latency, 3), "post_timeout_drain_ms": round(drain_ms, 3),
                       "effective_api_timeout_seconds": effective_timeout,
                       "backoff_seconds": RATE_LIMIT_WAITED["seconds"] - start_backoff,
                       "provider_calls": calls, "http_attempts": [e for e in events if e["kind"] == "http_attempt" and e["call_id"] in call_ids],
                       "shared_retrieval": pair_meta,
                       "latency_ms_standalone_component_sum": round(latency + (pair_meta["latency_ms"]
                            if pair_meta and pair_meta["replayed"] else 0), 3),
                       "latency_interpretation": "observed_HTTP; second_AC_arm_replays_retrieval; component_sum_is_reconstructed_not_observed" if pair_meta else "observed_HTTP",
                       "payloads": list(payloads), "retrieval": compact_retrieval(result),
                       "model": config["answer_model"], "index_build_id": index["structured"]["index_build_id"] if arm != ARMS[1] else None,
                       "raw_index_sha256": index["raw_index_sha256"] if arm == ARMS[1] else None,
                       "recall_at_5": None, "reciprocal_rank_at_5": None, "first_relevant_rank": None,
                       "human_review": None}
                row["error_class"] = services[arm].last_error if arm in retrievers else errors[arm].get("class")
                row["status_ok"] = response.status_code == 200 and row["status"] == str(question.expected_status)
                row["false_answer"] = row["status"] == "answered" and str(question.expected_status) != "answered"
                row["false_abstention"] = str(question.expected_status) == "answered" and row["status"] in (
                                               "insufficient_evidence", "needs_clarification", "conflicting_sources")
                row["retrieval_scored"] = question.scored and arm != ARMS[1]
                if row["retrieval_scored"]:
                    ranked = [(s["workflow_id"], s["revision"], s["step_id"]) for s in result["steps"]] if result else []
                    scores = score_ranking(ranked, [{ref.key for ref in unit} for unit in question.gold_units], 5)
                    row.update(recall_at_5=scores["recall"], reciprocal_rank_at_5=scores["reciprocal_rank"],
                               first_relevant_rank=scores["first_relevant_rank"])
                if response.status_code == 200 and arm in retrievers:
                    answer = AnswerResponse.model_validate(body)
                    row["answer_sha256"] = answer_digest(answer)
                    row["citation_checks"] = [check_citation(c, corpus, request, access) for c in answer.citations]
                    row["grounding"] = check_grounding(answer)
                    row["leakage"] = check_leakage(question, answer, corpus, request)
                elif response.status_code == 200:
                    row["answer_sha256"] = digest([body["status"], body["answer"], body["citations"]])
                    allowed = {c["id"]: c for c in (result or {}).get("chunks", [])}
                    row["citation_checks"] = [services[arm].check_citation(c, allowed) for c in body["citations"]]
                    row["grounding"] = {"structural_only": True, "semantic_support": None}
                    row["leakage"] = []
                    row["baseline_guard"] = services[arm].last_guard
                else:
                    row.update(answer_sha256=None, citation_checks=[], grounding=None, leakage=[])
                append(output, row)
                print(json.dumps({"phase": phase, "arm": arm, "qid": qid, "http": response.status_code,
                                  "status": row["status"], "latency_ms": row["latency_ms"],
                                  "calls": len(calls), "citations": len(row["citation_checks"])}), flush=True)
    finally:
        for client in clients.values():
            client.__exit__(None, None, None)
        translator.close()
        embedder.close()
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    if phase == "smoke":
        errors_found = [r for r in rows if r["http_status"] != 200]
        real_generation = {arm: any(r["arm"] == arm and any(c["stage"] == "answer_generation" and c["ok"]
                                         for c in r["provider_calls"]) for r in rows) for arm in ARMS}
        passed = len(rows) == len(order) and not errors_found and all(real_generation.values())
        save(run_dir / "smoke_status.json", {"passed": passed, "rows": len(rows), "real_generation": real_generation,
                                            "errors": [{"arm": r["arm"], "qid": r["question_id"]} for r in errors_found],
                                            "finished_at": now(), "quality_threshold_used": False})
        if not passed:
            raise SystemExit(2)
    else:
        save(run_dir / "run_status.json", {"completed_rows": len(rows), "expected_rows": len(order),
                                          "complete": len(rows) == len(order), "finished_at": now()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "smoke", "run", "report"))
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--config", default="benchmarks/knowflow_real_dev/config.json", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if args.command == "prepare":
        prepare(json.loads(args.config.read_text(encoding="utf-8")), args.run_dir.resolve())
    elif args.command in ("smoke", "run"):
        run_questions(args.run_dir.resolve(), "smoke" if args.command == "smoke" else "full")
    else:
        from .report import write_report
        write_report(args.run_dir.resolve())


if __name__ == "__main__":
    main()
