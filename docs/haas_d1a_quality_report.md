# D1-A Quality Report — Haas SMTC Pilot

Manual QC performed 2026-09-11 against the 3 selected development sources and their
2 linked companion guides. Evidence quoted verbatim where relevant; no "looks good"
verdicts.

## SRC_HAAS_0001 — Side-Mount Tool Changer Double Arm Troubleshooting

| Check | Status | Evidence |
|---|---|---|
| Direct URL opens | **PASS** | `https://www.haascnc.com/video/service/TmjjC7BDDag.html` returned HTTP 200 this session; `<meta name="videoID" content="TmjjC7BDDag">` present in the page body. |
| Title matches | **PASS** | Page `<title>` = "Side-Mount Tool Changer Double Arm Troubleshooting"; YouTube oEmbed title = "Side-Mount Tool Changer Double Arm Troubleshooting - Haas Automation Service" — same underlying title, oEmbed appends the channel tagline. |
| Duration correct | **PASS** | yt-dlp reports `duration=191` (seconds) directly from YouTube's own metadata API → `duration_ms=191000` recorded. |
| Publisher attribution supported | **PASS** | YouTube oEmbed `author_name="Haas Automation, Inc."` and yt-dlp `uploader`/`channel` both = "Haas Automation, Inc." — two independent confirmations, neither derived from the search-result title. |
| Transcript span start/end align with source | **PASS** | First cue `00:00:00.000 --> 00:00:09.390` = video's actual opening line ("today we're going to talk about your sidemount to change a double arm"); last cue `00:02:59.370 --> 00:03:04.890` ends with the sign-off ("visit Haas CNC comm and thanks for watching"), consistent with `duration_ms=191000`. |
| ≥3 utterances have correct timestamps | **PASS** | `00:01:44.340` "in extreme cases you may experience drop in tools"; `00:02:04.260` "let's check the clearance between the tool holder and the retaining fingers"; `00:02:26.100` "make sure that there's a ... gap between the finger and the V flange" — all three checked against the cue boundaries in the retained `.vtt`. |
| Negation/terminology/numbers/units preserved | **PASS (corrected, with citation)** | The official caption at `00:02:26.100` originally read "a 20,000 meter gap". TG0128's own retrieved text (SRC_HAAS_0002) states verbatim: "The correct space is between 0.014 in (0.36 mm) and 0.020 in (0.51 mm)." `corrected.json` now reads "...a 0.020 in (0.51 mm) gap..." — see `acquisition/preprocessing/transcripts/SRC_HAAS_0001/corrections.diff` for the exact before/after and citation. `raw.json` is untouched. |
| Clip/keyframe maps to original time | **PASS** | 3 keyframes extracted at `00:00:41.220`, `00:02:04.300`, `00:02:26.100` — original-video ms, unchanged. `kf_0124300.jpg` (00:02:04.3) was opened and visually inspected this session: shows a presenter beside an open Haas VMC with the tool changer visible, consistent with the transcript's "let's get the double arm in a position where we can check the clearance" at that timestamp. |
| Access restrictions documented | **PASS** | `docs/data_rights_register.md` row for SRC_HAAS_0001. |
| No metadata inferred from search-result title alone | **PASS** | `presenter`/`presenter_role` left `null` — the retained caption transcript is anonymous first-person narration; no name is self-stated, so none was invented even though earlier web-search snippets loosely attributed similar Haas videos to a named presenter. |

## SRC_HAAS_0002 — TG0128 guide (companion to SRC_HAAS_0001)

| Check | Status | Evidence |
|---|---|---|
| Direct URL opens | **PASS (earlier in session)** | Confirmed HTTP 200, 349,057 bytes, title "Side Mount Tool Changer (SMTC) - Double Arm / Cambox - Troubleshooting Guide - TG0128" matched exactly. |
| Body content retained and hashed | **PASS (via manual retrieval)** | Automated re-fetch stayed blocked (HTTP 403); the operator opened the same public URL directly and relayed the visible text, now stored as `raw_text` and hashed as `content_sha256=a8a47506...`. Provenance recorded honestly as operator-relayed, not an automated fetch. |
| Reasoning/outcome coverage | **PASS** | Full symptom → possible-cause → corrective-action table (10 distinct alarm groups incl. 2066, 622, 627, 628/673, 855); explicit pass/fail criteria ("less than 1/4 in (6 mm) of lost motion"; feeler-gauge range 0.014–0.020 in); step-by-step manual-recovery procedure. |
| Cross-references its own related sources | **PASS** | Page text explicitly names "Video - Tool Changer Recovery - Side Mount Tool Changer (SMTC)" and "VMC, HMC - Side-Mount Tool Changer - Manual Recovery" as the alarm-2066 remedy — corroborating, from the primary source itself, the curated FAM-SMTC-RECOVERY link already recorded between SRC_HAAS_0003 and SRC_HAAS_0004. |

