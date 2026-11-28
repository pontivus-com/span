"""Pure understanding/version/challenge transition and receipt decisions.

No filesystem, database, transport, clock, or model access belongs here.
The shell supplies the clock and persists the one resulting transition.
"""

from __future__ import annotations

import datetime as _datetime
from dataclasses import dataclass as _dataclass

from span.core.model.commands import (
    ChallengeDisposition,
    ConclusionContentDraft,
    ConfirmConclusion,
    CorrectConclusion,
    CreateUnderstandingCommand,
    ExplicitTarget,
    GapDraft,
    ProposedConclusion,
    ReplaceConclusion,
    ResolvedChallengeDisposition,
    UnresolvedChallengeDisposition,
    UpdateUnderstandingCommand,
    WithdrawConclusion,
)
from span.core.model.investigation import (
    ContextOrigin,
    ContextState,
    InvestigationContext,
    InvestigationContextRef,
)
from span.core.model.primitives import (
    ContentDigest,
    ChallengeId,
    ChallengeRevision,
    ConclusionId,
    ConclusionRevisionNumber,
    ConclusionRevisionRef,
    EvidenceRef,
    EvidenceScope,
    SemanticBasis,
    UnderstandingId,
    UnderstandingVersionNumber,
    evidence_scope_contains,
)
from span.core.model.recording import (
    ReceiptDecision,
    ReceiptDecisionKind,
    RecordReceipt,
    RecordingKey,
    RuntimeAcceptedEffect,
)
from span.core.model.surfaces import AcceptedDependencyEffects
from span.core.model.understanding import (
    AcceptedChallengeDispositionRef,
    AcceptedChallengeOpeningEffect,
    AcceptedUnderstandingEffect,
    Challenge,
    ChallengeDispositionRecord,
    ChallengeDispositionDecision,
    ChallengeFacts,
    ChallengeResolution,
    ChallengeResolutionFacts,
    ChallengeState,
    AcceptedRevisionEffect,
    CurationDisposition,
    CurationOrigin,
    CurationState,
    RevisionEffectAction,
    ResolvedChallengeRecord,
    UnresolvedChallengeRecord,
    ConclusionRevision,
    RecordedQuestionGap,
    SupportedConclusion,
    Understanding,
    UnderstandingVersion,
    WithdrawnConclusion,
)
from span.core.rejection import Rejection, RejectionCauseKind


class RecordingConflict(Rejection):
    """A compare-and-set, receipt, or challenge revision conflict."""

    def __init__(
        self,
        cause: str,
        *,
        cause_kind: RejectionCauseKind = RejectionCauseKind.VERSION_CONFLICT,
        current_version: int | None = None,
    ) -> None:
        super().__init__(
            cause,
            cause_kind=cause_kind,
            current_version=current_version,
        )


class RecordingValidationError(Rejection):
    """The command/context content cannot be accepted as submitted."""

    def __init__(
        self,
        cause: str,
        *,
        cause_kind: RejectionCauseKind = RejectionCauseKind.VALIDATION,
        public_identity: str | None = None,
        public_cause: str | None = None,
    ) -> None:
        super().__init__(
            cause,
            cause_kind=cause_kind,
            public_identity=public_identity,
            public_cause=public_cause,
        )

    @classmethod
    def context_required(cls, cause: str) -> RecordingValidationError:
        """Construct the canonical missing-context validation failure."""
        return cls(cause, cause_kind=RejectionCauseKind.CONTEXT_REQUIRED)

    @classmethod
    def continuation_invalid(cls, cause: str) -> RecordingValidationError:
        """Construct the canonical unusable-continuation validation failure."""
        return cls(cause, cause_kind=RejectionCauseKind.CONTINUATION_INVALID)


@_dataclass(frozen=True)
class ChallengeEffect:
    challenge_id: ChallengeId
    previous_revision: ChallengeRevision
    new_revision: ChallengeRevision
    state: ChallengeState
    disposition: ChallengeDispositionRecord
    resolution: ChallengeResolution | None = None


