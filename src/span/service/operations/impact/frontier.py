"""Span service impact operation (plan §11.5; v0.6 §14 Amendment A-01).

Change-condition derivation and impact answers. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses

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
from span.service.questions import (
    effective_impact_slice,
)
from span.service.requests import (
    ChangeKind,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_exact_subject,
)


@_dataclasses.dataclass
class _ImpactQuestion:
    """The discriminated question one impact answer is composed around."""

    proposal: m.ProposedChange
    slice: str
    root: m.SubjectId
    scope: m.SemanticQuestionScope
    anchors: tuple[str, ...]


def _impact_question(
    subject: m.Subject,
    *,
    change_kind: ChangeKind,
    change_description: str | None,
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...],
    question_selection: m.SemanticQuestionSelection | None,
    root_question: m.SemanticQuestionScope | None,
) -> _ImpactQuestion:
    """Build the proposal and the exact CQ-08 question for this impact unit.

    ``change_description`` is carried for agent context but never text-mined:
    proposal-content inference would violate AP-01. Anchors pass verbatim as
    question_terms and are never mined from prose.
    """
    proposal = m.ProposedChange(
        change_kind=change_kind,
        change_description=change_description,
        affected_assertions=affected_assertions,
    )
    sid = subject.subject_id
    if question_selection is not None:
        host_slice = question_selection.question_slice
        basis = question_selection.materiality_basis or "IMPACT question-local"
        anchors = tuple(question_selection.question_anchors)
    else:
        host_slice = sid.canonical_locator
        basis = "IMPACT question-local"
        anchors = ()
    question_slice = effective_impact_slice(
        host_slice, change_kind, change_description, affected_assertions
    )
    root = root_question.scope_root if root_question is not None else sid
    return _ImpactQuestion(
        proposal=proposal,
        slice=question_slice,
        root=root,
        scope=m.SemanticQuestionScope(
            scope_root=root,
            subject=sid,
            question_class=m.SemanticQuestionClass.CQ_08,
            question_slice=question_slice,
            materiality_basis=basis,
        ),
        anchors=anchors,
    )


def _has_recorded_impact_coverage(
    repository_id: str,
    *,
    root: m.SubjectId,
    subject_id: m.SubjectId,
    question_slice: str,
    store: SemanticStore,
) -> bool:
    """Recorded non-PENDING coverage for the exact frontier question (B.7).

    Recorded PENDING is admitted-but-unexamined and still needs its first
    examination, while ANSWERED/OPEN/NOT_APPLICABLE serve as qualified views
    with reassessment through explicit refresh. Claim existence never counts.
    """
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
        and coverage.question.question_class is m.SemanticQuestionClass.CQ_08
        and coverage.question.question_slice == question_slice
        and coverage.disposition is not m.SemanticQuestionDisposition.PENDING
        for coverage in coverages
    )


def _impact_suspension(
    repository_id: str,
    subject: m.Subject,
    question: _ImpactQuestion,
    frontier_subject_id: m.SubjectId,
    suspended: tuple[m.SubjectId, ...],
    resolution: m.SubjectResolution | None,
    *,
    question_selection: m.SemanticQuestionSelection | None,
    seeds: tuple[m.EvidenceRef, ...],
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
) -> PendingInterpretation | None:
    """Suspend one unexamined frontier subject, resolved semantically first."""
    full = _resolve_exact_subject(
        repository_id,
        frontier_subject_id,
        structural=structural,
        bounds=bounds,
    )
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
        operation_intent=m.SemanticIntent.IMPACT,
        question_slice=question.slice,
        proposed_change=question.proposal,
        question_terms=question.anchors,
    )
    return _suspend(
        op="impact",
        repository_id=repository_id,
        subject=full,
        task=task,
        seeds=seeds,
        bounds=bounds,
        state=state,
        resolution=resolution,
        scope=(subject,),
        suspended=suspended + (frontier_subject_id,),
        change_kind=question.proposal.change_kind.value,
        change_description=question.proposal.change_description,
        affected_assertions=tuple(question.proposal.affected_assertions),
        operation_intent="IMPACT",
        question_slice=question.slice,
        continuations=continuations,
        root_question=question.scope,
        question_selection=question_selection,
    )


def _impact_target_gate(
    repository_id: str,
    subject: m.Subject,
    question: _ImpactQuestion,
    suspended: tuple[m.SubjectId, ...],
    resolution: m.SubjectResolution | None,
    *,
    question_selection: m.SemanticQuestionSelection | None,
    seeds: tuple[m.EvidenceRef, ...],
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
) -> PendingInterpretation | None:
    """Suspend the change target itself when its question is unexamined."""
    sid = subject.subject_id
    if sid in suspended:
        return None
    if _has_recorded_impact_coverage(
        repository_id,
        root=question.root,
        subject_id=sid,
        question_slice=question.slice,
        store=store,
    ):
        return None
    return _impact_suspension(
        repository_id,
        subject,
        question,
        sid,
        suspended,
        resolution,
        question_selection=question_selection,
        seeds=seeds,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
    )


@_dataclasses.dataclass
class _ImpactFrontier:
    """The bounded structural reach and its loaded semantic state."""

    reach: m.StructuralResult[m.StructuralReachNode] | None
    visited: list[m.SubjectId]
    via_edge: dict[m.SubjectId, m.StructuralEdge | None]
    node_claims: dict[m.SubjectId, tuple[m.SemanticClaim, ...]]
    node_rels: dict[m.SubjectId, tuple[m.SemanticRelationship, ...]]


def _impact_frontier(
    repository_id: str,
    subject: m.Subject,
    question: _ImpactQuestion,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    suspended: tuple[m.SubjectId, ...],
    resolution: m.SubjectResolution | None,
    *,
    question_selection: m.SemanticQuestionSelection | None,
    seeds: tuple[m.EvidenceRef, ...],
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
) -> _ImpactFrontier | PendingInterpretation:
    """Expand the bounded reach, suspending the first unexamined frontier unit."""
    sid = subject.subject_id
    try:
        reach = structural.reach(
            repository_id,
            sid,
            (),
            StructuralDirection.BOTH,
            bounds.max_depth,
            bounds,
        )
    except ValueError:
        reach = None
    visited: list[m.SubjectId] = [sid]
    via_edge: dict[m.SubjectId, m.StructuralEdge | None] = {sid: None}
    if reach is not None:
        for node in reach.items:
            if node.subject not in visited:
                if len(visited) >= bounds.max_subjects:
                    break
                visited.append(node.subject)
                via_edge[node.subject] = node.via
    node_claims: dict[m.SubjectId, tuple[m.SemanticClaim, ...]] = {}
    node_rels: dict[m.SubjectId, tuple[m.SemanticRelationship, ...]] = {}
    for visited_id in visited:
        if visited_id == sid:
            node_claims[visited_id] = claims
            node_rels[visited_id] = relationships
            continue
        loaded_claims, loaded_rels, _, _ = _load_subject_state(
            repository_id, visited_id, store=store, bounds=bounds
        )
        if visited_id not in suspended and not _has_recorded_impact_coverage(
            repository_id,
            root=question.root,
            subject_id=visited_id,
            question_slice=question.slice,
            store=store,
        ):
            pending = _impact_suspension(
                repository_id,
                subject,
                question,
                visited_id,
                suspended,
                resolution,
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
        node_claims[visited_id] = loaded_claims
        node_rels[visited_id] = loaded_rels
    return _ImpactFrontier(
        reach=reach,
        visited=visited,
        via_edge=via_edge,
        node_claims=node_claims,
        node_rels=node_rels,
    )
