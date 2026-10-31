"""Server-owned lifecycle identifiers shared by lifecycle services."""

from __future__ import annotations

import uuid as _uuid

__all__ = ["server_context_id"]


def server_context_id() -> str:
    """Issue one server-owned investigation context identity."""
    return f"ctx-srv-{_uuid.uuid4().hex}"
