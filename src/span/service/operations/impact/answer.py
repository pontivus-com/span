"""Span service impact operation (plan §11.5; v0.6 §14 Amendment A-01).

Change-condition derivation and impact answers. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses

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
    _select_answer_items,
    coverage_counts_for,
    state_explanation_for,
)
from span.service.freshness import (
    _refresh_view,
)
from span.service.questions import (
    _paged_question_views,
)
from span.service.refs import (
    _claim_ref,
    _item_ref,
    _ref_value,
    _relationship_ref,
)
from span.service.requests import (
    ChangeKind,
)
from span.service.operations.impact.conditions import _derive_change_conditions
from span.service.operations.impact.frontier import (
    _impact_frontier,
    _impact_question,
    _impact_target_gate,
    _ImpactFrontier,
)
from span.service.resolution import (
    _load_subject_state,
)


def _impact_items(
    change_kind: ChangeKind,
    subject: m.Subject,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    frontier: _ImpactFrontier,
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...],
) -> tuple[tuple[m.ChangeCondition, ...], list[m.ImpactItem]]:
    """Derive change conditions and one impact item per reached subject."""
    sid = subject.subject_id
    target_rels = [
        relationship
        for relationship in relationships
        if relationship.source == sid or relationship.target == sid
    ]
    conditions = _derive_change_conditions(
        change_kind,
        subject,
        claims,
        tuple(target_rels),
        affected_assertions=affected_assertions,
    )
    items: list[m.ImpactItem] = []
    for visited_id in frontier.visited:
        if visited_id == sid:
            continue
        claims_here = frontier.node_claims[visited_id]
        rels_here = frontier.node_rels[visited_id]
        linking = [
            relationship
            for relationship in list(rels_here) + target_rels
            if (relationship.source == sid and relationship.target == visited_id)
            or (relationship.target == sid and relationship.source == visited_id)
        ]
        established = [
            relationship
            for relationship in linking
            if relationship.trust is m.TrustState.ESTABLISHED
        ]
        questionable = [
            item
            for item in (*claims_here, *rels_here)
            if item.freshness.state is not m.FreshnessState.CURRENT
            or item.trust
            in (
                m.TrustState.UNRESOLVED,
                m.TrustState.AMBIGUOUS,
                m.TrustState.CONFLICTED,
                m.TrustState.PARTIAL,
            )
        ]
        edge = frontier.via_edge.get(visited_id)
        if questionable:
            establishment = m.ImpactEstablishment.PARTIAL_OR_UNRESOLVED
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.DERIVED_JOIN,
                summary=(
                    "dependent semantic state is stale, unverifiable, or unresolved"
                ),
                input_refs=tuple(_item_ref(item) for item in questionable),
            )
        elif established:
            establishment = m.ImpactEstablishment.SEMANTICALLY_ESTABLISHED
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.DERIVED_JOIN,
                summary=(
                    f"{len(established)} established canonical "
                    f"relationship(s) connect the change target to "
                    f"this subject"
                ),
                input_refs=tuple(
                    _relationship_ref(relationship) for relationship in established
                ),
            )
        else:
            establishment = m.ImpactEstablishment.STRUCTURAL_POSSIBILITY
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.STRUCTURAL_OBSERVATION,
                summary=(
                    "structural reach only; no canonical relationship established"
                ),
                input_refs=(),
            )
        items.append(
            m.ImpactItem(
                subject=visited_id,
                establishment=establishment,
                basis=basis,
                structural_evidence=(edge,) if edge is not None else (),
                relevant_claims=tuple(_claim_ref(claim) for claim in claims_here),
                relevant_relationships=tuple(
                    _relationship_ref(relationship)
                    for relationship in list(rels_here) + established
                ),
            )
        )
    return conditions, items


@_dataclasses.dataclass
class _ImpactSelection:
    """The answer's admitted items, leaves, and truncation state."""

    context: tuple[m.ClaimRef | m.RelationshipRef, ...]
    conditions: tuple[m.ChangeCondition, ...]
    impacts: tuple[m.ImpactItem, ...]
    verification: tuple[m.ClaimRef | m.RelationshipRef, ...]
    claims: tuple[m.SemanticClaim, ...]
    relationships: tuple[m.SemanticRelationship, ...]
    conflicts: list[m.RecordedConflict]
    unresolved: list[m.ResolutionRequirement]
    truncated: bool
    category: str | None


