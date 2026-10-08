"""MCP transport adapter (plan Phase 4.2–4.4). Transport only.

Maps the eight canonical public operations (§11.3) to MCP tools
one-for-one. Ingress parses once into the canonical service contracts
through strict canonical decode (I-02; unknown fields, unknown enums,
and missing required fields fail closed). Egress serializes the
discriminated result — `SemanticAnswer`, `PendingInterpretation`,
`HookStatusNotice`, or `SemanticInitializeRepositoryResult` — through
the same canonical encoding. No semantic rule lives here: tool
descriptions are capability-oriented and concise; lifecycle and
orchestration guidance belongs in Agent Skills.

Result envelope differences (answer vs pending vs notice) are
preserved exactly as the service returns them, including the
`SemanticAnswer | PendingInterpretation` submit union (§11.12).
Exchange failures surface as typed errors, never as invented
semantics. A JSON ingress failure never consumes the continuation:
the agent resubmits the corrected result under the same continuation.
"""

from __future__ import annotations

import json as _json
from collections.abc import Callable as _Callable
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
)
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.agent_exchange.continuations import ContinuationStore
from span import service_operations as ops

__all__ = [
    "TOOL_NAMES",
    "TOOL_SCHEMAS",
    "TOOL_DESCRIPTIONS",
    "ToolResult",
    "ServiceContext",
    "McpAdapter",
    "decode_request",
    "encode_result",
]


@_dataclass(frozen=True)
class ServiceContext:
    """Wired service dependencies for one repository (shell lifecycle)."""

    structural: StructuralSource
    evidence: EvidenceSource
    store: SemanticStore
    continuations: ContinuationStore
    authority_seeds: tuple[m.EvidenceRef, ...] = ()


@_dataclass(frozen=True)
class ToolResult:
    """One tool invocation outcome (transport envelope, not semantics)."""

    content: str
    is_error: bool = False


def _object(description: str, required: tuple[str, ...] = ()) -> dict:
    return {
        "type": "object",
        "description": description,
        "properties": {},
        "required": list(required),
    }


def _canonical(description: str) -> dict:
    return {
        "type": "object",
        "description": (
            description + " Canonical JSON: the exact canonical "
            "encoding of the named carrier, including its $type tag."
        ),
    }


TOOL_DESCRIPTIONS: dict[str, str] = {
    "span_initialize_repository": (
        "Prepare a repository for semantic queries in a dedicated "
        "setup session. No semantic interpretation happens here."
    ),
    "span_explain": (
        "Explain what a subject is, what it does, and what governs it, "
        "with evidence, authority, and freshness."
    ),
    "span_impact": (
        "Pre-change semantic brief for a proposed material change: "
        "impacts, conditions, authority, verification, blockers."
    ),
    "span_trace": (
        "Producers, carriers, consumers, boundaries, and lifecycle path "
        "for a target, upstream/downstream/both."
    ),
    "span_authority": (
        "Governing sources with status, applicability, precedence, and "
        "conflicts shown side-by-side."
    ),
    "span_status": (
        "Per-claim freshness, changed evidence, verification currency, "
        "and refresh scope. HOOK_FAST returns a compact notice only."
    ),
    "span_refresh": (
        "Explicitly reinterpret stale scope. Never automatic."
    ),
    "span_submit_interpretation": (
        "Submit a typed interpretation result for a pending "
        "continuation. Returns the suspended operation's answer, or "
        "the next pending unit while frontiers remain."
    ),
}