@_dataclass(frozen=True)
class UnderstandingTransition:
    understanding: Understanding
    new_version: UnderstandingVersion
    new_conclusions: tuple[ConclusionRevision, ...]
    challenge_effects: tuple[ChallengeEffect, ...] = ()
    curations: tuple[CurationDisposition, ...] = ()
    revision_effects: tuple[AcceptedRevisionEffect, ...] = ()

    def accepted_effect(
        self, dependencies: AcceptedDependencyEffects
    ) -> AcceptedUnderstandingEffect:
        """Project accepted facts directly, without inspecting a later version."""
        return AcceptedUnderstandingEffect(
            understanding_id=self.understanding.understanding_id,
            version=self.new_version.version,
            revision_effects=self.revision_effects,
            challenge_dispositions=tuple(
                AcceptedChallengeDispositionRef(
                    effect.challenge_id, effect.new_revision
                )
                for effect in self.challenge_effects
            ),
            dependency_effects=dependencies,
        )


def accepted_challenge_opening(challenge: Challenge) -> AcceptedChallengeOpeningEffect:
    """Preserve the original opening coordinate before any disposition."""
    if (
        challenge.facts.state is not ChallengeState.OPEN
        or challenge.facts.challenge_revision.value != 1
    ):
        raise ValueError("challenge opening requires the newly accepted revision")
    return AcceptedChallengeOpeningEffect(
        challenge_id=challenge.facts.challenge_id,
        challenge_revision=challenge.facts.challenge_revision,
        understanding_id=challenge.facts.understanding_id,
        target_version=challenge.facts.target_version,
        target_conclusions=challenge.target_conclusions,
    )


def receipt_content_decision(
    existing_digest: ContentDigest | None,
    digest: ContentDigest,
) -> ReceiptDecisionKind:
    """Namespace-neutral replay/conflict decision for one request content digest."""
    if existing_digest is None:
        return ReceiptDecisionKind.NEW
    if existing_digest == digest:
        return ReceiptDecisionKind.REPLAY
    return ReceiptDecisionKind.CONFLICT


def receipt_decision(
    existing: RecordReceipt | None,
    key: RecordingKey,
    digest: ContentDigest,
) -> ReceiptDecision:
    """Receipt-first decision for one request key/content pair (FD-3)."""
    if existing is not None and existing.key != key:
        raise RecordingConflict(
            "receipt identity does not match the recording key",
            cause_kind=RejectionCauseKind.REPLAY_CONFLICT,
        )
    decision = receipt_content_decision(
        None if existing is None else existing.content_digest,
        digest,
    )
    if decision is ReceiptDecisionKind.NEW:
        return ReceiptDecision(decision)
    if decision is ReceiptDecisionKind.REPLAY:
        return ReceiptDecision(decision, receipt=existing)
    return ReceiptDecision(
        decision,
        receipt=existing,
        reason="this submission identity already committed different content",
    )


def build_receipt(
    key: RecordingKey,
    digest: ContentDigest,
    committed_at: _datetime.datetime,
    *,
    effect: RuntimeAcceptedEffect,
    context: InvestigationContextRef | None,
    original_addressing_repository_id: str,
    replay_expires_at: _datetime.datetime | None = None,
) -> RecordReceipt:
    """Build one exact runtime receipt; historical uncertainty is offline-only."""
    return RecordReceipt(
        key=key,
        original_addressing_repository_id=original_addressing_repository_id,
        content_digest=digest,
        committed_at=committed_at,
        context=context,
        accepted_effect=effect,
        replay_expires_at=replay_expires_at,
    )


def _scopes_compatible(left: EvidenceScope, right: EvidenceScope) -> bool:
    return evidence_scope_contains(left, right) or evidence_scope_contains(right, left)


def _require_live_context(context: InvestigationContext, repository_id: str) -> None:
    if context.state is not ContextState.LIVE:
        raise RecordingValidationError("the investigation context is not live")
    if context.repository_id != repository_id:
        raise RecordingValidationError("the context belongs to another repository")


def resolve_create_target(
    target: object,
    context: InvestigationContext,
    repository_id: str,
) -> ExplicitTarget:
    """Resolve a create target from the context or an explicit command target."""
    _require_live_context(context, repository_id)
    if isinstance(target, ExplicitTarget):
        if context.origin is ContextOrigin.QUESTION:
            raise RecordingValidationError(
                "a question context already binds its target; do not re-author it"
            )
        if context.origin is not ContextOrigin.EVIDENCE_ONLY:
            raise RecordingValidationError(
                "this context origin cannot create understanding"
            )
        if not _scopes_compatible(context.scope, target.scope):
            raise RecordingValidationError(
                "the explicit target is incompatible with the context evidence scope"
            )
        return target
    # Context-bound target.
    if context.origin is not ContextOrigin.QUESTION:
        raise RecordingValidationError(
            "only a question context supplies a bound semantic target"
        )
    if not context.question:
        raise RecordingValidationError("the question context has no bound question")
    return ExplicitTarget(question=context.question, scope=context.scope)


