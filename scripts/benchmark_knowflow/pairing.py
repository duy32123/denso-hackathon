"""Persist one real retrieval per A/C pair; replay exactly before graph ablation.

This is an experimental intervention, not production caching. Answer generation
still passes through QAService and the API for both arms. Shared provider calls
are costed once in the experiment ledger, separately from each arm's generation.
"""
import copy
import json
import time
from pathlib import Path

from retrieval.indexing.embeddings import EmbeddingError, RATE_LIMIT_WAITED
from retrieval.indexing.search_index import RetrievalError, digest
from retrieval.retrieval.query import TranslationError


def without_graph(result):
    output = copy.deepcopy(result)
    output["relations"], output["related_steps"], output["related_claims"] = [], [], []
    return output


def pre_graph_signature(result):
    return digest({k: v for k, v in result.items() if k not in
                   ("relations", "related_steps", "related_claims", "trace")})


class PairedRetrieval:
    def __init__(self, directory, recorder, retrieve_fn, corpus_hash):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.recorder, self.retrieve_fn, self.corpus_hash = recorder, retrieve_fn, corpus_hash
        self.last_metadata = None

    def get(self, db, request, config):
        from dataclasses import asdict
        self.last_metadata = None
        key = digest({"request": request.model_dump(mode="json"), "config": asdict(config),
                      "corpus": self.corpus_hash})
        path = self.directory / f"{self.recorder.phase}_{self.recorder.question_id}.json"
        replay = path.is_file()
        if replay:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry["key"] != key or digest(entry["result"]) != entry["result_sha256"]:
                raise ValueError("Paired retrieval input/result changed")
        else:
            previous_arm = self.recorder.arm
            begin = len(self.recorder.events)
            start_backoff = RATE_LIMIT_WAITED["seconds"]
            start = time.perf_counter()
            self.recorder.arm = "AC_shared_retrieval"
            result, error = None, None
            try:
                result = self.retrieve_fn(db, request, config=config)
            except Exception as exc:
                error = type(exc).__name__
            finally:
                self.recorder.arm = previous_arm
            events = self.recorder.events[begin:]
            entry = {"key": key, "result": result, "result_sha256": digest(result),
                     "error_class": error, "latency_ms": (time.perf_counter() - start) * 1000,
                     "provider_call_ids": [e["call_id"] for e in events if e["kind"] == "provider_call"],
                     "backoff_seconds": RATE_LIMIT_WAITED["seconds"] - start_backoff,
                     "owner_arm": previous_arm,
                     "pre_graph_sha256": pre_graph_signature(result) if result else None,
                     "translation_sha256": digest((result or {}).get("trace", {}).get("query_translation"))}
            # Commit only complete retrieval output. No regenerated partial answers.
            path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.last_metadata = {k: v for k, v in entry.items() if k != "result"} | {"replayed": replay}
        if entry["error_class"]:
            error_type = {"EmbeddingError": EmbeddingError, "TranslationError": TranslationError,
                          "RetrievalError": RetrievalError}.get(entry["error_class"], RetrievalError)
            raise error_type("Shared real retrieval failed; no second retrieval attempt was made")
        return copy.deepcopy(entry["result"])