TOOL_SCHEMAS: dict[str, dict] = {
    "span_initialize_repository": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_initialize_repository"],
        "properties": {
            "repository_locator": {"type": "string"},
            "structural_provider_config": {"type": "string"},
            "authority_seeds": {
                "type": "array",
                "description": "Canonical EvidenceRef items.",
            },
        },
        "required": ["repository_locator", "structural_provider_config"],
    },
    "span_explain": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_explain"],
        "properties": {
            "repository_id": {"type": "string"},
            "target": _canonical("SubjectSelector."),
            "bounds": _canonical("QueryBounds. Omit for defaults."),
            "page_token": {"type": ["string", "null"]},
        },
        "required": ["repository_id", "target"],
    },
    "span_impact": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_impact"],
        "properties": {
            "repository_id": {"type": "string"},
            "target": _canonical("SubjectSelector."),
            "change_kind": {
                "type": "string",
                "enum": [k.value for k in m.ChangeKind],
            },
            "change_description": {"type": ["string", "null"]},
            "affected_assertions": {
                "type": "array",
                "description": (
                    "Canonical ClaimRef/RelationshipRef items naming "
                    "the established assertions the proposal alters."
                ),
            },
            "bounds": _canonical("QueryBounds. Omit for defaults."),
            "page_token": {"type": ["string", "null"]},
        },
        "required": [
            "repository_id", "target", "change_kind",
            "change_description",
        ],
    },
    "span_trace": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_trace"],
        "properties": {
            "repository_id": {"type": "string"},
            "target": _canonical("SubjectSelector."),
            "direction": {
                "type": "string",
                "enum": ["UPSTREAM", "DOWNSTREAM", "BOTH"],
            },
            "relationship_filter": {
                "type": ["array", "null"],
                "description": "RelationshipKind values or null.",
            },
            "boundary_only": {"type": "boolean"},
            "bounds": _canonical("QueryBounds. Omit for defaults."),
            "page_token": {"type": ["string", "null"]},
        },
        "required": [
            "repository_id", "target", "direction", "relationship_filter",
            "boundary_only",
        ],
    },
    "span_authority": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_authority"],
        "properties": {
            "repository_id": {"type": "string"},
            "target": _canonical("SubjectSelector or ClaimRef."),
            "bounds": _canonical("QueryBounds. Omit for defaults."),
            "page_token": {"type": ["string", "null"]},
        },
        "required": ["repository_id", "target"],
    },
    "span_status": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_status"],
        "properties": {
            "repository_id": {"type": "string"},
            "target": _canonical(
                "SubjectSelector, ClaimRef, RelationshipRef, "
                "EvidenceScope, or null. AnswerRef is rejected: "
                "answers are never persisted."
            ),
            "mode": {"type": "string", "enum": ["NORMAL", "HOOK_FAST"]},
            "bounds": _canonical("QueryBounds. Omit for defaults."),
            "page_token": {"type": ["string", "null"]},
        },
        "required": ["repository_id", "target"],
    },
    "span_refresh": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_refresh"],
        "properties": {
            "repository_id": {"type": "string"},
            "target": _canonical(
                "SubjectSelector, EvidenceScope, or null "
                "(null is rejected: repo-wide refresh needs enumeration)."
            ),
            "stale_only": {"type": "boolean"},
            "bounds": _canonical("QueryBounds. Omit for defaults."),
            "page_token": {"type": ["string", "null"]},
        },
        "required": ["repository_id", "target"],
    },
    "span_submit_interpretation": {
        "type": "object",
        "description": TOOL_DESCRIPTIONS["span_submit_interpretation"],
        "properties": {
            "continuation": {"type": "string"},
            "result": _canonical("SemanticInterpretationResult."),
            "repository_id": {"type": "string"},
        },
        "required": ["continuation", "result", "repository_id"],
    },
}

TOOL_NAMES: tuple[str, ...] = (
    "span_initialize_repository",
    "span_explain",
    "span_impact",
    "span_trace",
    "span_authority",
    "span_status",
    "span_refresh",
    "span_submit_interpretation",
)

_REQUEST_CLASS: dict[str, type] = {
    "span_explain": ops.SemanticExplainRequest,
    "span_impact": ops.SemanticImpactRequest,
    "span_trace": ops.SemanticTraceRequest,
    "span_authority": ops.SemanticAuthorityRequest,
    "span_status": ops.SemanticStatusRequest,
    "span_refresh": ops.SemanticRefreshRequest,
    "span_submit_interpretation": ops.SemanticSubmitInterpretationRequest,
}


def decode_request(tool_name: str, arguments: dict) -> object:
    """Strict ingress: one boundary, one contract, one parse (I-02).

    The arguments are the canonical request encoding without its
    `$type` tag; `bounds` may be omitted for service defaults (§5.1).
    Unknown tools, unknown fields, unknown enums, and missing required
    fields fail closed.
    """
    if tool_name == "span_initialize_repository":
        return _decode_init(arguments)
    cls = _REQUEST_CLASS.get(tool_name)
    if cls is None:
        raise ValueError(f"unknown tool: {tool_name}")
    if not isinstance(arguments, dict):
        raise ValueError(f"arguments for {tool_name} must be an object")
    payload = dict(arguments)
    if tool_name == "span_submit_interpretation":
        # Transport-level routing key, not part of the canonical
        # submit contract: consumed here, never parsed as semantics.
        payload.pop("repository_id", None)
    else:
        # Plan §5.1: omitted bounds use service defaults. (Submit
        # carries no bounds by contract.)
        if "bounds" not in payload or payload["bounds"] is None:
            payload["bounds"] = m.to_canonical(
                DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds
            )
    payload["$type"] = cls.__name__
    try:
        return m.from_canonical(cls, payload)
    except m.CanonicalDecodeError as exc:
        raise ValueError(f"invalid {tool_name} arguments: {exc}") from None


