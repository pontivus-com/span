"""Deterministic fixture evidence source (plan Phase 1.6).

Serves in-memory files as evidence: inventory (fingerprints), selection
(relevance only — seeds plus structural context, never authority), and
bounded reads. Fixture-shell policy: exceeding byte bounds raises
(fixture authoring error) rather than silently truncating semantic
input.
"""

from __future__ import annotations

import datetime as _datetime

from span.core import model as m
from span.shell import paging as _paging
from span.shell.structural.memory import fingerprint_content

__all__ = ["FixtureEvidenceSource"]


class FixtureEvidenceSource:
    """EvidenceSource over an explicit file map (tests/fixtures only)."""

    def __init__(
        self, repository_id: str, files: dict[str, str]
    ) -> None:
        self._repository_id = repository_id
        self._files = dict(files)

    def _check_repository(self, repository_id: str) -> None:
        if repository_id != self._repository_id:
            raise ValueError(f"unknown repository: {repository_id}")

    def _ref_for(self, path: str) -> m.EvidenceRef:
        from span.shell.structural.memory import evidence_kind_for_path

        return m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{path}"),
            repository_id=self._repository_id,
            source_kind=evidence_kind_for_path(path),
            locator=path,
            revision_or_fingerprint=fingerprint_content(self._files[path]),
        )

    def _expand_paths(self, paths: tuple[str, ...]) -> list[str]:
        """Scope paths naming files stay; paths naming a directory
        prefix expand to the files beneath (sorted). Retrieval only."""
        expanded: list[str] = []
        for path in dict.fromkeys(paths):
            if path in self._files:
                expanded.append(path)
                continue
            prefix = path.rstrip("/") + "/"
            expanded.extend(
                sorted(
                    p for p in self._files
                    if p == path or p.startswith(prefix)
                )
            )
        return expanded

    def inventory_evidence(
        self,
        repository_id: str,
        scope: m.EvidenceScope,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.EvidenceInventoryPage:
        self._check_repository(repository_id)
        if scope.paths or scope.evidence_refs:
            paths = self._expand_paths(tuple(scope.paths))
            ref_paths = [
                r.locator for r in scope.evidence_refs if r.locator in self._files
            ]
            paths = sorted(set(paths) | set(ref_paths))
        else:
            paths = sorted(self._files)
        items = tuple(
            m.EvidenceInventoryItem(
                evidence_ref=self._ref_for(p),
                content_fingerprint=fingerprint_content(self._files[p]),
            )
            for p in paths
        )
        kept, bound_info = _paging.paginate(
            items, bounds.max_evidence_units, "inventory", page_token
        )
        # NOTE: the repository state for inventory pages is operational
        # metadata supplied by the caller context in Phase 1 flows; the
        # fixture source reports a stable fingerprint-only baseline here.
        return m.EvidenceInventoryPage(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=m.RepositoryState(
                repository_id=self._repository_id,
                revision_id="fixture",
                dirty=False,
                state_fingerprint="fixture",
                observed_at=self._now(),
            ),
            bound_info=bound_info,
        )

    def list_inventory_entries(
        self,
        repository_id: str,
        scope: m.EvidenceScope,
        fingerprint_locators: tuple[str, ...] = (),
    ) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
        self._check_repository(repository_id)
        if scope.paths or scope.evidence_refs:
            expanded = self._expand_paths(tuple(scope.paths))
            ref_paths = [
                r.locator for r in scope.evidence_refs if r.locator in self._files
            ]
            paths = sorted(set(expanded) | set(ref_paths))
        else:
            paths = sorted(self._files)
        return (
            tuple((p, f"ev-{p}") for p in paths if p in self._files),
            {
                loc: fingerprint_content(self._files[loc])
                for loc in dict.fromkeys(fingerprint_locators)
                if loc in self._files
            },
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
            if key not in seen and ref.locator in self._files:
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
                truncated_category="selection" if len(kept) < len(ordered) else None,
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
            content = self._files.get(ref.locator)
            if content is None:
                raise ValueError(f"unknown evidence locator: {ref.locator}")
            total += len(content.encode("utf-8"))
            if total > bounds.max_evidence_bytes:
                raise ValueError(
                    "fixture evidence exceeds max_evidence_bytes "
                    f"({bounds.max_evidence_bytes})"
                )
            units.append(
                m.EvidenceUnit(
                    evidence_ref=ref,
                    content=content,
                    content_fingerprint=fingerprint_content(content),
                )
            )
        if len(units) > bounds.max_evidence_units:
            raise ValueError(
                "fixture evidence exceeds max_evidence_units "
                f"({bounds.max_evidence_units})"
            )
        return tuple(units)

    @staticmethod
    def _now() -> _datetime.datetime:
        return _datetime.datetime.now(_datetime.timezone.utc)
