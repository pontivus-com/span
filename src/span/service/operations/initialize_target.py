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
        repository_id,
        target,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
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
    target_id: m.TargetId | None = None,
) -> m.SemanticAnswer | PendingInterpretation:
    # E-13B mapping frontier: unaccounted inventory first, question=None.
    if target_id is not None:
        assoc = store.load_target_association(repository_id, target_id)
        if assoc is not None:
            from span.service.discovery import enumerate_target_inventory

            try:
                inv_items = enumerate_target_inventory(
                    repository_id,
                    target_scope,
                    evidence=evidence,
                    bounds=bounds,
                )
            except ValueError:
                inv_items = None
            if inv_items is not None:
                accounted_ids = {
                    acc.evidence_ref.evidence_id.value
                    for acc in assoc.inventory_accounting
                }
                unaccounted = sorted(
                    (
                        it
                        for it in inv_items
                        if it.evidence_ref.evidence_id.value not in accounted_ids
                    ),
                    key=lambda it: (
                        it.evidence_ref.evidence_id.value,
                        it.evidence_ref.locator,
                    ),
                )
                if unaccounted:
                    # S5/J-6: bind a bounded, deterministic batch of
                    # unaccounted members in one mapping unit. No new
                    # batch-size constant: the existing evidence bound is
                    # the limit; the frontier order is stable identity.
                    batch = tuple(unaccounted[: bounds.max_evidence_units])
                    item = batch[0]
                    anchor = None
                    for cand in candidates:
                        if (
                            cand.subject_id.canonical_locator
                            == item.evidence_ref.locator
                        ):
                            anchor = cand
                            break
                    if anchor is None:
                        for cand in scope:
                            if (
                                cand.subject_id.canonical_locator
                                == item.evidence_ref.locator
                            ):
                                anchor = cand
                                break
                    if anchor is None:
                        anchor_sid = m.SubjectId(
                            repository_id=repository_id,
                            subject_kind=m.SubjectKind.OTHER,
                            canonical_locator=item.evidence_ref.locator,
                        )
                        anchor = m.Subject(
                            subject_id=anchor_sid,
                            display_name=item.evidence_ref.locator,
                            declared_kind=item.evidence_ref.locator,
                        )
                    mapping_task = prepare_interpretation_task(
                        repository_id,
                        anchor,
                        structural=structural,
                        evidence=evidence,
                        bounds=bounds,
                        state=state,
                        authority_seeds=authority_seeds,
                        operation_intent=m.SemanticIntent.EXPLAIN,
                        store=store,
                        scope_root=anchor.subject_id,
                        objective=objective,
                        target_scope=target_scope,
                        target_id=target_id,
                        target_inventory_items=batch,
                        mapping_mode=True,
                    )
                    return _suspend(
                        op="initialize_target",
                        repository_id=repository_id,
                        subject=anchor,
                        task=mapping_task,
                        seeds=authority_seeds,
                        bounds=bounds,
                        state=state,
                        resolution=None,
                        scope=scope,
                        remaining=candidates,
                        continuations=continuations,
                        operation_intent="EXPLAIN",
                        question_slice=mapping_task.request.question_slice,
                        establish_baseline=False,
                        objective=objective,
                        target_scope=target_scope,
                        target_id=target_id,
                    )
            # E-13B semantic-question phase: PENDING target questions only.
            # OPEN is terminal-for-now; ANSWERED/NOT_APPLICABLE need no task.
            ordered_questions = sorted(
                assoc.target_questions,
                key=lambda q: (
                    q.question_class.value,
                    q.scope_root.canonical_locator,
                    q.subject.canonical_locator,
                    q.question_slice,
                ),
            )
            for target_q in ordered_questions:
                try:
                    coverages = store.load_all_question_coverages(
                        repository_id,
                        target_q.scope_root,
                        (target_q.subject,),
                    )
                except Exception:
                    continue
                match = None
                for cov in coverages:
                    if cov.question is None:
                        continue
                    q = cov.question
                    if (
                        q.scope_root == target_q.scope_root
                        and q.subject == target_q.subject
                        and q.question_class == target_q.question_class
                        and q.question_slice == target_q.question_slice
                    ):
                        match = cov
                        break
                # Absent coverage with no persisted row: treat as PENDING
                # only if the question is still admitted and no terminal
                # row exists; otherwise the status projection reports
                # INCOMPLETE without inventing work here.
                needs_task = False
                if match is None:
                    # No persisted row yet for an admitted question:
                    # it was admitted as PENDING by mapping.
                    needs_task = True
                elif match.disposition is m.SemanticQuestionDisposition.PENDING:
                    needs_task = True
                if not needs_task:
                    continue
                anchor_subjects = store.load_subjects(
                    repository_id, (target_q.subject,)
                )
                if not anchor_subjects:
                    continue
                anchor = anchor_subjects[0]
                member_refs = tuple(
                    acc.evidence_ref
                    for acc in assoc.inventory_accounting
                    if target_q.scope_root in acc.assigned_area_subjects
                )
                # Unresolved mappings stay visible: their evidence rides
                # along as required (non-authority) context so later
                # evidence can correct the grouping through revision.
                unresolved_refs = tuple(
                    acc.evidence_ref
                    for acc in assoc.inventory_accounting
                    if acc.resolution_requirements
                )
                sem_task = prepare_interpretation_task(
                    repository_id,
                    anchor,
                    structural=structural,
                    evidence=evidence,
                    bounds=bounds,
                    state=state,
                    authority_seeds=tuple(authority_seeds),
                    operation_intent=m.SemanticIntent.EXPLAIN,
                    question_slice=target_q.question_slice,
                    store=store,
                    scope_root=target_q.scope_root,
                    question_class=target_q.question_class,
                    materiality_basis=target_q.materiality_basis,
                    objective=objective,
                    target_scope=target_scope,
                    target_id=target_id,
                    required_evidence_refs=member_refs + unresolved_refs,
                )
                return _suspend(
                    op="initialize_target",
                    repository_id=repository_id,
                    subject=anchor,
                    task=sem_task,
                    seeds=authority_seeds,
                    bounds=bounds,
                    state=state,
                    resolution=None,
                    scope=scope,
                    remaining=candidates,
                    continuations=continuations,
                    operation_intent="EXPLAIN",
                    question_slice=sem_task.request.question_slice,
                    establish_baseline=False,
                    objective=objective,
                    target_scope=target_scope,
                    target_id=target_id,
                )
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
            )
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
        # frontier instead of re-asking an OPEN audit (same pattern as the
        # live-session resume in service/exchange.py).
        next_cov = _next_baseline_pending(
            repository_id,
            subject,
            store=store,
            bounds=bounds,
        )
        if next_cov is not None:
            return _suspend_baseline_pending(
                repository_id,
                subject,
                next_cov,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=bounds,
                state=state,
                seeds=authority_seeds,
                resolution=None,
                continuations=continuations,
                op="initialize_target",
                scope=candidates,
                remaining=candidates[index + 1 :],
                objective=objective,
                target_scope=target_scope,
                target_id=target_id,
            )
        task = prepare_interpretation_task(
            repository_id,
            subject,
            structural=structural,
            evidence=evidence,
            bounds=bounds,
            state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.EXPLAIN,
            store=store,
            scope_root=subject.subject_id,
            establish_baseline=True,
            objective=objective,
            target_scope=target_scope,
        )
        return _suspend(
            op="initialize_target",
            repository_id=repository_id,
            subject=subject,
            task=task,
            seeds=authority_seeds,
            bounds=bounds,
            state=state,
            resolution=None,
            scope=scope,
            remaining=candidates[index + 1 :],
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=task.request.question_slice,
            establish_baseline=True,
            objective=objective,
            target_scope=target_scope,
            target_id=target_id,
        )
    return _compose_status_answer(
        repository_id,
        scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
    )


