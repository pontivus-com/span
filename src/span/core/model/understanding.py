"""Understandings, immutable versions, conclusions, and explicit challenges.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.claims import AssertionNature
from span.core.model.investigation import (
    DiscoveryObservation,
    EvidenceAdmissionOutcome,
    InvestigationContext,
    SourceObservation,
)
from span.core.model.primitives import (
    BoundInfo,
    ChallengeId,
    ChallengeRevision,
    ConclusionId,
    DiscoveryObservationId,
    ConclusionRevisionNumber,
    ConclusionRevisionRef,
    EvidenceRef,
    EvidenceScope,
    SemanticBasis,
    UnderstandingId,
    UnderstandingVersionNumber,
    _require_non_empty,
)
from span.core.model.repository import EvidenceUnit
from span.core.model.recording import RecordReceipt
from span.core.model.support import (
    SupportDependency,
    SupportUnavailable,
    UnderstandingSupport,
)


def _require_aware(name: str, value: _datetime.datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@_dataclass(frozen=True)
class Gap:
    """One explicit unresolved question in a version snapshot."""

    question: str
    basis: str

    def __post_init__(self) -> None:
        _require_non_empty("Gap.question", self.question)
        _require_non_empty("Gap.basis", self.basis)


@_dataclass(frozen=True)
class SupportedConclusion:
    """A conclusion asserted with admitted support in one revision."""

    statement: str
    assertion_nature: AssertionNature
    scope: EvidenceScope
    support: tuple[SupportDependency, ...]

    def __post_init__(self) -> None:
        _require_non_empty("SupportedConclusion.statement", self.statement)
        if not self.support:
            raise ValueError("a supported conclusion requires at least one dependency")


@_dataclass(frozen=True)
class WithdrawnConclusion:
    """An explicit withdrawal; historical content is never deleted."""

    reason: str
    support: tuple[SupportDependency, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("WithdrawnConclusion.reason", self.reason)


ConclusionContent = _typing.Union[SupportedConclusion, WithdrawnConclusion]


@_dataclass(frozen=True)
class ConclusionRevision:
    """One immutable revision of a conclusion lineage."""

    understanding_id: UnderstandingId
    conclusion_id: ConclusionId
    revision: ConclusionRevisionNumber
    originating_version: UnderstandingVersionNumber
    content: ConclusionContent
    basis: SemanticBasis

    def __post_init__(self) -> None:
        if self.originating_version.value < 1:
            raise ValueError("originating_version must be positive")


@_dataclass(frozen=True)
class Understanding:
    """Stable understanding identity plus its compare-and-set version pointer."""

    understanding_id: UnderstandingId
    repository_id: str
    question: str
    scope: EvidenceScope
    current_version: UnderstandingVersionNumber
    created_at: _datetime.datetime
    provenance: str = ""

    def __post_init__(self) -> None:
        _require_non_empty("Understanding.repository_id", self.repository_id)
        _require_non_empty("Understanding.question", self.question)
        _require_aware("Understanding.created_at", self.created_at)


@_dataclass(frozen=True)
class UnderstandingVersion:
    """A complete immutable membership snapshot of conclusion revisions."""

    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    question: str
    scope: EvidenceScope
    conclusions: tuple[ConclusionRevisionRef, ...]
    created_at: _datetime.datetime
    gaps: tuple[Gap, ...] = ()
    provenance: str = ""
    previous_version: UnderstandingVersionNumber | None = None

    def __post_init__(self) -> None:
        _require_non_empty("UnderstandingVersion.question", self.question)
        _require_aware("UnderstandingVersion.created_at", self.created_at)
        if self.previous_version is not None:
            if self.previous_version.value >= self.version.value:
                raise ValueError("previous_version must precede version")
        lineages: set[ConclusionId] = set()
        for ref in self.conclusions:
            if ref.understanding_id != self.understanding_id:
                raise ValueError("conclusion membership crosses understandings")
            if ref.conclusion_id in lineages:
                raise ValueError(
                    f"duplicate conclusion lineage in version: {ref.conclusion_id}"
                )
            lineages.add(ref.conclusion_id)


@_dataclass(frozen=True)
class UnderstandingCandidate:
    """One discovered saved understanding, never an asserted answer."""

    understanding_id: UnderstandingId
    current_version: UnderstandingVersionNumber
    question: str
    scope: EvidenceScope
    matched_conclusions: tuple[ConclusionRevisionRef, ...]
    match_reasons: tuple[str, ...]
    lexical_overlap: int
    scope_associated: bool

    def __post_init__(self) -> None:
        _require_non_empty("UnderstandingCandidate.question", self.question)
        if self.lexical_overlap < 0:
            raise ValueError("lexical_overlap cannot be negative")


@_dataclass(frozen=True)
class UnderstandingDiscovery:
    """Bounded candidate discovery with explicit ambiguity and truncation."""

    candidates: tuple[UnderstandingCandidate, ...]
    bound_info: BoundInfo
    limit_reason: str | None = None


class ChallengeState(_enum.Enum):
    OPEN = "OPEN"
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"


@_dataclass(frozen=True)
class ChallengeResolution:
    """Evidence-backed settlement recorded with the resulting understanding."""

    reasoning: str
    resulting_understanding_id: UnderstandingId
    resulting_version: UnderstandingVersionNumber
    conclusions: tuple[ConclusionRevisionRef, ...] = ()
    withdrawn: tuple[ConclusionRevisionRef, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("ChallengeResolution.reasoning", self.reasoning)


@_dataclass(frozen=True)
class UnresolvedChallengeRecord:
    """One accepted unresolved disposition at its exact challenge revision."""

    challenge_revision: ChallengeRevision
    remaining_question: str
    basis: str
    recorded_at: _datetime.datetime

    def __post_init__(self) -> None:
        _require_non_empty(
            "UnresolvedChallengeRecord.remaining_question",
            self.remaining_question,
        )
        _require_non_empty("UnresolvedChallengeRecord.basis", self.basis)
        _require_aware("UnresolvedChallengeRecord.recorded_at", self.recorded_at)


@_dataclass(frozen=True)
class ResolvedChallengeRecord:
    """One accepted resolution at its exact challenge revision."""

    challenge_revision: ChallengeRevision
    resolution: "ChallengeResolution"
    recorded_at: _datetime.datetime

    def __post_init__(self) -> None:
        _require_aware("ResolvedChallengeRecord.recorded_at", self.recorded_at)


ChallengeDispositionRecord = _typing.Union[
    UnresolvedChallengeRecord,
    ResolvedChallengeRecord,
]


@_dataclass(frozen=True)
class Challenge:
    """An explicit dispute bound to exact understanding/conclusion revisions."""

    challenge_id: ChallengeId
    understanding_id: UnderstandingId
    target_version: UnderstandingVersionNumber
    target_conclusions: tuple[ConclusionRevisionRef, ...]
    reason: str
    evidence: tuple[EvidenceRef, ...]
    provenance: str
    challenge_revision: ChallengeRevision
    state: ChallengeState
    created_at: _datetime.datetime
    resolution: ChallengeResolution | None = None
    dispositions: tuple[ChallengeDispositionRecord, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("Challenge.reason", self.reason)
        _require_aware("Challenge.created_at", self.created_at)
        if self.state is ChallengeState.RESOLVED and self.resolution is None:
            raise ValueError("a resolved challenge requires a resolution")
        if self.state is not ChallengeState.RESOLVED and self.resolution is not None:
            raise ValueError("only a resolved challenge carries a resolution")
        for ref in self.target_conclusions:
            if ref.understanding_id != self.understanding_id:
                raise ValueError("challenge target crosses understandings")


@_dataclass(frozen=True)
class RetrievedUnderstanding:
    """One exact understanding snapshot with its bodies and live support."""

    understanding: Understanding
    version: UnderstandingVersion
    conclusions: tuple[ConclusionRevision, ...]
    support: UnderstandingSupport | SupportUnavailable
    challenges: tuple[Challenge, ...] = ()


@_dataclass(frozen=True)
class UnderstandingSnapshotSelector:
    """Select one exact understanding version; omitted version means current."""

    repository_id: str
    understanding_id: str
    version: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            "UnderstandingSnapshotSelector.repository_id", self.repository_id
        )
        _require_non_empty(
            "UnderstandingSnapshotSelector.understanding_id",
            self.understanding_id,
        )
        if self.version is not None and self.version < 1:
            raise ValueError("UnderstandingSnapshotSelector.version is positive")


@_dataclass(frozen=True)
class ContextRetrievalSelector:
    """Select one recoverable investigation context and its admitted content."""

    repository_id: str
    context_id: str

    def __post_init__(self) -> None:
        _require_non_empty("ContextRetrievalSelector.repository_id", self.repository_id)
        _require_non_empty("ContextRetrievalSelector.context_id", self.context_id)


@_dataclass(frozen=True)
class ReceiptRetrievalSelector:
    """Select one retained recording receipt by its caller-known identity."""

    repository_id: str
    context_id: str
    submission_id: str

    def __post_init__(self) -> None:
        _require_non_empty("ReceiptRetrievalSelector.repository_id", self.repository_id)
        _require_non_empty("ReceiptRetrievalSelector.context_id", self.context_id)
        _require_non_empty("ReceiptRetrievalSelector.submission_id", self.submission_id)


RetrieveRequest = _typing.Union[
    UnderstandingSnapshotSelector,
    ContextRetrievalSelector,
    ReceiptRetrievalSelector,
]


@_dataclass(frozen=True)
class RetrievedContext:
    """One context with its admitted source and discovery observations."""

    context: InvestigationContext
    observations: tuple[SourceObservation, ...]
    discovery: tuple[DiscoveryObservation, ...] = ()


@_dataclass(frozen=True)
class RetrievedReceipt:
    """One retained receipt; the context may already have been reaped."""

    receipt: RecordReceipt
    context: InvestigationContext | None = None


RetrieveResult = _typing.Union[
    RetrievedUnderstanding,
    RetrievedContext,
    RetrievedReceipt,
]


@_dataclass(frozen=True)
class ReassessRequest:
    """Qualify one understanding version against present support."""

    repository_id: str
    understanding_id: str
    version: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty("ReassessRequest.repository_id", self.repository_id)
        _require_non_empty("ReassessRequest.understanding_id", self.understanding_id)


@_dataclass(frozen=True)
class UnderstandingCandidateAnswer:
    """Candidate identities plus their exact stored snapshots.

    The snapshots are qualified candidates, not an assertion that any one is
    applicable to the caller's question.
    """

    context: InvestigationContext
    discovery: UnderstandingDiscovery
    retrieved: tuple[RetrievedUnderstanding, ...] = ()
    bound_info: BoundInfo | None = None


@_dataclass(frozen=True)
class InvestigationNeeded:
    """No saved candidate; the context and inspectable evidence to investigate."""

    context: InvestigationContext
    outcomes: tuple[EvidenceAdmissionOutcome, ...]
    evidence: tuple[EvidenceUnit, ...]
    reason: str
    discovery_observation_id: DiscoveryObservationId | None = None
    bound_info: BoundInfo | None = None

    def __post_init__(self) -> None:
        _require_non_empty("InvestigationNeeded.reason", self.reason)


@_dataclass(frozen=True)
class DiscoveryLimit:
    """No usable candidate or scope; no repository-wide absence is claimed."""

    discovery: UnderstandingDiscovery


UnderstandQuestionResult = _typing.Union[
    UnderstandingCandidateAnswer,
    InvestigationNeeded,
    DiscoveryLimit,
]
