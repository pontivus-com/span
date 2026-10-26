"""Page-token mechanics: two cursor grammars, one owner (plan §5, I-39).

Page tokens are opaque listing cursors, unrelated to interpretation
continuations. Exactly two grammars exist:

* ``pg:<offset>`` — a plain listing offset, for listings whose ordering the
  store owns.
* ``pgv:<version>:<offset>[:<offset>...]`` — a version-bound cursor carrying one
  to four offsets. The version binds the page to the query, membership, or
  selected question it was issued against, so drift restarts the listing
  instead of silently skipping. Structural listings carry one offset; service
  answer cursors carry three; scoped status cursors carry four.

Unknown or malformed tokens fail closed. No semantic content is interpreted
here: pure slicing plus ``BoundInfo``.
"""

from __future__ import annotations

import hashlib as _hashlib

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
    "format_scope_token",
    "parse_scope_token",
    "parse_service_token_bound",
    "paginate",
    "INVALID_PAGE_TOKEN_MESSAGE",
    "STALE_CONTINUATION_PREFIX",
]

_PREFIX = "pg:"
_VERSIONED_PREFIX = "pgv:"

#: The public diagnostic for any unusable cursor. Callers raising their own
#: typed error reuse this text instead of restating it.
INVALID_PAGE_TOKEN_MESSAGE = (
    "page token is invalid for this request; restart pagination from the "
    "first page with page_token omitted"
)

#: Prefix of the drift diagnostic; adapters map it to their typed error.
STALE_CONTINUATION_PREFIX = "stale listing continuation"


def parse_page_token(page_token: str | None) -> int:
    """Decode a plain ``pg:`` token to its listing offset (fail closed)."""
    if page_token is None:
        return 0
    if not page_token.startswith(_PREFIX):
        raise ValueError(f"unknown page token: {page_token}")
    try:
        offset = int(page_token[len(_PREFIX) :])
    except ValueError:
        raise ValueError(f"unknown page token: {page_token}") from None
    if offset < 0:
        raise ValueError(f"unknown page token: {page_token}")
    return offset


def next_page_token(offset: int) -> str:
    """Encode a listing offset as the token for the next page."""
    return f"{_PREFIX}{offset}"


def question_digest(*parts: str) -> str:
    """Digest binding pages to their selected question (S4 §5.4).

    Covers operation, repository, target identity, service-derived question
    identity or default marker, and listing-affecting filters. 16 hex chars of
    sha256 over exact UTF-8 bytes. Binds pages to the selected question; it does
    not promise snapshot isolation.
    """
    payload = "\x00".join(parts)
    return _hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _format_version(version: str) -> None:
    if not version or ":" in version:
        raise ValueError(f"invalid listing version: {version!r}")


def _parse_versioned_offsets(
    page_token: str | None,
    *,
    version: str | None,
    expected: int,
) -> tuple[str, tuple[int, ...]]:
    """Decode one ``pgv`` cursor, enforcing its offset count and version."""
    if page_token is None:
        return "", (0,) * expected
    if not page_token.startswith(_VERSIONED_PREFIX):
        raise ValueError(f"unknown page token: {page_token}")
    body = page_token[len(_VERSIONED_PREFIX) :]
    fields = body.split(":")
    if len(fields) != expected + 1:
        raise ValueError(f"unknown page token: {page_token}")
    token_version, *raw_offsets = fields
    try:
        offsets = tuple(int(part) for part in raw_offsets)
    except ValueError:
        raise ValueError(f"unknown page token: {page_token}") from None
    if not token_version or any(offset < 0 for offset in offsets):
        raise ValueError(f"unknown page token: {page_token}")
    if version is not None and token_version != version:
        raise ValueError(
            f"{STALE_CONTINUATION_PREFIX}: token version "
            f"{token_version!r} != current {version!r}"
        )
    return token_version, offsets


def format_versioned_token(version: str, offset: int) -> str:
    """Encode a version-bound structural listing cursor ([design note F](docs/design-references.md#f) §4.3).

    Distinct from plain ``pg:`` offsets; the two are never interchanged. The
    version binds the query hash and listing version (index mtime + fingerprint).
    """
    _format_version(version)
    if offset < 0:
        raise ValueError(f"invalid listing offset: {offset}")
    return f"{_VERSIONED_PREFIX}{version}:{offset}"


def parse_versioned_token(
    page_token: str | None,
    *,
    version: str,
) -> int:
    """Decode a version-bound structural cursor, failing closed on drift.

    ``None`` starts the listing at zero. A well-formed token bound to a
    different version raises ValueError naming the observed version; callers
    map this to the typed stale-continuation error and restart the listing.
    """
    _, offsets = _parse_versioned_offsets(page_token, version=version, expected=1)
    return offsets[0]


