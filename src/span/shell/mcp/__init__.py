"""MCP transport adapter package (plan §4.2–4.4)."""

from __future__ import annotations

from span.shell.mcp.adapter import McpAdapter  # noqa: F401
from span.shell.mcp.models import ServiceContext, ToolResult  # noqa: F401
from span.shell.mcp.schemas import (  # noqa: F401
    _REQUEST_CLASS,
    TOOL_DESCRIPTIONS,
    TOOL_NAMES,
    TOOL_OUTPUT_SCHEMAS,
    TOOL_OUTPUT_TYPES,
    TOOL_SCHEMAS,
)
from span.shell.mcp.wire import (  # noqa: F401
    canonical_result_payload,
    decode_request,
    encode_result,
)

__all__ = [
    "TOOL_NAMES",
    "TOOL_SCHEMAS",
    "TOOL_OUTPUT_SCHEMAS",
    "TOOL_DESCRIPTIONS",
    "ToolResult",
    "ServiceContext",
    "McpAdapter",
    "decode_request",
    "encode_result",
    "canonical_result_payload",
]
