"""Closed recording commands and their branch-required content.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.claims import AssertionNature
from span.core.model.primitives import (
    ChallengeId,
    ChallengeRevision,
    ConclusionId,
    ConclusionRevisionRef,
    EvidenceRef,
    EvidenceScope,
    RequestId,
    SemanticBasis,
    UnderstandingId,
    UnderstandingVersionNumber,
    _require_non_empty,
)
from span.core.model.recording import RecordingIdentity
from span.core.model.support import SupportDependency
from span.core.model.verification import ProposedVerificationRun


@_dataclass(frozen=True)
class ContextBoundTarget:
    """The context's bound question/scope is the create target."""


@_dataclass(frozen=True)
class ExplicitTarget:
    """The create command supplies the semantic target explicitly."""

    question: str
    scope: EvidenceScope

    def __post_init__(self) -> None:
        _require_non_empty("ExplicitTarget.question", self.question)


UnderstandingTarget = _typing.Union[ContextBoundTarget, ExplicitTarget]


@_dataclass(frozen=True)
class ConclusionContentDraft:
    """Flattened supported-conclusion content used by every action."""

    statement: str
    assertion_nature: AssertionNature
    scope: EvidenceScope
    support: tuple[SupportDependency, ...]
    basis: SemanticBasis

    def __post_init__(self) -> None:
        _require_non_empty("ConclusionContentDraft.statement", self.statement)
        if not self.support:
            raise ValueError(
                "a conclusion content draft requires at least one dependency"
            )


@_dataclass(frozen=True)
class ProposedConclusion(ConclusionContentDraft):
    conclusion_id: ConclusionId


@_dataclass(frozen=True)
class ConfirmConclusion(ConclusionContentDraft):
    conclusion_id: ConclusionId

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_non_empty("ConfirmConclusion.basis.summary", self.basis.summary)


@_dataclass(frozen=True)
class CorrectConclusion(ConclusionContentDraft):
    conclusion_id: ConclusionId

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_non_empty("CorrectConclusion.basis.summary", self.basis.summary)


@_dataclass(frozen=True)
class ReplaceConclusion(ConclusionContentDraft):
    old: ConclusionRevisionRef
    new_conclusion_id: ConclusionId
    replacement_basis: SemanticBasis

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_non_empty(
            "ReplaceConclusion.replacement_basis.summary",
            self.replacement_basis.summary,
        )


