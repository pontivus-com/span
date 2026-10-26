"""MCP server runtime (plan Phase 4.2/4.2a). Transport only.

Wires the thin adapter (`shell/mcp.py`) to the selected MCP SDK
(`mcp.server`, MIT). All semantic ingress/egress lives in the
adapter — strict canonical contracts in, canonical JSON out. This
module only transports tool specs, arguments, and results, plus
explicit repository provisioning for initialization (plan §11.1).

The low-level `Server` request handlers are used instead of
signature-derived tool wrappers so client arguments reach the one
strict ingress parse unmodified: no second semantic model, no
coercion layer, no fallback parsing (I-04, I-18, AP-06).
"""

from __future__ import annotations

import argparse as _argparse
import asyncio as _asyncio
import dataclasses as _dataclasses
import pathlib as _pathlib
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.context import (
    open_repository_context as _open_context,
)
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.mcp import (
    TOOL_DESCRIPTIONS,
    TOOL_NAMES,
    TOOL_OUTPUT_SCHEMAS,
    TOOL_SCHEMAS,
    McpAdapter,
    ServiceContext,
)
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural import (
    canonical_root_from_config,
    containing_registered_root,
    repo_root_from_config,
    repository_id_from_config,
    structural_source_from_config,
)
from span.shell.structural.graft import GraftStructuralSource
from span import service as ops

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


def _repo_root_from_config(provider_config: str) -> _pathlib.Path:
    return repo_root_from_config(provider_config)


def provision_repository(
    config: ServerConfig,
    request: ops.SemanticInitializeRepositoryRequest,
) -> tuple[ServiceContext, ops.SemanticInitializeRepositoryResult]:
    """Explicit provisioning for `initialize_repository` (§11.1).

    Provisioning order: structural `ensure_current` (one bounded
    provider-owned build into Span's data directory on a missing or
    stale index; no-op when current) → filesystem evidence setup →
    file-backed store → authority-seed resolution → initialization →
    registration context. Service initialization stays provider
    agnostic; this shell owner selects and manages the provider.

    A missing or malformed provider index after the bounded build is a
    typed actionable setup failure (ValueError); a dirty tree after a
    successful build still provisions (provider available, freshness
    UNVERIFIABLE). Ordinary reads never build.
    """
    structural, repository_id = structural_source_from_config(
        request.repository_locator, data_dir=config.data_dir
    )
    root = _repo_root_from_config(request.repository_locator)
    # Explicit setup hook: bring the provider index current before any
    # evidence/store work. One bounded attempt inside the provider.
    currency = structural.ensure_current(repository_id)
    if isinstance(structural, GraftStructuralSource):
        if not structural.has_index():
            raise ValueError(
                f"structural indexer unavailable for {str(root)!r}: "
                f"{currency.reason}; rerun installation to provision "
                f"the indexer, then retry setup"
            )
    evidence = FilesystemEvidenceSource(repository_id, root)
    config.data_dir.mkdir(parents=True, exist_ok=True)
    store = SqliteSemanticStore(str(config.data_dir / f"{repository_id}.db"))
    resolved_request = request
    if request.authority_seeds:
        # Only an explicit non-empty tuple needs locator resolution.
        # ``None`` preserves and ``()`` clears without a resolution
        # round-trip.
        inventory = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(
                paths=(),
                evidence_refs=request.authority_seeds,
            ),
            DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
        )
        by_locator = {
            item.evidence_ref.locator: item.evidence_ref for item in inventory.items
        }
        resolved_seeds: list[m.EvidenceRef] = []
        for seed in request.authority_seeds:
            try:
                resolved_seeds.append(by_locator[seed.locator])
            except KeyError:
                raise ValueError(
                    "unknown authority seed locator: " f"{seed.locator}"
                ) from None
        resolved_request = _dataclasses.replace(
            request, authority_seeds=tuple(resolved_seeds)
        )
    canonical_root = canonical_root_from_config(request.repository_locator)
    result = ops.initialize_repository(
        resolved_request,
        repository_id=repository_id,
        structural=structural,
        evidence=evidence,
        store=store,
        canonical_root=canonical_root,
        nested_within=containing_registered_root(config.data_dir, canonical_root),
    )
    context = ServiceContext(
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=ContinuationStore(),
        authority_seeds=store.load_repository_authority_seeds(repository_id),
    )
    return context, result


def open_repository_context(
    config: ServerConfig,
    repository_locator: str,
) -> tuple[str, ServiceContext]:
    """Open an already-provisioned repository context without setup.

    Repository registration at MCP process startup is transport-only.
    The first repository-scoped call opens the working context through
    the canonical shell opener: structural source, filesystem evidence,
    the existing schema-7 semantic store with its persisted authority
    seeds, and continuation state. This never
    calls `ensure_current`, `initialize_repository`, or
    `provision_repository`, and it does not create a store or schema
    for a repository explicit initialization has not provisioned.
    """
    return _open_context(config.data_dir, repository_locator)


#: Repository-scoped tools ([design note H](docs/design-references.md#h) §7): their descriptions carry
#: the currently registered canonical repository IDs at list time so
#: agents discover identity before the first repository-scoped call.
_REPO_SCOPED_TOOLS = frozenset(
    {
        "initialize_target",
        "explain",
        "impact",
        "trace",
        "authority",
        "status",
        "refresh",
        "submit_interpretation",
        "locate",
        "neighbors",
    }
)


def handle_list_tools(adapter: McpAdapter) -> list[dict]:
    """Tool specs verbatim from the adapter (one source of truth).

    `TOOL_DESCRIPTIONS` stays the static capability source; the
    registered-repository note below is transport presentation only,
    appended here so pre-call discovery needs no repository-scoped
    request and no filesystem-path guessing.
    """
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
    """Construct the SDK server with Span's two handlers.

    The SDK import lives in this function: `shell/mcp.py` (adapter,
    specs, ingress/egress) never imports the SDK and stays testable
    without it. S9 §5.9: package version exposed through server
    initialization metadata.
    """
    from mcp.server import Server
    import mcp.types as _types

    try:
        from span import __version__ as _pkg_version
    except Exception:
        _pkg_version = "unknown"
    try:
        server: Server = Server("span", version=str(_pkg_version))
    except TypeError:
        # Older SDK without version kwarg: name only, version carried
        # in list-tools description suffix via handle_list_tools.
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
            "Span semantic-repository MCP server (stdio transport). "
            "Repositories are registered explicitly at startup; "
            "per-request work never initializes, rebuilds, or refreshes."
        ),
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory for SQLite semantic stores (created if absent).",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="REPO_PATH",
        help=(
            "Register a repository at startup "
            "(repeatable; e.g. --repo /path/to/repo). "
            "Provider-neutral locator; the shell resolves the "
            "structural provider internally."
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
    # repository identity before serving MCP and performs no provider
    # build, semantic-store open, or target work. Provisioning remains
    # explicit through `initialize_repository` and installer verification.
    for repository_locator in args.repo:
        repository_id = repository_id_from_config(repository_locator)
        adapter.register_repository_locator(
            repository_id,
            repository_locator,
        )
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
