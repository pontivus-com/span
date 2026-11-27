"""Typed support dependencies and their evaluation state.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.verification import (
    VerificationRun,
    VerificationRunFacts,
    verification_facts,
)
from span.core.model.functional_pyramid import (
    FunctionalPyramidId,
    FunctionalRouteSupport,
)
from span.core.model.investigation import SourceRange
from span.core.model.primitives import (
    AuthorityApplicability,
    AuthorityBinding,
    AuthorityKind,
    AuthorityStatus,
    ConclusionRevisionRef,
    DeclaredPrecedence,
    EvidenceRef,
    EvidenceScope,
    DiscoveryObservationId,
    SourceObservationId,
    SupportState,
    UnderstandingId,
    UnderstandingVersionNumber,
    _require_non_empty,
)


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
    FunctionalRouteSupport,
]


@_dataclass(frozen=True)
class DependencyFinding:
    """One dependency's own evaluation, addressed by its identity (FD-16)."""

    dependency: SupportDependency
    state: SupportState
    reason: str = ""


@_dataclass(frozen=True)
class SupportEvaluation:
    """The result of checking declared support against present evidence.

    ``observed_at`` is supplied by the shell clock; the core never reads a
    clock. ``limitations`` keeps bounded or unverifiable checks explicit.
    """

    state: SupportState
    dependencies: tuple[SupportDependency, ...]
    reason: str = ""
    findings: tuple[DependencyFinding, ...] = ()
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


@_dataclass(frozen=True)
class SourceSupportBasis:
    evidence: EvidenceRef
    observation_id: SourceObservationId
    ranges: tuple[SourceRange, ...]
    captured_at: _datetime.datetime
    whole_file: bool

    def __post_init__(self) -> None:
        if self.captured_at.utcoffset() is None:
            raise ValueError("source basis requires an aware observation time")
        if not self.whole_file and not self.ranges:
            raise ValueError("source basis requires a recorded evidence boundary")


@_dataclass(frozen=True)
class DiscoverySupportBasis:
    repository_id: str
    scope: EvidenceScope
    captured_at: _datetime.datetime

    def __post_init__(self) -> None:
        _require_non_empty("discovery basis repository", self.repository_id)
        if self.captured_at.utcoffset() is None:
            raise ValueError("discovery basis requires an aware observation time")


@_dataclass(frozen=True)
class AuthoritySupportBasis:
    evidence: EvidenceRef
    authority_kind: AuthorityKind
    status: AuthorityStatus
    applicability: AuthorityApplicability
    declared_precedence: DeclaredPrecedence | None


@_dataclass(frozen=True)
class PremiseSupportBasis:
    ref: ConclusionRevisionRef


@_dataclass(frozen=True)
class GovernanceSupportBasis:
    repository_id: str
    pyramid_id: FunctionalPyramidId
    scope: EvidenceScope

    def __post_init__(self) -> None:
        _require_non_empty("governance basis repository", self.repository_id)


@_dataclass(frozen=True)
class UnavailableSupportBasis:
    reference: SourceObservationId | DiscoveryObservationId
    reason: str
    recovery: str

    def __post_init__(self) -> None:
        _require_non_empty("unavailable basis reason", self.reason)
        _require_non_empty("unavailable basis recovery", self.recovery)


SupportBasis = _typing.Union[
    SourceSupportBasis,
    DiscoverySupportBasis,
    AuthoritySupportBasis,
    PremiseSupportBasis,
    GovernanceSupportBasis,
    UnavailableSupportBasis,
]


@_dataclass(frozen=True)
class SupportFinding:
    basis: SupportBasis
    state: SupportState
    reason: str

    def __post_init__(self) -> None:
        if self.state is SupportState.CURRENT:
            raise ValueError("public support findings require non-current support")


@_dataclass(frozen=True)
class SupportQualification:
    """Compact public support evaluation for one already-identified subject."""

    state: SupportState
    observed_at: _datetime.datetime
    reason: str
    limitations: tuple[str, ...]
    findings: tuple[SupportFinding, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("SupportQualification.observed_at must be aware")


@_dataclass(frozen=True)
class ConclusionQualification:
    ref: ConclusionRevisionRef
    evaluation: SupportQualification


@_dataclass(frozen=True)
class ObservationQualification:
    observation_id: SourceObservationId
    evaluation: SupportQualification


@_dataclass(frozen=True)
class UnderstandingQualification:
    state: SupportState
    observed_at: _datetime.datetime
    limitations: tuple[str, ...]
    conclusions: tuple[ConclusionQualification, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("UnderstandingQualification.observed_at must be aware")


@_dataclass(frozen=True)
class VerificationQualification:
    state: SupportState
    observed_at: _datetime.datetime
    limitations: tuple[str, ...]
    observations: tuple[ObservationQualification, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("VerificationQualification.observed_at must be aware")


@_dataclass(frozen=True)
class VerificationView:
    """Exact recorded execution and independently deliverable collections."""

    facts: VerificationRunFacts
    observations: tuple[SourceObservationId, ...]
    environment_limitations: tuple[str, ...]
    qualification: VerificationQualification | SupportUnavailable | None


def verification_view(
    run: VerificationRun,
    qualification: VerificationQualification | SupportUnavailable | None,
) -> VerificationView:
    return VerificationView(
        facts=verification_facts(run),
        observations=run.observations,
        environment_limitations=run.environment_limitations,
        qualification=qualification,
    )


def basis_evidence(bases: tuple[SupportBasis, ...]) -> tuple[EvidenceRef, ...]:
    """The exact source and governing citations named by semantic bases."""
    return tuple(
        dict.fromkeys(
            basis.evidence
            for basis in bases
            if isinstance(basis, (SourceSupportBasis, AuthoritySupportBasis))
        )
    )


def compact_support(
    value: SupportEvaluation, bases: tuple[SupportBasis, ...]
) -> SupportQualification:
    """Combine one evaluated result with its exact recorded semantic facts."""
    if value.observed_at is None:
        raise ValueError("public support qualification requires evaluation time")
    non_current = tuple(
        finding
        for finding in value.findings
        if finding.state is not SupportState.CURRENT
    )
    return SupportQualification(
        state=value.state,
        observed_at=value.observed_at,
        reason=value.reason,
        limitations=value.limitations,
        findings=tuple(
            SupportFinding(basis=basis, state=finding.state, reason=finding.reason)
            for finding, basis in zip(non_current, bases, strict=True)
        ),
    )
