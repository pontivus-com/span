"""Recording identity, request keys, and immutable acceptance receipts.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.investigation import InvestigationContextRef
from span.core.model.primitives import (
    ContentDigest,
    ChallengeId,
    ConclusionRevisionRef,
    InvestigationContextId,
    HistoricalAcceptanceDetailUnavailable,
    UnderstandingVersionRef,
    RequestId,
    VerificationRunId,
    _require_non_empty,
)
from span.core.model.surfaces import AcceptedSurfaceEffect
from span.core.model.understanding import (
    AcceptedChallengeOpeningEffect,
    AcceptedUnderstandingEffect,
    ReceiptRetrievalSelector,
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


@_dataclass(frozen=True)
class AcceptedVerificationEffect:
    """The exact accepted execution identity, independent of live qualification."""

    run_id: VerificationRunId


RuntimeAcceptedEffect = _typing.Union[
    AcceptedUnderstandingEffect,
    AcceptedVerificationEffect,
    AcceptedSurfaceEffect,
    AcceptedChallengeOpeningEffect,
]
AcceptedEffect = RuntimeAcceptedEffect | HistoricalAcceptanceDetailUnavailable


@_dataclass(frozen=True)
class RecordReceipt:
    """Immutable acceptance at its original request key (TD §12)."""

    key: RecordingKey
    original_addressing_repository_id: str
    content_digest: ContentDigest
    committed_at: _datetime.datetime
    context: InvestigationContextRef | None
    accepted_effect: AcceptedEffect
    replay_expires_at: _datetime.datetime | None = None

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
        if isinstance(self.accepted_effect, AcceptedSurfaceEffect):
            if self.context is not None:
                raise ValueError("surface acceptance cannot carry a context")
            if self.accepted_effect.surface.repository_id != self.key.repository_id:
                raise ValueError("surface acceptance belongs to another repository")
        elif (
            self.context is None or self.context.repository_id != self.key.repository_id
        ):
            raise ValueError("semantic acceptance requires its exact owner context")

    @property
    def selector(self) -> ReceiptRetrievalSelector:
        return ReceiptRetrievalSelector(
            repository_id=self.key.repository_id, request_id=self.key.request_id.value
        )

    @property
    def understanding_versions(self) -> tuple[UnderstandingVersionRef, ...]:
        effect = self.accepted_effect
        if isinstance(effect, HistoricalAcceptanceDetailUnavailable):
            return effect.understanding_versions
        if isinstance(effect, AcceptedUnderstandingEffect):
            return (UnderstandingVersionRef(effect.understanding_id, effect.version),)
        return ()

    @property
    def verification_run_ids(self) -> tuple[VerificationRunId, ...]:
        effect = self.accepted_effect
        if isinstance(effect, HistoricalAcceptanceDetailUnavailable):
            return effect.verification_run_ids
        if isinstance(effect, AcceptedVerificationEffect):
            return (effect.run_id,)
        return ()

    @property
    def challenge_ids(self) -> tuple[ChallengeId, ...]:
        effect = self.accepted_effect
        if isinstance(effect, HistoricalAcceptanceDetailUnavailable):
            return effect.challenge_ids
        if isinstance(effect, AcceptedChallengeOpeningEffect):
            return (effect.challenge_id,)
        return ()

    @property
    def dependency_refs(self) -> tuple[ConclusionRevisionRef, ...]:
        effect = self.accepted_effect
        if isinstance(effect, HistoricalAcceptanceDetailUnavailable):
            return effect.dependent_effect_refs
        if isinstance(effect, AcceptedUnderstandingEffect):
            return tuple(item.ref for item in effect.dependency_effects.effects)
        return ()


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
