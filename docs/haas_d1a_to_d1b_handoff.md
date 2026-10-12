# D1-A → D1-B Handoff — Haas SMTC Pilot

D1-A status: **complete**. All artifacts required by the acceptance criteria exist,
validate, and are checksum-backed; both guide bodies are now retained; keyframes exist
for all 3 dev videos. One content-overlap observation is flagged for D1-B's awareness
(section 13) rather than concealed. No claims, workflows, technical validation, RAG, or
fine-tuning were created under D1-A.

## 1. Selected development sources

| source_id | Title | Canonical URL | Kind | Family |
|---|---|---|---|---|
| SRC_HAAS_0001 | Side-Mount Tool Changer Double Arm Troubleshooting | https://www.haascnc.com/video/service/TmjjC7BDDag.html | official_service_video | FAM-DOUBLE-ARM-TROUBLESHOOTING |
| SRC_HAAS_0002 | SMTC Double Arm/Cambox Troubleshooting Guide — TG0128 | https://www.haascnc.com/service/troubleshooting-and-how-to/troubleshooting/Side_Mount_Tool_Changer_SMTC_Double_Arm_Troubleshooting_Guide.html | service_document | FAM-DOUBLE-ARM-TROUBLESHOOTING |
| SRC_HAAS_0003 | Tool Changer Recovery; Haas SMTC | https://www.haascnc.com/video/service/2bra6qm6wm4.html | official_service_video | FAM-SMTC-RECOVERY |
| SRC_HAAS_0004 | SMTC Manual Recovery how-to (Mill) | https://www.haascnc.com/service/troubleshooting-and-how-to/how-to/mill---side-mount-tool-changer---manual-recovery.html | service_document | FAM-SMTC-RECOVERY |
| SRC_HAAS_0005 | Replace a Tool Pocket on Your Haas SMTC | https://www.haascnc.com/video/service/cs-BvWsKXyU.html | official_service_video | FAM-SMTC-POCKET-REPAIR |

Three official_service_video pilots (SRC_HAAS_0001, _0003, _0005), each in its own
near-duplicate family, per the D1-A prompt's "three-video pilot" framing.

### Playable video links (checked 2026-09-24)

The haascnc.com video pages above are not reliable locators for a person: in a normal browser
the SRC_HAAS_0005 page returned 404, and automated requests get a Cloudflare challenge (403).
The same three videos play on YouTube. Each link below was checked against YouTube's own page:
title, channel (Haas Automation, Inc.) and exact length against the `duration_ms` recorded here.

| source_id | Watch | Length (YouTube = `duration_ms`) |
|---|---|---|
| SRC_HAAS_0001 | https://www.youtube.com/watch?v=TmjjC7BDDag | 191 s |
| SRC_HAAS_0003 | https://www.youtube.com/watch?v=2bRa6qm6wm4 | 360 s |
| SRC_HAAS_0005 | https://www.youtube.com/watch?v=cs-BvWsKXyU | 261 s |

**YouTube video IDs are case-sensitive, and SRC_HAAS_0003's is stored in lowercase.** `Source.url`,
the source candidate catalog and the source-ID registry all hold `2bra6qm6wm4`, which YouTube reports
as "Video unavailable"; the correct ID has a capital R (`2bRa6qm6wm4`, which is also what the page's own
`videoID` meta reads in `haas_d1a_quality_report.md`). The canonical data is checksum-backed and the
registry keys on the URL, so correcting it is a coordinated change for Team 1, not done here. Until
then, use the links in this table. `acquisition/extraction/review.py` builds worklist links from
`Source.url`, so regenerating `review_worklist_real_wf_0002_0003.md` reproduces the wrong-case links
until the data is corrected.

## 2. Reserved holdout families

