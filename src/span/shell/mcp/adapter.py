"""MCP tool dispatch: one canonical request/result per tool, transport only.

The adapter owns no semantic rule. It routes a tool to exactly one service
operation, serializes the canonical result, and maps failures onto the typed
transport envelope. Unknown tool names reject without compatibility dispatch
and perform no work.
"""

from __future__ import annotations

import json as _json
import logging as _logging
import pathlib as _pathlib
from collections.abc import Callable as _Callable
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import cast as _cast

from span.core import model as m
from span.core.recording import RecordingConflict, RecordingValidationError
from span.core.rejection import (
    Rejection,
    RejectionCauseKind,
    StructuralValidationError,
)
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
    LifecycleStoreInvariantError,
    SchemaVersionError,
    UnknownRepository,
)
from span.shell.sqlite_store.functional_pyramid import (
    FunctionalPyramidInstallationSchemaError,
    FunctionalPyramidInstallationStoreError,
)
from span.service.functional_pyramid import FunctionalPyramidService

try:  # Shell-owned provider-error mapping; the port gains no new result.
    from span.shell.structural.graft import GraftUnavailableError
except Exception:  # pragma: no cover - import-time fallback
    GraftUnavailableError = None  # type: ignore[assignment,misc]

__all__ = ["McpAdapter"]

_RESULT_UNION_TOOLS = frozenset({"ask", "record", "reconsider"})
_LOGGER = _logging.getLogger(__name__)


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
    functional_pyramid: FunctionalPyramidService | None = None

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

    def repository_context(self, repository_id: str) -> ServiceContext:
        """Open/reuse one registered repository context for installation services."""
        return self._context(repository_id)

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
        except StructuralValidationError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_structural_rejected(tool_name, arguments, exc))
            return encode_error(
                "ingress",
                "the request does not match the declared tool schema",
                "correct the named request fields, then retry",
            )
        except (RoutingError, ValueError) as exc:
            return encode_error("ingress", str(exc))
        installation_scoped = _is_functional_pyramid_request(tool_name, request)
        repository_id: str | None = None
        if not installation_scoped:
            try:
                repository_id = repository_route(tool_name, request, route)
            except (RoutingError, ValueError) as exc:
                if (
                    isinstance(request, m.AskRequest)
                    and request.continuation is not None
                ):
                    continuation_rejection = (
                        RecordingValidationError.continuation_invalid(
                            "the continuation cannot be routed"
                        )
                    )
                    return _encoded_result(_rejected(request, continuation_rejection))
                return encode_error("ingress", str(exc))
        try:
            if installation_scoped:
                outcome = _call_functional_pyramid(
                    tool_name,
                    request,
                    self.functional_pyramid,
                )
            else:
                assert repository_id is not None
                context = self._context(repository_id)
                outcome = _call_operation(tool_name, request, context)
        except StaleContinuationError:
            return encode_error(
                "stale_continuation",
                "the continuation is stale",
                "restart the listing from its first page",
            )
        except RecordingConflict as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_rejected(request, exc))
            return encode_error(
                exc.cause_kind.value,
                _public_rejection_cause(exc.cause_kind),
                exc.required_action,
            )
        except RecordingValidationError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_rejected(request, exc))
            return encode_error(
                exc.cause_kind.value,
                _public_rejection_cause(exc.cause_kind),
                exc.required_action,
            )
        except (
            SchemaVersionError,
            FunctionalPyramidInstallationSchemaError,
            FunctionalPyramidInstallationStoreError,
        ) as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_unavailable(tool_name, exc))
            failure, recovery = _operational_failure(exc)
            return encode_error("unavailable", failure, recovery)
        except LifecycleStoreInvariantError:
            _LOGGER.exception("unexpected lifecycle store invariant failure")
            return encode_error(
                "internal",
                "Span could not complete the operation",
                "report the operation failure without internal diagnostics",
            )
        except LifecycleStoreError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_unavailable(tool_name, exc))
            failure, recovery = _operational_failure(exc)
            return encode_error("unavailable", failure, recovery)
        except ValueError as exc:
            if tool_name in _RESULT_UNION_TOOLS:
                return _encoded_result(_rejected(request, exc))
            rejection = (
                exc if isinstance(exc, Rejection) else Rejection("invalid request")
            )
            return encode_error(
                rejection.cause_kind.value,
                _public_rejection_cause(rejection.cause_kind),
                rejection.required_action,
            )
        except Exception as exc:  # noqa: BLE001 - typed provider boundary
            if GraftUnavailableError is not None and isinstance(
                exc, GraftUnavailableError
            ):
                return encode_error(
                    "unavailable",
                    "the structural provider is unavailable",
                    "continue without this structural operation",
                )
            _LOGGER.exception("unexpected lifecycle operation failure")
            return encode_error(
                "internal",
                "Span could not complete the operation",
                "report the operation failure without internal diagnostics",
            )
        return _encoded_result(outcome)


