"""Diem vao duy nhat cho ca hai doi: validate mot thu muc bundle."""

from __future__ import annotations

from pathlib import Path

from .issues import Report
from .loader import load_bundle
from .rules import check_bundle


def validate_bundle(bundle_dir: str | Path) -> Report:
    report = Report(bundle_path=str(bundle_dir))
    bundle = load_bundle(bundle_dir, report)
    if bundle is not None:
        check_bundle(bundle, report)
    return report