def _gap_values(
    drafts: tuple[GapDraft, ...],
) -> tuple[RecordedQuestionGap, ...]:
    return tuple(
        RecordedQuestionGap(question=item.question, basis=item.basis) for item in drafts
    )


def _supported_content(draft: ConclusionContentDraft) -> SupportedConclusion:
    return SupportedConclusion(
        statement=draft.statement,
        assertion_nature=draft.assertion_nature,
        scope=draft.scope,
        support=tuple(draft.support),
    )


def create_understanding(
    understanding_id: UnderstandingId,
    command: CreateUnderstandingCommand,
    context: InvestigationContext,
    now: _datetime.datetime,
    *,
    surface_boundary_version: int = 1,
) -> UnderstandingTransition:
    """Create version 1 from a closed create command."""
    repository_id = command.identity.repository_id
    target = resolve_create_target(command.target, context, repository_id)
    version_number = UnderstandingVersionNumber(1)
    revisions: list[ConclusionRevision] = []
    refs: list[ConclusionRevisionRef] = []
    lineages: set[ConclusionId] = set()
    for proposed in command.conclusions:
        if proposed.conclusion_id in lineages:
            raise RecordingValidationError("duplicate conclusion ID in create")
        lineages.add(proposed.conclusion_id)
        if not evidence_scope_contains(target.scope, proposed.scope):
            raise RecordingValidationError(
                "a conclusion scope lies outside the understanding scope"
            )
        revision = ConclusionRevision(
            understanding_id=understanding_id,
            conclusion_id=proposed.conclusion_id,
            revision=ConclusionRevisionNumber(1),
            originating_version=version_number,
            content=_supported_content(proposed),
            basis=proposed.basis,
        )
        revisions.append(revision)
        refs.append(
            ConclusionRevisionRef(
                understanding_id=understanding_id,
                conclusion_id=proposed.conclusion_id,
                revision=revision.revision,
            )
        )
    version = UnderstandingVersion(
        understanding_id=understanding_id,
        version=version_number,
        question=target.question,
        scope=target.scope,
        conclusions=tuple(refs),
        created_at=now,
        gaps=_gap_values(command.gaps),
        provenance=command.provenance,
        previous_version=None,
        surface_boundary_version=surface_boundary_version,
    )
    understanding = Understanding(
        understanding_id=understanding_id,
        repository_id=repository_id,
        surface=command.surface,
        question=target.question,
        scope=target.scope,
        current_version=version_number,
        created_at=now,
        provenance=command.provenance,
    )
    return UnderstandingTransition(
        understanding=understanding,
        new_version=version,
        new_conclusions=tuple(revisions),
        revision_effects=tuple(
            AcceptedRevisionEffect(
                RevisionEffectAction.CREATE, ref, True, CurationState.CAPTURED
            )
            for ref in refs
        ),
    )


def _latest_revisions(
    revisions: tuple[ConclusionRevision, ...],
) -> dict[ConclusionId, ConclusionRevisionNumber]:
    latest: dict[ConclusionId, ConclusionRevisionNumber] = {}
    for revision in revisions:
        current = latest.get(revision.conclusion_id)
        if current is None or revision.revision.value > current.value:
            latest[revision.conclusion_id] = revision.revision
    return latest


def _membership_refs(
    membership: tuple[ConclusionRevisionRef, ...],
) -> dict[ConclusionId, ConclusionRevisionRef]:
    return {ref.conclusion_id: ref for ref in membership}


def _replace_membership(
    membership: list[ConclusionRevisionRef],
    conclusion_id: ConclusionId,
    replacement: ConclusionRevisionRef | None,
) -> None:
    for index, ref in enumerate(membership):
        if ref.conclusion_id == conclusion_id:
            if replacement is None:
                membership.pop(index)
            else:
                membership[index] = replacement
            return
    if replacement is not None:
        membership.append(replacement)
    else:
        raise RecordingValidationError(
            f"conclusion is not in the current membership: {conclusion_id.value}"
        )


def _revision_for(
    understanding_id: UnderstandingId,
    conclusion_id: ConclusionId,
    revision_number: ConclusionRevisionNumber,
    version_number: UnderstandingVersionNumber,
    content: SupportedConclusion | WithdrawnConclusion,
    basis: SemanticBasis,
) -> ConclusionRevision:
    return ConclusionRevision(
        understanding_id=understanding_id,
        conclusion_id=conclusion_id,
        revision=revision_number,
        originating_version=version_number,
        content=content,
        basis=basis,
    )


