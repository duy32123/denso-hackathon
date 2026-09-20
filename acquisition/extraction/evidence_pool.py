"""D1-B evidence candidate pool.

Turns D1-A's retained inputs into *evidence candidates* with stable IDs:

- every caption cue of a dev video  -> a speech candidate  ``SRC_HAAS_0005:U0012``
- every cue a human corrected       -> an extra candidate ``SRC_HAAS_0001:C0021``
  whose parent is the raw cue (Schema 1.0.0 section 4: a corrected transcript must
  keep the ASR/caption trace, never overwrite it)
- every non-empty line of a guide   -> a text candidate    ``SRC_HAAS_0002:T0007``

Candidates are not Schema entities. A workflow turns one or more *consecutive*
candidates into an ``Evidence`` record with :func:`span` + :func:`to_evidence`;
the workflow, not the pool, owns the nested ``<workflow_id>_EV_nnn`` ID.

ID stability: an ID is the 1-based ordinal of the cue/line inside an input whose
sha256 is recorded in the pool manifest. If that input ever changes, ordinals may
point at different text, so :func:`write_pool` refuses to overwrite the pool
instead of silently re-numbering it.

Holdout sources are never read: only sources assigned ``dev`` in the split
manifest are processed (Team 1 plan: do not touch holdout before the D15 lock).

Usage (from the repo root)::

    python -m acquisition.extraction.evidence_pool build
    python -m acquisition.extraction.evidence_pool show SRC_HAAS_0005:U0003 SRC_HAAS_0005:U0004
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from knowflow_contracts.models import Evidence

from acquisition.validation.validate_d1a_extra import check_transcript_bounds

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_SOURCES = REPO_ROOT / "data" / "sources" / "haas_pilot_sources.jsonl"
SPLIT_MANIFEST = REPO_ROOT / "data" / "splits" / "haas_d1a_split_manifest.json"
TRANSCRIPTS_DIR = REPO_ROOT / "acquisition" / "preprocessing" / "transcripts"
POOL_DIR = REPO_ROOT / "acquisition" / "extraction" / "evidence_pool"

POOL_VERSION = "1"


class PoolError(ValueError):
    """Input or request that would produce a wrong or unstable candidate."""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    source_id: str
    kind: str  # "U" raw cue | "C" corrected cue | "T" guide line
    ordinal: int
    modality: str  # speech | text
    start_ms: int | None
    end_ms: int | None
    text: str
    transcript_origin: str  # official_caption | human | none
    parent_candidate_id: str | None
    input_file: str
    input_sha256: str
    text_span_unique: bool | None  # text candidates only: can text_span alone locate it?


@dataclass(frozen=True)
class Span:
    """Consecutive candidates of one source, ready to become one Evidence record."""

    source_id: str
    candidate_ids: tuple[str, ...]
    modality: str
    start_ms: int | None
    end_ms: int | None
    quote: str
    transcript_origin: str
    parent_candidate_ids: tuple[str, ...]  # raw cues this span corrects; empty if none


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rel(path: Path) -> str:
    """Repo-relative path, so the committed pool does not embed anyone's home directory."""
    resolved = path.resolve()
    return resolved.relative_to(REPO_ROOT).as_posix() if resolved.is_relative_to(REPO_ROOT) else resolved.as_posix()


def candidate_id(source_id: str, kind: str, ordinal: int) -> str:
    return f"{source_id}:{kind}{ordinal:04d}"


# --- building ------------------------------------------------------------------


def dev_source_ids(split_manifest: Path = SPLIT_MANIFEST) -> set[str]:
    data = json.loads(split_manifest.read_text(encoding="utf-8"))
    return {sid for fam in data["families"] if fam["split"] == "dev" for sid in fam["source_ids"]}