def _ensure_target_association(
    repository_id: str,
    canonical_scope: m.EvidenceScope,
    canonical_objective: str,
    target_id: m.TargetId,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.TargetAssociation:
    """Create/load/reconcile the TargetAssociation (Addendum E §§4C.6A–6C).

    Fully enumerates inventory across pages; truncation without progress
    raises (caller maps to UNVERIFIABLE). Accepted initialize_target always
    refreshes touch/expiry and the diagnostic observed repository
    fingerprint. Membership reconciliation only: content freshness for
    stable members remains owned by existing evidence/coverage
    dependencies plus scoped refresh (§§4C.6B/4C.6E).
    """
    from span.service.discovery import enumerate_target_inventory

    items = enumerate_target_inventory(
        repository_id, canonical_scope, evidence=evidence, bounds=bounds
    )
    fingerprint = m.target_inventory_fingerprint(items)
    # Store failures propagate: a missing association is None, a broken
    # store is an error, never silent absence.
    existing = store.load_target_association(repository_id, target_id)
    if existing is None:
        assoc = m.TargetAssociation(
            target_id=target_id,
            repository_id=repository_id,
            target_scope=canonical_scope,
            objective=canonical_objective,
            inventory_fingerprint=fingerprint,
            observed_repository_state_fingerprint=state.state_fingerprint,
        )
        store.write_index_batch(m.CanonicalIndexBatch(target_associations=(assoc,)))
        return assoc
    if existing.inventory_fingerprint == fingerprint:
        # Explicit re-entry with unchanged membership: deterministic
        # membership reconciliation only. Accounting entries are retained
        # as-is; only the diagnostic repository fingerprint is re-observed
        # and retention is refreshed. Content-only changes never route
        # through here (§§4C.6B/4C.6E).
        touched = m.TargetAssociation(
            target_id=existing.target_id,
            repository_id=existing.repository_id,
            target_scope=canonical_scope,
            objective=canonical_objective,
            area_subjects=existing.area_subjects,
            target_questions=existing.target_questions,
            inventory_accounting=existing.inventory_accounting,
            inventory_fingerprint=existing.inventory_fingerprint,
            observed_repository_state_fingerprint=state.state_fingerprint,
        )
        store.write_index_batch(m.CanonicalIndexBatch(target_associations=(touched,)))
        return touched
    present = {item.evidence_ref.evidence_id.value for item in items}
    by_id = {item.evidence_ref.evidence_id.value: item for item in items}
    for acc in existing.inventory_accounting:
        eid = acc.evidence_ref.evidence_id.value
        if eid not in present:
            continue
        current_ref = by_id[eid].evidence_ref
        if (
            current_ref.locator != acc.evidence_ref.locator
            or current_ref.source_kind != acc.evidence_ref.source_kind
        ):
            raise ValueError(
                f"persisted target identity conflicts with provider "
                f"snapshot for {eid!r}; reconciliation refused"
            )
    retained = tuple(
        acc
        for acc in existing.inventory_accounting
        if acc.evidence_ref.evidence_id.value in present
    )
    area_subjects = tuple(
        dict.fromkeys(sid for acc in retained for sid in acc.assigned_area_subjects)
    )
    admitted = set(area_subjects)
    target_questions = tuple(
        q for q in existing.target_questions if q.scope_root in admitted
    )
    reconciled = m.TargetAssociation(
        target_id=existing.target_id,
        repository_id=existing.repository_id,
        target_scope=canonical_scope,
        objective=canonical_objective,
        area_subjects=area_subjects,
        target_questions=target_questions,
        inventory_accounting=retained,
        inventory_fingerprint=fingerprint,
        observed_repository_state_fingerprint=state.state_fingerprint,
    )
    store.write_index_batch(m.CanonicalIndexBatch(target_associations=(reconciled,)))
    return reconciled


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
    _ensure_target_association(
        request.repository_id,
        canonical_scope,
        canonical_objective,
        target_id,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
    )
    subjects = target_subjects(
        request.repository_id,
        canonical_scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
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
