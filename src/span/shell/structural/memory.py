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
from span.ports.structural import StaleContinuationError
from span.ports.structural import StructuralDirection
from span.shell import paging as _paging

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

    def describe_current(
        self,
        repository_id: str,
    ) -> m.Freshness:
        """In-memory source has no separate index: always current."""
        self._check_repository(repository_id)
        return m.Freshness(
            state=m.FreshnessState.CURRENT,
            reason="in-memory source has no separate index",
        )

    def ensure_current(
        self,
        repository_id: str,
    ) -> m.Freshness:
        """No-op: nothing to rebuild for an in-memory source."""
        return self.describe_current(repository_id)

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
                truncated_category=(
                    "candidates" if len(kept) < len(candidates) else None
                ),
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

    def _index_version(self) -> str:
        """Listing version binding cursors (Addendum F §4.3).

        In-memory content is the index: any mutation replaces the
        instance, so the content fingerprint is a stable version.
        """
        return f"mem-{self._state_fingerprint()[:16]}"

    def _scoped_version(self, scope: m.EvidenceScope | None) -> str:
        """Index version bound to the exact scope (J-10 token identity)."""
        base = self._index_version()
        if scope is None or not (scope.paths or scope.evidence_refs):
            return base
        return f"{base}|{m.evidence_scope_fingerprint(scope)}"

    def _versioned_offset(
        self, page_token: str | None, version: str | None = None
    ) -> int:
        try:
            return _paging.parse_versioned_token(
                page_token,
                version=self._index_version() if version is None else version,
            )
        except ValueError as exc:
            if str(exc).startswith("stale listing continuation"):
                raise StaleContinuationError(str(exc)) from None
            raise

    def _versioned_page(
        self,
        items: tuple[object, ...],
        offset: int,
        max_results: int,
        category: str,
        version: str | None = None,
    ) -> tuple[tuple[object, ...], m.BoundInfo]:
        kept = items[offset : offset + max_results]
        remaining = len(items) - (offset + len(kept))
        truncated = remaining > 0
        token_version = self._index_version() if version is None else version
        return tuple(kept), m.BoundInfo(
            requested_max_results=max_results,
            requested_max_depth=0,
            returned_results=len(kept),
            truncated=truncated,
            truncated_category=category if truncated else None,
            continuation_token=(
                _paging.format_versioned_token(token_version, offset + len(kept))
                if truncated
                else None
            ),
        )

    def verify_files(
        self,
        repository_id: str,
        files: tuple[str, ...],
    ) -> m.StructuralFreshnessReport:
        """File-set freshness verdict (Addendum F §4.0 port).

        In-memory content is authoritatively present: known files verify,
        unknown files are stale. Coverage is VERIFIED exactly when
        nothing is stale or unverifiable — there is no index/file split
        to drift.
        """
        self._check_repository(repository_id)
        stale = sorted({p for p in dict.fromkeys(files) if p not in self._files})
        coverage = m.ScopeCoverage.VERIFIED if not stale else m.ScopeCoverage.UNVERIFIED
        detail = (
            "clean-verified"
            if coverage is m.ScopeCoverage.VERIFIED
            else "touched-file-mismatch"
        )
        return m.StructuralFreshnessReport(
            stale_files=tuple(stale),
            unverifiable_files=(),
            coverage=coverage,
            coverage_detail=detail,
        )

    def search_symbols(
        self,
        repository_id: str,
        query: str,
        match: m.StructuralLocateMatch,
        bounds: m.QueryBounds,
        page_token: str | None = None,
        scope: m.EvidenceScope | None = None,
    ) -> m.StructuralResult[m.StructuralSearchHit]:
        """Paginated name/locator search (Addendum F §4.0 port; J-10)."""
        self._check_repository(repository_id)
        if not query:
            raise ValueError("search query must be non-empty")
        version = self._scoped_version(scope)
        offset = self._versioned_offset(page_token, version=version)
        if match is m.StructuralLocateMatch.EXACT:
            ranked = [
                (s, m.CandidateRankBasis.EXACT_LOCATOR)
                for s in self._subjects
                if query == s.locator
            ]
            if not ranked:
                # Bare display names never equal a locator; fall
                # through to exact-name matching (same recall fix as
                # the graft provider). Still exact-only, no substring.
                for s in self._subjects:
                    if query == s.display_name:
                        ranked.append((s, m.CandidateRankBasis.EXACT_DECLARATION))
                    elif query == s.locator.rsplit(":", 1)[-1].rsplit("/", 1)[-1]:
                        ranked.append((s, m.CandidateRankBasis.EXACT_NAME))
        else:
            ranked = self._match_name(
                m.SubjectSelector(
                    exact_subject_id=None,
                    name_or_locator=query,
                    expected_kinds=(),
                    retrieval_scope_hint=None,
                )
            )
        order = {
            m.CandidateRankBasis.EXACT_LOCATOR: 0,
            m.CandidateRankBasis.EXACT_DECLARATION: 1,
            m.CandidateRankBasis.EXACT_NAME: 2,
            m.CandidateRankBasis.PARTIAL_NAME: 3,
            m.CandidateRankBasis.STRUCTURAL_PROXIMITY: 4,
        }
        ranked.sort(key=lambda x: (order[x[1]], x[0].locator))
        if scope is not None:
            # J-10: scope applied before ranking/pagination so an
            # out-of-scope global match can never consume a page.
            ranked = [
                (s, rank)
                for s, rank in ranked
                if m.evidence_scope_allows(s.locator, scope)
            ]
        candidates = tuple(
            m.StructuralSearchHit(
                candidate=m.SubjectCandidate(
                    subject=self._to_subject(s),
                    structural_evidence=(),
                    rank_basis=rank,
                ),
                span_text=None,
                signature_text=None,
            )
            for s, rank in ranked
        )
        kept, bound_info = self._versioned_page(
            candidates, offset, bounds.max_results, "search", version=version
        )
        return m.StructuralResult(
            items=kept,  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
            stale_omitted=0,
            coverage=m.ScopeCoverage.VERIFIED,
            coverage_detail="clean-verified",
        )

    def file_outline(
        self,
        repository_id: str,
        locator: str,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralResult[m.StructuralOutlineEntry]:
        """Symbols defined in one file (Addendum F §4.0 port)."""
        self._check_repository(repository_id)
        offset = self._versioned_offset(page_token)
        members = sorted(
            (s for s in self._subjects if _file_path(s.locator) == locator),
            key=lambda s: s.locator,
        )
        if not members:
            coverage = (
                m.ScopeCoverage.UNVERIFIED
                if locator in self._files
                else m.ScopeCoverage.VERIFIED
            )
            kept, bound_info = self._versioned_page((), offset, 1, "outline")
            return m.StructuralResult(
                items=(),
                repository_state=self.repository_state(repository_id),
                bound_info=bound_info,
                unsupported=False,
                stale_omitted=0,
                coverage=coverage,
                coverage_detail=(
                    "clean-verified"
                    if coverage is m.ScopeCoverage.VERIFIED
                    else "unverifiable-file"
                ),
            )
        entries = tuple(
            m.StructuralOutlineEntry(
                subject=self._to_subject(s),
                span_text=None,
                signature_text=None,
            )
            for s in members
        )
        kept, bound_info = self._versioned_page(
            entries, offset, bounds.max_results, "outline"
        )
        return m.StructuralResult(
            items=kept,  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
            stale_omitted=0,
            coverage=m.ScopeCoverage.VERIFIED,
            coverage_detail="clean-verified",
        )

    def locations(
        self,
        repository_id: str,
        subject: m.SubjectId,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralResult[m.StructuralLocation]:
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
        kept, bound_info = _paging.paginate(
            items, bounds.max_results, "locations", page_token
        )
        coverage, detail = self._page_coverage(
            tuple(item.location.locator for item in kept)
        )
        return m.StructuralResult(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=state,
            bound_info=bound_info,
            unsupported=False,
            coverage=coverage,
            coverage_detail=detail,
        )

    def edges(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralResult[m.StructuralEdge]:
        self._check_repository(repository_id)
        locator = subject.canonical_locator
        kinds = set(edge_kinds) if edge_kinds else set(m.StructuralEdgeKind)
        found: list[m.StructuralEdge] = []
        for edge in self._edges:
            if edge.kind not in kinds:
                continue
            if (
                direction
                in (
                    StructuralDirection.DOWNSTREAM,
                    StructuralDirection.BOTH,
                )
                and edge.source_locator == locator
            ):
                found.append(self._to_edge(edge))
            elif (
                direction
                in (
                    StructuralDirection.UPSTREAM,
                    StructuralDirection.BOTH,
                )
                and edge.target_locator == locator
            ):
                found.append(self._to_edge(edge))
        found.sort(
            key=lambda e: (
                e.kind.value,
                e.source.canonical_locator,
                e.target.canonical_locator,
            )
        )
        kept, bound_info = _paging.paginate(
            tuple(found), bounds.max_results, "edges", page_token
        )
        coverage, detail = self._page_coverage(
            tuple(edge.evidence.locator for edge in kept)
        )
        return m.StructuralResult(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
            coverage=coverage,
            coverage_detail=detail,
        )

    def reach(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        max_depth: int,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralResult[m.StructuralReachNode]:
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
        via: dict[str, m.StructuralEdge | None] = {subject.canonical_locator: None}
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
        kept, bound_info = _paging.paginate(
            tuple(nodes),
            bounds.max_results,
            "reach",
            page_token,
            requested_max_depth=limit,
        )
        coverage, detail = self._page_coverage(
            tuple(node.via.evidence.locator for node in kept if node.via is not None)
        )
        return m.StructuralResult(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
            coverage=coverage,
            coverage_detail=detail,
        )

    # -- private --------------------------------------------------------

    def _page_coverage(self, paths: tuple[str, ...]) -> tuple[m.ScopeCoverage, str]:
        """Coverage for a closed-world page over in-memory evidence.

        Memory content is authoritative: a cited file this source knows is
        current, and one it does not know could never have been indexed.
        """
        stale = sorted(
            {path for path in dict.fromkeys(paths) if path not in self._files}
        )
        if stale:
            return m.ScopeCoverage.UNVERIFIED, "touched-file-mismatch"
        return m.ScopeCoverage.VERIFIED, "clean-verified"

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
