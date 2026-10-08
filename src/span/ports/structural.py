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
    StructuralEdgeKind,
    StructuralEdgePage,
    StructuralLocationPage,
    StructuralReachPage,
    SubjectId,
    SubjectResolution,
    SubjectSelector,
)


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
