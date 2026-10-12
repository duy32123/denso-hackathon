"""Official YouTube caption file (WebVTT) -> D1-A transcript utterances."""
from __future__ import annotations

import hashlib
import html
import re

_CUE = re.compile(r"(\d+):(\d\d):(\d\d)\.(\d{3}) --> (\d+):(\d\d):(\d\d)\.(\d{3})")


def _ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_vtt(vtt: str) -> list[dict]:
    """One utterance per cue: wrapped lines joined, entities unescaped, padding dropped."""
    out: list[dict] = []
    for block in re.split(r"\n\s*\n", vtt.replace("\r\n", "\n")):
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            m = _CUE.match(line)
            if not m:
                continue
            text = " ".join(html.unescape(" ".join(lines[i + 1 :])).split())
            if text:
                out.append({"start_ms": _ms(*m.groups()[:4]), "end_ms": _ms(*m.groups()[4:]), "text": text})
            break
    return out


def raw_text(utterances: list[dict]) -> str:
    return " ".join(u["text"] for u in utterances)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
