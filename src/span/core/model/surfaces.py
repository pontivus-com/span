"""Surface identity, containment boundary, and reported status.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.model.primitives import _require_non_empty


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

    repository_id: str
    kind: SurfaceKind
    locator: str

    def __post_init__(self) -> None:
        _require_non_empty("SurfaceKey.repository_id", self.repository_id)
        _require_repository_relative("SurfaceKey.locator", self.locator)


@_dataclass(frozen=True)
class SurfaceReference:
    """A public exact surface selection: kind and locator.

    ``repository_id`` is optional because ``ask`` already carries the routed
    repository. An ``AmbiguousSurface`` candidate can be copied back verbatim.
    """

    kind: SurfaceKind
    locator: str
    repository_id: str | None = None

    def __post_init__(self) -> None:
        _require_repository_relative("SurfaceReference.locator", self.locator)
        if self.repository_id is not None:
            _require_non_empty("SurfaceReference.repository_id", self.repository_id)


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
class SurfaceStatus:
    """The reported distribution over one surface (L2 surface status)."""

    surface: SurfaceKey
    current: int = 0
    stale: int = 0
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
