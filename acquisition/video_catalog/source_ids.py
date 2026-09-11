"""Persisted D1-A source ID allocator.

Keyed on canonical URL, not title/order, so reruns are idempotent (D1-A prompt
section 3: "Allocate IDs through code and persist them... Do not let an LLM
invent IDs independently on reruns.").
"""
from __future__ import annotations

import json
import os


class SourceIdAllocator:
    def __init__(self, registry_path: str):
        self.registry_path = registry_path
        if os.path.exists(registry_path):
            with open(registry_path, encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {"next_seq": 1, "urls": {}}

    def get_or_create(self, canonical_url: str) -> str:
        urls = self._data["urls"]
        if canonical_url in urls:
            return urls[canonical_url]
        sid = f"SRC_HAAS_{self._data['next_seq']:04d}"
        self._data["next_seq"] += 1
        urls[canonical_url] = sid
        self._save()
        return sid

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.registry_path) or ".", exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
