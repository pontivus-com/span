"""Test-only schema-delivery lab.

Each tool isolates one schema construct so a host's code-mode declaration can
be inspected without conflating it with the full candidate command. This file
is diagnostic only; it is not a shipped Span operation, a domain carrier, or
a second request grammar.

Run with:
    PYTHONPATH=src .venv/bin/python tests/fixtures/host-contract/schema_lab_server.py
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from span.core import model as m
from span.core.schema import schema_for_request
from span.core.schema import record_wire as rw

__all__ = ["build_server", "main"]


def _object(properties: dict[str, object], required: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def _nominal() -> dict:
    return _object({"value": {"type": "string"}}, ("value",))


def _inline_refs(value: object, defs: dict[str, object], seen: set[str]) -> object:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[-1]
            if name in seen or name not in defs:
                return value
            return _inline_refs(defs[name], defs, seen | {name})
        return {
            key: _inline_refs(item, defs, seen)
            for key, item in value.items()
            if key != "$defs"
        }
    if isinstance(value, list):
        return [_inline_refs(item, defs, seen) for item in value]
    return value


def _inlined_create_schema() -> dict:
    schema = schema_for_request(m.CreateUnderstandingCommand)
    return _inline_refs(schema, schema.get("$defs", {}), set())


def _string() -> dict:
    return {"type": "string"}


def _nullable_string() -> dict:
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _array(items: dict) -> dict:
    return {"type": "array", "items": items}


def _simple_identity() -> dict:
    return _object(
        {
            "repository_id": _string(),
            "context_id": _string(),
            "submission_id": _string(),
        },
        ("repository_id", "context_id", "submission_id"),
    )


def _simple_scope() -> dict:
    return _object({"paths": _array(_string())}, ("paths",))


def _simple_evidence_ref() -> dict:
    return _object(
        {
            "evidence_id": _string(),
            "repository_id": _string(),
            "source_kind": {
                "type": "string",
                "enum": ["SOURCE_CODE", "DOCUMENTATION", "OTHER"],
            },
            "locator": _string(),
            "revision_or_fingerprint": _nullable_string(),
            "section_or_span": _nullable_string(),
        },
        ("evidence_id", "repository_id", "source_kind", "locator"),
    )


def _simple_support() -> dict:
    return {
        "anyOf": [
            _object(
                {"$type": {"const": "SourceSupport"}, "observation_id": _string()},
                ("$type", "observation_id"),
            ),
            _object(
                {
                    "$type": {"const": "AuthoritySupportDependency"},
                    "authority_evidence_id": _string(),
                    "authority_kind": {"type": "string"},
                    "status": {"type": "string"},
                },
                ("$type", "authority_evidence_id", "authority_kind", "status"),
            ),
            _object(
                {
                    "$type": {"const": "PremiseSupport"},
                    "understanding_id": _string(),
                    "conclusion_id": _string(),
                    "revision": {"type": "integer"},
                },
                ("$type", "understanding_id", "conclusion_id", "revision"),
            ),
            _object(
                {"$type": {"const": "DiscoverySupport"}, "observation_id": _string()},
                ("$type", "observation_id"),
            ),
        ]
    }


def _simple_conclusion() -> dict:
    return _object(
        {
            "conclusion_id": _string(),
            "statement": _string(),
            "assertion_nature": {
                "type": "string",
                "enum": ["DESCRIPTIVE", "NORMATIVE"],
            },
            "scope": _simple_scope(),
            "support": _array(_simple_support()),
            "basis_derivation": {
                "type": "string",
                "enum": [
                    "EXPLICIT_EVIDENCE",
                    "SEMANTIC_INTERPRETATION",
                    "STRUCTURAL_OBSERVATION",
                    "DERIVED_JOIN",
                ],
            },
            "basis_summary": _string(),
            "basis_evidence": _array(_simple_evidence_ref()),
        },
        (
            "conclusion_id",
            "statement",
            "assertion_nature",
            "scope",
            "support",
            "basis_derivation",
            "basis_summary",
            "basis_evidence",
        ),
    )


def _simple_gap() -> dict:
    return _object({"question": _string(), "basis": _string()}, ("question", "basis"))


def _simple_create() -> dict:
    return _object(
        {
            "identity": _simple_identity(),
            "target": {
                "anyOf": [
                    _object({"$type": {"const": "ContextBoundTarget"}}, ("$type",)),
                    _object(
                        {
                            "$type": {"const": "ExplicitTarget"},
                            "question": _string(),
                            "scope": _simple_scope(),
                        },
                        ("$type", "question", "scope"),
                    ),
                ]
            },
            "conclusions": _array(_simple_conclusion()),
            "gaps": _array(_simple_gap()),
            "provenance": _string(),
        },
        ("identity", "target", "conclusions"),
    )


def _simple_action() -> dict:
    conclusion = _simple_conclusion()
    return {
        "anyOf": [
            _object(
                {"$type": {"const": "AddConclusion"}, "conclusion": conclusion},
                ("$type", "conclusion"),
            ),
            _object(
                {
                    "$type": {"const": "ConfirmConclusion"},
                    "conclusion_id": _string(),
                    "conclusion": conclusion,
                },
                ("$type", "conclusion_id", "conclusion"),
            ),
            _object(
                {
                    "$type": {"const": "WithdrawConclusion"},
                    "conclusion_id": _string(),
                    "basis_summary": _string(),
                },
                ("$type", "conclusion_id", "basis_summary"),
            ),
        ]
    }


def _simple_update() -> dict:
    return _object(
        {
            "identity": _simple_identity(),
            "understanding_id": _string(),
            "expected_version": {"type": "integer"},
            "actions": _array(_simple_action()),
            "gaps": _array(_simple_gap()),
            "provenance": _string(),
        },
        (
            "identity",
            "understanding_id",
            "expected_version",
            "actions",
        ),
    )


def _simple_verification() -> dict:
    return _object(
        {
            "identity": _simple_identity(),
            "run": _object(
                {
                    "repository_id": _string(),
                    "scope": _object(
                        {"description": _string(), "paths": _array(_string())},
                        ("description", "paths"),
                    ),
                    "observations": _array(_string()),
                    "command": _nullable_string(),
                    "scenario": _nullable_string(),
                    "outcome": {
                        "type": "string",
                        "enum": ["PASS", "FAIL", "INCONCLUSIVE"],
                    },
                    "observed_at": _string(),
                    "observer": _string(),
                    "environment_limitations": _array(_string()),
                },
                (
                    "repository_id",
                    "scope",
                    "observations",
                    "outcome",
                    "observed_at",
                    "observer",
                ),
            ),
        },
        ("identity", "run"),
    )


def _simple_record() -> dict:
    return _object(
        {
            "command": {
                "anyOf": [
                    _object(
                        {
                            "$type": {"const": "CreateUnderstandingCommand"},
                            "create": _simple_create(),
                        },
                        ("$type", "create"),
                    ),
                    _object(
                        {
                            "$type": {"const": "UpdateUnderstandingCommand"},
                            "update": _simple_update(),
                        },
                        ("$type", "update"),
                    ),
                    _object(
                        {
                            "$type": {"const": "RecordVerificationCommand"},
                            "verification": _simple_verification(),
                        },
                        ("$type", "verification"),
                    ),
                ]
            }
        },
        ("command",),
    )


def _branch(tag: str, schema: dict) -> dict:
    branch = dict(schema)
    properties = dict(branch.get("properties", {}))
    properties["$type"] = {"const": tag}
    branch["properties"] = properties
    branch["required"] = ["$type"] + list(branch.get("required", []))
    return branch


def _simple_record_flat() -> dict:
    return _object(
        {
            "command": {
                "anyOf": [
                    _branch("CreateUnderstandingCommand", _simple_create()),
                    _branch("UpdateUnderstandingCommand", _simple_update()),
                    _branch("RecordVerificationCommand", _simple_verification()),
                ]
            }
        },
        ("command",),
    )


def _simple_action_flat() -> dict:
    fields = {
        "conclusion_id": _string(),
        "statement": _string(),
        "assertion_nature": {
            "type": "string",
            "enum": ["DESCRIPTIVE", "NORMATIVE"],
        },
        "scope": _simple_scope(),
        "support": _array(_simple_support()),
        "basis_derivation": {
            "type": "string",
            "enum": [
                "EXPLICIT_EVIDENCE",
                "SEMANTIC_INTERPRETATION",
                "STRUCTURAL_OBSERVATION",
                "DERIVED_JOIN",
            ],
        },
        "basis_summary": _string(),
        "basis_evidence": _array(_simple_evidence_ref()),
    }
    required = (
        "conclusion_id",
        "statement",
        "assertion_nature",
        "scope",
        "support",
        "basis_derivation",
        "basis_summary",
        "basis_evidence",
    )
    return {
        "anyOf": [
            _object(
                {"$type": {"const": "AddConclusion"}, **fields}, ("$type", *required)
            ),
            _object(
                {"$type": {"const": "ConfirmConclusion"}, **fields},
                ("$type", *required),
            ),
            _object(
                {
                    "$type": {"const": "WithdrawConclusion"},
                    "conclusion_id": _string(),
                    "basis_summary": _string(),
                },
                ("$type", "conclusion_id", "basis_summary"),
            ),
        ]
    }


def _simple_update_flat() -> dict:
    return _object(
        {
            "identity": _simple_identity(),
            "understanding_id": _string(),
            "expected_version": {"type": "integer"},
            "actions": _array(_simple_action_flat()),
            "gaps": _array(_simple_gap()),
            "provenance": _string(),
        },
        (
            "identity",
            "understanding_id",
            "expected_version",
            "actions",
        ),
    )


def _simple_withdraw_action() -> dict:
    return _object(
        {
            "conclusion_id": _string(),
            "basis_summary": _string(),
        },
        ("conclusion_id", "basis_summary"),
    )


def _simple_replace_action() -> dict:
    return _object(
        {
            "old_understanding_id": _string(),
            "old_conclusion_id": _string(),
            "old_revision": {"type": "integer"},
            "new_conclusion": _simple_conclusion(),
            "replacement_basis_summary": _string(),
        },
        (
            "old_understanding_id",
            "old_conclusion_id",
            "old_revision",
            "new_conclusion",
            "replacement_basis_summary",
        ),
    )


def _simple_update_split() -> dict:
    return _object(
        {
            "identity": _simple_identity(),
            "understanding_id": _string(),
            "expected_version": {"type": "integer"},
            "add": _array(_simple_conclusion()),
            "confirm": _array(_simple_conclusion()),
            "correct": _array(_simple_conclusion()),
            "replace": _array(_simple_replace_action()),
            "withdraw": _array(_simple_withdraw_action()),
            "gaps": _array(_simple_gap()),
            "provenance": _string(),
        },
        (
            "identity",
            "understanding_id",
            "expected_version",
        ),
    )


def _simple_update_split_min() -> dict:
    return _object(
        {
            "identity": _simple_identity(),
            "understanding_id": _string(),
            "expected_version": {"type": "integer"},
            "add": _array(_simple_conclusion()),
            "withdraw": _array(_simple_withdraw_action()),
        },
        (
            "identity",
            "understanding_id",
            "expected_version",
        ),
    )


def _simple_record_root_union() -> dict:
    return {
        "anyOf": [
            _branch("CreateUnderstandingCommand", _simple_create()),
            _branch("UpdateUnderstandingCommand", _simple_update_split()),
            _branch("RecordVerificationCommand", _simple_verification()),
        ]
    }


def _simple_record_wrapper_split() -> dict:
    return _object(
        {
            "command": {
                "anyOf": [
                    _branch("CreateUnderstandingCommand", _simple_create()),
                    _branch("UpdateUnderstandingCommand", _simple_update_split()),
                    _branch("RecordVerificationCommand", _simple_verification()),
                ]
            }
        },
        ("command",),
    )


def _simple_record_root_oneof() -> dict:
    return {
        "type": "object",
        "oneOf": [
            _branch("CreateUnderstandingCommand", _simple_create()),
            _branch("UpdateUnderstandingCommand", _simple_update_split()),
            _branch("RecordVerificationCommand", _simple_verification()),
        ],
    }


def _simple_update_one_action() -> dict:
    return _object(
        {
            "identity": _simple_identity(),
            "understanding_id": _string(),
            "expected_version": {"type": "integer"},
            "action": _simple_action_flat(),
        },
        ("identity", "understanding_id", "expected_version", "action"),
    )


def _simple_add_action_tool() -> dict:
    fields = {
        "identity": _simple_identity(),
        "understanding_id": _string(),
        "expected_version": {"type": "integer"},
        "conclusion": _simple_conclusion(),
    }
    return _object(
        fields, ("identity", "understanding_id", "expected_version", "conclusion")
    )


def _tool_specs() -> list[types.Tool]:
    nominal = _nominal()
    union = {
        "anyOf": [
            _object(
                {
                    "$type": {"const": "BranchA"},
                    "a": {"type": "string"},
                },
                ("$type", "a"),
            ),
            _object(
                {
                    "$type": {"const": "BranchB"},
                    "b": {"type": "integer"},
                },
                ("$type", "b"),
            ),
        ]
    }
    cases = {
        "lab_flat": _object({"name": {"type": "string"}}, ("name",)),
        "lab_nominal": _object({"id": nominal}, ("id",)),
        "lab_nominal_string": _object({"id": {"type": "string"}}, ("id",)),
        "lab_array_nominal": _object(
            {"ids": {"type": "array", "items": nominal}}, ("ids",)
        ),
        "lab_array_string": _object(
            {"ids": {"type": "array", "items": {"type": "string"}}}, ("ids",)
        ),
        "lab_nested": _object(
            {
                "outer": _object(
                    {"inner": _object({"value": {"type": "string"}}, ("value",))},
                    ("inner",),
                )
            },
            ("outer",),
        ),
        "lab_union": _object({"target": union}, ("target",)),
        "lab_full_create": schema_for_request(m.CreateUnderstandingCommand),
        "lab_production_create": schema_for_request(m.CreateUnderstandingCommand),
        "lab_production_create_inlined": _inline_refs(
            schema_for_request(m.CreateUnderstandingCommand),
            schema_for_request(m.CreateUnderstandingCommand).get("$defs", {}),
            set(),
        ),
        "lab_production_update": schema_for_request(m.UpdateUnderstandingCommand),
        "lab_production_update_inlined": _inline_refs(
            schema_for_request(m.UpdateUnderstandingCommand),
            schema_for_request(m.UpdateUnderstandingCommand).get("$defs", {}),
            set(),
        ),
        "lab_wire_create": schema_for_request(rw.RecordCreateWire),
        "lab_wire_create_inlined": _inline_refs(
            schema_for_request(rw.RecordCreateWire),
            schema_for_request(rw.RecordCreateWire).get("$defs", {}),
            set(),
        ),
        "lab_wire_update": schema_for_request(rw.RecordUpdateWire),
        "lab_wire_update_inlined": _inline_refs(
            schema_for_request(rw.RecordUpdateWire),
            schema_for_request(rw.RecordUpdateWire).get("$defs", {}),
            set(),
        ),
        "lab_wire_verification": schema_for_request(rw.RecordVerificationWire),
        "lab_wire_add": schema_for_request(rw.RecordAddWire),
        "lab_wire_confirm": schema_for_request(rw.RecordConfirmWire),
        "lab_wire_correct": schema_for_request(rw.RecordCorrectWire),
        "lab_wire_replace": schema_for_request(rw.RecordReplaceWire),
        "lab_wire_withdraw": schema_for_request(rw.RecordWithdrawWire),
        "lab_full_create_inlined": _inlined_create_schema(),
        "lab_create_simple": _simple_create(),
        "lab_record_simple": _simple_record(),
        "lab_record_flat": _simple_record_flat(),
        "lab_update_simple": _simple_update(),
        "lab_update_flat": _simple_update_flat(),
        "lab_update_split": _simple_update_split(),
        "lab_update_split_min": _simple_update_split_min(),
        "lab_update_one_action": _simple_update_one_action(),
        "lab_add_action_tool": _simple_add_action_tool(),
        "lab_record_wrapper_split": _simple_record_wrapper_split(),
        "lab_record_root_oneof": _simple_record_root_oneof(),
        "lab_verification_simple": _simple_verification(),
    }
    return [
        types.Tool(
            name=name,
            description=f"Schema lab case: {name}",
            inputSchema=schema,
            outputSchema=_object({"ok": {"type": "boolean"}}, ("ok",)),
        )
        for name, schema in cases.items()
    ]


async def _list_tools(_context: object, _params: object) -> types.ListToolsResult:
    return types.ListToolsResult(tools=_tool_specs())


async def _call_tool(
    _context: object, params: types.CallToolRequestParams
) -> types.CallToolResult:
    result = {"ok": True, "tool": params.name}
    return types.CallToolResult(
        content=[types.TextContent(text=json.dumps(result))],
        structuredContent=result,
    )


def build_server() -> Server:
    return Server(
        "span-schema-lab",
        version="0.9.0-lab",
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
    )


async def _serve() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
