"""BM25, cosine and reciprocal rank fusion on an already-filtered candidate set."""

import math
import re
import unicodedata
from collections import Counter

TOKENIZER_VERSION = "unicode-fold-1"
STOPWORDS = set("a an the is are of to for and or how what why when do does i you can "
                "la va cua cho toi cac nhung mot nhu nao gi tai sao khi co duoc voi de".split())


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
                   if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    # Preserve numbers, negation, and codes like VF-2; do not stem technical units.
    return [t for t in re.findall(r"[^\W_]+(?:[-_\.][^\W_]+)*", fold(text)) if t not in STOPWORDS]


def bm25(query: str, documents: dict[str, list[str]], k1: float = 1.2, b: float = .75) -> dict[str, float]:
    if not documents:
        return {}
    terms = set(tokens(query))
    lengths = {key: len(words) for key, words in documents.items()}
    average = sum(lengths.values()) / len(documents) or 1
    frequencies = {key: Counter(words) for key, words in documents.items()}
    df = Counter(term for freq in frequencies.values() for term in freq if term in terms)
    result = {}
    for key, freq in frequencies.items():
        score = 0.0
        for term in terms:
            tf = freq[term]
            if tf:
                idf = math.log(1 + (len(documents) - df[term] + .5) / (df[term] + .5))
                score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * lengths[key] / average))
        if score > 0:
            result[key] = score
    return result


def ordered(scores: dict[str, float], limit: int) -> list[str]:
    return sorted(scores, key=lambda key: (-scores[key], key))[:limit]


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(dict.fromkeys(ranking), start=1):
            scores[key] = scores.get(key, 0) + 1 / (k + rank)
    return scores


def rank(query: str, docs: list[dict], query_vector: list[float] | None, *,
         strategy: str, candidate_k: int, min_cosine: float, rrf_k: int) -> list[dict]:
    lexical = bm25(query, {d["id"]: d["tokens"] for d in docs}) if strategy != "vector" else {}
    dense = {}
    if strategy != "lexical":
        if query_vector is None:
            raise ValueError("Vector/hybrid requires a query embedding")
        for doc in docs:
            values = doc["vector"]
            if values is None or len(values) != len(query_vector):
                raise ValueError("Missing/incompatible indexed vector; rebuild index")
            cosine = sum(a * b for a, b in zip(values, query_vector, strict=True))
            if cosine >= min_cosine:
                dense[doc["id"]] = cosine
    lex_order, vec_order = ordered(lexical, candidate_k), ordered(dense, candidate_k)
    if strategy == "hybrid":
        combined = rrf([lex_order, vec_order], rrf_k)
    elif strategy == "lexical":
        combined = {key: lexical[key] for key in lex_order}
    else:
        combined = {key: dense[key] for key in vec_order}
    lookup = {d["id"]: d for d in docs}
    return [{"doc": lookup[key], "score": combined[key],
             "lexical_score": lexical.get(key), "vector_score": dense.get(key)}
            for key in ordered(combined, len(combined))]
