"""Span service trace operation (plan §11.6; v0.6 §14 Amendment A-01).

Bounded structural-semantic traversal with resume. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_exact_subject,
)


from span.service.operations.trace.answer import (
    _compose_trace_answer,
)


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


@_dataclasses.dataclass
class _TraceQuestion:
    """The discriminated CQ-04 question and the edge kinds one walk reads."""

    scope: m.SemanticQuestionScope
    slice: str
    root: m.SubjectId
    basis: str
    anchors: tuple[str, ...]
    kinds: tuple[m.RelationshipKind, ...]


def _trace_question(
    target: m.Subject,
    *,
    direction: StructuralDirection,
    relationship_filter: tuple[m.RelationshipKind, ...] | None,
    boundary_only: bool,
    question_selection: m.SemanticQuestionSelection | None,
    root_subject: m.SubjectId | None,
) -> _TraceQuestion:
    """Derive the exact CQ-04 identity and the relationship kinds to read."""
    from span.service.questions import (
        effective_trace_slice as _eff_slice,
    )

    root = root_subject or target.subject_id
    if question_selection is not None:
        host_slice = question_selection.question_slice
        basis = question_selection.materiality_basis or "TRACE question-local"
        anchors = tuple(question_selection.question_anchors)
    else:
        host_slice = target.subject_id.canonical_locator
        basis = "TRACE question-local"
        anchors = ()
    effective_slice = _eff_slice(
        host_slice, direction, relationship_filter, boundary_only
    )
    kinds = (
        tuple(relationship_filter)
        if relationship_filter is not None
        else tuple(m.RelationshipKind)
    )
    if boundary_only:
        kinds = tuple(
            kind for kind in kinds if kind is m.RelationshipKind.CROSSES_BOUNDARY
        )
    return _TraceQuestion(
        scope=m.SemanticQuestionScope(
            scope_root=root,
            subject=target.subject_id,
            question_class=m.SemanticQuestionClass.CQ_04,
            question_slice=effective_slice,
            materiality_basis=basis,
        ),
        slice=effective_slice,
        root=root,
        basis=basis,
        anchors=anchors,
        kinds=kinds,
    )


def _has_recorded_trace_coverage(
    repository_id: str,
    *,
    root: m.SubjectId,
    subject_id: m.SubjectId,
    question_slice: str,
    store: SemanticStore,
) -> bool:
    """Recorded non-PENDING coverage for the exact frontier question (B.7)."""
    try:
        coverages = store.load_all_question_coverages(
            repository_id,
            root,
            (subject_id,),
        )
    except Exception:
        coverages = ()
    return any(
        coverage.question is not None
        and coverage.question.scope_root == root
        and coverage.question.subject == subject_id
        and coverage.question.question_class is m.SemanticQuestionClass.CQ_04
        and coverage.question.question_slice == question_slice
        and coverage.disposition is not m.SemanticQuestionDisposition.PENDING
        for coverage in coverages
    )


def _trace_frontier_suspension(
    repository_id: str,
    target: m.Subject,
    question: _TraceQuestion,
    frontier_subject_id: m.SubjectId,
    resolution: m.SubjectResolution | None,
    suspended: tuple[m.SubjectId, ...],
    *,
    direction: StructuralDirection,
    relationship_filter: tuple[m.RelationshipKind, ...] | None,
    boundary_only: bool,
    question_selection: m.SemanticQuestionSelection | None,
    seeds: tuple[m.EvidenceRef, ...],
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
) -> PendingInterpretation | None:
    """Suspend one unexamined frontier subject, resolving it semantically first."""
    full = _resolve_exact_subject(
        repository_id, frontier_subject_id, structural=structural, bounds=bounds
    )
    if full is None:
        try:
            stored = store.load_subjects(repository_id, (frontier_subject_id,))
        except Exception:
            stored = ()
        full = stored[0] if stored else None
    if full is None:
        return None
    task = prepare_interpretation_task(
        repository_id,
        full,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=seeds,
        operation_intent=m.SemanticIntent.TRACE,
        question_slice=question.slice,
        store=store,
        scope_root=question.root,
        question_class=m.SemanticQuestionClass.CQ_04,
        materiality_basis=question.basis,
        question_terms=question.anchors,
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
        suspended=suspended + (frontier_subject_id,),
        operation_intent="TRACE",
        question_slice=question.slice,
        trace_direction=direction.value,
        trace_filter=(
            tuple(relationship_filter) if relationship_filter is not None else ()
        ),
        trace_filter_set=relationship_filter is not None,
        trace_boundary=boundary_only,
        continuations=continuations,
        root_question=question.scope,
        question_selection=question_selection,
    )


@_dataclasses.dataclass
class _TraceWalk:
    """One deterministic frontier walk's accumulated readback."""

    relationships: tuple[m.SemanticRelationship, ...]
    claims: tuple[m.SemanticClaim, ...]
    structural_edges: tuple[m.StructuralEdge, ...]
    truncated: bool
    coverage: tuple[m.ScopeCoverage, str | None]


