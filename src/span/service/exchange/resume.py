"""Dispatch a committed submission to the owning operation's composer."""

from __future__ import annotations

from span.core import model as m
from span.core import requirements as _requirements
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort
from span.core.continuations import RefreshSnapshot, SuspendedOperation

from span.service.establishment import (
    _Establishment,
    _next_establishment_pending,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.operations.authority import (
    _compose_authority_answer,
)
from span.service.operations.explain import (
    _compose_explain_answer,
)
from span.service.operations.impact import (
    _compose_impact_answer,
)
from span.service.operations.initialize_target import (
    _next_target_pending,
)
from span.service.operations.refresh import (
    _compose_refresh_answer,
)
from span.service.operations.trace import (
    _resume_trace,
)
from span.service.questions import (
    _stale_question_scopes,
)
from span.service.requests import (
    ChangeKind,
)

from span.service.exchange.identity import _question_key
from span.service.exchange.prepare import _PreparedSubmission


def _resume_initialize_target(
    record: SuspendedOperation,
    prepared: _PreparedSubmission,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> m.SemanticAnswer | PendingInterpretation:
    """Resume an initialize_target run across its remaining suspended units."""
    bounds = record.bounds
    if prepared.target.target_id is not None:
        return _next_target_pending(
            record.repository_id,
            record.remaining,
            record.scope,
            objective=record.objective,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=prepared.state,
            authority_seeds=record.seeds,
            continuations=continuations,
            target_scope=record.target_scope,
            target_id=record.target_id,
        )
    establishment = _Establishment(
        op="initialize_target",
        repository_id=record.repository_id,
        root=record.subject,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=prepared.state,
        seeds=record.seeds,
        continuations=continuations,
        scope=record.scope,
        remaining=record.remaining,
        objective=record.objective,
        target_scope=record.target_scope,
        target_id=record.target_id,
    )
    pending = _next_establishment_pending(establishment)
    if pending is not None:
        return pending
    return _next_target_pending(
        record.repository_id,
        record.remaining,
        record.scope,
        objective=record.objective,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=prepared.state,
        authority_seeds=record.seeds,
        continuations=continuations,
        target_scope=record.target_scope,
        target_id=record.target_id,
    )


def _deferred_refresh_requirements(
    deferred: tuple[m.SemanticQuestionScope, ...],
) -> tuple[m.ResolutionRequirement, ...]:
    """Name questions that became eligible after this chain's snapshot."""
    return tuple(
        _requirements.missing_semantic_coverage(
            subject_or_claim=question.subject,
            description=(
                f"{question.question_class.value} '{question.question_slice}' "
                f"for '{question.subject.canonical_locator}' appeared after "
                "this refresh snapshot was taken and was deferred; run refresh "
                "again to examine it"
            ),
            supporting_context=(),
        )
        for question in deferred
    )


def _suspend_refresh_scope(
    record: SuspendedOperation,
    prepared: _PreparedSubmission,
    *,
    subject: m.Subject,
    scope: m.SemanticQuestionScope | None,
    remaining: tuple[m.Subject, ...],
    snapshot: RefreshSnapshot,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> PendingInterpretation:
    """Suspend one refresh unit under the persisted question identity."""
    bounds = record.bounds
    task = prepare_interpretation_task(
        record.repository_id,
        subject,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=prepared.state,
        authority_seeds=record.seeds,
        operation_intent=m.SemanticIntent.STATUS,
        question_slice=(
            scope.question_slice
            if scope is not None
            else subject.subject_id.canonical_locator
        ),
        store=store,
        scope_root=(scope.scope_root if scope is not None else subject.subject_id),
        question_class=(scope.question_class if scope is not None else None),
        materiality_basis=(scope.materiality_basis if scope is not None else ""),
    )
    return _suspend(
        op="refresh",
        repository_id=record.repository_id,
        subject=subject,
        task=task,
        seeds=record.seeds,
        bounds=bounds,
        state=prepared.state,
        resolution=None,
        scope=record.scope,
        remaining=remaining,
        changed=record.changed,
        continuations=continuations,
        operation_intent="STATUS",
        question_slice=task.request.question_slice,
        refresh=snapshot,
    )


def _resume_refresh_cycle(
    record: SuspendedOperation,
    prepared: _PreparedSubmission,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> m.SemanticAnswer | PendingInterpretation:
    """Drain one finite per-subject snapshot, then advance or answer.

    The snapshot is fixed when the chain reaches a subject. Each submission
    marks its bound question attempted, so a repeated ``PENDING`` cannot
    re-attempt it. A question that appears after the snapshot is deferred and
    named in the final answer, never attempted in this chain.
    """
    bounds = record.bounds
    snapshot = record.refresh or RefreshSnapshot()
    submitted = record.request.question
    attempted = snapshot.attempted
    if submitted is not None and submitted not in attempted:
        attempted = attempted + (submitted,)
    current = _stale_question_scopes(
        record.repository_id,
        record.subject,
        store=store,
        evidence=evidence,
        bounds=bounds,
        suspended=continuations.live_question_keys(),
    )
    eligible = set(snapshot.eligible)
    deferred = tuple(question for question in current if question not in eligible)
    deferred_all = tuple(dict.fromkeys(snapshot.deferred + deferred))
    next_scope = next(
        (
            question
            for question in current
            if question in eligible and question not in attempted
        ),
        None,
    )
    if next_scope is not None:
        return _suspend_refresh_scope(
            record,
            prepared,
            subject=record.subject,
            scope=next_scope,
            remaining=record.remaining,
            snapshot=RefreshSnapshot(
                eligible=snapshot.eligible,
                attempted=attempted + (next_scope,),
                deferred=deferred_all,
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    if record.remaining:
        subject, rest = record.remaining[0], record.remaining[1:]
        current = _stale_question_scopes(
            record.repository_id,
            subject,
            store=store,
            evidence=evidence,
            bounds=bounds,
            suspended=continuations.live_question_keys(),
        )
        next_scope = current[0] if current else None
        return _suspend_refresh_scope(
            record,
            prepared,
            subject=subject,
            scope=next_scope,
            remaining=rest,
            snapshot=RefreshSnapshot(
                eligible=tuple(current),
                attempted=(next_scope,) if next_scope is not None else (),
                deferred=deferred_all,
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    return _compose_refresh_answer(
        record.repository_id,
        record.scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=prepared.state,
        changed=record.changed,
        extra_unresolved=_deferred_refresh_requirements(deferred_all),
    )


def _resume_explain(
    record: SuspendedOperation,
    prepared: _PreparedSubmission,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> m.SemanticAnswer | PendingInterpretation:
    """Resume an explain run, suspending its next baseline unit if any."""
    bounds = record.bounds
    if record.establish_baseline:
        establishment = _Establishment(
            op="explain",
            repository_id=record.repository_id,
            root=record.subject,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=prepared.state,
            seeds=record.seeds,
            continuations=continuations,
            resolution=record.resolution,
        )
        pending = _next_establishment_pending(establishment)
        if pending is not None:
            return pending
    return _compose_explain_answer(
        record.repository_id,
        record.subject,
        record.resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=prepared.state,
        scope_root=record.subject.subject_id,
        question_key=_question_key(record.request.question),
    )


def _resume_authority(
    record: SuspendedOperation,
    prepared: _PreparedSubmission,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> m.SemanticAnswer:
    """Resume an authority run by composing its answer."""
    return _compose_authority_answer(
        record.repository_id,
        record.subject,
        record.resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=record.bounds,
        state=prepared.state,
        question_key=_question_key(record.request.question),
    )


def _resume_impact(
    record: SuspendedOperation,
    prepared: _PreparedSubmission,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> m.SemanticAnswer | PendingInterpretation:
    """Resume an impact run with its accumulated suspended subjects."""
    target = record.scope[0] if record.scope else record.subject
    suspended = record.suspended
    if record.subject.subject_id not in suspended:
        suspended = suspended + (record.subject.subject_id,)
    return _compose_impact_answer(
        record.repository_id,
        target,
        record.resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=record.bounds,
        state=prepared.state,
        change_kind=(
            ChangeKind(record.change_kind)
            if record.change_kind is not None
            else ChangeKind.BEHAVIOR
        ),
        change_description=record.change_description,
        affected_assertions=record.affected_assertions,
        seeds=record.seeds,
        suspended=suspended,
        continuations=continuations,
        question_selection=record.question_selection,
        root_question=record.root_question,
    )


def _resume_operation(
    record: SuspendedOperation,
    prepared: _PreparedSubmission,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> m.SemanticAnswer | PendingInterpretation:
    """Dispatch a committed submission to the owning operation's composer."""
    if record.op == "initialize_target":
        return _resume_initialize_target(
            record,
            prepared,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    if record.op == "refresh":
        return _resume_refresh_cycle(
            record,
            prepared,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    if record.op == "explain":
        return _resume_explain(
            record,
            prepared,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    if record.op == "authority":
        return _resume_authority(
            record,
            prepared,
            structural=structural,
            evidence=evidence,
            store=store,
        )
    if record.op == "trace":
        return _resume_trace(
            record,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=record.bounds,
            state=prepared.state,
            continuations=continuations,
        )
    if record.op == "impact":
        return _resume_impact(
            record,
            prepared,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    raise AssertionError(f"unhandled suspended op: {record.op}")
