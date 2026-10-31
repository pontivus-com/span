"""Typed support dependencies and their evaluation state.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.verification import VerificationRun
from span.core.model.primitives import (
    AuthorityBinding,
    ConclusionRevisionRef,
    DiscoveryObservationId,
    SourceObservationId,
    UnderstandingId,
    UnderstandingVersionNumber,
    _require_non_empty,
)


class SupportState(_enum.Enum):
    """Support currency, independent of retrieval/page availability."""

    CURRENT = "CURRENT"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    UNVERIFIABLE = "UNVERIFIABLE"


@_dataclass(frozen=True)
class SourceSupport:
    """A conclusion depends on one immutable full-content observation."""

    observation_id: SourceObservationId


@_dataclass(frozen=True)
class AuthoritySupportDependency:
    """A conclusion depends on a governing source and its applicability."""

    authority: AuthorityBinding


@_dataclass(frozen=True)
class PremiseSupport:
    """A conclusion depends on one exact semantic premise revision."""

    premise: ConclusionRevisionRef


@_dataclass(frozen=True)
class DiscoverySupport:
    """A conclusion depends on a directory/completeness boundary."""

    observation_id: DiscoveryObservationId


SupportDependency = _typing.Union[
    SourceSupport,
    AuthoritySupportDependency,
    PremiseSupport,
    DiscoverySupport,
]


@_dataclass(frozen=True)
class SupportEvaluation:
    """The result of checking declared support against present evidence.

    ``observed_at`` is supplied by the shell clock; the core never reads a
    clock. ``limitations`` keeps bounded or unverifiable checks explicit.
    """

    state: SupportState
    dependencies: tuple[SupportDependency, ...]
    reason: str = ""
    observed_at: _datetime.datetime | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at is not None:
            if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
                raise ValueError("SupportEvaluation.observed_at must be aware")


@_dataclass(frozen=True)
class ConclusionSupport:
    """Support qualification for one exact conclusion revision."""

    ref: ConclusionRevisionRef
    evaluation: SupportEvaluation


@_dataclass(frozen=True)
class SupportUnavailable:
    """A present-support evaluation could not be produced.

    This is a typed operational outcome, never a support verdict: missing or
    unreadable provider state is not ``UNVERIFIABLE`` support of the claim.
    """

    reason: str

    def __post_init__(self) -> None:
        _require_non_empty("SupportUnavailable.reason", self.reason)


@_dataclass(frozen=True)
class UnderstandingSupport:
    """Support qualification for one complete understanding version."""

    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    conclusions: tuple[ConclusionSupport, ...]
    state: SupportState
    observed_at: _datetime.datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("UnderstandingSupport.observed_at must be aware")


@_dataclass(frozen=True)
class ObservationSupport:
    """Support qualification for one observation cited by a run."""

    observation_id: SourceObservationId
    evaluation: SupportEvaluation


@_dataclass(frozen=True)
class VerificationSupport:
    """Support qualification for one independent verification run."""

    run: VerificationRun
    observations: tuple[ObservationSupport, ...]
    state: SupportState
    observed_at: _datetime.datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("VerificationSupport.observed_at must be aware")


@_dataclass(frozen=True)
class VerificationSupportRequest:
    """Select one verification run for support qualification."""

    repository_id: str
    run_id: str

    def __post_init__(self) -> None:
        _require_non_empty(
            "VerificationSupportRequest.repository_id", self.repository_id
        )
        _require_non_empty("VerificationSupportRequest.run_id", self.run_id)
