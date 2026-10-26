"""Public schema surface (re-exported)."""

from __future__ import annotations

from span.core.schema.projection import (  # noqa: F401
    schema_for_request,
    schema_for_result,
    definition_closure,
)
from span.core.schema.wire import (  # noqa: F401
    from_wire,
    to_wire,
    to_wire_root,
    compact_payload,
)

__all__ = [
    "schema_for_request",
    "schema_for_result",
    "definition_closure",
    "from_wire",
    "to_wire",
    "to_wire_root",
    "compact_payload",
]
