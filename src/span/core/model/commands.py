"""Closed recording commands and their branch-required content.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.schema import constraints as _constraints
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
from span.core.model.investigation import (
    EvidenceRequest,
    InvestigationContextRef,
)
from span.core.model.recording import RecordingIdentity
from span.core.model.support import SupportDependency
from span.core.model.surfaces import SurfaceKey, SurfaceReference
from span.core.model.understanding import (
    CurrentUnderstandingSelector,
    ReceiptRetrievalSelector,
    RecordedQuestionSelector,
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
    """One pure obtain, explicit admission, exact selector, or continuation."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(
                _constraints.PresenceField("surface"),
                _constraints.PresenceField("reference"),
                _constraints.PresenceField("continuation"),
                _constraints.PresenceField("selector"),
            ),
            minimum=1,
            maximum=1,
            label="ask branch",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("surface"), True
                ),
            ),
            label="surface ask repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("reference"), True
                ),
            ),
            label="reference ask repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("reference", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("reference"), True
                ),
            ),
            label="reference ask locator",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("continuation", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("continuation"), True
                ),
            ),
            label="ask continuation",
        ),
        _constraints.PresenceRule(
            fields=(
                _constraints.PresenceField("repository_id"),
                _constraints.PresenceField("request_id"),
                _constraints.PresenceField("evidence"),
            ),
            minimum=0,
            maximum=0,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("continuation"), True
                ),
            ),
            label="continuation ask has no repository override",
        ),
        _constraints.PresenceRule(
            fields=(
                _constraints.PresenceField("repository_id"),
                _constraints.PresenceField("request_id"),
                _constraints.PresenceField("evidence"),
            ),
            minimum=0,
            maximum=0,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("selector"), True
                ),
            ),
            label="selector ask namespace",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("surface.repository_id"),),
            minimum=0,
            maximum=0,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("surface"), True
                ),
            ),
            label="surface ask embedded repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("evidence", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("evidence"), True
                ),
            ),
            label="explicit evidence admission",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("request_id", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("evidence"), True
                ),
            ),
            label="explicit evidence admission request identity",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("request_id"),),
            minimum=0,
            maximum=0,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("evidence"), False
                ),
            ),
            label="pure ask request identity",
        ),
    )

    repository_id: str | None = None
    request_id: str | None = None
    surface: SurfaceReference | None = None
    reference: str | None = None
    continuation: str | None = None
    selector: (
        RecordedQuestionSelector
        | CurrentUnderstandingSelector
        | UnderstandingSnapshotSelector
        | ReceiptRetrievalSelector
        | None
    ) = None
    evidence: tuple[EvidenceRequest, ...] | None = None

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)


@_dataclass(frozen=True)
class ChallengeConclusionRef:
    """One exact conclusion revision named by a public challenge."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("understanding_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="challenge conclusion understanding identity",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("conclusion_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="challenge conclusion identity",
        ),
    )

    understanding_id: str
    conclusion_id: str
    revision: int

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)
        if self.revision < 1:
            raise ValueError("ChallengeConclusionRef.revision must be positive")


@_dataclass(frozen=True)
class ChallengeRaise:
    """One explicit dispute raised through reconsider (L2 §4.3)."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("request_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="challenge request identity",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("understanding_id", non_empty=True),),
            minimum=1,
            maximum=1,
            label="challenge understanding identity",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("reason", non_empty=True),),
            minimum=1,
            maximum=1,
            label="challenge reason",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("target_conclusions", non_empty=True),),
            minimum=1,
            maximum=1,
            label="challenge target conclusions",
        ),
    )

    request_id: str
    understanding_id: str
    target_version: int
    target_conclusions: tuple[ChallengeConclusionRef, ...]
    reason: str
    evidence: tuple[EvidenceRef, ...] = ()
    context: InvestigationContextRef | None = None

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)
        if self.target_version < 1:
            raise ValueError("ChallengeRaise.target_version must be positive")


@_dataclass(frozen=True)
class ReconsiderRequest:
    """A changed scope to re-align, or one explicit challenge."""

    __structural_rules__: _typing.ClassVar[tuple[_constraints.PresenceRule, ...]] = (
        _constraints.PresenceRule(
            fields=(
                _constraints.PresenceField("changed_paths", non_empty=True),
                _constraints.PresenceField("changed_surfaces", non_empty=True),
            ),
            minimum=1,
            maximum=2,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("challenge"), False
                ),
            ),
            label="changed-scope reconsider",
        ),
        _constraints.PresenceRule(
            fields=(
                _constraints.PresenceField("changed_paths", non_empty=True),
                _constraints.PresenceField("changed_surfaces", non_empty=True),
            ),
            minimum=0,
            maximum=0,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("challenge"), True
                ),
            ),
            label="challenge reconsider scope",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("changed_paths", non_empty=True), True
                ),
            ),
            label="changed-path repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("changed_surfaces", non_empty=True), True
                ),
            ),
            label="changed-surface repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id"),),
            minimum=0,
            maximum=0,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("challenge"), True
                ),
                _constraints.PresenceCondition(
                    _constraints.PresenceField("challenge.context"), True
                ),
            ),
            label="context-bound challenge repository",
        ),
        _constraints.PresenceRule(
            fields=(_constraints.PresenceField("repository_id", non_empty=True),),
            minimum=1,
            maximum=1,
            when=(
                _constraints.PresenceCondition(
                    _constraints.PresenceField("challenge"), True
                ),
                _constraints.PresenceCondition(
                    _constraints.PresenceField("challenge.context"), False
                ),
            ),
            label="direct challenge repository",
        ),
    )

    repository_id: str | None = None
    changed_paths: tuple[str, ...] = ()
    changed_surfaces: tuple[SurfaceKey, ...] = ()
    challenge: ChallengeRaise | None = None

    def __post_init__(self) -> None:
        _constraints.validate_structural_rules(self)
        for path in self.changed_paths:
            _require_non_empty("ReconsiderRequest.changed_paths", path)
        if self.repository_id is not None:
            for surface in self.changed_surfaces:
                if surface.repository_id != self.repository_id:
                    raise ValueError("changed surfaces must share the repository")

    @property
    def bound_repository_id(self) -> str:
        if self.challenge is not None and self.challenge.context is not None:
            return self.challenge.context.repository_id
        assert self.repository_id is not None
        return self.repository_id


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
