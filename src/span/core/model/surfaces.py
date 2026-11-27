"""Surface identity, containment boundary, and reported status.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.schema import constraints as _constraints
from span.core.model.primitives import (
    ConclusionRevisionRef,
    SupportState,
    UnderstandingId,
    UnderstandingVersionNumber,
    _require_non_empty,
)


class ChangeReason(_enum.Enum):
    """Why a surface appears in a reconsideration result (FD-20)."""

    CONTAINMENT = "containment"
    DIRECT = "direct"
    INDIRECT = "indirect"


class SurfaceAction(_enum.Enum):
    """A surface declaration is either created or boundary-updated."""

    CREATE = "create"
    UPDATE = "update"


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
class AcceptedDependencyEffect:
    """Immutable accepted owner, revision and per-revision causes (FD-20)."""

    surface: SurfaceKey
    ref: ConclusionRevisionRef
    reasons: tuple[ChangeReason, ...]

    def __post_init__(self) -> None:
        if not self.reasons or len(set(self.reasons)) != len(self.reasons):
            raise ValueError("accepted dependency causes must be nonempty and distinct")
        if ChangeReason.CONTAINMENT in self.reasons:
            raise ValueError(
                "containment alone is a surface cause, not a revision cause"
            )


@_dataclass(frozen=True)
class AcceptedDependencyEffects:
    """The complete ordered accepted dependency selection, before live qualification."""

    effects: tuple[AcceptedDependencyEffect, ...]

    def __post_init__(self) -> None:
        refs = tuple(item.ref for item in self.effects)
        if len(set(refs)) != len(refs):
            raise ValueError("accepted dependency effects require distinct refs")


@_dataclass(frozen=True)
class SurfaceReference:
    """A public exact surface selection within the enclosing repository."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("locator", non_empty=True),),
            minimum=1,
            maximum=1,
            label="surface reference locator",
        ),
    )

    kind: SurfaceKind
    locator: str

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
class PendingConclusionRef:
    """One CURRENT-support captured conclusion awaiting curation."""

    ref: ConclusionRevisionRef
    understanding_version: UnderstandingVersionNumber


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
class SurfaceStatusSubject:
    surface: SurfaceKey


@_dataclass(frozen=True)
class QuestionStatusSubject:
    surface: SurfaceKey
    question: str

    def __post_init__(self) -> None:
        _require_non_empty("status question", self.question)


@_dataclass(frozen=True)
class UnderstandingStatusSubject:
    surface: SurfaceKey
    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber


StatusSubject = _typing.Union[
    SurfaceStatusSubject, QuestionStatusSubject, UnderstandingStatusSubject
]


@_dataclass(frozen=True)
class SurfaceStatusSummary:
    """One immediate child's distribution; exact refs are obtained at its owner."""

    surface: SurfaceKey
    current: int
    pending: int
    stale: int
    unassessed: int
    unexamined: int
    unexamined_limited: bool

    def __post_init__(self) -> None:
        _validate_counts(
            self.current, self.pending, self.stale, self.unassessed, self.unexamined
        )


def _validate_counts(*values: int) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        raise ValueError("status counts must be non-negative integers")


@_dataclass(frozen=True)
class SurfaceStatus:
    """The distribution over exactly the selected semantic population (FD-28)."""

    subject: StatusSubject
    current: int = 0
    pending: int = 0
    pending_refs: tuple[PendingConclusionRef, ...] = ()
    stale: int = 0
    stale_refs: tuple[StaleConclusionRef, ...] = ()
    unassessed: int = 0
    unexamined: int | None = None
    unexamined_limited: bool | None = None
    descendants: tuple[SurfaceStatusSummary, ...] = ()

    @property
    def surface(self) -> SurfaceKey:
        return self.subject.surface

    def __post_init__(self) -> None:
        _validate_counts(self.current, self.pending, self.stale, self.unassessed)
        if isinstance(self.subject, SurfaceStatusSubject):
            if self.unexamined is None or self.unexamined_limited is None:
                raise ValueError("ordinary surface status requires boundary coverage")
            _validate_counts(self.unexamined)
        elif (
            self.unexamined is not None
            or self.unexamined_limited is not None
            or self.descendants
        ):
            raise ValueError("exact membership status has no boundary coverage")
        if len(self.pending_refs) != self.pending:
            raise ValueError(
                "SurfaceStatus.pending_refs must name every and only pending conclusion"
            )
        if len(self.stale_refs) != self.stale:
            raise ValueError(
                "SurfaceStatus.stale_refs must name every and only stale conclusion"
            )
        refs = tuple(item.ref for item in self.pending_refs + self.stale_refs)
        if len(set(refs)) != len(refs):
            raise ValueError("status revision references must be unique")
        if isinstance(self.subject, UnderstandingStatusSubject):
            for item in self.pending_refs + self.stale_refs:
                if (
                    item.ref.understanding_id != self.subject.understanding_id
                    or item.understanding_version != self.subject.version
                ):
                    raise ValueError("status reference is outside selected version")


@_dataclass(frozen=True)
class SurfaceStatusUnavailable:
    """Transient operational inability to compose live owner status."""

    reason: str
    surface: SurfaceKey | None = None

    def __post_init__(self) -> None:
        _require_non_empty("SurfaceStatusUnavailable.reason", self.reason)
