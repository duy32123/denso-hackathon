"""Validate real/dev inputs without reading any holdout contents."""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from collections import Counter
from pathlib import Path

from retrieval.evaluation.harness import check_gold, load_questions
from retrieval.importer.store import import_bundle
from retrieval.indexing.search_index import read_corpus, digest

ROOT = Path(__file__).resolve().parents[2]


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def verify_label_approval(config):
    if config.get("label_revalidation_pending"):
        # Execution approval on existing gold is distinct from source review.
        authorization = json.loads((ROOT / config["execution_authorization"]).read_text(encoding="utf-8"))
        if (authorization.get("kind") != "user_execution_authorization" or
                authorization.get("human_source_review") is not False or
                authorization.get("questions_sha256") != sha_file(ROOT / config["questions"])):
            raise ValueError("Missing authorization to measure unchanged labels with pending source revalidation")
        if config.get("expanded_label_review"):
            raise ValueError("Pending revalidation cannot be marked completed human review")
        return
    if not config.get("expanded_label_review"):
        return
    path = ROOT / config["expanded_label_review"]
    if not path.is_file():
        raise ValueError("Expanded-corpus negative labels need a completed human review before preparing the official run")
    approval = json.loads(path.read_text(encoding="utf-8"))
    if (approval.get("reviewer_kind") != "human" or not approval.get("reviewer_id") or
            approval.get("questions_sha256_after") != sha_file(ROOT / config["questions"]) or
            approval.get("bundle_manifest_sha256") != sha_file(ROOT / config["bundle"] / "manifest.json") or
            approval.get("pending_questions") != []):
        raise ValueError("Expanded-corpus negative labels still require human review")


def audit(config, db):
    if (config["source_type"], config["dataset_split"]) != ("real", "dev"):
        raise ValueError("This benchmark cannot open synthetic or holdout")
    verify_label_approval(config)
    bundle = ROOT / config["bundle"]
    imported = import_bundle(bundle, db, source_type="real", split="dev")
    corpus = read_corpus(db, "real", "dev")
    questions, qhash = load_questions(ROOT / config["questions"])
    count = config.get("expected_questions", 66)
    if len(questions) != count or any((q.source_type, q.dataset_split, q.label.status) !=
                                  ("real", "dev", "reviewed") for q in questions):
        raise ValueError(f"Require exactly {count} reviewed real/dev questions")
    if any(q.label.reviewed_by == q.label.labeled_by for q in questions):
        raise ValueError("Question reviewer must be independent of the label author")
    check_gold(questions, corpus["workflows"])
    files = [ROOT / config["questions"], *bundle.glob("*.*"),
             ROOT / "data/sources/haas_pilot_sources.jsonl", *sorted((ROOT / "data/workflows/dev").glob("*.json"))]
    if config.get("expanded_label_review"):
        files.append(ROOT / config["expanded_label_review"])
        files.extend((ROOT / config["expanded_label_review"]).parent / name for name in
                     ("label_changes.jsonl", "negative_label_review.csv", "manifest.json"))
    if config.get("execution_authorization"):
        files.append(ROOT / config["execution_authorization"])
    sources = []
    for source in corpus["sources"].values():
        transcript = ROOT / f"acquisition/preprocessing/transcripts/{source.source_id}/corrected.json"
        if source.source_kind == "official_service_video":
            if not transcript.is_file():
                raise FileNotFoundError(f"Missing corrected transcript: {source.source_id}")
            files.append(transcript)
        sources.append({"source_id": source.source_id, "source_kind": str(source.source_kind),
                        "title": source.title, "url": source.url, "content_sha256": source.content_sha256,
                        "raw_text_chars": len(source.raw_text or ""), "transcript":
                        str(transcript.relative_to(ROOT)).replace("\\", "/") if transcript.is_file() else None})
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha_file(p) for p in files if p.is_file()}
    state = {"head": git("rev-parse", "HEAD"), "feature_head": git("rev-parse", "feature/a2-knowledge-space-3d"),
             "branch": git("branch", "--show-current"), "status": git("status", "--porcelain")}
    labels = Counter(q.label.status for q in questions)
    workflows = [{"workflow_id": wf.workflow_id, "revision": wf.revision,
                  "lifecycle": str(wf.lifecycle), "steps": len(wf.steps), "claims": len(wf.claims),
                  "relations": len(wf.relations), "source_ids": wf.source_ids,
                  "technical_review": dict(Counter(str(c.technical_review) for c in wf.claims)),
                  "source_review": dict(Counter(str(c.source_review) for c in wf.claims))}
                 for wf in corpus["workflows"].values()]
    return {
        "git": state, "bundle_manifest": json.loads((bundle / "manifest.json").read_text(encoding="utf-8")),
        "import_result": imported, "active_workflows": workflows, "sources": sources,
        "questions": len(questions), "questions_sha256": qhash, "corpus_files_sha256": digest(hashes),
        "input_files": hashes, "labels": dict(labels),
        "expanded_negative_label_revalidation": {"pending": bool(config.get("label_revalidation_pending")),
            "human_source_revalidated_questions": 0 if config.get("label_revalidation_pending") else None,
            "note": "Existing label review is preserved; user execution approval is not human source review"},
        "reviewers": dict(Counter(q.label.reviewed_by for q in questions)),
        "languages": dict(Counter(q.language for q in questions)),
        "expected_status": dict(Counter(str(q.expected_status) for q in questions)),
        "retrieval_gold_denominator": sum(q.scored for q in questions),
        "python": platform.python_version(), "platform": platform.platform(),
        "dependencies": {d: importlib.metadata.version(d) for d in
                         ("google-genai", "pydantic", "fastapi", "httpx", "snowballstemmer", "python-dotenv", "pytest")},
        "holdout_opened": False, "synthetic_opened": False
    }