def _trace_walk(
    repository_id: str,
    target: m.Subject,
    question: _TraceQuestion,
    resolution: m.SubjectResolution | None,
    suspended: tuple[m.SubjectId, ...],
    *,
    direction: StructuralDirection,
    relationship_filter: tuple[m.RelationshipKind, ...] | None,
    boundary_only: bool,
    question_selection: m.SemanticQuestionSelection | None,
    seeds: tuple[m.EvidenceRef, ...],
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
    page_token: str | None,
) -> _TraceWalk | PendingInterpretation:
    """Expand one deterministic frontier at a time, suspending missing work."""
    visited: list[m.SubjectId] = []
    rels: list[m.SemanticRelationship] = []
    claims: list[m.SemanticClaim] = []
    structural_edges: list[m.StructuralEdge] = []
    structural_coverage = m.ScopeCoverage.VERIFIED
    structural_details: list[str | None] = []
    queue: list[tuple[m.SubjectId, int]] = [(target.subject_id, 0)]
    target_windowed = False
    while queue and len(rels) + len(structural_edges) < bounds.max_results:
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
        if sid not in suspended and not _has_recorded_trace_coverage(
            repository_id,
            root=question.root,
            subject_id=sid,
            question_slice=question.slice,
            store=store,
        ):
            pending = _trace_frontier_suspension(
                repository_id,
                target,
                question,
                sid,
                resolution,
                suspended,
                direction=direction,
                relationship_filter=relationship_filter,
                boundary_only=boundary_only,
                question_selection=question_selection,
                seeds=seeds,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=bounds,
                state=state,
                continuations=continuations,
            )
            if pending is not None:
                return pending
        for claim in loaded_claims:
            claims.append(claim)
        for rel in loaded_rels:
            if rel.kind in question.kinds:
                rels.append(rel)
        if depth >= bounds.max_depth:
            continue
        page = structural.edges(repository_id, sid, (), direction, bounds)
        if page.coverage is not m.ScopeCoverage.VERIFIED:
            structural_coverage = m.ScopeCoverage.UNVERIFIED
        structural_details.append(page.coverage_detail)
        for edge in page.items:
            structural_edges.append(edge)
            for endpoint in _trace_endpoints(locator, edge=edge, direction=direction):
                queue.append((endpoint, depth + 1))
        for rel in loaded_rels:
            for endpoint in _trace_endpoints(locator, rel=rel, direction=direction):
                queue.append((endpoint, depth + 1))
    return _TraceWalk(
        relationships=tuple(rels),
        claims=tuple(claims),
        structural_edges=tuple(structural_edges[: bounds.max_results]),
        truncated=bool(queue),
        coverage=(
            structural_coverage,
            _answers.merge_coverage_detail(tuple(structural_details)),
        ),
    )


def _trace_drive(
    repository_id: str,
    target: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
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
    selected bounded question through discovery, interpretation, persistence,
    and readback. Anchors pass verbatim as question_terms. Every resumption and
    new frontier task forwards the retained selection; later frontiers never
    re-derive anchors by mining prose.

    Expands one deterministic frontier at a time. Resume restarts the
    deterministic walk, so each subject is requested at most once and the walk
    always terminates.

    Paging (I S4 pgq): `page_token` windows the target subject's initial state
    load only; frontier expansion loads proceed unpaged. Page deep results
    through narrower targets.
    """
    question = _trace_question(
        target,
        direction=direction,
        relationship_filter=relationship_filter,
        boundary_only=boundary_only,
        question_selection=question_selection,
        root_subject=root_subject,
    )
    walk = _trace_walk(
        repository_id,
        target,
        question,
        resolution,
        suspended,
        direction=direction,
        relationship_filter=relationship_filter,
        boundary_only=boundary_only,
        question_selection=question_selection,
        seeds=seeds,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
        page_token=page_token,
    )
    if isinstance(walk, PendingInterpretation):
        return walk
    return _compose_trace_answer(
        repository_id,
        target,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        relationships=walk.relationships,
        claims=walk.claims,
        structural_edges=walk.structural_edges,
        truncated_walk=walk.truncated,
        structural_coverage=walk.coverage,
    )
