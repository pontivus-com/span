"""One establishment path: sufficiency, next admitted unit, first unit.

Every entry point that can establish a root — ``explain(establish_baseline)``,
``initialize_target``, and their submission resumes — delegates here. The store's
persisted question coverage decides whether the root is sufficient, which
admitted unit resumes next, or whether the first unit starts; no caller keeps a
private copy of that order.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _conflicts_for,
)
from span.service.freshness import (
    _premise_preflight,
)
from span.service.interpretation.suspend import _suspend
from span.service.interpretation.task import (
    prepare_interpretation_task,
)
from span.service.questions import (
    effective_question_view,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.resolution import (
    _load_all_coverages_or_defer,
    _load_subject_state,
)


def _baseline_sufficient(
    repository_id: str,
    scope_root: m.SubjectId,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> bool:
    """Recorded scoped sufficiency for an expressly selected root (B.3.2).

    True only when: (a) all nine root CQ classes have an explicit
    applicability disposition; (b) every admitted material root/member
    question is ANSWERED or genuinely NOT_APPLICABLE with *current*
    (effective) dependencies; (c) no unresolved requirements, conflicts,
    or unassessed items remain in scope; (d) no outstanding
    pages, unexamined questions, unprocessed premise frontier, or
    stale/unverifiable items; (e) synthesis rests on established,
    currently supported member evidence. Recorded dispositions alone
    never suffice — effective currentness is recomputed.
    """
    try:
        coverages = _load_all_coverages_or_defer(
            repository_id,
            scope_root,
            (),
            store=store,
            bounds=bounds,
            purpose="baseline sufficiency audit",
        )
    except Exception:
        return False
    root_covs = [
        cov
        for cov in coverages
        if cov.question is not None and cov.question.scope_root == scope_root
    ]
    if not root_covs:
        return False
    # (a) all nine root CQ classes have an explicit disposition entry
    # on the root subject itself.
    root_classes: set[m.SemanticQuestionClass] = set()
    for coverage in root_covs:
        question = coverage.question
        if question is not None and question.subject == scope_root:
            root_classes.add(question.question_class)
    if any(cls not in root_classes for cls in m.SemanticQuestionClass):
        return False
    # (b)+(d) every admitted question effective-current ANSWERED or
    # NOT_APPLICABLE; PENDING/OPEN/noncurrent/stale block sufficiency.
    for cov in root_covs:
        if cov.question is None:
            continue
        try:
            view = effective_question_view(
                cov,
                evidence=evidence,
                store=store,
                repository_id=repository_id,
            )
        except Exception:
            return False
        if view.recorded_disposition in (
            m.SemanticQuestionDisposition.PENDING,
            m.SemanticQuestionDisposition.OPEN,
        ):
            return False
        if view.effective_disposition not in (
            m.SemanticQuestionDisposition.ANSWERED,
            m.SemanticQuestionDisposition.NOT_APPLICABLE,
        ):
            return False
        if view.freshness.state is not m.FreshnessState.CURRENT:
            return False
        # (c) any open requirement (missing authority/evidence,
        # conflicts, stale premises) prevents full sufficiency.
        if view.resolution_requirements:
            return False
    # (c) no conflicts among scoped canonical items.
    try:
        scoped_subjects = tuple(
            dict.fromkeys(
                cov.question.subject for cov in root_covs if cov.question is not None
            )
        )
        scoped_claims: list[m.SemanticClaim] = []
        scoped_rels: list[m.SemanticRelationship] = []
        for sid in scoped_subjects:
            loaded_c, loaded_r, _, _ = _load_subject_state(
                repository_id,
                sid,
                store=store,
                bounds=bounds,
            )
            scoped_claims.extend(loaded_c)
            scoped_rels.extend(loaded_r)
        if _conflicts_for(
            repository_id,
            tuple(scoped_claims),
            tuple(scoped_rels),
            store=store,
        ):
            return False
        # (d) no stale/unverifiable items and no unprocessed premise
        # frontier across scoped results.
        all_refs: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
            _claim_ref(c) for c in scoped_claims
        ) + tuple(_relationship_ref(r) for r in scoped_rels)
        if all_refs:
            premise_updates = _premise_preflight(
                repository_id,
                all_refs,
                store=store,
                bounds=bounds,
            )
            if premise_updates:
                return False
            if any(
                c.freshness.state is not m.FreshnessState.CURRENT for c in scoped_claims
            ) or any(
                r.freshness.state is not m.FreshnessState.CURRENT for r in scoped_rels
            ):
                return False
        # (d) no outstanding pages: every scoped subject load must be
        # exhaustive within bounds.
        for sid in scoped_subjects:
            claim_page = store.load_claims(repository_id, (sid,), (), bounds, None)
            if claim_page.bound_info.truncated:
                return False
    except Exception:
        return False
    # (e) is entailed by (b)+(d): every ANSWERED result ref resolved
    # above to a CURRENT canonical item through the effective views.
    return True


def _next_baseline_pending(
    repository_id: str,
    root: m.Subject,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.InterpretationCoverage | None:
    """First admitted PENDING question under a baseline root, if any.

    Deterministic order (CQ class, subject, slice). Used both when a
    baseline resumes after submit and when the baseline operation is
    re-entered after a lost continuation: persisted coverage — never
    prompt wording — determines remaining work, so the audit is never
    restarted while admitted work exists.
    """
    try:
        pending = store.load_all_question_coverages(
            repository_id,
            root.subject_id,
            (root.subject_id,),
        )
    except Exception:
        try:
            pending = store.load_question_coverages(
                repository_id,
                root.subject_id,
                (root.subject_id,),
                bounds,
            )
        except Exception:
            pending = ()
    next_pending = [
        cov
        for cov in pending
        if cov.disposition is m.SemanticQuestionDisposition.PENDING
        and cov.question is not None
    ]
    next_pending.sort(
        key=lambda c: (
            c.question.question_class.value,  # type: ignore[union-attr]
            c.question.subject.canonical_locator,  # type: ignore[union-attr]
            c.question.question_slice,  # type: ignore[union-attr]
        )
    )
    return next_pending[0] if next_pending else None


def _suspend_baseline_pending(
    repository_id: str,
    root: m.Subject,
    coverage: m.InterpretationCoverage,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    seeds: tuple[m.EvidenceRef, ...],
    resolution: m.SubjectResolution | None,
    continuations: ContinuationPort,
    op: str = "explain",
    scope: tuple[m.Subject, ...] = (),
    remaining: tuple[m.Subject, ...] = (),
    objective: str = "",
    target_scope: m.EvidenceScope = m.EvidenceScope(),
    target_id: m.TargetId | None = None,
) -> PendingInterpretation:
    """Suspend the next admitted baseline question under its persisted
    identity (no regenerated wording, no restarted audit)."""
    assert coverage.question is not None
    try:
        loaded = store.load_subjects(repository_id, (coverage.question.subject,))
        nxt_subject = (
            m.Subject(
                subject_id=loaded[0].subject_id,
                display_name=loaded[0].display_name,
                declared_kind=loaded[0].declared_kind,
            )
            if loaded
            else root
        )
    except Exception:
        nxt_subject = root
    nxt_task = prepare_interpretation_task(
        repository_id,
        nxt_subject,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=seeds,
        operation_intent=m.SemanticIntent.EXPLAIN,
        question_slice=coverage.question.question_slice,
        store=store,
        scope_root=coverage.question.scope_root,
        question_class=coverage.question.question_class,
        materiality_basis=coverage.question.materiality_basis,
        establish_baseline=False,
        objective=objective,
        target_scope=target_scope,
        target_id=target_id,
    )
    return _suspend(
        op=op,
        repository_id=repository_id,
        subject=nxt_subject,
        task=nxt_task,
        seeds=seeds,
        bounds=bounds,
        state=state,
        resolution=resolution,
        scope=scope,
        remaining=remaining,
        continuations=continuations,
        operation_intent="EXPLAIN",
        question_slice=coverage.question.question_slice,
        establish_baseline=True,
        objective=objective,
        target_scope=target_scope,
        target_id=target_id,
    )


@_dataclasses.dataclass
class _Establishment:
    """One establishment step: which root, for which operation, and where."""

    op: str
    repository_id: str
    root: m.Subject
    structural: StructuralSource
    evidence: EvidenceSource
    store: SemanticStore
    bounds: m.QueryBounds
    state: m.RepositoryState
    seeds: tuple[m.EvidenceRef, ...]
    continuations: ContinuationPort
    resolution: m.SubjectResolution | None = None
    scope: tuple[m.Subject, ...] = ()
    remaining: tuple[m.Subject, ...] = ()
    objective: str = ""
    target_scope: m.EvidenceScope = m.EvidenceScope()
    target_id: m.TargetId | None = None


def _cq01_established(
    repository_id: str,
    scope_root: m.SubjectId,
    *,
    store: SemanticStore,
) -> bool:
    """True when a CQ-01 for this root was already admitted.

    Worklist exhaustion with an admitted CQ-01 means the audit ran and left
    qualified (honest OPEN/PENDING) state: serve that answer instead of
    starting a redundant second audit.
    """
    try:
        existing = store.load_all_question_coverages(
            repository_id,
            scope_root,
            (scope_root,),
        )
    except Exception:
        existing = ()
    for coverage in existing:
        question = coverage.question
        if question is None:
            continue
        if (
            question.question_class is m.SemanticQuestionClass.CQ_01
            and question.subject == scope_root
        ):
            return True
    return False


def _next_establishment_pending(
    step: _Establishment,
) -> PendingInterpretation | None:
    """Resume the next admitted establishment unit under its stored identity."""
    coverage = _next_baseline_pending(
        step.repository_id,
        step.root,
        store=step.store,
        bounds=step.bounds,
    )
    if coverage is None:
        return None
    return _suspend_baseline_pending(
        step.repository_id,
        step.root,
        coverage,
        structural=step.structural,
        evidence=step.evidence,
        store=step.store,
        bounds=step.bounds,
        state=step.state,
        seeds=step.seeds,
        resolution=step.resolution,
        continuations=step.continuations,
        op=step.op,
        scope=step.scope,
        remaining=step.remaining,
        objective=step.objective,
        target_scope=step.target_scope,
        target_id=step.target_id,
    )


def _start_establishment(step: _Establishment) -> PendingInterpretation:
    """Start the first unit of a root with no admitted establishment work."""
    task = prepare_interpretation_task(
        step.repository_id,
        step.root,
        structural=step.structural,
        evidence=step.evidence,
        bounds=step.bounds,
        state=step.state,
        authority_seeds=step.seeds,
        operation_intent=m.SemanticIntent.EXPLAIN,
        store=step.store,
        scope_root=step.root.subject_id,
        establish_baseline=True,
        objective=step.objective,
        target_scope=step.target_scope,
    )
    return _suspend(
        op=step.op,
        repository_id=step.repository_id,
        subject=step.root,
        task=task,
        seeds=step.seeds,
        bounds=step.bounds,
        state=step.state,
        resolution=step.resolution,
        scope=step.scope,
        remaining=step.remaining,
        continuations=step.continuations,
        operation_intent="EXPLAIN",
        question_slice=task.request.question_slice,
        establish_baseline=True,
        objective=step.objective,
        target_scope=step.target_scope,
        target_id=step.target_id,
    )
