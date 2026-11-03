"""Answer, gap, ambiguity, rejection, and change results.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.claims import AssertionNature
from span.core.model.outcomes import (
    UnderstandingRecorded,
    VerificationRecorded,
)
from span.core.model.primitives import (
    ConclusionRevisionRef,
    EvidenceRef,
    EvidenceScope,
    InvestigationContextId,
    SourceObservationId,
    _require_non_empty,
)
from span.core.model.repository import EvidenceUnit
from span.core.model.support import (
    ConclusionSupport,
    SupportEvaluation,
    SupportUnavailable,
    VerificationSupport,
)
from span.core.model.surfaces import (
    Surface,
    SurfaceKey,
    SurfaceStatus,
)
from span.core.model.understanding import (
    Challenge,
    RecordedQuestionGap,
    RetrievedReceipt,
    RetrievedUnderstanding,
)
from span.core.model.verification import VerificationRun
from span.core.rejection import RejectionCauseKind


class GapReason(_enum.Enum):
    """The four exhaustive gap reasons (FD-25)."""

    INVALIDATED = "invalidated"
    UNVERIFIABLE = "unverifiable"
    UNASSESSED = "unassessed"
    NO_MATCH = "no_match"


class ChangeReason(_enum.Enum):
    """Why a surface appears in a reconsideration result (FD-20)."""

    CONTAINMENT = "containment"
    DIRECT = "direct"
    INDIRECT = "indirect"


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
    support: ConclusionSupport
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("ConclusionView.statement", self.statement)
        if self.support.ref != self.ref:
            raise ValueError("ConclusionView.support must describe ConclusionView.ref")


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
    qualification: VerificationSupport | SupportUnavailable

    def __post_init__(self) -> None:
        if isinstance(self.qualification, VerificationSupport):
            if self.qualification.run.run_id != self.run.run_id:
                raise ValueError(
                    "VerificationView.qualification must describe the same run"
                )


@_dataclass(frozen=True)
class Answer:
    """Current content for one surface (FD-23, FD-24, FD-28)."""

    surface: SurfaceKey
    status: SurfaceStatus
    question: str = ""
    conclusions: tuple[ConclusionView, ...] = ()
    groups: tuple[AnswerGroup, ...] = ()
    gaps: tuple[RecordedQuestionGap, ...] = ()
    verification: tuple[VerificationView, ...] = ()
    references: tuple[str, ...] = ()
    context: InvestigationContextId | None = None
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        if not self.conclusions and not self.groups:
            raise ValueError("an Answer requires at least one current conclusion")
        if self.question:
            if not self.conclusions:
                raise ValueError(
                    "a question Answer requires at least one current conclusion"
                )
        elif not self.groups:
            raise ValueError(
                "a no-question Answer requires at least one grouped question"
            )
        if self.status.surface != self.surface:
            raise ValueError("Answer.status must describe Answer.surface")


@_dataclass(frozen=True)
class Gap:
    """No current conclusion, with exactly one reason (FD-25)."""

    surface: SurfaceKey
    reason: GapReason
    recovery: str
    question: str = ""
    changed_evidence: tuple[EvidenceRef, ...] = ()
    historical: tuple[ConclusionRevisionRef, ...] = ()
    missing: tuple[str, ...] = ()
    evidence: tuple[EvidenceUnit, ...] = ()
    observations: tuple[SourceObservationId, ...] = ()
    context: InvestigationContextId | None = None
    continuation: str | None = None
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("Gap.recovery", self.recovery)


@_dataclass(frozen=True)
class EvidencePage:
    """One bounded page of evidence omitted from a gap (FD-55–FD-57).

    It carries evidence, not current conclusions. A page always advances: a
    page with no evidence and the same continuation is invalid.
    """

    evidence: tuple[EvidenceUnit, ...]
    continuation: str | None = None
    omitted: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        if not self.evidence and self.continuation is not None:
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
    candidates: tuple[SurfaceKey, ...]
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
    reasons: tuple[ChangeReason, ...]
    support: SupportEvaluation | SupportUnavailable

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
class Changed:
    """The bounded reconsideration result (FD-20, FD-21, FD-22)."""

    surfaces: tuple[ChangedSurface, ...] = ()
    unaffected: tuple[SurfaceKey, ...] = ()
    omitted: tuple[str, ...] = ()
    truncated: bool = False
    context: InvestigationContextId | None = None

    def __post_init__(self) -> None:
        if self.truncated and self.unaffected:
            raise ValueError("a truncated walk cannot report surfaces as unaffected")


@_dataclass(frozen=True)
class Challenged:
    """A challenge opened by reconsideration, with its derived context."""

    challenge: Challenge
    context: InvestigationContextId | None = None


AskResult = _typing.Union[
    Answer,
    Gap,
    AmbiguousSurface,
    RetrievedUnderstanding,
    RetrievedReceipt,
    EvidencePage,
    Unavailable,
]
RecordResult = _typing.Union[
    UnderstandingRecorded,
    VerificationRecorded,
    SurfaceDeclared,
    Rejected,
    Unavailable,
]
ReconsiderResult = _typing.Union[Changed, Challenged, Rejected, Unavailable]
