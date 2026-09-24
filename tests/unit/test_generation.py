"""Offline WP3 policy tests. Stub model verdicts are NOT quality measurements."""

import copy

import pytest

from conftest import FIXTURE_ROOT, REPO_ROOT
from knowflow_contracts.models import QueryContext, QueryRequest
from retrieval.generation.engine import generate_answer
from retrieval.generation.evidence import EvidenceAccess, external_url
from retrieval.generation.models import AnswerDraft, GenerationError, Verification
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import RetrievalError, build_index, read_corpus
from retrieval.retrieval.engine import RetrievalConfig, retrieve


class StubModel:
    def __init__(self, transform=None, verification=None):
        self.transform, self.verification = transform, verification
        self.calls = []

    def draft(self, payload):
        self.calls.append(("draft", payload))
        item = payload["candidates"][0]
        draft = {"status": "answered", "statements": [{"text": item["claim"]["text"],
                 "claim_ref": copy.deepcopy(item["claim_ref"]),
                 "evidence_ids": [item["evidence"][0]["evidence"]["evidence_id"]]}]}
        if self.transform:
            self.transform(draft)
        return AnswerDraft.model_validate(draft)

    def verify(self, payload):
        self.calls.append(("verify", payload))
        return self.verification or Verification(answers_question=True, supported=[True] * len(payload["statements"]))

    def close(self):
        pass


@pytest.fixture
def prepared(tmp_path):
    db = tmp_path / "kb.sqlite"
    import_bundle(FIXTURE_ROOT / "F01_complete", db, source_type="synthetic", split="dev")
    build_index(db, mode="synthetic", split="dev")
    request = QueryRequest(question="Cách tháo nắp che?", context=QueryContext(machine_model="DEMO_TC_A"),
                           mode="synthetic", dataset_split="dev")
    result = retrieve(db, request, config=RetrievalConfig(strategy="lexical"))
    assert result["status"] == "retrieved"
    return request, result, read_corpus(db, "synthetic", "dev")


def generate(prepared, model=None, access=None):
    return generate_answer(*prepared, model=model or StubModel(), access=access or EvidenceAccess(REPO_ROOT))


def test_canonical_citation_and_original_language(prepared):
    before = copy.deepcopy(prepared[1])
    model = StubModel()
    answer = generate(prepared, model)
    assert answer.status == "answered" and "Dữ liệu mô phỏng" in answer.answer
    citation = answer.citations[0]
    item = prepared[1]["claims"][0]
    assert citation.claim_ref.model_dump() == item["claim_ref"]
    assert citation.answer_span in answer.answer
    assert citation.source_review == item["claim"]["source_review"] == "pending"
    assert citation.technical_review == item["claim"]["technical_review"]
    assert before == prepared[1]  # no canonical text, review or package mutation
    assert [name for name, _ in model.calls] == ["draft", "verify"]


@pytest.mark.parametrize("field,value", [
    ("workflow_id", "OTHER_WF"), ("revision", 999), ("entity_type", "step"), ("entity_id", "invented"),
])
def test_forged_claim_reference_rejected(prepared, field, value):
    model = StubModel(lambda draft: draft["statements"][0]["claim_ref"].update({field: value}))
    answer = generate(prepared, model)
    assert answer.status == "insufficient_evidence" and not answer.citations
    assert len(model.calls) == 1  # code rejects before the semantic judge


@pytest.mark.parametrize("change", [
    lambda d: d["statements"][0].update(evidence_ids=["invented"]),
    lambda d: d["statements"][0].update(evidence_ids=[]),
    lambda d: d["statements"][0].update(source_review="expert_validated"),
    lambda d: d["statements"][0].update(text=" "),
    lambda d: d["statements"][0].update(text="Tighten to 999 Nm."),
    lambda d: d.update(statements=[]),
])
def test_invalid_draft_fails_closed(prepared, change):
    answer = generate(prepared, StubModel(change))
    assert answer.status == "insufficient_evidence" and answer.citations == []


def test_an_evidence_id_not_linked_to_the_claim_fails_closed(prepared):
    """A stray id is not noise: on real/dev it was the evidence for extra content the model had merged into a
    one-claim statement (a 'press E-stop' sentence cited to a claim that never mentions the E-stop). Dropping
    the id kept the sentence and lost its support, and the verifier, which only sees what is left, passed it."""
    model = StubModel(lambda d: d["statements"][0].update(
        evidence_ids=d["statements"][0]["evidence_ids"] + ["invented"]))
    answer = generate(prepared, model)
    assert answer.status == "insufficient_evidence" and not answer.citations
    assert [name for name, _ in model.calls] == ["draft"]  # rejected by code before the semantic judge


