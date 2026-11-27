"""Recording identity, request keys, and immutable acceptance receipts.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    ChallengeId,
    ChallengeRevision,
    ConclusionRevisionRef,
    ContentDigest,
    EvidenceRef,
    InvestigationContextId,
    RequestId,
    UnderstandingId,
    UnderstandingVersionNumber,
    VerificationRunId,
    _require_non_empty,
)
from span.core.model.investigation import InvestigationContextRef
from span.core.model.surfaces import SurfaceAction, SurfaceKey
from span.core.model.understanding import (
    AcceptedRevisionEffect,
    AcceptedChallengeDisposition,
    AcceptedVerificationReceipt,
    ReceiptRetrievalSelector,
    RetrievedContext,
    RetrievedUnderstanding,
    HistoricalAcceptanceDetailUnavailable,
    UnderstandingVersionRef,
)
from span.core.model.functional_pyramid import (
    FunctionalPyramidAction,
    FunctionalPyramidId,
    FunctionalPyramidMemberView,
    FunctionalPyramidParticipationEffect,
    FunctionalPyramidVersion,
)


@_dataclass(frozen=True)
class RecordingIdentity:
    """The caller-owned recording decision identity (FD-3).

    ``request_id`` is the key. ``context_id`` is the evidence context the
    request was made in; it is not part of the receipt key, so a replay is
    decided by request identity and content digest alone.
    """

    repository_id: str
    request_id: RequestId
    context_id: InvestigationContextId

    def __post_init__(self) -> None:
        _require_non_empty("RecordingIdentity.repository_id", self.repository_id)


@_dataclass(frozen=True)
class RecordingKey:
    """The unique key of one recording decision: repository and request."""

    repository_id: str
    request_id: RequestId

    def __post_init__(self) -> None:
        _require_non_empty("RecordingKey.repository_id", self.repository_id)


@_dataclass(frozen=True)
class RequestBinding:
    """One initial request identity plus the canonical input digest."""

    repository_id: str
    request_id: RequestId
    content_digest: ContentDigest

    def __post_init__(self) -> None:
        _require_non_empty("RequestBinding.repository_id", self.repository_id)


class ChangeReason(_enum.Enum):
    """Why a surface appears in a reconsideration result (FD-20)."""

    CONTAINMENT = "containment"
    DIRECT = "direct"
    INDIRECT = "indirect"


@_dataclass(frozen=True)
class AcceptedDependencyEffect:
    surface: SurfaceKey
    ref: ConclusionRevisionRef
    reasons: tuple[ChangeReason, ...]

    def __post_init__(self) -> None:
        if not self.reasons or len(set(self.reasons)) != len(self.reasons):
            raise ValueError("accepted effect requires distinct nonempty reasons")


@_dataclass(frozen=True)
class AcceptedDependencyEffects:
    effects: tuple[AcceptedDependencyEffect, ...]

    def __post_init__(self) -> None:
        if len({item.ref for item in self.effects}) != len(self.effects):
            raise ValueError("accepted effect refs must be unique")


@_dataclass(frozen=True)
class AcceptedChallengeDispositionRef:
    challenge_id: ChallengeId
    challenge_revision: ChallengeRevision


@_dataclass(frozen=True)
class AcceptedUnderstandingEffect:
    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    revision_effects: tuple[AcceptedRevisionEffect, ...]
    challenge_dispositions: tuple[AcceptedChallengeDispositionRef, ...]
    dependency_effects: AcceptedDependencyEffects

    def __post_init__(self) -> None:
        if any(
            item.ref.understanding_id != self.understanding_id
            for item in self.revision_effects
        ):
            raise ValueError("accepted revision effect crosses understandings")


@_dataclass(frozen=True)
class AcceptedVerificationEffect:
    run_id: VerificationRunId


@_dataclass(frozen=True)
class AcceptedSurfaceEffect:
    action: SurfaceAction
    surface: SurfaceKey
    boundary_version: int

    def __post_init__(self) -> None:
        if self.boundary_version < 1:
            raise ValueError("accepted boundary version must be positive")


@_dataclass(frozen=True)
class AcceptedChallengeOpeningEffect:
    challenge_id: ChallengeId
    challenge_revision: ChallengeRevision
    target_version: UnderstandingVersionNumber
    target_conclusions: tuple[ConclusionRevisionRef, ...]

    def __post_init__(self) -> None:
        if self.challenge_revision.value != 1 or not self.target_conclusions:
            raise ValueError("accepted challenge opening requires initial exact targets")


NewAcceptedEffect = _typing.Union[
    AcceptedUnderstandingEffect,
    AcceptedVerificationEffect,
    AcceptedSurfaceEffect,
    AcceptedChallengeOpeningEffect,
]
AcceptedEffect = NewAcceptedEffect | HistoricalAcceptanceDetailUnavailable


@_dataclass(frozen=True)
class RecordReceipt:
    """Immutable acceptance under the canonical owner key and original digest."""

    key: RecordingKey
    original_addressing_repository_id: str
    content_digest: ContentDigest
    committed_at: _datetime.datetime
    accepted_effect: AcceptedEffect
    context: InvestigationContextRef | None
    replay_expires_at: _datetime.datetime | None

    def __post_init__(self) -> None:
        _require_non_empty(
            "original addressing repository", self.original_addressing_repository_id
        )
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError("RecordReceipt.committed_at must be timezone-aware")
        if self.replay_expires_at is not None:
            if (
                self.replay_expires_at.tzinfo is None
                or self.replay_expires_at.utcoffset() is None
            ):
                raise ValueError("RecordReceipt.replay_expires_at must be aware")
            if self.replay_expires_at < self.committed_at:
                raise ValueError("replay_expires_at cannot precede committed_at")
        if (self.context is None) != isinstance(
            self.accepted_effect, AcceptedSurfaceEffect
        ):
            raise ValueError("only a surface acceptance has no investigation context")
        if (
            self.context is not None
            and self.context.repository_id != self.key.repository_id
        ):
            raise ValueError("receipt context must belong to the canonical owner")
        if (
            isinstance(self.accepted_effect, AcceptedSurfaceEffect)
            and self.accepted_effect.surface.repository_id != self.key.repository_id
        ):
            raise ValueError("accepted surface must belong to the canonical owner")


def historical_acceptance(
    receipt: RecordReceipt,
) -> HistoricalAcceptanceDetailUnavailable:
    """Name known acceptance coordinates when exact detail cannot be served."""
    effect = receipt.accepted_effect
    if isinstance(effect, HistoricalAcceptanceDetailUnavailable):
        return effect
    versions: tuple[UnderstandingVersionRef, ...] = ()
    runs: tuple[VerificationRunId, ...] = ()
    challenges: tuple[ChallengeId, ...] = ()
    dependents: tuple[ConclusionRevisionRef, ...] = ()
    if isinstance(effect, AcceptedUnderstandingEffect):
        versions = (UnderstandingVersionRef(effect.understanding_id, effect.version),)
        challenges = tuple(item.challenge_id for item in effect.challenge_dispositions)
        dependents = tuple(item.ref for item in effect.dependency_effects.effects)
    elif isinstance(effect, AcceptedVerificationEffect):
        runs = (effect.run_id,)
    elif isinstance(effect, AcceptedChallengeOpeningEffect):
        challenges = (effect.challenge_id,)
    return HistoricalAcceptanceDetailUnavailable(
        understanding_versions=versions,
        verification_run_ids=runs,
        challenge_ids=challenges,
        dependent_effect_refs=dependents,
        reason="exact accepted detail is unavailable",
        recovery="retrieve the named historical records; do not repeat the write",
    )


@_dataclass(frozen=True)
class FunctionalPyramidReceipt:
    request_id: RequestId
    content_digest: ContentDigest
    committed_at: _datetime.datetime
    action: FunctionalPyramidAction
    pyramid_id: FunctionalPyramidId | None
    version: FunctionalPyramidVersion | None
    members: tuple[FunctionalPyramidMemberView, ...]
    participation_effects: tuple[FunctionalPyramidParticipationEffect, ...]
    dependency_effects: (
        AcceptedDependencyEffects | HistoricalAcceptanceDetailUnavailable
    )

    def __post_init__(self) -> None:
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError(
                "FunctionalPyramidReceipt.committed_at must be aware"
            )
        if len({effect.repository_id for effect in self.participation_effects}) != len(
            self.participation_effects
        ):
            raise ValueError("participation effects must be unique per repository")
        if self.action in (
            FunctionalPyramidAction.ACTIVATE,
            FunctionalPyramidAction.REVISE,
        ):
            if self.pyramid_id is None or self.version is None or not self.members:
                raise ValueError(
                    "activate/revise receipt requires live instance members"
                )
            return
        if self.members:
            raise ValueError("deactivate/exclude receipt has no active members")
        if self.action is FunctionalPyramidAction.DEACTIVATE:
            if self.pyramid_id is None or self.version is None:
                raise ValueError("deactivate receipt requires pyramid identity/version")
            return
        if self.action is FunctionalPyramidAction.EXCLUDE:
            if self.pyramid_id is not None or self.version is not None:
                raise ValueError("exclude receipt has no pyramid identity/version")


@_dataclass(frozen=True)
class RetrievedFunctionalPyramidReceipt:
    """Public installation acceptance; digest and retained member carriers stay private."""

    request_id: RequestId
    committed_at: _datetime.datetime
    action: FunctionalPyramidAction
    pyramid_id: FunctionalPyramidId | None
    version: FunctionalPyramidVersion | None
    member_repository_ids: tuple[str, ...]
    member_declaration_refs: tuple[EvidenceRef, ...]
    participation_effects: tuple[FunctionalPyramidParticipationEffect, ...]
    dependency_effects: (
        AcceptedDependencyEffects | HistoricalAcceptanceDetailUnavailable
    )

    @classmethod
    def from_receipt(
        cls, receipt: FunctionalPyramidReceipt
    ) -> RetrievedFunctionalPyramidReceipt:
        return cls(
            request_id=receipt.request_id,
            committed_at=receipt.committed_at,
            action=receipt.action,
            pyramid_id=receipt.pyramid_id,
            version=receipt.version,
            member_repository_ids=tuple(item.repository_id for item in receipt.members),
            member_declaration_refs=tuple(
                ref for item in receipt.members for ref in item.declaration_refs
            ),
            participation_effects=receipt.participation_effects,
            dependency_effects=receipt.dependency_effects,
        )


@_dataclass(frozen=True)
class AcceptedUnderstandingReceipt:
    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    revision_effects: tuple[AcceptedRevisionEffect, ...]
    challenge_dispositions: tuple[AcceptedChallengeDisposition, ...]
    dependency_effects: AcceptedDependencyEffects


ReceiptAuditEffect = _typing.Union[
    AcceptedUnderstandingReceipt,
    AcceptedVerificationReceipt,
    AcceptedSurfaceEffect,
    AcceptedChallengeOpeningEffect,
    HistoricalAcceptanceDetailUnavailable,
]


@_dataclass(frozen=True)
class RetrievedReceipt:
    receipt_selector: ReceiptRetrievalSelector
    committed_at: _datetime.datetime
    accepted_effect: ReceiptAuditEffect

    def __post_init__(self) -> None:
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError("receipt audit timestamp must be aware")


RetrieveResult = _typing.Union[
    RetrievedUnderstanding,
    RetrievedContext,
    RetrievedReceipt,
]


class ReceiptDecisionKind(_enum.Enum):
    NEW = "NEW"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"


@_dataclass(frozen=True)
class ReceiptDecision:
    """The receipt-first outcome for one recording key/content pair."""

    kind: ReceiptDecisionKind
    receipt: RecordReceipt | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.kind is ReceiptDecisionKind.NEW:
            if self.receipt is not None:
                raise ValueError("a NEW decision carries no receipt")
        elif self.receipt is None:
            raise ValueError(f"a {self.kind.value} decision requires a receipt")
