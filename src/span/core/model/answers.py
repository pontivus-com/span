"""Answer, gap, ambiguity, rejection, and change results.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.claims import AssertionNature
from span.core.model.effects import ChangedSurface
from span.core.model.outcomes import (
    UnderstandingRecorded,
    VerificationRecorded,
)
from span.core.model.functional_pyramid import (
    FunctionalPyramidAction,
    FunctionalPyramidCandidate,
    FunctionalPyramidId,
    FunctionalPyramidParticipation,
    FunctionalPyramidParticipationEffect,
    FunctionalPyramidPlacementView,
    FunctionalPyramidPublicFinding,
    FunctionalPyramidValidationFinding,
    FunctionalPyramidReceiptSelector,
    FunctionalPyramidStatus,
    FunctionalPyramidUnavailable,
    FunctionalPyramidVersion,
    FunctionalPyramidView,
    RetrievedFunctionalPyramidReceipt,
)
from span.core.model.investigation import (
    EvidenceAdmissionView,
    EvidenceDelivery,
    EvidenceRequest,
    InvestigationContextRef,
)
from span.core.model.primitives import (
    ConclusionRevisionRef,
    EvidenceRef,
    EvidenceScope,
    HistoricalAcceptanceDetailUnavailable,
    UnderstandingVersionNumber,
    SupportState,
    _require_non_empty,
)
from span.core.model.support import (
    SupportQualification,
    VerificationView,
)
from span.core.model.surfaces import (
    AcceptedDependencyEffect,
    SurfaceAction,
    SurfaceKey,
    SurfaceReference,
    SurfaceStatus,
)
from span.core.model.understanding import (
    AuditConclusion,
    ChallengeView,
    PendingCuration,
    ReceiptRetrievalSelector,
    RecordedQuestionGap,
    RetrievedReceipt,
    RetrievedUnderstanding,
)
from span.core.rejection import RejectionCauseKind


class GapReason(_enum.Enum):
    """The exhaustive semantic gap reasons (FD-25)."""

    INVALIDATED = "invalidated"
    UNVERIFIABLE = "unverifiable"
    PENDING_CURATION = "pending_curation"
    UNASSESSED = "unassessed"


@_dataclass(frozen=True)
class ConclusionView:
    """One current conclusion with the content the agent needs (F6, F7).

    The support evaluation is projected once. The view carries the statement,
    nature, scope, support, and the evidence references the conclusion cites,
    so a current answer never requires a second retrieval.
    """

    ref: ConclusionRevisionRef
    statement: str
    assertion_nature: AssertionNature
    scope: EvidenceScope
    support: SupportQualification
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("ConclusionView.statement", self.statement)


@_dataclass(frozen=True)
class AnswerGroup:
    """One recorded question's current conclusions in the document view."""

    question: str
    conclusions: tuple[ConclusionView, ...]

    def __post_init__(self) -> None:
        _require_non_empty("AnswerGroup.question", self.question)
        if not self.conclusions:
            raise ValueError("an AnswerGroup requires a current conclusion")


@_dataclass(frozen=True)
class Answer:
    """Current content for one surface (FD-23, FD-24, FD-28)."""

    surface: SurfaceKey
    status: SurfaceStatus
    functional_pyramid: (
        FunctionalPyramidView
        | FunctionalPyramidUnavailable
        | FunctionalPyramidParticipation
    )
    conclusions: tuple[ConclusionView, ...] = ()
    groups: tuple[AnswerGroup, ...] = ()
    gaps: tuple[RecordedQuestionGap, ...] = ()
    verification: tuple[VerificationView, ...] = ()
    references: tuple[str, ...] = ()
    admission: EvidenceAdmissionView | None = None
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        if not self.conclusions and not self.groups:
            raise ValueError("an Answer requires at least one current conclusion")
        if self.status.surface != self.surface:
            raise ValueError("Answer.status must describe Answer.surface")


@_dataclass(frozen=True)
class HistoricalConclusion:
    """One non-current conclusion served as historical content in a Gap.

    ``L2`` requires unsupported content to appear as historical content, not
    only as a reference. The carrier keeps the exact revision identity, the
    understanding version that holds it, the statement the agent needs, the
    evidence references the conclusion cites, and the present non-current
    support state that makes it historical. Evidence bodies are never copied.
    """

    ref: ConclusionRevisionRef
    understanding_version: UnderstandingVersionNumber
    statement: str
    state: SupportState
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("HistoricalConclusion.statement", self.statement)
        if self.state is SupportState.CURRENT:
            raise ValueError(
                "HistoricalConclusion.state must be non-current; a current "
                "conclusion belongs in Answer.conclusions"
            )


