"""Understandings, immutable versions, conclusions, and explicit challenges.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.schema import constraints as _constraints
from span.core.model.claims import AssertionNature
from span.core.model.investigation import (
    DiscoveryObservation,
    InvestigationContext,
    SourceObservation,
)
from span.core.model.primitives import (
    ChallengeId,
    ChallengeRevision,
    ClaimRef,
    ConclusionId,
    ConclusionRevisionNumber,
    ConclusionRevisionRef,
    DerivationKind,
    EvidenceRef,
    EvidenceScope,
    RelationshipRef,
    SemanticBasis,
    UnderstandingId,
    UnderstandingVersionNumber,
    VerificationRunId,
    _require_non_empty,
)
from span.core.model.surfaces import SurfaceKey, SurfaceReference
from span.core.model.support import (
    SupportBasis,
    SupportDependency,
    SupportQualification,
    SupportUnavailable,
    basis_evidence,
)
from span.core.model.verification import VerificationRun


def _require_aware(name: str, value: _datetime.datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@_dataclass(frozen=True)
class RecordedQuestionGap:
    """One explicit unresolved question in a version snapshot."""

    question: str
    basis: str

    def __post_init__(self) -> None:
        _require_non_empty("RecordedQuestionGap.question", self.question)
        _require_non_empty("RecordedQuestionGap.basis", self.basis)


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


class CurationState(_enum.Enum):
    """Derived reuse maturity for one exact semantic revision."""

    CAPTURED = "CAPTURED"
    CURATED = "CURATED"


class CurationOrigin(_enum.Enum):
    """How an immutable curation disposition was established."""

    EXPLICIT = "EXPLICIT"
    INHERITED_CONFIRMATION = "INHERITED_CONFIRMATION"


@_dataclass(frozen=True)
class CurationDisposition:
    """Immutable shared-reuse qualification for one exact revision."""

    ref: ConclusionRevisionRef
    accepted_in_version: UnderstandingVersionNumber
    reasoning: str
    provenance: str
    recorded_at: _datetime.datetime
    origin: CurationOrigin
    inherited_from: ConclusionRevisionRef | None = None

    def __post_init__(self) -> None:
        _require_non_empty("CurationDisposition.reasoning", self.reasoning)
        _require_non_empty("CurationDisposition.provenance", self.provenance)
        _require_aware("CurationDisposition.recorded_at", self.recorded_at)
        if self.origin is CurationOrigin.EXPLICIT:
            if self.inherited_from is not None:
                raise ValueError(
                    "explicit curation cannot carry an inherited predecessor"
                )
            return
        if self.inherited_from is None:
            raise ValueError("inherited confirmation curation requires inherited_from")
        if (
            self.inherited_from.understanding_id != self.ref.understanding_id
            or self.inherited_from.conclusion_id != self.ref.conclusion_id
        ):
            raise ValueError(
                "inherited curation predecessor must share the conclusion lineage"
            )
        if self.inherited_from.revision.value + 1 != self.ref.revision.value:
            raise ValueError(
                "inherited curation predecessor must be the immediate revision"
            )


@_dataclass(frozen=True)
class Understanding:
    """Stable understanding identity plus its compare-and-set version pointer."""

    understanding_id: UnderstandingId
    repository_id: str
    surface: SurfaceKey
    question: str
    scope: EvidenceScope
    current_version: UnderstandingVersionNumber
    created_at: _datetime.datetime
    provenance: str = ""

    def __post_init__(self) -> None:
        _require_non_empty("Understanding.repository_id", self.repository_id)
        _require_non_empty("Understanding.question", self.question)
        _require_aware("Understanding.created_at", self.created_at)
        if self.surface.repository_id != self.repository_id:
            raise ValueError("Understanding.surface must share the repository")


@_dataclass(frozen=True)
class UnderstandingVersion:
    """A complete immutable membership snapshot of conclusion revisions."""

    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    question: str
    scope: EvidenceScope
    conclusions: tuple[ConclusionRevisionRef, ...]
    created_at: _datetime.datetime
    gaps: tuple[RecordedQuestionGap, ...] = ()
    provenance: str = ""
    previous_version: UnderstandingVersionNumber | None = None
    surface_boundary_version: int = 1

    def __post_init__(self) -> None:
        _require_non_empty("UnderstandingVersion.question", self.question)
        _require_aware("UnderstandingVersion.created_at", self.created_at)
        if self.surface_boundary_version < 1:
            raise ValueError("surface_boundary_version must be positive")
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
class SupportedAuditContent:
    statement: str
    assertion_nature: AssertionNature
    scope: EvidenceScope
    evidence: tuple[EvidenceRef, ...]
    maturity: CurationState
    qualification: SupportQualification | SupportUnavailable


@_dataclass(frozen=True)
class WithdrawnAuditContent:
    reason: str


@_dataclass(frozen=True)
class AuditConclusion:
    """Exact recorded content and derivation, with separately live qualification."""

    ref: ConclusionRevisionRef
    originating_version: UnderstandingVersionNumber
    content: SupportedAuditContent | WithdrawnAuditContent
    basis: tuple[SupportBasis, ...]
    derivation: DerivationKind
    summary: str
    input_refs: tuple[ClaimRef | RelationshipRef | EvidenceRef, ...]


def audit_conclusion(
    revision: ConclusionRevision,
    basis: tuple[SupportBasis, ...],
    *,
    maturity: CurationState,
    qualification: SupportQualification | SupportUnavailable | None,
) -> AuditConclusion:
    """Project immutable recorded facts without reevaluating their meaning."""
    if len(basis) != len(revision.content.support):
        raise ValueError("audit must preserve each recorded support basis")
    content: SupportedAuditContent | WithdrawnAuditContent
    if isinstance(revision.content, SupportedConclusion):
        if qualification is None:
            raise ValueError("supported audit content requires live qualification")
        content = SupportedAuditContent(
            statement=revision.content.statement,
            assertion_nature=revision.content.assertion_nature,
            scope=revision.content.scope,
            evidence=basis_evidence(basis),
            maturity=maturity,
            qualification=qualification,
        )
    else:
        if qualification is not None:
            raise ValueError("withdrawn audit content has no live qualification")
        content = WithdrawnAuditContent(reason=revision.content.reason)
    return AuditConclusion(
        ref=ConclusionRevisionRef(
            understanding_id=revision.understanding_id,
            conclusion_id=revision.conclusion_id,
            revision=revision.revision,
        ),
        originating_version=revision.originating_version,
        content=content,
        basis=basis,
        derivation=revision.basis.derivation,
        summary=revision.basis.summary,
        input_refs=revision.basis.input_refs,
    )


@_dataclass(frozen=True)
class RetrievedUnderstanding:
    """One exact version's recorded facts, never the mutable current pointer."""

    repository_id: str
    surface: SurfaceKey
    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    question: str
    scope: EvidenceScope
    created_at: _datetime.datetime
    provenance: str
    previous_version: UnderstandingVersionNumber | None
    surface_boundary_version: int
    gaps: tuple[RecordedQuestionGap, ...]
    conclusions: tuple[AuditConclusion, ...]
    challenges: tuple[Challenge, ...] = ()
    curations: tuple[CurationDisposition, ...] = ()