def test_duplicate_evidence_ids_still_fail_closed(prepared):
    answer = generate(prepared, StubModel(lambda d: d["statements"][0].update(
        evidence_ids=d["statements"][0]["evidence_ids"] * 2)))
    assert answer.status == "insufficient_evidence" and not answer.citations


@pytest.mark.parametrize("verification", [
    Verification(answers_question=False, supported=[True]),
    Verification(answers_question=True, supported=[False]),
    Verification(answers_question=True, supported=[]),
    Verification(answers_question=True, supported=[True, True]),
])
def test_semantic_failure_or_wrong_verdict_count_rejects_entire_answer(prepared, verification):
    answer = generate(prepared, StubModel(verification=verification))
    assert answer.status == "insufficient_evidence" and not answer.citations
    assert answer.unresolved_claim_refs


@pytest.mark.parametrize("status", ["needs_clarification", "insufficient_evidence", "conflicting_sources"])
def test_retrieval_gate_never_calls_model(prepared, status):
    request, result, corpus = prepared
    result["status"] = status
    result["missing_context"] = ["machine_model"] if status == "needs_clarification" else []
    if status == "conflicting_sources":
        result["conflicts"] = result["claims"][:1]
    model = StubModel()
    answer = generate(prepared, model)
    assert answer.status == status and not answer.citations and not model.calls
    assert answer.missing_context == result["missing_context"]
    assert bool(answer.unresolved_claim_refs) == (status == "conflicting_sources")


def test_missing_assets_abstain_before_model(prepared):
    class Unavailable:
        def view(self, *_):
            from retrieval.generation.evidence import EvidenceView
            return EvidenceView(False, "unavailable")

    model = StubModel()
    answer = generate(prepared, model, Unavailable())
    assert answer.status == "insufficient_evidence" and answer.unresolved_claim_refs and not model.calls


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(source_type="real"),
    lambda r: r.update(dataset_split="holdout"),
    lambda r: r.update(index_build_id="stale"),
    lambda r: r.update(record_build_id="stale"),
    lambda r: r["claims"][0]["claim"].update(text="forged canonical claim"),
    lambda r: r["claims"][0]["claim_ref"].update(revision=2),
])
def test_untrusted_or_stale_package_rejected(prepared, mutate):
    mutate(prepared[1])
    with pytest.raises(RetrievalError):
        generate(prepared)


def test_procedure_with_gaps_abstains(prepared):
    prepared[1]["trace"].update(intent="procedure", omitted_step_ids=["missing_step"])
    model = StubModel()
    assert generate(prepared, model).status == "insufficient_evidence"
    assert model.calls == []


def test_partial_procedure_not_presented_as_complete(prepared):
    prepared[1]["trace"]["intent"] = "procedure"
    prepared[1]["steps"].append({"step_id": "uncovered"})
    model = StubModel()
    assert generate(prepared, model).status == "insufficient_evidence"
    assert len(model.calls) == 1