@_dataclass(frozen=True)
class Gap:
    """No current conclusion, with exactly one semantic reason (FD-25)."""

    surface: SurfaceKey
    status: SurfaceStatus
    functional_pyramid: (
        FunctionalPyramidView
        | FunctionalPyramidUnavailable
        | FunctionalPyramidParticipation
    )
    reason: GapReason
    recovery: str
    changed_evidence: tuple[EvidenceRef, ...] = ()
    historical: tuple[HistoricalConclusion, ...] = ()
    missing: tuple[str, ...] = ()
    source_pointers: tuple[EvidenceRequest, ...] = ()
    admission: EvidenceAdmissionView | None = None
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("Gap.recovery", self.recovery)
        if self.status.surface != self.surface:
            raise ValueError("Gap.status must describe Gap.surface")


@_dataclass(frozen=True)
class EvidencePage:
    """One bounded continuation page of explicitly selected evidence."""

    deliveries: tuple[EvidenceDelivery, ...]
    continuation: str | None = None
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        if not self.deliveries and self.continuation is not None:
            raise ValueError("an evidence page must advance or end")


@_dataclass(frozen=True)
class SurfaceDeclared:
    """One exact accepted surface boundary coordinate."""

    receipt_selector: ReceiptRetrievalSelector
    committed_at: _datetime.datetime
    action: SurfaceAction
    surface: SurfaceKey
    boundary_version: int


@_dataclass(frozen=True)
class AmbiguousSurface:
    """A reference resolves to more than one granularity (FD-26)."""

    reference: str
    candidates: tuple[SurfaceReference, ...]
    missing_decision: str

    def __post_init__(self) -> None:
        _require_non_empty("AmbiguousSurface.reference", self.reference)
        _require_non_empty("AmbiguousSurface.missing_decision", self.missing_decision)
        if len(self.candidates) < 2:
            raise ValueError("AmbiguousSurface requires at least two candidates")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError("AmbiguousSurface candidates must be distinct")


@_dataclass(frozen=True)
class Unavailable:
    """An operational failure, distinct from an empty result (FD-27, FD-39)."""

    operation: str
    failure: str
    recovery: str

    def __post_init__(self) -> None:
        _require_non_empty("Unavailable.operation", self.operation)
        _require_non_empty("Unavailable.failure", self.failure)
        _require_non_empty("Unavailable.recovery", self.recovery)


@_dataclass(frozen=True)
class Rejected:
    """An actionable rejection, distinct from replay (FD-39, FD-41).

    ``cause`` is the server's exact validation message. ``cause_kind`` is the
    typed reason; the adapter copies both and never re-derives them from text.
    """

    identity: str
    required_action: str
    cause_kind: RejectionCauseKind
    cause: str
    current_version: int | None = None
    current_boundary_version: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty("Rejected.identity", self.identity)
        _require_non_empty("Rejected.required_action", self.required_action)
        _require_non_empty("Rejected.cause", self.cause)
        if self.current_version is not None and self.current_version < 1:
            raise ValueError("Rejected.current_version must be positive")
        if (
            self.current_boundary_version is not None
            and self.current_boundary_version < 1
        ):
            raise ValueError("Rejected.current_boundary_version must be positive")


@_dataclass(frozen=True)
class FunctionalPyramidRecorded:
    """Accepted Functional Pyramid write plus its current actionable projection."""

    receipt_selector: FunctionalPyramidReceiptSelector
    committed_at: _datetime.datetime
    action: FunctionalPyramidAction
    pyramid_id: FunctionalPyramidId | None
    version: FunctionalPyramidVersion | None
    participation_effects: tuple[FunctionalPyramidParticipationEffect, ...]
    dependent_effects: tuple[ChangedSurface, ...] = ()
    reestablishment_contexts: tuple[InvestigationContextRef, ...] = ()

    def __post_init__(self) -> None:
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError("FunctionalPyramidRecorded.committed_at must be aware")
        repositories = tuple(
            context.repository_id for context in self.reestablishment_contexts
        )
        if repositories != tuple(sorted(repositories)):
            raise ValueError(
                "FunctionalPyramidRecorded contexts must be ordered by repository_id"
            )
        if len(set(repositories)) != len(repositories):
            raise ValueError(
                "FunctionalPyramidRecorded has at most one context per repository"
            )