def _require_current(
    by_lineage: dict[ConclusionId, ConclusionRevisionRef],
    conclusion_id: ConclusionId,
) -> ConclusionRevisionRef:
    ref = by_lineage.get(conclusion_id)
    if ref is None:
        raise RecordingValidationError(
            f"conclusion is not in the current version: {conclusion_id.value}"
        )
    return ref


def _next_revision(
    latest: dict[ConclusionId, ConclusionRevisionNumber],
    conclusion_id: ConclusionId,
) -> ConclusionRevisionNumber:
    current = latest.get(conclusion_id)
    return ConclusionRevisionNumber(1 if current is None else current.value + 1)


def _register_revision(
    *,
    understanding_id: UnderstandingId,
    conclusion_id: ConclusionId,
    revision: ConclusionRevision,
    by_lineage: dict[ConclusionId, ConclusionRevisionRef],
    latest: dict[ConclusionId, ConclusionRevisionNumber],
    revisions: list[ConclusionRevision],
) -> ConclusionRevisionRef:
    ref = ConclusionRevisionRef(
        understanding_id=understanding_id,
        conclusion_id=conclusion_id,
        revision=revision.revision,
    )
    by_lineage[conclusion_id] = ref
    latest[conclusion_id] = revision.revision
    revisions.append(revision)
    return ref


def _apply_action(
    action: object,
    *,
    understanding_id: UnderstandingId,
    version_number: UnderstandingVersionNumber,
    understanding_scope: EvidenceScope,
    membership: list[ConclusionRevisionRef],
    by_lineage: dict[ConclusionId, ConclusionRevisionRef],
    latest: dict[ConclusionId, ConclusionRevisionNumber],
    revisions: list[ConclusionRevision],
) -> tuple[ConclusionRevisionRef, RevisionEffectAction, ConclusionRevisionRef | None]:
    if isinstance(action, ProposedConclusion):
        conclusion_id = action.conclusion_id
        if conclusion_id in by_lineage or conclusion_id in latest:
            raise RecordingValidationError(
                f"conclusion lineage already exists: {conclusion_id.value}"
            )
        if not evidence_scope_contains(understanding_scope, action.scope):
            raise RecordingValidationError(
                "a conclusion scope lies outside the understanding scope"
            )
        revision = _revision_for(
            understanding_id,
            conclusion_id,
            ConclusionRevisionNumber(1),
            version_number,
            _supported_content(action),
            action.basis,
        )
        ref = _register_revision(
            understanding_id=understanding_id,
            conclusion_id=conclusion_id,
            revision=revision,
            by_lineage=by_lineage,
            latest=latest,
            revisions=revisions,
        )
        membership.append(ref)
        return ref, RevisionEffectAction.ADD, None
    if isinstance(action, (ConfirmConclusion, CorrectConclusion)):
        old_ref = _require_current(by_lineage, action.conclusion_id)
        if not evidence_scope_contains(understanding_scope, action.scope):
            raise RecordingValidationError(
                "a conclusion scope lies outside the understanding scope"
            )
        revision = _revision_for(
            understanding_id,
            action.conclusion_id,
            _next_revision(latest, action.conclusion_id),
            version_number,
            _supported_content(action),
            action.basis,
        )
        if old_ref.revision.value >= revision.revision.value:
            raise RecordingValidationError("conclusion revision did not advance")
        ref = _register_revision(
            understanding_id=understanding_id,
            conclusion_id=action.conclusion_id,
            revision=revision,
            by_lineage=by_lineage,
            latest=latest,
            revisions=revisions,
        )
        _replace_membership(membership, action.conclusion_id, ref)
        kind = (
            RevisionEffectAction.CONFIRM
            if isinstance(action, ConfirmConclusion)
            else RevisionEffectAction.CORRECT
        )
        return ref, kind, None
    if isinstance(action, ReplaceConclusion):
        old_current = _require_current(by_lineage, action.old.conclusion_id)
        if action.old != old_current:
            raise RecordingValidationError(
                "the replacement does not name the current conclusion revision"
            )
        if action.new_conclusion_id in by_lineage or action.new_conclusion_id in latest:
            raise RecordingValidationError(
                "replacement introduces an existing conclusion lineage"
            )
        if not evidence_scope_contains(understanding_scope, action.scope):
            raise RecordingValidationError(
                "a conclusion scope lies outside the understanding scope"
            )
        revision = _revision_for(
            understanding_id,
            action.new_conclusion_id,
            ConclusionRevisionNumber(1),
            version_number,
            _supported_content(action),
            action.replacement_basis,
        )
        ref = _register_revision(
            understanding_id=understanding_id,
            conclusion_id=action.new_conclusion_id,
            revision=revision,
            by_lineage=by_lineage,
            latest=latest,
            revisions=revisions,
        )
        membership[:] = [
            item
            for item in membership
            if item.conclusion_id != action.old.conclusion_id
        ]
        membership.append(ref)
        by_lineage.pop(action.old.conclusion_id, None)
        return ref, RevisionEffectAction.REPLACE, action.old
    if isinstance(action, WithdrawConclusion):
        _require_current(by_lineage, action.conclusion_id)
        revision = _revision_for(
            understanding_id,
            action.conclusion_id,
            _next_revision(latest, action.conclusion_id),
            version_number,
            WithdrawnConclusion(
                reason=action.basis.summary,
                support=tuple(action.support),
            ),
            action.basis,
        )
        ref = _register_revision(
            understanding_id=understanding_id,
            conclusion_id=action.conclusion_id,
            revision=revision,
            by_lineage=by_lineage,
            latest=latest,
            revisions=revisions,
        )
        _replace_membership(membership, action.conclusion_id, ref)
        return ref, RevisionEffectAction.WITHDRAW, None
    raise RecordingValidationError(
        f"unhandled conclusion action: {type(action).__name__}"
    )


