"""Recoverable investigation contexts and exact evidence admission.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    DiscoveryObservationId,
    EvidenceRef,
    EvidenceScope,
    InvestigationContextId,
    QueryBounds,
    RequestId,
    SourceObservationId,
    _require_non_empty,
    _require_positive_int,
)
from span.core.model.recording import ContentDigest


class ContextOrigin(_enum.Enum):
    QUESTION = "QUESTION"
    CHANGED_SUPPORT = "CHANGED_SUPPORT"
    CHALLENGE = "CHALLENGE"
    EVIDENCE_ONLY = "EVIDENCE_ONLY"


class ContextState(_enum.Enum):
    LIVE = "LIVE"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"


@_dataclass(frozen=True)
class DiscoveryObservation:
    """One immutable directory/completeness observation.

    Binds the exact scope examined to the membership fingerprint observed at
    that moment, so an absence or completeness claim cites what was actually
    inspected rather than a later repository state.
    """

    observation_id: DiscoveryObservationId
    repository_id: str
    scope: EvidenceScope
    membership_fingerprint: str
    captured_at: _datetime.datetime

    def __post_init__(self) -> None:
        _require_non_empty("DiscoveryObservation.repository_id", self.repository_id)
        _require_non_empty(
            "DiscoveryObservation.membership_fingerprint",
            self.membership_fingerprint,
        )
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("DiscoveryObservation.captured_at must be aware")


@_dataclass(frozen=True)
class SourceObservation:
    """One immutable observed source plus its delivered excerpt boundary.

    ``evidence`` is the reference other carriers cite; ``content_digest`` is
    the observed full-content fingerprint. ``delivered_ranges`` records the
    exact lines delivered; an empty tuple with ``whole_file`` means the full
    text was delivered. The observation ID is the membership key a context
    admits; the evidence ID is the citation key.
    """

    observation_id: SourceObservationId
    repository_id: str
    evidence: EvidenceRef
    content_digest: ContentDigest
    captured_at: _datetime.datetime
    total_lines: int
    delivered_ranges: tuple[SourceRange, ...] = ()
    whole_file: bool = False
    excerpt: str = ""

    def __post_init__(self) -> None:
        if self.evidence.repository_id != self.repository_id:
            raise ValueError(
                "source observation evidence belongs to another repository"
            )
        if not self.whole_file and not self.delivered_ranges:
            raise ValueError(
                "a source observation reports ranges or an explicit "
                "whole-file delivery"
            )
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("SourceObservation.captured_at must be aware")
        if self.total_lines < 0:
            raise ValueError("SourceObservation.total_lines cannot be negative")


@_dataclass(frozen=True)
class LifecycleRetention:
    """Finite operational lifetime policy for contexts and replay state.

    Deployment supplies the concrete durations; this carrier only validates
    that they are finite, positive, and that replay retention covers the
    context write-acceptance lifetime. Semantic history has a separate,
    reference-safe policy and is not bounded by these values.
    """

    context_lifetime: _datetime.timedelta
    replay_retention: _datetime.timedelta

    def __post_init__(self) -> None:
        for name, value in (
            ("context_lifetime", self.context_lifetime),
            ("replay_retention", self.replay_retention),
        ):
            if value <= _datetime.timedelta(0):
                raise ValueError(f"LifecycleRetention.{name} must be positive")
        if self.replay_retention < self.context_lifetime:
            raise ValueError(
                "replay retention cannot be shorter than the context lifetime"
            )


@_dataclass(frozen=True)
class SourceRange:
    """One inclusive line range used for citation and delivery."""

    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        _require_positive_int("SourceRange.start_line", self.start_line)
        _require_positive_int("SourceRange.end_line", self.end_line)
        if self.end_line < self.start_line:
            raise ValueError("SourceRange.end_line precedes start_line")


@_dataclass(frozen=True)
class EvidenceRequest:
    """One exact source/range request in an admission batch."""

    locator: str
    ranges: tuple[SourceRange, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("EvidenceRequest.locator", self.locator)


@_dataclass(frozen=True)
class AdmittedEvidence:
    request: EvidenceRequest
    observation_id: SourceObservationId
    delivered_ranges: tuple[SourceRange, ...]
    admitted_at: _datetime.datetime
    whole_file: bool = False

    def __post_init__(self) -> None:
        if self.admitted_at.tzinfo is None or self.admitted_at.utcoffset() is None:
            raise ValueError("AdmittedEvidence.admitted_at must be aware")
        if not self.whole_file and not self.delivered_ranges:
            raise ValueError(
                "an admission reports ranges or an explicit whole-file delivery"
            )


@_dataclass(frozen=True)
class AlreadyAdmittedEvidence:
    request: EvidenceRequest
    observation_id: SourceObservationId


class EvidenceSourceFailureKind(_enum.Enum):
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    UNREADABLE = "UNREADABLE"


@_dataclass(frozen=True)
class EvidenceSourceFailure:
    request: EvidenceRequest
    kind: EvidenceSourceFailureKind
    reason: str

    def __post_init__(self) -> None:
        _require_non_empty("EvidenceSourceFailure.reason", self.reason)


@_dataclass(frozen=True)
class OmittedEvidence:
    request: EvidenceRequest
    reason: str

    def __post_init__(self) -> None:
        _require_non_empty("OmittedEvidence.reason", self.reason)


EvidenceAdmissionOutcome = _typing.Union[
    AdmittedEvidence,
    AlreadyAdmittedEvidence,
    EvidenceSourceFailure,
    OmittedEvidence,
]


@_dataclass(frozen=True)
class EvidenceStartRequest:
    """Start one evidence-only context from a bounded exact-source batch."""

    repository_id: str
    request_id: RequestId
    scope: EvidenceScope
    requests: tuple[EvidenceRequest, ...]
    bounds: QueryBounds

    def __post_init__(self) -> None:
        _require_non_empty("EvidenceStartRequest.repository_id", self.repository_id)
        if not self.requests:
            raise ValueError("an evidence start request requires sources")


@_dataclass(frozen=True)
class UnderstandQuestionRequest:
    """One ordinary scoped question against saved understanding and evidence."""

    repository_id: str
    request_id: RequestId
    question: str
    scope: EvidenceScope
    bounds: QueryBounds
    page_token: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            "UnderstandQuestionRequest.repository_id", self.repository_id
        )
        _require_non_empty("UnderstandQuestionRequest.question", self.question)


@_dataclass(frozen=True)
class EvidenceExtendRequest:
    """Admit further exact sources into one existing live context."""

    repository_id: str
    context_id: InvestigationContextId
    requests: tuple[EvidenceRequest, ...]
    bounds: QueryBounds

    def __post_init__(self) -> None:
        _require_non_empty("EvidenceExtendRequest.repository_id", self.repository_id)
        if not self.requests:
            raise ValueError("an evidence extend request requires sources")


@_dataclass(frozen=True)
class EvidenceAdmissionResult:
    """The context plus one closed outcome for every submitted item."""

    context: "InvestigationContext"
    outcomes: tuple[EvidenceAdmissionOutcome, ...]

    def __post_init__(self) -> None:
        for outcome in self.outcomes:
            if not isinstance(
                outcome,
                (
                    AdmittedEvidence,
                    AlreadyAdmittedEvidence,
                    EvidenceSourceFailure,
                    OmittedEvidence,
                ),
            ):
                raise TypeError(
                    "unhandled evidence admission outcome: " f"{type(outcome).__name__}"
                )


@_dataclass(frozen=True)
class InvestigationContext:
    """One recoverable investigation, not a mandatory semantic question."""

    context_id: InvestigationContextId
    repository_id: str
    request_id: RequestId
    request_digest: ContentDigest
    origin: ContextOrigin
    state: ContextState
    scope: EvidenceScope
    created_at: _datetime.datetime
    question: str | None = None
    purpose: str | None = None
    admitted_evidence: tuple[AdmittedEvidence, ...] = ()
    recovery_ref: str | None = None
    expires_at: _datetime.datetime | None = None

    def __post_init__(self) -> None:
        _require_non_empty("InvestigationContext.repository_id", self.repository_id)
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("InvestigationContext.created_at must be aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
                raise ValueError("InvestigationContext.expires_at must be aware")
            if self.expires_at < self.created_at:
                raise ValueError("expires_at cannot precede created_at")
        if self.origin is ContextOrigin.QUESTION and not self.question:
            raise ValueError("a QUESTION context requires a bound question")
