"""Span service subject resolution + store-read plumbing (v0.6 §14 Amendment A-01).

Identity resolution over the structural source (observations only —
ambiguity is never overridden, names alone are never identity, §4.2)
plus subject-state and coverage-enumeration reads. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.core import validation as _validation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection
from span.core import paging as _paging


def _load_all_coverages_or_defer(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    purpose: str,
) -> tuple[m.InterpretationCoverage, ...]:
    """Unbounded coverage enumeration with bounds-safety deferral (B-03).

    Retirement and withdrawal fanout must see every owning question.
    When the total exceeds the operation bounds the owners cannot be
    safely enumerated, so the unit is rejected/deferred with an
    outstanding-scope requirement — never retired with an incomplete
    fanout, and nothing is partially mutated (raise precedes write).
    """
    try:
        total = store.count_question_coverages(repository_id, scope_root, subject_ids)
    except Exception:
        total = None
    if total is not None and total > bounds.max_results:
        raise _validation.InterpretationUnitRejected(
            (
                f"{purpose}: {total} owning questions exceed "
                f"bounds max_results={bounds.max_results}; deferred with "
                "outstanding scope — narrow the scope and resubmit",
            )
        )
    try:
        return store.load_all_question_coverages(repository_id, scope_root, subject_ids)
    except Exception:
        try:
            return store.load_question_coverages(
                repository_id, scope_root, subject_ids, bounds
            )
        except Exception:
            return ()


def _load_subject_state(
    repository_id: str,
    sid: m.SubjectId,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    direction: StructuralDirection = StructuralDirection.BOTH,
    page_token: str | None = None,
) -> tuple[
    tuple[m.SemanticClaim, ...],
    tuple[m.SemanticRelationship, ...],
    str | None,
    str | None,
]:
    """Load one subject's state window plus per-list next tokens.

    The answer-level token carries per-list offsets
    (``pgq:<digest>:<claims_skip>:<rels_skip>:<questions_skip>``); each load windows
    from its own offset, so every item is reachable exactly once across
    pages. The returned tokens are the raw store cursors (``None`` =
    exhausted).
    """
    claims_skip, rels_skip, _ = _paging.parse_service_token(page_token)
    claim_page = store.load_claims(
        repository_id,
        (sid,),
        tuple(m.ClaimKind),
        bounds,
        _paging.next_page_token(claims_skip) if claims_skip else None,
    )
    rel_page = store.load_relationships(
        repository_id,
        (sid,),
        tuple(m.RelationshipKind),
        direction,
        bounds,
        _paging.next_page_token(rels_skip) if rels_skip else None,
    )
    return (
        claim_page.items,
        rel_page.items,
        claim_page.bound_info.continuation_token,
        rel_page.bound_info.continuation_token,
    )
