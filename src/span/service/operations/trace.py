"""Span service trace operation (plan §11.6; v0.6 §14 Amendment A-01).

Bounded structural-semantic traversal with resume. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.continuations import SuspendedOperation

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    _conflicts_for,
    _select_answer_items,
    coverage_counts_for,
    state_explanation_for,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.freshness import (
    preflight,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.questions import (
    _paged_question_views,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    SemanticTraceRequest,
)
from span.service.resolution import (
    _has_established_semantic_state,
    _load_subject_state,
    _resolve_contextual_subjects,
    _resolve_exact_subject,
    _resolve_query_subject,
)

__all__ = [
    "_trace_endpoints",
    "_trace_drive",
    "_compose_trace_answer",
    "trace",
    "_resume_trace",
]


def _trace_endpoints(
    current: str,
    *,
    rel: m.SemanticRelationship | None = None,
    edge: m.StructuralEdge | None = None,
    direction: StructuralDirection,
) -> list[m.SubjectId]:
    """Traversal endpoints for one path segment under a direction."""
    if rel is not None:
        if direction is StructuralDirection.DOWNSTREAM:
            return [rel.target] if rel.source.canonical_locator == current else []
        if direction is StructuralDirection.UPSTREAM:
            return [rel.source] if rel.target.canonical_locator == current else []
        return [rel.source, rel.target]
    assert edge is not None
    if direction is StructuralDirection.DOWNSTREAM:
        return [edge.target] if edge.source.canonical_locator == current else []
    if direction is StructuralDirection.UPSTREAM:
        return [edge.source] if edge.target.canonical_locator == current else []
    return [edge.source, edge.target]


def _trace_drive(
    repository_id: str,
    target: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    direction: StructuralDirection,
    relationship_filter: tuple[m.RelationshipKind, ...] | None,
    boundary_only: bool,
    seeds: tuple[m.EvidenceRef, ...],
    suspended: tuple[m.SubjectId, ...],
    page_token: str | None = None,
    question_selection: m.SemanticQuestionSelection | None = None,
    root_subject: m.SubjectId | None = None,
) -> m.SemanticAnswer | PendingInterpretation:
    """Bounded iterative frontier expansion (plan §8.6) with suspension.

    S4 §5.4: gates interpretation on the relevant question's effective
    coverage (not claim/relationship existence). Carries an explicitly
    selected bounded question through discovery, interpretation,
    persistence, and readback. Anchors pass verbatim as question_terms.
    Every resumption and new frontier task forwards the retained
    selection; later frontiers never re-derive anchors by mining prose.

    Expands one deterministic frontier at a time. Resume restarts the
    deterministic walk, so each subject is requested at most once and
    the walk always terminates.

    Paging (I S4 pgq): `page_token` windows the target subject's
    initial state load only; frontier expansion loads proceed unpaged.
    Page deep results through narrower targets.
    """
    from span.service.questions import (
        effective_trace_slice as _eff_slice,
    )

    _root = root_subject or target.subject_id
    # Derive effective question identity for the primary target.
    if question_selection is not None:
        _host_slice = question_selection.question_slice
        _basis = question_selection.materiality_basis or "TRACE question-local"
        _anchors = tuple(question_selection.question_anchors)
    else:
        _host_slice = target.subject_id.canonical_locator
        _basis = "TRACE question-local"
        _anchors = ()
    _effective_slice = _eff_slice(
        _host_slice, direction, relationship_filter, boundary_only
    )
    _primary_scope = m.SemanticQuestionScope(
        scope_root=_root,
        subject=target.subject_id,
        question_class=m.SemanticQuestionClass.CQ_04,
        question_slice=_effective_slice,
        materiality_basis=_basis,
    )
    kinds = (
        tuple(relationship_filter)
        if relationship_filter is not None
        else tuple(m.RelationshipKind)
    )
    if boundary_only:
        kinds = tuple(k for k in kinds if k is m.RelationshipKind.CROSSES_BOUNDARY)
    visited: list[m.SubjectId] = []
    rels: list[m.SemanticRelationship] = []
    claims: list[m.SemanticClaim] = []
    sedges: list[m.StructuralEdge] = []
    structural_coverage = m.ScopeCoverage.VERIFIED
    structural_details: list[str | None] = []
    queue: list[tuple[m.SubjectId, int]] = [(target.subject_id, 0)]
    truncated_walk = False
    target_windowed = False
    while queue and len(rels) + len(sedges) < bounds.max_results:
        sid, depth = queue.pop(0)
        locator = sid.canonical_locator
        if sid in visited:
            continue
        visited.append(sid)
        window = None if target_windowed else page_token
        target_windowed = True
        loaded_claims, loaded_rels, _, _ = _load_subject_state(
            repository_id,
            sid,
            store=store,
            bounds=bounds,
            direction=direction,
            page_token=window,
        )
        # S4: question-aware gate (Addendum B B.7). The frontier
        # subject's derived question (original root, class, exact slice,
        # subject changed) needs recorded non-PENDING coverage; recorded
        # PENDING is admitted-but-unexamined. Claim existence alone
        # never counts.
        _frontier_scope = m.SemanticQuestionScope(
            scope_root=_root,
            subject=sid,
            question_class=m.SemanticQuestionClass.CQ_04,
            question_slice=_effective_slice,
            materiality_basis=_basis,
        )
        try:
            _covs = store.load_all_question_coverages(
                repository_id,
                _root,
                (sid,),
            )
        except Exception:
            _covs = ()
        _covered = any(
            _c.question is not None
            and _c.question.scope_root == _root
            and _c.question.subject == sid
            and _c.question.question_class is m.SemanticQuestionClass.CQ_04
            and _c.question.question_slice == _effective_slice
            and _c.disposition is not m.SemanticQuestionDisposition.PENDING
            for _c in _covs
        )
        if not _covered and sid not in suspended:
            # Resolve semantic-only frontier subjects through shared
            # resolver rather than structural identity alone.
            full = _resolve_exact_subject(
                repository_id, sid, structural=structural, bounds=bounds
            )
            if full is None:
                try:
                    _stored = store.load_subjects(repository_id, (sid,))
                except Exception:
                    _stored = ()
                full = _stored[0] if _stored else None
            if full is not None:
                task = prepare_interpretation_task(
                    repository_id,
                    full,
                    structural=structural,
                    evidence=evidence,
                    bounds=bounds,
                    state=state,
                    authority_seeds=seeds,
                    operation_intent=m.SemanticIntent.TRACE,
                    question_slice=_effective_slice,
                    store=store,
                    scope_root=_root,
                    question_class=m.SemanticQuestionClass.CQ_04,
                    materiality_basis=_basis,
                    question_terms=_anchors,
                )
                return _suspend(
                    op="trace",
                    repository_id=repository_id,
                    subject=full,
                    task=task,
                    seeds=seeds,
                    bounds=bounds,
                    state=state,
                    resolution=resolution,
                    scope=(target,),
                    suspended=suspended + (sid,),
                    operation_intent="TRACE",
                    question_slice=_effective_slice,
                    trace_direction=direction.value,
                    trace_filter=(
                        tuple(relationship_filter)
                        if relationship_filter is not None
                        else ()
                    ),
                    trace_filter_set=relationship_filter is not None,
                    trace_boundary=boundary_only,
                    continuations=continuations,
                    root_question=_primary_scope,
                    question_selection=question_selection,
                )
        for claim in loaded_claims:
            claims.append(claim)
        for rel in loaded_rels:
            if rel.kind in kinds:
                rels.append(rel)
        if depth >= bounds.max_depth:
            continue
        page = structural.edges(repository_id, sid, (), direction, bounds)
        if page.coverage is not m.ScopeCoverage.VERIFIED:
            structural_coverage = m.ScopeCoverage.UNVERIFIED
        structural_details.append(page.coverage_detail)
        for edge in page.items:
            sedges.append(edge)
            for endpoint in _trace_endpoints(locator, edge=edge, direction=direction):
                queue.append((endpoint, depth + 1))
        for rel in loaded_rels:
            for endpoint in _trace_endpoints(locator, rel=rel, direction=direction):
                queue.append((endpoint, depth + 1))
    if queue:
        truncated_walk = True
    return _compose_trace_answer(
        repository_id,
        target,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        relationships=tuple(rels),
        claims=tuple(claims),
        structural_edges=tuple(sedges[: bounds.max_results]),
        truncated_walk=truncated_walk,
        structural_coverage=(
            structural_coverage,
            _answers.merge_coverage_detail(tuple(structural_details)),
        ),
    )


def _compose_trace_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    relationships: tuple[m.SemanticRelationship, ...],
    claims: tuple[m.SemanticClaim, ...],
    structural_edges: tuple[m.StructuralEdge, ...],
    truncated_walk: bool,
    structural_coverage: tuple[m.ScopeCoverage, str | None] = (
        m.ScopeCoverage.VERIFIED,
        None,
    ),
    page_token: str | None = None,
) -> m.SemanticAnswer:
    ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in claims
    ) + tuple(_relationship_ref(r) for r in relationships)
    updates = preflight(
        repository_id, ids, evidence=evidence, store=store, bounds=bounds
    )
    fresh_by_id = {u.semantic_id.id.value: u.freshness for u in updates}

    def _fresh_claim(claim: m.SemanticClaim) -> m.SemanticClaim:
        freshness = fresh_by_id.get(claim.claim_id.value)
        if freshness is None:
            return claim
        return m.SemanticClaim(
            claim_id=claim.claim_id,
            subject=claim.subject,
            kind=claim.kind,
            value=claim.value,
            assertion_nature=claim.assertion_nature,
            evidence=claim.evidence,
            authority=claim.authority,
            trust=claim.trust,
            freshness=freshness,
            basis=claim.basis,
        )

    def _fresh_rel(rel: m.SemanticRelationship) -> m.SemanticRelationship:
        freshness = fresh_by_id.get(rel.relationship_id.value)
        if freshness is None:
            return rel
        return m.SemanticRelationship(
            relationship_id=rel.relationship_id,
            source=rel.source,
            kind=rel.kind,
            target=rel.target,
            assertion_nature=rel.assertion_nature,
            evidence=rel.evidence,
            authority=rel.authority,
            trust=rel.trust,
            freshness=freshness,
            basis=rel.basis,
        )

    claims = tuple(_fresh_claim(c) for c in claims)
    relationships = tuple(_fresh_rel(r) for r in relationships)
    conflicts_all = _conflicts_for(repository_id, claims, relationships, store=store)
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(claims, relationships, conflicts_all, bounds.max_results)
    )
    boundary_ids: list[m.SubjectId] = []
    lifecycle_refs: list[m.ClaimRef | m.RelationshipRef] = []
    for claim in kept_claims:
        if claim.kind is m.ClaimKind.LIFECYCLE_STATE:
            lifecycle_refs.append(_claim_ref(claim))
    for rel in kept_rels:
        if rel.kind in (
            m.RelationshipKind.TRANSITIONS_TO,
            m.RelationshipKind.PERSISTS_AT,
        ):
            lifecycle_refs.append(_relationship_ref(rel))
        if rel.kind is m.RelationshipKind.CROSSES_BOUNDARY:
            boundary_ids.extend((rel.source, rel.target))
    if boundary_ids:
        loaded = store.load_subjects(repository_id, tuple(dict.fromkeys(boundary_ids)))
        boundary_ids = [
            s.subject_id
            for s in loaded
            if s.subject_id.subject_kind is m.SubjectKind.BOUNDARY
        ] + [i for i in boundary_ids]
        seen: set[str] = set()
        deduped = []
        for i in boundary_ids:
            if i.canonical_locator not in seen:
                seen.add(i.canonical_locator)
                deduped.append(i)
        boundary_ids = deduped
    requirements: list[m.ResolutionRequirement] = []
    structural_requirement = _answers.structural_coverage_requirement(
        "trace", structural_coverage[0], structural_coverage[1]
    )
    if structural_requirement is not None:
        requirements.append(structural_requirement)
    if resolution is not None:
        requirements.extend(_answers.requirements_for_resolution(resolution))
    for rel in kept_rels:
        requirements.extend(_answers.requirements_for_relationship(rel))
    for claim in kept_claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    (kept_boundary, kept_edges), truncated, category, token = _answers.truncate_fields(
        (
            (tuple(boundary_ids), "boundary_context"),
            (structural_edges, "structural_edges"),
        ),
        max(0, bounds.max_results - len(kept_conf) - len(kept_rels)),
    )
    truncated = truncated or items_truncated
    if category is None:
        category = items_category
    sid = subject.subject_id
    views, _, qremaining = _paged_question_views(
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
    content = m.TraceContent(
        relationships=kept_rels,  # type: ignore[arg-type]
        structural_edges=kept_edges,  # type: ignore[arg-type]
        boundary_context=kept_boundary,  # type: ignore[arg-type]
        lifecycle_context=tuple(lifecycle_refs),
        claims=kept_claims,
        conflicts=kept_conf,
        question_coverage=views,
    )
    returned = (
        len(kept_conf)
        + len(kept_rels)
        + len(lifecycle_refs)
        + len(kept_boundary)
        + len(kept_edges)
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "trc", repository_id, subject.subject_id.canonical_locator
        ),
        intent=m.SemanticIntent.TRACE,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for r in kept_rels for ref in r.evidence),
        resolution_requirements=tuple(requirements),
        bounds=bounds,
        withheld_category=category or ("walk" if truncated_walk else None),
        continuation_token=None,
        state_explanation=state_explanation_for(
            tuple(kept_claims),
            tuple(kept_rels),
            coverage=coverage_counts_for(views),
            bounds=(bounds.max_results, truncated or truncated_walk),
        ),
    )


def trace(
    request: SemanticTraceRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Context operation (plan §11.6): producers/carriers/consumers,
    explicit semantic-vs-structural path segments, boundary crossings,
    representations/contracts, transformation owners, lifecycle
    transitions and persistence points. Structural paths stay possible
    routes — never runtime facts or authority. Suspends via §11.12 when
    frontier interpretation is missing; never interprets inline.

    Paging (plan I-39): `page_token` windows the target subject's
    initial state load only; frontier expansion loads proceed unpaged.
    Page deep results through narrower targets."""
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.TRACE, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    if request.target.exact_subject_id is None:
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
        if not use_direct:
            _, trace_root = _resolve_contextual_subjects(
                request.repository_id,
                request.target,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=bounds,
            )
            if trace_root.ambiguity is not m.ResolutionAmbiguity.NOT_FOUND:
                resolution = trace_root
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
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
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
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
                "trc",
                request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.TRACE,
            repository_state=state,
            subject_resolution=resolution,
            content=m.TraceContent(),
            evidence=(),
            resolution_requirements=requirements,
            bounds=bounds,
            withheld_category=None,
            continuation_token=None,
        )
    return _trace_drive(
        request.repository_id,
        resolution.candidates[0].subject,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        bounds=bounds,
        state=state,
        direction=request.direction,
        relationship_filter=request.relationship_filter,
        boundary_only=request.boundary_only,
        seeds=authority_seeds,
        suspended=(),
        page_token=request.page_token,
        question_selection=request.question_selection,
        root_subject=resolution.candidates[0].subject.subject_id,
    )


def _resume_trace(
    record: SuspendedOperation,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationStore,
) -> m.SemanticAnswer | PendingInterpretation:
    target = record.scope[0] if record.scope else record.subject
    resumed = record.suspended
    if record.subject.subject_id not in resumed:
        resumed = resumed + (record.subject.subject_id,)
    return _trace_drive(
        record.repository_id,
        target,
        record.resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        bounds=bounds,
        state=state,
        direction=StructuralDirection(record.trace_direction or "BOTH"),
        relationship_filter=(record.trace_filter if record.trace_filter_set else None),
        boundary_only=record.trace_boundary,
        seeds=record.seeds,
        suspended=resumed,
        question_selection=record.question_selection,
        root_subject=(
            record.root_question.scope_root
            if record.root_question is not None
            else target.subject_id
        ),
    )
