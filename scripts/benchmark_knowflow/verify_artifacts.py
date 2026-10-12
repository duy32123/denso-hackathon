"""Verify frozen inputs, journals, review hashes and retained evidence without API calls."""
import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from dotenv import dotenv_values
from retrieval.generation.evidence import EvidenceAccess
from retrieval.indexing.search_index import digest, read_corpus
from .audit import ROOT, sha_file
from .report import ARMS, read_jsonl
from .report import call_cost


def verify(run_dir, require_complete=True):
    frozen = json.loads((run_dir / "frozen_config.json").read_text(encoding="utf-8"))
    paths = json.loads((run_dir / "working_paths.json").read_text(encoding="utf-8"))
    config = frozen["config"]
    questions = read_jsonl(ROOT / config["questions"])
    rows = read_jsonl(run_dir / "rows.jsonl")
    expected = {(arm, q["question_id"]) for arm in ARMS for q in questions}
    observed = [(r["arm"], r["question_id"]) for r in rows]
    if len(observed) != len(set(observed)) or set(observed) - expected:
        raise ValueError("Duplicate or unexpected output rows")
    if require_complete and set(observed) != expected:
        raise ValueError("Benchmark is incomplete")
    changed = [name for group in ("input_files", "measurement_code_sha256")
               for name, value in frozen[group].items() if sha_file(ROOT / name) != value]
    if changed:
        raise ValueError(f"Frozen files changed: {changed}")
    product = subprocess.run(["git", "diff", "--quiet", frozen["product_commit"], "--", "retrieval", "data", "acquisition", "contracts"],
                             cwd=ROOT, check=False)
    if product.returncode:
        raise ValueError("Product or canonical data changed from measured commit")
    calls = read_jsonl(run_dir / "provider_calls.jsonl")
    call_lookup = {r["call_id"]: r for r in calls if r["kind"] == "provider_call"}
    if len(call_lookup) != sum(r["kind"] == "provider_call" for r in calls):
        raise ValueError("Duplicate provider call IDs")
    for row in rows:
        if row["http_status"] == 200:
            body = row["response"]
            if digest([body["status"], body["answer"], body["citations"]]) != row["answer_sha256"]:
                raise ValueError("Answer digest mismatch")
        for call in row["provider_calls"]:
            if call != call_lookup.get(call["call_id"]):
                raise ValueError("Row call differs from append-only provider journal")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    with (run_dir / "per_question.csv").open(encoding="utf-8-sig", newline="") as stream:
        per_question = list(csv.DictReader(stream))
    for arm in ARMS:
        full_calls = [c for c in call_lookup.values() if c["phase"] == "full" and c["arm"] == arm]
        ledger_known = sum(v for c in full_calls if (v := call_cost(c, config)) is not None)
        if summary["summaries"][arm]["cost"]["provider_calls"] != len(full_calls):
            raise ValueError("Summary dropped unfinished provider calls")
        if abs(summary["summaries"][arm]["cost"]["known_list_price_subtotal_usd"] - ledger_known) > 1e-10:
            raise ValueError("Summary cost does not match provider ledger")
        csv_known = sum(float(r["known_subtotal_usd"]) for r in per_question if r["arm"] == arm)
        if abs(csv_known-ledger_known) > 1e-10:
            raise ValueError("Per-question CSV dropped interrupted expense")
    with (run_dir / "human_review.csv").open(encoding="utf-8-sig", newline="") as stream:
        review = list(csv.DictReader(stream))
    if require_complete and {(r["arm"], r["question_id"]) for r in review} != expected:
        raise ValueError("Review sheet does not cover all tasks")
    corpus = read_corpus(ROOT / paths["db"], "real", "dev")
    access, evidence, assets = EvidenceAccess(ROOT), [], {}
    for wf in corpus["workflows"].values():
        for ev in wf.evidence:
            src = corpus["sources"][ev.source_id]
            view = access.view(ev, src)
            evidence.append({"workflow_id": wf.workflow_id, "revision": wf.revision,
                             "evidence_id": ev.evidence_id, "available": view.available, "access_kind": view.kind})
            if view.asset_path:
                relative = str(view.asset_path.relative_to(ROOT)).replace("\\", "/")
                original = subprocess.check_output(["git", "show", f"{frozen['product_commit']}:{relative}"], cwd=ROOT)
                sha = sha_file(view.asset_path)
                if hashlib.sha256(original).hexdigest() != sha:
                    raise ValueError("Evidence asset differs from product commit")
                assets[relative] = sha
    # Credentials are read only to test for accidental inclusion, never returned or printed.
    secrets = [v.encode() for k, v in dotenv_values(ROOT / ".env").items()
               if v and len(v) >= 12 and ("KEY" in k.upper() or "TOKEN" in k.upper() or "SECRET" in k.upper())]
    secret_hits = [str(p.relative_to(ROOT)) for p in run_dir.iterdir() if p.is_file()
                   and any(secret in p.read_bytes() for secret in secrets)]
    if secret_hits:
        raise ValueError(f"Credential detected in generated files: {secret_hits}")
    result = {"planned_tasks": len(expected), "recorded_tasks": len(observed), "missing_tasks": len(expected - set(observed)),
              "duplicates": 0, "frozen_files_changed": [], "product_unchanged": True,
              "review_rows": len(review), "answer_hashes_valid": True, "provider_journal_matches_rows": True,
              "cost_includes_interrupted_calls": True, "per_question_cost_matches_complete_ledger": True,
              "credential_findings": 0, "retained_evidence": dict(Counter(e["access_kind"] for e in evidence)),
              "unavailable_evidence": [e for e in evidence if not e["available"]],
              "evidence_asset_files": assets, "evidence_assets_sha256": digest(assets),
              "evidence_assets_match_product_commit": True, "holdout_opened": False,
              "report_code_sha256": sha_file(Path(__file__).with_name("report.py")),
              "review_import_code_sha256": sha_file(Path(__file__).with_name("review.py"))}
    (run_dir / "artifact_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("planned_tasks", "recorded_tasks", "missing_tasks", "product_unchanged", "credential_findings", "retained_evidence")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    verify(args.run_dir.resolve(), not args.allow_partial)


if __name__ == "__main__":
    main()
