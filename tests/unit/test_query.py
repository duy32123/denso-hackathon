"""Query translation, relevance gate and relevance-bound conflicts. Stubs are NOT eval results."""

import pytest

from conftest import FIXTURE_ROOT, REPO_ROOT, read_bundle, write_bundle
from knowflow_contracts.models import QueryContext, QueryRequest
from retrieval.importer import import_bundle
from retrieval.indexing.embeddings import retry_rate_limited, unit_vector
from retrieval.indexing.search_index import build_index
from retrieval.retrieval.engine import RetrievalConfig, retrieve
from retrieval.retrieval.query import content_terms, looks_vietnamese, term_coverage
from retrieval.retrieval.ranking import tokens

REAL_BUNDLE = REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle"
GREASE_STEPS = {"B0_SRC_HAAS_0005_ST_006", "REAL_WF_0001_ST_007"}
VI_GREASE = "Bôi trơn con trượt của hốc dao như thế nào?"


class StubTranslator:
    __test__ = False
    config = {"provider": "test", "model": "table", "prompt_version": "1"}

    def __init__(self, table):
        self.table, self.calls = table, 0

    def to_english(self, text):
        self.calls += 1
        return self.table[text]


class CountingEmbedder:
    """dim0 = 'da', dim1 = 'den'/'bao' (weaker): F06's conflict step stays above
    min_cosine yet ranks below its assertable step."""
    __test__ = False
    config = {"provider": "test", "model": "counting", "version": "1", "dimensions": 3}

    def __init__(self):
        self.calls = 0

    def documents(self, texts):
        return [self._vector(text) for text in texts]

    def query(self, text):
        self.calls += 1
        return self._vector(text)

    def _vector(self, text):
        words = set(tokens(text))
        return unit_vector([2.0 if "da" in words else 0.0, .6 if words & {"den", "bao"} else 0.0, .05], 3)


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("real") / "store.sqlite"
    import_bundle(REAL_BUNDLE, db, source_type="real", split="dev")
    build_index(db, mode="real", split="dev")
    return db


def ask(db, question, *, mode="real", translator=None, embedder=None, **config):
    config = {"strategy": "lexical", "intent": "detail", **config}
    return retrieve(db, QueryRequest(question=question, context=QueryContext(), mode=mode, dataset_split="dev"),
                    config=RetrievalConfig(**config), translator=translator, embedder=embedder)


@pytest.mark.parametrize("text,expected", [
    (VI_GREASE, True),
    ("boi tron con truot hoc dao bang gi", True),   # no diacritics
    ("How do I lubricate the pocket slider?", False),
    ("Can I change the rapids?", False),
])
def test_vietnamese_detection(text, expected):
    assert looks_vietnamese(text) is expected


def test_english_stemming_matches_word_forms_but_keeps_codes():
    assert tokens("rotating rapids", stem=True) == tokens("rotate rapid", stem=True)
    assert tokens("VF-2 alarm 2066", stem=True)[::2] == ["vf-2", "2066"]
    assert tokens("thao nap", stem=False) == ["thao", "nap"]  # Vietnamese stays unstemmed
    assert content_terms("Is it rotating?", stem=True) == content_terms("rotate", stem=True)


def test_term_coverage_weights_rare_terms():
    docs = [{"tokens": ["pocket", "slider", "grease"]}, {"tokens": ["pocket", "bolt"]}]
    assert term_coverage(["pocket", "slider"], docs) == (1.0, [])
    coverage, unseen = term_coverage(["pocket", "coolant"], docs)
    assert unseen == ["coolant"] and coverage < .2  # the common term barely counts
    assert term_coverage([], docs) == (1.0, [])
    assert content_terms("What steps should I use for the pocket?") == ["pocket"]


def test_translated_vietnamese_question_searches_english_corpus(real_db):
    translator = StubTranslator({VI_GREASE: "How do I lubricate the pocket slider?"})
    result = ask(real_db, VI_GREASE, translator=translator)
    assert translator.calls == 1 and result["status"] == "retrieved"
    assert result["trace"]["query_translation"]["text"] == "How do I lubricate the pocket slider?"
    assert result["trace"]["relevance"]["gate"] == "passed"
    assert GREASE_STEPS & {step["step_id"] for step in result["steps"][:3]}
    # Claims are the original English snapshot text, never the translation.
    assert all(c["claim"]["text"] != "How do I lubricate the pocket slider?" for c in result["claims"])


def test_untranslated_vietnamese_question_skips_the_gate(real_db):
    result = ask(real_db, VI_GREASE)
    assert result["trace"]["query_translation"] is None
    assert result["trace"]["relevance"]["gate"] == "skipped"
    never = StubTranslator({VI_GREASE: "unused"})
    result = ask(real_db, VI_GREASE, translator=never, query_translation="never")
    assert never.calls == 0 and result["trace"]["relevance"]["gate"] == "skipped"


def test_out_of_scope_question_rejected_before_embedding(real_db):
    embedder = CountingEmbedder()
    result = ask(real_db, "How do I clean the chip conveyor?", strategy="vector", embedder=embedder)
    assert result["status"] == "insufficient_evidence" and result["claims"] == []
    assert result["trace"]["relevance"] == {"term_coverage": 0.0, "unseen_terms": ["clean", "chip", "conveyor"],
                                            "min_term_coverage": .10, "gate": "rejected"}
    assert embedder.calls == 0
    disabled = ask(real_db, "How do I clean the chip conveyor?", min_term_coverage=0)
    assert disabled["trace"]["relevance"]["gate"] == "passed"


class RateLimited(Exception):
    code = 429


class Denied(Exception):
    code = 403


def failing(errors, result="ok"):
    """A call that raises the given errors in turn, then returns result."""
    calls = []

    def call():
        calls.append(1)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return result
    return call, calls


def test_rate_limit_waits_the_server_delay_then_succeeds():
    call, calls = failing([RateLimited("{'retryDelay': '2s'}"), RateLimited("{'retryDelay': '2s'}")])
    waits = []
    assert retry_rate_limited(call, sleep=waits.append) == "ok"
    assert waits == [3.0, 3.0] and len(calls) == 3


@pytest.mark.parametrize("error", [Denied("forbidden"), RateLimited("{'retryDelay': '3600s'}")])
def test_other_errors_and_daily_quotas_are_not_retried(error):
    call, calls = failing([error])
    waits = []
    with pytest.raises(type(error)):
        retry_rate_limited(call, sleep=waits.append)
    assert waits == [] and len(calls) == 1


def test_conflict_is_reported_only_when_it_competes_for_top_k(tmp_path):
    embedder = CountingEmbedder()
    db = tmp_path / "store.sqlite"
    import_bundle(write_bundle(tmp_path / "bundle", read_bundle(FIXTURE_ROOT / "F06_conflict")), db,
                  source_type="synthetic", split="dev")
    build_index(db, mode="synthetic", split="dev", embedder=embedder)
    narrow = ask(db, "da reset cum den bao", mode="synthetic", strategy="vector", embedder=embedder, top_k=1)
    assert narrow["status"] == "retrieved" and narrow["conflicts"] == []
    wide = ask(db, "da reset cum den bao", mode="synthetic", strategy="vector", embedder=embedder, top_k=5)
    assert wide["status"] == "conflicting_sources" and len(wide["conflicts"]) == 2
