"""Span service leaf ref constructors (v0.6 §14 Amendment A-01).

Pure converters over canonical carriers. Bottom layer: no intra-service
imports. Verbatim from ``span.service_operations``; only the module
path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.core.refs import ref_value

__all__ = [
    "_claim_ref",
    "_relationship_ref",
    "_item_ref",
    "_ref_value",
]


def _claim_ref(claim: m.SemanticClaim) -> m.ClaimRef:
    return m.ClaimRef(id=claim.claim_id)


def _relationship_ref(rel: m.SemanticRelationship) -> m.RelationshipRef:
    return m.RelationshipRef(id=rel.relationship_id)


def _item_ref(
    item: m.SemanticClaim | m.SemanticRelationship,
) -> m.ClaimRef | m.RelationshipRef:
    if isinstance(item, m.SemanticClaim):
        return _claim_ref(item)
    return _relationship_ref(item)


def _ref_value(ref: m.ClaimRef | m.RelationshipRef) -> str:
    return ref_value(ref)
