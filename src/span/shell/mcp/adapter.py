"""MCP tool dispatch: one canonical operation per tool, transport only.

Maps the canonical public operations (§11.3) to MCP tools one-for-one.
Ingress parses once into the canonical service contracts through strict
canonical decode (I-02; unknown fields, unknown enums, and missing required
fields fail closed). Egress serializes the discriminated result through the
same canonical encoding. No semantic rule lives here.
"""

from __future__ import annotations

import json as _json
import pathlib as _pathlib
from collections.abc import Callable as _Callable
from typing import Protocol as _Protocol
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import cast as _cast

from span.core import model as m
from span.ports.interpretation import InterpretationUnavailable
from span.ports.structural import StaleContinuationError
from span import service as ops
from span.shell.mcp.models import (
    ServiceContext,
    ToolResult,
)
from span.shell.mcp.schemas import _REQUEST_CLASS
from span.shell.mcp.wire import (
    _decode_init,
    _error,
    canonical_result_payload,
    decode_request,
)

try:  # Shell-owned provider-error mapping (I S1 §5.1): graft failure maps
    # to the existing unavailable envelope. The generic port gains no new
    # result and the service catches no shell-specific exception.
    from span.shell.structural.graft import GraftUnavailableError
except Exception:  # pragma: no cover - import-time fallback
    GraftUnavailableError = None  # type: ignore[assignment,misc]

__all__ = ["McpAdapter"]


class _RoutedRequest(_Protocol):
    """Every non-init request carries the repository it addresses."""

    repository_id: str


@_dataclass
class McpAdapter:
    """Thin tool-to-service projection (plan §4.2–4.4).

    Holds wired per-repository service contexts plus a lightweight
    locator registry for repositories whose context has not been opened
    yet. Owns no semantic rules: every call parses into a canonical
    contract, invokes exactly one service operation, and serializes its
    result.

    Registration and provisioning are separate: registering a locator
    only advertises repository identity, while a repository-scoped call
    opens its context once through the injected `context_loader`.
    Initialization provisions a new context (structural source,
    evidence, store) and therefore arrives through the injected
    `provisioner`, supplied by the server runtime that owns the data
    directory. Without one, init reports unavailable — never a fake.
    """

    contexts: dict[str, ServiceContext] = _field(default_factory=dict)
    provisioner: (
        _Callable[
            [ops.SemanticInitializeRepositoryRequest],
            tuple[ServiceContext, ops.SemanticInitializeRepositoryResult],
        ]
        | None
    ) = None
    repository_locators: dict[str, str] = _field(default_factory=dict)
    context_loader: _Callable[[str], ServiceContext] | None = None

    def register(self, repository_id: str, context: ServiceContext) -> None:
        """Record one repository's wired context (explicit admin path)."""
        self.contexts[repository_id] = context

    def register_repository_locator(
        self, repository_id: str, repository_locator: str
    ) -> None:
        """Record repository identity for discovery only.

        Registration is transport metadata: it performs no structural
        build, no semantic-store open, no authority-seed resolution, and
        no target work. A full context registered through `register`
        always takes precedence over this lazy locator.
        """
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
        """Canonical discovery set: opened contexts plus locators."""
        return tuple(sorted(set(self.contexts) | set(self.repository_locators)))

    def _context(self, repository_id: str) -> ServiceContext:
        context = self.contexts.get(repository_id)
        if context is not None:
            return context
        locator = self.repository_locators.get(repository_id)
        if locator is not None:
            if self.context_loader is None:
                raise ValueError(
                    f"repository not opened and no context loader is "
                    f"configured: {repository_id!r}"
                )
            context = self.context_loader(locator)
            self.contexts[repository_id] = context
            return context
        registered = list(self.registered_repository_ids())
        raise ValueError(
            f"unknown repository: {repository_id!r}; " f"registered: {registered}"
        )

    def dispatch(self, tool_name: str, arguments: dict) -> ToolResult:
        """Invoke one canonical operation; transport errors stay typed."""
        if tool_name == "initialize_repository":
            return self._dispatch_init(arguments)
        if tool_name not in _REQUEST_CLASS:
            return _error("unknown_tool", f"unknown tool: {tool_name}")
        try:
            request = decode_request(tool_name, arguments)
        except ValueError as exc:
            return _error("ingress", str(exc))
        repository_id, ingress_error = _ingress_identity(
            tool_name, arguments, _cast(_RoutedRequest, request)
        )
        if ingress_error is not None:
            return ingress_error
        try:
            context = self._context(repository_id)
        except ValueError as exc:
            return _error("unknown_repository", str(exc))
        try:
            outcome = _call_operation(tool_name, request, context)
        except InterpretationUnavailable as exc:
            return _error("unavailable", str(exc))
        except StaleContinuationError as exc:
            return _error(
                "stale_continuation",
                f"{exc}; restart the listing from page one with page_token null",
            )
        except ops.InterpretationUnitRejected as exc:
            return _error(
                "validation",
                "; ".join(exc.diagnostics)
                + "; correct the result and resubmit using the same continuation.",
            )
        except (
            ops.AuthorityTargetError,
            ops.StatusTargetError,
            ops.RefreshScopeError,
            ValueError,
        ) as exc:
            return _error("rejected", str(exc))
        except Exception as exc:
            # Shell-owned GraftUnavailableError mapping (I S1 §5.1): an
            # Exception outside the typed/ValueError envelope path maps to
            # the existing unavailable envelope. No stored fallback.
            if GraftUnavailableError is not None and isinstance(
                exc, GraftUnavailableError
            ):
                return _error("unavailable", str(exc))
            raise
        if isinstance(outcome, ToolResult):
            return outcome
        return _encoded_result(outcome)

    def _dispatch_init(self, arguments: dict) -> ToolResult:
        try:
            request = _decode_init(arguments)
        except ValueError as exc:
            return _error("ingress", str(exc))
        if self.provisioner is None:
            return _error(
                "unavailable",
                "initialize_repository needs a provisioned " "server data directory",
            )
        try:
            context, result = self.provisioner(request)
        except ValueError as exc:
            return _error("rejected", str(exc))
        self.register(result.repository_id, context)
        payload = canonical_result_payload(result)
        return ToolResult(
            content=_json.dumps(payload, sort_keys=True),
            structured_content=payload,
            is_error=False,
        )


