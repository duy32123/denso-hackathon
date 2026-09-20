# Keyframe selection method — D1-A evidence hardening

## What changed

The original D1-A/WP2 process picked a timestamp from a caption cue boundary and treated
"opened and visually verified this session" as a claim of adequacy, without a documented
per-frame judgment against a defined standard. This document is that standard, applied
retroactively to the 20 existing keyframes and going forward for any replacement.

## Definition of a valid keyframe

A frame is accepted only if **all** apply: the claimed component is visible; the claimed
action/state is visible; the frame is sharp enough to inspect; the subject is not
materially obstructed; the timestamp is the correct occurrence (not a different, similar
operation); on-screen text is legible when the claim depends on it; it is not only the
setup before the action or only the aftermath; it was not selected merely because speech
occurs nearby; its caption/observation_note describes only what is visible; it keeps its
original-video timestamp.

A frame is rejected — regardless of sharpness or composition — if any of: the action
happens between sampled frames; motion blur prevents inspection; the subject is
occluded; it belongs to a different (even if similar) operation; it is a generic view
without the claimed evidence; it needs audio to be understood; it shows the result but is
labelled the action (or vice versa); the model cannot determine what is visible; or
component/machine identity is being inferred rather than shown.

## Evidence-package choice used this session

- **Single frame** — used for every accepted item in this audit: stable control-screen
  text (`kf_0065500`, `kf_0116500`, `kf_0123000`, `kf_0157000`, `kf_0242900`, `kf_0258000`),
  or a clearly held tool/component (`kf_0041220`, `kf_0124300`, `kf_0170000`, `kf_0190000`).
- **Transcript-only, no visual attached** — used where dense re-sampling proved the action
  is never filmed: the feeler-gauge measurement in `REAL_WF_0002` step 6 (see
  `docs/keyframe_evidence_review.md`). The spoken instruction and the written spec
  (TG0128) already carried this claim; forcing a visual onto it would have been exactly
  the "assign a visual merely to look complete" defect the brief forbids.
- **Reworded single frame** — used where the frame is genuinely the best available visual
  but the claim built on it over-reached (named an unverifiable component identity, or
  implied a moment the frame can't prove): `kf_0115000` (bench B-roll, kept for what it
  visibly shows, explanation corrected) and `kf_0142700` (roller kept, "cam follower"
  identity and rotation claim moved to transcript-only evidence in `REAL_WF_0001.r2`).
- **Sequence/clip** — not required by anything found in this audit. The one candidate for
  it (proving the SRC_HAAS_0005 roller "spins freely") was resolved by keeping that claim
  on transcript evidence instead, since a sequence built from adjacent frames of a hand
  holding a nearly-stationary part would not visibly prove rotation either — a short clip
  would be the only honest way to show that motion, and none was extracted or promoted
  this session (left as a known gap; see the final report's limitations).

## Adaptive sampling (used for the one re-extraction window this session)

`SRC_HAAS_0001`'s 143000–151750ms window (the claimed feeler-gauge check) was extended
±3s from the original single 146100ms sample and re-sampled at ffmpeg's `fps=4` (250ms
step) rather than one fixed interval, specifically because the original single frame sat
inside a fast-motion band. OpenCV Laplacian-variance sharpness scoring separated three
bands: transitional blur (143500–144250ms, 5–61), a genuinely sharp band (144500–147250ms,
55–68) that still shows only empty reaching hands, and a sustained fast-motion band
(147500–149750ms, 3.7–4.5) holding low for ten consecutive samples — not one outlier frame.
No frame in the full 8.75s window shows a physical feeler gauge. Extraction command:
`ffmpeg -ss 143 -to 152 -i <source> -vf "fps=4,showinfo" -q:v 2 out_%04d.jpg`; original
timestamps taken from `showinfo`'s reported `pts_time` plus the 143000ms seek offset, not
the output filename index.
