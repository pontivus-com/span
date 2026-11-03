"""Closed recording commands and their branch-required content.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
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
from span.core.model.surfaces import SurfaceKey, SurfaceReference
from span.core.model.understanding import (
    ReceiptRetrievalSelector,
    UnderstandingSnapshotSelector,
)
from span.core.model.verification import ProposedVerificationRun


class RecordKind(_enum.Enum):
    """The three public record kinds: understanding, verification, surface."""

    UNDERSTANDING = "understanding"
    VERIFICATION = "verification"
    SURFACE = "surface"


class SurfaceAction(_enum.Enum):
    """A surface declaration is either created or boundary-updated."""

    CREATE = "create"
    UPDATE = "update"


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
                "a conclusion requires at least one support dependency; pass an "
                "AdmittedSourceSupportWire whose observation_id is the "
                "observations[0].value from the preceding ask"
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
class AskRequest:
    """One scoped question, document view, exact reference, or continuation.

    Exactly one of ``surface``, ``reference``, ``selector``, or
    ``continuation`` is supplied. ``question`` is optional for surface and
    reference forms; every other form rejects it.
    """

    repository_id: str
    request_id: str | None = None
    surface: SurfaceReference | None = None
    reference: str | None = None
    continuation: str | None = None
    selector: UnderstandingSnapshotSelector | ReceiptRetrievalSelector | None = None
    question: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("AskRequest.repository_id", self.repository_id)
        forms = (
            self.surface is not None,
            self.reference is not None,
            self.continuation is not None,
            self.selector is not None,
        )
        if sum(forms) != 1:
            raise ValueError(
                "ask takes exactly one of surface, reference, selector, or "
                "continuation"
            )
        if (self.surface is not None or self.reference is not None) and (
            self.request_id is None
        ):
            raise ValueError("a surface or reference ask requires request_id")
        if self.request_id is not None:
            _require_non_empty("AskRequest.request_id", self.request_id)
        if self.surface is not None:
            if (
                self.surface.repository_id is not None
                and self.surface.repository_id != self.repository_id
            ):
                raise ValueError("AskRequest.surface must share the repository")
        if self.reference is not None:
            _require_non_empty("AskRequest.reference", self.reference)
        if self.continuation is not None:
            _require_non_empty("AskRequest.continuation", self.continuation)
            if self.question is not None:
                raise ValueError("a continuation form does not take a question")
        if self.selector is not None:
            if self.selector.repository_id != self.repository_id:
                raise ValueError("AskRequest.selector must share the repository")
            if self.question is not None:
                raise ValueError("an exact-reference form does not take a question")
        if self.question is not None:
            _require_non_empty("AskRequest.question", self.question)


@_dataclass(frozen=True)
class ChallengeConclusionRef:
    """One exact conclusion revision named by a public challenge."""

    understanding_id: str
    conclusion_id: str
    revision: int

    def __post_init__(self) -> None:
        _require_non_empty(
            "ChallengeConclusionRef.understanding_id", self.understanding_id
        )
        _require_non_empty("ChallengeConclusionRef.conclusion_id", self.conclusion_id)
        if self.revision < 1:
            raise ValueError("ChallengeConclusionRef.revision must be positive")


@_dataclass(frozen=True)
class ChallengeRaise:
    """One explicit dispute raised through reconsider (L2 §4.3).

    ``context_id`` is optional: the service derives it from the target version
    and cited evidence when the caller does not supply a preceding context.
    """

    request_id: str
    understanding_id: str
    target_version: int
    target_conclusions: tuple[ChallengeConclusionRef, ...]
    reason: str
    evidence: tuple[EvidenceRef, ...] = ()
    context_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("ChallengeRaise.request_id", self.request_id)
        _require_non_empty("ChallengeRaise.understanding_id", self.understanding_id)
        _require_non_empty("ChallengeRaise.reason", self.reason)
        if self.target_version < 1:
            raise ValueError("ChallengeRaise.target_version must be positive")
        if not self.target_conclusions:
            raise ValueError("a challenge requires at least one target conclusion")


@_dataclass(frozen=True)
class ReconsiderRequest:
    """A changed scope to re-align, or one explicit challenge (FD-17, L2 §4.3).

    Exactly one branch is supplied: a changed scope (``changed_paths`` and/or
    ``changed_surfaces``) or a ``challenge`` raise. The two are never combined.
    """

    repository_id: str
    changed_paths: tuple[str, ...] = ()
    changed_surfaces: tuple[SurfaceKey, ...] = ()
    challenge: ChallengeRaise | None = None

    def __post_init__(self) -> None:
        _require_non_empty("ReconsiderRequest.repository_id", self.repository_id)
        has_scope = bool(self.changed_paths or self.changed_surfaces)
        if self.challenge is not None and has_scope:
            raise ValueError(
                "reconsideration takes a changed scope or a challenge, not both"
            )
        if not has_scope and self.challenge is None:
            raise ValueError("reconsideration requires a changed scope or a challenge")
        for path in self.changed_paths:
            _require_non_empty("ReconsiderRequest.changed_paths", path)
        for surface in self.changed_surfaces:
            if surface.repository_id != self.repository_id:
                raise ValueError("changed surfaces must share the repository")


@_dataclass(frozen=True)
class CreateUnderstandingCommand:
    identity: RecordingIdentity
    surface: SurfaceKey
    target: UnderstandingTarget
    conclusions: tuple[ProposedConclusion, ...]
    gaps: tuple[GapDraft, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.conclusions:
            raise ValueError("a create command requires at least one conclusion")
        if self.surface.repository_id != self.identity.repository_id:
            raise ValueError("the surface must share the recording repository")
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
