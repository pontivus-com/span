"""Server-owned lifecycle identifiers shared by lifecycle services."""

from __future__ import annotations

import uuid as _uuid

__all__ = ["server_context_id", "server_selection_id", "server_cursor_id"]


def _server_identity(prefix: str) -> str:
    return f"{prefix}{_uuid.uuid4().hex}"


def server_context_id() -> str:
    """Issue one server-owned investigation context identity."""
    return _server_identity("ctx-srv-")


def server_selection_id() -> str:
    """Issue one opaque durable selection identity."""
    return _server_identity("sel-srv-")


def server_cursor_id() -> str:
    """Issue one opaque durable delivery cursor identity."""
    return _server_identity("cur-srv-")
