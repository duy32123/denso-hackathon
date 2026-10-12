"""Add the five post-pilot dev sources (SRC_HAAS_0008..0012) to the D1-A data.

Everything curated (titles, presenter, what the video shows, caption fixes and the
basis for each) lives in SOURCES below; the rest is mechanical, so rerunning on a
finished tree changes nothing.  Captions are the uploader's own English WebVTT
files, fetched beforehand with yt-dlp into --captions-dir as <youtube_id>.en.vtt.

    python scripts/add_d1a_dev_sources.py --captions-dir <dir>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from acquisition.preprocessing.captions import parse_vtt, raw_text, sha256_text  # noqa: E402
from acquisition.video_catalog.source_ids import SourceIdAllocator  # noqa: E402

RETRIEVED_AT = "2026-10-12T10:51:00Z"
PRODUCER = "yt-dlp 2026.x + youtube official uploader captions (en)"
DESC = "the video's official YouTube description"

# (cue number, text to replace, replacement, basis)  -- terminology only, cited.
SOURCES = [
    {
        "yt": "DXtocZX8hf0", "title": "Alarm 626 Tool Pocket Slide Error", "duration_ms": 86000,
        "published_at": "2018-08-24T00:00:00Z", "presenter": "Orville Collins", "presenter_role": "Service Engineer",
        "family": "FAM-TOOL-POCKET-ALARM-626", "subsystem": "tool changer - tool pocket up/down travel",
        "subsystem_basis": "curated", "task_type": "troubleshooting", "task_type_basis": "source",
        "machine_family": "", "machine_family_basis": "unknown",
        "symptoms": "alarm 626; tool pocket fails to reach the proper up/down position", "alarm_codes": "626",
        "components": "tool pocket; carousel; pocket air cylinder; air line; pocket up/down proximity switches; pocket up/down solenoid",
        "visible_actions": "yes - screwdriver touch test of a proximity switch; pocket and carousel inspection",
        "reasoning_coverage": "partial - lists causes to rule out in order (air, lines, switches, solenoid) with the reason low air matters",
        "outcome": "yes - command several tool changes to confirm; escalate to the HFO if alarm 626 persists",
        "why": "Alarm-driven diagnosis (explicit code, ordered checks, an escalation point). The narration never names the "
               "tool changer style, so the subsystem is curated, not source-stated, and the family stays isolated.",
        "why_family": "Alarm 626 tool pocket troubleshooting; the narration does not say whether the changer is side-mount or umbrella.",
        "why_no_cross_split": "No holdout source covers an alarm-code diagnosis of a pocket fault: SRC_HAAS_0006 is umbrella-style maintenance and SRC_HAAS_0007 is a generic stuck toolholder call. Both stay untouched.",
        "corrections": [
            (1, "up in", "up and", "self-consistency: the same transcript says \"pocket up and down\" in cues 8, 10 and 11"),
            (3, "several - changes", "several tool changes", "self-consistency: the same sentence ends \"make sure the tool change is working correctly\""),
            (13, "ha spectra outlet", "HFO", "the description ends \"please contact your local HFO\""),
        ],
        "frames": [
            (17500, "Control screen with an 'Automatic Recovery' dialog reading 'Waiting for the pocket to push up'."),
            (21500, "Control screen: Active Alarms list and a red banner '626 TOOL-POCKET SLIDE ERROR'."),
            (35000, "Pneumatics panel with an air pressure gauge and a bank of solenoid valves, beside an 'AIR - LUBRICATION' diagram label."),
            (41000, "Close-up of a pneumatic cylinder with a thin air line, mounted in a cast housing."),
            (61000, "Close-up of a solenoid valve with a thin tool tip pressed into a recess on its face."),
        ],
        "related": [],
    },
    {
        "yt": "cwYsbzAW3r0", "title": "Spindle Troubleshooting", "duration_ms": 236000,
        "published_at": "2018-03-22T00:00:00Z", "presenter": "Andrew", "presenter_role": None,
        "family": "FAM-SPINDLE-TROUBLESHOOTING", "subsystem": "mill spindle (lubrication, heat, noise/vibration, tool sticking)",
        "subsystem_basis": "source", "task_type": "troubleshooting", "task_type_basis": "source",
        "machine_family": "Haas mills", "machine_family_basis": "source",
        "symptoms": "spindle seized; spindle running hot; noise or vibration; tool sticking in the taper", "alarm_codes": "none stated",
        "components": "spindle; lubrication pump; metering valve; sight glass; spindle taper; drive dogs; belt",
        "visible_actions": "partial - pump and sight-glass checks shown, mostly narrated",
        "reasoning_coverage": "strong - each symptom is tied to a probable external cause and what to fix before replacing the spindle",
        "outcome": "partial - ends with the claim that troubleshooting can avoid a spindle replacement; no single verification step",
        "why": "Symptom-to-cause diagnostic flow with strong reasoning, on a subsystem (spindle) the pilot never touched.",
        "why_family": "Spindle symptom triage (seize, heat, noise, stuck tool) before replacement.",
        "why_no_cross_split": "No holdout source covers the spindle. SRC_HAAS_0010 (alarm 254) is a different, alarm-driven task and sits in its own dev family.",
        "corrections": [
            (6, "busier pump", "Bijur pump", "the on-screen overlay \"LUBRICATION - CHECK THE BIJUR PUMP\" shown at 00:00:44"),
            (11, "Mobil SH c6 25", "Mobil SHC 625", "the on-screen Haas parts page \"OIL, REFILL MOBIL SHC 625\" shown at 00:01:08"),
        ],
        "frames": [
            (44000, "Overlay 'LUBRICATION - CHECK THE BIJUR PUMP' over the presenter, who sits beside a white cabinet."),
            (68000, "Haas parts page for 'OIL, REFILL MOBIL SHC 625', part 93-2220A, with the overlay 'ALWAYS USE'."),
            (88000, "Overlay 'LUBRICATION - CHECK THE VALVE BODY' over a close-up of a Bijur Delimon reservoir with MIN/MAX marks."),
            (122000, "Overlay 'OVERHEATING - TOO MUCH OIL - PROPER AMOUNT OF OIL' over a lubrication reservoir with MIN/MAX marks, behind an open door."),
            (164000, "Overlay 'NOISE/VIBRATION - CHECK YOUR TOOLING - SPINDLE IS BALANCED - CHECK ALIGNMENT / TENSION' beside the presenter holding a tool."),
            (205000, "Overlay 'STUCK TOOL - CHECK TOOLING / APPLICATION - CHECK LONG TOOLS - CHECK SPINDLE TEMPERATURE' over the presenter."),
        ],
        "related": [],
    },
    {
        "yt": "M-VcwEodqP0", "title": "Alarm 254 Spindle Motor Overheat", "duration_ms": 90000,
        "published_at": "2018-07-11T00:00:00Z", "presenter": "Orville Collins", "presenter_role": "Service Engineer",
        "family": "FAM-SPINDLE-MOTOR-OVERHEAT-254", "subsystem": "spindle motor thermal protection",
        "subsystem_basis": "source", "task_type": "troubleshooting", "task_type_basis": "source",
        "machine_family": "Haas mills (vertical and horizontal)", "machine_family_basis": "source",
        "symptoms": "alarm 254 spindle motor overheat during a job", "alarm_codes": "254",
        "components": "spindle motor; motor temperature sensor; spindle fan; I/O PCB cable P39; ferrite filter; spindle head cover",
        "visible_actions": "partial - cabinet and spindle-head views while the checks are narrated",
        "reasoning_coverage": "strong - says how the sensor triggers the alarm, then what to rule out",
        "outcome": "partial - escalate to the HFO if the alarm persists; no explicit pass check",
        "why": "Alarm-driven diagnosis with a stated trigger mechanism and a machine-generation branch (next-gen control).",
        "why_family": "Alarm 254 spindle motor overheat.",
        "why_no_cross_split": "No holdout source covers a spindle-motor alarm. SRC_HAAS_0009 shares the word spindle but is a symptom triage, not this alarm.",
        "corrections": [
            (1, "alarmed 2:54 spin the motor overheat", "alarm 254 spindle motor overheat", "the video's own title, \"Alarm 254 Spindle Motor Overheat\""),
            (4, "alarm to 54", "alarm 254", "the title, and the same alarm said correctly in the description (\"a 254 alarm\")"),
            (14, "local hospital outlet", "local HFO", "the description: \"please contact your local HFO\""),
        ],
        "frames": [
            (26500, "Control screen with an orange banner '254 SPINDLE MOTOR OVERHEAT'."),
            (31000, "Main Spindle panel: spindle speed 2700 RPM, spindle power 18.7 KW, Spindle Load bar reading 149%."),
            (40500, "Close-up of a fan inside a sheet-metal housing, shown while the spindle fan is discussed."),
            (64000, "A technician crouches at an open control cabinet; drives, boards and a 40 horsepower vector drive are visible."),
            (66500, "3D model of a circuit board with the connector labelled 'P39'."),
            (78500, "Close-up of a black cable labelled 'THERM PROBE' clamped to a brass fitting."),
        ],
        "related": [],
    },
    {
        "yt": "DgHQtvvf1kI", "title": "Alarm 9973 Unstable Incoming Power", "duration_ms": 181000,
        "published_at": "2018-05-08T00:00:00Z", "presenter": "Andrew Harnett", "presenter_role": "Service Engineer",
        "family": "FAM-INCOMING-POWER-ALARM-9973", "subsystem": "incoming power monitoring (Wye-Delta contactor and I/O PCB)",
        "subsystem_basis": "source", "task_type": "troubleshooting", "task_type_basis": "source",
        "machine_family": "", "machine_family_basis": "unknown",
        "symptoms": "alarm 9973 on screen and machine stops; brownout in the shop", "alarm_codes": "9973",
        "components": "Wye-Delta contactor; auxiliary contacts; I/O PCB; vector drive; incoming power line; voltage stabilizer",
        "visible_actions": "yes - covers removed to show the contactor, cable and I/O PCB",
        "reasoning_coverage": "strong - explains how the machine monitors the contactor and why the alarm usually means unstable power, not a bad part",
        "outcome": "yes - checks end with the brownout conclusion and a power-conditioner recommendation",
        "why": "Electrical, safety-gated diagnosis (power down and wait for the vector drive light first) with a clear 'do not replace' conclusion and a branch for software versions.",
        "why_family": "Alarm 9973 incoming-power diagnosis.",
        "why_no_cross_split": "No holdout source covers machine electrical or power alarms.",
        "corrections": [
            (1, "the 997 three-alarm", "the 9973 alarm", "the video's own title, \"ALARM 9973 Unstable Incoming Power\""),
            (2, "wide delta contactor", "Wye-Delta contactor", "the description: \"does not require a Wye-Delta replacement\""),
            (7, "wide delta", "Wye-Delta", "the description: \"does not require a Wye-Delta replacement\""),
            (10, "997 three alarm", "9973 alarm", "the title"),
            (19, "997 three alarm", "9973 alarm", "the title"),
            (25, "why delta contact or", "Wye-Delta contactor", "the description's \"Wye_Delta_Contactor_Troubleshooting_Guide\" link and \"Wye-Delta\""),
        ],
        "frames": [
            (3000, "Title card: 'HAAS AUTOMATION SERVICE VIDEO - ALARM 9973 - INVALID POWER CONTROL STATE DETECTED'."),
            (51000, "Close-up of a contactor block with the overlay label 'AUXILIARY CONTACTS'."),
            (66000, "Control screen with a red banner for alarm 9973 whose visible text includes 'INVALID POWE' (the end is cut off)."),
            (79000, "POWER ON and POWER OFF buttons with the caption 'ALARM 9973 - POWER DOWN THE MACHINE. WAIT UNTIL VECTOR DRIVE LIGHT TURNS OFF.'"),
            (81000, "Vector drive label 'DANGER! High voltage! No user serviceable parts inside. Light must be out before replacing drive' with the same caption."),
            (87000, "Hands removing a metal cover; caption 'ALARM 9973 - REMOVE COVERS FROM THE WYE/DELTA CONTRACTOR AND I/O PCB.'"),
            (99000, "Two stacked contactors and a terminal block; caption about the Wye/Delta auxiliary contacts being connected to the I/O PCB and no arcing."),
        ],
        "related": [],
    },
    {
        "yt": "ezplV3447C8", "title": "X-Axis Mill Waycover Replacement", "duration_ms": 411000,
        "published_at": "2018-06-12T00:00:00Z", "presenter": "Orville Collins", "presenter_role": "Service Engineer",
        "family": "FAM-X-AXIS-WAYCOVER-REPLACEMENT", "subsystem": "X-axis way covers (mill)",
        "subsystem_basis": "source", "task_type": "maintenance", "task_type_basis": "source",
        "machine_family": "Haas VMC", "machine_family_basis": "source",
        "symptoms": "popping noise from way covers; leaking way cover section; damaged wiper", "alarm_codes": "none stated",
        "components": "x-axis way cover; wiper; retainer; guide bar; gasket; RTV silicone; red-eye grease; linear guides",
        "visible_actions": "yes - full wiper and way-cover replacement shown for old and new styles",
        "reasoning_coverage": "partial - explains why loose rails and missing lubrication damage the covers, then mostly procedure",
        "outcome": "yes - release e-stop, reset, jog slowly to confirm the cover does not bind",
        "why": "Long physical replacement procedure with a revision branch (old vs. new style, Aug 2013 change) and tooling list.",
        "why_family": "X-axis way cover and wiper replacement.",
        "why_no_cross_split": "No holdout source covers way covers or enclosure parts.",
        "corrections": [
            (10, "weight covers", "way covers", "self-consistency: \"way covers\" is used correctly in cues 2-3 of this transcript"),
            (8, "pulled away covers back", "pull the way covers back", "self-consistency: \"way covers\" in cues 2-3 and the imperative \"inspect ... tighten\" that follows"),
            (19, "he stopped the machine", "e-stop the machine", "self-consistency: cue 50 says \"put the machine in e-stop\""),
            (38, "away cover one leaf", "the way cover one leaf", "self-consistency: \"way cover\" in cues 2-3"),
            (57, "away covers once", "way covers once", "self-consistency: \"way covers\" in cues 2-3"),
        ],
        "frames": [
            (124000, "The presenter, in work gloves, separates way cover sections laid out on a bench."),
            (148000, "A black wiper strip with a row of holes held against the edge of a sheet-metal part."),
            (209000, "A hand presses a black wiper strip along the top edge of a sheet-metal section."),
            (238000, "A red grease cartridge held over the open machine bed; the linear guides carry red grease."),
            (252000, "A way cover section being fitted over the ball screw and linear guides."),
            (330000, "Caption 'PARTS/TOOLS REQUIRED': waycover kit (new style), #21 drill bit, 10/32 tap, RTV silicone, RED-i grease, scraper."),
            (352000, "Graphic of a #21 drill bit and a 10/32 tap over a way cover mounting bar."),
        ],
        "related": [],
    },
]


def _jdump(obj, **kw) -> str:
    return json.dumps(obj, ensure_ascii=False, **kw)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _sha_bytes(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_transcripts(sid: str, spec: dict, vtt: str) -> tuple[list[dict], list[dict]]:
    raw = parse_vtt(vtt)
    corrected = [dict(u) for u in raw]
    blocks = []
    for cue, old, new, basis in spec["corrections"]:
        u = corrected[cue - 1]
        if u["text"].count(old) != 1:
            raise SystemExit(f"{sid} cue {cue}: {old!r} not found exactly once in {u['text']!r}")
        before = u["text"]
        u["text"] = before.replace(old, new)
        blocks.append((u, before, basis))
    head = {"source_id": sid, "transcript_origin": "official_caption", "timestamp_basis": "original_video_ms"}
    base = ROOT / "acquisition/preprocessing/transcripts" / sid
    _write(base / "raw.json", _jdump({**head, "producer": PRODUCER, "processed_at": RETRIEVED_AT, "utterances": raw}, indent=2) + "\n")
    _write(base / "corrected.json", _jdump({**head, "producer": PRODUCER, "processed_at": RETRIEVED_AT, "utterances": corrected}, indent=2) + "\n")
    if blocks:
        out = ["# Corrections applied 2026-10-12 (terminology only; every one cites a primary source", "# or the same transcript's own usage; timestamps and sentence structure are unchanged).", ""]
        for u, before, basis in blocks:
            out += [f"utterance start_ms={u['start_ms']} end_ms={u['end_ms']}", "", f"- {before}", f"+ {u['text']}", "", f"Basis: {basis}.", ""]
    else:
        out = ["# No corrections applied 2026-10-12.", "# corrected.json is byte-identical in text to raw.json; no caption error was found that a", "# primary source or the transcript's own usage could settle.", ""]
    _write(base / "corrections.diff", "\n".join(out))
    return raw, corrected


def source_record(sid: str, spec: dict, raw: list[dict]) -> dict:
    yt = spec["yt"]
    text = raw_text(raw)
    return {
        "access_note": (
            f"Public video on the official 'Haas Automation, Inc.' YouTube channel (https://www.youtube.com/watch?v={yt}), "
            "mirrored at the canonical URL above, which is built from the same video id and was not fetched (haascnc.com "
            "returns a Cloudflare challenge to automated requests). Publisher, presenter and role are taken from the "
            "channel's own video description. Manual (non-auto) English captions downloaded via yt-dlp "
            "(official_caption). No video file is committed; a 1080p video-only stream is kept locally (gitignored) "
            "for keyframe extraction. Redistribution not established -- do not redistribute retained "
            "caption text outside this pilot."
        ),
        "asset_uri": None,
        "content_sha256": sha256_text(text),
        "duration_ms": spec["duration_ms"],
        "language": "en",
        "presenter": spec["presenter"],
        "presenter_role": spec["presenter_role"],
        "published_at": spec["published_at"],
        "publisher": "Haas Automation, Inc.",
        "raw_text": text,
        "related_source_ids": spec["related"],
        "retrieved_at": RETRIEVED_AT,
        "source_id": sid,
        "source_kind": "official_service_video",
        "source_type": "real",
        "title": spec["title"],
        "url": f"https://www.haascnc.com/video/service/{yt}.html",
    }


def catalog_row(cand: str, sid: str, spec: dict, text_sha: str, fields: list[str]) -> dict:
    yt = spec["yt"]
    row = dict.fromkeys(fields, "")
    row.update(
        candidate_id=cand, source_id=sid, title=spec["title"], canonical_url=f"https://www.haascnc.com/video/service/{yt}.html",
        source_kind="official_service_video", publisher="Haas Automation Inc.", presenter=spec["presenter"],
        presenter_role=spec["presenter_role"] or "", published_at=spec["published_at"], retrieved_at="2026-10-12",
        language="en", duration_ms=str(spec["duration_ms"]), manufacturer="Haas Automation", manufacturer_basis="source",
        machine_family=spec["machine_family"], machine_family_basis=spec["machine_family_basis"],
        machine_model="", machine_model_basis="unknown", subsystem=spec["subsystem"], subsystem_basis=spec["subsystem_basis"],
        task_type=spec["task_type"], task_type_basis=spec["task_type_basis"], symptoms=spec["symptoms"], symptoms_basis="source",
        alarm_codes=spec["alarm_codes"], alarm_codes_basis="source", components=spec["components"], components_basis="source",
        audio_quality="clear narrated voiceover", video_quality="1080p stream inspected for keyframe selection",
        caption_status="official manual English caption", visible_actions=spec["visible_actions"],
        reasoning_coverage=spec["reasoning_coverage"], outcome_or_verification_present=spec["outcome"],
        access_status=f"accessible - public YouTube (https://www.youtube.com/watch?v={yt}); haascnc.com page not fetched (Cloudflare)",
        access_note="Publisher, presenter and role from the channel's own video description; operator authorization for download recorded in docs/data_rights_register.md",
        content_sha256=text_sha, near_duplicate_group=spec["family"], proposed_split="dev", selection_status="selected",
        selection_reason=spec["why"],
    )
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captions-dir", required=True, type=Path)
    args = ap.parse_args()

    alloc = SourceIdAllocator(str(ROOT / "data/catalogs/haas_d1a_source_id_registry.json"))
    src_path = ROOT / "data/sources/haas_pilot_sources.jsonl"
    have = {json.loads(l)["source_id"] for l in src_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    inv_path = ROOT / "acquisition/preprocessing/haas_d1a_media_inventory.jsonl"
    csv_path = ROOT / "acquisition/video_catalog/haas_d1a_source_candidates.csv"
    split_path = ROOT / "data/splits/haas_d1a_split_manifest.json"

    new_sources, inv_rows, csv_rows, families = [], [], [], []
    with csv_path.open(encoding="utf-8", newline="") as f:
        fields = csv.DictReader(f).fieldnames
    for n, spec in enumerate(SOURCES):
        sid = alloc.get_or_create(f"https://www.haascnc.com/video/service/{spec['yt']}.html")
        if sid in have:
            continue
        vtt = (args.captions_dir / f"{spec['yt']}.en.vtt").read_text(encoding="utf-8")
        raw, _ = build_transcripts(sid, spec, vtt)
        rec = source_record(sid, spec, raw)
        new_sources.append(rec)
        csv_rows.append(catalog_row(f"CAND-{13 + n:03d}", sid, spec, rec["content_sha256"], fields))
        base = ROOT / "acquisition/preprocessing/transcripts" / sid
        common = {"source_id": sid, "created_at": RETRIEVED_AT, "local_start_ms": 0, "local_end_ms": spec["duration_ms"],
                  "original_start_ms": 0, "original_end_ms": spec["duration_ms"]}
        inv_rows.append({**common, "artifact_id": f"{sid}_TRANSCRIPT_RAW", "artifact_type": "transcript_raw",
                         "access_status": "retained (text transcript only, per operator authorization); no video/audio binary committed",
                         "content_sha256": _sha_bytes(base / "raw.json"), "notes": "transcript_origin=official_caption; timestamps are original-video ms, unchanged from YouTube caption cues",
                         "parent_artifact_id": None, "producer": "yt-dlp official uploader captions (en) -- no ASR run", "producer_version": "yt-dlp 2026.x",
                         "storage_uri": f"acquisition/preprocessing/transcripts/{sid}/raw.json"})
        inv_rows.append({**common, "artifact_id": f"{sid}_TRANSCRIPT_CORRECTED", "artifact_type": "transcript_corrected",
                         "access_status": "retained (text transcript only)", "content_sha256": _sha_bytes(base / "corrected.json"),
                         "notes": f"{len(spec['corrections'])} terminology correction(s); see corrections.diff" if spec["corrections"] else "text identical to raw.json; corrections.diff records that no change was made",
                         "parent_artifact_id": f"{sid}_TRANSCRIPT_RAW",
                         "producer": "manual review (terminology corrections, cited)" if spec["corrections"] else "manual review (no corrections needed)",
                         "producer_version": "n/a", "storage_uri": f"acquisition/preprocessing/transcripts/{sid}/corrected.json"})
        media = ROOT / "data/media/haas_d1a" / f"{sid}_{spec['yt'].replace('-', '').replace('_', '')}_1080p.mp4"
        inv_rows.append({**common, "artifact_id": f"{sid}_VIDEO_1080P", "artifact_type": "video_1080p_local",
                         "access_status": "retained locally only, under operator session authorization; not committed to git (data/media/ is gitignored); not redistributed",
                         "content_sha256": _sha_bytes(media) if media.exists() else None,
                         "notes": "downloaded solely to extract the keyframes of this source; kept out of version control per repo convention and D1-A rights rules",
                         "parent_artifact_id": None, "producer": "yt-dlp format 137/299 (1080p, video-only, no audio)", "producer_version": "yt-dlp 2026.x",
                         "storage_uri": f"data/media/haas_d1a/{media.name} (gitignored, not committed)"})
        for ms, note in spec["frames"]:
            kf = ROOT / f"acquisition/preprocessing/keyframes/{sid}/kf_{ms:07d}.jpg"
            kf.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ms / 1000:.3f}", "-i", str(media),
                            "-frames:v", "1", "-q:v", "3", str(kf)], check=True)
            inv_rows.append({**common, "artifact_id": f"{sid}_KF_{ms:07d}", "artifact_type": "keyframe",
                             "access_status": "retained and committed (small derived JPEG, no video bytes)",
                             "content_sha256": _sha_bytes(kf), "local_start_ms": ms, "local_end_ms": ms,
                             "original_start_ms": ms, "original_end_ms": ms,
                             "notes": f"Chosen by reading the 1080p frame against its claim (AI vision review, no human sign-off yet). Shows: {note}",
                             "parent_artifact_id": f"{sid}_VIDEO_1080P", "producer": "ffmpeg -ss <t> -frames:v 1",
                             "producer_version": "ffmpeg 9.0", "storage_uri": f"acquisition/preprocessing/keyframes/{sid}/{kf.name}"})
        families.append({
            "near_duplicate_group": spec["family"], "split": "dev", "source_ids": [sid],
            "members": [{"source_id": sid, "role": "official_service_video"}],
            "why_family": spec["why_family"], "why_no_cross_split": spec["why_no_cross_split"],
        })
    if not new_sources:
        print("nothing to add")
        return

    with src_path.open("a", encoding="utf-8", newline="") as f:
        for rec in new_sources:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    with inv_path.open("a", encoding="utf-8", newline="") as f:
        for row in inv_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    raw_csv = csv_path.read_bytes()
    eol = "\r\n" if b"\r\n" in raw_csv else "\n"
    guide = dict.fromkeys(fields, "")
    guide.update(
        candidate_id="CAND-018", title="Wye-Delta Contactor Troubleshooting Guide (haascnc.com DIY page)",
        canonical_url="https://www.haascnc.com/service/troubleshooting-and-how-to/troubleshooting/Wye_Delta_Contactor_Troubleshooting_Guide.html",
        source_kind="service_document", publisher="Haas Automation Inc.", retrieved_at="2026-10-12", language="en",
        manufacturer="Haas Automation", manufacturer_basis="source", selection_status="deferred",
        access_status="not retrieved - haascnc.com returns a Cloudflare challenge to automated requests",
        access_note="Linked from the official description of SRC_HAAS_0011 as the related DIY troubleshooting page",
        selection_reason="Probable companion guide of SRC_HAAS_0011. Not selected until its text is retrieved by ordinary manual browsing, as was done for TG0128 (SRC_HAAS_0002); no source_id allocated.",
    )
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator=eol)
        for row in csv_rows + [guide]:
            w.writerow(row)

    # Text insertion, not a json.dumps round trip, so the manifest keeps its layout.
    text = split_path.read_text(encoding="utf-8")
    blocks = ",\n".join(
        "    {\n"
        f'      "near_duplicate_group": {_jdump(fam["near_duplicate_group"])},\n'
        '      "split": "dev",\n'
        f'      "source_ids": [{_jdump(fam["source_ids"][0])}],\n'
        '      "members": [\n'
        f'        {{"source_id": {_jdump(fam["source_ids"][0])}, "role": "official_service_video"}}\n'
        "      ],\n"
        f'      "why_family": {_jdump(fam["why_family"])},\n'
        f'      "why_no_cross_split": {_jdump(fam["why_no_cross_split"])}\n'
        "    }"
        for fam in families
    )
    rule = ("2026-10-12: five more official service videos (SRC_HAAS_0008..0012) added to dev, each in its own "
            "family; holdout sources SRC_HAAS_0006 and SRC_HAAS_0007 were not touched.")
    fam_end, rules_end = '\n  ],\n  "excluded_not_split"', "\n  ]\n}\n"
    assert text.count(fam_end) == 1 and text.count(rules_end) == 1
    text = text.replace(fam_end, f",\n{blocks}{fam_end}").replace(rules_end, f",\n    {_jdump(rule)}{rules_end}")
    split_path.write_bytes(text.encode("utf-8"))
    # The allocator saves in text mode, which writes CRLF on Windows; the repo's copy is LF.
    registry = Path(alloc.registry_path)
    registry.write_bytes(registry.read_bytes().replace(b"\r\n", b"\n"))
    print("added", [r["source_id"] for r in new_sources])


if __name__ == "__main__":
    main()
