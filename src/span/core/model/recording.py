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
    ContentDigest,
    CurationState,
    ConclusionRevisionRef,
    InvestigationContextId,
    RequestId,
    UnderstandingId,
    UnderstandingVersionNumber,
    VerificationRunId,
    _require_non_empty,
)
from span.core.model.investigation import InvestigationContextRef
from span.core.model.surfaces import (
    AcceptedDependencyEffects,
    SurfaceAction,
    SurfaceKey,
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


class RevisionEffectAction(_enum.Enum):
    """The exact action accepted by an understanding transition."""

    CREATE = "CREATE"
    ADD = "ADD"
    CONFIRM = "CONFIRM"
    CORRECT = "CORRECT"
    REPLACE = "REPLACE"
    WITHDRAW = "WITHDRAW"
    CURATE = "CURATE"


@_dataclass(frozen=True)
class AcceptedRevisionEffect:
    """Immutable action fact, independent of subsequent support or maturity."""

    action: RevisionEffectAction
    ref: ConclusionRevisionRef
    changed: bool
    maturity: CurationState | None
    replaced_ref: ConclusionRevisionRef | None = None

    def __post_init__(self) -> None:
        if not self.changed and self.action is not RevisionEffectAction.CONFIRM:
            raise ValueError("only confirmation may be unchanged")
        if (self.maturity is None) != (self.action is RevisionEffectAction.WITHDRAW):
            raise ValueError("withdrawal alone has no reuse maturity")
        if (self.replaced_ref is not None) != (
            self.action is RevisionEffectAction.REPLACE
        ):
            raise ValueError("replacement alone names the replaced revision")
        if self.replaced_ref is not None and (
            self.replaced_ref.understanding_id != self.ref.understanding_id
            or self.replaced_ref.conclusion_id == self.ref.conclusion_id
        ):
            raise ValueError(
                "replacement must name another lineage in the same understanding"
            )


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
class AcceptedChallengeCoordinate:
    """The exact accepted challenge disposition revision."""

    challenge_id: ChallengeId
    challenge_revision: ChallengeRevision


@_dataclass(frozen=True)
class AcceptedUnderstandingEffect:
    """The immutable facts produced by one semantic transition."""

    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    revision_effects: tuple[AcceptedRevisionEffect, ...]
    challenge_dispositions: tuple[AcceptedChallengeCoordinate, ...]
    dependent_effects: AcceptedDependencyEffects

    def __post_init__(self) -> None:
        refs = tuple(effect.ref for effect in self.revision_effects)
        if any(ref.understanding_id != self.understanding_id for ref in refs):
            raise ValueError("accepted revision effects cross understanding identity")
        if len(set(refs)) != len(refs):
            raise ValueError("accepted revision effects contain duplicate refs")
        challenge_ids = tuple(item.challenge_id for item in self.challenge_dispositions)
        if len(set(challenge_ids)) != len(challenge_ids):
            raise ValueError("accepted challenge dispositions contain duplicate IDs")


@_dataclass(frozen=True)
class AcceptedSurfaceEffect:
    """The original accepted boundary, never the mutable surface pointer."""

    action: SurfaceAction
    surface: SurfaceKey
    boundary_version: int

    def __post_init__(self) -> None:
        if self.boundary_version < 1:
            raise ValueError("accepted surface boundary version must be positive")
        if self.action is SurfaceAction.CREATE and self.boundary_version != 1:
            raise ValueError("accepted create must identify boundary version one")


@_dataclass(frozen=True)
class AcceptedChallengeOpeningEffect:
    """Exact opening identity and disputed version/refs."""

    challenge_id: ChallengeId
    challenge_revision: ChallengeRevision
    understanding_id: UnderstandingId
    target_version: UnderstandingVersionNumber
    target_conclusions: tuple[ConclusionRevisionRef, ...]

    def __post_init__(self) -> None:
        if self.challenge_revision.value != 1:
            raise ValueError("accepted challenge opening must identify revision one")
        if any(
            ref.understanding_id != self.understanding_id
            for ref in self.target_conclusions
        ):
            raise ValueError("accepted challenge opening crosses understanding identity")


@_dataclass(frozen=True)
class AcceptedVerificationEffect:
    """The exact accepted execution identity, independent of live qualification."""

    run_id: VerificationRunId


AcceptedWriteEffect = _typing.Union[
    AcceptedUnderstandingEffect,
    AcceptedVerificationEffect,
    AcceptedSurfaceEffect,
    AcceptedChallengeOpeningEffect,
]
AcceptedReceiptEffect = _typing.Union[
    AcceptedWriteEffect, HistoricalAcceptanceDetailUnavailable
]


@_dataclass(frozen=True)
class RecordReceipt:
    """Immutable acceptance, independently of live qualification and replay."""

    key: RecordingKey
    original_addressing_repository_id: str
    content_digest: ContentDigest
    committed_at: _datetime.datetime
    accepted_effect: AcceptedReceiptEffect
    context: InvestigationContextRef | None
    replay_expires_at: _datetime.datetime | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            "original addressing repository", self.original_addressing_repository_id
        )
        if self.committed_at.utcoffset() is None:
            raise ValueError("RecordReceipt.committed_at must be timezone-aware")
        if self.replay_expires_at is not None:
            if self.replay_expires_at.utcoffset() is None:
                raise ValueError("RecordReceipt.replay_expires_at must be aware")
            if self.replay_expires_at < self.committed_at:
                raise ValueError("replay_expires_at cannot precede committed_at")
        if isinstance(self.accepted_effect, AcceptedSurfaceEffect):
            if self.context is not None:
                raise ValueError("surface acceptance has no investigation context")
            if self.accepted_effect.surface.repository_id != self.key.repository_id:
                raise ValueError("surface acceptance must share receipt owner")
        elif (
            self.context is None or self.context.repository_id != self.key.repository_id
        ):
            raise ValueError("semantic acceptance requires its owner-bound context")


def unavailable_acceptance(
    receipt: RecordReceipt,
) -> HistoricalAcceptanceDetailUnavailable:
    """Retain known accepted coordinates when required detail cannot be read."""
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
        dependents = tuple(item.ref for item in effect.dependent_effects.effects)
    elif isinstance(effect, AcceptedVerificationEffect):
        runs = (effect.run_id,)
    elif isinstance(effect, AcceptedChallengeOpeningEffect):
        challenges = (effect.challenge_id,)
        versions = (
            UnderstandingVersionRef(effect.understanding_id, effect.target_version),
        )
    return HistoricalAcceptanceDetailUnavailable(
        versions,
        runs,
        challenges,
        dependents,
        "exact accepted detail is unavailable",
        "retrieve the named historical records; do not repeat the write",
    )


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
