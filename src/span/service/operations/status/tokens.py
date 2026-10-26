"""Status cursors: the operation's one page-token grammar.

Every status cursor is issued and read here, so the answer token shape has one
owner and the shell paging module is reached from one place.
"""

from __future__ import annotations

from span.ports.structural import StaleContinuationError
from span.core.paging import (
    INVALID_PAGE_TOKEN_MESSAGE,
    format_question_token as _format_question_token,
    format_scope_token as _format_scope_token,
    format_service_token as _format_service_token,
    format_versioned_token as _format_versioned_token,
    parse_scope_token as _paging_parse_scope_token,
    parse_service_token_bound as _parse_service_token_bound,
)

__all__ = [
    "_format_question_token",
    "_format_scope_token",
    "_format_service_token",
    "_format_versioned_token",
    "_parse_service_token_bound",
    "_scope_cursor",
]


def _scope_cursor(page_token: str | None) -> tuple[int, int, int, int]:
    """Read a scope cursor's offsets without validating its version.

    The version binds the membership fingerprint, which is only known after
    the frontier is resolved; the offsets are safe to read first. Returns
    (frontier, claims, relationships, questions).
    """
    try:
        return _paging_parse_scope_token(page_token)
    except ValueError:
        raise StaleContinuationError(INVALID_PAGE_TOKEN_MESSAGE) from None


def _parse_scope_token(page_token: str | None, *, version: str) -> None:
    """Validate a scope cursor against its version, or fail closed."""
    try:
        _paging_parse_scope_token(page_token, version=version)
    except ValueError as exc:
        raise StaleContinuationError(str(exc)) from None
