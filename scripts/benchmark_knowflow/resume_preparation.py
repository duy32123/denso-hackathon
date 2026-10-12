"""Resume an interrupted/failed index build, retaining all prior API expense."""
import argparse
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from .audit import ROOT, sha_file
from .__main__ import verify_freeze, save, append
from .providers import Recorder, IndexEmbedder, now
from .baseline import build_raw_index, public_chunk
from .report import read_jsonl
from retrieval.indexing.search_index import build_index, read_corpus


def resume(run_dir):
    config = verify_freeze(run_dir)
    if (run_dir / "smoke_rows.jsonl").exists() or (run_dir / "rows.jsonl").exists():
        raise ValueError("Index preparation cannot change after answer measurement starts")
    paths = json.loads((run_dir / "working_paths.json").read_text(encoding="utf-8"))
    db = ROOT / paths["db"]
    recorder = Recorder(run_dir / "provider_calls.jsonl")
    recorder.events = read_jsonl(recorder.path)
    embedder = IndexEmbedder(recorder, config["embedding_dimensions"], **config.get("index_pacing", {}))
    try:
        recorder.arm = "A_knowflow"
        start = time.perf_counter()
        manifest = build_index(db, mode="real", split="dev", embedder=embedder)
        structured_ms = (time.perf_counter()-start)*1000
        recorder.arm = "B_transcript_rag"
        corpus = read_corpus(db, "real", "dev")
        start = time.perf_counter()
        streams, chunks = build_raw_index(corpus["sources"], ROOT, config, embedder)
        raw_ms = (time.perf_counter()-start)*1000
        save(ROOT / paths["raw_index"], {"streams": streams, "chunks": chunks, "embedding": embedder.config})
        projection = run_dir / "raw_source_chunks.jsonl"
        if projection.exists():
            raise ValueError("Raw projection already exists; do not silently replace a measured baseline")
        for chunk in chunks:
            append(projection, public_chunk(chunk))
        save(run_dir / "index_manifest.json", {"structured": manifest,
             "structured_index_latency_ms": structured_ms, "raw_index_latency_ms": raw_ms,
             "raw_chunks": len(chunks), "raw_index_sha256": sha_file(ROOT / paths["raw_index"]),
             "raw_chunk_projection_sha256": sha_file(projection), "raw_preprocessing": config["baseline"],
             "index_pacing": config.get("index_pacing"),
             "previous_preparation_failure_retained": True,
             "previous_failed_preparation_total_latency_ms": None,
             "ablation": "One real retrieval per A/C pair, identical pre-ablation candidates; C removes graph fields"})
        save(run_dir / "preparation_status.json", {"ok": True, "finished_at": now(), "resumed_before_smoke_full": True})
        print(json.dumps({"prepared": True, "raw_chunks": len(chunks), "structured_documents": manifest["record_count"]}), flush=True)
    except Exception as exc:
        save(run_dir / "preparation_status.json", {"ok": False, "error_class": type(exc).__name__, "finished_at": now()})
        underlying = exc.__context__
        data = getattr(underlying, "response_json", {}) or {}
        data = data.get("error", data) if isinstance(data, dict) else {}
        details = data.get("details", []) if isinstance(data, dict) else []
        safe = {"error_class": type(exc).__name__, "quotas": [{k: v.get(k) for k in
                ("quotaMetric", "quotaId", "quotaValue", "quotaDimensions")} for d in details for v in d.get("violations", [])],
                "retry_delay": next((d["retryDelay"] for d in details if "retryDelay" in d), None)}
        append(run_dir / "preparation_errors.jsonl", safe)
        print(json.dumps({"prepared": False, **safe}), flush=True)
        raise SystemExit(2) from None
    finally:
        embedder.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    resume(args.run_dir.resolve())
