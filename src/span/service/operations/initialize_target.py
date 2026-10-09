"""Host-facing semantic target establishment (Addendum D).

This operation owns only the deterministic boundary and frontier.  The
active host agent still performs semantic interpretation and submits the
canonical typed result through ``submit_interpretation``.  No model is
invoked here and no second semantic writer or progress store is introduced.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore

from span.service.bounds import resolve_bounds as _resolve_bounds
from span.service.interpretation import (
    _next_baseline_pending,
    _suspend,
    _suspend_baseline_pending,
    prepare_interpretation_task,
)
from span.service.operations.explain import _baseline_sufficient
from span.service.operations.status import _compose_status_answer
from span.service.repository import _is_initialized, _uninitialized_answer
from span.service.requests import SemanticInitializeTargetRequest
from span.service.resolution import _resolve_target_subjects

__all__ = ["initialize_target", "target_subjects"]


def target_subjects(
    repository_id: str,
    target: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """Enumerate bounded structural candidates in the exact target.

    These candidates make the exchange resumable; they are not semantic
    areas and their count is not a completion claim. The exact target is
    carried separately on each pending interpretation request.
    """
    return _resolve_target_subjects(
        repository_id, target, structural=structural,
        evidence=evidence, store=store, bounds=bounds,
    )


def _next_target_pending(
    repository_id: str,
    candidates: tuple[m.Subject, ...],
    scope: tuple[m.Subject, ...],
    *,
    objective: str,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...],
    continuations: ContinuationStore,
    target_scope: m.EvidenceScope,
) -> m.SemanticAnswer | PendingInterpretation:
    for index, subject in enumerate(candidates):
        if _baseline_sufficient(
            repository_id, subject.subject_id,
            store=store, evidence=evidence, bounds=bounds,
        ):
            continue
        # Persisted worklist first: an admitted PENDING question under this
        # anchor resumes under its stored identity so a restart advances the
        # frontier instead of re-asking an OPEN audit (same pattern as the
        # live-session resume in service/exchange.py).
        next_cov = _next_baseline_pending(
            repository_id, subject, store=store, bounds=bounds,
        )
        if next_cov is not None:
            return _suspend_baseline_pending(
                repository_id, subject, next_cov,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, seeds=authority_seeds,
                resolution=None, continuations=continuations,
                op="initialize_target", scope=candidates,
                remaining=candidates[index + 1:],
                objective=objective, target_scope=target_scope,
            )
        task = prepare_interpretation_task(
            repository_id, subject,
            structural=structural, evidence=evidence, bounds=bounds,
            state=state, authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.EXPLAIN,
            store=store, scope_root=subject.subject_id,
            establish_baseline=True, objective=objective,
            target_scope=target_scope,
        )
        return _suspend(
            op="initialize_target", repository_id=repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=None,
            scope=scope, remaining=candidates[index + 1:],
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=task.request.question_slice,
            establish_baseline=True,
            objective=objective,
            target_scope=target_scope,
        )
    return _compose_status_answer(
        repository_id, scope, structural=structural, evidence=evidence,
        store=store, bounds=bounds, state=state,
    )


def initialize_target(
    request: SemanticInitializeTargetRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Start or resume explicit-target semantic establishment.

    The returned pending unit is the first unresolved structural candidate in
    the exact target. Its request carries the complete target boundary and its
    continuation carries the remaining bounded candidates; after a submission
    the exchange layer requests the next unit automatically.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    objective = request.objective.strip()
    if not objective:
        raise ValueError("initialize_target objective must be non-empty")
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS, request.repository_id, bounds, state
        )
    subjects = target_subjects(
        request.repository_id, request.target,
        structural=structural, evidence=evidence, store=store, bounds=bounds,
    )
    return _next_target_pending(
        request.repository_id, subjects, subjects,
        objective=objective, structural=structural, evidence=evidence,
        store=store, bounds=bounds, state=state,
        authority_seeds=authority_seeds, continuations=continuations,
        target_scope=request.target,
    )
