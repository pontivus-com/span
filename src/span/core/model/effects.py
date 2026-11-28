"""Canonical public dependency effect projections."""

from __future__ import annotations

import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    ConclusionRevisionRef,
    SupportState,
    UnderstandingVersionNumber,
    _require_non_empty,
)
from span.core.model.support import SupportQualification, SupportUnavailable
from span.core.model.surfaces import ChangeReason, SurfaceKey


@_dataclass(frozen=True)
class ChangedConclusion:
    """One conclusion considered by reconsideration and its present state.

    ``reasons`` mean "considered", not "stale". A conclusion may be included
    because its surface was considered and still be ``CURRENT``.
    """

    ref: ConclusionRevisionRef
    expected_version: UnderstandingVersionNumber
    reasons: tuple[ChangeReason, ...]
    support: SupportQualification | SupportUnavailable

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("ChangedConclusion requires at least one reason")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("ChangedConclusion reasons must be distinct")


class EffectDispositionState(_enum.Enum):
    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"
    UNAVAILABLE = "UNAVAILABLE"


@_dataclass(frozen=True)
class EffectDisposition:
    """The exact pinned effect when no ordinary actionable result can be issued."""

    ref: ConclusionRevisionRef
    reasons: tuple[ChangeReason, ...]
    state: EffectDispositionState
    reason: str
    recovery: str | None = None
    support: SupportQualification | None = None

    def __post_init__(self) -> None:
        if not self.reasons or len(set(self.reasons)) != len(self.reasons):
            raise ValueError("effect disposition requires distinct nonempty causes")
        if ChangeReason.CONTAINMENT in self.reasons:
            raise ValueError("containment alone is not a revision cause")
        _require_non_empty("effect disposition reason", self.reason)
        if self.state is EffectDispositionState.UNAVAILABLE:
            if not self.recovery:
                raise ValueError("unavailable effect requires recovery")
        if self.state is EffectDispositionState.CURRENT:
            if self.support is None or self.support.state is not SupportState.CURRENT:
                raise ValueError(
                    "current disposition requires verified current support"
                )
        elif self.support is not None:
            raise ValueError("non-current dispositions cannot carry a support verdict")


@_dataclass(frozen=True)
class ChangedSurface:
    """One surface that must be re-examined, with every reason (FD-20)."""

    surface: SurfaceKey
    reasons: tuple[ChangeReason, ...]
    conclusions: tuple[ChangedConclusion | EffectDisposition, ...] = ()

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("ChangedSurface requires at least one reason")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("ChangedSurface reasons must be distinct")
