"""Offline regressions for saving, compiling, exporting and replaying B0 output."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from acquisition.extraction import compile_workflow as cw
from acquisition.extraction import exporter
from acquisition.extraction import extraction_pipeline as pipeline
from acquisition.extraction.schema_v1 import WorkflowBundle


@pytest.fixture
def response_data():
    return {
        "workflow_id": "B0_SRC_HAAS_0005",
        "source_ids": ["SRC_HAAS_0005"],
        "title": "Test tool changer",
        "steps": [{
            "step_id": "ST_001", "display_order": 1, "title": "Test operation",
            "fields": {"action": {"state": "present", "claims": [{
                "text": "Run several tool changes to check operation.",
                "role": "action", "evidence_type": "stated",
                "evidence": [["SRC_HAAS_0005:U0029", "SRC_HAAS_0005:U0031"]],
                "explanation": "Caption describes the test.",
            }]}},
        }],
    }


@pytest.fixture
def source_record():
    sources = pipeline.REPO_ROOT / "data/sources/haas_pilot_sources.jsonl"
    return next(record for record in map(json.loads, sources.read_text(encoding="utf-8").splitlines())
                if record["source_id"] == "SRC_HAAS_0005")


def stub_llm(monkeypatch, raw):
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return raw

    adapter = SimpleNamespace(model="offline-test-model", generate_structured_output=generate)
    monkeypatch.setattr(pipeline, "get_llm_adapter", lambda **kwargs: adapter)
    return calls


@pytest.mark.parametrize("relative", [True, False])
def test_pipeline_saves_compilable_draft_and_valid_bundle(tmp_path, monkeypatch, response_data, source_record, relative):
    raw = json.dumps(response_data, ensure_ascii=False)
    calls = stub_llm(monkeypatch, raw)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sources.jsonl").write_text(json.dumps(source_record) + "\n", encoding="utf-8")
    transcript = pipeline.REPO_ROOT / "acquisition/preprocessing/transcripts/SRC_HAAS_0005/corrected.json"
    (tmp_path / "corrected.json").write_bytes(transcript.read_bytes())
    base = Path(".") if relative else tmp_path
    output = base / "nested/result.draft.json"
    bundle_dir = base / "nested/bundle"
    pipeline.run_extraction_pipeline(
        transcript_path=base / "corrected.json", metadata_path=base / "sources.jsonl",
        output_path=output, bundle_dir=bundle_dir,
    )

    assert len(calls) == 1
    draft = json.loads(output.read_text(encoding="utf-8"))
    assert draft["steps"][0]["fields"]["action"]["claims"][0]["evidence"] == [
        ["SRC_HAAS_0005:U0029"], ["SRC_HAAS_0005:U0031"],
    ]
    snapshot = cw.compile_draft(draft)
    assert snapshot == json.loads((bundle_dir / "workflows.jsonl").read_text(encoding="utf-8"))
    assert len(snapshot["evidence"]) == 2
    assert {claim["source_review"] for claim in snapshot["claims"]} == {"pending"}
    assert {claim["technical_review"] for claim in snapshot["claims"]} == {"not_requested"}
    assert output.with_suffix(".raw.json").read_text(encoding="utf-8") == raw
    assert exporter.verify_bundle_integrity(bundle_dir)["valid"]
    lineage = json.loads((bundle_dir / "lineage.json").read_text(encoding="utf-8"))["lineage"]
    assert Path(lineage["draft_output"]) == output.resolve()
    assert lineage["mode"] == "llm"
    assert lineage["prompt_version"] == pipeline.PROMPT_VERSION
    assert lineage["raw_sha256"] == exporter.sha256_file(output.with_suffix(".raw.json"))


@pytest.mark.parametrize("export_bundle", [True, False])
def test_unknown_evidence_fails_before_overwriting_outputs(tmp_path, monkeypatch, caplog, response_data, export_bundle):
    response_data["steps"][0]["fields"]["action"]["claims"][0]["evidence"] = [["SRC_HAAS_0005:U9999"]]
    raw = json.dumps(response_data)
    stub_llm(monkeypatch, raw)
    output = tmp_path / "previous.draft.json"
    output.write_text("previous draft", encoding="utf-8")
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text("previous bundle", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown evidence-pool candidate") as error:
        pipeline.run_extraction_pipeline(output_path=output, bundle_dir=bundle_dir, export_bundle=export_bundle)
    assert "Test operation" in str(error.value) and "field action, claim 1" in str(error.value)
    assert output.read_text(encoding="utf-8") == "previous draft"
    assert (bundle_dir / "manifest.json").read_text(encoding="utf-8") == "previous bundle"
    assert output.with_suffix(".raw.json").read_text(encoding="utf-8") == raw
    assert "Hoàn tất" not in caplog.text


@pytest.mark.parametrize("export_bundle", [True, False])
def test_contract_failure_preserves_raw_without_publishing(tmp_path, monkeypatch, response_data, export_bundle):
    # Pydantic permits this; the shared contract forbids claims in a missing field.
    response_data["steps"][0]["fields"]["action"]["state"] = "missing"
    raw = json.dumps(response_data)
    stub_llm(monkeypatch, raw)
    output = tmp_path / "new/result.draft.json"
    bundle_dir = tmp_path / "bundle"
    with pytest.raises(ValueError):
        pipeline.run_extraction_pipeline(output_path=output, bundle_dir=bundle_dir, export_bundle=export_bundle)
    assert not output.exists()
    assert not bundle_dir.exists()
    assert output.with_suffix(".raw.json").read_text(encoding="utf-8") == raw


def test_malformed_response_is_kept_when_output_parent_is_new(tmp_path, monkeypatch):
    raw = "{invalid json"
    stub_llm(monkeypatch, raw)
    output = tmp_path / "new/result.draft.json"
    with pytest.raises(ValueError, match="Draft không hợp lệ"):
        pipeline.run_extraction_pipeline(output_path=output, export_bundle=False)
    assert not output.exists()
    assert output.with_suffix(".raw.json").read_text(encoding="utf-8") == raw


def test_cli_replays_saved_draft_without_calling_llm(tmp_path, monkeypatch, response_data):
    raw = json.dumps(response_data)
    saved = tmp_path / "saved.draft.json"
    saved.write_text(raw, encoding="utf-8")
    monkeypatch.setattr(pipeline, "get_llm_adapter", lambda **kwargs: pytest.fail("Replay must not instantiate an LLM"))
    monkeypatch.setattr("sys.argv", ["extraction_pipeline", "--from-draft", str(saved)])
    pipeline.main()
    assert saved.read_text(encoding="utf-8") == raw
    normalized = tmp_path / "saved.normalized.draft.json"
    snapshot = cw.compile_draft(json.loads(normalized.read_text(encoding="utf-8")))
    assert len(snapshot["evidence"]) == 2
    bundle_dir = tmp_path / "bundle_saved.normalized"
    assert exporter.verify_bundle_integrity(bundle_dir)["valid"]
    lineage = json.loads((bundle_dir / "lineage.json").read_text(encoding="utf-8"))["lineage"]
    assert lineage["mode"] == "from_draft"
    assert lineage["model"] is None and lineage["model_provenance"] == "unknown"
    assert "prompt_version" not in lineage


def test_replay_refuses_to_overwrite_original(tmp_path, response_data):
    saved = tmp_path / "saved.draft.json"
    raw = json.dumps(response_data)
    saved.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="giữ nguyên bản đầu vào"):
        pipeline.run_extraction_pipeline(from_draft=saved, output_path=saved)
    assert saved.read_text(encoding="utf-8") == raw


def test_exporter_refuses_compile_failure_without_fallback(tmp_path, response_data, source_record):
    response_data["steps"][0]["fields"]["action"]["claims"][0]["evidence"] = [["SRC_HAAS_0005:U9999"]]
    with pytest.raises(cw.DraftError, match="unknown evidence-pool candidate"):
        exporter.export_schema_v1_bundle(WorkflowBundle.model_validate(response_data), source_record, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


def test_exporter_requires_validator(tmp_path, monkeypatch, response_data, source_record):
    monkeypatch.setattr(exporter, "validate_bundle", None)
    with pytest.raises(RuntimeError, match="thiếu validator"):
        exporter.export_schema_v1_bundle(WorkflowBundle.model_validate(response_data), source_record, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


def test_draft_only_validates_supplied_metadata(tmp_path, monkeypatch, response_data, source_record):
    stub_llm(monkeypatch, json.dumps(response_data))
    source_record["duration_ms"] = 1  # All cited timestamps are now outside the source.
    metadata_path = tmp_path / "sources.jsonl"
    metadata_path.write_text(json.dumps(source_record) + "\n", encoding="utf-8")
    output = tmp_path / "draft.json"
    with pytest.raises(ValueError):
        pipeline.run_extraction_pipeline(metadata_path=metadata_path, output_path=output, export_bundle=False)
    assert not output.exists()


def test_preparation_preserves_evidence_and_covers_relation_claims(response_data, source_record):
    relation_claim = copy.deepcopy(response_data["steps"][0]["fields"]["action"]["claims"][0])
    response_data["relations"] = [{"type": "requires", "from_step": 1, "to_step": 1, "claim": relation_claim}]
    bundle = WorkflowBundle.model_validate(response_data)
    before = bundle.model_dump(mode="json")
    prepared = exporter.prepare_draft(bundle, source_record)
    assert prepared["relations"][0]["claim"]["evidence"] == [["SRC_HAAS_0005:U0029"], ["SRC_HAAS_0005:U0031"]]
    assert bundle.model_dump(mode="json") == before


@pytest.mark.parametrize("evidence", [
    [["SRC_HAAS_0005:U0029", "SRC_HAAS_0005:U0029"]],
    [["SRC_HAAS_0005:U0029", "SRC_HAAS_0001:U0030"]],
    [["SRC_HAAS_0005:U0029", "unknown"]],
])
def test_normalization_keeps_invalid_references_for_compiler_to_reject(evidence):
    assert exporter._sanitize_evidence_spans(evidence) == evidence
