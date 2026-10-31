"""Canonical reference-only transport projection for record commands.

This module is the single public transport boundary for the record command
shapes. It is not a host-specific DTO: every host shares it, the schema is
generated from these types, and it decodes strictly into the canonical domain
commands.

The projection carries admitted observation/reference identities, not the full
evidence or authority structures. The service resolves those references to
canonical carriers before constructing the domain command. That keeps the
wire small and preserves the evidence-admission / semantic-recording
separation.
"""

from __future__ import annotations

import datetime as _datetime
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.identity import payload_digest
from span.core.model.canonical import to_canonical
from span.core.model import commands as _c
from span.core.model import primitives as _p
from span.core.model import support as _s
from span.core.model import verification as _v
from span.core.model.recording import ContentDigest
from span.core.model.claims import AssertionNature


@_dataclass(frozen=True)
class RecordWireResolver:
    """Required reference resolution supplied by the service boundary."""

    reference: _typing.Callable[[str], _p.EvidenceRef]
    authority: _typing.Callable[[str], _p.AuthorityBinding]


@_dataclass(frozen=True)
class SourceSupportWire:
    observation_id: str


@_dataclass(frozen=True)
class AuthoritySupportWire:
    authority_ref: str


@_dataclass(frozen=True)
class PremiseSupportWire:
    understanding_id: str
    conclusion_id: str
    revision: int


@_dataclass(frozen=True)
class DiscoverySupportWire:
    observation_id: str


SupportWire = _typing.Union[
    SourceSupportWire,
    AuthoritySupportWire,
    PremiseSupportWire,
    DiscoverySupportWire,
]


@_dataclass(frozen=True)
class GapWire:
    question: str
    basis: str


@_dataclass(frozen=True)
class ConclusionWire:
    conclusion_id: str
    statement: str
    assertion_nature: AssertionNature
    scope_paths: tuple[str, ...]
    scope_evidence_refs: tuple[str, ...]
    support: tuple[SupportWire, ...]
    basis_derivation: _p.DerivationKind
    basis_summary: str
    basis_input_refs: tuple[str, ...]


@_dataclass(frozen=True)
class ReplaceWire:
    old_understanding_id: str
    old_conclusion_id: str
    old_revision: int
    new_conclusion: ConclusionWire
    replacement_basis_derivation: _p.DerivationKind
    replacement_basis_summary: str
    replacement_basis_input_refs: tuple[str, ...]


@_dataclass(frozen=True)
class WithdrawWire:
    conclusion_id: str
    basis_derivation: _p.DerivationKind
    basis_summary: str
    basis_input_refs: tuple[str, ...]
    support: tuple[SupportWire, ...] = ()


@_dataclass(frozen=True)
class ConclusionRefWire:
    understanding_id: str
    conclusion_id: str
    revision: int


@_dataclass(frozen=True)
class UnresolvedDispositionWire:
    challenge_id: str
    expected_challenge_revision: int
    remaining_question: str
    basis: str


@_dataclass(frozen=True)
class ResolvedDispositionWire:
    challenge_id: str
    expected_challenge_revision: int
    reasoning: str
    resulting_understanding_id: str
    resulting_version: int
    conclusions: tuple[ConclusionRefWire, ...] = ()
    withdrawn: tuple[ConclusionRefWire, ...] = ()
    evidence_refs: tuple[str, ...] = ()


DispositionWire = _typing.Union[
    UnresolvedDispositionWire,
    ResolvedDispositionWire,
]


@_dataclass(frozen=True)
class IdentityWire:
    repository_id: str
    context_id: str
    submission_id: str


@_dataclass(frozen=True)
class ContextBoundTargetWire:
    pass


@_dataclass(frozen=True)
class ExplicitTargetWire:
    question: str
    scope_paths: tuple[str, ...]
    scope_evidence_refs: tuple[str, ...]


TargetWire = _typing.Union[ContextBoundTargetWire, ExplicitTargetWire]


