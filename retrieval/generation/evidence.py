"""Offline evidence opening. A retained caption is NOT a verified live video.

Only keyframes below the configured keyframe root may be read. No server-side URL
fetching, arbitrary filesystem reads, or synthetic video links are performed.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from knowflow_contracts.models import Evidence, Source


def normalized(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def external_url(url: str | None) -> str | None:
    try:
        parts = urlsplit(url or "")
        if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password:
            return url
    except ValueError:
        pass
    return None


@dataclass(frozen=True)
class EvidenceView:
    available: bool
    kind: str
    text: str | None = None
    asset_path: Path | None = None
    media_type: str | None = None


class EvidenceAccess:
    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.keyframe_root = self.repo_root / "acquisition/preprocessing/keyframes"

    def _image(self, uri: str | None) -> EvidenceView:
        if not uri or ":" in uri or uri.startswith(("/", "\\")):
            return EvidenceView(False, "unavailable")
        try:
            from PIL import Image
        except ImportError:
            return EvidenceView(False, "unavailable")
        try:
            path = (self.repo_root / uri).resolve()
            if not path.is_relative_to(self.keyframe_root.resolve()) or not path.is_file():
                return EvidenceView(False, "unavailable")
            if path.stat().st_size > 20 * 1024 * 1024:
                return EvidenceView(False, "unavailable")
            with Image.open(path) as picture:
                media = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(picture.format)
                if media is None or picture.width * picture.height > 20_000_000:
                    return EvidenceView(False, "unavailable")
                picture.verify()
            # A valid header alone is not sufficient: the image must decode too.
            with Image.open(path) as picture:
                picture.load()
            return EvidenceView(True, "keyframe", asset_path=path, media_type=media)
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            pass
        return EvidenceView(False, "unavailable")

    def view(self, evidence: Evidence, source: Source) -> EvidenceView:
        if evidence.source_id != source.source_id:
            return EvidenceView(False, "unavailable")
        if source.source_type == "synthetic":
            text = evidence.quote or evidence.observation_note or source.raw_text
            return EvidenceView(bool(text), "synthetic_text", text=text)
        if evidence.modality == "visual":
            return self._image(evidence.asset_uri)
        quote, raw = normalized(evidence.quote or ""), normalized(source.raw_text or "")
        if not quote or quote not in raw:
            return EvidenceView(False, "unavailable")
        if evidence.modality == "speech":
            loc = evidence.locator
            valid = (evidence.transcript_origin != "none" and loc.start_ms is not None
                     and loc.end_ms is not None and source.duration_ms is not None
                     and 0 <= loc.start_ms < loc.end_ms <= source.duration_ms)
            return EvidenceView(valid, "retained_transcript" if valid else "unavailable", text=evidence.quote)
        if evidence.modality == "text" and (evidence.locator.text_span or evidence.locator.page):
            return EvidenceView(True, "retained_text", text=evidence.quote)
        return EvidenceView(False, "unavailable")
