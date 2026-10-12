"""Instrumentation around real product adapters, preserving their prompts and retries."""
import contextlib
import hashlib
import json
import os
import time
from datetime import datetime, timezone

from google import genai
from google.genai import types

from retrieval.generation.gemini import GeminiAnswerModel
from retrieval.indexing.embeddings import GeminiEmbedder
from retrieval.indexing.search_index import digest
from retrieval.retrieval.query import GeminiTranslator


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Recorder:
    def __init__(self, path):
        self.path, self.events, self.stage = path, [], "unassigned"
        self.phase, self.arm, self.question_id = "preparation", "index", None
        self.call_id = None

    @contextlib.contextmanager
    def at(self, stage):
        previous = self.stage
        self.stage = stage
        try:
            yield
        finally:
            self.stage = previous

    def write(self, entry):
        row = {"phase": self.phase, "arm": self.arm, "question_id": self.question_id, **entry}
        self.events.append(row)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")

    def request_hook(self, request):
        request.extensions["benchmark_start"] = time.perf_counter()
        request.extensions["benchmark_call"] = self.call_id

    def response_hook(self, response):
        # Intentionally omit headers, request URL, key, SDK exception text and body.
        self.write({"kind": "http_attempt", "call_id": response.request.extensions.get("benchmark_call"),
                    "stage": self.stage, "status_code": response.status_code,
                    "elapsed_ms": round((time.perf_counter() - response.request.extensions["benchmark_start"]) * 1000, 3),
                    "at": now()})

    def client(self, timeout=30000):
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("API key is not configured")
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=timeout,
                            client_args={"event_hooks": {"request": [self.request_hook], "response": [self.response_hook]}}))
        return ClientProxy(client, self)


class ClientProxy:
    def __init__(self, inner, recorder):
        self.inner, self.models = inner, ModelsProxy(inner.models, recorder)

    def close(self):
        self.inner.close()


class ModelsProxy:
    def __init__(self, inner, recorder):
        self.inner, self.recorder = inner, recorder

    def _call(self, operation, kwargs):
        rec = self.recorder
        identifiers = [int(e["call_id"].split("-")[-1]) for e in rec.events if e.get("call_id")]
        call_id = f"call-{max(identifiers, default=0) + 1:06d}"
        rec.call_id = call_id
        start, timestamp = time.perf_counter(), now()
        contents = kwargs.get("contents")
        row = {"kind": "provider_call", "call_id": call_id, "stage": rec.stage,
               "operation": operation, "model": kwargs["model"], "started_at": timestamp,
               "input_sha256": digest(contents), "input_utf8_bytes": len(json.dumps(contents, ensure_ascii=False).encode("utf-8")),
               "input_tokens": None, "output_tokens": None, "billed_output_tokens": None,
               "total_tokens": None, "usage_origin": None, "response_text": None}
        # Survives process interruption before response/finally; unknown usage is
        # still a possible billed call and must not disappear from accounting.
        rec.write({**row, "kind": "provider_call_started", "ok": None,
                   "error_class": None, "elapsed_ms": None})
        try:
            response = getattr(self.inner, operation)(**kwargs)
            meta = getattr(response, "usage_metadata", None)
            row.update({"ok": True, "error_class": None, "http_code": None,
                        "model_version": getattr(response, "model_version", None),
                        "usage_metadata": meta.model_dump(mode="json") if meta else None})
            if meta:
                row.update(input_tokens=meta.prompt_token_count, output_tokens=meta.candidates_token_count,
                           total_tokens=meta.total_token_count, usage_origin="provider_usage_metadata")
                if meta.total_token_count is not None and meta.prompt_token_count is not None:
                    row["billed_output_tokens"] = meta.total_token_count - meta.prompt_token_count
            if operation == "generate_content":
                row["response_text"] = response.text
            elif operation == "embed_content":
                row["embedding_metadata"] = response.metadata.model_dump(mode="json") if response.metadata else None
                row["embedding_statistics"] = [v.statistics.model_dump(mode="json") if v.statistics else None
                                               for v in response.embeddings or []]
                # No character-to-token estimate and no fabricated zero.
            return response
        except Exception as exc:
            row.update(ok=False, error_class=type(exc).__name__, http_code=getattr(exc, "code", None))
            raise
        finally:
            row["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 3)
            rec.write(row)
            rec.call_id = None

    def generate_content(self, **kwargs):
        return self._call("generate_content", kwargs)

    def embed_content(self, **kwargs):
        return self._call("embed_content", kwargs)


class MeasuredEmbedder(GeminiEmbedder):
    def __init__(self, recorder, dimensions=768):
        super().__init__(dimensions)
        self.recorder, self._client = recorder, recorder.client()

    def documents(self, texts):
        with self.recorder.at("embedding_index"):
            return super().documents(texts)

    def query(self, text):
        with self.recorder.at("embedding_query"):
            return super().query(text)


class MeasuredTranslator(GeminiTranslator):
    def __init__(self, recorder, model):
        super().__init__(model)
        self.recorder, self._client = recorder, recorder.client()

    def to_english(self, text):
        with self.recorder.at("translation"):
            return super().to_english(text)


class IndexEmbedder(MeasuredEmbedder):
    """Operational index pacing; preserves text chunks, vectors and aggregation.

    Query adapters remain unchanged. This class only reduces the batch sent to
    the real provider while creating the two indexes; no vector is synthesized.
    """
    def __init__(self, recorder, dimensions=768, *, batch_size=32, min_interval_seconds=0):
        super().__init__(recorder, dimensions)
        if not 1 <= batch_size <= 32 or min_interval_seconds < 0:
            raise ValueError("Invalid index batching/pacing")
        self.batch_size, self.min_interval_seconds = batch_size, min_interval_seconds
        self._last_index_call = None

    def _embed(self, texts, task):
        output = []
        for start in range(0, len(texts), self.batch_size):
            if self._last_index_call is not None:
                delay = self.min_interval_seconds - (time.perf_counter() - self._last_index_call)
                if delay > 0:
                    time.sleep(delay)
            self._last_index_call = time.perf_counter()
            output.extend(super()._embed(texts[start:start+self.batch_size], task))
        return output


class MeasuredAnswerModel(GeminiAnswerModel):
    def __init__(self, recorder, config, payloads):
        super().__init__(config["answer_model"], timeout_ms=config["execution"]["provider_timeout_ms"])
        self.recorder, self.config, self.payloads = recorder, config, payloads
        self._client = recorder.client(self.timeout_ms)

    def _call(self, policy, payload, schema):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.payloads.append({"stage": self.recorder.stage, "payload_sha256": hashlib.sha256(body).hexdigest(),
                              "payload_utf8_bytes": len(body), "policy_sha256": digest(policy),
                              "candidate_count": len(payload.get("candidates", payload.get("chunks", []))),
                              "relation_count": len(payload.get("relations", []))})
        if len(body) > self.config["generation"]["max_payload_utf8_bytes"]:
            raise ValueError("Benchmark common context budget exceeded; input not truncated")
        return super()._call(policy, payload, schema)

    def draft(self, payload):
        with self.recorder.at("answer_generation"):
            return super().draft(payload)

    def verify(self, payload):
        with self.recorder.at("answer_verification"):
            return super().verify(payload)