def speech_candidates(source: dict, raw_path: Path, corrected_path: Path | None = None) -> list[Candidate]:
    source_id = source["source_id"]
    raw_bytes = raw_path.read_bytes()
    raw = json.loads(raw_bytes)
    if raw.get("source_id") != source_id:
        raise PoolError(f"{_rel(raw_path)}: transcript belongs to {raw.get('source_id')}, not {source_id}")
    if raw.get("timestamp_basis") != "original_video_ms":
        raise PoolError(f"{_rel(raw_path)}: timestamps must be on the original video (original_video_ms)")
    if source.get("duration_ms") is None:
        raise PoolError(f"{source_id}: video source has no measured duration_ms")

    bound_errors = check_transcript_bounds(str(raw_path), source["duration_ms"])
    if bound_errors:
        raise PoolError(f"{_rel(raw_path)}: " + "; ".join(bound_errors))

    raw_sha = _sha256(raw_bytes)
    origin = raw.get("transcript_origin", "official_caption")
    out = [
        Candidate(
            candidate_id=candidate_id(source_id, "U", i),
            source_id=source_id,
            kind="U",
            ordinal=i,
            modality="speech",
            start_ms=u["start_ms"],
            end_ms=u["end_ms"],
            text=u["text"],
            transcript_origin=origin,
            parent_candidate_id=None,
            input_file=_rel(raw_path),
            input_sha256=raw_sha,
            text_span_unique=None,
        )
        for i, u in enumerate(raw["utterances"], start=1)
    ]

    if corrected_path is not None and corrected_path.is_file():
        out.extend(_corrected_candidates(source_id, raw["utterances"], corrected_path))
    return out


def _corrected_candidates(source_id: str, raw_utts: list[dict], corrected_path: Path) -> list[Candidate]:
    corrected_bytes = corrected_path.read_bytes()
    corrected = json.loads(corrected_bytes)["utterances"]
    if len(corrected) != len(raw_utts):
        raise PoolError(f"{_rel(corrected_path)}: correction changed the number of cues")

    out: list[Candidate] = []
    for i, (r, c) in enumerate(zip(raw_utts, corrected), start=1):
        if (r["start_ms"], r["end_ms"]) != (c["start_ms"], c["end_ms"]):
            raise PoolError(f"{_rel(corrected_path)} cue {i}: a correction may change text, never timestamps")
        if r["text"] == c["text"]:
            continue
        # Whatever the file header says, an edited cue is human-produced text.
        out.append(
            Candidate(
                candidate_id=candidate_id(source_id, "C", i),
                source_id=source_id,
                kind="C",
                ordinal=i,
                modality="speech",
                start_ms=c["start_ms"],
                end_ms=c["end_ms"],
                text=c["text"],
                transcript_origin="human",
                parent_candidate_id=candidate_id(source_id, "U", i),
                input_file=_rel(corrected_path),
                input_sha256=_sha256(corrected_bytes),
                text_span_unique=None,
            )
        )
    return out


def text_candidates(source: dict) -> list[Candidate]:
    source_id = source["source_id"]
    raw_text = source.get("raw_text")
    if not raw_text:
        raise PoolError(f"{source_id}: document source has no raw_text")
    text_sha = _sha256(raw_text.encode("utf-8"))
    if source.get("content_sha256") and source["content_sha256"] != text_sha:
        raise PoolError(f"{source_id}: raw_text does not match content_sha256")

    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    counts: dict[str, int] = {}
    for line in lines:
        counts[line] = counts.get(line, 0) + 1

    return [
        Candidate(
            candidate_id=candidate_id(source_id, "T", i),
            source_id=source_id,
            kind="T",
            ordinal=i,
            modality="text",
            start_ms=None,
            end_ms=None,
            text=line,
            transcript_origin="none",
            parent_candidate_id=None,
            input_file=f"{_rel(DEV_SOURCES)}#{source_id}.raw_text",
            input_sha256=text_sha,
            text_span_unique=counts[line] == 1,
        )
        for i, line in enumerate(lines, start=1)
    ]


