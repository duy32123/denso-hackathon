# D1-A Data Rights & Access Register — Haas SMTC Pilot

Access date for all rows: **2026-09-11**. Owner/publisher for every row: **Haas
Automation, Inc.** (confirmed independently via YouTube oEmbed `author_name`, yt-dlp
`uploader`/`channel` fields, and — for two sources — the official haascnc.com page text
itself).

Operator authorization of record: the user explicitly authorized downloading Haas
official video/caption material and running ASR for this prototype during this session.
This is recorded here as the **operator's own assertion for this pilot**, not as a grant
of rights from Haas Automation or YouTube, and it does not authorize redistribution.

## Dev sources

| source_id | Canonical page | Canonical video | Public? | Download permitted? | Local retention? | Clips/keyframes/transcripts storable? | Redistribution? | Decision | Open question |
|---|---|---|---|---|---|---|---|---|---|
| SRC_HAAS_0001 | haascnc.com guide page (confirmed HTTP 200) | youtube.com/watch?v=TmjjC7BDDag | Yes | Unclear (YouTube ToS restricts downloading without permission; operator authorized for this prototype) | Caption text only, per operator authorization | Yes, caption transcript only (retained, hashed) | **No** | `asset_uri=null`; retained the official caption transcript (text) only; no video/audio file retained | Whether Haas/YouTube would license clip/keyframe storage for a shipped (non-prototype) product |
| SRC_HAAS_0002 | haascnc.com guide TG0128 (confirmed HTTP 200 this session, body not retained) | n/a (document) | Yes | N/A (text page) | Page body not retained (session access became blocked before saving) | N/A this session | No | `raw_text=null`, `content_sha256=null`; re-fetch and hash next session | Re-confirm reachability once Cloudflare access stabilizes |
| SRC_HAAS_0003 | haascnc.com how-to page (confirmed HTTP 200) | youtube.com/watch?v=2bRa6qm6wm4 | Yes | Unclear (same as above; operator authorized) | Caption text only | Yes, caption transcript only | **No** | `asset_uri=null`; caption transcript retained and hashed; no video/audio retained | Same as SRC_HAAS_0001 |
| SRC_HAAS_0004 | haascnc.com how-to page (confirmed HTTP 200, body not retained) | n/a (document) | Yes | N/A (text page) | Page body not retained | N/A this session | No | `raw_text=null`, `content_sha256=null`; re-fetch and hash next session | Same as SRC_HAAS_0002 |
| SRC_HAAS_0005 | not confirmed this session (Cloudflare 403) | youtube.com/watch?v=cs-BvWsKXyU | Yes | Unclear (same as above; operator authorized) | Caption text only | Yes, caption transcript only | **No** | `asset_uri=null`; caption transcript retained and hashed; no video/audio retained | Confirm the haascnc.com page separately from YouTube |

## Holdout sources (untouched beyond eligibility)

| source_id | Canonical video | Public? | Processing done |
|---|---|---|---|
| SRC_HAAS_0006 | youtube.com/watch?v=HXsqcIapVgc | Yes | Title, duration, uploader, upload date only (yt-dlp metadata, no download). No captions, no transcript, no guide fetch. |
| SRC_HAAS_0007 | youtube.com/watch?v=ZlU-dWyulOU | Yes | Same as above. |

## Operational decisions applied everywhere

- **No video or audio binary was downloaded or retained** for any source, dev or
  holdout. Only text (official YouTube captions for the 3 dev videos) was retained,
  under the operator's authorization for this prototype.
- `asset_uri` is `null` on every Source record: nothing beyond caption text is retained,
  so there is no local media asset to point to.
- Retained caption transcripts are hashed (`content_sha256`) against the exact `.vtt`
  bytes downloaded, so the retained artifact is auditable.
- Redistribution outside this pilot is **not** established for any source; do not publish
  or share the retained caption text externally.
- Two guide pages (SRC_HAAS_0002, SRC_HAAS_0004) were confirmed reachable (HTTP 200,
  title match) earlier in the session but their bodies were not saved before
  haascnc.com began returning a Cloudflare challenge to further requests from this
  session. This is recorded as a limitation, not fabricated as retained content.
- No login, CAPTCHA, robots restriction, or DRM was bypassed. `robots.txt` on
  haascnc.com permits `/service/`; the Cloudflare interstitial encountered later in the
  session was treated as an access boundary, not something to defeat — repeated fetches
  were stopped rather than retried aggressively or worked around.
