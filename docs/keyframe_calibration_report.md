# Keyframe visual-capability calibration — D1-A evidence hardening

Performed 2026-09-14, before any replacement frame was accepted into a draft. Uses real
frames already in hand from the dev sources (no holdout content touched) rather than a
synthetic exercise, because the audit that followed needed exactly these distinctions and
they are drawn from the actual dense-sampling and full-keyframe-audit work done this
session — not staged afterward.

## The six frames

| Case | Frame | Source |
|---|---|---|
| Clearly correct action/state frame | `acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0065500.jpg` | committed keyframe |
| Immediately before | candidate at 144000ms (SRC_HAAS_0001 dense window, index 5 of 36) — Laplacian sharpness 0.7 | scratch extraction, this session |
| Immediately after | candidate at 144250ms (index 6) — sharpness 16.2, transitioning back into focus | scratch extraction, this session |
| Blurred / obstructed | candidate at 147500–149750ms band (indices 19–28) — sharpness held at 3.7–4.5 across ten consecutive frames, confirming sustained motion blur, not a one-frame outlier | scratch extraction, this session |
| Visually similar but wrong operation | `acquisition/preprocessing/keyframes/SRC_HAAS_0005/kf_0142700.jpg` compared against `SRC_HAAS_0003/kf_0190000.jpg` — both show a gloved hand gripping a metal part near tool-holder hardware, but on two different machines/operations (pocket teardown vs. double-arm recovery) | committed keyframes |
| Relevant screen text | `acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0242900.jpg` | committed keyframe |

## Structured output

```json
[
  {"source_id": "SRC_HAAS_0003", "timestamp_ms": 65500, "visible_actor_action": null,
   "visible_component": "control screen", "visible_tool": null,
   "visible_machine_state": "alarm active, automatic recovery offered",
   "visible_screen_text": "2066 TOOL CHANGER HOME POSITION FAULT / AUTOMATIC RECOVERY",
   "image_quality": {"sharpness": "good", "occlusion": "none", "lighting": "good"},
   "evidence_adequacy": "supports",
   "reason": "Every character of the alarm text is individually legible; directly matches the claimed alarm code and label."},

  {"source_id": "SRC_HAAS_0001", "timestamp_ms": 144000, "visible_actor_action": "presenter's arm mid-motion, blurred",
   "visible_component": null, "visible_tool": null, "visible_machine_state": null, "visible_screen_text": null,
   "image_quality": {"sharpness": "poor", "occlusion": "none", "lighting": "usable"},
   "evidence_adequacy": "cannot_determine",
   "reason": "Motion blur (Laplacian variance 0.7, the lowest in the 36-frame window) makes the arm and hand shape indistinct; nothing beyond 'a limb is moving' can be read from this frame."},

  {"source_id": "SRC_HAAS_0001", "timestamp_ms": 144250, "visible_actor_action": "presenter's hand settling near the double arm",
   "visible_component": "double arm (partial)", "visible_tool": null, "visible_machine_state": null, "visible_screen_text": null,
   "image_quality": {"sharpness": "poor", "occlusion": "partial", "lighting": "usable"},
   "evidence_adequacy": "does_not_support",
   "reason": "Sharpness has recovered somewhat (16.2) but the frame is transitional -- the hand has not yet reached a settled position and no tool or gauge is visible; rejected as neither a clean before nor a clean action frame."},

  {"source_id": "SRC_HAAS_0001", "timestamp_ms": 148000, "visible_actor_action": null,
   "visible_component": null, "visible_tool": null, "visible_machine_state": null, "visible_screen_text": null,
   "image_quality": {"sharpness": "poor", "occlusion": "none", "lighting": "usable"},
   "evidence_adequacy": "cannot_determine",
   "reason": "Ten consecutive frames (147500-149750ms) hold sharpness 3.7-4.5, confirming sustained fast motion, not a single bad sample; nothing legible in any of them. This is the window originally claimed to show a feeler-gauge measurement -- it does not, and no adjacent sharp frame in the wider 143000-151750ms window shows a gauge either."},

  {"source_id": "SRC_HAAS_0005", "timestamp_ms": 142700, "visible_actor_action": "gloved hands gripping a cylindrical roller on a removed machined part",
   "visible_component": "removed pocket assembly, cylindrical roller", "visible_tool": null,
   "visible_machine_state": null, "visible_screen_text": null,
   "image_quality": {"sharpness": "good", "occlusion": "partial", "lighting": "usable"},
   "evidence_adequacy": "partial",
   "reason": "Clearly shows hands holding a machined part with a roller -- but nothing in the frame identifies the roller as a 'cam follower' or shows it rotating; that identity and the free-spin check are spoken, not visible. Visually similar in composition to SRC_HAAS_0003's kf_0190000 (gloved hand + metal tool-holder hardware) despite being a different machine, different operation, and different claim -- the two must not be conflated by appearance alone."},

  {"source_id": "SRC_HAAS_0003", "timestamp_ms": 242900, "visible_actor_action": null,
   "visible_component": "control screen", "visible_tool": null,
   "visible_machine_state": "arm at origin, awaiting operator action",
   "visible_screen_text": "Manual tool changer operation / ATC REV - Rotate double arm towards origin / ... / Suggested next action: Raise pocket up / Arm at ORIGIN",
   "image_quality": {"sharpness": "good", "occlusion": "none", "lighting": "good"},
   "evidence_adequacy": "supports",
   "reason": "All listed command text and the suggested-next-action box are individually legible and match the claim verbatim."}
]
```

## Gate result

- **Correct frame identified:** yes (`kf_0065500`, `kf_0242900` both scored `supports` with verbatim screen text).
- **Visually similar but wrong operation rejected as such:** yes — `kf_0142700` was not conflated with `kf_0190000` despite similar composition (gloved hand + metal hardware); each was judged against its own claim and machine context, and `kf_0142700`'s claim was found to over-assert identity.
- **Obstructed/blurred frame flagged, not silently accepted:** yes — both the 144000ms and 148000ms bands were flagged `cannot_determine`/poor sharpness rather than passed through, and the 148000ms finding (`no gauge visible anywhere in the window`) directly caused the removal of `REAL_WF_0002_CL_017`'s visual evidence in the real audit.
- **No invented components:** yes — the model declined to name the SRC_HAAS_0005 roller a "cam follower" from pixels alone, which is exactly the defect being corrected in `REAL_WF_0001.r2`.

Gate passed. Proceeded to the full 20-keyframe audit (`docs/keyframe_evidence_review.md`)
using this same standard.