def build_pool(
    sources_path: Path = DEV_SOURCES,
    transcripts_dir: Path = TRANSCRIPTS_DIR,
    split_manifest: Path = SPLIT_MANIFEST,
) -> dict[str, list[Candidate]]:
    allowed = dev_source_ids(split_manifest)
    pool: dict[str, list[Candidate]] = {}

    for line in sources_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        source = json.loads(line)
        source_id = source["source_id"]
        if source_id not in allowed:
            raise PoolError(f"{source_id} is not a dev source in the split manifest; refusing to read it")

        if source["source_kind"] == "official_service_video":
            tdir = transcripts_dir / source_id
            raw_path = tdir / "raw.json"
            if not raw_path.is_file():
                raise PoolError(f"{source_id}: missing {_rel(raw_path)}")
            pool[source_id] = speech_candidates(source, raw_path, tdir / "corrected.json")
        elif source["source_kind"] == "service_document":
            pool[source_id] = text_candidates(source)

    return pool


# --- persisting ----------------------------------------------------------------


def _inputs(candidates: list[Candidate]) -> dict[str, str]:
    return {c.input_file: c.input_sha256 for c in candidates}


def write_pool(pool: dict[str, list[Candidate]], out_dir: Path = POOL_DIR) -> Path:
    manifest_path = out_dir / "manifest.json"
    new_inputs = {sid: _inputs(cands) for sid, cands in pool.items()}

    if manifest_path.is_file():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        for sid, inputs in old.get("sources", {}).items():
            old_inputs = inputs["inputs"]
            if sid in new_inputs and old_inputs != new_inputs[sid]:
                raise PoolError(
                    f"{sid}: inputs changed since the pool was built {old_inputs} -> {new_inputs[sid]}. "
                    "Candidate IDs could now point at different text; build a new pool version "
                    "instead of overwriting this one."
                )

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "pool_version": POOL_VERSION,
        "note": "Evidence candidates, not Schema 1.0.0 entities. IDs are ordinals within the hashed inputs below.",
        "sources": {},
    }
    for sid in sorted(pool):
        cands = pool[sid]
        body = "".join(
            json.dumps(asdict(c), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for c in cands
        ).encode("utf-8")
        (out_dir / f"{sid}.jsonl").write_bytes(body)
        manifest["sources"][sid] = {
            "file": f"{sid}.jsonl",
            "sha256": _sha256(body),
            "candidate_count": len(cands),
            "inputs": new_inputs[sid],
        }

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest_path


def load_pool(out_dir: Path = POOL_DIR) -> dict[str, Candidate]:
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    index: dict[str, Candidate] = {}
    for sid, entry in manifest["sources"].items():
        body = (out_dir / entry["file"]).read_bytes()
        if _sha256(body) != entry["sha256"]:
            raise PoolError(f"{entry['file']}: checksum does not match the pool manifest")
        for line in body.decode("utf-8").splitlines():
            cand = Candidate(**json.loads(line))
            index[cand.candidate_id] = cand
    return index


# --- using ---------------------------------------------------------------------


def span(candidates: list[Candidate]) -> Span:
    """Join consecutive candidates of one source.

    Caption cues split sentences mid-way ("...a 20,000 meter gap between the" /
    "finger and the V flange..."), so one claim often needs two or three cues.
    Raw and corrected cues may be mixed; each ordinal may appear once.
    """
    if not candidates:
        raise PoolError("a span needs at least one candidate")
    ordered = sorted(candidates, key=lambda c: c.ordinal)
    first = ordered[0]

    if len({c.source_id for c in ordered}) != 1:
        raise PoolError("a span cannot cross sources")
    if len({c.modality for c in ordered}) != 1:
        raise PoolError("a span cannot mix modalities")
    ordinals = [c.ordinal for c in ordered]
    if len(set(ordinals)) != len(ordinals):
        raise PoolError(f"ordinal used twice in one span: {ordinals}")
    if ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
        raise PoolError(f"candidates must be consecutive, got ordinals {ordinals}")

    corrected = [c for c in ordered if c.kind == "C"]
    # Cues are fragments of one running sentence; guide lines are separate lines
    # (joined with "\n" so each still matches its line in raw_text).
    sep = " " if first.modality == "speech" else "\n"
    return Span(
        source_id=first.source_id,
        candidate_ids=tuple(c.candidate_id for c in ordered),
        modality=first.modality,
        start_ms=first.start_ms,
        end_ms=ordered[-1].end_ms,
        quote=sep.join(c.text for c in ordered),
        transcript_origin="human" if corrected else first.transcript_origin,
        parent_candidate_ids=tuple(c.parent_candidate_id for c in corrected if c.parent_candidate_id),
    )


def raw_parent(sp: Span, index: dict[str, Candidate]) -> Span | None:
    """The uncorrected span over the same cues, or None if nothing was corrected.

    A workflow that cites a corrected span must also carry this raw span as its
    own Evidence and list it in ``parent_evidence_ids`` (validator V03).
    """
    if not sp.parent_candidate_ids:
        return None
    raw_ids = [cid.replace(":C", ":U") for cid in sp.candidate_ids]
    return span([index[cid] for cid in raw_ids])


def to_evidence(sp: Span, evidence_id: str, *, parent_evidence_ids: tuple[str, ...] = ()) -> dict:
    """A Schema 1.0.0 Evidence record for a span, validated by the shared models."""
    if sp.parent_candidate_ids and not parent_evidence_ids:
        raise PoolError(
            f"{evidence_id}: span contains corrected cues; pass the Evidence ID of raw_parent(span) "
            "as parent_evidence_ids so the caption trace is kept"
        )
    record = {
        "evidence_id": evidence_id,
        "source_id": sp.source_id,
        "modality": sp.modality,
        "locator": {
            "start_ms": sp.start_ms,
            "end_ms": sp.end_ms,
            "page": None,
            "text_span": sp.quote if sp.modality == "text" else None,
        },
        "quote": sp.quote,
        "observation_note": None,
        "asset_uri": None,
        "transcript_origin": sp.transcript_origin,
        "parent_evidence_ids": list(parent_evidence_ids),
    }
    return Evidence.model_validate(record).model_dump(mode="json")


# --- CLI -----------------------------------------------------------------------


def _cmd_build(args: argparse.Namespace) -> int:
    pool = build_pool()
    path = write_pool(pool, Path(args.out) if args.out else POOL_DIR)
    for sid, cands in sorted(pool.items()):
        kinds = {k: sum(1 for c in cands if c.kind == k) for k in "UCT"}
        detail = " ".join(f"{k}={n}" for k, n in kinds.items() if n)
        dupes = sum(1 for c in cands if c.text_span_unique is False)
        print(f"{sid}: {len(cands)} candidates ({detail})" + (f", {dupes} non-unique text spans" if dupes else ""))
    print(f"wrote {_rel(path)}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    index = load_pool()
    missing = [cid for cid in args.candidate_ids if cid not in index]
    if missing:
        print(f"unknown candidate(s): {', '.join(missing)}", file=sys.stderr)
        return 1
    sp = span([index[cid] for cid in args.candidate_ids])
    print(json.dumps(asdict(sp), ensure_ascii=False, indent=2))
    parent = raw_parent(sp, index)
    if parent is not None:
        print("\nraw parent (must also be cited as Evidence):")
        print(json.dumps(asdict(parent), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence_pool", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="(re)build the candidate pool from D1-A inputs")
    p_build.add_argument("--out", help="output directory (default: acquisition/extraction/evidence_pool)")
    p_build.set_defaults(func=_cmd_build)

    p_show = sub.add_parser("show", help="print the span formed by consecutive candidate IDs")
    p_show.add_argument("candidate_ids", nargs="+")
    p_show.set_defaults(func=_cmd_show)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PoolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
