"""Span service trace operation (plan §11.6; v0.6 §14 Amendment A-01).

Bounded structural-semantic traversal with resume. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    _conflicts_for,
    _select_answer_items,
    coverage_counts_for,
    state_explanation_for,
)
from span.service.freshness import (
    preflight,
)
from span.service.questions import (
    _paged_question_views,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)


def _trace_live_view(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[
    tuple[m.SemanticClaim, ...],
    tuple[m.SemanticRelationship, ...],
]:
    """Refresh every delivered item's freshness through the persisting preflight."""
    ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(claim) for claim in claims
    ) + tuple(_relationship_ref(relationship) for relationship in relationships)
    updates = preflight(
        repository_id, ids, evidence=evidence, store=store, bounds=bounds
    )
    fresh_by_id = {update.semantic_id.id.value: update.freshness for update in updates}
    return (
        tuple(
            (
                _dataclasses.replace(claim, freshness=fresh_by_id[claim.claim_id.value])
                if claim.claim_id.value in fresh_by_id
                else claim
            )
            for claim in claims
        ),
        tuple(
            (
                _dataclasses.replace(
                    relationship,
                    freshness=fresh_by_id[relationship.relationship_id.value],
                )
                if relationship.relationship_id.value in fresh_by_id
                else relationship
            )
            for relationship in relationships
        ),
    )


def _trace_context_refs(
    repository_id: str,
    kept_claims: tuple[m.SemanticClaim, ...],
    kept_rels: tuple[m.SemanticRelationship, ...],
    *,
    store: SemanticStore,
) -> tuple[list[m.SubjectId], list[m.ClaimRef | m.RelationshipRef]]:
    """Lifecycle references and deduplicated boundary subjects for the answer."""
    boundary_ids: list[m.SubjectId] = []
    lifecycle_refs: list[m.ClaimRef | m.RelationshipRef] = []
    for claim in kept_claims:
        if claim.kind is m.ClaimKind.LIFECYCLE_STATE:
            lifecycle_refs.append(_claim_ref(claim))
    for relationship in kept_rels:
        if relationship.kind in (
            m.RelationshipKind.TRANSITIONS_TO,
            m.RelationshipKind.PERSISTS_AT,
        ):
            lifecycle_refs.append(_relationship_ref(relationship))
        if relationship.kind is m.RelationshipKind.CROSSES_BOUNDARY:
            boundary_ids.extend((relationship.source, relationship.target))
    if not boundary_ids:
        return boundary_ids, lifecycle_refs
    loaded = store.load_subjects(repository_id, tuple(dict.fromkeys(boundary_ids)))
    ordered = [
        subject.subject_id
        for subject in loaded
        if subject.subject_id.subject_kind is m.SubjectKind.BOUNDARY
    ] + boundary_ids
    seen: set[str] = set()
    deduped: list[m.SubjectId] = []
    for subject_id in ordered:
        if subject_id.canonical_locator not in seen:
            seen.add(subject_id.canonical_locator)
            deduped.append(subject_id)
    return deduped, lifecycle_refs


def _trace_requirements(
    kept_claims: tuple[m.SemanticClaim, ...],
    kept_rels: tuple[m.SemanticRelationship, ...],
    resolution: m.SubjectResolution | None,
    structural_coverage: tuple[m.ScopeCoverage, str | None],
) -> list[m.ResolutionRequirement]:
    """Structural coverage, resolution, and item requirements for the answer."""
    requirements: list[m.ResolutionRequirement] = []
    structural_requirement = _answers.structural_coverage_requirement(
        "trace", structural_coverage[0], structural_coverage[1]
    )
    if structural_requirement is not None:
        requirements.append(structural_requirement)
    if resolution is not None:
        requirements.extend(_answers.requirements_for_resolution(resolution))
    for relationship in kept_rels:
        requirements.extend(_answers.requirements_for_relationship(relationship))
    for claim in kept_claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    return requirements


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
    claims, relationships = _trace_live_view(
        repository_id,
        claims,
        relationships,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    conflicts_all = _conflicts_for(repository_id, claims, relationships, store=store)
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(claims, relationships, conflicts_all, bounds.max_results)
    )
    boundary_ids, lifecycle_refs = _trace_context_refs(
        repository_id,
        kept_claims,
        kept_rels,
        store=store,
    )
    requirements = _trace_requirements(
        kept_claims, kept_rels, resolution, structural_coverage
    )
    (kept_boundary, kept_edges), truncated, category, token = _answers.truncate_fields(
        (
            (tuple(boundary_ids), "boundary_context"),
            (structural_edges, "structural_edges"),
        ),
        max(0, bounds.max_results - len(kept_conf) - len(kept_rels)),
    )
    del token
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
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "trc", repository_id, subject.subject_id.canonical_locator
        ),
        intent=m.SemanticIntent.TRACE,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for rel in kept_rels for ref in rel.evidence),
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
