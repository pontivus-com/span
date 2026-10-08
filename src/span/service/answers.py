"""Span service shared answer primitives (v0.6 §14 Amendment A-01).

Downstream-neutral constructors and selectors used by every answer
composer plus ``repository.py``. Imports only ``refs``,
``core.validation`` (pure), port signatures, ``model``, and
``shell.paging`` — never ``freshness.py`` or ``questions.py``.
Verbatim from ``span.service_operations``; only the module path
changed.
"""

from __future__ import annotations

from span.core import model as m
from span.core import validation as _validation
from span.ports.store import SemanticStore
from span.shell import paging as _paging
from span.service.refs import (
    _claim_ref,
    _ref_value,
    _relationship_ref,
)

__all__ = [
    "_answer_id",
    "_bound_info",
    "_recorded_conflicts",
    "_conflicts_for",
    "_select_answer_items",
    "_freshness_items_for",
    "_next_service_token",
]


def _answer_id(prefix: str, request_part: str, subject_part: str) -> m.AnswerId:
    import hashlib as _hashlib

    digest = _hashlib.sha256(
        f"{prefix}:{request_part}:{subject_part}".encode("utf-8")
    ).hexdigest()[:16]
    return m.AnswerId(f"{prefix}-{digest}")


def _next_service_token(
    page_token: str | None,
    kept_claims: tuple[m.SemanticClaim, ...],
    kept_rels: tuple[m.SemanticRelationship, ...],
    loaded_claims: tuple[m.SemanticClaim, ...],
    loaded_rels: tuple[m.SemanticRelationship, ...],
    claims_token: str | None,
    rels_token: str | None,
    questions_skip: int = 0,
    questions_remaining: int = 0,
) -> str | None:
    """Answer-level next token from shown counts (plan I-39).

    Each side advances past shown items only, so unshown-but-loaded
    items reappear in the next window instead of being skipped. A side
    is exhausted when its load cursor is done and everything loaded
    was shown.
    """
    claims_skip, rels_skip, qskip = _paging.parse_service_token(page_token)
    claims_exhausted = (
        claims_token is None and len(kept_claims) >= len(loaded_claims)
    )
    rels_exhausted = (
        rels_token is None and len(kept_rels) >= len(loaded_rels)
    )
    questions_exhausted = questions_remaining <= 0
    if claims_exhausted and rels_exhausted and questions_exhausted:
        return None
    return _paging.format_service_token(
        claims_skip + len(kept_claims),
        rels_skip + len(kept_rels),
        (qskip + questions_skip) if not questions_exhausted else qskip,
    )


def _bound_info(
    bounds: m.QueryBounds,
    returned: int,
    truncated: bool,
    category: str | None,
    token: str | None = None,
) -> m.BoundInfo:
    return m.BoundInfo(
        requested_max_results=bounds.max_results,
        requested_max_depth=bounds.max_depth,
        returned_results=returned,
        truncated=truncated,
        truncated_category=category,
        continuation_token=token,
    )


def _recorded_conflicts(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    store: SemanticStore,
) -> tuple[m.SemanticConflict, ...]:
    """Merge validated agent-proposed conflicts (plan §6.4) with derived ones.

    Only pairs whose both sides resolve among the loaded items are shown;
    anything else is a store inconsistency, never guessed into place.
    """
    if not claims and not relationships:
        return ()
    scope = tuple(
        dict.fromkeys(
            [c.subject for c in claims]
            + [r.source for r in relationships]
            + [r.target for r in relationships]
        )
    )
    known = {_claim_ref(c) for c in claims} | {
        _relationship_ref(r) for r in relationships
    }
    merged: list[m.SemanticConflict] = []
    for record in store.load_conflicts(repository_id, scope):
        if record.left in known and record.right in known:
            merged.append(
                m.SemanticConflict(
                    left=record.left,
                    right=record.right,
                    declared_precedence=record.declared_precedence,
                )
            )
    merged.sort(
        key=lambda c: (
            _ref_value(c.left),
            _ref_value(c.right),
        )
    )
    return tuple(merged)


