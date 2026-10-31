"""Recording outcomes: the atomic receipt plus present support qualification.

Recording returns the accepted effect and one live qualification of that
effect. The qualification is observed after commit, so a provider failure can
never turn an accepted write into a reported rejection; it is represented as
``SupportUnavailable`` instead.
"""

from __future__ import annotations

import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.recording import RecordReceipt
from span.core.model.support import (
    SupportUnavailable,
    UnderstandingSupport,
    VerificationSupport,
)
from span.core.model.understanding import Challenge


@_dataclass(frozen=True)
class UnderstandingRecorded:
    """One accepted understanding effect with its present support state."""

    receipt: RecordReceipt
    qualification: UnderstandingSupport | SupportUnavailable


@_dataclass(frozen=True)
class VerificationRecorded:
    """One accepted verification run with its present support state."""

    receipt: RecordReceipt
    qualification: VerificationSupport | SupportUnavailable


@_dataclass(frozen=True)
class ChallengeRecorded:
    """One accepted challenge, including its complete disposition history."""

    receipt: RecordReceipt
    challenge: Challenge


RecordOutcome = _typing.Union[
    UnderstandingRecorded,
    VerificationRecorded,
    ChallengeRecorded,
]