def _select_impact(
    repository_id: str,
    target_id: m.SubjectId,
    *,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    items: list[m.ImpactItem],
    conditions: tuple[m.ChangeCondition, ...],
    frontier: _ImpactFrontier,
    resolution: m.SubjectResolution | None,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> _ImpactSelection:
    """Admit items and impacts at the answer's single ceiling."""
    target_context: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [_claim_ref(claim) for claim in claims]
        + [_relationship_ref(relationship) for relationship in relationships]
    )
    verification: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [
            _claim_ref(claim)
            for claim in claims
            if claim.kind is m.ClaimKind.VERIFICATION
        ]
        + [
            _relationship_ref(relationship)
            for relationship in relationships
            if relationship.kind is m.RelationshipKind.VERIFIED_BY
        ]
    )
    all_claims = list(claims) + [
        claim
        for node_id, node in frontier.node_claims.items()
        for claim in node
        if node_id != target_id
    ]
    all_rels = list(relationships) + [
        relationship
        for node_id, node in frontier.node_rels.items()
        for relationship in node
        if node_id != target_id
    ]
    conflicts_all = _conflicts_for(
        repository_id, tuple(all_claims), tuple(all_rels), store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            tuple(all_claims),
            tuple(all_rels),
            conflicts_all,
            bounds.max_results,
        )
    )
    kept_ids = {claim.claim_id.value for claim in kept_claims} | {
        relationship.relationship_id.value for relationship in kept_rels
    }
    kept_context = tuple(ref for ref in target_context if _ref_value(ref) in kept_ids)
    kept_ver = tuple(ref for ref in verification if _ref_value(ref) in kept_ids)
    unresolved: list[m.ResolutionRequirement] = []
    if frontier.reach is not None:
        structural_requirement = _answers.structural_coverage_requirement(
            "impact", frontier.reach.coverage, frontier.reach.coverage_detail
        )
        if structural_requirement is not None:
            unresolved.append(structural_requirement)
    if resolution is not None:
        unresolved.extend(_answers.requirements_for_resolution(resolution))
    for claim in kept_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for relationship in kept_rels:
        unresolved.extend(_answers.requirements_for_relationship(relationship))
    kept_impacts = tuple(
        m.ImpactItem(
            subject=item.subject,
            establishment=item.establishment,
            basis=item.basis,
            structural_evidence=item.structural_evidence,
            relevant_claims=tuple(
                ref for ref in item.relevant_claims if _ref_value(ref) in kept_ids
            ),
            relevant_relationships=tuple(
                ref
                for ref in item.relevant_relationships
                if _ref_value(ref) in kept_ids
            ),
        )
        for item in items
    )
    rest_budget = max(
        0,
        bounds.max_results
        - len(kept_conf)
        - len(kept_context)
        - len(kept_ver)
        - len(kept_claims)
        - len(kept_rels)
        - len(unresolved),
    )
    kept_impacts = kept_impacts[:rest_budget]
    kept_conds = conditions[: max(0, rest_budget - len(kept_impacts))]
    truncated = items_truncated or (
        len(kept_impacts) < len(items) or len(kept_conds) < len(conditions)
    )
    category = items_category
    if category is None and truncated:
        category = "impacts"
    return _ImpactSelection(
        context=kept_context,
        conditions=kept_conds,
        impacts=kept_impacts,
        verification=kept_ver,
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        unresolved=unresolved,
        truncated=truncated,
        category=category,
    )


def _compose_impact_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    change_kind: ChangeKind,
    change_description: str | None,
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
    seeds: tuple[m.EvidenceRef, ...] = (),
    suspended: tuple[m.SubjectId, ...] = (),
    page_token: str | None = None,
    question_selection: m.SemanticQuestionSelection | None = None,
    root_question: m.SemanticQuestionScope | None = None,
) -> m.SemanticAnswer | PendingInterpretation:
    question = _impact_question(
        subject,
        change_kind=change_kind,
        change_description=change_description,
        affected_assertions=affected_assertions,
        question_selection=question_selection,
        root_question=root_question,
    )
    sid = subject.subject_id
    claims, relationships, _, _ = _load_subject_state(
        repository_id,
        sid,
        store=store,
        bounds=bounds,
        page_token=page_token if not suspended else None,
    )
    gate = _impact_target_gate(
        repository_id,
        subject,
        question,
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
    if gate is not None:
        return gate
    claims, relationships = _refresh_view(
        repository_id,
        claims,
        relationships,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    frontier = _impact_frontier(
        repository_id,
        subject,
        question,
        claims,
        relationships,
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
    if isinstance(frontier, PendingInterpretation):
        return frontier
    conditions, items = _impact_items(
        change_kind,
        subject,
        claims,
        relationships,
        frontier,
        affected_assertions,
    )
    selection = _select_impact(
        repository_id,
        sid,
        claims=claims,
        relationships=relationships,
        items=items,
        conditions=conditions,
        frontier=frontier,
        resolution=resolution,
        store=store,
        bounds=bounds,
    )
    views, _, qremaining = _paged_question_views(
        repository_id,
        sid,
        (sid,),
        store=store,
        bounds=bounds,
        page_token=page_token,
        evidence=evidence,
    )
    truncated = selection.truncated
    category = selection.category
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    content = m.ImpactContent(
        target_context=selection.context,
        change_conditions=selection.conditions,
        impacts=selection.impacts,
        verification=selection.verification,
        claims=selection.claims,
        relationships=selection.relationships,
        conflicts=selection.conflicts,
        question_coverage=views,
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "imp",
            repository_id,
            f"{sid.canonical_locator}:{change_kind.value}",
        ),
        intent=m.SemanticIntent.IMPACT,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for claim in selection.claims for ref in claim.evidence),
        resolution_requirements=tuple(selection.unresolved),
        bounds=bounds,
        withheld_category=category,
        continuation_token=None,
        state_explanation=state_explanation_for(
            tuple(selection.claims),
            tuple(selection.relationships),
            coverage=coverage_counts_for(views),
            bounds=(bounds.max_results, truncated),
        ),
    )
