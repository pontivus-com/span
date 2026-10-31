"""MCP transport adapter package (lifecycle surface)."""

from __future__ import annotations

from span.shell.mcp.adapter import McpAdapter  # noqa: F401
from span.shell.mcp.models import (  # noqa: F401
    ServiceContext,
    ToolError,
    ToolResult,
)
from span.shell.mcp.schemas import (  # noqa: F401
    REMOVED_TOOLS,
    TOOL_DESCRIPTIONS,
    TOOL_NAMES,
    TOOL_OUTPUT_SCHEMAS,
    TOOL_OUTPUT_TYPES,
    TOOL_REQUEST_TYPES,
    TOOL_SCHEMAS,
)
from span.shell.mcp.wire import (  # noqa: F401
    canonical_result_payload,
    decode_request,
    encode_error,
    encode_result,
)

__all__ = [
    "REMOVED_TOOLS",
    "TOOL_NAMES",
    "TOOL_SCHEMAS",
    "TOOL_OUTPUT_SCHEMAS",
    "TOOL_DESCRIPTIONS",
    "TOOL_REQUEST_TYPES",
    "TOOL_OUTPUT_TYPES",
    "ToolError",
    "ToolResult",
    "ServiceContext",
    "McpAdapter",
    "decode_request",
    "encode_result",
    "encode_error",
    "canonical_result_payload",
]
