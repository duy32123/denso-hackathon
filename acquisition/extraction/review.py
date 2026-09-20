"""D1-B source-review tooling (Team 1 plan WP5; Schema 1.0.0 sections 5-6).

``source_checked`` may only be set by a human ReviewEvent, and a review is only
valid for the exact content that was checked. This module makes both mechanical:

    sheet   -> a CSV with one row per claim, for the reviewer (D1-C) to fill in
               Excel / Google Sheets: claim, verbatim evidence, a watch link
    apply   -> reads the filled sheet and appends a review session to
               acquisition/extraction/reviews/<workflow_id>.r<rev>.review.json
    status  -> checked / rejected / pending / stale counts
    promote -> compiles the draft, turns the review record into ReviewEvents and
               claim states, validates, and writes data/workflows/<split>/ for
               the exporter

Every decision stores a *fingerprint* of the claim it was made on (claim text,
role, scope, attribution, each link's explanation and the linked evidence
content). If the draft later changes that claim or its evidence, the decision is
stale and promotion refuses it: an old review is never inherited by new content.

The reviewer must not be the draft's ``authored_by`` (Team 1 plan: the person who
labels and the person who checks should differ); ``--allow-self-review`` exists
for emergencies and marks every event note as a self-review.

Usage (from the repo root)::

    python -m acquisition.extraction.review sheet   acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json
    python -m acquisition.extraction.review apply   acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json \\
        acquisition/extraction/reviews/REAL_WF_0001.r1.sheet.csv --reviewer-id <github-user> --reviewer-role "D1-C annotation/QA"
    python -m acquisition.extraction.review status  acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json
    python -m acquisition.extraction.review promote acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from acquisition.export import exporter
from acquisition.extraction import compile_workflow as cw

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEWS_DIR = REPO_ROOT / "acquisition" / "extraction" / "reviews"
WORKFLOWS_ROOT = REPO_ROOT / "data" / "workflows"

SHEET_COLUMNS = ["claim_id", "fingerprint", "step", "field", "evidence_type", "claim", "evidence", "watch", "decision", "note"]
SOURCE_DECISIONS = ("source_checked", "rejected")
_YOUTUBE_PAGE = re.compile(r"haascnc\.com/video/service/(?P<vid>[A-Za-z0-9_-]{11})\.html$")


class ReviewError(ValueError):
    """The review cannot be recorded or applied as requested."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- fingerprint -----------------------------------------------------------------


_EVIDENCE_CONTENT = ("source_id", "modality", "locator", "quote", "observation_note", "asset_uri", "transcript_origin")
_CLAIM_CONTENT = ("text", "role", "evidence_type", "attribution", "scope", "conflicts_with")


