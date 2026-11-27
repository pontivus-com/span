"""Independent execution runs and their observed support boundary.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    EvidenceScope,
    SourceObservationId,
    VerificationRunId,
    _require_non_empty,
)


class VerificationOutcome(_enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@_dataclass(frozen=True)
class VerificationScope:
    """The bounded scope an execution actually exercised."""

    description: str
    scope: EvidenceScope

    def __post_init__(self) -> None:
        _require_non_empty("VerificationScope.description", self.description)


def _validate_execution(
    *,
    repository_id: str,
    command: str | None,
    scenario: str | None,
    observer: str,
    observed_at: _datetime.datetime,
) -> None:
    _require_non_empty("VerificationRun.repository_id", repository_id)
    if not command and not scenario:
        raise ValueError("a verification run requires a command or scenario")
    _require_non_empty("VerificationRun.observer", observer)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("VerificationRun.observed_at must be aware")


def _require_observations(observations: tuple[SourceObservationId, ...]) -> None:
    if not observations:
        raise ValueError("a verification run requires source observations")


@_dataclass(frozen=True)
class ProposedVerificationRun:
    """The command-side content of one independent run."""

    repository_id: str
    scope: VerificationScope
    observations: tuple[SourceObservationId, ...]
    command: str | None
    scenario: str | None
    outcome: VerificationOutcome
    observed_at: _datetime.datetime
    observer: str
    environment_limitations: tuple[str, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        _require_observations(self.observations)
        _validate_execution(
            repository_id=self.repository_id,
            command=self.command,
            scenario=self.scenario,
            observer=self.observer,
            observed_at=self.observed_at,
        )


@_dataclass(frozen=True)
class VerificationRunFacts:
    """Immutable fixed execution facts shared by the retained and public run."""

    run_id: VerificationRunId
    repository_id: str
    scope: VerificationScope
    command: str | None
    scenario: str | None
    outcome: VerificationOutcome
    observed_at: _datetime.datetime
    observer: str
    provenance: str = ""

    def __post_init__(self) -> None:
        _validate_execution(
            repository_id=self.repository_id,
            command=self.command,
            scenario=self.scenario,
            observer=self.observer,
            observed_at=self.observed_at,
        )


@_dataclass(frozen=True)
class VerificationRun:
    """One complete immutable accepted execution."""

    facts: VerificationRunFacts
    observations: tuple[SourceObservationId, ...]
    environment_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_observations(self.observations)
