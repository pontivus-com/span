"""MCP tool dispatch: one canonical request/result per tool, transport only.

The adapter owns no semantic rule. It routes a tool to exactly one service
operation, serializes the canonical result, and maps failures onto the typed
transport envelope. Unknown tool names reject without compatibility dispatch
and perform no work.
"""

from __future__ import annotations

import json as _json
import pathlib as _pathlib
from collections.abc import Callable as _Callable
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import cast as _cast

from span.core import model as m
from span.core.recording import RecordingConflict, RecordingValidationError
from span.core.rejection import Rejection
from span.core.schema import record_wire as _rw
from span.ports.structural import StaleContinuationError
from span.shell.mcp.models import ServiceContext, ToolResult
from span.shell.mcp.schemas import TOOL_REQUEST_TYPES
from span.shell.mcp.wire import (
    RoutingError,
    canonical_result_payload,
    decode_request,
    encode_error,
    repository_route,
    strip_route,
)
from span.shell.sqlite_store.lifecycle import (
    LifecycleStoreError,
    SchemaVersionError,
    UnknownRepository,
)

try:  # Shell-owned provider-error mapping; the port gains no new result.
    from span.shell.structural.graft import GraftUnavailableError
except Exception:  # pragma: no cover - import-time fallback
    GraftUnavailableError = None  # type: ignore[assignment,misc]

__all__ = ["McpAdapter"]

_RESULT_UNION_TOOLS = frozenset({"ask", "record", "reconsider"})


@_dataclass
class McpAdapter:
    """Thin tool-to-service projection over lifecycle contexts."""

    contexts: dict[str, ServiceContext] = _field(default_factory=dict)
    provisioner: (
        _Callable[
            [m.InitializeRepositoryRequest],
            tuple[ServiceContext, m.InitializeRepositoryResult],
        ]
        | None
    ) = None
    repository_locators: dict[str, str] = _field(default_factory=dict)
    context_loader: _Callable[[str], ServiceContext] | None = None

    def register(self, repository_id: str, context: ServiceContext) -> None:
        """Record one repository's wired context (explicit setup path)."""
        self.contexts[repository_id] = context

    def register_repository_locator(
        self, repository_id: str, repository_locator: str
    ) -> None:
        """Record repository identity for discovery only; opens nothing."""
        if not repository_id or not repository_locator:
            raise ValueError("repository identity and locator must be non-empty")
        canonical = str(_pathlib.Path(repository_locator).resolve())
        existing = self.repository_locators.get(repository_id)
        if existing is not None:
            existing_canonical = str(_pathlib.Path(existing).resolve())
            if existing_canonical != canonical:
                raise m.RepositoryIdentityConflict(
                    repository_id, existing_canonical, canonical
                )
            return
        self.repository_locators[repository_id] = repository_locator

    def registered_repository_ids(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.contexts) | set(self.repository_locators)))

    def _context(self, repository_id: str) -> ServiceContext:
        context = self.contexts.get(repository_id)
        if context is not None:
            return context
        locator = self.repository_locators.get(repository_id)
        if locator is not None:
            if self.context_loader is None:
                raise LifecycleStoreError(
                    f"repository not opened and no context loader is "
                    f"configured: {repository_id!r}"
                )
            context = self.context_loader(locator)
            self.contexts[repository_id] = context
            return context
        raise LifecycleStoreError(
            f"unknown repository: {repository_id!r}; "
            f"registered: {list(self.registered_repository_ids())}"
        )

    def dispatch(self, tool_name: str, arguments: dict[str, object]) -> ToolResult:
        """Invoke one tool; every failure stays a typed envelope."""
        if tool_name not in TOOL_REQUEST_TYPES:
            return encode_error("unknown_tool", f"unknown tool: {tool_name}")
        try:
            request = decode_request(tool_name, arguments)
            _, route = strip_route(tool_name, arguments)
            repository_id = repository_route(tool_name, request, route)
        except (RoutingError, ValueError) as exc:
            return encode_error("ingress", str(exc))
        try:
            context = self._context(repository_id)
        except LifecycleStoreError as exc:
            return encode_error(
                "unavailable",
                str(exc),
                "run the installer to bind this repository",
            )
        try:
            outcome = _call_operation(tool_name, request, context)
        except StaleContinuationError as exc:
            return encode_error(
                "stale_continuation",
                f"{exc}; restart the listing from page one with " "page_token null",
            )
        except RecordingConflict as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_rejected(request, exc))
            return encode_error(exc.cause_kind.value, str(exc))
        except RecordingValidationError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_rejected(request, exc))
            return encode_error(exc.cause_kind.value, str(exc))
        except SchemaVersionError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_unavailable(tool_name, exc))
            return encode_error(
                "unavailable",
                str(exc),
                "run `span-install --transition-store <repository-id> "
                "--transition-phase inspect` for the offline transition",
            )
        except LifecycleStoreError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_unavailable(tool_name, exc))
            return encode_error("rejected", str(exc))
        except ValueError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_rejected(request, exc))
            return encode_error("rejected", str(exc))
        except Exception as exc:  # noqa: BLE001 - typed provider boundary
            if GraftUnavailableError is not None and isinstance(
                exc, GraftUnavailableError
            ):
                return encode_error("unavailable", str(exc))
            raise
        return _encoded_result(outcome)


