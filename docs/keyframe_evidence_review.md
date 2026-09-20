# Keyframe evidence review — D1-A hardening, 2026-09-14

Full re-audit of all 20 committed D1-A keyframes, judged against
`docs/keyframe_selection_method.md`'s standard by reading the actual JPEG bytes (Claude
Opus 5, in-session), not filenames or timestamps. Structured per-item records are in
`data/keyframes/keyframe_selections.jsonl` (verdict + reason) and
`data/keyframes/keyframe_review.jsonl` (the human-review-shaped record required by the
brief — see the honesty note below). Rejections and their lineage are in
`data/keyframes/keyframe_replacements.jsonl`.

## Result summary

| # | Source | ts (ms) | Claim | Verdict | Disposition |
|---|---|---|---|---|---|
| 1 | SRC_HAAS_0001 | 41220 | REAL_WF_0002_CL_004 | accepted | unchanged |
| 2 | SRC_HAAS_0001 | 115000 | REAL_WF_0002_CL_012 | **replace** | frame kept, evidence explanation corrected (was audio-proximity framing) |
| 3 | SRC_HAAS_0001 | 124300 | REAL_WF_0002_CL_015 | accepted | unchanged |
| 4 | SRC_HAAS_0001 | 146100 | REAL_WF_0002_CL_017 | **reject** | visual claim removed from draft; step now rests on transcript evidence only |
| 5 | SRC_HAAS_0001 | 170000 | REAL_WF_0002_CL_023 | accepted | unchanged |
| 6 | SRC_HAAS_0003 | 65500 | REAL_WF_0003_CL_006 | accepted | unchanged |
| 7 | SRC_HAAS_0003 | 116500 | REAL_WF_0003_CL_009 | accepted | unchanged |
| 8 | SRC_HAAS_0003 | 123000 | REAL_WF_0003_CL_011 | accepted | unchanged |
| 9 | SRC_HAAS_0003 | 157000 | REAL_WF_0003_CL_016 | accepted | unchanged |
| 10 | SRC_HAAS_0003 | 190000 | REAL_WF_0003_CL_020 | accepted | unchanged |
| 11 | SRC_HAAS_0003 | 242900 | REAL_WF_0003_CL_024 | accepted | unchanged |
| 12 | SRC_HAAS_0003 | 258000 | REAL_WF_0003_CL_028 | accepted | unchanged |
| 13 | SRC_HAAS_0005 | 142700 | REAL_WF_0001_CL_021 | **replace** | frame kept, claim reworded in REAL_WF_0001.r2 (supersedes r1) |
| 14 | SRC_HAAS_0005 | 11800 | unwired | **reject** | inventory note corrected (misdescribed content); no claim affected |
| 15 | SRC_HAAS_0005 | 28000 | unwired | accepted | unchanged |
| 16 | SRC_HAAS_0005 | 65000 | unwired | accepted (weak) | flagged: action direction unconfirmable from a single still |
| 17 | SRC_HAAS_0005 | 76000 | unwired | accepted | unchanged |
| 18 | SRC_HAAS_0005 | 158000 | unwired | accepted | unchanged |
| 19 | SRC_HAAS_0005 | 222000 | unwired | accepted (weak) | flagged: glass-reflection ghosting reduces legibility |
| 20 | SRC_HAAS_0005 | 244800 | unwired | accepted | unchanged, generic (no specific claim) |

**16 accepted as-is** (2 flagged weak, noted above but not rejected), **2 replaced**
(kept the frame, corrected what is claimed about it), **1 rejected outright** (visual
claim removed, no replacement frame exists because the action is never filmed), **1
inventory-note-only correction** (unwired, no workflow effect). **0 rejected keyframes
were converted to a sequence or clip** — no case in this audit needed one (see
`keyframe_selection_method.md`'s evidence-package section for why).

## Why each correction, in the reviewer's own words

**#2, #13 (reword, keep frame):** both cases follow the same pattern — a real, in-focus,
on-topic frame, whose *evidence explanation* borrowed language from the narration
("falls within the window where the narration names...", "the narration at the same
moment names the roller as...") instead of stating only what the pixels show. The claim
text in #2 was already purely descriptive and needed no change; #13's claim named an
unverifiable technical identity and an unprovable motion, so it was reworded and, because
`REAL_WF_0001` is already exported, moved into revision 2.

**#4 (reject, no replacement):** this is the one genuine "audio-only evidence
misrepresented as visual" case with no fix available by picking a different still. Dense
re-sampling of the full surrounding 8.75-second window (36 frames, both the original
143–152s span and neighboring bands) never shows a feeler gauge — the video narrates the
measurement without filming it. The correct fix per the brief's own rules is to drop the
visual claim, not to force a nearby frame to stand in for it; the step's action field
already had, and keeps, a transcript-sourced claim citing the same instruction.

**#14 (inventory-note correction only):** the committed image is fine (sharp, on-topic
intro shot of the presenter); its *description* was wrong (claimed "open carousel/pocket
area", the frame shows the closed-door intro). Corrected in the media inventory; since no
claim in any workflow cites this frame, no evidence lineage was affected.

## Human review — honesty note

The brief requires a *human* reviewer on every selected keyframe. This session's review
was performed by Claude Opus 5 reading the actual pixels, which is a real improvement
over the prior process (transcript-cue selection with no documented per-frame judgment)
but is **not** the human sign-off the acceptance criteria call for.
`data/keyframes/keyframe_review.jsonl` carries the required record shape with
`reviewer_kind: "ai_vision_review"` and `human_signoff: null` on every row, specifically
so this gap is visible in the data rather than silently implied as satisfied. A human
reviewer should read the 4 corrected items above (and, ideally, spot-check a sample of
the 16 accepted-as-is) and fill in `human_signoff` before this correction is treated as
fully closed.
