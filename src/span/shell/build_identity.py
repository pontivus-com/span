"""Observe the packaged build identity without checkout or receipt fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path


def decode_build_identity(text: str) -> dict[str, str] | None:
    try:
        value = json.loads(text)
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    revision = value.get("source_revision")
    digest = value.get("source_digest")
    if (
        not isinstance(revision, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})(?:-dirty)?", revision) is None
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        return None
    return {"source_revision": revision, "source_digest": digest}


def read_build_identity(package_root: Path) -> dict[str, str] | None:
    try:
        return decode_build_identity(
            (package_root / "BUILD_IDENTITY").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError):
        return None


def installed_build_identity() -> dict[str, str] | None:
    return read_build_identity(Path(__file__).resolve().parents[1])