def _curation_effects(
    current_version: UnderstandingVersion,
    new_version: UnderstandingVersion,
    command: UpdateUnderstandingCommand,
    existing_curations: tuple[CurationDisposition, ...],
    now: _datetime.datetime,
) -> tuple[CurationDisposition, ...]:
    """Derive exact immutable curation effects from one accepted update."""
    prior_by_lineage = {ref.conclusion_id: ref for ref in current_version.conclusions}
    resulting_by_lineage = {ref.conclusion_id: ref for ref in new_version.conclusions}
    curated = {item.ref: item for item in existing_curations}
    effects: list[CurationDisposition] = []

    for curate_action in command.curate:
        ref = prior_by_lineage.get(curate_action.conclusion_id)
        if ref is None:
            raise RecordingValidationError(
                "curation target is not in the current understanding version: "
                f"{curate_action.conclusion_id.value}"
            )
        if ref in curated:
            raise RecordingValidationError(
                "curation target is already curated: "
                f"{curate_action.conclusion_id.value}@{ref.revision.value}"
            )
        effects.append(
            CurationDisposition(
                ref=ref,
                accepted_in_version=new_version.version,
                reasoning=curate_action.reasoning,
                provenance=command.provenance,
                recorded_at=now,
                origin=CurationOrigin.EXPLICIT,
            )
        )

    for confirm_action in command.confirm:
        predecessor = prior_by_lineage.get(confirm_action.conclusion_id)
        if predecessor is None:
            raise RecordingValidationError(
                "confirm target is not in the current understanding version: "
                f"{confirm_action.conclusion_id.value}"
            )
        prior_curation = curated.get(predecessor)
        if prior_curation is None:
            continue
        successor = resulting_by_lineage.get(confirm_action.conclusion_id)
        if successor is None:
            raise RecordingValidationError(
                "confirmed curated conclusion is missing from resulting membership"
            )
        if successor == predecessor:
            continue
        effects.append(
            CurationDisposition(
                ref=successor,
                accepted_in_version=new_version.version,
                reasoning=prior_curation.reasoning,
                provenance=prior_curation.provenance,
                recorded_at=now,
                origin=CurationOrigin.INHERITED_CONFIRMATION,
                inherited_from=predecessor,
            )
        )

    return tuple(effects)


def _accepted_revision_effects(
    actions: list[
        tuple[ConclusionRevisionRef, RevisionEffectAction, ConclusionRevisionRef | None]
    ],
    curations: tuple[CurationDisposition, ...],
    unchanged: frozenset[ConclusionRevisionRef],
    prior_curations: tuple[CurationDisposition, ...],
) -> tuple[AcceptedRevisionEffect, ...]:
    curated = {item.ref for item in (*prior_curations, *curations)}
    effects = [
        AcceptedRevisionEffect(
            action=action,
            ref=ref,
            changed=ref not in unchanged,
            maturity=(
                None
                if action is RevisionEffectAction.WITHDRAW
                else (
                    CurationState.CURATED if ref in curated else CurationState.CAPTURED
                )
            ),
            replaced_ref=replaced,
        )
        for ref, action, replaced in actions
    ]
    effects.extend(
        AcceptedRevisionEffect(
            RevisionEffectAction.CURATE, item.ref, True, CurationState.CURATED
        )
        for item in curations
        if item.origin is CurationOrigin.EXPLICIT
    )
    return tuple(effects)


