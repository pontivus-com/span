"""Span service shared answer primitives (v0.6 §14 Amendment A-01).

Downstream-neutral constructors and selectors used by every answer
composer plus ``repository.py``. Imports only ``refs``,
``core.validation`` (pure), port signatures, ``model``, and
``core.paging`` — never ``freshness.py`` or ``questions.py``.
Verbatim from ``span.service_operations``; only the module path
changed.
"""

from __future__ import annotations


from span.core import model as m
from span.core import paging as _paging


def _answer_id(prefix: str, request_part: str, subject_part: str) -> m.AnswerId:
    import hashlib as _hashlib

    digest = _hashlib.sha256(
        f"{prefix}:{request_part}:{subject_part}".encode("utf-8")
    ).hexdigest()[:16]
    return m.AnswerId(f"{prefix}-{digest}")


def _bounds_key(bounds: m.QueryBounds) -> str:
    """Deterministic listing-affecting bounds identity (M-06.5).

    Every bounds field that can change the selected/ordered page slice
    is part of the query digest; `page_token` is never part of it.
    """
    return "|".join(
        str(value)
        for value in (
            bounds.max_results,
            bounds.max_depth,
            bounds.max_subjects,
            bounds.max_evidence_units,
            bounds.max_evidence_bytes,
            bounds.max_candidate_claims,
            bounds.max_candidate_relationships,
        )
    )


def _query_digest(
    operation: str,
    repository_id: str,
    target_key: str,
    question_key: str,
    bounds: m.QueryBounds,
) -> str:
    """Query digest binding a service page token to its request (M-06.5)."""
    return _paging.question_digest(
        operation,
        repository_id,
        target_key,
        question_key,
        _bounds_key(bounds),
    )


def _validate_service_token(
    page_token: str | None,
    expected_digest: str,
) -> None:
    """Reject a page token bound to a different query (M-06.5a).

    The public diagnostic names the remedy, never the internal encoding.
    """
    if page_token is None:
        return
    try:
        digest, _, _, _ = _paging.parse_question_token(page_token)
    except ValueError:
        raise ValueError(_paging.INVALID_PAGE_TOKEN_MESSAGE) from None
    if digest != expected_digest:
        raise ValueError(_paging.INVALID_PAGE_TOKEN_MESSAGE)


def _next_service_offsets(
    page_token: str | None,
    kept_claims: tuple[m.SemanticClaim, ...],
    kept_rels: tuple[m.SemanticRelationship, ...],
    loaded_claims: tuple[m.SemanticClaim, ...],
    loaded_rels: tuple[m.SemanticRelationship, ...],
    claims_token: str | None,
    rels_token: str | None,
    questions_skip: int = 0,
    questions_remaining: int = 0,
    expected_digest: str | None = None,
) -> tuple[int, int, int] | None:
    """Offsets of the next item page, or ``None`` when every list is done.

    Each side advances past shown items only, so every item is reachable
    exactly once. A side is exhausted when its load cursor is done and
    everything loaded was shown.
    """
    # Decode incoming offsets through the cursor owner; any other grammar or
    # a token bound to a different query forces a restart.
    if page_token is None:
        claims_skip, rels_skip, qskip = 0, 0, 0
    else:
        try:
            token_digest, claims_skip, rels_skip, qskip = _paging.parse_question_token(
                page_token
            )
        except ValueError:
            raise ValueError(_paging.INVALID_PAGE_TOKEN_MESSAGE) from None
        if expected_digest is not None and token_digest != expected_digest:
            raise ValueError(_paging.INVALID_PAGE_TOKEN_MESSAGE)
    claims_exhausted = claims_token is None and len(kept_claims) >= len(loaded_claims)
    rels_exhausted = rels_token is None and len(kept_rels) >= len(loaded_rels)
    questions_exhausted = questions_remaining <= 0
    if claims_exhausted and rels_exhausted and questions_exhausted:
        return None
    return (
        claims_skip + len(kept_claims),
        rels_skip + len(kept_rels),
        (qskip + questions_skip) if not questions_exhausted else qskip,
    )


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
    query_digest: str = "default",
    expected_digest: str | None = None,
) -> str | None:
    """Answer-level next token from shown counts (plan I-39; I S4 pgq).

    Binds pages to the selected question via query_digest. Rejects old
    pg: service cursors upstream; emits pgq only. Each side advances
    past shown items only.
    """
    offsets = _next_service_offsets(
        page_token,
        kept_claims,
        kept_rels,
        loaded_claims,
        loaded_rels,
        claims_token,
        rels_token,
        questions_skip=questions_skip,
        questions_remaining=questions_remaining,
        expected_digest=expected_digest,
    )
    if offsets is None:
        return None
    return _paging.format_question_token(query_digest, *offsets)