def _decode_init(arguments: dict) -> ops.SemanticInitializeRepositoryRequest:
    if not isinstance(arguments, dict):
        raise ValueError("span_initialize_repository needs an object")
    try:
        return m.from_canonical(
            ops.SemanticInitializeRepositoryRequest,
            {
                "$type": "SemanticInitializeRepositoryRequest",
                **arguments,
            },
        )
    except m.CanonicalDecodeError as exc:
        raise ValueError(
            f"invalid span_initialize_repository arguments: {exc}"
        ) from None


def encode_result(result: object) -> str:
    """Deterministic canonical JSON for the discriminated result."""
    return _json.dumps(m.to_canonical(result), sort_keys=True)


def _error(kind: str, message: str) -> ToolResult:
    return ToolResult(
        content=_json.dumps(
            {"error": kind, "message": message}, sort_keys=True
        ),
        is_error=True,
    )


@_dataclass
class McpAdapter:
    """Thin tool-to-service projection (plan §4.2–4.4).

    Holds wired per-repository service contexts. Owns no semantic
    rules: every call parses into a canonical contract, invokes exactly
    one service operation, and serializes its result.

    Initialization provisions a new context (structural source,
    evidence, store) and therefore arrives through the injected
    `provisioner`, supplied by the server runtime that owns the data
    directory. Without one, init reports unavailable — never a fake.
    """

    contexts: dict[str, ServiceContext] = _field(default_factory=dict)
    provisioner: _Callable[
        [ops.SemanticInitializeRepositoryRequest],
        tuple[
            ServiceContext, ops.SemanticInitializeRepositoryResult
        ],
    ] | None = None

    def register(
        self, repository_id: str, context: ServiceContext
    ) -> None:
        """Record one repository's wired context (explicit admin path)."""
        self.contexts[repository_id] = context

    def _context(self, repository_id: str) -> ServiceContext:
        try:
            return self.contexts[repository_id]
        except KeyError:
            raise ValueError(
                f"unknown repository: {repository_id}"
            ) from None

    def dispatch(
        self, tool_name: str, arguments: dict
    ) -> ToolResult:
        """Invoke one canonical operation; transport errors stay typed."""
        if tool_name == "span_initialize_repository":
            return self._dispatch_init(arguments)
        if tool_name not in _REQUEST_CLASS:
            return _error("unknown_tool", f"unknown tool: {tool_name}")
        try:
            request = decode_request(tool_name, arguments)
        except ValueError as exc:
            return _error("ingress", str(exc))
        if tool_name == "span_submit_interpretation":
            repository_id = arguments.get("repository_id")
        else:
            repository_id = request.repository_id  # type: ignore[union-attr]
        if not isinstance(repository_id, str) or not repository_id:
            return _error("ingress", "repository_id must be non-empty")
        try:
            context = self._context(repository_id)
        except ValueError as exc:
            return _error("unknown_repository", str(exc))
        try:
            if tool_name == "span_explain":
                result = ops.explain(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "span_impact":
                result = ops.impact(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "span_trace":
                result = ops.trace(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "span_authority":
                result = ops.authority(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "span_status":
                result = ops.status(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "span_refresh":
                result = ops.refresh(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "span_submit_interpretation":
                result = ops.submit_interpretation(
                    request.continuation,  # type: ignore[union-attr]
                    request.result,  # type: ignore[union-attr]
                    structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                )
            else:  # Unreachable: guarded above.
                return _error("unknown_tool", f"unknown tool: {tool_name}")
        except InterpretationUnavailable as exc:
            return _error("unavailable", str(exc))
        except InterpretationIngressFailure as exc:
            return _error("ingress", str(exc))
        except ops.InterpretationUnitRejected as exc:
            return _error("validation", "; ".join(exc.diagnostics))
        except (ops.AuthorityTargetError, ops.StatusTargetError,
                ops.RefreshScopeError, ValueError) as exc:
            return _error("rejected", str(exc))
        try:
            return ToolResult(content=encode_result(result))
        except (TypeError, ValueError) as exc:
            return _error("transport", f"cannot encode result: {exc}")

    def _dispatch_init(self, arguments: dict) -> ToolResult:
        try:
            request = _decode_init(arguments)
        except ValueError as exc:
            return _error("ingress", str(exc))
        if self.provisioner is None:
            return _error(
                "unavailable",
                "span_initialize_repository needs a provisioned "
                "server data directory",
            )
        try:
            context, result = self.provisioner(request)
        except ValueError as exc:
            return _error("rejected", str(exc))
        self.register(result.repository_id, context)
        return ToolResult(content=encode_result(result))
