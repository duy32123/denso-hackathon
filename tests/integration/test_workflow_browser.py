"""WP4 reader/history endpoints: exact revision, corpus boundaries, no writes or LLM."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from conftest import FIXTURE_ROOT, REPO_ROOT, read_bundle, write_bundle
from knowflow_contracts.models import Workflow
from retrieval.api.app import create_app
from retrieval.generation.browse import snapshot_diff
from retrieval.generation.service import QAService
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index


def no_model():
    raise AssertionError("Browsing must never call an LLM")


@pytest.fixture
def browser(tmp_path):
    db = tmp_path / "real.sqlite"
    bundle = REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle"
    import_bundle(bundle, db, source_type="real", split="dev")
    build = build_index(db, mode="real", split="dev")["index_build_id"]
    service = QAService({("real", "dev"): db}, repo_root=REPO_ROOT, model_factory=no_model)
    with TestClient(create_app(service)) as client:
        yield client, db, {"mode": "real", "dataset_split": "dev", "index_build_id": build}


def test_catalog_workflow_history_are_read_only_and_keep_source_metadata(browser):
    client, db, params = browser
    before = db.read_bytes()
    catalog = client.get("/v1/workflows", params={"mode": "real", "dataset_split": "dev"})
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["read_only"] and body["index_build_id"] == params["index_build_id"]
    assert ("B0_SRC_HAAS_0005", 2) in {(w["workflow_id"], w["revision"]) for w in body["workflows"]}
    assert ("B0_SRC_HAAS_0005", 1) not in {(w["workflow_id"], w["revision"]) for w in body["workflows"]}
    response = client.get("/v1/workflows/B0_SRC_HAAS_0005/2", params=params)
    assert response.status_code == 200
    data = response.json()
    assert data["read_only"] and len(data["workflow"]["steps"]) == 9
    assert data["workflow"]["context"]["machine_model"] is None
    assert data["review_counts"]["technical"] == {"not_requested": 33}
    assert all("raw_text" not in source for source in data["sources"])
    assert all("asset_uri" not in ev for ev in data["workflow"]["evidence"])
    claim = next(c for c in data["workflow"]["claims"] if c["claim_id"].endswith("CL_020"))
    assert claim["attribution"] and claim["scope"] and claim["evidence_links"]
    history = client.get("/v1/workflows/B0_SRC_HAAS_0005/2/history", params=params).json()
    assert [item["revision"] for item in history["revisions"]] == [1, 2]
    change = history["revisions"][1]["diff"]
    assert [c["id"] for c in change["claims"]["changed"]] == ["B0_SRC_HAAS_0005_CL_020"]
    assert change["claims"]["changed"][0]["fields"] == ["evidence_links"]
    assert change["evidence"]["added"] == ["B0_SRC_HAAS_0005_EV_033"]
    assert change["evidence"]["changed"] == []
    assert history["revisions"][0]["index_build_id"] is None  # r1 was imported, not indexed in this DB
    assert db.read_bytes() == before


@pytest.mark.parametrize("path,patch,status", [
    ("/v1/workflows/B0_SRC_HAAS_0005/1", {}, 404),
    ("/v1/workflows/B0_SRC_HAAS_0005/1/history", {}, 404),
    ("/v1/workflows/UNKNOWN/2", {}, 404),
    ("/v1/workflows/B0_SRC_HAAS_0005/2", {"index_build_id": "invented"}, 404),
    ("/v1/workflows/B0_SRC_HAAS_0005/2/history", {"index_build_id": "invented"}, 404),
    ("/v1/workflows/B0_SRC_HAAS_0005/2", {"mode": "synthetic"}, 422),
    ("/v1/workflows/B0_SRC_HAAS_0005/2/history", {"dataset_split": "holdout"}, 422),
    ("/v1/workflows/B0_SRC_HAAS_0005/invalid", {}, 422),
])
def test_reader_cannot_cross_revision_index_or_namespace(browser, path, patch, status):
    client, _, params = browser
    response = client.get(path, params={**params, **patch})
    assert response.status_code == status
    assert response.json()["error"]["code"] in ("workflow_not_found", "namespace_unavailable", "invalid_request")


def test_workflow_read_and_history_do_not_require_current_index(browser):
    client, db, params = browser
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM settings WHERE key='active_retrieval_build'")
    assert client.get("/v1/workflows", params={"mode": "real", "dataset_split": "dev"}).status_code == 503
    assert client.get("/v1/workflows/B0_SRC_HAAS_0005/2", params=params).status_code == 200
    assert client.get("/v1/workflows/B0_SRC_HAAS_0005/2/history", params=params).status_code == 200


def test_history_uses_old_index_for_old_revision_and_does_not_jump_forward(tmp_path):
    data = read_bundle(FIXTURE_ROOT / "F09_revision_update")
    first = {**data, "workflows": data["workflows"][:1]}
    db = tmp_path / "synthetic.sqlite"
    import_bundle(write_bundle(tmp_path / "old", first), db, source_type="synthetic", split="dev")
    old_build = build_index(db, mode="synthetic", split="dev")["index_build_id"]
    import_bundle(FIXTURE_ROOT / "F09_revision_update", db, source_type="synthetic", split="dev")
    new_build = build_index(db, mode="synthetic", split="dev")["index_build_id"]
    service = QAService({("synthetic", "dev"): db}, repo_root=REPO_ROOT, model_factory=no_model)
    wid = first["workflows"][0]["workflow_id"]
    params = {"mode": "synthetic", "dataset_split": "dev", "index_build_id": new_build}
    with TestClient(create_app(service)) as client:
        body = client.get(f"/v1/workflows/{wid}/2/history", params=params).json()
        assert [(r["revision"], r["index_build_id"]) for r in body["revisions"]] == [(1, old_build), (2, new_build)]
        old = {**params, "index_build_id": old_build}
        assert client.get(f"/v1/workflows/{wid}/1", params=params).status_code == 404
        old_history = client.get(f"/v1/workflows/{wid}/1/history", params=old).json()
        assert [r["revision"] for r in old_history["revisions"]] == [1]
        snapshot = client.get(f"/v1/workflows/{wid}/1", params=old).json()
        assert all(source["url"] is None for source in snapshot["sources"])
        assert snapshot["workflow"]["source_type"] == "synthetic"


def test_reader_exposes_conflicts_and_questions_without_promoting_them(tmp_path):
    for fixture in ("F06_conflict", "F02_rationale_missing"):
        path = FIXTURE_ROOT / fixture
        assert path.is_dir()
        db = tmp_path / f"{fixture}.sqlite"
        import_bundle(path, db, source_type="synthetic", split="dev")
        build = build_index(db, mode="synthetic", split="dev")["index_build_id"]
        service = QAService({("synthetic", "dev"): db}, repo_root=REPO_ROOT, model_factory=no_model)
        original = read_bundle(path)["workflows"][0]
        with TestClient(create_app(service)) as client:
            response = client.get(f"/v1/workflows/{original['workflow_id']}/{original['revision']}",
                                  params={"mode": "synthetic", "dataset_split": "dev", "index_build_id": build})
            assert response.status_code == 200
            wf = response.json()["workflow"]
            assert wf["claims"] == Workflow.model_validate(original).model_dump(mode="json")["claims"]
            assert wf["questions"] == original["questions"]


def test_diff_redacts_asset_paths_and_preserves_review_change_meaning():
    raw = read_bundle(FIXTURE_ROOT / "F09_revision_update")["workflows"][0]
    old = Workflow.model_validate(raw)
    new = old.model_copy(deep=True)
    new.revision += 1
    new.claims[0].source_review = "source_checked"
    new.evidence[0].asset_uri = "private/path/image.png"
    delta = snapshot_diff(old, new)
    assert "private/path" not in json.dumps(delta)
    change = next(c for c in delta["claims"]["changed"] if c["id"] == new.claims[0].claim_id)
    assert change["fields"] == ["source_review"]
    assert change["after"]["technical_review"] == "not_requested"