def _conflicts_for(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    store: SemanticStore,
) -> tuple[m.SemanticConflict, ...]:
    """All visible conflicts: core-derived plus recorded proposals."""
    derived = _validation.find_conflicts(claims, relationships)
    recorded = _recorded_conflicts(
        repository_id, claims, relationships, store=store
    )
    seen = {
        (_ref_value(c.left), _ref_value(c.right)) for c in derived
    }
    extra = tuple(
        c for c in recorded
        if (_ref_value(c.left), _ref_value(c.right)) not in seen
    )
    return derived + extra


def _select_answer_items(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    conflicts: tuple[m.SemanticConflict, ...],
    max_results: int,
    extra_mandatory: tuple[str, ...] = (),
) -> tuple[
    tuple[m.SemanticClaim, ...],
    tuple[m.SemanticRelationship, ...],
    tuple[m.SemanticConflict, ...],
    bool,
    str | None,
]:
    """Bounded item selection preserving answer self-containment (I-36).

    Conflict pairs are atomic and their endpoints mandatory: a known
    conflict is never truncated to one visible side. All ref-lists in
    the answer are derived from the kept set only, so no reference
    dangles. Returns kept claims, kept relationships, kept conflicts,
    truncated flag, and first-dropped category.
    """
    kept_conf = list(conflicts[:max_results])
    truncated = len(conflicts) > len(kept_conf)
    category: str | None = "conflicts" if truncated else None

    def _mandatory(pairs: list[m.SemanticConflict]) -> list[str]:
        ids: list[str] = []
        for pair in pairs:
            ids.append(_ref_value(pair.left))
            ids.append(_ref_value(pair.right))
        ids.extend(extra_mandatory)
        return list(dict.fromkeys(ids))

    while kept_conf and (
        len(kept_conf)
        + len(set(_mandatory(kept_conf)) & (
            {c.claim_id.value for c in claims}
            | {r.relationship_id.value for r in relationships}
        )) > max_results
    ):
        kept_conf.pop()
        truncated = True
        if category is None:
            category = "conflicts"
    mandatory = set(_mandatory(kept_conf))
    budget = max_results - len(kept_conf)
    mand_claims = [c for c in claims if c.claim_id.value in mandatory]
    mand_rels = [
        r for r in relationships if r.relationship_id.value in mandatory
    ]
    rest_claims = [c for c in claims if c.claim_id.value not in mandatory]
    rest_rels = [
        r for r in relationships if r.relationship_id.value not in mandatory
    ]
    kept_claims = list(mand_claims)
    kept_rels = list(mand_rels)
    # Fair round-robin fill in stable order: each side advances only
    # past shown items, so per-list page offsets stay exact (I-39).
    while len(kept_claims) + len(kept_rels) < budget and (
        rest_claims or rest_rels
    ):
        if rest_claims:
            kept_claims.append(rest_claims.pop(0))
            if len(kept_claims) + len(kept_rels) >= budget:
                break
        if rest_rels:
            kept_rels.append(rest_rels.pop(0))
    if len(kept_claims) + len(kept_rels) < len(claims) + len(relationships):
        truncated = True
        if category is None:
            category = "claims"
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    kept_conf = [
        pair for pair in kept_conf
        if _ref_value(pair.left) in kept_ids
        and _ref_value(pair.right) in kept_ids
    ]
    return tuple(kept_claims), tuple(kept_rels), tuple(kept_conf), truncated, category


def _freshness_items_for(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.FreshnessItem, ...]:
    """Per-item freshness records for exactly the carried items (I-36)."""
    return tuple(
        [m.FreshnessItem(_claim_ref(c), c.subject, c.freshness, c.trust)
         for c in claims]
        + [m.FreshnessItem(_relationship_ref(r), r.source, r.freshness, r.trust)
           for r in relationships]
    )
