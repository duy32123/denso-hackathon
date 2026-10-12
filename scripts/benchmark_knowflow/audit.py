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


def audit(config, db):
    if (config["source_type"], config["dataset_split"]) != ("real", "dev"):
        raise ValueError("This benchmark cannot open synthetic or holdout")
    bundle = ROOT / config["bundle"]
    imported = import_bundle(bundle, db, source_type="real", split="dev")
    corpus = read_corpus(db, "real", "dev")
    questions, qhash = load_questions(ROOT / config["questions"])
    if len(questions) != 66 or any((q.source_type, q.dataset_split, q.label.status) !=
                                  ("real", "dev", "reviewed") for q in questions):
        raise ValueError("Require exactly 66 reviewed real/dev questions")
    check_gold(questions, corpus["workflows"])
    files = [ROOT / config["questions"], *bundle.glob("*.*"),
             ROOT / "data/sources/haas_pilot_sources.jsonl", *sorted((ROOT / "data/workflows/dev").glob("*.json"))]
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
        "reviewers": dict(Counter(q.label.reviewed_by for q in questions)),
        "languages": dict(Counter(q.language for q in questions)),
        "expected_status": dict(Counter(str(q.expected_status) for q in questions)),
        "retrieval_gold_denominator": sum(q.scored for q in questions),
        "python": platform.python_version(), "platform": platform.platform(),
        "dependencies": {d: importlib.metadata.version(d) for d in
                         ("google-genai", "pydantic", "fastapi", "httpx", "snowballstemmer", "python-dotenv", "pytest")},
        "holdout_opened": False, "synthetic_opened": False
    }
