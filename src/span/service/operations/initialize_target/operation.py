"""Host-facing semantic target establishment ([design note D](docs/design-references.md#d)).

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
from span.ports.continuation import ContinuationPort

from span.service.bounds import resolve_bounds as _resolve_bounds
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.establishment import (
    _baseline_sufficient,
    _Establishment,
    _next_establishment_pending,
    _start_establishment,
)
from span.service.operations.status import _compose_status_answer
from span.service.repository import _is_initialized, _uninitialized_answer
from span.service.requests import SemanticInitializeTargetRequest

__all__ = ["initialize_target", "target_subjects"]


from span.service.operations.initialize_target.admission import (
    _ensure_target_association,
    target_subjects,
)


def _target_question_needs_task(
    repository_id: str,
    target_question: m.SemanticQuestionScope,
    *,
    store: SemanticStore,
) -> bool:
    """True when an admitted target question still needs its first examination.

    OPEN is terminal-for-now; ANSWERED/NOT_APPLICABLE need no task. A question
    with no persisted row was admitted as PENDING, so it needs one; a persisted
    PENDING row needs its first examination too.
    """
    try:
        coverages = store.load_all_question_coverages(
            repository_id,
            target_question.scope_root,
            (target_question.subject,),
        )
    except Exception:
        return False
    for coverage in coverages:
        question = coverage.question
        if question is None:
            continue
        if (
            question.scope_root == target_question.scope_root
            and question.subject == target_question.subject
            and question.question_class == target_question.question_class
            and question.question_slice == target_question.question_slice
        ):
            return coverage.disposition is m.SemanticQuestionDisposition.PENDING
    # No persisted row yet for an admitted question: it was admitted as
    # PENDING by deterministic admission.
    return True


def _target_question_pending(
    repository_id: str,
    target_id: m.TargetId,
    association: m.TargetAssociation,
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
    continuations: ContinuationPort,
    target_scope: m.EvidenceScope,
) -> PendingInterpretation | None:
    """Suspend the first admitted target question that still needs a task."""
    ordered_questions = sorted(
        association.target_questions,
        key=lambda question: (
            question.question_class.value,
            question.scope_root.canonical_locator,
            question.subject.canonical_locator,
            question.question_slice,
        ),
    )
    for target_question in ordered_questions:
        if not _target_question_needs_task(repository_id, target_question, store=store):
            continue
        anchor_subjects = store.load_subjects(repository_id, (target_question.subject,))
        if not anchor_subjects:
            continue
        anchor = anchor_subjects[0]
        member_refs = tuple(
            account.evidence_ref
            for account in association.inventory_accounting
            if target_question.scope_root in account.assigned_area_subjects
        )
        semantic_task = prepare_interpretation_task(
            repository_id,
            anchor,
            structural=structural,
            evidence=evidence,
            bounds=bounds,
            state=state,
            authority_seeds=tuple(authority_seeds),
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice=target_question.question_slice,
            store=store,
            scope_root=target_question.scope_root,
            question_class=target_question.question_class,
            materiality_basis=target_question.materiality_basis,
            objective=objective,
            target_scope=target_scope,
            target_id=target_id,
            required_evidence_refs=member_refs,
        )
        return _suspend(
            op="initialize_target",
            repository_id=repository_id,
            subject=anchor,
            task=semantic_task,
            seeds=authority_seeds,
            bounds=bounds,
            state=state,
            resolution=None,
            scope=scope,
            remaining=candidates,
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=semantic_task.request.question_slice,
            establish_baseline=False,
            objective=objective,
            target_scope=target_scope,
            target_id=target_id,
        )
    return None


def _baseline_candidates_pending(
    repository_id: str,
    candidates: tuple[m.Subject, ...],
    *,
    objective: str,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...],
    continuations: ContinuationPort,
    target_scope: m.EvidenceScope,
    target_id: m.TargetId | None,
) -> PendingInterpretation | None:
    """Resume or start the first candidate whose baseline is insufficient."""
    for index, subject in enumerate(candidates):
        if _baseline_sufficient(
            repository_id,
            subject.subject_id,
            store=store,
            evidence=evidence,
            bounds=bounds,
        ):
            continue
        # Persisted worklist first: an admitted PENDING question under this
        # anchor resumes under its stored identity so a restart advances the
        # frontier instead of re-asking an OPEN audit.
        establishment = _Establishment(
            op="initialize_target",
            repository_id=repository_id,
            root=subject,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            seeds=authority_seeds,
            continuations=continuations,
            scope=candidates,
            remaining=candidates[index + 1 :],
            objective=objective,
            target_scope=target_scope,
            target_id=target_id,
        )
        pending = _next_establishment_pending(establishment)
        if pending is not None:
            return pending
        return _start_establishment(establishment)
    return None


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
    continuations: ContinuationPort,
    target_scope: m.EvidenceScope,
    target_id: m.TargetId | None = None,
) -> m.SemanticAnswer | PendingInterpretation:
    # E-13B semantic phase: admission already accounted for the inventory
    # deterministically; this stage asks questions only.
    if target_id is not None:
        association = store.load_target_association(repository_id, target_id)
        if association is not None:
            pending = _target_question_pending(
                repository_id,
                target_id,
                association,
                candidates,
                scope,
                objective=objective,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=bounds,
                state=state,
                authority_seeds=authority_seeds,
                continuations=continuations,
                target_scope=target_scope,
            )
            if pending is not None:
                return pending
            # No mapping and no PENDING target work: terminal target status.
            from span.service.operations.status import (
                _target_status_answer as _tgt_status,
            )

            return _tgt_status(
                repository_id,
                target_id,
                evidence=evidence,
                store=store,
                bounds=bounds,
                state=state,
                continuations=continuations,
            )
    pending = _baseline_candidates_pending(
        repository_id,
        candidates,
        objective=objective,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        authority_seeds=authority_seeds,
        continuations=continuations,
        target_scope=target_scope,
        target_id=target_id,
    )
    if pending is not None:
        return pending
    return _compose_status_answer(
        repository_id,
        scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
    )


def initialize_target(
    request: SemanticInitializeTargetRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Start or resume explicit-target semantic establishment.

    Canonicalizes scope/objective, derives the deterministic TargetId,
    creates/loads/reconciles the TargetAssociation, then returns the first
    unresolved structural candidate. Its request carries the complete target
    boundary and its continuation carries the canonical TargetId.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    canonical_scope, canonical_objective = m.canonicalize_target_scope(
        request.repository_id, request.target, request.objective
    )
    target_id = m.derive_target_id(
        request.repository_id, canonical_scope, canonical_objective
    )
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS, request.repository_id, bounds, state
        )
    subjects = target_subjects(
        request.repository_id,
        canonical_scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    _ensure_target_association(
        request.repository_id,
        canonical_scope,
        canonical_objective,
        target_id,
        subjects=subjects,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
    )
    return _next_target_pending(
        request.repository_id,
        subjects,
        subjects,
        objective=canonical_objective,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        authority_seeds=authority_seeds,
        continuations=continuations,
        target_scope=canonical_scope,
        target_id=target_id,
    )
