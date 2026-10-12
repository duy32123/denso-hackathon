"""parse_vtt turns an official YouTube caption file into the utterance rows the
D1-A transcripts use. The golden case is SRC_HAAS_0005, whose raw.json was
produced from this exact caption file, so the converter must reproduce it."""
import json
from pathlib import Path

from acquisition.preprocessing.captions import parse_vtt, raw_text, sha256_text

ROOT = Path(__file__).resolve().parents[2]
VTT = (Path(__file__).parent / "fixtures" / "cs-BvWsKXyU.en.vtt").read_text(encoding="utf-8")


def test_reproduces_the_existing_src_haas_0005_transcript():
    golden = json.loads(
        (ROOT / "acquisition/preprocessing/transcripts/SRC_HAAS_0005/raw.json").read_text(encoding="utf-8")
    )
    assert parse_vtt(VTT) == golden["utterances"]


def test_joins_wrapped_lines_and_drops_nbsp_padding():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nhello&nbsp;\nthere&nbsp;&nbsp;\n"
    assert parse_vtt(vtt) == [{"start_ms": 1000, "end_ms": 2500, "text": "hello there"}]


def test_unescapes_html_entities():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nR&amp;D &lt;fast&gt;\n"
    assert parse_vtt(vtt)[0]["text"] == "R&D <fast>"


def test_skips_cues_with_no_text():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n&nbsp;\n\n00:00:02.000 --> 00:00:03.000\nok\n"
    assert [u["text"] for u in parse_vtt(vtt)] == ["ok"]


def _source(source_id):
    lines = (ROOT / "data/sources/haas_pilot_sources.jsonl").read_text(encoding="utf-8").splitlines()
    return next(r for r in map(json.loads, lines) if r["source_id"] == source_id)


def test_raw_text_is_the_cue_texts_joined_by_a_space():
    rec = _source("SRC_HAAS_0005")
    assert raw_text(parse_vtt(VTT)) == rec["raw_text"]


def test_sha256_text_follows_the_convention_the_document_sources_already_obey():
    rec = _source("SRC_HAAS_0002")
    assert sha256_text(rec["raw_text"]) == rec["content_sha256"]
