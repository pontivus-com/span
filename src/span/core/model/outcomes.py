"""Recording outcomes: compact public acceptance plus exact audit coordinates."""

from __future__ import annotations

import datetime as _datetime
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    UnderstandingId,
    UnderstandingVersionNumber,
    VerificationRunId,
)
from span.core.model.recording import RecordReceipt
from span.core.model.support import (
    SupportUnavailable,
    SupportQualification,
    VerificationQualification,
)
from span.core.model.effects import ChangedSurface
from span.core.model.investigation import InvestigationContextRef
from span.core.model.surfaces import SurfaceKey
from span.core.model.understanding import (
    AcceptedChallengeDisposition,
    AcceptedRevisionEffect,
    Challenge,
    ReceiptRetrievalSelector,
    RevisionEffectAction,
)
from span.core.model.verification import VerificationOutcome


@_dataclass(frozen=True)
class RecordedRevisionEffect:
    """The exact accepted action with independently evaluated live support."""

    effect: AcceptedRevisionEffect
    qualification: SupportQualification | SupportUnavailable | None


    def __post_init__(self) -> None:
        if (self.qualification is None) != (
            self.effect.action is RevisionEffectAction.WITHDRAW
        ):
            raise ValueError("withdrawal alone has no live support qualification")


@_dataclass(frozen=True)
class UnderstandingRecorded:
    """One accepted understanding effect with compact live qualification."""

    receipt_selector: ReceiptRetrievalSelector
    committed_at: _datetime.datetime
    understanding_id: UnderstandingId
    version: UnderstandingVersionNumber
    surface: SurfaceKey
    revision_effects: tuple[RecordedRevisionEffect, ...]
    challenge_dispositions: tuple[AcceptedChallengeDisposition, ...]
    dependent_effects: tuple[ChangedSurface, ...]
    reestablishment_contexts: tuple[InvestigationContextRef, ...]


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