def test_real_retained_caption_is_not_live_video(tmp_path):
    db = tmp_path / "real.sqlite"
    import_bundle(REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle", db, source_type="real", split="dev")
    build_index(db, mode="real", split="dev")
    req = QueryRequest(question="How is the pocket slider lubricated?", context=QueryContext(), mode="real", dataset_split="dev")
    result = retrieve(db, req, config=RetrievalConfig(strategy="lexical"))
    model = StubModel()
    answer = generate_answer(req, result, read_corpus(db, "real", "dev"), model=model, access=EvidenceAccess(REPO_ROOT))
    assert answer.status == "answered"
    assert "According to the source (not technically validated)" in answer.answer
    assert all(c.source_review == "source_checked" for c in answer.citations)
    candidate = model.calls[0][1]["candidates"][0]
    assert candidate["evidence"][0]["access_kind"] == "retained_transcript"
    assert candidate["claim"]["text"] in answer.answer


@pytest.mark.parametrize("uri", ["../../.env", ".env", "C:/secret.jpg", "https://example.com/image.jpg", "//server/secret.jpg"])
def test_asset_path_escape_and_remote_fetch_forbidden(tmp_path, uri):
    assert not EvidenceAccess(tmp_path)._image(uri).available


def test_asset_file_must_decode_and_stay_in_keyframe_root(tmp_path):
    from PIL import Image
    root = tmp_path / "acquisition/preprocessing/keyframes"
    root.mkdir(parents=True)
    asset = root / "test.jpg"
    asset.write_text("not an image", encoding="utf-8")
    access = EvidenceAccess(tmp_path)
    uri = asset.relative_to(tmp_path).as_posix()
    assert not access._image(uri).available
    asset.write_bytes(b"\xff\xd8\xff" + b"test-image")
    assert not access._image(uri).available
    Image.new("RGB", (16, 16)).save(asset)
    assert access._image(uri).available
    assert access._image(uri).media_type == "image/jpeg"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///secret", "https://user:secret@example.com", "http://example.com"])
def test_unsafe_external_urls_not_displayed(url):
    assert external_url(url) is None


def test_retained_text_must_actually_contain_quote(prepared):
    corpus = prepared[2]
    wf = next(iter(corpus["workflows"].values()))
    ev = next(e for e in wf.evidence if e.quote)
    src = corpus["sources"][ev.source_id].model_copy(update={"source_type": "real"})
    ev = ev.model_copy(update={"transcript_origin": "official_caption"})
    assert not EvidenceAccess(REPO_ROOT).view(ev, src).available
    src = src.model_copy(update={"raw_text": ev.quote})
    assert EvidenceAccess(REPO_ROOT).view(ev, src).available


CORRECTED = "so your tool changer s alarm down"


def corrected_case(prepared, tmp_path, *, origin="human", source_id=None, transcript_id=None,
                   utterances=None, write=True):
    """A speech quote that exists only in the human-corrected transcript, not in Source.raw_text."""
    corpus = prepared[2]
    wf = next(iter(corpus["workflows"].values()))
    ev = next(e for e in wf.evidence if e.quote)
    src = corpus["sources"][ev.source_id].model_copy(update={
        "source_type": "real", "raw_text": "so your tool changes alarm down", "duration_ms": 60_000})
    sid = source_id or ev.source_id
    src = src.model_copy(update={"source_id": sid})
    ev = ev.model_copy(update={
        "source_id": sid, "modality": "speech", "transcript_origin": origin, "quote": CORRECTED,
        "locator": ev.locator.model_copy(update={"start_ms": 1000, "end_ms": 5000, "page": None, "text_span": None})})
    if write:
        import json
        folder = tmp_path / "acquisition/preprocessing/transcripts" / sid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "corrected.json").write_text(json.dumps({
            "source_id": transcript_id or sid, "utterances": utterances or [
                {"start_ms": 0, "end_ms": 6000, "text": "So your tool changer's alarm down"},
                {"start_ms": 50_000, "end_ms": 60_000, "text": "unrelated closing words"}]}), encoding="utf-8")
    return EvidenceAccess(tmp_path), ev, src


def test_human_corrected_quote_opens_from_the_retained_corrected_transcript(prepared, tmp_path):
    access, ev, src = corrected_case(prepared, tmp_path)
    view = access.view(ev, src)
    assert view.available and view.kind == "retained_transcript"


@pytest.mark.parametrize("case", [
    {"origin": "official_caption"},                                   # only human-origin quotes may differ
    {"origin": "asr"},
    {"utterances": [{"start_ms": 50_000, "end_ms": 60_000, "text": "So your tool changer's alarm down"}]},
    {"write": False},                                                 # no retained corrected transcript
    {"transcript_id": "SRC_OTHER"},                                   # transcript belongs to another source
])
def test_corrected_quote_fails_closed_unless_the_retained_transcript_proves_it(prepared, tmp_path, case):
    access, ev, src = corrected_case(prepared, tmp_path, **case)
    assert not access.view(ev, src).available


@pytest.mark.parametrize("source_id", ["..", "../transcripts", "a/b", "a\\b", ""])
def test_corrected_transcript_lookup_cannot_leave_its_root(prepared, tmp_path, source_id):
    access, ev, src = corrected_case(prepared, tmp_path, write=False)
    ev, src = ev.model_copy(update={"source_id": source_id}), src.model_copy(update={"source_id": source_id})
    import json
    (tmp_path / "acquisition/preprocessing").mkdir(parents=True, exist_ok=True)
    (tmp_path / "acquisition/preprocessing/corrected.json").write_text(json.dumps({
        "source_id": source_id, "utterances": [{"start_ms": 0, "end_ms": 6000, "text": CORRECTED}]}), encoding="utf-8")
    assert not access.view(ev, src).available


def test_provider_failure_not_mislabeled_as_no_evidence(prepared):
    class Offline(StubModel):
        def draft(self, payload):
            raise GenerationError("provider unavailable")
    with pytest.raises(GenerationError):
        generate(prepared, Offline())


