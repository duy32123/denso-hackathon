# Keyframe capability audit — D1-A evidence hardening

Performed 2026-09-14 as part of the keyframe-evidence-accuracy correction. Every capability
below was already present in this environment; nothing new was installed. What changed is
*which* capability is allowed to make a selection decision.

## Inventory

| Need | Capability | Version / source | Role in this pipeline |
|---|---|---|---|
| Frame extraction | ffmpeg | `9.0-full_build` (Gyan.dev, via winget: `Gyan.FFmpeg`) | Extracts candidate JPEGs at exact seek points; `showinfo` filter reports the actually-presented PTS, which is what gets recorded as `original_timestamp_ms` — never the requested `-ss` value, which can be off by up to one frame interval on a seek. |
| Media probing | ffprobe | `9.0-full_build` (same package) | Duration, frame rate (SRC_HAAS_0001 = 60000/1001 ≈ 59.94fps, SRC_HAAS_0003 = 30fps, SRC_HAAS_0005 = 30000/1001 ≈ 29.97fps), stream bounds. |
| Sharpness / motion pre-filter | opencv-python | `4.13.0.92` | Laplacian variance for blur (used this session to rank the 36-frame SRC_HAAS_0001 143000–151750ms candidate window; scores ranged 0.7–68.1, cleanly separating the in-focus band from two blurred bands). A *pre-filter only* — it narrows what gets shown to the vision judge, it never accepts or rejects evidence itself. |
| Array / image IO | numpy `2.3.5`, Pillow `12.3.0` | already installed | Backing libraries for the above. |
| **Visual understanding (the judge)** | **Claude Opus 5** (`claude-opus-5`), in-session | Anthropic, current session | The only component that reads actual pixels and decides whether a frame supports its claimed evidence purpose. Every accept/reject/replace verdict in `data/keyframes/keyframe_selections.jsonl` was made this way — by opening the JPEG and comparing it against the claim text, not by inspecting a filename or a timestamp. |

## Deliberately not installed

| Candidate | Why not |
|---|---|
| PySceneDetect | `ffmpeg`'s own `select='gt(scene,N)'` / dense fixed-interval sampling plus manual sharpness ranking covered every case this session needed; adding a second scene-detection dependency for a capability already reachable through the installed ffmpeg build would violate "smallest trustworthy capability set." |
| Tesseract OCR | The multimodal model reads the Haas control-screen text natively and correctly (see calibration below: it transcribed "2066 TOOL CHANGER HOME POSITION FAULT" and "Tool changer recovery completed. Press 'E' to exit." verbatim from the pixels). A second, weaker OCR path would add a dependency without adding capability. |
| A scripted Anthropic API vision adapter (e.g. via `anthropic` SDK, already in `pyproject.toml`) | No API key exists in this environment (`.env` absent; `.env.example` only has Gemini/generic `LLM_API_KEY` placeholders). A selection pipeline that cannot be calibrated in the environment that ships it must not be the thing that actually selects evidence — the brief is explicit about this. In-session Claude reading the bytes directly is the calibrated, provable path. |
| Any package requiring new credentials or broad permissions | None were needed; nothing was installed that requests anything beyond local file/process access it already had. |

## Pinning

`ffmpeg`/`ffprobe` 9.0-full_build and `opencv-python` 4.13.0.92 are recorded here and in
`pyproject.toml`'s new `media` optional-dependency group (`opencv-python==4.13.0.92`,
`numpy==2.3.5`, `Pillow==12.3.0` — the ffmpeg binary itself is a system tool, pinned by
version string in the media inventory's `producer_version` field per keyframe, as it
already was).
