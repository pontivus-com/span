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
    UnderstandingVersionNumber,
    _require_non_empty,
)
from span.core.model.support import (
    SupportQualification,
    SupportState,
    SupportUnavailable,
    VerificationQualification,
)
from span.core.model.surfaces import (
    ChangeReason,
    Surface,
    SurfaceKey,
    SurfaceReference,
    SurfaceStatus,
)
from span.core.model.understanding import (
    AuditConclusion,
    Challenge,
    HistoricalAcceptanceDetailUnavailable,
    PendingCuration,
    ReceiptRetrievalSelector,
    RecordedQuestionGap,
    RetrievedReceipt,
    RetrievedUnderstanding,
)
from span.core.model.verification import VerificationRun
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
class VerificationView:
    """One applicable verification run and its present qualification.

    The run is authoritative for identity. A failed qualification still names
    the run it could not qualify.
    """

    run: VerificationRun
    qualification: VerificationQualification | SupportUnavailable


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
    """The accepted surface declaration or boundary update."""

    action: str
    surface: Surface

    def __post_init__(self) -> None:
        if self.action not in ("create", "update"):
            raise ValueError("SurfaceDeclared.action must be create or update")


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


@_dataclass(frozen=True)
class ChangedSurface:
    """One surface that must be re-examined, with every reason (FD-20)."""

    surface: SurfaceKey
    reasons: tuple[ChangeReason, ...]
    conclusions: tuple[ChangedConclusion, ...] = ()

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("ChangedSurface requires at least one reason")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("ChangedSurface reasons must be distinct")


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
    challenge: Challenge
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


AskResult = _typing.Union[
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