def _structural_rejected(
    tool_name: str,
    arguments: dict[str, object],
    exc: StructuralValidationError,
) -> m.Rejected:
    """Project typed ingress faults through the existing public result shape."""
    repository_id = arguments.get("repository_id")
    request_id = arguments.get("request_id")
    identity_parts = [tool_name]
    if isinstance(repository_id, str) and repository_id:
        identity_parts.append(repository_id)
    if isinstance(request_id, str) and request_id:
        identity_parts.append(request_id)
    coordinates = tuple(dict.fromkeys(item.coordinate for item in exc.faults))
    cause = "; ".join(f"{item.coordinate}: {item.message}" for item in exc.faults)
    required_action = (
        "correct " + ", ".join(coordinates) + ", then retry"
        if coordinates
        else "correct the named field, then retry"
    )
    return m.Rejected(
        identity="/".join(identity_parts),
        required_action=required_action,
        cause_kind=RejectionCauseKind.VALIDATION,
        cause=cause,
    )


def _request_identity(request: object) -> str:
    """The exact caller identity a rejection names."""
    if isinstance(request, m.ReconsiderRequest):
        challenge = request.challenge
        repository_id = request.repository_id or "unknown"
        if challenge is None:
            return repository_id
        return f"{repository_id}/{challenge.request_id}/{challenge.understanding_id}"
    if isinstance(request, m.AskRequest):
        try:
            repository_id = repository_route("ask", request, None)
        except (RoutingError, ValueError):
            repository_id = "unknown"
        return f"{repository_id}/{request.request_id or 'read'}"
    if isinstance(request, _rw.RecordRequestWire):
        if request.kind is m.RecordKind.FUNCTIONAL_PYRAMID:
            return f"functional_pyramid/{request.request_id}"
        identity = request.identity
        base = f"{identity.repository_id}/{identity.request_id}"
        if request.understanding_id is not None:
            return f"{base}/{request.understanding_id}"
        return base
    return "unknown"


def _public_rejection_cause(kind: RejectionCauseKind) -> str:
    """Stable contract vocabulary for caller-correctable failures."""
    if kind is RejectionCauseKind.SOURCE_DRIFT:
        return "recorded support is not current"
    if kind is RejectionCauseKind.VERSION_CONFLICT:
        return "the requested understanding version is not current"
    if kind is RejectionCauseKind.SURFACE_CONFLICT:
        return "the requested surface boundary conflicts with current state"
    if kind is RejectionCauseKind.SURFACE_REQUIRED:
        return "the request does not identify one semantic surface"
    if kind is RejectionCauseKind.SURFACE_AMBIGUOUS:
        return "the semantic scope identifies multiple candidate surfaces"
    if kind is RejectionCauseKind.SURFACE_MISMATCH:
        return "the selected surface does not own the carried semantic scope"
    if kind is RejectionCauseKind.CONTEXT_TARGET_CONFLICT:
        return "the explicit target conflicts with the bound investigation context"
    if kind is RejectionCauseKind.CONTEXT_BINDING_CONFLICT:
        return "the request identity is bound to different context content"
    if kind is RejectionCauseKind.CONTEXT_SCOPE_CONFLICT:
        return "the requested evidence lies outside the bound investigation context"
    if kind is RejectionCauseKind.CONTEXT_REQUIRED:
        return "the required investigation context is unavailable"
    if kind is RejectionCauseKind.CONTINUATION_INVALID:
        return "the continuation cannot be used"
    if kind is RejectionCauseKind.OBSERVATION_NOT_ADMITTED:
        return "the referenced observation is not admitted to the investigation context"
    if kind is RejectionCauseKind.REPLAY_CONFLICT:
        return "the request identity is already bound to different content"
    if kind is RejectionCauseKind.ALREADY_EXISTS:
        return "the understanding already exists"
    return "the request failed lifecycle validation"


