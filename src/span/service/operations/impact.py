"""Span service impact operation (plan §11.5; v0.6 §14 Amendment A-01).

Change-condition derivation and impact answers. Verbatim from
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

from span.service.answers import (
    _answer_id,
    _bound_info,
    _conflicts_for,
    _select_answer_items,
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
)
from span.service.refs import (
    _claim_ref,
    _item_ref,
    _ref_value,
    _relationship_ref,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    ChangeKind,
    SemanticImpactRequest,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_exact_subject,
    _resolve_query_subject,
)

__all__ = [
    '_derive_change_conditions',
    '_compose_impact_answer',
    'impact',
]

def _derive_change_conditions(
    change_kind: ChangeKind,
    target: m.Subject,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
) -> tuple[m.ChangeCondition, ...]:
    """Deterministic ChangeCondition derivation (plan §11.5.1, I-38).

    Dimension flags, never severity/confidence/approval scores. Presence
    rows fire on established canonical state; kind-gated rows additionally
    require the stated change_kind. Proposal-sensitive rows fire only for
    typed affected assertions resolved against current canonical state;
    proposal prose is never mined. `OTHER` suppresses kind-gated rows
    only — independently established dimensions still apply.
    """
    sid = target.subject_id
    established_claims = {
        c.claim_id.value: c
        for c in claims
        if c.trust is m.TrustState.ESTABLISHED
    }
    established_rels = {
        r.relationship_id.value: r
        for r in relationships
        if r.trust is m.TrustState.ESTABLISHED
    }
    affected = {_ref_value(ref) for ref in affected_assertions}
    rel_kinds = {r.kind for r in relationships}
    has_kind = change_kind is not ChangeKind.OTHER
    conditions: list[m.ChangeCondition] = []
    if any(
        value in established_claims
        and established_claims[value].authority is not None
        and established_claims[value].authority.status
        is m.AuthorityStatus.ACCEPTED
        and established_claims[value].freshness.state
        is m.FreshnessState.CURRENT
        for value in affected
    ) or any(
        value in established_rels
        and established_rels[value].kind is m.RelationshipKind.GOVERNED_BY
        for value in affected
    ):
        conditions.append(m.ChangeCondition.AUTHORITY_CHANGE)
    if has_kind and change_kind is ChangeKind.OWNERSHIP:
        conditions.append(m.ChangeCondition.OWNERSHIP_CHANGE)
    elif any(
        value in established_claims
        and established_claims[value].kind
        in (
            m.ClaimKind.OWNERSHIP_CUSTODY,
            m.ClaimKind.TRANSFORMATION_OWNERSHIP,
        )
        for value in affected
    ):
        conditions.append(m.ChangeCondition.OWNERSHIP_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.REPRESENTATION
        and (
            any(
                c.kind is m.ClaimKind.REPRESENTATION_CONTRACT
                for c in established_claims.values()
            )
            or m.RelationshipKind.REPRESENTS_AS in rel_kinds
        )
    ):
        conditions.append(m.ChangeCondition.CANONICAL_REPRESENTATION_CHANGE)
    target_item_ids = {
        c.claim_id.value for c in claims if c.subject == sid
    } | {
        r.relationship_id.value
        for r in relationships
        if r.source == sid or r.target == sid
    }
    if any(
        value in established_rels
        and established_rels[value].kind
        is m.RelationshipKind.CROSSES_BOUNDARY
        for value in affected
    ) or (
        sid.subject_kind is m.SubjectKind.BOUNDARY
        and bool(affected & target_item_ids)
    ):
        conditions.append(m.ChangeCondition.BOUNDARY_CHANGE)
    if sid.subject_kind is m.SubjectKind.CONTRACT and any(
        c.authority is not None
        and c.authority.status is m.AuthorityStatus.ACCEPTED
        and c.authority.applicability.description
        for c in claims
        if c.kind is m.ClaimKind.REPRESENTATION_CONTRACT
        or c.kind is m.ClaimKind.PURPOSE
    ):
        conditions.append(m.ChangeCondition.PUBLIC_CONTRACT_CHANGE)
    if any(
        value in established_claims
        and established_claims[value].kind
        is m.ClaimKind.INVARIANT_CONSTRAINT
        for value in affected
    ):
        conditions.append(m.ChangeCondition.INVARIANT_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.CONFIGURATION
        or any(
            c.kind is m.ClaimKind.CONFIGURATION_ENVIRONMENT
            for c in established_claims.values()
        )
        or m.RelationshipKind.CONFIGURED_BY in rel_kinds
    ):
        conditions.append(m.ChangeCondition.CONFIGURATION_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.LIFECYCLE
        or any(
            c.kind is m.ClaimKind.LIFECYCLE_STATE
            for c in established_claims.values()
        )
        or m.RelationshipKind.TRANSITIONS_TO in rel_kinds
        or m.RelationshipKind.PERSISTS_AT in rel_kinds
    ):
        conditions.append(m.ChangeCondition.LIFECYCLE_CHANGE)
    if any(
        value in established_claims
        and established_claims[value].kind is m.ClaimKind.VERIFICATION
        for value in affected
    ) or any(
        value in established_rels
        and established_rels[value].kind is m.RelationshipKind.VERIFIED_BY
        for value in affected
    ):
        conditions.append(m.ChangeCondition.VERIFICATION_CHANGE)
    order = {condition: n for n, condition in enumerate(m.ChangeCondition)}
    return tuple(sorted(set(conditions), key=order.__getitem__))

def _compose_impact_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    change_kind: ChangeKind,
    change_description: str | None,
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
    seeds: tuple[m.EvidenceRef, ...] = (),
    suspended: tuple[str, ...] = (),
    page_token: str | None = None,
) -> m.SemanticAnswer | PendingInterpretation:
    # change_description is carried on suspend/resume for agent context but
    # never text-mined: proposal-content inference would violate AP-01.
    proposal = m.ProposedChange(
        change_kind=change_kind,
        change_description=change_description,
        affected_assertions=affected_assertions,
    )
    sid = subject.subject_id
    claims, relationships, _, _ = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds,
        page_token=page_token if not suspended else None,
    )
    if not claims and not relationships:
        if sid.canonical_locator not in suspended:
            full = _resolve_exact_subject(
                repository_id, sid, structural=structural, bounds=bounds
            )
            if full is not None:
                task = prepare_interpretation_task(
                    repository_id, full, structural=structural,
                    evidence=evidence, bounds=bounds, state=state,
                    authority_seeds=seeds,
                    operation_intent=m.SemanticIntent.IMPACT,
                    question_slice=full.subject_id.canonical_locator,
                    proposed_change=proposal,
                )
                return _suspend(
                    op="impact", repository_id=repository_id,
                    subject=full, task=task, seeds=seeds,
                    bounds=bounds, state=state, resolution=resolution,
                    scope=(subject,),
                    suspended=suspended + (sid.canonical_locator,),
                    change_kind=change_kind.value,
                    change_description=change_description,
                    affected_assertions=affected_assertions,
                    operation_intent="IMPACT",
                    question_slice=full.subject_id.canonical_locator,
                    continuations=continuations,
                )
        claims, relationships = (), ()
    claims, relationships = _refresh_view(
        repository_id, claims, relationships,
        evidence=evidence, store=store, bounds=bounds,
    )
    try:
        reach = structural.reach(
            repository_id, sid, (), StructuralDirection.BOTH,
            bounds.max_depth, bounds,
        )
    except ValueError:
        reach = None
    visited: list[m.SubjectId] = [sid]
    via_edge: dict[str, m.StructuralEdge | None] = {
        sid.canonical_locator: None
    }
    if reach is not None:
        for node in reach.items:
            locator = node.subject.canonical_locator
            if locator not in [v.canonical_locator for v in visited]:
                if len(visited) >= bounds.max_subjects:
                    break
                visited.append(node.subject)
                via_edge[locator] = node.via
    node_claims: dict[str, tuple[m.SemanticClaim, ...]] = {}
    node_rels: dict[str, tuple[m.SemanticRelationship, ...]] = {}
    for visited_id in visited:
        locator = visited_id.canonical_locator
        if locator == sid.canonical_locator:
            node_claims[locator] = claims
            node_rels[locator] = relationships
            continue
        loaded_c, loaded_r, _, _ = _load_subject_state(
            repository_id, visited_id, store=store, bounds=bounds
        )
        if not loaded_c and not loaded_r and locator not in suspended:
            full = _resolve_exact_subject(
                repository_id, visited_id, structural=structural,
                bounds=bounds,
            )
            if full is not None:
                task = prepare_interpretation_task(
                    repository_id, full, structural=structural,
                    evidence=evidence, bounds=bounds, state=state,
                    authority_seeds=seeds,
                    operation_intent=m.SemanticIntent.IMPACT,
                    question_slice=full.subject_id.canonical_locator,
                    proposed_change=proposal,
                )
                return _suspend(
                    op="impact", repository_id=repository_id,
                    subject=full, task=task, seeds=seeds,
                    bounds=bounds, state=state, resolution=resolution,
                    scope=(subject,),
                    suspended=suspended + (locator,),
                    change_kind=change_kind.value,
                    change_description=change_description,
                    affected_assertions=affected_assertions,
                    operation_intent="IMPACT",
                    question_slice=full.subject_id.canonical_locator,
                    continuations=continuations,
                )
        node_claims[locator] = loaded_c
        node_rels[locator] = loaded_r
    target_rels = [
        r for r in relationships
        if r.source == sid or r.target == sid
    ]
    conditions = _derive_change_conditions(
        change_kind, subject, claims, tuple(target_rels),
        affected_assertions=affected_assertions,
    )
    items: list[m.ImpactItem] = []
    for visited_id in visited:
        locator = visited_id.canonical_locator
        if locator == sid.canonical_locator:
            continue
        claims_here = node_claims[locator]
        rels_here = node_rels[locator]
        linking = [
            r for r in list(rels_here) + target_rels
            if (r.source == sid and r.target == visited_id)
            or (r.target == sid and r.source == visited_id)
        ]
        established = [r for r in linking if r.trust is m.TrustState.ESTABLISHED]
        questionable = [
            i for i in (*claims_here, *rels_here)
            if i.freshness.state is not m.FreshnessState.CURRENT
            or i.trust
            in (
                m.TrustState.UNRESOLVED,
                m.TrustState.AMBIGUOUS,
                m.TrustState.CONFLICTED,
                m.TrustState.PARTIAL,
            )
        ]
        edge = via_edge.get(locator)
        if questionable:
            establishment = m.ImpactEstablishment.PARTIAL_OR_UNRESOLVED
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.DERIVED_JOIN,
                summary=(
                    "dependent semantic state is stale, unverifiable, "
                    "or unresolved"
                ),
                input_refs=tuple(
                    _item_ref(i) for i in questionable
                ),
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
                    _relationship_ref(r) for r in established
                ),
            )
        else:
            establishment = m.ImpactEstablishment.STRUCTURAL_POSSIBILITY
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.STRUCTURAL_OBSERVATION,
                summary=(
                    "structural reach only; no canonical relationship "
                    "established"
                ),
                input_refs=(),
            )
        items.append(
            m.ImpactItem(
                subject=visited_id,
                establishment=establishment,
                basis=basis,
                structural_evidence=(edge,) if edge is not None else (),
                relevant_claims=tuple(
                    _claim_ref(c) for c in claims_here
                ),
                relevant_relationships=tuple(
                    _relationship_ref(r)
                    for r in list(rels_here) + established
                ),
            )
        )
    target_context: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [_claim_ref(c) for c in claims]
        + [_relationship_ref(r) for r in relationships]
    )
    verification: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [_claim_ref(c) for c in claims if c.kind is m.ClaimKind.VERIFICATION]
        + [
            _relationship_ref(r)
            for r in relationships
            if r.kind is m.RelationshipKind.VERIFIED_BY
        ]
    )
    all_claims = list(claims) + [
        c for loc, cs in node_claims.items()
        for c in cs
        if loc != sid.canonical_locator
    ]
    all_rels = list(relationships) + [
        r for loc, rs in node_rels.items()
        for r in rs
        if loc != sid.canonical_locator
    ]
    conflicts_all = _conflicts_for(
        repository_id, tuple(all_claims), tuple(all_rels), store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            tuple(all_claims), tuple(all_rels), conflicts_all,
            bounds.max_results,
        )
    )
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    kept_context = tuple(
        ref for ref in target_context if _ref_value(ref) in kept_ids
    )
    kept_ver = tuple(
        ref for ref in verification if _ref_value(ref) in kept_ids
    )
    unresolved: list[m.ResolutionRequirement] = []
    if resolution is not None:
        unresolved.extend(_answers.requirements_for_resolution(resolution))
    for claim in kept_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for rel in kept_rels:
        unresolved.extend(_answers.requirements_for_relationship(rel))
    kept_impacts = tuple(
        m.ImpactItem(
            subject=item.subject,
            establishment=item.establishment,
            basis=item.basis,
            structural_evidence=item.structural_evidence,
            relevant_claims=tuple(
                ref for ref in item.relevant_claims
                if _ref_value(ref) in kept_ids
            ),
            relevant_relationships=tuple(
                ref for ref in item.relevant_relationships
                if _ref_value(ref) in kept_ids
            ),
        )
        for item in items
    )
    rest_budget = max(
        0,
        bounds.max_results
        - len(kept_conf) - len(kept_context) - len(kept_ver)
        - len(kept_claims) - len(kept_rels) - len(unresolved),
    )
    kept_impacts = kept_impacts[:rest_budget]
    kept_conds = conditions[: max(0, rest_budget - len(kept_impacts))]
    truncated = items_truncated or (
        len(kept_impacts) < len(items) or len(kept_conds) < len(conditions)
    )
    category = items_category
    if category is None and truncated:
        category = "impacts"
    views, _, qremaining = _paged_question_views(
        repository_id, sid, (sid,),
        store=store, bounds=bounds, page_token=page_token,
        evidence=evidence,
    )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    content = m.ImpactContent(
        target_context=kept_context,
        change_conditions=kept_conds,
        impacts=kept_impacts,
        verification=kept_ver,
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        unresolved=tuple(unresolved),
        question_coverage=views,
    )
    returned = (
        len(kept_conf) + len(unresolved) + len(kept_impacts)
        + len(kept_context) + len(kept_ver) + len(kept_conds)
    )
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "imp", repository_id,
            f"{sid.canonical_locator}:{change_kind.value}",
        ),
        intent=m.SemanticIntent.IMPACT,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
        resolution_requirements=tuple(unresolved),
        bound_info=_bound_info(bounds, returned, truncated, category, None),
    )

def impact(
    request: SemanticImpactRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Pre-change semantic brief (plan §11.5, task 3.8).

    Composes already-established CQ/F information for a proposed
    material change: identity/purpose/responsibility, owner/custodian,
    governing authority and invariants, boundary/representation context,
    derived ChangeConditions (§11.5.1), established vs structural-only
    downstream impacts, verification currency, conflicts/staleness, and
    requirements. Suspends via §11.12 when interpretation is missing;
    never interprets inline, never invents authority or severity.

    Paging (plan I-39): `page_token` windows the target subject's
    initial state load only; downstream node loads proceed unpaged.
    Page deep results through narrower targets.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.IMPACT, request.repository_id, bounds, state
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
                "imp", request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.IMPACT,
            repository_state=state,
            subject_resolution=resolution,
            content=m.ImpactContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    if request.change_kind is ChangeKind.OTHER and not request.change_description:
        raise ValueError(
            "change_kind OTHER requires a change_description (§11.10)"
        )
    return _compose_impact_answer(
        request.repository_id, resolution.candidates[0].subject, resolution,
        structural=structural, evidence=evidence, store=store,
        continuations=continuations, bounds=bounds, state=state,
        change_kind=request.change_kind,
        change_description=request.change_description,
        affected_assertions=request.affected_assertions,
        seeds=authority_seeds, suspended=(),
        page_token=request.page_token,
    )