def format_scope_token(
    version: str,
    frontier_offset: int,
    claims_offset: int = 0,
    relationships_offset: int = 0,
    questions_offset: int = 0,
) -> str:
    """Encode a scoped status cursor: frontier position plus item offsets.

    A scope read can stop in two different places, so its cursor names both:
    where the subject frontier resumes and — when one subject's lists did not
    fit on the page — how far into those lists the page reached. The item half
    stays zero for a page that carried whole subjects.
    """
    _format_version(version)
    return (
        f"{_VERSIONED_PREFIX}{version}:{frontier_offset}:"
        f"{claims_offset}:{relationships_offset}:{questions_offset}"
    )


def parse_scope_token(
    page_token: str | None,
    *,
    version: str | None = None,
) -> tuple[int, int, int, int]:
    """Decode a scoped status cursor to (frontier, claims, rels, questions).

    ``None`` starts at the first page. ``version`` binds the cursor to the
    query and membership it was issued against; a different version fails
    closed naming both, so a changed scope restarts instead of skipping. A
    token from another listing operation has a different field count and is
    rejected here rather than misread.
    """
    _, offsets = _parse_versioned_offsets(page_token, version=version, expected=4)
    return (offsets[0], offsets[1], offsets[2], offsets[3])


def format_question_token(
    digest: str,
    claims_next: int | None,
    rels_next: int | None,
    questions_next: int | None = 0,
) -> str | None:
    """Encode per-list offsets bound to a question digest (S4 §5.4)."""
    left = claims_next if claims_next is not None else 0
    right = rels_next if rels_next is not None else 0
    qskip = questions_next if questions_next is not None else 0
    if left == 0 and right == 0 and qskip == 0:
        return None
    if not digest or ":" in digest:
        raise ValueError(f"invalid question digest: {digest!r}")
    return f"{_VERSIONED_PREFIX}{digest}:{left}:{right}:{qskip}"


def parse_question_token(
    page_token: str | None,
) -> tuple[str, int, int, int]:
    """Decode a question-bound cursor to (digest, claims, rels, questions)."""
    if page_token is None:
        raise ValueError("missing page token")
    digest, offsets = _parse_versioned_offsets(page_token, version=None, expected=3)
    return digest, offsets[0], offsets[1], offsets[2]


def format_service_token(
    claims_next: int | None,
    rels_next: int | None,
    questions_next: int | None = 0,
    query_digest: str = "default",
) -> str | None:
    """Encode per-list offsets for a service answer cursor.

    Service answer cursors use the one version-bound grammar with a default
    digest for non-question-bound listings; question-bound callers pass the
    real digest.
    """
    return format_question_token(query_digest, claims_next, rels_next, questions_next)


def parse_service_token(page_token: str | None) -> tuple[int, int, int]:
    """Decode an answer-level token to per-list offsets (fail closed).

    Only the version-bound service grammar is accepted; a plain ``pg:`` listing
    cursor or a token with the wrong offset count is rejected with a
    restart-listing diagnostic. No alternative fallback.
    """
    if page_token is None:
        return (0, 0, 0)
    try:
        _, offsets = _parse_versioned_offsets(page_token, version=None, expected=3)
    except ValueError:
        raise ValueError(INVALID_PAGE_TOKEN_MESSAGE) from None
    return (offsets[0], offsets[1], offsets[2])


def parse_service_token_bound(
    page_token: str | None,
) -> tuple[str, int, int, int]:
    """Decode a bound service token, preserving its query digest.

    ``None`` starts a listing at zero with an empty digest marker. Callers that
    require query binding compare the returned digest with the request-derived
    digest; callers that only need offsets use ``parse_service_token``.
    """
    if page_token is None:
        return ("", 0, 0, 0)
    return parse_question_token(page_token)


def paginate(
    items: tuple[object, ...],
    max_results: int,
    category: str,
    page_token: str | None,
    requested_max_depth: int = 0,
) -> tuple[tuple[object, ...], m.BoundInfo]:
    """Slice one listing page and describe it deterministically."""
    offset = parse_page_token(page_token)
    kept = items[offset : offset + max_results]
    remaining = len(items) - (offset + len(kept))
    truncated = remaining > 0
    return tuple(kept), m.BoundInfo(
        requested_max_results=max_results,
        requested_max_depth=requested_max_depth,
        returned_results=len(kept),
        truncated=truncated,
        truncated_category=category if truncated else None,
        continuation_token=(next_page_token(offset + len(kept)) if truncated else None),
    )