@_dataclass(frozen=True)
class Changed:
    """The bounded reconsideration result (FD-20, FD-21, FD-22, FD-89)."""

    reestablishment_contexts: tuple[InvestigationContextRef, ...] = ()
    surfaces: tuple[ChangedSurface, ...] = ()
    unaffected: tuple[SurfaceKey, ...] = ()
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        if self.truncated and self.unaffected:
            raise ValueError("a truncated walk cannot report surfaces as unaffected")
        repositories = tuple(
            context.repository_id for context in self.reestablishment_contexts
        )
        if len(set(repositories)) != len(repositories):
            raise ValueError(
                "Changed.reestablishment_contexts must contain at most one "
                "context per repository"
            )
        if repositories != tuple(sorted(repositories)):
            raise ValueError(
                "Changed.reestablishment_contexts must be ordered by repository_id"
            )


@_dataclass(frozen=True)
class Challenged:
    """A challenge opened by reconsideration, with its derived context."""

    receipt_selector: ReceiptRetrievalSelector
    committed_at: _datetime.datetime
    challenge: ChallengeView
    context: InvestigationContextRef
    prior_conclusions: tuple[AuditConclusion, ...]

    def __post_init__(self) -> None:
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError("challenge commitment timestamp must be aware")
        if tuple(item.ref for item in self.prior_conclusions) != (
            self.challenge.target_conclusions
        ):
            raise ValueError("challenge prior conclusions must match exact targets")


@_dataclass(frozen=True)
class AcceptedDetailUnavailable:
    """A committed write whose required historical detail cannot be served."""

    receipt_selector: ReceiptRetrievalSelector | FunctionalPyramidReceiptSelector
    committed_at: _datetime.datetime
    detail: HistoricalAcceptanceDetailUnavailable

    def __post_init__(self) -> None:
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError("acceptance commitment timestamp must be aware")


class ResultKind(_enum.Enum):
    """Semantic classification of the original bounded result (L1–L4)."""

    ANSWER = "Answer"
    GAP = "Gap"
    RETRIEVED_UNDERSTANDING = "RetrievedUnderstanding"
    RETRIEVED_RECEIPT = "RetrievedReceipt"
    FUNCTIONAL_PYRAMID_VIEW = "FunctionalPyramidView"
    FUNCTIONAL_PYRAMID_STATUS = "FunctionalPyramidStatus"
    FUNCTIONAL_PYRAMID_CANDIDATE = "FunctionalPyramidCandidate"
    FUNCTIONAL_PYRAMID_RECORDED = "FunctionalPyramidRecorded"
    RETRIEVED_FUNCTIONAL_PYRAMID_RECEIPT = "RetrievedFunctionalPyramidReceipt"
    UNDERSTANDING_RECORDED = "UnderstandingRecorded"
    VERIFICATION_RECORDED = "VerificationRecorded"
    SURFACE_DECLARED = "SurfaceDeclared"
    CHANGED = "Changed"
    CHALLENGED = "Challenged"
    AMBIGUOUS_SURFACE = "AmbiguousSurface"
    ACCEPTED_DETAIL_UNAVAILABLE = "AcceptedDetailUnavailable"


def _validate_part(start: int, total: int, count: int) -> None:
    if not 0 <= start < total or not 0 < count <= total - start:
        raise ValueError("a result part must advance within its exact collection")