def claim_fingerprint(claim: dict, evidence_by_id: dict[str, dict]) -> str:
    """Hash of what the reviewer actually checks. IDs are excluded on purpose:
    renumbering alone does not change what the source supports."""
    payload = {k: claim[k] for k in _CLAIM_CONTENT}
    payload["links"] = [
        {
            "support_status": link["support_status"],
            "explanation": link["explanation"],
            "evidence": {k: evidence_by_id[link["evidence_id"]][k] for k in _EVIDENCE_CONTENT},
        }
        for link in claim["evidence_links"]
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def fingerprints(snapshot: dict) -> dict[str, str]:
    evidence = {e["evidence_id"]: e for e in snapshot["evidence"]}
    return {c["claim_id"]: claim_fingerprint(c, evidence) for c in snapshot["claims"]}


# --- sheet -----------------------------------------------------------------------


def _clock(ms: int | None) -> str:
    return "" if ms is None else f"{ms // 60000}:{(ms // 1000) % 60:02d}"


def _watch_link(source: dict | None, start_ms: int) -> str:
    """Reviewer convenience only. How Team 2 opens evidence is still an open decision with D2-A."""
    if source is None:
        return ""
    match = _YOUTUBE_PAGE.search(source.get("url") or "")
    if match:
        return f"https://www.youtube.com/watch?v={match['vid']}&t={start_ms // 1000}s"
    return f"{source.get('url')} @ {_clock(start_ms)}"


def _evidence_lines(claim: dict, evidence: dict[str, dict]) -> list[str]:
    lines = []
    for link in claim["evidence_links"]:
        ev = evidence[link["evidence_id"]]
        loc = ev["locator"]
        when = f"[{_clock(loc['start_ms'])}-{_clock(loc['end_ms'])}] " if loc["start_ms"] is not None else ""
        if ev["modality"] == "visual":
            lines.append(f"{when}(visual) {ev['observation_note']} | {ev['asset_uri']}")
        else:
            label = "corrected caption" if ev["transcript_origin"] == "human" else ev["modality"]
            lines.append(f'{when}({label}) "{ev["quote"]}"')
            for parent_id in ev["parent_evidence_ids"]:
                lines.append(f'{when}(raw caption) "{evidence[parent_id]["quote"]}"')
        lines.append(f"    why: {link['explanation']}")
    return lines


def build_sheet(snapshot: dict, sources: dict[str, dict]) -> list[dict]:
    evidence = {e["evidence_id"]: e for e in snapshot["evidence"]}
    fps = fingerprints(snapshot)
    placement: dict[str, tuple[str, str]] = {}
    for step in snapshot["steps"]:
        for role, ref in step["fields"].items():
            for cid in ref["claim_ids"]:
                placement.setdefault(cid, (f"{step['display_order']}. {step['title']}", role))
    orders = {s["step_id"]: s["display_order"] for s in snapshot["steps"]}
    for rel in snapshot["relations"]:
        for cid in rel["claim_ids"]:
            placement.setdefault(cid, (f"{rel['relation_type']}: step {orders[rel['from_step_id']]} -> step {orders[rel['to_step_id']]}", "relation"))

    rows = []
    for claim in snapshot["claims"]:
        step, field = placement.get(claim["claim_id"], ("", claim["role"]))
        timed = [evidence[l["evidence_id"]] for l in claim["evidence_links"] if evidence[l["evidence_id"]]["locator"]["start_ms"] is not None]
        watch = _watch_link(sources.get(timed[0]["source_id"]), timed[0]["locator"]["start_ms"]) if timed else ""
        rows.append({
            "claim_id": claim["claim_id"],
            "fingerprint": fps[claim["claim_id"]],
            "step": step,
            "field": field,
            "evidence_type": claim["evidence_type"],
            "claim": claim["text"],
            "evidence": "\n".join(_evidence_lines(claim, evidence)),
            "watch": watch,
            "decision": "",
            "note": "",
        })
    return rows


def write_sheet(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel opens UTF-8 correctly
        writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_sheet(path: Path) -> list[dict]:
    """Accepts what Excel or Google Sheets saves: with or without BOM, ',' ';' or tab."""
    text = path.read_text(encoding="utf-8-sig")
    # Detect only the delimiter from the header. A full Sniffer dialect guessed from
    # one unquoted line gets quote escaping wrong, and the evidence column is full
    # of verbatim quotes, so every other rule stays Excel's.
    header = text.split("\n", 1)[0]
    delimiter = max(",;\t", key=header.count)
    rows = list(csv.DictReader(io.StringIO(text), dialect=csv.excel, delimiter=delimiter))
    missing = {"claim_id", "fingerprint", "decision", "note"} - set(rows[0] if rows else {})
    if missing:
        raise ReviewError(f"{path.name}: sheet is missing column(s) {sorted(missing)}")
    return [{k: (v or "").strip() for k, v in row.items() if k is not None} for row in rows]


# --- recording -------------------------------------------------------------------


def session_from_sheet(
    snapshot: dict,
    rows: list[dict],
    *,
    reviewer_id: str,
    reviewer_role: str,
    author: str | None,
    allow_self_review: bool = False,
    clock: Callable[[], str] = _utc_now,
) -> dict:
    if not reviewer_id.strip() or not reviewer_role.strip():
        raise ReviewError("reviewer_id and reviewer_role are required: a review must say who checked")
    self_review = bool(author) and author is not None and reviewer_id.strip().casefold() == author.strip().casefold()
    if self_review and not allow_self_review:
        raise ReviewError(f"{reviewer_id} authored this draft; the source check must be done by someone else")

    current = fingerprints(snapshot)
    errors, seen, decisions = [], set(), []
    for n, row in enumerate(rows, start=2):  # line 1 is the header
        decision = row.get("decision", "").lower()
        if not decision:
            continue
        cid = row.get("claim_id", "")
        if decision not in SOURCE_DECISIONS:
            errors.append(f"line {n} {cid}: decision must be one of {SOURCE_DECISIONS} or empty, got '{decision}'")
            continue
        if cid not in current:
            errors.append(f"line {n}: unknown claim_id '{cid}'")
            continue
        if row.get("fingerprint") != current[cid]:
            errors.append(f"line {n} {cid}: claim changed since this sheet was generated; regenerate the sheet and re-check it")
            continue
        if cid in seen:
            errors.append(f"line {n} {cid}: claim appears twice in the sheet")
            continue
        note = row.get("note") or None
        if decision == "rejected" and not note:
            errors.append(f"line {n} {cid}: a rejection needs a note saying what the source does not support")
            continue
        if self_review:
            note = f"(self-review) {note}" if note else "(self-review)"
        seen.add(cid)
        decisions.append({"claim_id": cid, "fingerprint": current[cid], "dimension": "source", "decision": decision, "note": note})

    if errors:
        raise ReviewError("sheet rejected, nothing recorded:\n  " + "\n  ".join(errors))
    if not decisions:
        raise ReviewError("the sheet has no decisions; fill the 'decision' column")
    return {
        "reviewer_id": reviewer_id.strip(),
        "reviewer_role": reviewer_role.strip(),
        "reviewed_at": clock(),
        "self_review": self_review,
        "decisions": decisions,
    }


def record_path(workflow_id: str, revision: int, reviews_dir: Path = REVIEWS_DIR) -> Path:
    return reviews_dir / f"{workflow_id}.r{revision}.review.json"


def load_record(workflow_id: str, revision: int, reviews_dir: Path = REVIEWS_DIR) -> dict:
    path = record_path(workflow_id, revision, reviews_dir)
    if not path.is_file():
        return {"workflow_id": workflow_id, "revision": revision, "sessions": []}
    record = json.loads(path.read_text(encoding="utf-8"))
    if (record["workflow_id"], record["revision"]) != (workflow_id, revision):
        raise ReviewError(f"{path.name} belongs to {record['workflow_id']}@r{record['revision']}")
    return record


def append_session(record: dict, session: dict, reviews_dir: Path = REVIEWS_DIR) -> Path:
    record = copy.deepcopy(record)
    record["sessions"].append(session)
    path = record_path(record["workflow_id"], record["revision"], reviews_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


# --- applying --------------------------------------------------------------------


def _valid_decisions(snapshot: dict, record: dict) -> tuple[list[tuple[dict, dict]], list[str]]:
    """Decisions that still match current content, and claims whose latest review is stale.

    A decision whose fingerprint no longer matches is dropped if a later decision
    on the same claim and dimension matches (it was about an earlier, never
    published draft). Otherwise the claim is stale: it was reviewed, then changed.
    """
    current = fingerprints(snapshot)
    valid: list[tuple[dict, dict]] = []
    latest_ok: dict[tuple[str, str], bool] = {}
    for session in record["sessions"]:
        for d in session["decisions"]:
            ok = current.get(d["claim_id"]) == d["fingerprint"]
            latest_ok[(d["claim_id"], d["dimension"])] = ok
            if ok:
                valid.append((session, d))
    stale = sorted({cid for (cid, _), ok in latest_ok.items() if not ok})
    return valid, stale


def review_status(snapshot: dict, record: dict) -> dict:
    valid, stale = _valid_decisions(snapshot, record)
    latest = {d["claim_id"]: d["decision"] for _, d in valid if d["dimension"] == "source"}
    claims = [c["claim_id"] for c in snapshot["claims"]]
    return {
        "claims": len(claims),
        "source_checked": sum(1 for c in claims if latest.get(c) == "source_checked" and c not in stale),
        "rejected": [c for c in claims if latest.get(c) == "rejected" and c not in stale],
        "pending": [c for c in claims if c not in latest and c not in stale],
        "stale": stale,
    }


def merge_reviews(snapshot: dict, record: dict) -> dict:
    """ReviewEvents + claim review states for this revision. Refuses stale reviews."""
    if (record["workflow_id"], record["revision"]) != (snapshot["workflow_id"], snapshot["revision"]):
        raise ReviewError("review record and snapshot are for different workflow revisions")
    valid, stale = _valid_decisions(snapshot, record)
    if stale:
        raise ReviewError(f"claims changed after review, re-check them: {', '.join(stale)}")

    merged = copy.deepcopy(snapshot)
    claims = {c["claim_id"]: c for c in merged["claims"]}
    events = []
    for n, (session, d) in enumerate(valid, start=1):
        events.append({
            "review_id": f"{merged['workflow_id']}_RV_{n:03d}",
            "target_type": "claim",
            "target_id": d["claim_id"],
            "dimension": d["dimension"],
            "decision": d["decision"],
            "reviewer_id": session["reviewer_id"],
            "reviewer_role": session["reviewer_role"],
            "reviewed_at": session["reviewed_at"],
            "note": d["note"],
        })
        key = "source_review" if d["dimension"] == "source" else "technical_review"
        claims[d["claim_id"]][key] = d["decision"]  # later sessions override earlier ones
    merged["review_events"] = events
    return merged


def promote(
    draft_path: Path,
    *,
    allow_incomplete: bool = False,
    reviews_dir: Path = REVIEWS_DIR,
    workflows_root: Path = WORKFLOWS_ROOT,
) -> tuple[Path, dict]:
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    snapshot = cw.compile_draft(draft)
    record = load_record(snapshot["workflow_id"], snapshot["revision"], reviews_dir)
    status = review_status(snapshot, record)

    if status["stale"]:
        raise ReviewError(f"claims changed after review, re-check them: {', '.join(status['stale'])}")
    open_items = status["pending"] + status["rejected"]
    if open_items and not allow_incomplete:
        raise ReviewError(
            f"{len(status['pending'])} claim(s) pending and {len(status['rejected'])} rejected; fix rejected claims in "
            "the draft and review everything before promotion (or pass --allow-incomplete)"
        )

    merged = merge_reviews(snapshot, record)
    result = cw.check_draft_snapshot(draft, merged)
    if not result.report.ok:
        raise ReviewError("reviewed snapshot fails validation:\n  " + "\n  ".join(str(i) for i in result.report.errors))
    path = cw.write_snapshot(merged, workflows_root / draft["dataset_split"])
    return path, status


# --- CLI -------------------------------------------------------------------------


def _show(path: Path) -> str:
    resolved = path.resolve()
    return resolved.relative_to(REPO_ROOT).as_posix() if resolved.is_relative_to(REPO_ROOT) else str(resolved)


# The CLI reads REVIEWS_DIR / WORKFLOWS_ROOT at call time (not as default
# arguments) so tests can point it at a temporary directory.


def _load_draft_snapshot(draft_path: str) -> tuple[dict, dict]:
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    return draft, cw.compile_draft(draft)


def _sources(split: str) -> dict[str, dict]:
    path = Path(str(exporter.SPLITS[split]["sources"]))
    return {r["source_id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if r}


def _cmd_sheet(args) -> int:
    draft, snapshot = _load_draft_snapshot(args.draft)
    out = Path(args.out) if args.out else REVIEWS_DIR / f"{snapshot['workflow_id']}.r{snapshot['revision']}.sheet.csv"
    rows = build_sheet(snapshot, _sources(draft["dataset_split"]))
    write_sheet(rows, out)
    print(f"wrote {_show(out)} ({len(rows)} claims). Fill 'decision' with source_checked or rejected; a rejection needs a note.")
    return 0


def _cmd_apply(args) -> int:
    draft, snapshot = _load_draft_snapshot(args.draft)
    session = session_from_sheet(
        snapshot, read_sheet(Path(args.sheet)), reviewer_id=args.reviewer_id, reviewer_role=args.reviewer_role,
        author=draft.get("authored_by"), allow_self_review=args.allow_self_review,
    )
    record = load_record(snapshot["workflow_id"], snapshot["revision"], REVIEWS_DIR)
    path = append_session(record, session, REVIEWS_DIR)
    counts = {d: sum(1 for x in session["decisions"] if x["decision"] == d) for d in SOURCE_DECISIONS}
    print(f"recorded {len(session['decisions'])} decision(s) {counts} by {session['reviewer_id']} -> {_show(path)}")
    return 0


def _cmd_status(args) -> int:
    _, snapshot = _load_draft_snapshot(args.draft)
    status = review_status(snapshot, load_record(snapshot["workflow_id"], snapshot["revision"], REVIEWS_DIR))
    print(f"{snapshot['workflow_id']}@r{snapshot['revision']}: {status['claims']} claims, "
          f"{status['source_checked']} source_checked, {len(status['rejected'])} rejected, "
          f"{len(status['pending'])} pending, {len(status['stale'])} stale")
    for label in ("rejected", "stale"):
        if status[label]:
            print(f"  {label}: {', '.join(status[label])}")
    return 0


def _cmd_promote(args) -> int:
    path, status = promote(Path(args.draft), allow_incomplete=args.allow_incomplete,
                           reviews_dir=REVIEWS_DIR, workflows_root=WORKFLOWS_ROOT)
    print(f"promoted -> {_show(path)} ({status['source_checked']}/{status['claims']} source_checked). "
          "Next: python -m acquisition.export.exporter --split dev --check")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="review", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sheet", help="write the CSV review sheet for a draft")
    p.add_argument("draft")
    p.add_argument("--out")
    p.set_defaults(func=_cmd_sheet)

    p = sub.add_parser("apply", help="record a filled review sheet")
    p.add_argument("draft")
    p.add_argument("sheet")
    p.add_argument("--reviewer-id", required=True)
    p.add_argument("--reviewer-role", required=True)
    p.add_argument("--allow-self-review", action="store_true")
    p.set_defaults(func=_cmd_apply)

    p = sub.add_parser("status", help="how much of the draft is reviewed")
    p.add_argument("draft")
    p.set_defaults(func=_cmd_status)

    p = sub.add_parser("promote", help="merge reviews and write the snapshot for the exporter")
    p.add_argument("draft")
    p.add_argument("--allow-incomplete", action="store_true", help="promote with pending or rejected claims")
    p.set_defaults(func=_cmd_promote)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ReviewError, cw.DraftError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
