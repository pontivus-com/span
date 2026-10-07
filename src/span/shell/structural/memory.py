"""Deterministic in-memory structural source (plan Phase 1.5).

Implements the StructuralSource port over a declarative repository
description. All outputs are deterministic for identical inputs; the
only wall-clock value is RepositoryState.observed_at (operational
metadata, not semantic state).

Subject locators use ``path`` or ``path:Symbol`` form. The evidence
locator for a location is the file path. Evidence source kind follows a
documented suffix rule (``.md``/``.rst``/``.txt`` → DOCUMENTATION, else
SOURCE_CODE) — retrieval mechanics, never authority.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib as _hashlib
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.ports.structural import StructuralDirection

__all__ = [
    "InMemoryFile",
    "InMemoryEdge",
    "InMemorySubject",
    "InMemoryStructuralSource",
    "fingerprint_content",
    "DOCUMENT_SUFFIXES",
]

DOCUMENT_SUFFIXES = (".md", ".rst", ".txt")


def fingerprint_content(content: str) -> str:
    """Stable sha256 fingerprint for evidence content."""
    return _hashlib.sha256(content.encode("utf-8")).hexdigest()


@_dataclass(frozen=True)
class InMemoryFile:
    path: str
    content: str


@_dataclass(frozen=True)
class InMemoryEdge:
    source_locator: str
    kind: m.StructuralEdgeKind
    target_locator: str


@_dataclass(frozen=True)
class InMemorySubject:
    locator: str
    kind: m.SubjectKind
    display_name: str
    declared_kind: str | None = None


def _file_path(locator: str) -> str:
    return locator.split(":")[0]


def _evidence_kind(path: str) -> m.EvidenceSourceKind:
    return evidence_kind_for_path(path)


def evidence_kind_for_path(path: str) -> m.EvidenceSourceKind:
    """Deterministic evidence-kind rule (retrieval mechanics only)."""
    if path.endswith(DOCUMENT_SUFFIXES):
        return m.EvidenceSourceKind.DOCUMENTATION
    return m.EvidenceSourceKind.SOURCE_CODE


class InMemoryStructuralSource:
    """Deterministic StructuralSource over in-memory repository data."""

    def __init__(
        self,
        repository_id: str,
        files: tuple[InMemoryFile, ...],
        subjects: tuple[InMemorySubject, ...],
        edges: tuple[InMemoryEdge, ...] = (),
        revision: str = "r1",
        dirty: bool = False,
    ) -> None:
        self._repository_id = repository_id
        self._files = {f.path: f.content for f in files}
        self._subjects = subjects
        self._edges = edges
        self._revision = revision
        self._dirty = dirty

    # -- internal helpers -------------------------------------------------

    def file_fingerprint(self, path: str) -> str | None:
        """Current fingerprint for a path; None when the path is unknown."""
        content = self._files.get(path)
        if content is None:
            return None
        return fingerprint_content(content)

    def _state_fingerprint(self) -> str:
        parts = sorted(f"{p}:{fingerprint_content(c)}" for p, c in self._files.items())
        return _hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def _to_subject(self, spec: InMemorySubject) -> m.Subject:
        return m.Subject(
            subject_id=m.SubjectId(
                repository_id=self._repository_id,
                subject_kind=spec.kind,
                canonical_locator=spec.locator,
            ),
            display_name=spec.display_name,
            declared_kind=spec.declared_kind,
        )

    def _evidence_ref(self, path: str) -> m.EvidenceRef:
        fp = self.file_fingerprint(path)
        return m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{path}"),
            repository_id=self._repository_id,
            source_kind=_evidence_kind(path),
            locator=path,
            revision_or_fingerprint=fp,
        )

    # -- StructuralSource port --------------------------------------------

    def repository_state(self, repository_id: str) -> m.RepositoryState:
        self._check_repository(repository_id)
        return m.RepositoryState(
            repository_id=self._repository_id,
            revision_id=self._revision,
            dirty=self._dirty,
            state_fingerprint=self._state_fingerprint(),
            observed_at=_datetime.datetime.now(_datetime.timezone.utc),
        )

    def resolve_subject(
        self,
        repository_id: str,
        selector: m.SubjectSelector,
        bounds: m.QueryBounds,
    ) -> m.SubjectResolution:
        self._check_repository(repository_id)
        if selector.exact_subject_id is not None:
            matches = [
                (s, m.CandidateRankBasis.EXACT_LOCATOR)
                for s in self._subjects
                if self._subject_id_of(s) == selector.exact_subject_id
            ]
        else:
            matches = self._match_name(selector)
        if selector.expected_kinds:
            matches = [x for x in matches if x[0].kind in selector.expected_kinds]
        order = {
            m.CandidateRankBasis.EXACT_LOCATOR: 0,
            m.CandidateRankBasis.EXACT_DECLARATION: 1,
            m.CandidateRankBasis.EXACT_NAME: 2,
            m.CandidateRankBasis.PARTIAL_NAME: 3,
            m.CandidateRankBasis.STRUCTURAL_PROXIMITY: 4,
        }
        matches.sort(key=lambda x: (order[x[1]], x[0].locator))
        candidates = tuple(
            m.SubjectCandidate(
                subject=self._to_subject(s),
                structural_evidence=(),
                rank_basis=rank,
            )
            for s, rank in matches
        )
        if not candidates:
            ambiguity = m.ResolutionAmbiguity.NOT_FOUND
        elif len(candidates) == 1:
            ambiguity = m.ResolutionAmbiguity.RESOLVED
        else:
            ambiguity = m.ResolutionAmbiguity.AMBIGUOUS
        kept = candidates[: bounds.max_subjects]
        return m.SubjectResolution(
            candidates=kept,
            ambiguity=ambiguity,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_subjects,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(candidates),
                truncated_category="candidates" if len(kept) < len(candidates) else None,
                continuation_token=None,
            ),
        )

    def _match_name(
        self, selector: m.SubjectSelector
    ) -> list[tuple[InMemorySubject, m.CandidateRankBasis]]:
        query = selector.name_or_locator
        if not query:
            return []
        # §4.2: SubjectId is repository + kind + canonical locator. An
        # exact locator match is identity, not a ranking input — return
        # only exact matches instead of pooling substring candidates.
        exact = [
            (spec, m.CandidateRankBasis.EXACT_LOCATOR)
            for spec in self._subjects
            if query == spec.locator
            and (not selector.expected_kinds or spec.kind in selector.expected_kinds)
        ]
        if exact:
            return exact
        matches: list[tuple[InMemorySubject, m.CandidateRankBasis]] = []
        for spec in self._subjects:
            if query == spec.display_name:
                matches.append((spec, m.CandidateRankBasis.EXACT_DECLARATION))
            elif query == spec.locator.rsplit(":", 1)[-1].rsplit("/", 1)[-1]:
                matches.append((spec, m.CandidateRankBasis.EXACT_NAME))
            elif query in spec.display_name or query in spec.locator:
                matches.append((spec, m.CandidateRankBasis.PARTIAL_NAME))
        return matches

    def locations(
        self,
        repository_id: str,
        subject: m.SubjectId,
        bounds: m.QueryBounds,
    ) -> m.StructuralLocationPage:
        self._check_repository(repository_id)
        path = _file_path(subject.canonical_locator)
        state = self.repository_state(repository_id)
        if path not in self._files:
            items: tuple[m.StructuralLocation, ...] = ()
        else:
            items = (
                m.StructuralLocation(
                    subject=subject, location=self._evidence_ref(path)
                ),
            )
        kept = items[: bounds.max_results]
        return m.StructuralLocationPage(
            items=kept,
            repository_state=state,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_results,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(items),
                truncated_category="locations" if len(kept) < len(items) else None,
                continuation_token=None,
            ),
            unsupported=False,
        )

    def edges(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        bounds: m.QueryBounds,
    ) -> m.StructuralEdgePage:
        self._check_repository(repository_id)
        locator = subject.canonical_locator
        kinds = set(edge_kinds) if edge_kinds else set(m.StructuralEdgeKind)
        found: list[m.StructuralEdge] = []
        for edge in self._edges:
            if edge.kind not in kinds:
                continue
            if direction in (
                StructuralDirection.DOWNSTREAM,
                StructuralDirection.BOTH,
            ) and edge.source_locator == locator:
                found.append(self._to_edge(edge))
            elif direction in (
                StructuralDirection.UPSTREAM,
                StructuralDirection.BOTH,
            ) and edge.target_locator == locator:
                found.append(self._to_edge(edge))
        found.sort(key=lambda e: (
            e.kind.value,
            e.source.canonical_locator,
            e.target.canonical_locator,
        ))
        kept = tuple(found[: bounds.max_results])
        return m.StructuralEdgePage(
            items=kept,
            repository_state=self.repository_state(repository_id),
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_results,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(found),
                truncated_category="edges" if len(kept) < len(found) else None,
                continuation_token=None,
            ),
            unsupported=False,
        )

    def reach(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        max_depth: int,
        bounds: m.QueryBounds,
    ) -> m.StructuralReachPage:
        self._check_repository(repository_id)
        limit = min(max_depth, bounds.max_depth)
        kinds = set(edge_kinds) if edge_kinds else set(m.StructuralEdgeKind)
        adjacency: dict[str, list[m.StructuralEdge]] = {}
        for edge in self._edges:
            if edge.kind not in kinds:
                continue
            struct = self._to_edge(edge)
            if direction in (
                StructuralDirection.DOWNSTREAM,
                StructuralDirection.BOTH,
            ):
                adjacency.setdefault(edge.source_locator, []).append(struct)
            if direction in (
                StructuralDirection.UPSTREAM,
                StructuralDirection.BOTH,
            ):
                adjacency.setdefault(edge.target_locator, []).append(struct)
        for key in adjacency:
            adjacency[key].sort(
                key=lambda e: (
                    e.kind.value,
                    e.source.canonical_locator,
                    e.target.canonical_locator,
                )
            )
        seen = {subject.canonical_locator}
        frontier = [subject.canonical_locator]
        nodes: list[m.StructuralReachNode] = []
        via: dict[str, m.StructuralEdge | None] = {
            subject.canonical_locator: None
        }
        truncated = False
        for depth in range(1, limit + 1):
            nxt: list[str] = []
            for current in frontier:
                for edge in adjacency.get(current, []):
                    other = (
                        edge.target.canonical_locator
                        if edge.source.canonical_locator == current
                        else edge.source.canonical_locator
                    )
                    if other not in seen:
                        seen.add(other)
                        via[other] = edge
                        nxt.append(other)
            nxt.sort()
            for locator in nxt:
                nodes.append(
                    m.StructuralReachNode(
                        subject=m.SubjectId(
                            repository_id=self._repository_id,
                            subject_kind=self._kind_of(locator),
                            canonical_locator=locator,
                        ),
                        depth=depth,
                        via=via[locator],
                    )
                )
            frontier = nxt
            if not frontier:
                break
        kept = tuple(nodes[: bounds.max_results])
        if len(kept) < len(nodes):
            truncated = True
        return m.StructuralReachPage(
            items=kept,
            repository_state=self.repository_state(repository_id),
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_results,
                requested_max_depth=limit,
                returned_results=len(kept),
                truncated=truncated,
                truncated_category="reach" if truncated else None,
                continuation_token=None,
            ),
            unsupported=False,
        )

    # -- private --------------------------------------------------------

    def _check_repository(self, repository_id: str) -> None:
        if repository_id != self._repository_id:
            raise ValueError(f"unknown repository: {repository_id}")

    def _subject_id_of(self, spec: InMemorySubject) -> m.SubjectId:
        return m.SubjectId(
            repository_id=self._repository_id,
            subject_kind=spec.kind,
            canonical_locator=spec.locator,
        )

    def _kind_of(self, locator: str) -> m.SubjectKind:
        for spec in self._subjects:
            if spec.locator == locator:
                return spec.kind
        return m.SubjectKind.OTHER

    def _to_edge(self, edge: InMemoryEdge) -> m.StructuralEdge:
        return m.StructuralEdge(
            source=m.SubjectId(
                repository_id=self._repository_id,
                subject_kind=self._kind_of(edge.source_locator),
                canonical_locator=edge.source_locator,
            ),
            kind=edge.kind,
            target=m.SubjectId(
                repository_id=self._repository_id,
                subject_kind=self._kind_of(edge.target_locator),
                canonical_locator=edge.target_locator,
            ),
            evidence=self._evidence_ref(_file_path(edge.source_locator)),
        )
