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
| Negation/terminology/numbers/units preserved | **CONCERN, not silently fixed** | The official caption at `00:02:26.100` reads "a 20,000 meter gap" — almost certainly a YouTube auto-punctuation/transcription artifact for a feeler-gauge spec (likely ".020 inch" / "20 thousandths", consistent with TG0128's independently-reported 0.014–0.020 in range). This session did **not** edit `corrected.json` to "fix" this number: no primary-source confirmation of the exact intended value was obtained (TG0128's own body text could not be re-fetched — see access note), and the D1-A rule is to correct only with an auditable diff, not to guess. Flagged here as an open item for whoever next has haascnc.com access to confirm against TG0128 directly. |
| Clip/keyframe maps to original time | **N/A** | No clips or keyframes were produced this session (video file not downloaded; see rights register). |
| Access restrictions documented | **PASS** | `docs/data_rights_register.md` row for SRC_HAAS_0001. |
| No metadata inferred from search-result title alone | **PASS** | `presenter`/`presenter_role` left `null` — the retained caption transcript is anonymous first-person narration; no name is self-stated, so none was invented even though earlier web-search snippets loosely attributed similar Haas videos to a named presenter. |

## SRC_HAAS_0002 — TG0128 guide (companion to SRC_HAAS_0001)

| Check | Status | Evidence |
|---|---|---|
| Direct URL opens | **PASS (earlier in session)** | Confirmed HTTP 200, 349,057 bytes, title "Side Mount Tool Changer (SMTC) - Double Arm / Cambox - Troubleshooting Guide - TG0128" matched exactly. |
| Body content re-verifiable now | **FAIL (documented, not concealed)** | A later fetch attempt to re-save the body for hashing returned HTTP 403 (Cloudflare interstitial). `raw_text`/`content_sha256` are `null`. This is recorded as an open gap, not glossed over. |

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
| No metadata inferred from search-title alone | **PASS** | `alarm_codes=["2066"]` (catalog) taken directly from spoken caption text, not the video's title or a search snippet. |

## SRC_HAAS_0004 — Manual Recovery how-to guide (companion to SRC_HAAS_0003)

Same status as SRC_HAAS_0002: URL/title confirmed HTTP 200 (301,243 bytes) earlier this
session; body not retained before the host began challenging further requests.
`raw_text`/`content_sha256` are `null` — **FAIL (documented)**, not concealed.

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
| 2/2 companion guides: URL+title confirmed, body content **not** re-verifiable this session | FAIL, documented (not concealed) |
| 1 numeric caption artifact identified, left uncorrected pending primary-source confirmation | Open item |
| No holdout content processed beyond eligibility | PASS |
| No metadata inferred from search-result titles alone | PASS |
