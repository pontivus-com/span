"""Span service explain operation (plan §11.4; v0.6 §14 Amendment A-01).

Bounded semantic explanation with baseline establishment. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import answers as _answers
from span.core import model as m
from span.core import requirements as _requirements
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.establishment import (
    _baseline_sufficient,
    _cq01_established,
    _Establishment,
    _next_establishment_pending,
    _start_establishment,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.questions import (
    _question_local_missing,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    SemanticExplainRequest,
)
from span.service.resolution import (
    _has_established_semantic_state,
    _resolve_contextual_subjects,
    _resolve_query_subject,
)


from span.service.operations.explain.answer import (
    _baseline_answer,
    _compose_explain_answer,
)


def _explain_resolution(
    request: SemanticExplainRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.SubjectResolution:
    """Resolve the target, preferring contextual orientation when unexamined.

    A path that resolves directly but has no established semantic state is
    oriented contextually instead, so the operation answers about what the path
    actually participates in rather than about an empty subject.
    """
    resolution = _resolve_query_subject(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    if request.target.exact_subject_id is not None:
        return resolution
    use_direct = False
    if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
        if resolution.candidates and _has_established_semantic_state(
            request.repository_id,
            resolution.candidates[0].subject,
            store=store,
            bounds=bounds,
        ):
            use_direct = True
    elif resolution.ambiguity is m.ResolutionAmbiguity.AMBIGUOUS:
        for candidate in resolution.candidates:
            if _has_established_semantic_state(
                request.repository_id,
                candidate.subject,
                store=store,
                bounds=bounds,
            ):
                use_direct = True
                break
    if use_direct:
        return resolution
    orientation, _ = _resolve_contextual_subjects(
        request.repository_id,
        request.target,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    if orientation.ambiguity is m.ResolutionAmbiguity.NOT_FOUND:
        return resolution
    return orientation


def _unresolved_explain_answer(
    request: SemanticExplainRequest,
    resolution: m.SubjectResolution,
    *,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
) -> m.SemanticAnswer:
    """The answer when the requested explain target does not resolve."""
    requirements = _answers.requirements_for_resolution(
        resolution,
        repository_id=request.repository_id,
        name_or_locator=request.target.name_or_locator,
    )
    if (
        resolution.ambiguity is m.ResolutionAmbiguity.AMBIGUOUS
        and resolution.bound_info.truncated
        and resolution.bound_info.truncated_category in ("inventory", "context")
    ):
        requirements = requirements + (
            _requirements.incomplete_scope(
                subject_or_claim=None,
                description=(
                    "path context not completely examined within "
                    "bounds; narrow the path or raise bounds"
                ),
                supporting_context=(),
            ),
        )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "ans",
            request.repository_id,
            request.target.name_or_locator or "unknown",
        ),
        intent=m.SemanticIntent.EXPLAIN,
        repository_state=state,
        subject_resolution=resolution,
        content=m.ExplainContent(),
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=None,
        continuation_token=None,
        state_explanation=("returned assertions: none",),
    )


def _selected_explain_scope(
    request: SemanticExplainRequest,
    subject: m.Subject,
) -> tuple[m.SemanticQuestionScope | None, tuple[str, ...]]:
    """Derive the service-owned scope for a narrowed question selection."""
    if request.question_selection is None:
        return None, ()
    # S4: narrowed selection derives service-owned scope; anchors pass verbatim
    # as question_terms into bounded discovery. Effective slice equals host
    # slice verbatim for EXPLAIN/AUTHORITY (discriminator empty). Full-scope
    # supply is rejected because the selection type carries only
    # slice/basis/anchors.
    from span.service.questions import derive_service_question as _derive

    return _derive(
        subject=subject,
        scope_root=subject.subject_id,
        question_class=m.SemanticQuestionClass.CQ_01,
        selection=request.question_selection,
        default_slice=m.QUESTION_CLASS_DEFAULT_SLICE[m.SemanticQuestionClass.CQ_01],
        default_basis="EXPLAIN question-local",
    )


def _explain_baseline(
    request: SemanticExplainRequest,
    subject: m.Subject,
    resolution: m.SubjectResolution,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...],
) -> m.SemanticAnswer | PendingInterpretation:
    """One baseline audit: answer when sufficient, else resume or start a unit."""
    establishment = _Establishment(
        op="explain",
        repository_id=request.repository_id,
        root=subject,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        seeds=authority_seeds,
        continuations=continuations,
        resolution=resolution,
    )
    if _baseline_sufficient(
        request.repository_id,
        subject.subject_id,
        store=store,
        evidence=evidence,
        bounds=bounds,
    ):
        return _baseline_answer(
            request.repository_id,
            subject,
            resolution,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            page_token=request.page_token,
        )
    # Reissue recovery: never restart the audit while admitted work exists —
    # persisted coverage determines the next unit.
    pending = _next_establishment_pending(establishment)
    if pending is not None:
        return pending
    if _cq01_established(
        request.repository_id,
        subject.subject_id,
        store=store,
    ):
        # Worklist exhausted but qualified (OPEN/similarly honest states
        # remain): serve the qualified answer, never a redundant second audit.
        return _baseline_answer(
            request.repository_id,
            subject,
            resolution,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
        )
    return _start_establishment(establishment)


def _explain_selected(
    request: SemanticExplainRequest,
    subject: m.Subject,
    resolution: m.SubjectResolution,
    scope: m.SemanticQuestionScope,
    anchors: tuple[str, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...],
) -> m.SemanticAnswer | PendingInterpretation:
    """Answer one deliberately selected question, or suspend its first unit."""
    try:
        existing = store.load_all_question_coverages(
            request.repository_id,
            scope.scope_root,
            (scope.subject,),
        )
    except Exception:
        existing = ()
    match = None
    for coverage in existing:
        if coverage.question is None:
            continue
        question = coverage.question
        if (
            question.scope_root == scope.scope_root
            and question.subject == scope.subject
            and question.question_class == scope.question_class
            and question.question_slice == scope.question_slice
        ):
            match = coverage
            break
    if match is None:
        task = prepare_interpretation_task(
            request.repository_id,
            subject,
            structural=structural,
            evidence=evidence,
            bounds=bounds,
            state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice=scope.question_slice,
            store=store,
            scope_root=scope.scope_root,
            question_class=scope.question_class,
            materiality_basis=scope.materiality_basis,
            question_terms=anchors,
        )
        return _suspend(
            op="explain",
            repository_id=request.repository_id,
            subject=subject,
            task=task,
            seeds=authority_seeds,
            bounds=bounds,
            state=state,
            resolution=resolution,
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=scope.question_slice,
            root_question=scope,
            question_selection=request.question_selection,
        )
    # Existing coverage found: answer filtered to the selected identity.
    import dataclasses as _dc

    from span.service.questions import (
        filter_views_by_scope as _filter_views,
    )

    answer = _compose_explain_answer(
        request.repository_id,
        subject,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        page_token=request.page_token,
        scope_root=subject.subject_id,
        question_key=f"{scope.question_class.value}:{scope.question_slice}",
    )
    filtered = _filter_views(answer.content.question_coverage, scope)
    return _dc.replace(
        answer, content=_dc.replace(answer.content, question_coverage=filtered)
    )


def _suspend_missing_explain_question(
    request: SemanticExplainRequest,
    subject: m.Subject,
    missing_question: m.SemanticQuestionScope,
    resolution: m.SubjectResolution,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...],
) -> PendingInterpretation:
    """Suspend the subject's default question-local unit when it has none."""
    task = prepare_interpretation_task(
        request.repository_id,
        subject,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=authority_seeds,
        operation_intent=m.SemanticIntent.EXPLAIN,
        question_slice=missing_question.question_slice,
        store=store,
        scope_root=missing_question.scope_root,
        question_class=missing_question.question_class,
        materiality_basis=missing_question.materiality_basis,
    )
    return _suspend(
        op="explain",
        repository_id=request.repository_id,
        subject=subject,
        task=task,
        seeds=authority_seeds,
        bounds=bounds,
        state=state,
        resolution=resolution,
        continuations=continuations,
        operation_intent="EXPLAIN",
        question_slice=missing_question.question_slice,
    )


