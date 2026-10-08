"""Offset page-token mechanics shared by shell listings (plan §5, I-39).

Page tokens are opaque listing cursors only (`pg:<offset>`), unrelated to
interpretation continuations. Unknown or malformed tokens fail closed.
No semantic content is interpreted here: pure slicing plus BoundInfo.
"""

from __future__ import annotations

from span.core import model as m

__all__ = [
    "parse_page_token",
    "next_page_token",
    "parse_service_token",
    "format_service_token",
    "paginate",
]

_PREFIX = "pg:"


def parse_page_token(page_token: str | None) -> int:
    """Decode a token to its listing offset (fail closed on misuse)."""
    if page_token is None:
        return 0
    if not page_token.startswith(_PREFIX):
        raise ValueError(f"unknown page token: {page_token}")
    try:
        offset = int(page_token[len(_PREFIX):])
    except ValueError:
        raise ValueError(f"unknown page token: {page_token}") from None
    if offset < 0:
        raise ValueError(f"unknown page token: {page_token}")
    return offset


def next_page_token(offset: int) -> str:
    """Encode a listing offset as the token for the next page."""
    return f"{_PREFIX}{offset}"


def parse_service_token(page_token: str | None) -> tuple[int, int, int]:
    """Decode an answer-level token to per-list offsets (fail closed).

    Answer tokens are ``pg:<claims_skip>:<rels_skip>:<questions_skip>``.
    An absent token begins at zero. Pre-cutover two-offset tokens are
    rejected with a typed invalid-token error; no dual-format fallback.
    """
    if page_token is None:
        return (0, 0, 0)
    if not page_token.startswith(_PREFIX):
        raise ValueError(f"unknown page token: {page_token}")
    parts = page_token[len(_PREFIX):].split(":")
    try:
        if len(parts) == 3:
            offsets = (int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            raise ValueError(f"unknown page token: {page_token}")
    except ValueError:
        raise ValueError(f"unknown page token: {page_token}") from None
    if offsets[0] < 0 or offsets[1] < 0 or offsets[2] < 0:
        raise ValueError(f"unknown page token: {page_token}")
    return offsets


def format_service_token(
    claims_next: int | None, rels_next: int | None,
    questions_next: int | None = 0,
) -> str | None:
    """Encode per-list next offsets.

    Offsets always advance past shown items, including on exhausted
    sides: re-querying windows from the consumed position, so later
    arrivals on an exhausted side still surface. ``None`` only when
    all sides are exhausted.
    """
    if (
        claims_next is None and rels_next is None
        and (questions_next is None or questions_next == 0)
    ):
        # Preserve v0.6 two-None fast path only when no question page.
        if questions_next in (None, 0):
            return None
    left = claims_next if claims_next is not None else 0
    right = rels_next if rels_next is not None else 0
    qskip = questions_next if questions_next is not None else 0
    if qskip == 0 and left == 0 and right == 0 and (
        claims_next is None and rels_next is None
    ):
        return None
    return f"{_PREFIX}{left}:{right}:{qskip}"


def paginate(
    items: tuple[object, ...],
    max_results: int,
    category: str,
    page_token: str | None,
    requested_max_depth: int = 0,
) -> tuple[tuple[object, ...], m.BoundInfo]:
    """Slice one listing page and describe it deterministically."""
    offset = parse_page_token(page_token)
    kept = items[offset:offset + max_results]
    remaining = len(items) - (offset + len(kept))
    truncated = remaining > 0
    return tuple(kept), m.BoundInfo(
        requested_max_results=max_results,
        requested_max_depth=requested_max_depth,
        returned_results=len(kept),
        truncated=truncated,
        truncated_category=category if truncated else None,
        continuation_token=(
            next_page_token(offset + len(kept)) if truncated else None
        ),
    )
