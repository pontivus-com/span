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
)
from span.core.model.primitives import (
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
    VerificationRunId,
    evidence_scope_allows,
)
from span.core.model.recording import (
    ContentDigest,
    ReceiptDecision,
    ReceiptDecisionKind,
    RecordReceipt,
    RecordingIdentity,
)
from span.core.model.understanding import (
    Challenge,
    ChallengeDispositionRecord,
    ChallengeResolution,
    ChallengeState,
    ResolvedChallengeRecord,
    UnresolvedChallengeRecord,
    ConclusionRevision,
    Gap,
    SupportedConclusion,
    Understanding,
    UnderstandingVersion,
    WithdrawnConclusion,
)


class RecordingConflict(ValueError):
    """A compare-and-set, receipt, or challenge revision conflict."""


class RecordingValidationError(ValueError):
    """The command/context content cannot be accepted as submitted."""


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


def receipt_decision(
    existing: RecordReceipt | None,
    identity: RecordingIdentity,
    digest: ContentDigest,
) -> ReceiptDecision:
    """Receipt-first decision for one recording key/content pair."""
    if existing is None:
        return ReceiptDecision(ReceiptDecisionKind.NEW)
    if existing.identity != identity:
        raise RecordingConflict("receipt identity does not match the recording key")
    if existing.content_digest == digest:
        return ReceiptDecision(ReceiptDecisionKind.REPLAY, receipt=existing)
    return ReceiptDecision(
        ReceiptDecisionKind.CONFLICT,
        receipt=existing,
        reason="this submission identity already committed different content",
    )


def build_receipt(
    identity: RecordingIdentity,
    digest: ContentDigest,
    committed_at: _datetime.datetime,
    *,
    understanding: tuple[UnderstandingId, UnderstandingVersionNumber] | None = None,
    verification_run_id: VerificationRunId | None = None,
    challenge_id: ChallengeId | None = None,
    replay_expires_at: _datetime.datetime | None = None,
) -> RecordReceipt:
    """Build the immutable receipt for one accepted effect."""
    understanding_ids: tuple[UnderstandingId, ...] = ()
    understanding_versions: tuple[UnderstandingVersionNumber, ...] = ()
    verification_ids: tuple[VerificationRunId, ...] = ()
    challenge_ids: tuple[ChallengeId, ...] = ()
    if understanding is not None:
        understanding_ids = (understanding[0],)
        understanding_versions = (understanding[1],)
    if verification_run_id is not None:
        verification_ids = (verification_run_id,)
    if challenge_id is not None:
        challenge_ids = (challenge_id,)
    return RecordReceipt(
        identity=identity,
        content_digest=digest,
        committed_at=committed_at,
        accepted_understanding_ids=understanding_ids,
        accepted_understanding_versions=understanding_versions,
        accepted_verification_run_ids=verification_ids,
        accepted_challenge_ids=challenge_ids,
        replay_expires_at=replay_expires_at,
    )


def _scope_contains(outer: EvidenceScope, inner: EvidenceScope) -> bool:
    """Whether one declared scope is wholly inside another.

    An empty scope means the whole repository. Paths are prefixes; evidence
    references are exact locators. This is a deterministic boundary check,
    not an inferred semantic relationship.
    """
    if not outer.paths and not outer.evidence_refs:
        return True
    for path in inner.paths:
        if not evidence_scope_allows(path, outer):
            return False
    for ref in inner.evidence_refs:
        if not evidence_scope_allows(ref.locator, outer):
            return False
    return True


def _scopes_compatible(left: EvidenceScope, right: EvidenceScope) -> bool:
    return _scope_contains(left, right) or _scope_contains(right, left)


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


def _gap_values(drafts: tuple[GapDraft, ...]) -> tuple[Gap, ...]:
    return tuple(Gap(question=item.question, basis=item.basis) for item in drafts)


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
        if not _scope_contains(target.scope, proposed.scope):
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
    )
    understanding = Understanding(
        understanding_id=understanding_id,
        repository_id=repository_id,
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
) -> None:
    if isinstance(action, ProposedConclusion):
        conclusion_id = action.conclusion_id
        if conclusion_id in by_lineage or conclusion_id in latest:
            raise RecordingValidationError(
                f"conclusion lineage already exists: {conclusion_id.value}"
            )
        if not _scope_contains(understanding_scope, action.scope):
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
        return
    if isinstance(action, (ConfirmConclusion, CorrectConclusion)):
        old_ref = _require_current(by_lineage, action.conclusion_id)
        if not _scope_contains(understanding_scope, action.scope):
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
        return
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
        if not _scope_contains(understanding_scope, action.scope):
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
        return
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
        return
    raise RecordingValidationError(
        f"unhandled conclusion action: {type(action).__name__}"
    )


def apply_update(
    current_understanding: Understanding,
    current_version: UnderstandingVersion,
    existing_conclusions: tuple[ConclusionRevision, ...],
    command: UpdateUnderstandingCommand,
    context: InvestigationContext,
    now: _datetime.datetime,
    *,
    existing_challenges: tuple[Challenge, ...] = (),
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
            f"{current_version.version.value}"
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
    for action in actions:
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
    )
    updated_understanding = Understanding(
        understanding_id=current_understanding.understanding_id,
        repository_id=current_understanding.repository_id,
        question=current_understanding.question,
        scope=current_understanding.scope,
        current_version=new_version_number,
        created_at=current_understanding.created_at,
        provenance=current_understanding.provenance,
    )
    effects = apply_challenge_dispositions(
        existing_challenges=existing_challenges,
        dispositions=command.challenge_dispositions,
        resulting_understanding_id=current_understanding.understanding_id,
        resulting_understanding=new_version,
        known_revisions=(*existing_conclusions, *revisions),
        now=now,
    )
    return UnderstandingTransition(
        understanding=updated_understanding,
        new_version=new_version,
        new_conclusions=tuple(revisions),
        challenge_effects=effects,
    )