_TRANSITION_RECOVERY = (
    "run `span-install --transition-store <repository-id> "
    "--transition-phase inspect` for the offline transition"
)


def _request_identity(request: object) -> str:
    """The exact caller identity a rejection names."""
    if isinstance(request, m.ReconsiderRequest):
        challenge = request.challenge
        repository_id = request.repository_id or "unknown"
        if challenge is None:
            return repository_id
        return (
            f"{repository_id}/{challenge.request_id}/"
            f"{challenge.understanding_id}"
        )
    if isinstance(request, m.AskRequest):
        try:
            repository_id = repository_route("ask", request, None)
        except (RoutingError, ValueError):
            repository_id = "unknown"
        return f"{repository_id}/{request.request_id or 'read'}"
    if isinstance(request, _rw.RecordRequestWire):
        identity = request.identity
        base = f"{identity.repository_id}/{identity.request_id}"
        if request.understanding_id is not None:
            return f"{base}/{request.understanding_id}"
        return base
    return "unknown"


def _rejected(request: object, exc: Exception) -> m.Rejected:
    """Copy the typed rejection; never classify a message or extract a version."""
    rejection = exc if isinstance(exc, Rejection) else Rejection(str(exc))
    return m.Rejected(
        identity=_request_identity(request),
        required_action=rejection.required_action,
        cause_kind=rejection.cause_kind,
        cause=rejection.cause,
        current_version=rejection.current_version,
        current_boundary_version=rejection.current_boundary_version,
    )


def _unavailable(operation: str, exc: Exception) -> m.Unavailable:
    if isinstance(exc, SchemaVersionError):
        recovery = _TRANSITION_RECOVERY
    elif isinstance(exc, UnknownRepository):
        recovery = "run the installer to bind this repository"
    else:
        recovery = "read the named operational state, then retry"
    return m.Unavailable(
        operation=operation,
        failure=str(exc),
        recovery=recovery,
    )


def _call_operation(tool_name: str, request: object, context: ServiceContext) -> object:
    """Project one tool name onto exactly one canonical service operation."""
    if tool_name == "ask":
        return context.answer.ask(_cast(m.AskRequest, request))
    if tool_name == "record":
        return context.lifecycle.record(_cast(_rw.RecordRequestWire, request))
    if tool_name == "reconsider":
        return context.reconsider.reconsider(_cast(m.ReconsiderRequest, request))
    raise RoutingError(f"unknown tool: {tool_name}")


def _require_same_repository(
    context: ServiceContext, repository_id: str, what: str
) -> None:
    """Reject a routed reference that belongs to another repository."""
    if repository_id != context.repository_id:
        raise RecordingValidationError(
            f"{what} belongs to repository {repository_id!r}, not "
            f"{context.repository_id!r}"
        )


def _encoded_result(result: object) -> ToolResult:
    try:
        payload = canonical_result_payload(result)
    except (TypeError, ValueError) as exc:
        return encode_error("transport", f"cannot encode result: {exc}")
    return ToolResult(
        content=_json.dumps(payload, sort_keys=True),
        structured_content=payload,
        is_error=False,
    )


__all__ = ["McpAdapter"]