def _ingress_identity(
    tool_name: str,
    arguments: dict[str, object],
    request: _RoutedRequest,
) -> tuple[str, ToolResult | None]:
    """Reject crossed handle types and resolve the repository being addressed."""
    if tool_name == "submit_interpretation":
        repository_id = arguments.get("repository_id")
        continuation = arguments.get("continuation")
        if isinstance(continuation, str) and continuation.startswith(
            ("pg:", "pgv:", "pgn:")
        ):
            return "", _error(
                "ingress",
                "a page token was supplied where an interpretation "
                "continuation was expected; pass the continuation "
                "returned by the operation that suspended",
            )
    else:
        repository_id = request.repository_id
        page_token = arguments.get("page_token")
        if isinstance(page_token, str) and page_token.startswith(("cont-", "cont")):
            return "", _error(
                "ingress",
                "an interpretation continuation was supplied where a "
                "page token was expected; pass the page token returned "
                "by the operation being paged",
            )
    if not isinstance(repository_id, str) or not repository_id:
        return "", _error("ingress", "repository_id must be non-empty")
    return repository_id, None


def _call_operation(
    tool_name: str,
    request: object,
    context: ServiceContext,
) -> object:
    """Project one tool name onto exactly one canonical service operation."""
    if tool_name == "explain":
        return ops.explain(
            _cast(ops.SemanticExplainRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    if tool_name == "initialize_target":
        return ops.initialize_target(
            _cast(ops.SemanticInitializeTargetRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    if tool_name == "impact":
        return ops.impact(
            _cast(ops.SemanticImpactRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    if tool_name == "trace":
        return ops.trace(
            _cast(ops.SemanticTraceRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    if tool_name == "authority":
        return ops.authority(
            _cast(ops.SemanticAuthorityRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    if tool_name == "status":
        return ops.status(
            _cast(ops.SemanticStatusRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    if tool_name == "refresh":
        return ops.refresh(
            _cast(ops.SemanticRefreshRequest, request),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    if tool_name == "submit_interpretation":
        submission = _cast(ops.SemanticSubmitInterpretationRequest, request)
        return ops.submit_interpretation(
            submission.continuation,
            submission.result,
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
        )
    if tool_name == "locate":
        return ops.locate(
            request,  # type: ignore[arg-type]
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
        )
    if tool_name == "neighbors":
        return ops.neighbors(
            request,  # type: ignore[arg-type]
            structural=context.structural,
            store=context.store,
        )
    # Unreachable: dispatch guards against unknown tool names.
    return _error("unknown_tool", f"unknown tool: {tool_name}")


def _encoded_result(result: object) -> ToolResult:
    """Serialize one canonical result through the canonical encoder."""
    try:
        payload = canonical_result_payload(result)
    except (TypeError, ValueError) as exc:
        return _error("transport", f"cannot encode result: {exc}")
    return ToolResult(
        content=_json.dumps(payload, sort_keys=True),
        structured_content=payload,
        is_error=False,
    )