def _unchanged_confirmations(
    command: UpdateUnderstandingCommand,
    version: UnderstandingVersion,
    revisions: tuple[ConclusionRevision, ...],
    current: frozenset[ConclusionRevisionRef],
) -> frozenset[ConclusionRevisionRef]:
    """FD-31: consume evaluated currency, never infer it from unchanged wording."""
    by_lineage = _membership_refs(version.conclusions)
    by_ref = {
        (revision.conclusion_id, revision.revision.value): revision
        for revision in revisions
    }
    unchanged: set[ConclusionRevisionRef] = set()
    for action in command.confirm:
        ref = _require_current(by_lineage, action.conclusion_id)
        content = by_ref[(ref.conclusion_id, ref.revision.value)].content
        if not isinstance(content, SupportedConclusion):
            raise RecordingValidationError("confirm requires a supported predecessor")
        if (
            content.statement != action.statement
            or content.assertion_nature != action.assertion_nature
            or content.scope != action.scope
        ):
            raise RecordingValidationError(
                "changed conclusion content requires correct"
            )
        if ref in current and content.support == action.support:
            unchanged.add(ref)
    return frozenset(unchanged)


def apply_update(
    current_understanding: Understanding,
    current_version: UnderstandingVersion,
    existing_conclusions: tuple[ConclusionRevision, ...],
    command: UpdateUnderstandingCommand,
    context: InvestigationContext,
    now: _datetime.datetime,
    *,
    existing_challenges: tuple[Challenge, ...] = (),
    existing_curations: tuple[CurationDisposition, ...] = (),
    current_confirmations: frozenset[ConclusionRevisionRef] = frozenset(),
) -> UnderstandingTransition:
    """Apply one closed update to the current version, or reject atomically."""
    repository_id = command.identity.repository_id
    _require_live_context(context, repository_id)
    if current_understanding.understanding_id != command.understanding_id:
        raise RecordingValidationError("the selected understanding does not match")
    if current_version.understanding_id != command.understanding_id:
        raise RecordingValidationError("the current version belongs elsewhere")
    if command.expected_version != current_version.version:
        raise RecordingConflict(
            "expected understanding version "
            f"{command.expected_version.value} does not match current "
            f"{current_version.version.value}",
            current_version=current_version.version.value,
        )
    if not _scopes_compatible(context.scope, current_version.scope):
        raise RecordingValidationError(
            "the context evidence scope is incompatible with this understanding"
        )
    by_ref = {
        (revision.conclusion_id, revision.revision.value): revision
        for revision in existing_conclusions
    }
    for ref in current_version.conclusions:
        if (ref.conclusion_id, ref.revision.value) not in by_ref:
            raise RecordingValidationError(
                f"current conclusion revision is missing: {ref.conclusion_id.value}"
            )
    latest = _latest_revisions(existing_conclusions)
    membership = list(current_version.conclusions)
    by_lineage = _membership_refs(current_version.conclusions)
    new_version_number = UnderstandingVersionNumber(current_version.version.value + 1)
    revisions: list[ConclusionRevision] = []
    actions = (
        command.add
        + command.confirm
        + command.correct
        + command.replace
        + command.withdraw
    )
    unchanged = _unchanged_confirmations(
        command, current_version, existing_conclusions, current_confirmations
    )
    accepted: list[
        tuple[ConclusionRevisionRef, RevisionEffectAction, ConclusionRevisionRef | None]
    ] = []
    for action in actions:
        if isinstance(action, ConfirmConclusion):
            ref = _require_current(by_lineage, action.conclusion_id)
            if ref in unchanged:
                accepted.append((ref, RevisionEffectAction.CONFIRM, None))
                continue
        accepted.append(
            _apply_action(
                action,
                understanding_id=current_understanding.understanding_id,
                version_number=new_version_number,
                understanding_scope=current_version.scope,
                membership=membership,
                by_lineage=by_lineage,
                latest=latest,
                revisions=revisions,
            )
        )
    if not revisions and not (
        command.curate or command.challenge_dispositions or command.gaps is not None
    ):
        return UnderstandingTransition(
            understanding=current_understanding,
            new_version=current_version,
            new_conclusions=(),
            revision_effects=_accepted_revision_effects(
                accepted, (), unchanged, existing_curations
            ),
        )
    gaps = current_version.gaps if command.gaps is None else _gap_values(command.gaps)
    new_version = UnderstandingVersion(
        understanding_id=current_understanding.understanding_id,
        version=new_version_number,
        question=current_version.question,
        scope=current_version.scope,
        conclusions=tuple(membership),
        created_at=now,
        gaps=gaps,
        provenance=command.provenance,
        previous_version=current_version.version,
        surface_boundary_version=current_version.surface_boundary_version,
    )
    updated_understanding = Understanding(
        understanding_id=current_understanding.understanding_id,
        repository_id=current_understanding.repository_id,
        surface=current_understanding.surface,
        question=current_understanding.question,
        scope=current_understanding.scope,
        current_version=new_version_number,
        created_at=current_understanding.created_at,
        provenance=current_understanding.provenance,
    )
    curations = _curation_effects(
        current_version,
        new_version,
        command,
        existing_curations,
        now,
    )
    effects = apply_challenge_dispositions(
        existing_challenges=existing_challenges,
        dispositions=command.challenge_dispositions,
        resulting_understanding_id=current_understanding.understanding_id,
        resulting_understanding=new_version,
        known_revisions=(*existing_conclusions, *revisions),
        actions=actions,
        now=now,
    )
    return UnderstandingTransition(
        understanding=updated_understanding,
        new_version=new_version,
        new_conclusions=tuple(revisions),
        challenge_effects=effects,
        curations=curations,
        revision_effects=_accepted_revision_effects(
            accepted, curations, unchanged, existing_curations
        ),
    )


