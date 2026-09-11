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
| Clip/keyframe maps to original time | **PASS** | 3 keyframes extracted at `00:01:05.500`, `00:01:56.500`, `00:04:02.900`. `kf_0065500.jpg` (00:01:05.5) was opened and visually inspected this session: the machine control screen literally reads **"2066 TOOL CHANGER HOME POSITION FAULT"** with an "AUTOMATIC RECOVERY" label — a direct visual match to the transcript's "I see that I've got this 2066 tool changer fault alarm" at the same timestamp. |

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
