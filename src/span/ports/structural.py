"""StructuralSource port (plan §5.2) — the canonical structural boundary.

Structural observations only. A provider must not fake an unsupported
capability with an empty result: ``unsupported=True`` (with empty items)
is the typed ``UNSUPPORTED_CAPABILITY`` outcome (§4.11).
"""

import enum as _enum
import typing as _typing

from span.core.model import (
    BoundInfo,  # noqa: F401  (re-exported for port consumers)
    QueryBounds,
    RepositoryState,
    ScopeCoverage,  # noqa: F401
    StructuralEdgeKind,
    StructuralEdgePage,
    StructuralFreshnessReport,  # noqa: F401
    StructuralLocateMatch,  # noqa: F401
    StructuralLocationPage,
    StructuralOutlinePage,  # noqa: F401
    StructuralReachPage,
    StructuralSearchPage,  # noqa: F401
    Subject,
    SubjectId,
    SubjectResolution,
    SubjectSelector,
)


class StaleContinuationError(ValueError):
    """A version-bound listing continuation no longer matches the listing
    version (Addendum F §4.3). The caller restarts the listing from page
    one; the error names the observed new version."""


class StructuralDirection(_enum.Enum):
    """Edge/relationship traversal direction vocabulary (plan §5.2)."""

    UPSTREAM = "UPSTREAM"
    DOWNSTREAM = "DOWNSTREAM"
    BOTH = "BOTH"


@_typing.runtime_checkable
class StructuralSource(_typing.Protocol):
    """Generic structural-source boundary (plan MI-04)."""

    def repository_state(self, repository_id: str) -> RepositoryState:
        """Current repository state/fingerprint baseline."""
        ...

    def resolve_subject(
        self,
        repository_id: str,
        selector: SubjectSelector,
        bounds: QueryBounds,
    ) -> SubjectResolution:
        """Resolve a selector to candidate subjects (never by name alone)."""
        ...

    def locations(
        self,
        repository_id: str,
        subject: SubjectId,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> StructuralLocationPage:
        """Implementation locations for one subject."""
        ...

    def edges(
        self,
        repository_id: str,
        subject: SubjectId,
        edge_kinds: tuple[StructuralEdgeKind, ...],
        direction: StructuralDirection,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> StructuralEdgePage:
        """Structural edges for one subject in the given direction."""
        ...

    def reach(
        self,
        repository_id: str,
        subject: SubjectId,
        edge_kinds: tuple[StructuralEdgeKind, ...],
        direction: StructuralDirection,
        max_depth: int,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> StructuralReachPage:
        """Bounded structural reach expansion (no semantic judgment)."""
        ...

    def search_symbols(
        self,
        repository_id: str,
        query: str,
        match: StructuralLocateMatch,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> StructuralSearchPage:
        """Paginated name/locator search (Addendum F §4.0).

        Provider match order, real continuation tokens (never the
        tokenless truncation of resolve_subject). Tokens are
        version-bound per §4.3: a changed listing version raises
        StaleContinuationError.
        """
        ...

    def file_outline(
        self,
        repository_id: str,
        locator: str,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> StructuralOutlinePage:
        """Symbols defined in one file, deterministic order (F §4.0).

        Unknown file yields empty entries, never error. Tokens are
        version-bound per §4.3.
        """
        ...

    def verify_files(
        self,
        repository_id: str,
        files: tuple[str, ...],
    ) -> StructuralFreshnessReport:
        """File-set freshness verdict (Addendum F §4.0).

        Whole-file live fingerprints against recorded file hashes;
        symbol hashes are never compared against file bytes. Coverage
        follows the §4.0 two-tier rule for the given file set.
        """
        ...