| source_id | Title | Family | Reason isolated |
|---|---|---|---|
| SRC_HAAS_0006 | CT STYLE Umbrella/Carousel Tool Changer Maintenance | FAM-UMBRELLA-CT-MAINTENANCE | Different tool-changer subsystem (umbrella/carousel, not side-mount) |
| SRC_HAAS_0007 | Stuck Toolholder??? Orville Makes a Service Call | FAM-STUCK-TOOLHOLDER-GENERIC | Subsystem not explicitly stated; isolated rather than guessed into either family |

Both received eligibility metadata only (title, `duration_ms`, publisher, upload date via
yt-dlp/oEmbed). No captions, transcripts, or guide fetches were performed against them.

## 3. Rejected candidates and reasons

| Candidate | Reason |
|---|---|
| TG0127 (Carousel and Pocket Troubleshooting Guide) | Every fetch this session returned HTTP 403 (Cloudflare); content could not be inspected, so excluded rather than selected on title alone |
| TG0057 (DC-Series Tool Changer Troubleshooting Guide) | Same — blocked, not inspected; also a candidate holdout family that wasn't needed since two were already reserved |
| Umbrella online-manual troubleshooting guide | Same — blocked, not inspected; would have been SRC_HAAS_0006's companion guide |
| O4hmziNXEXQ (SMTC Double Arm Maintenance) | Same physical subsystem (double arm) as SRC_HAAS_0001 — selecting both risked two dev picks on the same underlying failure point rather than meaningfully different tasks |
| nkqpeOQotb0 (Maintenance Checklist) | Likely overlaps O4hmziNXEXQ/SRC_HAAS_0001 diagnostic content; excluded as redundant once 3 meaningfully-different picks existed |
| qy31u40w2ei ("Tool Changer Recovery; Umbrella-Style", ID from a search snippet) | oEmbed lookup failed against this ID — could not confirm it resolves to a real, current video; not used |

Full detail (per-requirement failure reasons) in
`acquisition/video_catalog/haas_d1a_source_candidates.csv`, rows CAND-008..CAND-012.

## 4. Source IDs and canonical URLs

See table in section 1 and 2 above; also in `data/sources/haas_pilot_sources.jsonl` (dev)
and `data/sources/haas_pilot_holdout_sources.jsonl` (holdout).

## 5. Direct guide/video relationships

