"""StructuralSource port (plan §5.2) — the canonical structural boundary.

Structural observations only. A provider must not fake an unsupported
capability with an empty result: ``unsupported=True`` (with empty items)
is the typed ``UNSUPPORTED_CAPABILITY`` outcome (§4.11).
"""

import enum as _enum
import typing as _typing

from span.core.model import (
    BoundInfo,  # noqa: F401  (re-exported for port consumers)
    EvidenceScope,
    Freshness,
    QueryBounds,
    RepositoryState,
    ScopeCoverage,  # noqa: F401
    StructuralEdge,
    StructuralEdgeKind,
    StructuralFreshnessReport,  # noqa: F401
    StructuralLocateMatch,  # noqa: F401
    StructuralLocation,
    StructuralOutlineEntry,
    StructuralReachNode,
    StructuralResult,
    StructuralSearchHit,
    SubjectId,
    SubjectResolution,
    SubjectSelector,
)


class StaleContinuationError(ValueError):
    """A version-bound listing continuation no longer matches the listing
    version ([design note F](docs/design-references.md#f) §4.3). The caller restarts the listing from page
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
    ) -> StructuralResult[StructuralLocation]:
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
    ) -> StructuralResult[StructuralEdge]:
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
    ) -> StructuralResult[StructuralReachNode]:
        """Bounded structural reach expansion (no semantic judgment)."""
        ...

    def search_symbols(
        self,
        repository_id: str,
        query: str,
        match: StructuralLocateMatch,
        bounds: QueryBounds,
        page_token: str | None = None,
        scope: EvidenceScope | None = None,
    ) -> StructuralResult[StructuralSearchHit]:
        """Paginated name/locator search ([design note F](docs/design-references.md#f) §4.0; J-10).

        Provider match order, real continuation tokens (never the
        tokenless truncation of resolve_subject). Tokens are
        version-bound per §4.3: a changed listing version raises
        StaleContinuationError. When ``scope`` is supplied the candidate
        population is filtered to it **before** ranking and pagination,
        entry currentness and whole-result coverage are computed against
        that exact scope, and the continuation token binds the scope so a
        token issued for one scope never resumes another.
        """
        ...

    def file_outline(
        self,
        repository_id: str,
        locator: str,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> StructuralResult[StructuralOutlineEntry]:
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
        """File-set freshness verdict ([design note F](docs/design-references.md#f) §4.0).

        Whole-file live fingerprints against recorded file hashes;
        symbol hashes are never compared against file bytes. Coverage
        follows the §4.0 two-tier rule for the given file set.
        """
        ...

    def describe_current(
        self,
        repository_id: str,
    ) -> Freshness:
        """Provider index currency verdict ([design note G](docs/design-references.md#g) §4.8d).

        Whether this provider's structural view is current for the
        repository, with a provider-local reason string. Read-only:
        never builds, fetches, or mutates. Core treats the reason as
        opaque diagnostics.
        """
        ...

    def ensure_current(
        self,
        repository_id: str,
    ) -> Freshness:
        """Refresh the provider's structural view, then report currency.

        Provider-owned execution against provider-owned artifacts only
        (a graft provider rebuilds its index into Span's data directory;
        a memory provider no-ops). Bounded: one attempt, then report.
        Failures return UNVERIFIABLE with a reason; never raise for
        build failure. Allowed only from explicit repository
        provisioning (`initialize_repository`) and explicit semantic
        `refresh`. Forbidden from `status`, `explain`, `locate`,
        `neighbors`, hooks, background workers, and ordinary reads.
        """
        ...
