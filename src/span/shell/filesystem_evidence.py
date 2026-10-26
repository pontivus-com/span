"""Filesystem evidence source (production EvidenceSource, plan §5.3).

Serves repository files as evidence over the shared evidence mechanics.
This module owns only the filesystem seams: the walked text inventory, file
existence, bounded byte reads, and the reported repository state. Retrieval
mechanics only; filename, path, or search-anchor matching never establishes
semantic authority (plan §5.3/§6.2).

Skipped unconditionally: `.git/`, `graft/` index output, and files probing
binary (null byte in the first block). Text decodes as UTF-8 with replacement;
fingerprints cover raw bytes so preflight comparison stays exact.
"""

from __future__ import annotations

import datetime as _datetime
import os as _os
import pathlib as _pathlib

from span.core import model as m
from span.shell.evidence_source import EvidenceSourceBase

__all__ = ["FilesystemEvidenceSource", "is_probably_text"]

_SKIP_DIRS = frozenset({".git", "graft", "__pycache__", "node_modules"})
_PROBE_BYTES = 8192


def is_probably_text(path: _pathlib.Path) -> bool:
    """Null-byte probe: binary files are not evidence text."""
    try:
        with open(path, "rb") as handle:
            return b"\x00" not in handle.read(_PROBE_BYTES)
    except OSError:
        return False


class FilesystemEvidenceSource(EvidenceSourceBase):
    """EvidenceSource over a repository working tree."""

    def __init__(self, repository_id: str, root: str | _pathlib.Path) -> None:
        super().__init__(repository_id)
        self._root = _pathlib.Path(root)

    def _paths(self) -> list[str]:
        found: list[str] = []
        # Prune skipped trees before descending: identical output set to the
        # unpruned walk (same is_file/membership/text filters below), without
        # entering .git/graft/caches.
        for current, dirnames, filenames in _os.walk(self._root):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            for name in sorted(filenames):
                if name in _SKIP_DIRS:
                    continue
                path = _pathlib.Path(current) / name
                if not path.is_file():
                    continue
                try:
                    relative = path.relative_to(self._root)
                except ValueError:
                    continue
                if not is_probably_text(path):
                    continue
                found.append(relative.as_posix())
        return sorted(found)

    def _exists(self, locator: str) -> bool:
        return (self._root / locator).is_file()

    def _read_bytes(self, locator: str) -> bytes:
        candidate = self._root / locator
        try:
            resolved = candidate.resolve()
        except OSError as exc:
            raise ValueError(f"unknown evidence locator: {locator}") from exc
        if self._root.resolve() not in resolved.parents:
            raise ValueError(f"evidence escapes repository: {locator}")
        try:
            return resolved.read_bytes()
        except OSError as exc:
            raise ValueError(f"unknown evidence locator: {locator}") from exc

    def _repository_state(self) -> m.RepositoryState:
        return m.RepositoryState(
            repository_id=self._repository_id,
            revision_id=None,
            dirty=False,
            state_fingerprint="filesystem",
            observed_at=_datetime.datetime.now(_datetime.timezone.utc),
        )