@_dataclass(frozen=True)
class RecordedQuestionSelector:
    """Select current membership by exact recorded question on one exact surface."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="recorded-question repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("question", non_empty=True),),
            minimum=1,
            maximum=1,
            label="recorded-question text",
        ),
    )

    repository_id: str
    surface: SurfaceReference
    question: str

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)


@_dataclass(frozen=True)
class CurrentUnderstandingSelector:
    """Select one understanding's current membership."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="current-understanding repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("understanding_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="current-understanding identity",
        ),
    )

    repository_id: str
    understanding_id: str

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)


@_dataclass(frozen=True)
class PendingCurationSelector:
    """Select the repository-local deterministic pending-curation queue."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="pending-curation repository",
        ),
    )

    repository_id: str
    after: ConclusionRevisionRef | None = None

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)


@_dataclass(frozen=True)
class PendingCurationItem:
    """One exact current-membership capture awaiting semantic review."""

    ref: ConclusionRevisionRef
    understanding_version: UnderstandingVersionNumber
    surface: SurfaceKey
    question: str

    def __post_init__(self) -> None:
        _require_non_empty("PendingCurationItem.question", self.question)


@_dataclass(frozen=True)
class PendingCuration:
    """One bounded deterministic page of pending-curation references."""

    repository_id: str
    items: tuple[PendingCurationItem, ...]
    next_after: ConclusionRevisionRef | None = None
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("PendingCuration.repository_id", self.repository_id)
        for item in self.items:
            if item.surface.repository_id != self.repository_id:
                raise ValueError(
                    "pending curation items must share the result repository"
                )
        if self.truncated:
            if not self.items or self.next_after != self.items[-1].ref:
                raise ValueError(
                    "truncated pending curation requires next_after equal to "
                    "the last returned revision"
                )
        elif self.next_after is not None:
            raise ValueError("non-truncated pending curation cannot carry next_after")


@_dataclass(frozen=True)
class UnderstandingSnapshotSelector:
    """Select one exact understanding version; omitted version means current."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="understanding-snapshot repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("understanding_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="understanding-snapshot identity",
        ),
    )

    repository_id: str
    understanding_id: str
    version: int | None = None

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)
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
    """Select one retained recording receipt by its request identity."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="receipt repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("request_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="receipt request identity",
        ),
    )

    repository_id: str
    request_id: str

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)


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
class UnderstandingVersionRef:
    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber


@_dataclass(frozen=True)
class HistoricalAcceptanceDetailUnavailable:
    """Retained acceptance coordinates whose original effect detail was not stored."""

    understanding_versions: tuple[UnderstandingVersionRef, ...]
    verification_run_ids: tuple[VerificationRunId, ...]
    challenge_ids: tuple[ChallengeId, ...]
    dependent_effect_refs: tuple[ConclusionRevisionRef, ...]
    reason: str
    recovery: str

    def __post_init__(self) -> None:
        _require_non_empty("historical acceptance reason", self.reason)
        _require_non_empty("historical acceptance recovery", self.recovery)


@_dataclass(frozen=True)
class AcceptedVerificationReceipt:
    """Exact recorded execution facts, without live qualification."""

    verification_runs: tuple[VerificationRun, ...]

    def __post_init__(self) -> None:
        if not self.verification_runs:
            raise ValueError("verification acceptance requires a recorded run")


@_dataclass(frozen=True)
class RetrievedReceipt:
    """Public immutable acceptance audit; replay internals stay private."""

    receipt_selector: ReceiptRetrievalSelector
    committed_at: _datetime.datetime
    accepted_effect: AcceptedVerificationReceipt | HistoricalAcceptanceDetailUnavailable

    def __post_init__(self) -> None:
        _require_aware("RetrievedReceipt.committed_at", self.committed_at)


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