@_dataclass(frozen=True)
class WithdrawConclusion:
    conclusion_id: ConclusionId
    basis: SemanticBasis
    support: tuple[SupportDependency, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("WithdrawConclusion.basis.summary", self.basis.summary)


def _action_conclusion_ids(action: object) -> tuple[ConclusionId, ...]:
    if isinstance(action, ReplaceConclusion):
        return (action.old.conclusion_id, action.new_conclusion_id)
    if isinstance(action, (ConfirmConclusion, CorrectConclusion, WithdrawConclusion)):
        return (action.conclusion_id,)
    raise TypeError(f"unhandled conclusion action: {type(action).__name__}")


@_dataclass(frozen=True)
class GapDraft:
    question: str
    basis: str

    def __post_init__(self) -> None:
        _require_non_empty("GapDraft.question", self.question)
        _require_non_empty("GapDraft.basis", self.basis)


@_dataclass(frozen=True)
class UnresolvedChallengeDisposition:
    challenge_id: ChallengeId
    expected_challenge_revision: ChallengeRevision
    remaining_question: str
    basis: str

    def __post_init__(self) -> None:
        _require_non_empty(
            "UnresolvedChallengeDisposition.remaining_question",
            self.remaining_question,
        )
        _require_non_empty("UnresolvedChallengeDisposition.basis", self.basis)


@_dataclass(frozen=True)
class ResolvedChallengeDisposition:
    challenge_id: ChallengeId
    expected_challenge_revision: ChallengeRevision
    reasoning: str
    resulting_understanding_id: UnderstandingId
    resulting_version: UnderstandingVersionNumber
    conclusions: tuple[ConclusionRevisionRef, ...] = ()
    withdrawn: tuple[ConclusionRevisionRef, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("ResolvedChallengeDisposition.reasoning", self.reasoning)


ChallengeDisposition = _typing.Union[
    UnresolvedChallengeDisposition,
    ResolvedChallengeDisposition,
]


@_dataclass(frozen=True)
class StartContextRequest:
    """Start one server-issued investigation context."""

    repository_id: str
    request_id: RequestId
    scope: EvidenceScope
    question: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("StartContextRequest.repository_id", self.repository_id)
        if self.question is not None:
            _require_non_empty("StartContextRequest.question", self.question)


@_dataclass(frozen=True)
class CreateUnderstandingCommand:
    identity: RecordingIdentity
    target: UnderstandingTarget
    conclusions: tuple[ProposedConclusion, ...]
    gaps: tuple[GapDraft, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.conclusions:
            raise ValueError("a create command requires at least one conclusion")
        ids = {item.conclusion_id for item in self.conclusions}
        if len(ids) != len(self.conclusions):
            raise ValueError("duplicate conclusion IDs in one create command")


@_dataclass(frozen=True)
class UpdateUnderstandingCommand:
    identity: RecordingIdentity
    understanding_id: UnderstandingId
    expected_version: UnderstandingVersionNumber
    add: tuple[ProposedConclusion, ...] = ()
    confirm: tuple[ConfirmConclusion, ...] = ()
    correct: tuple[CorrectConclusion, ...] = ()
    replace: tuple[ReplaceConclusion, ...] = ()
    withdraw: tuple[WithdrawConclusion, ...] = ()
    gaps: tuple[GapDraft, ...] | None = None
    challenge_dispositions: tuple[ChallengeDisposition, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        actions = (
            *self.confirm,
            *self.correct,
            *self.replace,
            *self.withdraw,
        )
        if not (
            self.add or actions or self.challenge_dispositions or self.gaps is not None
        ):
            raise ValueError("an understanding update must have an effect")
        touched: set[ConclusionId] = set()
        for proposed in self.add:
            if proposed.conclusion_id in touched:
                raise ValueError(
                    "multiple actions target one conclusion: "
                    f"{proposed.conclusion_id.value}"
                )
            touched.add(proposed.conclusion_id)
        for action in actions:
            for conclusion_id in _action_conclusion_ids(action):
                if conclusion_id in touched:
                    raise ValueError(
                        "multiple actions target one conclusion: "
                        f"{conclusion_id.value}"
                    )
                touched.add(conclusion_id)
        challenge_ids = [
            disposition.challenge_id for disposition in self.challenge_dispositions
        ]
        if len(set(challenge_ids)) != len(challenge_ids):
            raise ValueError("duplicate challenge IDs in one command")


@_dataclass(frozen=True)
class CreateChallengeCommand:
    """Create one explicit challenge bound to exact revisions."""

    identity: RecordingIdentity
    understanding_id: UnderstandingId
    target_version: UnderstandingVersionNumber
    target_conclusions: tuple[ConclusionRevisionRef, ...]
    reason: str
    evidence: tuple[EvidenceRef, ...]
    provenance: str = ""

    def __post_init__(self) -> None:
        _require_non_empty("CreateChallengeCommand.reason", self.reason)
        for ref in self.target_conclusions:
            if ref.understanding_id != self.understanding_id:
                raise ValueError("challenge target crosses understandings")


@_dataclass(frozen=True)
class RecordVerificationCommand:
    identity: RecordingIdentity
    run: ProposedVerificationRun


RecordCommand = _typing.Union[
    CreateUnderstandingCommand,
    UpdateUnderstandingCommand,
    RecordVerificationCommand,
    CreateChallengeCommand,
]


def command_support_dependencies(
    command: RecordCommand,
) -> tuple[SupportDependency, ...]:
    """Every typed support dependency declared by one recording command."""
    if isinstance(command, CreateUnderstandingCommand):
        return tuple(
            dependency
            for conclusion in command.conclusions
            for dependency in conclusion.support
        )
    if isinstance(command, UpdateUnderstandingCommand):
        drafts = (
            *command.add,
            *command.confirm,
            *command.correct,
            *command.replace,
        )
        return tuple(
            [dependency for draft in drafts for dependency in draft.support]
            + [
                dependency
                for withdrawal in command.withdraw
                for dependency in withdrawal.support
            ]
        )
    return ()
