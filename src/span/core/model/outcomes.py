"""Recording outcomes: compact public acceptance plus exact audit coordinates."""

from __future__ import annotations

import datetime as _datetime
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    ConclusionRevisionRef,
    UnderstandingId,
    UnderstandingVersionNumber,
    VerificationRunId,
)
from span.core.model.recording import RecordReceipt
from span.core.model.support import (
    SupportUnavailable,
    UnderstandingQualification,
    VerificationQualification,
)
from span.core.model.surfaces import SurfaceStatus, SurfaceStatusUnavailable
from span.core.model.understanding import Challenge, ReceiptRetrievalSelector
from span.core.model.verification import VerificationOutcome


@_dataclass(frozen=True)
class UnderstandingRecorded:
    """One accepted understanding effect with compact live qualification."""

    receipt_selector: ReceiptRetrievalSelector
    committed_at: _datetime.datetime
    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    affected_revisions: tuple[ConclusionRevisionRef, ...]
    dependent_effects: tuple[ConclusionRevisionRef, ...]
    qualification: UnderstandingQualification | SupportUnavailable
    status: SurfaceStatus | SurfaceStatusUnavailable


@_dataclass(frozen=True)
class VerificationRecorded:
    """One accepted verification run with compact live qualification."""

    receipt_selector: ReceiptRetrievalSelector
    committed_at: _datetime.datetime
    run_id: VerificationRunId
    command: str | None
    scenario: str | None
    outcome: VerificationOutcome
    qualification: VerificationQualification | SupportUnavailable


@_dataclass(frozen=True)
class ChallengeRecorded:
    """Internal accepted challenge composition; public reconsider returns Challenged."""

    receipt: RecordReceipt
    challenge: Challenge


RecordOutcome = _typing.Union[
    UnderstandingRecorded,
    VerificationRecorded,
    ChallengeRecorded,
]