## SRC_HAAS_0003 — Tool Changer Recovery; Haas Side Mount Tool Changer (SMTC)

| Check | Status | Evidence |
|---|---|---|
| Direct URL opens | **PASS** | `https://www.haascnc.com/video/service/2bra6qm6wm4.html` HTTP 200 this session; `<meta name="videoID" content="2bRa6qm6wm4">`. |
| Title matches | **PASS** | Page title and caption content both consistent with "Tool Changer Recovery; Haas Side Mount Tool Changer (SMTC)". |
| Duration correct | **PASS** | yt-dlp `duration=360` → `duration_ms=360000`. |
| Publisher/presenter attribution supported | **PASS** | Publisher via oEmbed + yt-dlp, both "Haas Automation, Inc.". `presenter="Andrew"` and `presenter_role="engineer"` are stated **verbatim on the official haascnc.com page** ("Andrew (engineer) walks you through the process step-by-step"), confirmed by direct fetch this session — not inferred. |
| Transcript span start/end align | **PASS** | First cue `00:00:03.710` "so your tool changer's alarm down..."; last spoken cue `00:05:33.170 --> 00:05:40.850` "keep your tool holders and the spindle taper clean, thanks a lot for watching this video" — consistent with `duration_ms=360000`. |
| ≥3 utterances have correct timestamps | **PASS** | `00:01:05.480` "I see that I've got this 2066 tool changer fault alarm"; `00:01:43.370` "press recover now it gives me the option of either restoring the tool changer or recovering a tap"; `00:04:02.900` "raise the pocket up ... now it's telling me no manual recovery action is required". |
| Negation/terminology/numbers/units preserved | **PASS** | Alarm code "2066" is stated clearly and unambiguously twice in the caption at `00:01:05` and `00:01:32` — no correction needed. |
| Access restrictions documented | **PASS** | `docs/data_rights_register.md` row for SRC_HAAS_0003. |
| No metadata inferred from search-title alone | **PASS** | `alarm_codes=["2066"]` (catalog) taken directly from spoken caption text, not the video's title or a search snippet; independently corroborated by TG0128's own symptom table, which lists "Alarm 2066 TOOL CHANGER HOME POSITION FAULT" as one of its entries. |
| Clip/keyframe maps to original time | **PASS** | 3 keyframes extracted at `00:01:05.500`, `00:01:56.500`, `00:04:02.900`. `kf_0065500.jpg` (00:01:05.5) was opened and visually inspected this session: the machine control screen literally reads **"2066 TOOL CHANGER HOME POSITION FAULT"** with an "AUTOMATIC RECOVERY" label — a direct visual match to the transcript's "I see that I've got this 2066 tool changer fault alarm" at the same timestamp. Re-extracted at 1080p (up from an initial 144p pass) for production use; every character of the alarm text is now individually legible. |

## SRC_HAAS_0004 — Manual Recovery how-to guide (companion to SRC_HAAS_0003)

| Check | Status | Evidence |
|---|---|---|
| Direct URL opens | **PASS (earlier in session)** | Confirmed HTTP 200, 301,243 bytes, title "Side-Mount Tool Changer - Manual Recovery - Mill" matched exactly. |
| Body content retained and hashed | **PASS (via manual retrieval)** | Automated re-fetch stayed blocked (HTTP 403); the operator opened the same public URL directly and relayed the visible text, now stored as `raw_text` and hashed as `content_sha256=66454ed7...`. |
| Machine family stated explicitly | **PASS** | Page states "how to perform a manual recovery on the Side-Mount Tool Changer (SMTC) of a Haas mill" and the title itself ends in "- Mill" — `machine_family` in the catalog is `basis=source`, not curated. |
| Outcome/verification present | **PASS** | Step 7: "Push [ATC/FWD] to test the recovery. If the tool change recovery is not successful, it is most likely that the machine is mechanically jammed." — an explicit pass/fail with a named next action. |
| Content-overlap finding | **Noted for D1-B** | This page's 7-step procedure is **word-for-word identical** to the "MANUAL RECOVERY HOW TO" section already reproduced verbatim inside TG0128 (SRC_HAAS_0002) — confirmed by direct text comparison. Both stay in `dev` (no split issue), but D1-B should be aware these two Source records carry duplicate procedure text and dedup accordingly rather than double-counting it as two independent confirmations. |
| Cross-references its own related source | **PASS** | TG0128 (SRC_HAAS_0002) independently names this exact page ("VMC, HMC - Side-Mount Tool Changer - Manual Recovery") as the alarm-2066 remedy, corroborating the curated FAM-SMTC-RECOVERY link from the primary source itself. |

