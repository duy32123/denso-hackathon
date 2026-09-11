"""D1-A checks not already covered by knowflow_contracts.validate_bundle
(D1-A prompt section 14): split leakage, checksum format, transcript bounds.
"""
from __future__ import annotations

import json
import re

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def check_no_split_leakage(dev_ids: set[str], holdout_ids: set[str]) -> list[str]:
    leaked = dev_ids & holdout_ids
    return [f"source_id {sid} appears in both dev and holdout" for sid in sorted(leaked)]


def check_sha256_format(hashes: dict[str, str | None]) -> list[str]:
    errors = []
    for label, value in hashes.items():
        if value is None:
            continue
        if not _SHA256_RE.match(value):
            errors.append(f"{label}: content_sha256 is not 64 lowercase hex chars: {value!r}")
    return errors


def check_transcript_bounds(raw_json_path: str, duration_ms: int) -> list[str]:
    with open(raw_json_path, encoding="utf-8") as f:
        data = json.load(f)
    errors = []
    for i, u in enumerate(data.get("utterances", [])):
        start, end = u["start_ms"], u["end_ms"]
        if not (start < end):
            errors.append(f"utterance[{i}]: start_ms {start} is not < end_ms {end}")
        if end > duration_ms:
            errors.append(f"utterance[{i}]: end_ms {end} exceeds duration_ms {duration_ms}")
        if start < 0:
            errors.append(f"utterance[{i}]: start_ms {start} is negative")
    return errors
