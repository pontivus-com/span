"""Recording identity, submission keys, and immutable acceptance receipts.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    ChallengeId,
    InvestigationContextId,
    RequestId,
    SubmissionId,
    UnderstandingId,
    UnderstandingVersionNumber,
    VerificationRunId,
    _require_non_empty,
)


@_dataclass(frozen=True)
class ContentDigest:
    """Canonical content digest; the server owns its derivation."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("ContentDigest", self.value)


@_dataclass(frozen=True)
class RecordingIdentity:
    """The caller-owned recording key components."""

    repository_id: str
    context_id: InvestigationContextId
    submission_id: SubmissionId

    def __post_init__(self) -> None:
        _require_non_empty("RecordingIdentity.repository_id", self.repository_id)


@_dataclass(frozen=True)
class RecordingKey:
    """The unique key of one recording submission."""

    repository_id: str
    context_id: InvestigationContextId
    submission_id: SubmissionId

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
class RecordReceipt:
    """Immutable evidence that one recording submission committed."""

    identity: RecordingIdentity
    content_digest: ContentDigest
    committed_at: _datetime.datetime
    accepted_understanding_ids: tuple[UnderstandingId, ...] = ()
    accepted_understanding_versions: tuple[UnderstandingVersionNumber, ...] = ()
    accepted_verification_run_ids: tuple[VerificationRunId, ...] = ()
    accepted_challenge_ids: tuple[ChallengeId, ...] = ()
    replay_expires_at: _datetime.datetime | None = None

    def __post_init__(self) -> None:
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
        if self.accepted_understanding_ids and (
            len(self.accepted_understanding_ids)
            != len(self.accepted_understanding_versions)
        ):
            raise ValueError("accepted understanding IDs and versions must correspond")
        if not (
            self.accepted_understanding_ids
            or self.accepted_verification_run_ids
            or self.accepted_challenge_ids
        ):
            raise ValueError("a receipt must record at least one accepted effect")


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
