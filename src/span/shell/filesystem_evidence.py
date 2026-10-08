"""Filesystem evidence source (production EvidenceSource, plan §5.3).

Serves repository files as evidence: inventory (byte fingerprints),
selection (relevance only — seeds plus structural context, never
authority), and bounded reads. Retrieval mechanics only; filename,
path, or search-anchor matching never establishes semantic authority
(plan §5.3/§6.2).

Skipped unconditionally: `.git/`, `graft/` index output, and files
probing binary (null byte in the first block). Text decodes as UTF-8
with replacement; fingerprints cover raw bytes so preflight comparison
stays exact.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib as _hashlib
import pathlib as _pathlib

from span.core import model as m
from span.shell import paging as _paging
from span.shell.structural.memory import evidence_kind_for_path

__all__ = ["FilesystemEvidenceSource", "is_probably_text"]

_SKIP_DIRS = frozenset({".git", "graft", "__pycache__", "node_modules"})
_PROBE_BYTES = 8192


def _fingerprint_bytes(data: bytes) -> str:
    return _hashlib.sha256(data).hexdigest()


def is_probably_text(path: _pathlib.Path) -> bool:
    """Null-byte probe: binary files are not evidence text."""
    try:
        with open(path, "rb") as handle:
            return b"\x00" not in handle.read(_PROBE_BYTES)
    except OSError:
        return False


class FilesystemEvidenceSource:
    """EvidenceSource over a repository working tree."""

    def __init__(
        self, repository_id: str, root: str | _pathlib.Path
    ) -> None:
        self._repository_id = repository_id
        self._root = _pathlib.Path(root)

    def _check_repository(self, repository_id: str) -> None:
        if repository_id != self._repository_id:
            raise ValueError(f"unknown repository: {repository_id}")

    def _paths(self) -> list[str]:
        found: list[str] = []
        for path in sorted(self._root.rglob("*")):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(self._root)
            except ValueError:
                continue
            if any(part in _SKIP_DIRS for part in relative.parts):
                continue
            if not is_probably_text(path):
                continue
            found.append(relative.as_posix())
        return found

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

    def list_inventory_entries(
        self,
        repository_id: str,
        fingerprint_locators: tuple[str, ...] = (),
    ) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
        self._check_repository(repository_id)
        paths = self._paths()
        in_tree = set(paths)
        return (
            tuple((p, f"ev-{p}") for p in paths),
            {
                loc: _fingerprint_bytes(self._read_bytes(loc))
                for loc in dict.fromkeys(fingerprint_locators)
                if loc in in_tree
            },
        )

    def _item_for(self, path: str) -> m.EvidenceInventoryItem:
        """One inventory item; each file read and hashed exactly once."""
        fingerprint = _fingerprint_bytes(self._read_bytes(path))
        return m.EvidenceInventoryItem(
            evidence_ref=self._ref_for(path, fingerprint),
            content_fingerprint=fingerprint,
        )

    def _ref_for(self, path: str, fingerprint: str) -> m.EvidenceRef:
        return m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{path}"),
            repository_id=self._repository_id,
            source_kind=evidence_kind_for_path(path),
            locator=path,
            revision_or_fingerprint=fingerprint,
        )

    def _expand_paths(self, paths: tuple[str, ...]) -> list[str]:
        """Expand scope paths: files stay; directories expand to the
        text files beneath them (sorted). Deterministic retrieval
        only — expansion never assigns relevance or authority."""
        expanded: list[str] = []
        for path in dict.fromkeys(paths):
            candidate = self._root / path
            if candidate.is_file():
                expanded.append(path)
                continue
            if candidate.is_dir():
                prefix = path.rstrip("/") + "/"
                for found in sorted(self._paths()):
                    if found == path or found.startswith(prefix):
                        expanded.append(found)
        return expanded

    def inventory_evidence(
        self,
        repository_id: str,
        scope: m.EvidenceScope,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.EvidenceInventoryPage:
        self._check_repository(repository_id)
        if scope.paths:
            paths = self._expand_paths(scope.paths)
        elif scope.evidence_refs:
            paths = [
                r.locator for r in scope.evidence_refs
                if (self._root / r.locator).is_file()
            ]
        else:
            paths = self._paths()
        # Slice before fingerprinting: pages after the first must not
        # re-hash the whole tree (snapshot paging in §8.5 walks every
        # page). Path order is deterministic, so kept items and
        # BoundInfo are identical to fingerprint-then-slice.
        kept_paths, bound_info = _paging.paginate(
            tuple(paths), bounds.max_evidence_units,
            "inventory", page_token,
        )
        items = tuple(self._item_for(p) for p in kept_paths)
        return m.EvidenceInventoryPage(
            items=items,  # type: ignore[arg-type]
            repository_state=m.RepositoryState(
                repository_id=self._repository_id,
                revision_id=None,
                dirty=False,
                state_fingerprint="filesystem",
                observed_at=_datetime.datetime.now(_datetime.timezone.utc),
            ),
            bound_info=bound_info,
        )

    def select_evidence(
        self,
        repository_id: str,
        subject: m.SubjectId,
        structural_context: tuple[m.StructuralObservation, ...],
        known_authority_seeds: tuple[m.EvidenceRef, ...],
        bounds: m.QueryBounds,
    ) -> m.EvidenceSelection:
        self._check_repository(repository_id)
        ordered: list[m.EvidenceRef] = []
        seen: set[str] = set()

        def _add(ref: m.EvidenceRef) -> None:
            key = ref.evidence_id.value
            if key not in seen and (self._root / ref.locator).is_file():
                seen.add(key)
                ordered.append(ref)

        for seed in known_authority_seeds:
            _add(seed)
        for obs in structural_context:
            if obs.location is not None:
                _add(obs.location)
        kept = tuple(ordered[: bounds.max_evidence_units])
        return m.EvidenceSelection(
            selected_refs=kept,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_evidence_units,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(ordered),
                truncated_category=(
                    "selection" if len(kept) < len(ordered) else None
                ),
                continuation_token=None,
            ),
        )

    def read_evidence(
        self,
        refs: tuple[m.EvidenceRef, ...],
        bounds: m.QueryBounds,
    ) -> tuple[m.EvidenceUnit, ...]:
        total = 0
        units: list[m.EvidenceUnit] = []
        for ref in refs:
            data = self._read_bytes(ref.locator)
            total += len(data)
            if total > bounds.max_evidence_bytes:
                raise ValueError(
                    "evidence exceeds max_evidence_bytes "
                    f"({bounds.max_evidence_bytes})"
                )
            units.append(
                m.EvidenceUnit(
                    evidence_ref=ref,
                    content=data.decode("utf-8", errors="replace"),
                    content_fingerprint=_fingerprint_bytes(data),
                )
            )
        if len(units) > bounds.max_evidence_units:
            raise ValueError(
                "evidence exceeds max_evidence_units "
                f"({bounds.max_evidence_units})"
            )
        return tuple(units)
