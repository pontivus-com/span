"""Span service impact operation (plan §11.5; v0.6 §14 Amendment A-01).

Change-condition derivation and impact answers. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations


from span.core import model as m

from span.service.refs import (
    _ref_value,
)
from span.service.requests import (
    ChangeKind,
)


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
        c.claim_id.value: c for c in claims if c.trust is m.TrustState.ESTABLISHED
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
    authority_change = False
    for value in affected:
        claim = established_claims.get(value)
        if claim is not None:
            binding = claim.authority
            if (
                binding is not None
                and binding.status is m.AuthorityStatus.ACCEPTED
                and claim.freshness.state is m.FreshnessState.CURRENT
            ):
                authority_change = True
                break
        relationship = established_rels.get(value)
        if (
            relationship is not None
            and relationship.kind is m.RelationshipKind.GOVERNED_BY
        ):
            authority_change = True
            break
    if authority_change:
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
    target_item_ids = {c.claim_id.value for c in claims if c.subject == sid} | {
        r.relationship_id.value
        for r in relationships
        if r.source == sid or r.target == sid
    }
    if any(
        value in established_rels
        and established_rels[value].kind is m.RelationshipKind.CROSSES_BOUNDARY
        for value in affected
    ) or (
        sid.subject_kind is m.SubjectKind.BOUNDARY and bool(affected & target_item_ids)
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
        and established_claims[value].kind is m.ClaimKind.INVARIANT_CONSTRAINT
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
            c.kind is m.ClaimKind.LIFECYCLE_STATE for c in established_claims.values()
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