- SRC_HAAS_0001 ↔ SRC_HAAS_0002 (curated: same subsystem/task, not a literal page embed —
  no `<iframe>`/`videoID` marker was found on the guide page's own markup).
- SRC_HAAS_0003 ↔ SRC_HAAS_0004 (curated, same basis).
- SRC_HAAS_0005 has no confirmed companion guide.

## 6. Metadata provenance and unknown fields

Canonical `Source` records carry only the 17 Schema 1.0.0 fields (no catalog-only
fields). Richer classification (manufacturer, subsystem, task_type, symptoms,
alarm_codes, components) with a `*_basis` (`source`/`curated`/`unknown`) column per
field lives in `acquisition/video_catalog/haas_d1a_source_candidates.csv` — this is
catalog-only, per D1-A prompt section 6, and must not be copied into `Source` as
unknown keys.

Notable `unknown`/`null` fields left honestly empty: `presenter`/`presenter_role` for
SRC_HAAS_0001 (video is anonymous narration) and SRC_HAAS_0005 (`presenter_role` — the
page that might state a role was inaccessible this session). Both guide bodies
(SRC_HAAS_0002, SRC_HAAS_0004) are now fully populated: `raw_text`/`content_sha256` were
filled after the operator relayed each page's visible text from the same public URL once
automated re-fetch stayed blocked
(`content_sha256=a8a47506a115f128e57290179fba3a874117c5f52ac8c8488ce065acc0f4ebb6` for
SRC_HAAS_0002, `66454ed72f033d500a25df30bdd3db84939b0411a6ed32ab9cd9e206f3aa0109` for
SRC_HAAS_0004).

## 7. Rights and access limitations

Full detail in `docs/data_rights_register.md`. Summary: no video/audio binaries were
downloaded or retained for any source. Only official YouTube caption text for the 3 dev
videos was retained (under the operator's session authorization), hashed, and stored.
`asset_uri` is `null` on every record. Redistribution outside this pilot is not
established.

## 8. Transcript origin and correction status

All 3 dev videos: `transcript_origin=official_caption` (manual, uploader-provided
English captions — not YouTube auto-captions). Raw transcript preserved unchanged at
`acquisition/preprocessing/transcripts/<source_id>/raw.json`; `corrected.json` is
byte-identical this session (no corrections were made); `corrections.diff` records that
explicitly. One suspected numeric caption artifact was found (SRC_HAAS_0001, "20,000
meter gap" at 00:02:26.100, almost certainly a mis-punctuated feeler-gauge spec) and was
**left uncorrected** pending primary-source confirmation — see
`docs/haas_d1a_quality_report.md`.

## 9. Media/locator availability

Every `Source.url` is a public, directly resolvable locator (haascnc.com page or, where
that page could not be reconfirmed this session, the equivalent public YouTube URL is in
`access_note`). For the 3 dev videos, a 1080p (full-HD) video-only stream (upgraded from
an initial 144p pass once production-quality keyframes were requested) was downloaded
locally under operator authorization solely to extract keyframes; it is kept under
`data/media/haas_d1a/` (gitignored per the repo's own convention) and is **not**
committed or redistributed — its hash is recorded in the inventory for provenance only.
9 keyframes (3 per dev video) were extracted at transcript-identified action/verification
moments **at full 1080p** (each 130–430 KB, vs. ~8 KB at the initial 144p pass), hashed,
committed under `acquisition/preprocessing/keyframes/<source_id>/`, and visually
opened/verified this session (see `docs/haas_d1a_quality_report.md`) — e.g. the alarm
text in `SRC_HAAS_0003/kf_0065500.jpg` is now individually legible character-by-character.
`acquisition/preprocessing/haas_d1a_media_inventory.jsonl` inventories all of this: 6
transcript rows (raw + corrected per dev video), 3 local-video provenance rows, and 9
keyframe rows (18 total).

## 10. Duplicate-family assignments

See `data/splits/haas_d1a_split_manifest.json` — 5 families total (3 dev, 2 holdout),
each with an explicit `why_no_cross_split` statement. Programmatically confirmed zero
overlap between dev and holdout `source_id` sets
(`acquisition/validation/validate_d1a_extra.py::check_no_split_leakage`).

## 11. Subsystem coverage assessment

Side-Mount Tool Changer (SMTC) content on haascnc.com covers three genuinely different
tasks with real diagnostic/procedural depth (troubleshooting, alarm recovery, physical
part replacement), each backed by an official manual-caption transcript with specific,
checkable claims (a measurable gap spec, an alarm code, a verification step). Two
additional families (umbrella/carousel-style, and an unclassified toolholder issue) are
available and reserved as holdout, supporting a genuine dev/holdout split rather than a
single scraped family repeated three ways.

## 12. Scope decision

**SMTC/tool-changer should remain the pilot subsystem.** Evidence supports it: 3
qualifying, meaningfully-different dev videos with official captions, explicit
diagnostic reasoning, at least one explicit alarm code, and ≥2 untouched holdout
families from the same manufacturer/domain. The one open question is whether the 5
candidates blocked by Cloudflare this session (TG0127, TG0057, the umbrella online
manual, and full body verification of TG0128/manual-recovery) would change this
assessment — nothing seen so far suggests they would.

## 13. Known blockers

1. **haascnc.com remains Cloudflare-blocked for automated requests from this session**
   (every automated fetch attempt to the domain returned HTTP 403 "Just a moment...").
   **Resolved via manual retrieval:** both affected guide pages (SRC_HAAS_0002 / TG0128
   and SRC_HAAS_0004 / manual-recovery how-to) were opened by the operator in a normal
   browser and their text relayed, then retained and hashed here. No automated bypass of
   the Cloudflare interstitial was performed or attempted.
2. **Resolved this session:** 9 keyframes (3 per dev video) were extracted from
   locally-downloaded low-resolution video streams and committed; see section 9.
   Full-resolution clips (as opposed to single keyframes) were not produced — a smaller,
   deliberate scope reduction, since keyframes already give D1-B a visual anchor at each
   cited timestamp.
3. **Resolved this session:** the "20,000 meter gap" caption artifact in SRC_HAAS_0001
   was corrected to "0.020 in (0.51 mm) gap" with an auditable diff citing TG0128's own
   stated spec (0.014–0.020 in). See
   `acquisition/preprocessing/transcripts/SRC_HAAS_0001/corrections.diff`.
4. **Content-overlap observation, not a blocker:** SRC_HAAS_0004's 7-step recovery
   procedure is word-for-word identical to the "MANUAL RECOVERY HOW TO" section already
   reproduced inside TG0128 (SRC_HAAS_0002). Both correctly stay in `dev` — this is not a
   split-leakage issue — but D1-B should dedup this shared procedure text rather than
   treat the two Sources as independently corroborating it.

## 14. Exact files D1-B should consume

- `data/sources/haas_pilot_sources.jsonl` — the 5 canonical dev Source records.
- `acquisition/preprocessing/transcripts/<source_id>/{raw,corrected}.json` — timestamped
  transcripts for SRC_HAAS_0001, SRC_HAAS_0003, SRC_HAAS_0005.
- `acquisition/preprocessing/keyframes/<source_id>/kf_<ms>.jpg` — 3 visual anchors per
  dev video, filename encodes the original-video millisecond timestamp.
- `data/splits/haas_d1a_split_manifest.json` — family/split assignments.
- `acquisition/video_catalog/haas_d1a_source_candidates.csv` — full catalog with
  provenance-basis columns, for any Context/metadata_provenance construction.
- Do **not** consume `data/sources/haas_pilot_holdout_sources.jsonl` for anything beyond
  confirming what is reserved — it must not inform workflow construction.
- Do **not** expect `data/media/haas_d1a/*.mp4` to exist for anyone else — it is a local,
  gitignored processing input, not a handoff artifact.
- `acquisition/export/haas_pilot_dev_bundle/` and
  `acquisition/export/haas_pilot_holdout_bundle/` — matching `manifest.json` +
  `sources.jsonl` + empty `workflows.jsonl` for each split (`dataset_split=dev` and
  `dataset_split=holdout` respectively), both independently validated via
  `knowflow-contracts validate`. This mirrors the Team 1 plan document's final handoff
  checklist item ("bundle real/dev dùng demo và bundle real/holdout phục vụ evaluator;
  mỗi bundle đủ manifest, sources, workflows") — D1-B/D2-A should later populate
  `workflows.jsonl` in each bundle in place, not create a parallel structure.

## 15. Checksums for handoff artifacts (sha256)

```
e705acc5dba6653e07bdf5c7ebc615f82bd7ff92a9d4c1626021572e13a11b86  data/sources/haas_pilot_sources.jsonl
1b448464affdbdecc7dd70abe43decaba4d1c61f9ada03af1575864ed8a75b98  data/sources/haas_pilot_holdout_sources.jsonl
0ce78038ce5abd07b74d2fe77d650e84d40f5bcd9a76572894ef6909f54ec1e9  data/splits/haas_d1a_split_manifest.json
ed4380dde64ba34ad3c8492668c1107d9efc6733340bed62e4c75a5d615c90c5  data/catalogs/haas_d1a_source_id_registry.json
ac2c7531cc973b93d90d2307f0c78b2f0409683d752e8a15a25bf76f1139c8b8  acquisition/video_catalog/haas_d1a_source_candidates.csv
57c0d17094db3d40870d9fac09e36f2f16b54c68698f1fded08aadc9081cf819  acquisition/export/haas_pilot_dev_bundle/manifest.json
e705acc5dba6653e07bdf5c7ebc615f82bd7ff92a9d4c1626021572e13a11b86  acquisition/export/haas_pilot_dev_bundle/sources.jsonl
52bb761d1cbd43770c91258147f09d2f702a9498c76498ee3f4c145c8cc87aee  acquisition/export/haas_pilot_holdout_bundle/manifest.json
1b448464affdbdecc7dd70abe43decaba4d1c61f9ada03af1575864ed8a75b98  acquisition/export/haas_pilot_holdout_bundle/sources.jsonl
db3a2bdca3dfae6a8cffd240f8cb82f798c05e42d91a24d9ee08a1823fb96bbd  acquisition/preprocessing/haas_d1a_media_inventory.jsonl
3093e3abd1c2c609fa3b0abd3d87bf9831457607a41bfb04f3daf6c961701d48  docs/data_rights_register.md
ffea53949ad3babfa4d8fbde486960c991104c3b0da977e2b76ea44c1221a6d9  docs/haas_d1a_quality_report.md
```

Per-keyframe and per-video-provenance hashes are in
`acquisition/preprocessing/haas_d1a_media_inventory.jsonl` (18 rows) rather than repeated
here.

## 16. Commands to validate or regenerate D1-A outputs

```bash
cd denso-hackathon
python -m pip install -e ".[dev]"

# schema validation of both bundles (real check, this repo's own validator):
knowflow-contracts validate acquisition/export/haas_pilot_dev_bundle acquisition/export/haas_pilot_holdout_bundle -v

# unit tests (ID allocator + extra D1-A checks) and the repo's own contract tests:
pytest -q

# recompute a checksum to spot-check section 15:
python -c "import hashlib;print(hashlib.sha256(open('data/sources/haas_pilot_sources.jsonl','rb').read()).hexdigest())"
```

## 17. WP2 second pass (2026-09-14) — new for D1-B/D1-C

A second, full line-by-line re-read of all 3 dev transcripts plus a keyframe-coverage
review (branch `team1/pilot-workflows-0001-0003`) found and fixed more caption artifacts
of the same kind as the original gap-spec fix, and added 11 new keyframes. Full detail in
`docs/haas_d1a_quality_report.md`'s "Second QC pass" section. Two things D1-B/D1-C should
know:

1. **The evidence pool changed.** `SRC_HAAS_0001`, `SRC_HAAS_0003` and `SRC_HAAS_0005` each
   gained new `C####` corrected-cue candidates. This does **not** renumber any existing
   `U####` candidate (positional, tied to array index) — any workflow already citing raw
   cues from these sources is unaffected. `REAL_WF_0001` (already reviewed/exported) was
   not touched.
2. **5 new SRC_HAAS_0005 keyframes are unwired media**, not yet cited by any claim:
   `kf_0028000.jpg` (E-stop press), `kf_0065000.jpg` (removing a tool from the carousel),
   `kf_0076000.jpg` (marking the disc for reinstallation), `kf_0158000.jpg` (applying
   grease to the pocket slider), `kf_0222000.jpg` (reinstalling with a pneumatic tool near
   the numbered carousel). `REAL_WF_0001` is already reviewed and exported, so
   incorporating these means a revision 2 (new `observed` claims, re-review, re-export) —
   left for D1-B/D1-C to decide, not done here.

## 18. Keyframe evidence hardening (2026-09-14) — corrective pass, new for D1-B/D1-C

A corrective pass (branch `team1/d1a-keyframe-evidence-hardening`) found that several
keyframes were visually related to their claims but did not actually prove them — selected
by transcript-cue proximity rather than by reading the pixels. Full diagnosis, method,
calibration and per-frame verdicts: `docs/keyframe_evidence_review.md`,
`docs/keyframe_selection_method.md`, `docs/keyframe_calibration_report.md`,
`docs/keyframe_capability_audit.md`. Structured ledgers:
`data/keyframes/keyframe_candidates.jsonl`, `keyframe_selections.jsonl`,
`keyframe_replacements.jsonl`, `keyframe_review.jsonl`.

**Changed evidence artifacts, all 20 keyframes re-audited:**

| Artifact | Change | Where |
|---|---|---|
| `REAL_WF_0002_CL_017` visual evidence (`kf_0146100.jpg`) | **Removed.** No feeler gauge exists anywhere in the surrounding 8.75s window (dense-resampled, 36 frames); the step's transcript claim is now its only evidence. `kf_0146100.jpg` stays committed but is unwired. | `acquisition/extraction/drafts/REAL_WF_0002.r1.draft.json` (not yet exported — safe to edit in place) |
| `REAL_WF_0002_CL_012` evidence explanation (`kf_0115000.jpg`) | **Reworded.** Frame kept (claim text was already accurate); explanation stopped citing narration proximity as the reason and now states plainly it's bench B-roll, not the on-machine moment. | same draft |
| `REAL_WF_0001_CL_021` (`kf_0142700.jpg`) | **New revision.** `REAL_WF_0001.r2` (`supersedes_revision: 1`) reworks the claim to stop naming an unverifiable "cam follower" identity and an unprovable rotation from a still. r1 stays untouched and published; its review status for this one claim correctly goes stale on recompile (2 other pre-existing claims unaffected). **r2 is not promoted or exported** — it needs the same D1-C human source-review step r1 went through before it can supersede r1 in `data/workflows/dev/`. | `acquisition/extraction/drafts/REAL_WF_0001.r2.draft.json`, `data/workflows/drafts/REAL_WF_0001.r2.json` |
| `SRC_HAAS_0005_KF_0011800` inventory note | **Corrected**, no evidence affected (unwired). | `acquisition/preprocessing/haas_d1a_media_inventory.jsonl` |
| `compile_workflow.py` keyframe-evidence path | **Bug fix.** Filename-derived timestamp → inventory-verified (path lookup + content-hash check) timestamp; fabricated multi-second locator span → 1ms locator at the real frame instant (schema V04 forbids zero-width). Recompiling **every** existing draft with a keyframe changes that evidence's `locator` shape (not its content or claim text) — expected, not a regression; `data/workflows/drafts/*.json` were regenerated accordingly. `data/workflows/dev/REAL_WF_0001.r1.json` (the only exported/published snapshot with visual evidence) is untouched. | `acquisition/extraction/compile_workflow.py`, new `acquisition/preprocessing/keyframes.py` |

**Action needed from D1-B/D1-C:** (1) a human reviewer should read `keyframe_review.jsonl`
and fill in `human_signoff` — every row currently has `reviewer_kind: "ai_vision_review"`
and `human_signoff: null`, since this pass's judgments were made by Claude Opus 5 reading
the pixels, not by a person; (2) `REAL_WF_0001.r2` needs the normal D1-C source-review +
promotion flow before it can supersede r1 in `dev/`; (3) `REAL_WF_0002.r1.draft.json`'s
edits should be folded into its first D1-C review rather than reviewed twice.

## 19. Five more dev sources (2026-10-12), SRC_HAAS_0008 to SRC_HAAS_0012

Branch `team1/d1a-expand-dev-sources`. The same process as the pilot, applied to five more
official Haas service videos, all in `dev`. The holdout sources SRC_HAAS_0006 and
SRC_HAAS_0007 were not touched. This section updates the counts in sections 1, 4, 14 and 15
(dev is now 10 sources and 12 published workflow revisions).

| source_id | Video | Length | Workflow | Family |
|---|---|---|---|---|
| SRC_HAAS_0008 | Alarm 626 Tool Pocket Slide Error | 86 s | `REAL_WF_0004` | FAM-TOOL-POCKET-ALARM-626 |
| SRC_HAAS_0009 | Spindle Troubleshooting | 236 s | `REAL_WF_0005` | FAM-SPINDLE-TROUBLESHOOTING |
| SRC_HAAS_0010 | Alarm 254 Spindle Motor Overheat | 90 s | `REAL_WF_0006` | FAM-SPINDLE-MOTOR-OVERHEAT-254 |
| SRC_HAAS_0011 | Alarm 9973 Unstable Incoming Power | 181 s | `REAL_WF_0007` | FAM-INCOMING-POWER-ALARM-9973 |
| SRC_HAAS_0012 | X-Axis Mill Waycover Replacement | 411 s | `REAL_WF_0008` | FAM-X-AXIS-WAYCOVER-REPLACEMENT |

### Playable video links (checked 2026-10-12)

Each link was read from YouTube's own metadata (title, channel "Haas Automation, Inc.", duration),
and the video id is compared character by character with `Source.url` by
`tests/unit/test_d1a_dev_expansion.py`, because ids are case-sensitive (see section 1).

| source_id | Watch |
|---|---|
| SRC_HAAS_0008 | https://www.youtube.com/watch?v=DXtocZX8hf0 |
| SRC_HAAS_0009 | https://www.youtube.com/watch?v=cwYsbzAW3r0 |
| SRC_HAAS_0010 | https://www.youtube.com/watch?v=M-VcwEodqP0 |
| SRC_HAAS_0011 | https://www.youtube.com/watch?v=DgHQtvvf1kI |
| SRC_HAAS_0012 | https://www.youtube.com/watch?v=ezplV3447C8 |

The haascnc.com page was not fetched for any of them (Cloudflare); `Source.url` is the
haascnc.com address built from the same video id, as for the pilot.

### How they were chosen

About 28 official service videos turned up in a metadata-only search. Only those with a
**manual English caption** were eligible, so no speech recognition was run. `tsp_eLbb-UQ`
(spindle orientation, side-mount) and `OrflTBq-JBo` (spindle encoder troubleshooting) were
dropped because they have no manual captions. The five above cover three alarm diagnoses,
one symptom triage and one replacement procedure, on subsystems the pilot did not reach.

### What was added

- `scripts/add_d1a_dev_sources.py` holds the curated values and builds the registry entries,
  Source records, catalog rows, split families, transcripts and keyframes. It is idempotent.
- `acquisition/preprocessing/captions.py` turns a caption file into utterances. Its tests
  reproduce the existing SRC_HAAS_0005 transcript exactly.
- Transcripts: `raw.json` is the uploader's caption; `corrected.json` carries terminology
  fixes only, each cited in `corrections.diff` against the video's title, its official
  description, an on-screen overlay, or the transcript's own usage. SRC_HAAS_0009's "Bijur pump"
  and "Mobil SHC 625" are fixed from on-screen text, which is the stronger source.
- 31 keyframes at 1080p, chosen by reading the frame against the claim it supports, not by
  cue timing. All 31 are in the `data/keyframes/` ledgers; six are marked `accepted_weak`
  because the frame alone cannot identify the part the narration names. Many of these videos carry on-screen captions and part labels, which make them
  strong visual evidence. The frame judgments were AI vision review, as in section 18, and
  were then signed off by `quyhienln` on 2026-10-12 (`human_signoff` in `keyframe_review.jsonl`).
  The 20 pilot rows still have no sign-off.
- `Source.content_sha256` for these five is the SHA-256 of `raw_text`, so it can be checked from
  the record. The pilot video records hold a different legacy value that nothing enforces.
- Five workflows, 169 claims, all `source_checked`. Each claim carries two review events:
  an AI-assisted pass recorded as `d1c-source-review` (a claim-by-claim read plus a script
  that flags any number, code or proper noun not found in the cited cues), and the human
  source review by `quyhienln` on 2026-10-12. Neither is `expert_validated`.

### Reviewer links

`data/catalogs/haas_playable_links.json` now holds the YouTube id of every dev video as YouTube
spells it, and `review.py` builds watch links from it. This closes the trap described in
section 1: regenerating a worklist no longer produces the lower-case SRC_HAAS_0003 link.
`Source.url` for SRC_HAAS_0003 is unchanged.

### Open items

1. **Wye-Delta contactor guide.** The description of SRC_HAAS_0011 links a Haas DIY page. It is
   recorded as deferred candidate CAND-018 with no source_id. Its text has to be copied by
   ordinary browsing, as for TG0128, before it can become a companion source.
2. **Refusal got worse on the larger corpus; recall did not.** Measured on the 66 reviewed
   questions, lexical, old bundle against new: Recall@5 0.9459 on both, status accuracy
   0.9848 to 0.8636, out-of-scope questions answered 1 to 9. The gate drops words found in
   more than 75% of steps, and words like "tool" and "carousel" fell under that line once the
   corpus stopped being all SMTC. One alternative rule was tried and was worse, so the gate is
   unchanged. Numbers, cause, labels to re-check and what is still owed (hybrid was not
   measured: Gemini quota) are in `docs/retrieval_dev_expansion_check.md`.
   `tests/unit/test_query.py` uses probes that are still out of domain.
3. **Evaluation records name the old bundle id** (`BUNDLE_HAAS_SMTC_DEV_20382d7957b6` in
   `data/eval/README.md`, `docs/retrieval_eval_real_dev.md`,
   `docs/gold_review_worklist_real_dev.md`, `benchmarks/results/20261011_real_dev/`). They describe
   runs on that bundle and remain true for it; the bundle is now
   `BUNDLE_HAAS_SMTC_DEV_95b81c529dbe`. Fifteen questions for the new workflows (Q069-Q083) were
   added to the question file, drafted by AI and reviewed by `quyhienln` on 2026-10-12.
4. **Each workflow lists open questions** (40 across the bundle) for fields the video does not
   cover, such as acceptance thresholds. They are in the snapshots, not here.

### Checksums (sha256)

```
1e50f901750ea2630037496bc58282a973d10c25a0417e690ddea60f9a2b3500  data/sources/haas_pilot_sources.jsonl
7e1afb016ced366080ec86102010390e3df70cf4db058d3a40be31b8eaffcdfa  data/splits/haas_d1a_split_manifest.json
ea85bea89b2889e9d22f2931a4735af9f1f748cb37c2d4df09684ce13de0c3bc  data/catalogs/haas_d1a_source_id_registry.json
2453d19fbf8b16fefe1e0683daea7872c5f2d89d722463bc836bf60e6dc63798  data/catalogs/haas_playable_links.json
a35c48c36d067cba9c2ab36299395e15aef410cc7c6e68694c55f7535696823e  acquisition/video_catalog/haas_d1a_source_candidates.csv
249a3e8d17c1e61cb55b840247fd9bd500030c06e5d0878ed1508c356192823b  acquisition/export/haas_pilot_dev_bundle/manifest.json
1e50f901750ea2630037496bc58282a973d10c25a0417e690ddea60f9a2b3500  acquisition/export/haas_pilot_dev_bundle/sources.jsonl
c4703bb729accc54d89e080941a3c80d99ff5a6408dbc9001ee02e5d6e66da16  acquisition/export/haas_pilot_dev_bundle/workflows.jsonl
8d1e67506668d6b89d21c129b2c0ad22df1f6e3723a307db7686a2bd5363d2a8  acquisition/preprocessing/haas_d1a_media_inventory.jsonl
fd56d421bb3cabfa0c8f39e9aa57421b4c16ed6ccfb0259db66d27d8dec9e09e  docs/data_rights_register.md
```
