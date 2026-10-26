"""Span service authority operation (plan §11.6; v0.6 §14 Amendment A-01).

Subject-scoped authority lookup. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    _conflicts_for,
    _next_service_token,
    _query_digest,
    _validate_service_token,
    coverage_counts_for,
    state_explanation_for,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.freshness import (
    _refresh_view,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.questions import (
    _paged_question_views,
    _question_local_missing,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    AuthorityTargetError,
    SemanticAuthorityRequest,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_query_subject,
)

__all__ = [
    "_compose_authority_answer",
    "authority",
]


def _compose_authority_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    page_token: str | None = None,
    question_key: str = "",
    target_key: str | None = None,
) -> m.SemanticAnswer:
    sid = subject.subject_id
    _target = target_key or (f"{sid.subject_kind.value}:{sid.canonical_locator}")
    _digest = _query_digest(
        "AUTHORITY",
        repository_id,
        _target,
        question_key,
        bounds,
    )
    _validate_service_token(page_token, _digest)
    claims, relationships, claims_token, rels_token = _load_subject_state(
        repository_id,
        sid,
        store=store,
        bounds=bounds,
        page_token=page_token,
    )
    claims, relationships = _refresh_view(
        repository_id,
        claims,
        relationships,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    bindings = tuple(
        claim.authority for claim in claims if claim.authority is not None
    ) + tuple(rel.authority for rel in relationships if rel.authority is not None)
    supersession = tuple(
        m.RelationshipRef(id=rel.relationship_id)
        for rel in relationships
        if rel.kind is m.RelationshipKind.SUPERSEDES
    )
    precedence = tuple(
        binding.declared_precedence
        for binding in bindings
        if binding.declared_precedence is not None
    )
    conflicts = _conflicts_for(repository_id, claims, relationships, store=store)
    requirements = (
        list(_answers.requirements_for_resolution(resolution))
        if resolution is not None
        else []
    )
    for claim in claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    unresolved_all = tuple(
        r for r in requirements if r.kind is m.ResolutionKind.MISSING_AUTHORITY
    )
    (
        (kept_conflicts, kept_unresolved, kept_bindings, kept_super, kept_prec),
        truncated,
        category,
        token,
    ) = _answers.truncate_fields(
        (
            (conflicts, "conflicts"),
            (unresolved_all, "unresolved"),
            (bindings, "bindings"),
            (supersession, "supersession"),
            (precedence, "precedence"),
        ),
        bounds.max_results,
    )
    views, qshown, qremaining = _paged_question_views(
        repository_id,
        sid,
        (sid,),
        store=store,
        bounds=bounds,
        page_token=page_token,
        evidence=evidence,
    )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    content = m.AuthorityContent(
        governing_bindings=kept_bindings,  # type: ignore[arg-type]
        supersession=kept_super,  # type: ignore[arg-type]
        precedence=kept_prec,  # type: ignore[arg-type]
        claims=claims,
        relationships=relationships,
        conflicts=kept_conflicts,  # type: ignore[arg-type]
        question_coverage=views,
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("aut", repository_id, sid.canonical_locator),
        intent=m.SemanticIntent.AUTHORITY,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(binding.evidence_ref for binding in kept_bindings),
        resolution_requirements=tuple(requirements),
        bounds=bounds,
        withheld_category=category,
        continuation_token=_next_service_token(
            page_token,
            claims,
            relationships,
            claims,
            relationships,
            claims_token,
            rels_token,
            questions_skip=qshown,
            questions_remaining=qremaining,
            query_digest=_digest,
        ),
        state_explanation=state_explanation_for(
            tuple(claims),
            tuple(relationships),
            coverage=coverage_counts_for(views),
            bounds=(bounds.max_results, truncated),
        ),
    )


def _authority_claim_answer(
    request: SemanticAuthorityRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> m.SemanticAnswer:
    """Answer one exact claim reference without question-scoped examination."""
    if request.question_selection is not None:
        raise AuthorityTargetError(
            "authority(target=ClaimRef, question_selection=...) is "
            "rejected: the ClaimRef branch loads one exact claim and "
            "performs no question-scoped examination"
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    try:
        (item,) = store.load_by_refs(request.repository_id, (request.target,))
    except ValueError as exc:
        raise AuthorityTargetError(str(exc)) from None
    if not isinstance(item, m.SemanticClaim):
        raise AuthorityTargetError("claim ref did not resolve to a claim")
    subjects = store.load_subjects(request.repository_id, (item.subject,))
    if not subjects:
        raise AuthorityTargetError("claim subject is not indexed")
    return _compose_authority_answer(
        request.repository_id,
        subjects[0],
        None,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        target_key=f"claim:{request.target.id.value}",
    )


def _unresolved_authority_answer(
    request: SemanticAuthorityRequest,
    resolution: m.SubjectResolution,
    *,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
) -> m.SemanticAnswer:
    """The answer when the requested authority target does not resolve."""
    requirements = _answers.requirements_for_resolution(
        resolution,
        repository_id=request.repository_id,
        name_or_locator=request.target.name_or_locator,
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "aut",
            request.repository_id,
            request.target.name_or_locator or "unknown",
        ),
        intent=m.SemanticIntent.AUTHORITY,
        repository_state=state,
        subject_resolution=resolution,
        content=m.AuthorityContent(),
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=None,
        continuation_token=None,
    )


def _selected_authority_scope(
    request: SemanticAuthorityRequest,
    subject: m.Subject,
) -> tuple[m.SemanticQuestionScope | None, tuple[str, ...]]:
    """Derive the service-owned scope for a narrowed question selection."""
    if request.question_selection is None:
        return None, ()
    # S4 §5.4: host slice/basis/anchors only; service derives root/subject/class.
    # Verbatim anchors forwarded as question_terms; the EXPLAIN/AUTHORITY
    # discriminator is empty.
    from span.service.questions import derive_service_question as _derive

    return _derive(
        subject=subject,
        scope_root=subject.subject_id,
        question_class=m.SemanticQuestionClass.CQ_06,
        selection=request.question_selection,
        default_slice=m.QUESTION_CLASS_DEFAULT_SLICE[m.SemanticQuestionClass.CQ_06],
        default_basis="AUTHORITY question-local",
    )


def _authority_selected(
    request: SemanticAuthorityRequest,
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
    found = any(
        coverage.question is not None
        and coverage.question.scope_root == scope.scope_root
        and coverage.question.subject == scope.subject
        and coverage.question.question_class == scope.question_class
        and coverage.question.question_slice == scope.question_slice
        for coverage in existing
    )
    if not found:
        task = prepare_interpretation_task(
            request.repository_id,
            subject,
            structural=structural,
            evidence=evidence,
            bounds=bounds,
            state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.AUTHORITY,
            question_slice=scope.question_slice,
            store=store,
            scope_root=scope.scope_root,
            question_class=scope.question_class,
            materiality_basis=scope.materiality_basis,
            question_terms=anchors,
        )
        return _suspend(
            op="authority",
            repository_id=request.repository_id,
            subject=subject,
            task=task,
            seeds=authority_seeds,
            bounds=bounds,
            state=state,
            resolution=resolution,
            continuations=continuations,
            operation_intent="AUTHORITY",
            question_slice=scope.question_slice,
            root_question=scope,
            question_selection=request.question_selection,
        )
    import dataclasses as _dc

    from span.service.questions import (
        filter_views_by_scope as _filter_views,
    )

    answer = _compose_authority_answer(
        request.repository_id,
        subject,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        page_token=request.page_token,
        question_key=f"{scope.question_class.value}:{scope.question_slice}",
    )
    filtered = _filter_views(answer.content.question_coverage, scope)
    return _dc.replace(
        answer, content=_dc.replace(answer.content, question_coverage=filtered)
    )


def _suspend_missing_authority_question(
    request: SemanticAuthorityRequest,
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
        operation_intent=m.SemanticIntent.AUTHORITY,
        question_slice=missing_question.question_slice,
        store=store,
        scope_root=missing_question.scope_root,
        question_class=missing_question.question_class,
        materiality_basis=missing_question.materiality_basis,
    )
    return _suspend(
        op="authority",
        repository_id=request.repository_id,
        subject=subject,
        task=task,
        seeds=authority_seeds,
        bounds=bounds,
        state=state,
        resolution=resolution,
        continuations=continuations,
        operation_intent="AUTHORITY",
        question_slice=missing_question.question_slice,
    )


def authority(
    request: SemanticAuthorityRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Authority/evidence operation (plan §11.7): governing sources,
    kind/status/applicability, supersession/precedence, conflicts
    side-by-side, missing authority as unresolved. Authority is never
    inferred — only explicit bindings are returned. Suspends via §11.12
    when interpretation is missing; never interprets inline."""
    if isinstance(request.target, m.ClaimRef):
        return _authority_claim_answer(
            request,
            structural=structural,
            evidence=evidence,
            store=store,
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.AUTHORITY, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        return _unresolved_authority_answer(
            request, resolution, state=state, bounds=bounds
        )
    subject = resolution.candidates[0].subject
    selected_scope, anchors = _selected_authority_scope(request, subject)
    if selected_scope is not None:
        return _authority_selected(
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
    missing_question = _question_local_missing(
        request.repository_id,
        subject,
        m.SemanticIntent.AUTHORITY,
        store=store,
        evidence=evidence,
        bounds=bounds,
    )
    if missing_question is not None:
        return _suspend_missing_authority_question(
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
    return _compose_authority_answer(
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
