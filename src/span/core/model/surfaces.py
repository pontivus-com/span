"""Surface identity, containment boundary, and reported status.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.schema import constraints as _constraints
from span.core.model.primitives import (
    ConclusionRevisionRef,
    UnderstandingVersionNumber,
    _require_non_empty,
)
from span.core.model.support import SupportState


class SurfaceKind(_enum.Enum):
    """The granularity a surface is declared or derived at (FD-1)."""

    FILE = "FILE"
    SYMBOL = "SYMBOL"
    SERVICE = "SERVICE"
    DOMAIN = "DOMAIN"

    @property
    def is_declared(self) -> bool:
        return self in (SurfaceKind.SERVICE, SurfaceKind.DOMAIN)


def _require_repository_relative(name: str, value: str) -> str:
    _require_non_empty(name, value)
    if value.startswith("/"):
        raise ValueError(f"{name} must be repository-relative")
    return value


@_dataclass(frozen=True)
class SurfaceKey:
    """The derived identity of one surface (FD-1)."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="surface repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("locator", non_empty=True),),
            minimum=1,
            maximum=1,
            label="surface locator",
        ),
    )

    repository_id: str
    kind: SurfaceKind
    locator: str

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)
        _require_repository_relative("SurfaceKey.locator", self.locator)


@_dataclass(frozen=True)
class SurfaceReference:
    """A public exact surface selection: kind and locator.

    ``repository_id`` is optional because ``ask`` already carries the routed
    repository. An ``AmbiguousSurface`` candidate can be copied back verbatim.
    """

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("locator", non_empty=True),),
            minimum=1,
            maximum=1,
            label="surface reference locator",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("repository_id"), True
                ),
            ),
            label="surface reference repository",
        ),
    )

    kind: SurfaceKind
    locator: str
    repository_id: str | None = None

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)
        _require_repository_relative("SurfaceReference.locator", self.locator)


@_dataclass(frozen=True)
class SurfaceBoundary:
    """Declared containment: path prefixes plus exact symbols (FD-5, FD-7)."""

    paths: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for path in self.paths:
            _require_repository_relative("SurfaceBoundary.paths", path)
        for symbol in self.symbols:
            _require_non_empty("SurfaceBoundary.symbols", symbol)
        if len(set(self.paths)) != len(self.paths):
            raise ValueError("SurfaceBoundary.paths contains duplicates")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("SurfaceBoundary.symbols contains duplicates")


@_dataclass(frozen=True)
class Surface:
    """One surface with its current boundary version (FD-1, FD-6, FD-7)."""

    key: SurfaceKey
    boundary: SurfaceBoundary = _field(default_factory=SurfaceBoundary)
    parent: SurfaceKey | None = None
    boundary_version: int = 1

    def __post_init__(self) -> None:
        if self.boundary_version < 1:
            raise ValueError("Surface.boundary_version must be positive")
        if self.parent is not None:
            if self.parent.repository_id != self.key.repository_id:
                raise ValueError("a parent surface must share the repository")
            if self.parent == self.key:
                raise ValueError("a surface cannot be its own parent")


@_dataclass(frozen=True)
class StaleConclusionRef:
    """One non-current conclusion addressed by the surface status (L2, L9).

    A count alone is not actionable. The reference names the exact conclusion
    revision, the understanding version that holds it, and the present support
    state. The statement stays out of the status; ``ask`` with the version
    returns it when the agent needs the content.
    """

    ref: ConclusionRevisionRef
    understanding_version: UnderstandingVersionNumber
    state: SupportState

    def __post_init__(self) -> None:
        if self.state is SupportState.CURRENT:
            raise ValueError(
                "StaleConclusionRef.state must be non-current; a current "
                "conclusion is counted, not referenced as stale"
            )


@_dataclass(frozen=True)
class SurfaceStatus:
    """The reported distribution over one surface (L2 surface status)."""

    surface: SurfaceKey
    current: int = 0
    stale: int = 0
    stale_refs: tuple[StaleConclusionRef, ...] = ()
    unassessed: int = 0
    unexamined: int = 0
    unexamined_limited: bool = False
    descendants: tuple[SurfaceStatus, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("current", self.current),
            ("stale", self.stale),
            ("unassessed", self.unassessed),
            ("unexamined", self.unexamined),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"SurfaceStatus.{name} must be a non-negative int")
        if len(self.stale_refs) != self.stale:
            raise ValueError(
                "SurfaceStatus.stale_refs must name every and only stale conclusion"
            )


@_dataclass(frozen=True)
class SurfaceStatusUnavailable:
    """Transient operational inability to compose live owner status."""

    reason: str
    surface: SurfaceKey | None = None

    def __post_init__(self) -> None:
        _require_non_empty("SurfaceStatusUnavailable.reason", self.reason)