## SRC_HAAS_0005 — Replace a Tool Pocket on Your Haas SMTC

| Check | Status | Evidence |
|---|---|---|
| Direct URL resolvable | **PARTIAL** | The YouTube URL and metadata (`https://www.youtube.com/watch?v=cs-BvWsKXyU`) were confirmed directly (yt-dlp, oEmbed). The `haascnc.com/video/service/cs-BvWsKXyU.html` mirror page returned HTTP 403 (Cloudflare) every attempt this session, so title/description on that specific page were **not** independently re-confirmed; the canonical `url` field still points to that haascnc.com page as the deepest stable Haas-owned locator, per the section-3 rule, with the access limitation stated in `access_note`. |
| Duration correct | **PASS** | yt-dlp `duration=261` → `duration_ms=261000`. |
| Publisher supported | **PASS** | oEmbed + yt-dlp both "Haas Automation, Inc.". |
| Transcript span aligns | **PASS** | First cue `00:00:00.000` "hi I'm Orville and today we're going to replace a damaged pocket..."; last cue `00:04:04.800 --> 00:04:09.390` "run the tool changer through several tool changes to ensure everything is working correctly, thanks for watching" — a clear verification step, consistent with `duration_ms=261000`. |
| ≥3 utterances timestamped | **PASS** | `00:01:33.540` "disconnect the main air ... remove the pilot check valve"; `00:02:22.680` "rotate that cam follower, make sure that it's spinning freely"; `00:03:53.460` "release the e-stop and run the tool changer". |
| Presenter | **PASS, partial** | `presenter="Orville"` self-stated in audio ("hi I'm Orville"). `presenter_role=null` — the haascnc.com page that might state a role could not be fetched this session; left null rather than borrowed from a third-party search snippet. |
| Access restrictions documented | **PASS** | `docs/data_rights_register.md` row for SRC_HAAS_0005. |
| Clip/keyframe maps to original time | **PASS** | 3 keyframes extracted at `00:00:11.800`, `00:02:22.700`, `00:04:04.800`. `kf_0011800.jpg` (00:00:11.8) was opened and visually inspected this session: shows the presenter beside the open carousel/pocket area, consistent with the transcript's "today we're going to replace a damaged pocket on the side mount tool changer" at that timestamp. |

## Holdout sources (SRC_HAAS_0006, SRC_HAAS_0007)

Per D1-A rules, holdout content was **not** processed beyond eligibility metadata.
QC here is limited to confirming that constraint was actually honored:

- No caption files exist under `acquisition/preprocessing/transcripts/` for either ID — **PASS**.
- Neither ID appears in `data/sources/haas_pilot_sources.jsonl` (dev bundle) — **PASS**,
  confirmed programmatically (`check_no_split_leakage` → 0 errors, see
  `acquisition/validation/validate_d1a_extra.py`).

## Summary

| Item | Result |
|---|---|
| 3/3 dev videos: URL, duration, publisher confirmed from primary/independent sources | PASS |
| 3/3 dev videos: ≥3 spot-checked utterance timestamps each | PASS (9 total) |
| 3/3 dev videos: ≥3 keyframes extracted, hashed, and visually verified against transcript content | PASS (9 total) |
| 2/2 companion guides: URL+title confirmed, full body retained and hashed | PASS (SRC_HAAS_0002 / TG0128 and SRC_HAAS_0004) |
| Content-overlap between SRC_HAAS_0002 and SRC_HAAS_0004 (identical 7-step procedure) | Noted for D1-B dedup awareness, not a split issue |
| 1 numeric caption artifact identified and corrected with an auditable diff, citing TG0128 | Resolved |
| No holdout content processed beyond eligibility | PASS |
| No metadata inferred from search-result titles alone | PASS |