def explain(
    request: SemanticExplainRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Orientation operation (plan §11.4).

    Returns an answer from stored/current semantics, or suspends with a
    pending-interpretation envelope when interpretation is missing
    (§11.12). Never interprets inline.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.EXPLAIN, request.repository_id, bounds, state
        )
    resolution = _explain_resolution(
        request,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        return _unresolved_explain_answer(
            request, resolution, state=state, bounds=bounds
        )
    subject = resolution.candidates[0].subject
    # S4 §5.4: question_selection and establish_baseline together rejected.
    if request.question_selection is not None and request.establish_baseline:
        raise ValueError(
            "question_selection and explain(establish_baseline=True) "
            "together are rejected; use one mode: baseline audit or "
            "narrowed question selection"
        )
    selected_scope, anchors = _selected_explain_scope(request, subject)
    if request.establish_baseline:
        return _explain_baseline(
            request,
            subject,
            resolution,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
            bounds=bounds,
            state=state,
            authority_seeds=authority_seeds,
        )
    if selected_scope is not None:
        return _explain_selected(
            request,
            subject,
            resolution,
            selected_scope,
            anchors,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
            bounds=bounds,
            state=state,
            authority_seeds=authority_seeds,
        )
    # S4: the default path uses primary-question coverage, never a
    # claim-existence shortcut.
    missing_question = _question_local_missing(
        request.repository_id,
        subject,
        m.SemanticIntent.EXPLAIN,
        store=store,
        evidence=evidence,
        bounds=bounds,
    )
    if missing_question is not None:
        return _suspend_missing_explain_question(
            request,
            subject,
            missing_question,
            resolution,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
            bounds=bounds,
            state=state,
            authority_seeds=authority_seeds,
        )
    return _compose_explain_answer(
        request.repository_id,
        subject,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        page_token=request.page_token,
        scope_root=subject.subject_id,
    )