def apply_challenge_dispositions(
    *,
    existing_challenges: tuple[Challenge, ...],
    dispositions: tuple[ChallengeDisposition, ...],
    resulting_understanding_id: UnderstandingId,
    resulting_understanding: UnderstandingVersion,
    known_revisions: tuple[ConclusionRevision, ...],
    now: _datetime.datetime,
) -> tuple[ChallengeEffect, ...]:
    """Validate and apply only explicitly addressed challenge dispositions."""
    by_id = {challenge.challenge_id: challenge for challenge in existing_challenges}
    by_revision = {
        (item.conclusion_id, item.revision.value): item for item in known_revisions
    }
    membership = {
        (ref.conclusion_id, ref.revision.value)
        for ref in resulting_understanding.conclusions
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
        if challenge.understanding_id != resulting_understanding_id:
            raise RecordingValidationError(
                "challenge targets a different understanding"
            )
        if challenge.challenge_revision != disposition.expected_challenge_revision:
            raise RecordingConflict(
                "challenge revision "
                f"{disposition.expected_challenge_revision.value} does not match "
                f"current {challenge.challenge_revision.value}"
            )
        new_revision = ChallengeRevision(challenge.challenge_revision.value + 1)
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
                    challenge_id=challenge.challenge_id,
                    previous_revision=challenge.challenge_revision,
                    new_revision=new_revision,
                    state=ChallengeState.UNRESOLVED,
                    disposition=record,
                )
            )
            continue
        if isinstance(disposition, ResolvedChallengeDisposition):
            if disposition.resulting_understanding_id != resulting_understanding_id:
                raise RecordingValidationError(
                    "a resolution must name the resulting understanding"
                )
            if (
                disposition.resulting_version.value
                != resulting_understanding.version.value
            ):
                raise RecordingValidationError(
                    "a resolution must name the new understanding version"
                )
            cited: set[tuple[ConclusionId, int]] = set()
            for ref in disposition.conclusions:
                cited.add(
                    _resolution_target(
                        ref,
                        understanding_id=resulting_understanding_id,
                        membership=membership,
                        by_revision=by_revision,
                        withdrawn=False,
                    )
                )
            for ref in disposition.withdrawn:
                cited.add(
                    _resolution_target(
                        ref,
                        understanding_id=resulting_understanding_id,
                        membership=membership,
                        by_revision=by_revision,
                        withdrawn=True,
                    )
                )
            if len(cited) != len(disposition.conclusions) + len(disposition.withdrawn):
                raise RecordingValidationError(
                    "a resolution cites one conclusion revision twice"
                )
            resolution = ChallengeResolution(
                reasoning=disposition.reasoning,
                resulting_understanding_id=disposition.resulting_understanding_id,
                resulting_version=disposition.resulting_version,
                conclusions=disposition.conclusions,
                withdrawn=disposition.withdrawn,
                evidence=disposition.evidence,
            )
            record = ResolvedChallengeRecord(
                challenge_revision=new_revision,
                resolution=resolution,
                recorded_at=now,
            )
            effects.append(
                ChallengeEffect(
                    challenge_id=challenge.challenge_id,
                    previous_revision=challenge.challenge_revision,
                    new_revision=new_revision,
                    state=ChallengeState.RESOLVED,
                    disposition=record,
                    resolution=resolution,
                )
            )
            continue
        raise RecordingValidationError(
            f"unhandled challenge disposition: {type(disposition).__name__}"
        )
    return tuple(effects)


def _resolution_target(
    ref: ConclusionRevisionRef,
    *,
    understanding_id: UnderstandingId,
    membership: set[tuple[ConclusionId, int]],
    by_revision: dict[tuple[ConclusionId, int], ConclusionRevision],
    withdrawn: bool,
) -> tuple[ConclusionId, int]:
    """Validate one resolution target against the resulting snapshot."""
    if ref.understanding_id != understanding_id:
        raise RecordingValidationError(
            "a challenge resolution cites another understanding"
        )
    key = (ref.conclusion_id, ref.revision.value)
    if key not in by_revision:
        raise RecordingValidationError(
            "a challenge resolution cites a revision that does not exist: "
            f"{ref.conclusion_id.value}@{ref.revision.value}"
        )
    if key not in membership:
        raise RecordingValidationError(
            "a challenge resolution cites a revision outside the resulting "
            f"version: {ref.conclusion_id.value}@{ref.revision.value}"
        )
    content = by_revision[key].content
    if withdrawn and not isinstance(content, WithdrawnConclusion):
        raise RecordingValidationError(
            "a withdrawn resolution target is not withdrawn: "
            f"{ref.conclusion_id.value}@{ref.revision.value}"
        )
    if not withdrawn and isinstance(content, WithdrawnConclusion):
        raise RecordingValidationError(
            "a concluded resolution target is withdrawn: "
            f"{ref.conclusion_id.value}@{ref.revision.value}"
        )
    return key


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
        challenge_id=challenge_id,
        understanding_id=understanding_id,
        target_version=target_version,
        target_conclusions=target_conclusions,
        reason=reason,
        evidence=tuple(evidence),
        provenance=provenance,
        challenge_revision=ChallengeRevision(1),
        state=ChallengeState.OPEN,
        created_at=now,
    )
