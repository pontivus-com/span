"""MCP wire boundary: strict ingress decode and canonical egress encode."""

from __future__ import annotations

import dataclasses as _dataclasses
import json as _json
import types as _types
import typing as _typing
from typing import cast as _cast

from span.core import model as m
from span.core import schema as _schema
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.mcp.models import ToolError, ToolResult
from span.shell.mcp.schemas import TOOL_REQUEST_TYPES

__all__ = [
    "RoutingError",
    "canonical_result_payload",
    "decode_request",
    "encode_error",
    "encode_result",
    "repository_route",
    "strip_route",
]


class RoutingError(ValueError):
    """The transport routing key is missing or contradicts the request."""


def strip_route(
    tool_name: str, arguments: dict[str, object]
) -> tuple[dict[str, object], str | None]:
    """Validate the argument object; canonical routing identity stays inside.

    Every repository-scoped canonical request carries its repository binding,
    so it reaches the strict decoder unchanged. ``initialize_repository``
    addresses a locator and is handled by its own setup dispatch.
    """
    if not isinstance(arguments, dict):
        raise RoutingError(f"arguments for {tool_name} must be an object")
    return dict(arguments), None


def decode_request(tool_name: str, arguments: dict[str, object]) -> object:
    """Strict ingress: one boundary, one contract, one parse.

    Unknown fields, unknown enums, missing required fields and a top-level
    ``$type`` fail closed.
    """
    root = TOOL_REQUEST_TYPES.get(tool_name)
    if root is None:
        raise RoutingError(f"unknown tool: {tool_name}")
    payload, _ = strip_route(tool_name, arguments)
    members = _union_members(root)
    if members:
        tag = payload.pop("$type", None)
        if not isinstance(tag, str):
            accepted = ", ".join(member.__name__ for member in members)
            raise ValueError(
                f"missing $type discriminator at root (accepted: {accepted})"
            )
        member = next((item for item in members if item.__name__ == tag), None)
        if member is None:
            raise ValueError(f"unknown $type {tag!r} at root")
        root = member
    if isinstance(root, type) and _dataclasses.is_dataclass(root):
        fields = {field.name for field in _dataclasses.fields(root)}
        if "bounds" in fields and "bounds" not in payload:
            canonical = _typing.cast(
                dict[str, object],
                m.to_canonical(DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds),
            )
            payload["bounds"] = {
                key: value for key, value in canonical.items() if key != "$type"
            }
    try:
        return _schema.from_wire(root, payload)
    except (m.CanonicalDecodeError, ValueError) as exc:
        raise ValueError(f"invalid {tool_name} arguments: {exc}") from None


def _union_members(root: object) -> tuple[type, ...]:
    origin = _typing.get_origin(root)
    if origin not in (_typing.Union, _types.UnionType):
        return ()
    members = [
        item
        for item in _typing.get_args(root)
        if isinstance(item, type) and _dataclasses.is_dataclass(item)
    ]
    return tuple(members)


def repository_route(tool_name: str, request: object, route: str | None) -> str:
    """Resolve the addressed repository without guessing.

    A canonical request that already carries repository identity must agree
    with the transport key. A request without identity requires the key.
    """
    embedded = _embedded_repository(request)
    if embedded is None:
        raise RoutingError(f"{tool_name} request carries no repository identity")
    if route is not None and route != embedded:
        raise RoutingError(
            f"{tool_name} repository_id {route!r} contradicts the request "
            f"repository {embedded!r}"
        )
    return embedded


def _embedded_repository(request: object) -> str | None:
    direct = getattr(request, "repository_id", None)
    if isinstance(direct, str) and direct:
        return direct
    identity = getattr(request, "identity", None)
    if identity is not None:
        embedded = getattr(identity, "repository_id", None)
        if isinstance(embedded, str) and embedded:
            return embedded
    return None


def canonical_result_payload(result: object) -> dict[str, object]:
    """Build the one canonical wire object used by both MCP result channels."""
    compact = _schema.to_wire_root(type(result), m.to_canonical(result))
    return _cast(dict, compact)


def encode_result(result: object) -> str:
    return _json.dumps(canonical_result_payload(result), sort_keys=True)


def encode_error(kind: str, message: str, replacement: str | None = None) -> ToolResult:
    error = ToolError(kind=kind, message=message, replacement=replacement)
    payload = canonical_result_payload(error)
    return ToolResult(
        content=_json.dumps(payload, sort_keys=True),
        structured_content=payload,
        is_error=True,
    )
