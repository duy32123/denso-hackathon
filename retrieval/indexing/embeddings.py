"""Multilingual dense embeddings; no lexical/hash-vector fallback."""

from __future__ import annotations

import math
import os
import re
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Protocol


class EmbeddingError(ValueError):
    pass


RATE_LIMIT_WAITED = {"seconds": 0.0}  # lets callers exclude back-off time from measured API time


def retry_rate_limited(call, *, retries: int = 3, max_wait: float = 65.0, sleep=time.sleep):
    """Retry only HTTP 429 (per-minute rate limit), waiting the server's retryDelay.

    Any other error, or a requested wait above max_wait (a daily quota), is raised at once.
    """
    for attempt in range(retries + 1):
        try:
            return call()
        except Exception as exc:
            if getattr(exc, "code", None) != 429 or attempt == retries:
                raise
            match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", str(exc))
            wait = float(match.group(1)) + 1 if match else min(max_wait, 5.0 * 2 ** attempt)
            if wait > max_wait:
                raise
            print(f"Gemini rate limit (429); retrying in {wait:.0f}s", file=sys.stderr)
            RATE_LIMIT_WAITED["seconds"] += wait
            sleep(wait)


class Embedder(Protocol):
    @property
    def config(self) -> dict: ...
    def documents(self, texts: list[str]) -> list[list[float]]: ...
    def query(self, text: str) -> list[float]: ...


def unit_vector(values: list[float], dimensions: int) -> list[float]:
    if len(values) != dimensions or not all(math.isfinite(v) for v in values):
        raise EmbeddingError("Embedding has invalid dimensions or non-finite values")
    norm = math.sqrt(sum(v * v for v in values))
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingError("Embedding has zero/invalid norm")
    return [v / norm for v in values]


class GeminiEmbedder:
    """Embeddings 1 task types; weights are hosted, output vectors are retained.

    Long documents use bounded chunks and a length-weighted mean of unit vectors.
    No source text is discarded locally. UTF-8 byte bounds keep chunks below the
    model's input limit; Developer API does not accept the Vertex auto_truncate flag.
    """

    def __init__(self, dimensions: int = 768):
        if dimensions not in (768, 1536, 3072):
            raise EmbeddingError("Choose 768, 1536 or 3072 dimensions")
        self.dimensions = dimensions
        self._client = None
        self.calls = 0

    @property
    def config(self) -> dict:
        return {
            "provider": "gemini", "model": "gemini-embedding-001",
            "version": "gemini-embedding-001", "dimensions": self.dimensions,
            "adapter_version": "2", "sdk_version": version("google-genai"),
            "document_task": "RETRIEVAL_DOCUMENT", "query_task": "RETRIEVAL_QUERY",
            "chunk_utf8_bytes": 1800, "aggregation": "length-weighted-unit-mean",
        }

    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types

        if not texts:
            return []
        if self._client is None:
            load_dotenv(Path(__file__).resolve().parents[2] / ".env")
            key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not key:
                raise EmbeddingError("Set GEMINI_API_KEY in .env to build/query dense embeddings")
            self._client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))
        vectors = []
        for start in range(0, len(texts), 32):
            batch = texts[start:start + 32]
            try:
                response = retry_rate_limited(lambda: self._client.models.embed_content(
                    model=self.config["model"], contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task, output_dimensionality=self.dimensions,
                    ),
                ))
                self.calls += 1
            except Exception as exc:
                # SDK exception strings may contain request URLs/credentials.
                code = getattr(exc, "code", None)
                raise EmbeddingError(
                    f"Gemini embedding request failed ({type(exc).__name__}, code={code}); "
                    "check network, API key, model access or quota. No fallback was used."
                ) from None
            rows = response.embeddings or []
            if len(rows) != len(batch):
                raise EmbeddingError("Gemini returned a different embedding count")
            vectors.extend(unit_vector(row.values or [], self.dimensions) for row in rows)
        return vectors

    def documents(self, texts: list[str]) -> list[list[float]]:
        chunks = [chunk_text(t) for t in texts]
        if any(not parts for parts in chunks):
            raise EmbeddingError("Cannot embed empty document")
        vectors = iter(self._embed([part for parts in chunks for part in parts], "RETRIEVAL_DOCUMENT"))
        result = []
        for parts in chunks:
            weighted = [0.0] * self.dimensions
            for part in parts:
                for i, value in enumerate(next(vectors)):
                    weighted[i] += len(part) * value
            result.append(unit_vector(weighted, self.dimensions))
        return result

    def query(self, text: str) -> list[float]:
        if not text.strip() or len(text.encode("utf-8")) > 1800:
            raise EmbeddingError("Query must be nonempty and at most 1800 UTF-8 bytes")
        return self._embed([text], "RETRIEVAL_QUERY")[0]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def chunk_text(text: str, max_bytes: int = 1800) -> list[str]:
    """Bound multilingual text by bytes without losing characters or whitespace."""
    parts, chars, size = [], [], 0
    for char in text:
        length = len(char.encode("utf-8"))
        if chars and size + length > max_bytes:
            parts.append("".join(chars))
            chars, size = [], 0
        chars.append(char)
        size += length
    if chars:
        parts.append("".join(chars))
    return parts
