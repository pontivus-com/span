"""MCP wire boundary: strict ingress decode and canonical egress encode."""

from __future__ import annotations

import json as _json
from typing import cast as _cast

from span.core import model as m
from span.core import schema as _schema
from span import service as ops
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.mcp.models import ToolResult
from span.shell.mcp.schemas import _REQUEST_CLASS

__all__ = [
    "decode_request",
    "encode_result",
]


def decode_request(tool_name: str, arguments: dict) -> object:
    """Strict ingress: one boundary, one contract, one parse (I-02).

    The arguments are the canonical request encoding without its
    `$type` tag; `bounds` may be omitted for service defaults (§5.1).
    Unknown tools, unknown fields, unknown enums, and missing required
    fields fail closed.
    """
    if tool_name == "initialize_repository":
        return _decode_init(arguments)
    cls = _REQUEST_CLASS.get(tool_name)
    if cls is None:
        raise ValueError(f"unknown tool: {tool_name}")
    if not isinstance(arguments, dict):
        raise ValueError(f"arguments for {tool_name} must be an object")
    payload = dict(arguments)
    if tool_name == "submit_interpretation":
        # Transport-level routing key, not part of the canonical
        # submit contract: consumed here, never parsed as semantics.
        payload.pop("repository_id", None)
    if tool_name == "neighbors" and payload.get("edge_kinds") is None:
        # Schema advertises null/empty for all; the carrier default
        # is (). Normalize here so the advertised contract decodes.
        payload["edge_kinds"] = []
    try:
        return _schema.from_wire(cls, payload)
    except (m.CanonicalDecodeError, ValueError) as exc:
        raise ValueError(f"invalid {tool_name} arguments: {exc}") from None


def _decode_init(arguments: dict) -> ops.SemanticInitializeRepositoryRequest:
    if not isinstance(arguments, dict):
        raise ValueError("initialize_repository needs an object")
    try:
        return _cast(
            ops.SemanticInitializeRepositoryRequest,
            _schema.from_wire(ops.SemanticInitializeRepositoryRequest, arguments),
        )
    except (m.CanonicalDecodeError, ValueError) as exc:
        raise ValueError(f"invalid initialize_repository arguments: {exc}") from None


def canonical_result_payload(result: object) -> dict:
    """Build the one canonical wire object used by both MCP result channels."""
    compact = _schema.to_wire_root(type(result), m.to_canonical(result))
    if isinstance(compact, dict) and compact.get("$type") == ("PendingInterpretation"):
        compact = _omit_static_profile(compact)
    return _cast(dict, compact)


def encode_result(result: object) -> str:
    """Deterministic compact JSON for the discriminated result (S6.4/S7).

    Pending units carry unit-specific content plus the immutable
    interpretation profile (J-9); the static SA handbook, full default
    vocabularies, default bounds, and base task-brief rules are omitted
    when they equal the profile defaults.
    """
    return _json.dumps(canonical_result_payload(result), sort_keys=True)


def _omit_static_profile(compact: dict) -> dict:
    """Drop static contract material that equals the profile defaults."""
    request = compact.get("request")
    if not isinstance(request, dict):
        return compact
    request = dict(request)
    request.pop("analysis_obligations", None)
    # J-9/S7: the full default vocabularies are profile material and are
    # omitted when they equal the canonical default.
    if sorted(request.get("allowed_claim_kinds", [])) == sorted(
        k.value for k in m.ClaimKind
    ):
        request.pop("allowed_claim_kinds", None)
    if sorted(request.get("allowed_relationship_kinds", [])) == sorted(
        k.value for k in m.RelationshipKind
    ):
        request.pop("allowed_relationship_kinds", None)
    default_bounds = _schema.to_wire(
        m.to_canonical(DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds),
        m.QueryBounds,
    )
    if request.get("bounds") == default_bounds:
        request.pop("bounds", None)
    brief = request.get("brief")
    if isinstance(brief, dict):
        request["brief"] = _omit_static_brief(brief)
    compact = dict(compact)
    compact["request"] = request
    return compact


def _omit_static_brief(brief: object) -> object:
    if not isinstance(brief, dict):
        return brief
    brief = dict(brief)
    base = {
        "material_path": list(m.TASK_BRIEF_MATERIAL_PATH),
        "semantic_result": list(m.TASK_BRIEF_SEMANTIC_RESULT),
        "adversarial_checks": list(m.TASK_BRIEF_ADVERSARIAL_CHECKS),
        "readback": list(m.TASK_BRIEF_READBACK),
    }
    for key, value in base.items():
        if brief.get(key) == value:
            brief.pop(key)
    if brief.get("open_handling") == list(m.TASK_BRIEF_OPEN_HANDLING):
        brief.pop("open_handling")
    submission_rules = brief.get("submission_rules")
    base_rules = list(m.TASK_BRIEF_SUBMISSION_RULES)
    if (
        isinstance(submission_rules, list)
        and submission_rules[: len(base_rules)] == base_rules
    ):
        dynamic_rules = submission_rules[len(base_rules) :]
        if dynamic_rules:
            brief["submission_rules"] = dynamic_rules
        else:
            brief.pop("submission_rules")
    return brief


def _error(kind: str, message: str) -> ToolResult:
    return ToolResult(
        content=_json.dumps({"error": kind, "message": message}, sort_keys=True),
        structured_content=None,
        is_error=True,
    )