@_dataclass(frozen=True)
class PlacementsPart:
    start: int
    total: int
    items: tuple[FunctionalPyramidPlacementView, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class UnresolvedPart:
    start: int
    total: int
    items: tuple[FunctionalPyramidPublicFinding, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class MemberRepositoryIdsPart:
    start: int
    total: int
    items: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class StatusFindingsPart:
    start: int
    total: int
    items: tuple[FunctionalPyramidPublicFinding, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class ValidationFindingsPart:
    start: int
    total: int
    items: tuple[FunctionalPyramidValidationFinding, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class GraphFindingsPart:
    start: int
    total: int
    items: tuple[FunctionalPyramidPublicFinding, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class MemberDeclarationRefsPart:
    start: int
    total: int
    items: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class ParticipationEffectsPart:
    start: int
    total: int
    items: tuple[FunctionalPyramidParticipationEffect, ...]

    def __post_init__(self) -> None:
        _validate_part(self.start, self.total, len(self.items))


def _validate_receipt_part(
    parent: tuple[FunctionalPyramidReceiptSelector, ...],
    start: int,
    total: int,
    count: int,
) -> None:
    if len(parent) != 1:
        raise ValueError("receipt effect part requires one receipt coordinate")
    _validate_part(start, total, count)


@_dataclass(frozen=True)
class AcceptedDependencyEffectsPart:
    parent: tuple[FunctionalPyramidReceiptSelector, ...]
    start: int
    total: int
    items: tuple[AcceptedDependencyEffect, ...]

    def __post_init__(self) -> None:
        _validate_receipt_part(self.parent, self.start, self.total, len(self.items))


@_dataclass(frozen=True)
class DependentEffectRefsPart:
    parent: tuple[FunctionalPyramidReceiptSelector, ...]
    start: int
    total: int
    items: tuple[ConclusionRevisionRef, ...]

    def __post_init__(self) -> None:
        _validate_receipt_part(self.parent, self.start, self.total, len(self.items))


ResultPart = _typing.Union[
    PlacementsPart,
    UnresolvedPart,
    MemberRepositoryIdsPart,
    StatusFindingsPart,
    ValidationFindingsPart,
    GraphFindingsPart,
    MemberDeclarationRefsPart,
    ParticipationEffectsPart,
    AcceptedDependencyEffectsPart,
    DependentEffectRefsPart,
]


def _part_belongs(part: ResultPart, kind: ResultKind) -> bool:
    if isinstance(part, (PlacementsPart, UnresolvedPart)):
        return kind is ResultKind.FUNCTIONAL_PYRAMID_VIEW
    if isinstance(part, MemberRepositoryIdsPart):
        return kind in (
            ResultKind.FUNCTIONAL_PYRAMID_STATUS,
            ResultKind.RETRIEVED_FUNCTIONAL_PYRAMID_RECEIPT,
        )
    if isinstance(part, StatusFindingsPart):
        return kind is ResultKind.FUNCTIONAL_PYRAMID_STATUS
    if isinstance(part, (ValidationFindingsPart, GraphFindingsPart)):
        return kind is ResultKind.FUNCTIONAL_PYRAMID_CANDIDATE
    return kind is ResultKind.RETRIEVED_FUNCTIONAL_PYRAMID_RECEIPT


@_dataclass(frozen=True)
class ResultPage:
    """An advancing slice of one bound selection, never a repeated obtain."""

    selection_id: str
    result_kind: ResultKind
    parts: tuple[ResultPart, ...]
    continuation: str | None
    omitted: tuple[str, ...]
    truncated: bool

    def __post_init__(self) -> None:
        _require_non_empty("ResultPage.selection_id", self.selection_id)
        if not self.parts:
            raise ValueError("a result page must advance")
        if any(not _part_belongs(part, self.result_kind) for part in self.parts):
            raise ValueError("result part does not belong to the bound result kind")
        if self.truncated != (self.continuation is not None):
            raise ValueError("truncation requires an exact continuation")
        if self.truncated != bool(self.omitted):
            raise ValueError("omission metadata must match truncation")
        if self.continuation is not None:
            _require_non_empty("ResultPage.continuation", self.continuation)


AskResult = _typing.Union[
    ResultPage,
    Answer,
    Gap,
    AmbiguousSurface,
    RetrievedUnderstanding,
    RetrievedReceipt,
    RetrievedFunctionalPyramidReceipt,
    EvidencePage,
    FunctionalPyramidStatus,
    FunctionalPyramidView,
    FunctionalPyramidParticipation,
    FunctionalPyramidUnavailable,
    FunctionalPyramidCandidate,
    PendingCuration,
    Rejected,
    Unavailable,
]
RecordResult = _typing.Union[
    UnderstandingRecorded,
    VerificationRecorded,
    SurfaceDeclared,
    FunctionalPyramidRecorded,
    AcceptedDetailUnavailable,
    Rejected,
    Unavailable,
]
ReconsiderResult = _typing.Union[
    Changed, Challenged, AcceptedDetailUnavailable, Rejected, Unavailable
]