@pytest.mark.parametrize("question,expected", [
    ("Cách tháo nắp che?", "vi"),
    ("cach thao nap che nhu the nao", "vi"),     # tieng Viet khong dau
    ("How is the cover removed?", "en"),
])
def test_answer_language_is_decided_by_code_and_sent_to_both_calls(prepared, question, expected):
    """Ca luot soan lan luot kiem nhan CUNG mot answer_language do code tinh.

    Truoc day moi luot tu doan tu cau hoi: cau hoi tieng Viet tren evidence tieng Anh thi
    luot soan viet tieng Anh, luot kiem bat sai ngon ngu va vut ca cau tra loi dung.
    """
    request, result, corpus = prepared
    model = StubModel()
    generate_answer(request.model_copy(update={"question": question}), result, corpus,
                    model=model, access=EvidenceAccess(REPO_ROOT))
    calls = dict(model.calls)
    assert calls["draft"]["answer_language"] == expected
    assert calls["verify"]["answer_language"] == expected


def test_prompts_name_the_supplied_language_instead_of_guessing():
    from retrieval.generation.gemini import DRAFT_POLICY, PROMPT_VERSION, VERIFY_POLICY

    assert "answer_language" in DRAFT_POLICY and "answer_language" in VERIFY_POLICY
    assert "language of the question" not in DRAFT_POLICY
    # Cau truc prompt doi thi verdict cu cua nguoi kiem khong con dung cho cau tra loi moi.
    assert PROMPT_VERSION == "grounded-qa-3"


def test_verifier_sees_the_answer_text_in_order_and_each_statements_steps(prepared):
    """Luot kiem phai thay dung cau tra loi nguoi dung doc, khong chi cac muc roi rac.

    Thieu `answer`, Gemini hay tra answers_question=false cho quy trinh day du, dung thu
    tu, moi cau supported ("khong co cau tra loi de kiem"). `step_ids` de no doi chieu
    duoc do phu va thu tu buoc ma code da chung minh.
    """
    request, result, corpus = prepared
    model = StubModel()
    answer = generate_answer(request, result, corpus, model=model, access=EvidenceAccess(REPO_ROOT))
    verify = dict(model.calls)["verify"]
    assert verify["answer"] == [c.answer_span for c in answer.citations]
    assert [s["statement"]["text"].strip() for s in verify["statements"]] == verify["answer"]
    item = next(c for c in result["claims"] if c["claim_ref"] == verify["statements"][0]["statement"]["claim_ref"])
    assert verify["statements"][0]["step_ids"] == item["matched_step_ids"]
    # Khong mo rong ra claim khong duoc cite (engine.py: khong cuu citation sai bang claim lan can).
    assert "candidates" not in verify


@pytest.fixture
def procedure(tmp_path):
    db = tmp_path / "kb.sqlite"
    import_bundle(FIXTURE_ROOT / "F01_complete", db, source_type="synthetic", split="dev")
    build_index(db, mode="synthetic", split="dev")
    request = QueryRequest(question="Quy trình tháo nắp che gồm những bước nào?",
                           context=QueryContext(machine_model="DEMO_TC_A"), mode="synthetic", dataset_split="dev")
    result = retrieve(db, request, config=RetrievalConfig(strategy="lexical"))
    assert result["status"] == "retrieved" and result["trace"]["intent"] == "procedure"
    return request, result, read_corpus(db, "synthetic", "dev")


def one_claim_per_step(payload, reverse):
    """Draft mot statement cho moi Step, theo display_order hoac nguoc lai."""
    by_step = {}
    for item in payload["candidates"]:
        if len(item["matched_step_ids"]) == 1:
            by_step.setdefault(item["matched_step_ids"][0], item)
    steps = sorted(payload["steps"], key=lambda s: s["display_order"], reverse=reverse)
    return {"status": "answered", "statements": [
        {"text": by_step[s["step_id"]]["claim"]["text"], "claim_ref": copy.deepcopy(by_step[s["step_id"]]["claim_ref"]),
         "evidence_ids": [by_step[s["step_id"]]["evidence"][0]["evidence"]["evidence_id"]]} for s in steps]}


@pytest.mark.parametrize("reverse,expected", [(False, "answered"), (True, "insufficient_evidence")])
def test_procedure_order_is_proved_by_code_not_left_to_the_verifier(procedure, reverse, expected):
    """Luot kiem cua Gemini de lot quy trinh dao nguoc; code phai chan truoc khi goi no."""
    class Model(StubModel):
        def draft(self, payload):
            self.calls.append(("draft", payload))
            return AnswerDraft.model_validate(one_claim_per_step(payload, reverse))

    model = Model()   # verify cua stub luon noi "dung": neu chan duoc thi la do code
    answer = generate(procedure, model)
    assert answer.status == expected
    assert [name for name, _ in model.calls] == (["draft", "verify"] if not reverse else ["draft"])
