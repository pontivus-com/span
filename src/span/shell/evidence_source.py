"""One evidence-source implementation over a storage seam (plan §2.6, S9/D4).

Inventory, selection, and bounded reads are the same retrieval mechanics
whatever the bytes come from. This base owns that behaviour once; a
concrete source supplies four storage seams: which locators exist, the
ordered locator inventory, the raw bytes for one locator, and the
repository state it reports. No semantic authority is assigned here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import hashlib as _hashlib
from typing import cast as _cast
from span.core import model as m
from span.core import paging as _paging
from span.shell.structural.memory import evidence_kind_for_path

__all__ = ["EvidenceSourceBase"]


class EvidenceSourceBase(ABC):
    """Shared EvidenceSource mechanics over a concrete storage backend."""

    def __init__(self, repository_id: str) -> None:
        self._repository_id = repository_id

    # -- storage seams ---------------------------------------------------

    @abstractmethod
    def _paths(self) -> list[str]:
        """Every locator the backend can serve, in deterministic order."""

    @abstractmethod
    def _exists(self, locator: str) -> bool:
        """Whether one locator names a servable file."""

    @abstractmethod
    def _read_bytes(self, locator: str) -> bytes:
        """Raw bytes for one locator; unknown or escaping locators raise."""

    @abstractmethod
    def _repository_state(self) -> m.RepositoryState:
        """Operational state metadata reported with inventory pages."""

    # -- shared mechanics -------------------------------------------------

    def _check_repository(self, repository_id: str) -> None:
        if repository_id != self._repository_id:
            raise ValueError(f"unknown repository: {repository_id}")

    def _fingerprint(self, locator: str) -> str:
        return _hashlib.sha256(self._read_bytes(locator)).hexdigest()

    def _ref_for(self, path: str, fingerprint: str) -> m.EvidenceRef:
        return m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{path}"),
            repository_id=self._repository_id,
            source_kind=evidence_kind_for_path(path),
            locator=path,
            revision_or_fingerprint=fingerprint,
        )

    def _expand_paths(self, paths: tuple[str, ...]) -> list[str]:
        """Scope paths naming files stay; directory prefixes expand."""
        expanded: list[str] = []
        for path in dict.fromkeys(paths):
            if self._exists(path):
                expanded.append(path)
                continue
            prefix = path.rstrip("/") + "/"
            expanded.extend(
                found for found in self._paths() if found.startswith(prefix)
            )
        return expanded

    def _item_for(self, path: str) -> m.EvidenceInventoryItem:
        """One inventory item; each file read and hashed exactly once."""
        fingerprint = self._fingerprint(path)
        return m.EvidenceInventoryItem(
            evidence_ref=self._ref_for(path, fingerprint),
            content_fingerprint=fingerprint,
        )

    # -- port operations --------------------------------------------------

    def list_inventory_entries(
        self,
        repository_id: str,
        scope: m.EvidenceScope,
        fingerprint_locators: tuple[str, ...] = (),
    ) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
        self._check_repository(repository_id)
        all_paths = self._paths()
        if scope.paths or scope.evidence_refs:
            paths = sorted(
                set(self._expand_paths(tuple(scope.paths)))
                | {
                    ref.locator
                    for ref in scope.evidence_refs
                    if self._exists(ref.locator)
                }
            )
        else:
            paths = all_paths
        in_tree = set(all_paths)
        return (
            tuple((path, f"ev-{path}") for path in paths if path in in_tree),
            {
                locator: self._fingerprint(locator)
                for locator in dict.fromkeys(fingerprint_locators)
                if locator in in_tree
            },
        )

    def inventory_evidence(
        self,
        repository_id: str,
        scope: m.EvidenceScope,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.EvidenceInventoryPage:
        self._check_repository(repository_id)
        if scope.paths or scope.evidence_refs:
            paths = sorted(
                set(self._expand_paths(tuple(scope.paths)))
                | {
                    ref.locator
                    for ref in scope.evidence_refs
                    if self._exists(ref.locator)
                }
            )
        else:
            paths = self._paths()
        # Slice before fingerprinting: pages after the first must not
        # re-hash the whole inventory (snapshot paging walks every page).
        kept_paths, bound_info = _paging.paginate(
            tuple(paths),
            bounds.max_evidence_units,
            "inventory",
            page_token,
        )
        items = tuple(self._item_for(_cast(str, path)) for path in kept_paths)
        return m.EvidenceInventoryPage(
            items=items,  # type: ignore[arg-type]
            repository_state=self._repository_state(),
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
            if key not in seen and self._exists(ref.locator):
                seen.add(key)
                ordered.append(ref)

        for seed in known_authority_seeds:
            _add(seed)
        for observation in structural_context:
            if observation.location is not None:
                _add(observation.location)
        kept = tuple(ordered[: bounds.max_evidence_units])
        return m.EvidenceSelection(
            selected_refs=kept,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_evidence_units,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(ordered),
                truncated_category="selection" if len(kept) < len(ordered) else None,
                continuation_token=None,
            ),
        )

    def read_exact(
        self,
        repository_id: str,
        request: m.EvidenceRequest,
        bounds: m.QueryBounds,
    ) -> m.EvidenceUnit | m.EvidenceSourceFailure:
        """Read one exact locator without structural subjects.

        Missing, non-text/unservable, and oversized sources are distinct
        failures; a provider read error is raised, not disguised as a source
        outcome.
        """
        self._check_repository(repository_id)
        if not self._exists(request.locator):
            return m.EvidenceSourceFailure(
                request,
                m.EvidenceSourceFailureKind.MISSING,
                f"unknown evidence locator: {request.locator}",
            )
        if request.locator not in set(self._paths()):
            return m.EvidenceSourceFailure(
                request,
                m.EvidenceSourceFailureKind.UNREADABLE,
                "not servable text evidence",
            )
        data = self._read_bytes(request.locator)
        if len(data) > bounds.max_evidence_bytes:
            return m.EvidenceSourceFailure(
                request,
                m.EvidenceSourceFailureKind.UNREADABLE,
                "evidence exceeds max_evidence_bytes",
            )
        fingerprint = _hashlib.sha256(data).hexdigest()
        return m.EvidenceUnit(
            evidence_ref=self._ref_for(request.locator, fingerprint),
            content=data.decode("utf-8", errors="replace"),
            content_fingerprint=fingerprint,
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
                    content_fingerprint=_hashlib.sha256(data).hexdigest(),
                )
            )
        if len(units) > bounds.max_evidence_units:
            raise ValueError(
                "evidence exceeds max_evidence_units " f"({bounds.max_evidence_units})"
            )
        return tuple(units)
