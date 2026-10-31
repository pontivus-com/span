"""MCP tool dispatch: one canonical request/result per tool, transport only.

The adapter owns no semantic rule. It routes a tool to exactly one service
operation, serializes the canonical result, and maps failures onto the typed
transport envelope. Retired tool names reject with an exact replacement and
perform no work.
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
from span.core.schema import record_wire as _rw
from span.ports.structural import StaleContinuationError
from span.service.navigation import (
    SemanticStructuralLocateRequest,
    SemanticStructuralNeighborsRequest,
)
from span.service import locate as locate_operation
from span.service import neighbors as neighbors_operation
from span.shell.mcp.models import ServiceContext, ToolResult
from span.shell.mcp.schemas import REMOVED_TOOLS, TOOL_REQUEST_TYPES
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
)

try:  # Shell-owned provider-error mapping; the port gains no new result.
    from span.shell.structural.graft import GraftUnavailableError
except Exception:  # pragma: no cover - import-time fallback
    GraftUnavailableError = None  # type: ignore[assignment,misc]

__all__ = ["McpAdapter"]


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
        if tool_name in REMOVED_TOOLS:
            return encode_error(
                "removed",
                f"{tool_name} was removed in 0.9.0",
                REMOVED_TOOLS[tool_name],
            )
        if tool_name == "initialize_repository":
            return self._dispatch_init(arguments)
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
                "call initialize_repository in a setup session",
            )
        try:
            outcome = _call_operation(tool_name, request, context)
        except StaleContinuationError as exc:
            return encode_error(
                "stale_continuation",
                f"{exc}; restart the listing from page one with " "page_token null",
            )
        except RecordingConflict as exc:
            return encode_error("conflict", str(exc))
        except RecordingValidationError as exc:
            return encode_error(_validation_kind(str(exc)), str(exc))
        except SchemaVersionError as exc:
            return encode_error(
                "unavailable",
                str(exc),
                "run `span-install --transition-store <repository-id> "
                "--transition-phase inspect` for the offline transition",
            )
        except LifecycleStoreError as exc:
            return encode_error("rejected", str(exc))
        except ValueError as exc:
            return encode_error("rejected", str(exc))
        except Exception as exc:  # noqa: BLE001 - typed provider boundary
            if GraftUnavailableError is not None and isinstance(
                exc, GraftUnavailableError
            ):
                return encode_error("unavailable", str(exc))
            raise
        return _encoded_result(outcome)

    def _dispatch_init(self, arguments: dict[str, object]) -> ToolResult:
        try:
            request = decode_request("initialize_repository", arguments)
        except ValueError as exc:
            return encode_error(
                "ingress", f"invalid initialize_repository arguments: {exc}"
            )
        if self.provisioner is None:
            return encode_error(
                "unavailable",
                "initialize_repository needs a provisioned server data " "directory",
            )
        try:
            context, result = self.provisioner(
                _cast(m.InitializeRepositoryRequest, request)
            )
        except SchemaVersionError as exc:
            return encode_error(
                "unavailable",
                str(exc),
                "run `span-install --transition-store <repository-id> "
                "--transition-phase inspect`",
            )
        except ValueError as exc:
            return encode_error("rejected", str(exc))
        self.register(result.repository_id, context)
        return _encoded_result(result)


def _validation_kind(message: str) -> str:
    lowered = message.lower()
    if "not current" in lowered or "drift" in lowered:
        return "source_drift"
    return "validation"


def _call_operation(tool_name: str, request: object, context: ServiceContext) -> object:
    """Project one tool name onto exactly one canonical service operation."""
    if tool_name == "start_context":
        return context.lifecycle.start_context(_cast(m.StartContextRequest, request))
    if tool_name == "understand_question":
        return context.understand.question(_cast(m.UnderstandQuestionRequest, request))
    if tool_name == "understand_retrieve":
        return context.understand.retrieve(_cast(m.RetrieveRequest, request))
    if tool_name == "reassess":
        reassess = _cast(m.ReassessRequest, request)
        _require_same_repository(context, reassess.repository_id, "understanding")
        return context.support.evaluate_version(
            reassess.understanding_id, reassess.version
        )
    if tool_name == "verification_support":
        verification = _cast(m.VerificationSupportRequest, request)
        _require_same_repository(
            context, verification.repository_id, "verification run"
        )
        return context.support.evaluate_verification(verification.run_id)
    if tool_name == "evidence_start":
        return context.evidence_service.start(_cast(m.EvidenceStartRequest, request))
    if tool_name == "evidence_extend":
        return context.evidence_service.extend(_cast(m.EvidenceExtendRequest, request))
    if tool_name == "record_create":
        return context.lifecycle.qualify_understanding(
            context.lifecycle.create(_cast(_rw.RecordCreateWire, request))
        )
    if tool_name == "record_add":
        return context.lifecycle.qualify_understanding(
            context.lifecycle.add(_cast(_rw.RecordAddWire, request))
        )
    if tool_name == "record_confirm":
        return context.lifecycle.qualify_understanding(
            context.lifecycle.confirm(_cast(_rw.RecordConfirmWire, request))
        )
    if tool_name == "record_correct":
        return context.lifecycle.qualify_understanding(
            context.lifecycle.correct(_cast(_rw.RecordCorrectWire, request))
        )
    if tool_name == "record_replace":
        return context.lifecycle.qualify_understanding(
            context.lifecycle.replace(_cast(_rw.RecordReplaceWire, request))
        )
    if tool_name == "record_withdraw":
        return context.lifecycle.qualify_understanding(
            context.lifecycle.withdraw(_cast(_rw.RecordWithdrawWire, request))
        )
    if tool_name == "record_challenge":
        return context.lifecycle.qualify_challenge(
            context.lifecycle.challenge(_cast(_rw.RecordChallengeWire, request))
        )
    if tool_name == "record_update":
        return context.lifecycle.qualify_understanding(
            context.lifecycle.update(_cast(_rw.RecordUpdateWire, request))
        )
    if tool_name == "record_verification":
        return context.lifecycle.qualify_verification(
            context.lifecycle.verification(_cast(_rw.RecordVerificationWire, request))
        )
    if tool_name == "locate":
        return locate_operation(
            _cast(SemanticStructuralLocateRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
        )
    if tool_name == "neighbors":
        return neighbors_operation(
            _cast(SemanticStructuralNeighborsRequest, request),
            structural=context.structural,
            store=context.store,
        )
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
