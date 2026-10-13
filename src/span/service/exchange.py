"""Span service agent-exchange coordination (plan §11.12; v0.6 §14 Amendment A-01).

Interpretation submission, reissue, and resume dispatch across the
owning operation modules. Owns no semantic predicate: validates via
``core`` and rebuilds answers via the owning op composers. Verbatim
from ``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import InterpretationIngressFailure
from span.ports.interpretation import InterpretationUnavailable
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.continuations import SuspendedOperation

from span.service.discovery import (
    _coverage_for_task,
)
from span.service.interpretation import (
    InterpretationTask,
    _materialize_unit,
    _next_baseline_pending,
    _suspend,
    _suspend_baseline_pending,
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
from span.service.operations.status import (
    _resume_status,
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
from span.service.resolution import (
    _resolve_exact_subject,
)

__all__ = [
    'submit_interpretation',
    'reissue_interpretation',
]

def submit_interpretation(
    continuation: str,
    result: m.SemanticInterpretationResult,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
) -> m.SemanticAnswer | PendingInterpretation:
    """Accept an agent's typed result and resume the operation (§11.12).

    Unknown or expired continuations yield InterpretationUnavailable
    (the agent re-issues the original operation, idempotently).
    Validation failure rejects the unit with no reissue (§7.5); the
    continuation is already consumed. Refresh resumes across remaining
    subjects, suspending again while affected work remains.
    """
    record = continuations.claim(continuation)
    if record is None:
        raise InterpretationUnavailable(
            f"unknown or expired continuation: {continuation}"
        )
    bounds = record.bounds
    task = InterpretationTask(
        request=record.request,
        fingerprints=record.fingerprints,
        known_subject_ids=record.known_subject_ids,
        observations=(),
    )
    state = structural.repository_state(record.repository_id)
    extra_known: list[m.SubjectId] = []
    endpoints = []
    for candidate in result.relationships:
        endpoints.extend((candidate.source, candidate.target))
    endpoints.extend(candidate.subject for candidate in result.claims)
    # Addendum E §4C.4/E-13B/C: first admission of an already-persisted
    # area is a valid mapping-only submission. Assigned area subjects that
    # already resolve in the store join the unit scope exactly like
    # claim/relationship endpoints, so validation does not reject reusable
    # existing coverage as an unknown target area.
    for acc in result.proposed_target_inventory_accounting:
        endpoints.extend(acc.assigned_area_subjects)
    for endpoint in endpoints:
        if endpoint in task.known_subject_ids or endpoint in extra_known:
            continue
        if (
            _resolve_exact_subject(
                record.repository_id, endpoint,
                structural=structural, bounds=bounds,
            )
            is not None
        ):
            extra_known.append(endpoint)
            continue
        # Registered semantic-only subjects live in the store, not the
        # structural source: previously indexed identities join the unit
        # scope exactly like structurally resolved ones (§4.11).
        if store.load_subjects(record.repository_id, (endpoint,)):
            extra_known.append(endpoint)
    request_question = task.request.question
    if request_question is not None:
        # §4C.6D amendment (answerability, 2026-10-11, refresh seam): the
        # run's own suspended question root joins unit scope when persisted.
        # The run is already about that question (initialize_target,
        # explain, and refresh suspensions alike), so no foreign scope can
        # smuggle in through it. Store-only: never structurally guessed.
        root = request_question.scope_root
        if root not in task.known_subject_ids and root not in extra_known:
            if store.load_subjects(record.repository_id, (root,)):
                extra_known.append(root)
    effective_target_id = (
        record.target_id
        if record.target_id is not None
        else task.request.target_id
    )
    has_target_proposals = bool(
        result.proposed_target_inventory_accounting
        or result.proposed_target_questions
    )
    target_assoc: m.TargetAssociation | None = None
    inventory_ids: frozenset[str] = frozenset()
    inventory_snapshot: dict[str, m.EvidenceRef] = {}
    inventory_fingerprints: dict[str, str] = {}
    target_item: m.EvidenceInventoryItem | None = task.request.target_inventory_item
    if effective_target_id is not None or has_target_proposals:
        try:
            target_assoc = store.load_target_association(
                record.repository_id, effective_target_id
            ) if effective_target_id is not None else None
        except Exception:
            target_assoc = None
        if effective_target_id is not None and target_assoc is None:
            from span.core.validation import InterpretationUnitRejected as _Rejected
            raise _Rejected(("target association does not resolve",))
        scope_for_inventory = (
            target_assoc.target_scope
            if target_assoc is not None
            else record.target_scope
        )
        try:
            from span.service.discovery import enumerate_target_inventory

            inv_items = enumerate_target_inventory(
                record.repository_id, scope_for_inventory,
                evidence=evidence, bounds=bounds,
            )
            inventory_ids = frozenset(
                item.evidence_ref.evidence_id.value for item in inv_items
            )
            inventory_snapshot = {
                item.evidence_ref.evidence_id.value: item.evidence_ref
                for item in inv_items
            }
            inventory_fingerprints = {
                item.evidence_ref.evidence_id.value: item.content_fingerprint
                for item in inv_items
            }
        except ValueError:
            inventory_ids = frozenset()
            inventory_snapshot = {}
            inventory_fingerprints = {}
        except Exception:
            inventory_ids = frozenset()
            inventory_snapshot = {}
            inventory_fingerprints = {}
        if target_assoc is not None:
            # §4C.6D amendment (answerability, 2026-10-11): admitted areas
            # join unit scope on target-bound submits, exactly like
            # mapping-assigned areas above — membership in the just-loaded
            # association is the authority, so no resolution round-trip.
            for area in target_assoc.area_subjects:
                if (
                    area not in task.known_subject_ids
                    and area not in extra_known
                ):
                    extra_known.append(area)
    _materialize_unit(
        task, result, store=store, evidence=evidence, state=state,
        extra_known_subjects=tuple(extra_known),
        coverage=_coverage_for_task(
            record.repository_id,
            tuple(s.subject_id for s in task.request.subjects),
            evidence=evidence, seeds=record.seeds,
            question=task.request.question,
        ),
        declared_complete=record.declared_complete,
        retire_scope=tuple(s.subject_id for s in task.request.subjects),
        target_id=effective_target_id,
        target_inventory_item=target_item,
        target_association=target_assoc,
        current_inventory_ids=inventory_ids,
        current_inventory_snapshot=inventory_snapshot,
        current_inventory_fingerprints=inventory_fingerprints,
    )
    if record.op == "initialize_target":
        if effective_target_id is not None:
            return _next_target_pending(
                record.repository_id, record.remaining, record.scope,
                objective=record.objective, structural=structural,
                evidence=evidence, store=store, bounds=bounds, state=state,
                authority_seeds=record.seeds, continuations=continuations,
                target_scope=record.target_scope,
                target_id=record.target_id,
            )
        next_cov = _next_baseline_pending(
            record.repository_id, record.subject,
            store=store, bounds=bounds,
        )
        if next_cov is not None:
            return _suspend_baseline_pending(
                record.repository_id, record.subject, next_cov,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, seeds=record.seeds,
                resolution=record.resolution, continuations=continuations,
                op="initialize_target", scope=record.scope,
                remaining=record.remaining, objective=record.objective,
                target_scope=record.target_scope,
                target_id=record.target_id,
            )
        return _next_target_pending(
            record.repository_id, record.remaining, record.scope,
            objective=record.objective, structural=structural,
            evidence=evidence, store=store, bounds=bounds, state=state,
            authority_seeds=record.seeds, continuations=continuations,
            target_scope=record.target_scope,
            target_id=record.target_id,
        )
    if record.op == "refresh" and record.remaining:
        nxt, rest = record.remaining[0], record.remaining[1:]
        nxt_stale = _stale_question_scopes(
            record.repository_id, nxt,
            store=store, evidence=evidence, bounds=bounds,
            suspended=continuations.live_question_keys(),
        )
        nxt_scope = nxt_stale[0] if nxt_stale else None
        nxt_task = prepare_interpretation_task(
            record.repository_id, nxt, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=record.seeds,
            operation_intent=m.SemanticIntent.STATUS,
            question_slice=(
                nxt_scope.question_slice if nxt_scope is not None
                else nxt.subject_id.canonical_locator
            ),
            store=store,
            scope_root=(
                nxt_scope.scope_root if nxt_scope is not None
                else nxt.subject_id
            ),
            question_class=(
                nxt_scope.question_class if nxt_scope is not None else None
            ),
            materiality_basis=(
                nxt_scope.materiality_basis if nxt_scope is not None else ""
            ),
        )
        return _suspend(
            op="refresh", repository_id=record.repository_id, subject=nxt,
            task=nxt_task, seeds=record.seeds, bounds=bounds, state=state,
            resolution=None, scope=record.scope, remaining=rest,
            changed=record.changed, continuations=continuations,
            operation_intent="STATUS",
            question_slice=nxt_task.request.question_slice,
            declared_complete=True,
        )
    if record.op == "explain":
        if record.establish_baseline:
            nxt_cov = _next_baseline_pending(
                record.repository_id, record.subject,
                store=store, bounds=bounds,
            )
            if nxt_cov is not None:
                return _suspend_baseline_pending(
                    record.repository_id, record.subject, nxt_cov,
                    structural=structural, evidence=evidence, store=store,
                    bounds=bounds, state=state, seeds=record.seeds,
                    resolution=record.resolution,
                    continuations=continuations,
                )
        return _compose_explain_answer(
            record.repository_id, record.subject, record.resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
            scope_root=record.subject.subject_id,
        )
    if record.op == "authority":
        return _compose_authority_answer(
            record.repository_id, record.subject, record.resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
        )
    if record.op == "trace":
        return _resume_trace(
            record, structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state, continuations=continuations,
        )
    if record.op == "status":
        return _resume_status(
            record, structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state, continuations=continuations,
        )
    if record.op == "impact":
        target = record.scope[0] if record.scope else record.subject
        return _compose_impact_answer(
            record.repository_id, target, record.resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
            change_kind=(
                ChangeKind(record.change_kind)
                if record.change_kind is not None
                else ChangeKind.BEHAVIOR
            ),
            change_description=record.change_description,
            affected_assertions=record.affected_assertions,
            seeds=record.seeds,
            suspended=record.suspended + (
                record.subject.subject_id.canonical_locator,
            ),
            continuations=continuations,
        )
    return _compose_refresh_answer(
        record.repository_id, record.scope,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state,
        changed=record.changed,
    )

def reissue_interpretation(
    continuation: str,
    *,
    continuations: ContinuationStore,
) -> PendingInterpretation:
    """Reissue the identical bounded task once on ingress failure (§7.4).

    Consumes the continuation; a second failure abandons the exchange
    (InterpretationIngressFailure). Semantic validation failure never
    reaches here — it rejects the unit via submit (§7.5).
    """
    record = continuations.claim(continuation)
    if record is None:
        raise InterpretationUnavailable(
            f"unknown or expired continuation: {continuation}"
        )
    if record.reissues >= 1:
        raise InterpretationIngressFailure(
            "interpretation task reissue exhausted; continuation abandoned"
        )
    token = continuations.pend(
        SuspendedOperation(
            op=record.op,
            repository_id=record.repository_id,
            subject=record.subject,
            scope=record.scope,
            remaining=record.remaining,
            changed=record.changed,
            resolution=record.resolution,
            request=record.request,
            fingerprints=record.fingerprints,
            known_subject_ids=record.known_subject_ids,
            seeds=record.seeds,
            bounds=record.bounds,
            state=record.state,
            reissues=record.reissues + 1,
            affected_assertions=record.affected_assertions,
            operation_intent=record.operation_intent,
            objective=record.objective,
            question_slice=record.question_slice,
            declared_complete=record.declared_complete,
            establish_baseline=record.establish_baseline,
            target_scope=record.target_scope,
            target_id=record.target_id,
        )
    )
    return PendingInterpretation(
        continuation=token, request=record.request
    )
