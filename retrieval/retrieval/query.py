"""Query preparation for lexical search and the relevance gate.

Translation lets a Vietnamese question SEARCH an English corpus; answers and citations
always come from the original snapshot (contract D-03). The corpus-wide IDF coverage
function is retained as a diagnostic/legacy baseline. The default claim-coherence
prefilter lives in relevance.py and requires terms to occur together in eligible content.
"""

from __future__ import annotations

import math
import os
import re
import unicodedata
from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

from retrieval.indexing.embeddings import retry_rate_limited
from .ranking import stem_word, tokens

# Question scaffolding and function words: they say how a question is asked, not what about.
QUESTION_WORDS = set(
    "should must need needs would could will shall it they them we my your our its this that these those "
    "there whether "
    "which where who whom on in at by from into onto as be been being was were has have had if then with "
    "after before about use used using like way properly correctly step steps procedure".split())
VI_LETTERS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")
# Frequent Vietnamese words that stay recognisable without diacritics and are not English.
VI_MARKERS = set("cach nhu nao khi cua cho khong bang tren trong duoc phai lam thay thao lap gi sao nen".split())
PROMPT = ("Translate the question into English for keyword search in an English maintenance manual "
          "for CNC machine tools. It may be Vietnamese typed without diacritics. Use standard CNC "
          "terms: 'dao' is a cutting tool (not a knife), 'hốc dao' is a tool pocket, 'trục chính' is "
          "the spindle. 'con trượt hốc dao' or 'con truot hoc dao' is the pocket slider, "
          "not a linear guide, way-cover rail, magazine guideway, or double-arm slider. "
          "Keep the requested component identity distinct. Keep numbers, model names and codes unchanged. Do not answer and do not add "
          "information. Output only the translation.\n\nQuestion: ")


class TranslationError(ValueError):
    pass


class Translator(Protocol):
    @property
    def config(self) -> dict: ...
    def to_english(self, text: str) -> str: ...


def looks_vietnamese(text: str) -> bool:
    lowered = unicodedata.normalize("NFC", text).casefold()
    if any(char in VI_LETTERS for char in lowered):
        return True
    return len(set(re.findall(r"[a-z]+", lowered)) & VI_MARKERS) >= 2


def content_terms(text: str, *, stem: bool = False) -> list[str]:
    terms = (t for t in tokens(text) if t not in QUESTION_WORDS)
    return list(dict.fromkeys(stem_word(t) if stem else t for t in terms))


def term_coverage(terms: list[str], docs: list[dict]) -> tuple[float, list[str]]:
    """IDF-weighted share of query terms found in the eligible corpus; rare terms weigh more."""
    if not terms:
        return 1.0, []
    df = Counter(t for doc in docs for t in set(doc["tokens"]))
    weight = {t: math.log(1 + (len(docs) - df[t] + .5) / (df[t] + .5)) for t in terms}
    return sum(w for t, w in weight.items() if df[t]) / sum(weight.values()), [t for t in terms if not df[t]]


class GeminiTranslator:
    """Vietnamese (with or without diacritics) to English, for lexical search only."""

    def __init__(self, model: str = "gemini-3.5-flash-lite"):
        self.model, self._client, self.calls = model, None, 0

    @property
    def config(self) -> dict:
        try:
            sdk = version("google-genai")
        except PackageNotFoundError:
            sdk = "not-installed"
        return {"provider": "gemini", "model": self.model, "prompt_version": "q2en-3",
                "temperature": 0, "sdk_version": sdk}

    def to_english(self, text: str) -> str:
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types

        if self._client is None:
            load_dotenv(Path(__file__).resolve().parents[2] / ".env")
            key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not key:
                raise TranslationError("Set GEMINI_API_KEY in .env to translate Vietnamese queries, "
                                       "or use --query-translation never")
            self._client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))
        try:
            response = retry_rate_limited(lambda: self._client.models.generate_content(
                model=self.model, contents=PROMPT + text,
                config=types.GenerateContentConfig(
                    temperature=0,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)),
            ))
            self.calls += 1
        except Exception as exc:
            # SDK exception strings may contain request URLs/credentials.
            raise TranslationError(
                f"Gemini translation failed ({type(exc).__name__}, code={getattr(exc, 'code', None)}); "
                "no fallback was used."
            ) from None
        english = (response.text or "").strip()
        if not english:
            raise TranslationError("Gemini returned an empty translation")
        return english

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