@_dataclass(frozen=True)
class RecordCreateWire:
    identity: IdentityWire
    target: TargetWire
    conclusions: tuple[ConclusionWire, ...]
    gaps: tuple[GapWire, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class RecordUpdateWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    add: tuple[ConclusionWire, ...] = ()
    confirm: tuple[ConclusionWire, ...] = ()
    correct: tuple[ConclusionWire, ...] = ()
    replace: tuple[ReplaceWire, ...] = ()
    withdraw: tuple[WithdrawWire, ...] = ()
    gaps: tuple[GapWire, ...] | None = None
    challenge_dispositions: tuple[DispositionWire, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class RecordAddWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    conclusion: ConclusionWire


@_dataclass(frozen=True)
class RecordConfirmWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    conclusion: ConclusionWire


@_dataclass(frozen=True)
class RecordCorrectWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    conclusion: ConclusionWire


@_dataclass(frozen=True)
class RecordReplaceWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    replacement: ReplaceWire


@_dataclass(frozen=True)
class RecordWithdrawWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    withdrawal: WithdrawWire


@_dataclass(frozen=True)
class ChallengeConclusionRefWire:
    understanding_id: str
    conclusion_id: str
    revision: int


@_dataclass(frozen=True)
class RecordChallengeWire:
    identity: IdentityWire
    understanding_id: str
    target_version: int
    target_conclusions: tuple[ChallengeConclusionRefWire, ...]
    reason: str
    evidence_refs: tuple[str, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class VerificationRunWire:
    repository_id: str
    scope_description: str
    scope_paths: tuple[str, ...]
    observations: tuple[str, ...]
    command: str | None
    scenario: str | None
    outcome: _v.VerificationOutcome
    observed_at: _datetime.datetime
    observer: str
    environment_limitations: tuple[str, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class RecordVerificationWire:
    identity: IdentityWire
    run: VerificationRunWire


def wire_content_digest(value: object) -> ContentDigest:
    """Hash one submitted wire payload, excluding its recording identity.

    This is the receipt-first digest: it is available before any evidence or
    authority reference is resolved, so a retained receipt can replay after
    its context was reaped. The same digest is passed to the atomic store.
    """
    canonical = to_canonical(value) if hasattr(value, "__dataclass_fields__") else value
    if not isinstance(canonical, dict):
        raise TypeError("a record wire payload must encode as an object")
    content = dict(canonical)
    content.pop("identity", None)
    return payload_digest(content)


def _scope(
    paths: tuple[str, ...],
    references: tuple[str, ...],
    resolver: RecordWireResolver,
) -> _p.EvidenceScope:
    return _p.EvidenceScope(
        paths=paths,
        evidence_refs=tuple(resolver.reference(item) for item in references),
    )


def _basis(
    derivation: _p.DerivationKind,
    summary: str,
    references: tuple[str, ...],
    resolver: RecordWireResolver,
) -> _p.SemanticBasis:
    return _p.SemanticBasis(
        derivation=derivation,
        summary=summary,
        input_refs=tuple(resolver.reference(item) for item in references),
    )


def _support(
    value: SupportWire,
    resolver: RecordWireResolver,
) -> _s.SupportDependency:
    if isinstance(value, SourceSupportWire):
        return _s.SourceSupport(
            observation_id=_p.SourceObservationId(value.observation_id)
        )
    if isinstance(value, AuthoritySupportWire):
        return _s.AuthoritySupportDependency(
            authority=resolver.authority(value.authority_ref)
        )
    if isinstance(value, PremiseSupportWire):
        return _s.PremiseSupport(
            premise=_p.ConclusionRevisionRef(
                understanding_id=_p.UnderstandingId(value.understanding_id),
                conclusion_id=_p.ConclusionId(value.conclusion_id),
                revision=_p.ConclusionRevisionNumber(value.revision),
            )
        )
    if isinstance(value, DiscoverySupportWire):
        return _s.DiscoverySupport(
            observation_id=_p.DiscoveryObservationId(value.observation_id)
        )
    raise TypeError(f"unhandled support wire: {type(value).__name__}")


def _content(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> tuple[
    str,
    AssertionNature,
    _p.EvidenceScope,
    tuple[_s.SupportDependency, ...],
    _p.SemanticBasis,
]:
    return (
        value.statement,
        value.assertion_nature,
        _scope(value.scope_paths, value.scope_evidence_refs, resolver),
        tuple(_support(item, resolver) for item in value.support),
        _basis(
            value.basis_derivation,
            value.basis_summary,
            value.basis_input_refs,
            resolver,
        ),
    )


def _proposed(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> _c.ProposedConclusion:
    statement, nature, scope, support, basis = _content(value, resolver)
    return _c.ProposedConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _confirm(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> _c.ConfirmConclusion:
    statement, nature, scope, support, basis = _content(value, resolver)
    return _c.ConfirmConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _correct(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> _c.CorrectConclusion:
    statement, nature, scope, support, basis = _content(value, resolver)
    return _c.CorrectConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _replace(
    value: ReplaceWire,
    resolver: RecordWireResolver,
) -> _c.ReplaceConclusion:
    statement, nature, scope, support, basis = _content(value.new_conclusion, resolver)
    return _c.ReplaceConclusion(
        old=_p.ConclusionRevisionRef(
            understanding_id=_p.UnderstandingId(value.old_understanding_id),
            conclusion_id=_p.ConclusionId(value.old_conclusion_id),
            revision=_p.ConclusionRevisionNumber(value.old_revision),
        ),
        new_conclusion_id=_p.ConclusionId(value.new_conclusion.conclusion_id),
        replacement_basis=_basis(
            value.replacement_basis_derivation,
            value.replacement_basis_summary,
            value.replacement_basis_input_refs,
            resolver,
        ),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _withdraw(
    value: WithdrawWire,
    resolver: RecordWireResolver,
) -> _c.WithdrawConclusion:
    return _c.WithdrawConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        basis=_basis(
            value.basis_derivation,
            value.basis_summary,
            value.basis_input_refs,
            resolver,
        ),
        support=tuple(_support(item, resolver) for item in value.support),
    )


def _identity(value: IdentityWire) -> _c.RecordingIdentity:
    return _c.RecordingIdentity(
        repository_id=value.repository_id,
        context_id=_p.InvestigationContextId(value.context_id),
        submission_id=_p.SubmissionId(value.submission_id),
    )


def _gap(value: GapWire) -> _c.GapDraft:
    return _c.GapDraft(question=value.question, basis=value.basis)


def _disposition(
    value: DispositionWire,
    resolver: RecordWireResolver,
) -> _c.ChallengeDisposition:
    if isinstance(value, UnresolvedDispositionWire):
        return _c.UnresolvedChallengeDisposition(
            challenge_id=_p.ChallengeId(value.challenge_id),
            expected_challenge_revision=_p.ChallengeRevision(
                value.expected_challenge_revision
            ),
            remaining_question=value.remaining_question,
            basis=value.basis,
        )
    if isinstance(value, ResolvedDispositionWire):
        return _c.ResolvedChallengeDisposition(
            challenge_id=_p.ChallengeId(value.challenge_id),
            expected_challenge_revision=_p.ChallengeRevision(
                value.expected_challenge_revision
            ),
            reasoning=value.reasoning,
            resulting_understanding_id=_p.UnderstandingId(
                value.resulting_understanding_id
            ),
            resulting_version=_p.UnderstandingVersionNumber(value.resulting_version),
            conclusions=tuple(
                _p.ConclusionRevisionRef(
                    understanding_id=_p.UnderstandingId(item.understanding_id),
                    conclusion_id=_p.ConclusionId(item.conclusion_id),
                    revision=_p.ConclusionRevisionNumber(item.revision),
                )
                for item in value.conclusions
            ),
            withdrawn=tuple(
                _p.ConclusionRevisionRef(
                    understanding_id=_p.UnderstandingId(item.understanding_id),
                    conclusion_id=_p.ConclusionId(item.conclusion_id),
                    revision=_p.ConclusionRevisionNumber(item.revision),
                )
                for item in value.withdrawn
            ),
            evidence=tuple(resolver.reference(item) for item in value.evidence_refs),
        )
    raise TypeError(f"unhandled disposition wire: {type(value).__name__}")


def _single_update(
    identity: IdentityWire,
    understanding_id: str,
    expected_version: int,
    *,
    add: tuple[_c.ProposedConclusion, ...] = (),
    confirm: tuple[_c.ConfirmConclusion, ...] = (),
    correct: tuple[_c.CorrectConclusion, ...] = (),
    replace: tuple[_c.ReplaceConclusion, ...] = (),
    withdraw: tuple[_c.WithdrawConclusion, ...] = (),
) -> _c.UpdateUnderstandingCommand:
    return _c.UpdateUnderstandingCommand(
        identity=_identity(identity),
        understanding_id=_p.UnderstandingId(understanding_id),
        expected_version=_p.UnderstandingVersionNumber(expected_version),
        add=add,
        confirm=confirm,
        correct=correct,
        replace=replace,
        withdraw=withdraw,
    )


def add_command(
    value: RecordAddWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        add=(_proposed(value.conclusion, resolver),),
    )


def confirm_command(
    value: RecordConfirmWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        confirm=(_confirm(value.conclusion, resolver),),
    )


def correct_command(
    value: RecordCorrectWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        correct=(_correct(value.conclusion, resolver),),
    )


def replace_command(
    value: RecordReplaceWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        replace=(_replace(value.replacement, resolver),),
    )


def withdraw_command(
    value: RecordWithdrawWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        withdraw=(_withdraw(value.withdrawal, resolver),),
    )


def create_command(
    value: RecordCreateWire,
    resolver: RecordWireResolver,
) -> _c.CreateUnderstandingCommand:
    target: _c.UnderstandingTarget
    if isinstance(value.target, ContextBoundTargetWire):
        target = _c.ContextBoundTarget()
    else:
        target = _c.ExplicitTarget(
            question=value.target.question,
            scope=_scope(
                value.target.scope_paths,
                value.target.scope_evidence_refs,
                resolver,
            ),
        )
    return _c.CreateUnderstandingCommand(
        identity=_identity(value.identity),
        target=target,
        conclusions=tuple(_proposed(item, resolver) for item in value.conclusions),
        gaps=tuple(_gap(item) for item in value.gaps),
        provenance=value.provenance,
    )


def update_command(
    value: RecordUpdateWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _c.UpdateUnderstandingCommand(
        identity=_identity(value.identity),
        understanding_id=_p.UnderstandingId(value.understanding_id),
        expected_version=_p.UnderstandingVersionNumber(value.expected_version),
        add=tuple(_proposed(item, resolver) for item in value.add),
        confirm=tuple(_confirm(item, resolver) for item in value.confirm),
        correct=tuple(_correct(item, resolver) for item in value.correct),
        replace=tuple(_replace(item, resolver) for item in value.replace),
        withdraw=tuple(_withdraw(item, resolver) for item in value.withdraw),
        gaps=None if value.gaps is None else tuple(_gap(item) for item in value.gaps),
        challenge_dispositions=tuple(
            _disposition(item, resolver) for item in value.challenge_dispositions
        ),
        provenance=value.provenance,
    )


def challenge_command(
    value: RecordChallengeWire,
    resolver: RecordWireResolver,
) -> _c.CreateChallengeCommand:
    return _c.CreateChallengeCommand(
        identity=_identity(value.identity),
        understanding_id=_p.UnderstandingId(value.understanding_id),
        target_version=_p.UnderstandingVersionNumber(value.target_version),
        target_conclusions=tuple(
            _p.ConclusionRevisionRef(
                understanding_id=_p.UnderstandingId(item.understanding_id),
                conclusion_id=_p.ConclusionId(item.conclusion_id),
                revision=_p.ConclusionRevisionNumber(item.revision),
            )
            for item in value.target_conclusions
        ),
        reason=value.reason,
        evidence=tuple(resolver.reference(item) for item in value.evidence_refs),
        provenance=value.provenance,
    )


def verification_command(
    value: RecordVerificationWire,
) -> _c.RecordVerificationCommand:
    run = value.run
    return _c.RecordVerificationCommand(
        identity=_identity(value.identity),
        run=_v.ProposedVerificationRun(
            repository_id=run.repository_id,
            scope=_v.VerificationScope(
                description=run.scope_description,
                scope=_p.EvidenceScope(paths=run.scope_paths),
            ),
            observations=tuple(
                _p.SourceObservationId(item) for item in run.observations
            ),
            command=run.command,
            scenario=run.scenario,
            outcome=run.outcome,
            observed_at=run.observed_at,
            observer=run.observer,
            environment_limitations=run.environment_limitations,
            provenance=run.provenance,
        ),
    )