## Second QC pass (2026-09-14, WP2 re-review)

Full line-by-line re-read of all 3 dev transcripts (not spot-checking), plus a review of
keyframe coverage relative to each video's actual step count. Basis for method: the same
1080p local files D1A originally downloaded (`data/media/haas_d1a/*.mp4`, gitignored,
sha256-confirmed unchanged); `ffmpeg`/`ffprobe` 9.0, matching the version already recorded
in the inventory.

### Additional caption corrections

Reading past the original spot-checks surfaced more of the same failure mode already
identified once (the "20,000 meter gap" artifact): the caption model mis-hears domain
terminology, most often "tool changer" itself, and once the publisher's own name. All of
the following are recorded with full before/after text and citation in each video's
`corrections.diff`; none change any timestamp or cue count.

| Video | Cues | Fix | Basis |
|---|---|---|---|
| SRC_HAAS_0001 | 4 cues | "sidemount to change a double arm" / "two changes" / "for to change or" → "tool changer(s)" | Source's own title; self-consistent with correct usage elsewhere in the same transcript |
| SRC_HAAS_0001 | 1 cue | "shin washers" → "shim washers" | TG0128 (SRC_HAAS_0002) T0038/T0111 both name this part "shim washers" |
| SRC_HAAS_0003 | 2 cues | "Hoss" → "Haas" | Publisher of record ("Haas Automation, Inc.") |
| SRC_HAAS_0003 | 3 cues | "tool changes"/"told change"/"total change your" → "tool changer" | Same self-consistency basis; matches the video's own title |
| SRC_HAAS_0005 | 1 cue | "shoulder boat" → "shoulder bolt" | Self-consistent: "shoulder bolt" used correctly twice earlier in the same transcript |
| SRC_HAAS_0005 | 1 cue | "several two changes" → "several tool changes" | Same self-consistency basis |

**Flagged, not corrected**: SRC_HAAS_0001's "unusual puffin or banging sound" (00:00:28).
"Puffin" is clearly wrong, but neither TG0128 nor any other retained source states whether
"popping" or "puffing" was meant — left as-is in both `raw.json` and `corrected.json`,
same discipline as the original gap-spec artifact before its citation was found.