def _resolved_challenge_effect(
    challenge: Challenge,
    disposition: ResolvedChallengeDisposition,
    new_revision: ChallengeRevision,
    resulting_understanding: UnderstandingVersion,
    by_revision: dict[tuple[ConclusionId, int], ConclusionRevision],
    actions: tuple[
        ProposedConclusion
        | ConfirmConclusion
        | CorrectConclusion
        | ReplaceConclusion
        | WithdrawConclusion,
        ...,
    ],
    now: _datetime.datetime,
) -> ChallengeEffect:
    """Derive one resolved challenge entirely from the resulting atomic state."""
    replacement_by_old: dict[ConclusionId, ConclusionId] = {}
    for action in actions:
        if not isinstance(action, ReplaceConclusion):
            continue
        if action.old.conclusion_id in replacement_by_old:
            raise RecordingValidationError(
                "challenge resolution replacement mapping is ambiguous"
            )
        replacement_by_old[action.old.conclusion_id] = action.new_conclusion_id

    target_ids = (
        disposition.target_conclusion_ids
        if disposition.target_conclusion_ids
        else tuple(ref.conclusion_id for ref in challenge.target_conclusions)
    )
    if len(set(target_ids)) != len(target_ids):
        raise RecordingValidationError(
            "a challenge resolution names one conclusion lineage twice"
        )
    membership_by_id = {
        ref.conclusion_id: ref for ref in resulting_understanding.conclusions
    }
    conclusions: list[ConclusionRevisionRef] = []
    withdrawn: list[ConclusionRevisionRef] = []
    resolved_ids: set[ConclusionId] = set()
    for target_id in target_ids:
        resolved_id = target_id
        if resolved_id not in membership_by_id:
            replacement = replacement_by_old.get(target_id)
            if replacement is None:
                raise RecordingValidationError(
                    "challenge resolution target does not identify a "
                    f"resulting conclusion: {target_id.value}"
                )
            resolved_id = replacement
        if resolved_id in resolved_ids:
            raise RecordingValidationError(
                "challenge resolution targets collapse to one resulting "
                f"conclusion: {resolved_id.value}"
            )
        resolved_ids.add(resolved_id)
        ref = membership_by_id.get(resolved_id)
        if ref is None:
            raise RecordingValidationError(
                "challenge resolution replacement is not in the "
                f"resulting membership: {resolved_id.value}"
            )
        revision = by_revision.get((ref.conclusion_id, ref.revision.value))
        if revision is None:
            raise RecordingValidationError(
                "challenge resolution resulting revision is missing: "
                f"{ref.conclusion_id.value}@{ref.revision.value}"
            )
        if isinstance(revision.content, WithdrawnConclusion):
            withdrawn.append(ref)
        else:
            conclusions.append(ref)

    resolution = ChallengeResolution(
        facts=ChallengeResolutionFacts(
            reasoning=disposition.reasoning,
            resulting_understanding_id=resulting_understanding.understanding_id,
            resulting_version=resulting_understanding.version,
        ),
        conclusions=tuple(conclusions),
        withdrawn=tuple(withdrawn),
        evidence=disposition.evidence,
    )
    record = ResolvedChallengeRecord(
        decision=ChallengeDispositionDecision(
            challenge_revision=new_revision,
            recorded_at=now,
        ),
        resolution=resolution,
    )
    return ChallengeEffect(
        challenge_id=challenge.facts.challenge_id,
        previous_revision=challenge.facts.challenge_revision,
        new_revision=new_revision,
        state=ChallengeState.RESOLVED,
        disposition=record,
        resolution=resolution,
    )


