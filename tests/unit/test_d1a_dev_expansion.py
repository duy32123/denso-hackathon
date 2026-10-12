"""The five dev sources added after the D1-A pilot (SRC_HAAS_0008..0012).

Every link in the chain has to agree: catalog row -> registry -> Source record ->
split manifest -> transcript -> media inventory -> published workflow -> rights
register. YouTube video ids are case-sensitive (SRC_HAAS_0003 was once stored in
lower case and its link died), so each URL is compared to the id character by
character.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

import pytest

from acquisition.preprocessing.captions import raw_text, sha256_text
from acquisition.validation.validate_d1a_extra import check_transcript_bounds

ROOT = Path(__file__).resolve().parents[2]
NEW = {
    "SRC_HAAS_0008": "DXtocZX8hf0",
    "SRC_HAAS_0009": "cwYsbzAW3r0",
    "SRC_HAAS_0010": "M-VcwEodqP0",
    "SRC_HAAS_0011": "DgHQtvvf1kI",
    "SRC_HAAS_0012": "ezplV3447C8",
}
BASIS = {"source", "curated", "unknown"}


def _jsonl(rel):
    return [json.loads(l) for l in (ROOT / rel).read_text(encoding="utf-8").splitlines() if l.strip()]


def _sources():
    return {r["source_id"]: r for r in _jsonl("data/sources/haas_pilot_sources.jsonl")}


@pytest.mark.parametrize("sid,yt", NEW.items())
def test_source_record_points_at_the_exact_video(sid, yt):
    rec = _sources()[sid]
    assert rec["url"] == f"https://www.haascnc.com/video/service/{yt}.html"
    assert f"https://www.youtube.com/watch?v={yt}" in rec["access_note"]
    assert rec["source_kind"] == "official_service_video"
    assert rec["publisher"] == "Haas Automation, Inc."
    assert rec["asset_uri"] is None


@pytest.mark.parametrize("sid,yt", NEW.items())
def test_registry_allocated_the_id_for_that_url(sid, yt):
    reg = json.loads((ROOT / "data/catalogs/haas_d1a_source_id_registry.json").read_text(encoding="utf-8"))
    assert reg["urls"][f"https://www.haascnc.com/video/service/{yt}.html"] == sid
    assert reg["next_seq"] > int(sid[-4:])


def test_each_new_source_sits_in_a_dev_family_and_never_in_holdout():
    fams = json.loads((ROOT / "data/splits/haas_d1a_split_manifest.json").read_text(encoding="utf-8"))["families"]
    split_of = {sid: f["split"] for f in fams for sid in f["source_ids"]}
    for sid in NEW:
        assert split_of.get(sid) == "dev", sid
    for f in fams:
        assert f["why_family"] and f["why_no_cross_split"]


@pytest.mark.parametrize("sid", NEW)
def test_transcript_matches_the_source_record(sid):
    rec = _sources()[sid]
    raw_path = ROOT / f"acquisition/preprocessing/transcripts/{sid}/raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    assert raw["transcript_origin"] == "official_caption"
    assert check_transcript_bounds(str(raw_path), rec["duration_ms"]) == []
    assert rec["raw_text"] == raw_text(raw["utterances"])
    assert rec["content_sha256"] == sha256_text(rec["raw_text"])
    corrected = json.loads((ROOT / f"acquisition/preprocessing/transcripts/{sid}/corrected.json").read_text(encoding="utf-8"))
    assert [(u["start_ms"], u["end_ms"]) for u in corrected["utterances"]] == [
        (u["start_ms"], u["end_ms"]) for u in raw["utterances"]
    ]
    assert (ROOT / f"acquisition/preprocessing/transcripts/{sid}/corrections.diff").is_file()


@pytest.mark.parametrize("sid,yt", NEW.items())
def test_catalog_row_records_the_basis_of_every_field(sid, yt):
    rows = list(csv.DictReader((ROOT / "acquisition/video_catalog/haas_d1a_source_candidates.csv").open(encoding="utf-8")))
    (row,) = [r for r in rows if r["source_id"] == sid]
    assert row["canonical_url"].endswith(f"/{yt}.html")
    assert (row["proposed_split"], row["selection_status"]) == ("dev", "selected")
    assert row["caption_status"] == "official manual English caption"
    for key, value in row.items():
        if key.endswith("_basis"):
            assert value in BASIS, f"{key}={value!r}"
    assert re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"])
    assert row["near_duplicate_group"].startswith("FAM-")


@pytest.mark.parametrize("sid", NEW)
def test_media_inventory_hashes_match_the_committed_files(sid):
    rows = [r for r in _jsonl("acquisition/preprocessing/haas_d1a_media_inventory.jsonl") if r["source_id"] == sid]
    kinds = [r["artifact_type"] for r in rows]
    assert kinds.count("transcript_raw") == 1 and kinds.count("transcript_corrected") == 1
    assert kinds.count("keyframe") >= 3
    for r in rows:
        if r["artifact_type"] in ("transcript_raw", "transcript_corrected", "keyframe"):
            data = (ROOT / r["storage_uri"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == r["content_sha256"], r["artifact_id"]


@pytest.mark.parametrize("sid", NEW)
def test_every_new_source_is_cited_by_a_published_dev_workflow(sid):
    cited = set()
    for p in (ROOT / "data/workflows/dev").glob("*.json"):
        cited.update(json.loads(p.read_text(encoding="utf-8"))["source_ids"])
    assert sid in cited


@pytest.mark.parametrize("sid", NEW)
def test_dev_bundle_carries_the_source_and_the_rights_register_covers_it(sid):
    bundle_ids = {r["source_id"] for r in _jsonl("acquisition/export/haas_pilot_dev_bundle/sources.jsonl")}
    assert sid in bundle_ids
    assert sid in (ROOT / "docs/data_rights_register.md").read_text(encoding="utf-8")