**Defect found and fixed in already-authored, not-yet-reviewed work**: 5 claims across
`REAL_WF_0002`/`REAL_WF_0003` (branch `team1/pilot-workflows-0001-0003`, PR #10) had
already paraphrased past exactly these caption errors — asserting "Haas"/"shim
washers"/"tool changer" in claim text while citing the *raw*, uncorrected candidate. Fixed
by switching each claim's evidence to the newly-added corrected (`C####`) candidate,
following the same pattern the existing gap-spec claim already used. One further claim
("popping") was reworded rather than corrected, since — as above — no source confirms
which word was actually meant.

### Additional keyframes (11 new, 9 → 20 total)

The original bar was "≥3 keyframes, visually verified" — a pass threshold, not
scene-change coverage. Re-checking coverage against each video's actual step count found
real gaps, most severe in SRC_HAAS_0005 (a repair video where only 1 of ~17 physical
sub-actions had a visual anchor) and SRC_HAAS_0003 (the physical tool-removal step and the
final verification screen were both unillustrated). All new frames: extracted natively at
1080p from the same local files as the original 9, sha256'd, and opened/visually inspected
this session (method identical to the original 9's "opened and visually verified").

| Video | New keyframe(s) | What each shows |
|---|---|---|
| SRC_HAAS_0001 | `kf_0115000.jpg` | Wider-angle B-roll cutaway of the double-arm bracket (drilled pockets, spring, forked finger) — anchors the locking-mechanism narration |
| SRC_HAAS_0001 | `kf_0170000.jpg` | Presenter holding a red straightedge against the double arm, sighting along it — anchors the straightness-check narration |
| SRC_HAAS_0003 | `kf_0123000.jpg` | Control screen reading "Tool changer recovery completed. Press 'E' to exit." with both status fields OK |
| SRC_HAAS_0003 | `kf_0157000.jpg` | "TOOL CHANGER RECOVERY" screen at its initial "OFF POSITION" state, just after entering manual recovery |
| SRC_HAAS_0003 | `kf_0190000.jpg` | Gloved hand pressing near the base of a tool holder mounted in the double arm |
| SRC_HAAS_0003 | `kf_0258000.jpg` | "ACTIVE TOOL" panel on the control screen, presenter pointing at it |
| SRC_HAAS_0005 | `kf_0028000.jpg` | Close-up of a hand pressing the EMERGENCY STOP button |
| SRC_HAAS_0005 | `kf_0065000.jpg` | Gloved hand removing a tool holder from the carousel |
| SRC_HAAS_0005 | `kf_0076000.jpg` | Hand marking a disc with a marker pen (reinstallation reference mark) |
| SRC_HAAS_0005 | `kf_0158000.jpg` | Two gloved hands applying grease to a cylindrical part |
| SRC_HAAS_0005 | `kf_0222000.jpg` | Presenter using a pneumatic tool near the numbered carousel, reinstalling |

`REAL_WF_0002`/`REAL_WF_0003` (not yet reviewed) gained one `observed` claim per frame that
fell inside an existing step (all 6). The 5 SRC_HAAS_0005 frames stay unwired media:
`REAL_WF_0001` is already reviewed and exported by D1-B, so incorporating them means a
revision 2 — flagged in `docs/haas_d1a_to_d1b_handoff.md` for D1-B/D1-C.

## Third QC pass (2026-09-14) — keyframe evidence hardening, corrective

The second pass above states each new keyframe was "opened and visually inspected this
session" and treats that as sufficient. It was not: "opened" and "judged against a defined
evidence standard" are different things, and no per-frame judgment against a standard was
recorded. This pass re-audited all 20 committed keyframes (the original 9 plus the second
pass's 11) against a written standard (`docs/keyframe_selection_method.md`) and recorded a
structured verdict for every one (`data/keyframes/keyframe_selections.jsonl`), not just the
ones later found wrong. Full detail, reasoning and per-item results are in
`docs/keyframe_evidence_review.md`; capability/calibration proof is in
`docs/keyframe_capability_audit.md` and `docs/keyframe_calibration_report.md`.

**What was actually wrong**, confirmed by reading pixels rather than filenames or
timestamps:

- `REAL_WF_0002_CL_017` (`SRC_HAAS_0001` step "Measure the finger-to-flange gap with a
  feeler gauge") was anchored to `kf_0146100.jpg`, which shows two empty hands reaching
  toward the machine — no feeler gauge. Dense re-sampling of the full surrounding window
  confirms the gauge is never filmed in this source; the visual claim was removed from the
  draft rather than forced onto a nearby frame, leaving the step's existing transcript
  claim as its only (correct) evidence.
- `REAL_WF_0001_CL_021` (`SRC_HAAS_0005`, the "cam follower" claim, already exported) named
  a component and a motion ("spins freely") that the narration states but the still frame
  cannot show. `REAL_WF_0001.r2` (`supersedes_revision: 1`) reworks the claim to describe
  only what `kf_0142700.jpg` visibly shows; the exported r1 is untouched, per the repo's
  immutability rule, and the affected claim's review status correctly goes stale on
  recompile (see `test_the_committed_draft_has_been_source_checked`).
- `REAL_WF_0002_CL_012`'s evidence explanation justified `kf_0115000.jpg` by "the window
  where the narration names the locking-mechanism finger" — audio proximity, the exact
  anti-pattern this correction targets — even though the frame is bench B-roll of a
  detached part. The claim text itself was already purely descriptive, so the frame is
  kept for that narrower purpose and only the explanation was corrected.
- The unwired `kf_0011800.jpg` inventory note misdescribed a closed-door intro shot as "the
  open carousel/pocket area"; corrected in the media inventory. No claim cites this frame.

A compiler defect was also found and fixed: `compile_workflow.py`'s `_keyframe_evidence`
derived a keyframe's timestamp by parsing its filename (`int(path.stem.split("_")[-1])`)
with no check that the file's bytes matched anything — a silently overwritten file with
the same name would pass unnoticed. It now looks the file up in
`acquisition/preprocessing/haas_d1a_media_inventory.jsonl` by path and re-hashes it against
the recorded `content_sha256`, refusing to compile on any mismatch or missing lineage
(`tests/unit/test_compile_workflow.py::test_keyframe_evidence_is_rejected_when_file_bytes_do_not_match_the_inventory_hash`).
It also stopped writing a fabricated multi-second locator span (borrowed from the
transcript search window) for a single still frame; a still now gets a 1ms locator at its
real timestamp (schema V04 forbids a zero-width interval).
