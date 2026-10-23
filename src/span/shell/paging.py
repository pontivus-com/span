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
    "parse_question_token",
    "format_question_token",
    "question_digest",
    "format_versioned_token",
    "parse_versioned_token",
    "paginate",
]

_PREFIX = "pg:"
_QUESTION_PREFIX = "pgq:"
_VERSIONED_PREFIX = "pgv:"


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

    Addendum I S4 §5.4 cutover: service answer cursors use the single
    grammar `pgq:<query_digest>:<claims_offset>:<relationships_offset>:
    <questions_offset>`. Old `pg:` service cursors are rejected with a
    restart-listing diagnostic; no alternative fallback. Plain single-offset
    store cursors (`pg:<offset>`) and structural `pgv` cursors retain
    their distinct contracts and are never interchanged here.
    """
    if page_token is None:
        return (0, 0, 0)
    if page_token.startswith(_QUESTION_PREFIX):
        # New grammar handled by parse_question_token; for callers that
        # only need offsets without digest binding, decode offsets here.
        try:
            _, c, r, q = parse_question_token(page_token)
        except ValueError:
            raise ValueError(
                f"unknown page token: {page_token}; restart the listing "
                "from page one with page_token null"
            ) from None
        return (c, r, q)
    # Old service cursors rejected atomically.
    raise ValueError(
        "page token is invalid for this request; restart pagination from "
        "the first page with page_token omitted"
    )


def question_digest(*parts: str) -> str:
    """Digest binding pages to their selected question (S4 §5.4).

    Covers operation, repository, target identity, service-derived
    question identity or default marker, and listing-affecting filters.
    16 hex chars of sha256 over exact UTF-8 bytes. Binds pages to the
    selected question; does not promise snapshot isolation.
    """
    import hashlib as _hashlib

    payload = "\x00".join(parts)
    return _hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def format_question_token(
    digest: str,
    claims_next: int | None,
    rels_next: int | None,
    questions_next: int | None = 0,
) -> str | None:
    """Encode per-list offsets bound to a question digest (S4 §5.4)."""
    if (
        claims_next is None and rels_next is None
        and (questions_next is None or questions_next == 0)
    ):
        if questions_next in (None, 0):
            return None
    left = claims_next if claims_next is not None else 0
    right = rels_next if rels_next is not None else 0
    qskip = questions_next if questions_next is not None else 0
    if qskip == 0 and left == 0 and right == 0 and (
        claims_next is None and rels_next is None
    ):
        return None
    if not digest or ":" in digest:
        raise ValueError(f"invalid question digest: {digest!r}")
    return f"{_QUESTION_PREFIX}{digest}:{left}:{right}:{qskip}"


def parse_question_token(
    page_token: str | None,
) -> tuple[str, int, int, int]:
    """Decode pgq token to (digest, claims, rels, questions)."""
    if page_token is None:
        raise ValueError("missing pgq page token")
    if not page_token.startswith(_QUESTION_PREFIX):
        raise ValueError(
            f"unknown page token: {page_token}; restart the listing "
            "from page one with page_token null"
        )
    body = page_token[len(_QUESTION_PREFIX):]
    parts = body.split(":")
    if len(parts) != 4:
        raise ValueError(
            f"unknown page token: {page_token}; restart the listing "
            "from page one with page_token null"
        )
    digest, c_text, r_text, q_text = parts
    try:
        c, r, q = int(c_text), int(r_text), int(q_text)
    except ValueError:
        raise ValueError(
            f"unknown page token: {page_token}; restart the listing "
            "from page one with page_token null"
        ) from None
    if not digest or c < 0 or r < 0 or q < 0:
        raise ValueError(
            f"unknown page token: {page_token}; restart the listing "
            "from page one with page_token null"
        )
    return digest, c, r, q


def parse_service_token_bound(
    page_token: str | None,
) -> tuple[str, int, int, int]:
    """Decode a bound service token, preserving its query digest.

    `None` starts a listing at zero with an empty digest marker. Callers
    that require query binding compare the returned digest with the
    request-derived digest; callers that only need offsets use
    ``parse_service_token``.
    """
    if page_token is None:
        return ("", 0, 0, 0)
    return parse_question_token(page_token)


def format_service_token(
    claims_next: int | None, rels_next: int | None,
    questions_next: int | None = 0,
    query_digest: str = "default",
) -> str | None:
    """Encode per-list offsets (I S4 §5.4 cutover: pgq only).

    Service answer cursors use the single grammar
    `pgq:<query_digest>:<claims>:<relationships>:<questions>`. Old `pg:`
    service cursors are rejected. This wrapper emits pgq with a default
    digest for non-question-bound listings; question-bound callers must
    use format_question_token with the real digest.
    """
    if (
        claims_next is None and rels_next is None
        and (questions_next is None or questions_next == 0)
    ):
        if questions_next in (None, 0):
            return None
    left = claims_next if claims_next is not None else 0
    right = rels_next if rels_next is not None else 0
    qskip = questions_next if questions_next is not None else 0
    if qskip == 0 and left == 0 and right == 0 and (
        claims_next is None and rels_next is None
    ):
        return None
    return format_question_token(query_digest, left, right, qskip)


def format_versioned_token(version: str, offset: int) -> str:
    """Encode a version-bound listing cursor (Addendum F §4.3).

    Distinct format from plain ``pg:`` offsets; the two are never
    interchanged. The version binds the query hash and listing version
    (index mtime + index fingerprint).
    """
    if not version or ":" in version:
        raise ValueError(f"invalid listing version: {version!r}")
    if offset < 0:
        raise ValueError(f"invalid listing offset: {offset}")
    return f"{_VERSIONED_PREFIX}{version}:{offset}"


def parse_versioned_token(
    page_token: str | None, *, version: str,
) -> int:
    """Decode a version-bound cursor, failing closed on version drift.

    ``None`` starts the listing at zero. A well-formed token bound to a
    different version raises ValueError naming the observed version —
    callers map this to the typed stale-continuation error and restart
    the listing from page one.
    """
    if page_token is None:
        return 0
    if not page_token.startswith(_VERSIONED_PREFIX):
        raise ValueError(f"unknown page token: {page_token}")
    body = page_token[len(_VERSIONED_PREFIX):]
    token_version, _, offset_text = body.rpartition(":")
    try:
        offset = int(offset_text)
    except ValueError:
        raise ValueError(f"unknown page token: {page_token}") from None
    if offset < 0 or not token_version:
        raise ValueError(f"unknown page token: {page_token}")
    if token_version != version:
        raise ValueError(
            f"stale listing continuation: token version "
            f"{token_version!r} != current {version!r}"
        )
    return offset


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