def apply_challenge_dispositions(
    *,
    existing_challenges: tuple[Challenge, ...],
    dispositions: tuple[ChallengeDisposition, ...],
    resulting_understanding_id: UnderstandingId,
    resulting_understanding: UnderstandingVersion,
    known_revisions: tuple[ConclusionRevision, ...],
    actions: tuple[
        ProposedConclusion
        | ConfirmConclusion
        | CorrectConclusion
        | ReplaceConclusion
        | WithdrawConclusion,
        ...,
    ],
    now: _datetime.datetime,
) -> tuple[ChallengeEffect, ...]:
    """Validate and apply only explicitly addressed challenge dispositions."""
    by_id = {challenge.facts.challenge_id: challenge for challenge in existing_challenges}
    by_revision = {
        (item.conclusion_id, item.revision.value): item for item in known_revisions
    }
    seen: set[ChallengeId] = set()
    effects: list[ChallengeEffect] = []
    for disposition in dispositions:
        if disposition.challenge_id in seen:
            raise RecordingValidationError("duplicate challenge ID in one command")
        seen.add(disposition.challenge_id)
        challenge = by_id.get(disposition.challenge_id)
        if challenge is None:
            raise RecordingValidationError(
                f"unknown challenge: {disposition.challenge_id.value}"
            )
        if challenge.facts.understanding_id != resulting_understanding_id:
            raise RecordingValidationError(
                "challenge targets a different understanding"
            )
        if challenge.facts.challenge_revision != disposition.expected_challenge_revision:
            raise RecordingConflict(
                "challenge revision "
                f"{disposition.expected_challenge_revision.value} does not match "
                f"current {challenge.facts.challenge_revision.value}",
                current_version=challenge.facts.challenge_revision.value,
            )
        new_revision = ChallengeRevision(challenge.facts.challenge_revision.value + 1)
        record: ChallengeDispositionRecord
        if isinstance(disposition, UnresolvedChallengeDisposition):
            record = UnresolvedChallengeRecord(
                challenge_revision=new_revision,
                remaining_question=disposition.remaining_question,
                basis=disposition.basis,
                recorded_at=now,
            )
            effects.append(
                ChallengeEffect(
                    challenge_id=challenge.facts.challenge_id,
                    previous_revision=challenge.facts.challenge_revision,
                    new_revision=new_revision,
                    state=ChallengeState.UNRESOLVED,
                    disposition=record,
                )
            )
            continue
        if isinstance(disposition, ResolvedChallengeDisposition):
            effects.append(
                _resolved_challenge_effect(
                    challenge,
                    disposition,
                    new_revision,
                    resulting_understanding,
                    by_revision,
                    actions,
                    now,
                )
            )
            continue
        raise RecordingValidationError(
            f"unhandled challenge disposition: {type(disposition).__name__}"
        )
    return tuple(effects)


def create_challenge(
    *,
    challenge_id: ChallengeId,
    understanding_id: UnderstandingId,
    target_version: UnderstandingVersionNumber,
    target_conclusions: tuple[ConclusionRevisionRef, ...],
    reason: str,
    evidence: tuple[EvidenceRef, ...],
    provenance: str,
    now: _datetime.datetime,
) -> Challenge:
    """Create one explicit dispute at its initial revision (1)."""
    return Challenge(
        facts=ChallengeFacts(
            challenge_id=challenge_id,
            understanding_id=understanding_id,
            target_version=target_version,
            reason=reason,
            provenance=provenance,
            challenge_revision=ChallengeRevision(1),
            state=ChallengeState.OPEN,
            created_at=now,
        ),
        target_conclusions=target_conclusions,
        evidence=tuple(evidence),
    )
