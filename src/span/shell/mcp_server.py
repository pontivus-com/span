"""MCP server runtime (stdio transport only).

Wires the thin lifecycle adapter to the selected MCP SDK. All semantic
ingress/egress lives in the adapter: canonical contracts in, canonical JSON
out. This module transports tool specs, arguments and results, and registers
repository identity at startup.

The low-level request handlers are used so client arguments reach the one
strict ingress parse unmodified: no second semantic model, no coercion layer,
no fallback parsing.
"""

from __future__ import annotations

import argparse as _argparse
import asyncio as _asyncio
import pathlib as _pathlib
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.shell.context import (
    open_repository_context as _open_context,
    provision_repository as _provision,
)
from span.shell.mcp import (
    TOOL_DESCRIPTIONS,
    TOOL_NAMES,
    TOOL_OUTPUT_SCHEMAS,
    TOOL_SCHEMAS,
    McpAdapter,
    ServiceContext,
)
from span.shell.structural import repository_id_from_config

__all__ = [
    "ServerConfig",
    "provision_repository",
    "open_repository_context",
    "handle_list_tools",
    "handle_call_tool",
    "build_server",
    "main",
]


@_dataclass(frozen=True)
class ServerConfig:
    """Server runtime configuration (transport-owned, never semantic)."""

    data_dir: _pathlib.Path


def provision_repository(
    config: ServerConfig,
    request: m.InitializeRepositoryRequest,
) -> tuple[ServiceContext, m.InitializeRepositoryResult]:
    """Explicit provisioning bound to this server's data directory."""
    return _provision(config.data_dir, request)


def open_repository_context(
    config: ServerConfig,
    repository_locator: str,
) -> tuple[str, ServiceContext]:
    """Open an already-provisioned repository without setup."""
    return _open_context(config.data_dir, repository_locator)


#: Repository-scoped tools: their descriptions carry registered canonical IDs
#: at list time so agents discover identity before the first scoped call.
_REPO_SCOPED_TOOLS = frozenset(
    {
        "start_context",
        "understand_question",
        "understand_retrieve",
        "reassess",
        "verification_support",
        "evidence_start",
        "evidence_extend",
        "record_create",
        "record_add",
        "record_confirm",
        "record_correct",
        "record_replace",
        "record_withdraw",
        "record_challenge",
        "record_update",
        "record_verification",
        "locate",
        "neighbors",
    }
)


def handle_list_tools(adapter: McpAdapter) -> list[dict]:
    """Tool specs verbatim from the adapter (one source of truth)."""
    registered = list(adapter.registered_repository_ids())
    if registered:
        scope_note = " Registered repositories: " + ", ".join(registered) + "."
    else:
        scope_note = (
            " No repositories registered yet; call " "initialize_repository first."
        )
    specs = []
    for name in TOOL_NAMES:
        description = TOOL_DESCRIPTIONS[name]
        if name in _REPO_SCOPED_TOOLS:
            description += scope_note
        specs.append(
            {
                "name": name,
                "description": description,
                "inputSchema": TOOL_SCHEMAS[name],
                "outputSchema": TOOL_OUTPUT_SCHEMAS[name],
            }
        )
    return specs


def handle_call_tool(
    adapter: McpAdapter, name: str, arguments: dict
) -> tuple[str, bool]:
    """Invoke one tool; returns (content JSON, is_error)."""
    result = adapter.dispatch(name, arguments or {})
    return result.content, result.is_error


def build_server(adapter: McpAdapter):
    """Construct the SDK server with Span's two handlers."""
    from mcp.server import Server
    import mcp.types as _types

    try:
        from span import __version__ as _pkg_version
    except Exception:
        _pkg_version = "unknown"
    try:
        server: Server = Server("span", version=str(_pkg_version))
    except TypeError:  # older SDK without version kwarg
        server = Server("span")

    async def _list_tools(_request: object, _params: object) -> object:
        return _types.ListToolsResult(
            tools=[
                _types.Tool(
                    name=spec["name"],
                    description=spec["description"],
                    inputSchema=spec["inputSchema"],
                    outputSchema=spec["outputSchema"],
                )
                for spec in handle_list_tools(adapter)
            ]
        )

    async def _call_tool(_request: object, params: object) -> object:
        name = params.name  # type: ignore[union-attr]
        arguments = params.arguments or {}  # type: ignore[union-attr]
        tool_result = adapter.dispatch(name, arguments)
        return _types.CallToolResult(
            content=[_types.TextContent(type="text", text=tool_result.content)],
            structuredContent=tool_result.structured_content,
            isError=tool_result.is_error,
        )

    server.add_request_handler("tools/list", _types.PaginatedRequestParams, _list_tools)
    server.add_request_handler("tools/call", _types.CallToolRequestParams, _call_tool)
    return server


def _parse_args(argv: list[str] | None = None) -> _argparse.Namespace:
    parser = _argparse.ArgumentParser(
        prog="span-mcp",
        description=(
            "Span maintained-understanding MCP server (stdio transport). "
            "Repositories are registered explicitly at startup; per-request "
            "work never initializes, migrates, or rebuilds a store."
        ),
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory for schema-10 lifecycle stores.",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="REPO_PATH",
        help=(
            "Register a repository at startup (repeatable; e.g. "
            "--repo /path/to/repo). Provider-neutral locator; the shell "
            "resolves the structural provider internally."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Server entry point (`span-mcp` console script, stdio)."""
    args = _parse_args(argv)
    config = ServerConfig(data_dir=_pathlib.Path(args.data_dir))
    adapter = McpAdapter(
        provisioner=lambda request: provision_repository(config, request),
        context_loader=lambda locator: open_repository_context(config, locator)[1],
    )
    # Startup registration is transport-only: it advertises canonical
    # identity before serving MCP and performs no provider build, store open,
    # or target work. Provisioning remains explicit.
    for repository_locator in args.repo:
        repository_id = repository_id_from_config(repository_locator)
        adapter.register_repository_locator(repository_id, repository_locator)
    _asyncio.run(_serve(adapter))


async def _serve(adapter: McpAdapter) -> None:
    from mcp.server.stdio import stdio_server

    server = build_server(adapter)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    main()
