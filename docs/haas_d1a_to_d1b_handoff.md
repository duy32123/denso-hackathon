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
`access_note`). For the 3 dev videos, a low-resolution (144p, video-only) stream was
downloaded locally under operator authorization solely to extract keyframes; it is kept
under `data/media/haas_d1a/` (gitignored per the repo's own convention) and is **not**
committed or redistributed — its hash is recorded in the inventory for provenance only.
9 keyframes (3 per dev video) were extracted at transcript-identified action/verification
moments, hashed, committed under `acquisition/preprocessing/keyframes/<source_id>/`, and
visually opened/verified this session (see `docs/haas_d1a_quality_report.md`).
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
7ffe335737c13e9f424d68a1f2f41b343595b02d2ce64541036713d59e4c475b  acquisition/preprocessing/haas_d1a_media_inventory.jsonl
addab43842e56993843a11b9cd03faf73b75bb5a20b8867bc5427d85d7b11ec0  docs/data_rights_register.md
b5540919258a5e3a147095835f9e4ceb22138414e7dc05bc6b58b10bc158aa6a  docs/haas_d1a_quality_report.md
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
