"""Deterministic fixture evidence source (test support only).

Serves in-memory files as evidence through the shared evidence mechanics: it
supplies only the storage seams, never a second copy of inventory, selection,
or read behaviour. Fixture-shell policy: exceeding byte bounds raises
(fixture authoring error) rather than silently truncating semantic input.
"""

from __future__ import annotations

import datetime as _datetime

from span.core import model as m
from span.shell.evidence_source import EvidenceSourceBase

__all__ = ["FixtureEvidenceSource"]


class FixtureEvidenceSource(EvidenceSourceBase):
    """EvidenceSource over an explicit file map (tests/fixtures only)."""

    def __init__(self, repository_id: str, files: dict[str, str]) -> None:
        super().__init__(repository_id)
        self._files = dict(files)

    def _paths(self) -> list[str]:
        return sorted(self._files)

    def _exists(self, locator: str) -> bool:
        return locator in self._files

    def _read_bytes(self, locator: str) -> bytes:
        content = self._files.get(locator)
        if content is None:
            raise ValueError(f"unknown evidence locator: {locator}")
        return content.encode("utf-8")

    def _repository_state(self) -> m.RepositoryState:
        return m.RepositoryState(
            repository_id=self._repository_id,
            revision_id="fixture",
            dirty=False,
            state_fingerprint="fixture",
            observed_at=_datetime.datetime.now(_datetime.timezone.utc),
        )