def _rejected(request: object, exc: Exception) -> m.Rejected:
    """Project one typed rejection without serializing internal diagnostics."""
    rejection = exc if isinstance(exc, Rejection) else Rejection("invalid request")
    return m.Rejected(
        identity=rejection.public_identity or _request_identity(request),
        required_action=rejection.required_action,
        cause_kind=rejection.cause_kind,
        cause=rejection.public_cause or _public_rejection_cause(rejection.cause_kind),
        current_version=rejection.current_version,
        current_boundary_version=rejection.current_boundary_version,
    )


def _operational_failure(exc: Exception) -> tuple[str, str]:
    """Map typed operational owners to stable public failure/recovery text."""
    if isinstance(
        exc,
        (
            FunctionalPyramidInstallationSchemaError,
            FunctionalPyramidInstallationStoreError,
        ),
    ):
        return (
            "Functional Pyramid installation state is unavailable",
            "run the installer/transition for this Span runtime before retrying",
        )
    if isinstance(exc, SchemaVersionError):
        return (
            "the repository store is incompatible with this Span runtime",
            "use a Span runtime compatible with this repository before continuing",
        )
    if isinstance(exc, UnknownRepository):
        return (
            "the requested repository is not available to Span",
            "open or register the repository with Span before continuing",
        )
    return (
        "the repository lifecycle state is unavailable",
        "continue without retained lifecycle state until repository availability is restored",
    )


def _unavailable(operation: str, exc: Exception) -> m.Unavailable:
    failure, recovery = _operational_failure(exc)
    return m.Unavailable(
        operation=operation,
        failure=failure,
        recovery=recovery,
    )


def _is_functional_pyramid_request(tool_name: str, request: object) -> bool:
    """Whether this canonical request belongs to the installation namespace."""
    if tool_name == "ask" and isinstance(request, m.AskRequest):
        return isinstance(
            request.selector,
            (
                m.FunctionalPyramidSelector,
                m.FunctionalPyramidDirectorySelector,
                m.FunctionalPyramidCandidateSelector,
                m.FunctionalPyramidReceiptSelector,
            ),
        )
    return (
        tool_name == "record"
        and isinstance(request, _rw.RecordRequestWire)
        and request.kind is m.RecordKind.FUNCTIONAL_PYRAMID
    )


def _call_functional_pyramid(
    tool_name: str,
    request: object,
    service: FunctionalPyramidService | None,
) -> object:
    """Project installation-scoped branches without inventing repository ownership."""
    if service is None:
        raise FunctionalPyramidInstallationSchemaError(
            "Functional Pyramid installation store is not initialized"
        )

    if tool_name == "ask" and isinstance(request, m.AskRequest):
        selector = request.selector
        if isinstance(selector, m.FunctionalPyramidSelector):
            return service.status(selector)
        if isinstance(selector, m.FunctionalPyramidCandidateSelector):
            return service.candidate(selector)
        if isinstance(selector, m.FunctionalPyramidReceiptSelector):
            receipt = service.receipt(selector)
            if receipt is None:
                raise RecordingValidationError(
                    "no Functional Pyramid receipt for request",
                    public_identity=selector.request_id.value,
                    public_cause="the exact Functional Pyramid receipt does not exist",
                )
            return receipt
        raise RoutingError("ask request is not Functional Pyramid installation-scoped")

    if tool_name == "record" and isinstance(request, _rw.RecordRequestWire):
        action = request.action
        if not isinstance(action, m.FunctionalPyramidAction):
            raise ValueError("Functional Pyramid record requires its declared action")
        return service.record(
            request_id=m.RequestId(request.request_id),
            action=action,
            members=request.members,
            pyramid_id=(
                None
                if request.pyramid_id is None
                else m.FunctionalPyramidId(request.pyramid_id)
            ),
            expected_version=(
                None
                if request.expected_version is None
                else m.FunctionalPyramidVersion(request.expected_version)
            ),
            repository_id=request.repository_id,
        )

    raise RoutingError(f"unknown installation-scoped tool: {tool_name}")


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
    except (TypeError, ValueError):
        _LOGGER.exception("failed to encode lifecycle operation result")
        return encode_error(
            "transport",
            "Span could not encode the operation result",
            "report the operation failure without internal diagnostics",
        )
    return ToolResult(
        content=_json.dumps(payload, sort_keys=True),
        structured_content=payload,
        is_error=False,
    )


__all__ = ["McpAdapter"]
