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
from span.shell.agent_exchange.continuations import ContinuationStore

from span.service.answers import (
    _answer_id,
    _bound_info,
    _conflicts_for,
    _next_service_token,
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
    '_compose_authority_answer',
    'authority',
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
) -> m.SemanticAnswer:
    sid = subject.subject_id
    claims, relationships, claims_token, rels_token = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds,
        page_token=page_token,
    )
    claims, relationships = _refresh_view(
        repository_id, claims, relationships,
        evidence=evidence, store=store, bounds=bounds,
    )
    bindings = tuple(
        claim.authority for claim in claims if claim.authority is not None
    ) + tuple(
        rel.authority for rel in relationships if rel.authority is not None
    )
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
    conflicts = _conflicts_for(
        repository_id, claims, relationships, store=store
    )
    requirements = (
        list(_answers.requirements_for_resolution(resolution))
        if resolution is not None
        else []
    )
    for claim in claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    unresolved_all = tuple(
        r for r in requirements
        if r.kind is m.ResolutionKind.MISSING_AUTHORITY
    )
    (kept_conflicts, kept_unresolved, kept_bindings, kept_super, kept_prec), truncated, category, token = (
        _answers.truncate_fields(
            (
                (conflicts, "conflicts"),
                (unresolved_all, "unresolved"),
                (bindings, "bindings"),
                (supersession, "supersession"),
                (precedence, "precedence"),
            ),
            bounds.max_results,
        )
    )
    views, qshown, qremaining = _paged_question_views(
        repository_id, sid, (sid,),
        store=store, bounds=bounds, page_token=page_token,
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
        unresolved=kept_unresolved,  # type: ignore[arg-type]
        question_coverage=views,
    )
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "aut", repository_id, sid.canonical_locator
        ),
        intent=m.SemanticIntent.AUTHORITY,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(
            binding.evidence_ref for binding in kept_bindings
        ),
        resolution_requirements=tuple(requirements),
        bound_info=_bound_info(
            bounds, len(kept_bindings), truncated, category,
            _next_service_token(
                page_token, claims, relationships, claims, relationships,
                claims_token, rels_token,
                questions_skip=qshown,
                questions_remaining=qremaining,
            ) or token,
        ),
    )

def authority(
    request: SemanticAuthorityRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Authority/evidence operation (plan §11.7): governing sources,
    kind/status/applicability, supersession/precedence, conflicts
    side-by-side, missing authority as unresolved. Authority is never
    inferred — only explicit bindings are returned. Suspends via §11.12
    when interpretation is missing; never interprets inline."""
    if isinstance(request.target, m.ClaimRef):
        bounds = _resolve_bounds(request.bounds, hook=False)
        state = structural.repository_state(request.repository_id)
        try:
            (item,) = store.load_by_refs(
                request.repository_id, (request.target,)
            )
        except ValueError as exc:
            raise AuthorityTargetError(str(exc)) from None
        if not isinstance(item, m.SemanticClaim):
            raise AuthorityTargetError("claim ref did not resolve to a claim")
        subjects = store.load_subjects(
            request.repository_id, (item.subject,)
        )
        if not subjects:
            raise AuthorityTargetError("claim subject is not indexed")
        return _compose_authority_answer(
            request.repository_id, subjects[0], None,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.AUTHORITY, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id, request.target, structural=structural,
        store=store, bounds=bounds,
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        requirements = _answers.requirements_for_resolution(
            resolution, repository_id=request.repository_id,
            name_or_locator=request.target.name_or_locator,
        )
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "aut", request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.AUTHORITY,
            repository_state=state,
            subject_resolution=resolution,
            content=m.AuthorityContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    subject = resolution.candidates[0].subject
    missing_question = _question_local_missing(
        request.repository_id, subject, m.SemanticIntent.AUTHORITY,
        store=store, evidence=evidence, bounds=bounds,
    )
    if missing_question is not None:
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.AUTHORITY,
            question_slice=missing_question.question_slice,
            store=store,
            scope_root=missing_question.scope_root,
            question_class=missing_question.question_class,
            materiality_basis=missing_question.materiality_basis,
        )
        return _suspend(
            op="authority", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
            operation_intent="AUTHORITY",
            question_slice=missing_question.question_slice,
        )
    return _compose_authority_answer(
        request.repository_id, subject, resolution,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state, page_token=request.page_token,
    )
