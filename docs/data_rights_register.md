# D1-A Data Rights & Access Register — Haas SMTC Pilot

Access date for all rows: **2026-09-11**. Owner/publisher for every row: **Haas
Automation, Inc.** (confirmed independently via YouTube oEmbed `author_name`, yt-dlp
`uploader`/`channel` fields, and — for two sources — the official haascnc.com page text
itself).

Operator authorization of record: the user explicitly authorized (a) downloading Haas
official video/caption material and running ASR for this prototype, and (b), in a
follow-up instruction, downloading video files directly for keyframe extraction where
necessary. Both are recorded here as the **operator's own assertion for this pilot**,
not as a grant of rights from Haas Automation or YouTube, and neither authorizes
redistribution.

## Dev sources

| source_id | Canonical page | Canonical video | Public? | Download permitted? | Local retention? | Clips/keyframes/transcripts storable? | Redistribution? | Decision | Open question |
|---|---|---|---|---|---|---|---|---|---|
| SRC_HAAS_0001 | haascnc.com guide page (confirmed HTTP 200) | youtube.com/watch?v=TmjjC7BDDag | Yes | Unclear (YouTube ToS restricts downloading without permission; operator authorized for this prototype) | Caption text (hashed) + a 144p video-only stream (local, gitignored, not committed) | Yes — caption transcript committed; 3 keyframes extracted, hashed, and committed | **No** | `asset_uri=null` (no committed media asset); video kept out of git per repo's own `data/media/` convention | Whether Haas/YouTube would license clip/keyframe storage for a shipped (non-prototype) product |
| SRC_HAAS_0002 | haascnc.com guide TG0128 — full page text retrieved | n/a (document) | Yes | N/A (text page) | Full body text retained and hashed (operator manually copied it from the public page after automated re-fetch was blocked) | N/A (text document) | No | `raw_text`/`content_sha256` populated | none — resolved |
| SRC_HAAS_0003 | haascnc.com how-to page (confirmed HTTP 200) | youtube.com/watch?v=2bRa6qm6wm4 | Yes | Unclear (same as above; operator authorized) | Caption text (hashed) + a 144p video-only stream (local, gitignored) | Yes — caption transcript committed; 3 keyframes extracted, hashed, and committed | **No** | `asset_uri=null`; video kept out of git | Same as SRC_HAAS_0001 |
| SRC_HAAS_0004 | haascnc.com how-to page — full page text retrieved | n/a (document) | Yes | N/A (text page) | Full body text retained and hashed (operator manually copied it from the public page after automated re-fetch was blocked) | N/A (text document) | No | `raw_text`/`content_sha256` populated | none — resolved |
| SRC_HAAS_0005 | not confirmed this session (Cloudflare 403) | youtube.com/watch?v=cs-BvWsKXyU | Yes | Unclear (same as above; operator authorized) | Caption text (hashed) + a 144p video-only stream (local, gitignored) | Yes — caption transcript committed; 3 keyframes extracted, hashed, and committed | **No** | `asset_uri=null`; video kept out of git | Confirm the haascnc.com page separately from YouTube |

## Holdout sources (untouched beyond eligibility)

| source_id | Canonical video | Public? | Processing done |
|---|---|---|---|
| SRC_HAAS_0006 | youtube.com/watch?v=HXsqcIapVgc | Yes | Title, duration, uploader, upload date only (yt-dlp metadata, no download). No captions, no transcript, no guide fetch. |
| SRC_HAAS_0007 | youtube.com/watch?v=ZlU-dWyulOU | Yes | Same as above. |

## Operational decisions applied everywhere

- **No holdout video/audio was downloaded**, and no dev video/audio was committed to
  git. For the 3 dev videos, a low-resolution (144p, video-only, no audio) stream was
  downloaded locally under the operator's explicit authorization, solely to extract
  keyframes; it lives under `data/media/haas_d1a/`, which the repository's own
  `.gitignore` already excludes ("Media va bundle sinh ra khi chay pipeline (khong
  commit)") — so this was never at risk of being committed, consistent with the
  git-workflow instruction not to commit video binaries.
- `asset_uri` is `null` on every Source record: no committed media asset exists to
  point to; the local video file is a processing input, not a published asset.
- Retained caption transcripts and the 9 extracted keyframes are hashed
  (`content_sha256`) against their exact bytes, so every retained/committed artifact is
  auditable (see `acquisition/preprocessing/haas_d1a_media_inventory.jsonl`, which also
  records — but does not publish — the local video files' hashes for provenance).
- Redistribution outside this pilot is **not** established for any source; do not publish
  or share the retained caption text, guide text, or keyframes externally.
- Both guide pages (SRC_HAAS_0002 / TG0128 and SRC_HAAS_0004 / manual-recovery how-to)
  are now fully retained: automated re-fetch was blocked by Cloudflare for both, so the
  operator opened each public URL in a browser and relayed the visible text, which was
  hashed and stored exactly as received.
- No login, CAPTCHA, robots restriction, or DRM was bypassed. `robots.txt` on
  haascnc.com permits `/service/`; the Cloudflare interstitial encountered on
  haascnc.com was treated as an access boundary for automated requests, not something to
  defeat — repeated automated fetches were stopped rather than retried aggressively or
  worked around. The one guide page recovered was obtained through ordinary manual
  browsing by the operator, not by circumventing the interstitial.
