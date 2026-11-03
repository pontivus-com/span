"""MCP tool vocabulary: the three lifecycle moments and their schemas.

The surface is exactly ``ask``, ``record``, and ``reconsider``. Action fields
inside ``record`` are semantic content, not separate tools. Every tool decodes
one canonical request and returns one canonical result.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core.schema import record_wire as rw
from span.core.schema import schema_for_request, schema_for_result

__all__ = [
    "REMOVED_TOOLS",
    "TOOL_DESCRIPTIONS",
    "TOOL_EXAMPLES",
    "TOOL_NAMES",
    "TOOL_OUTPUT_SCHEMAS",
    "TOOL_OUTPUT_TYPES",
    "TOOL_REQUEST_TYPES",
    "TOOL_SCHEMAS",
]


@_dataclasses.dataclass(frozen=True)
class ToolSpec:
    """One tool's canonical request/result pair and operator description."""

    name: str
    description: str
    request: object
    result: object


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "ask",
        "Call this before reading or grepping source to understand a covered "
        "surface. To reuse what is retained without knowing the exact recorded "
        "question, omit the question: this returns the surface document view "
        "in `groups` — one group per recorded question with its current "
        "conclusions — and the top-level `conclusions` stays empty. Read the "
        "group that answers your intent; for one targeted conclusion, ask "
        "again with that exact recorded question. "
        "To query one known question, supply it exactly; a paraphrase is a "
        "different question and returns a no_match gap. If the result is "
        "AmbiguousSurface, copy one candidate into an exact surface. Returns "
        "current conclusions with text, support, evidence, and status, plus "
        "applicable verification runs. A gap carries its evidence and a "
        "recovery: follow a continuation if evidence was omitted, and on "
        "no_match ask the same surface without a question. This replaces "
        "Read/Grep when the question is about understanding, not syntax. Start "
        "from `examples` in the input schema; `repository_id` is the registered "
        "id, not a path. ASK TEMPLATE: "
        '{"repository_id":"<id>","request_id":"<new id>",'
        '"surface":{"kind":"FILE","locator":"<path>"},"question":"<question>"}',
        m.AskRequest,
        m.AskResult,
    ),
    ToolSpec(
        "record",
        "Call this after you have established a conclusion from source or "
        "tests. Creates, updates, or verifies understanding, or declares a "
        "service/domain surface and its boundary. `kind` selects what is "
        "recorded: understanding, verification, or surface. An understanding "
        "create is flat: no action and no actions; action belongs to "
        "kind=surface. State the evidence you already hold; Span "
        "derives context, ids, and revisions. "
        "A create may use the context_id from ask instead of question and "
        "scope_paths; do not send both. "
        "CREATE TEMPLATE (copy and fill): "
        '{"repository_id":"<id>","request_id":"<new id>",'
        '"kind":"understanding","question":"<exact question>",'
        '"scope_paths":["<path>"],"conclusion":"<statement>",'
        '"locator":"<path>"} '
        "Use observation_id instead of locator when the ask Gap gave you one. "
        "Omit surface; Span derives it from one scope_path, or from the context. "
        "With a context, omit question and scope_paths. "
        "UPDATE TEMPLATE: the same request with understanding_id and "
        "expected_version, kind understanding, actions.add, and no surface. "
        "SURFACE TEMPLATE (only when the answer spans several files): "
        '{"repository_id":"<id>","request_id":"<new id>","kind":"surface",'
        '"action":"create","surface":{"kind":"SERVICE","locator":"<name>",'
        '"boundary":{"paths":["<path>"],"symbols":[]},"parent":null}} '
        'Then record against it with surface {"kind":"SERVICE",'
        '"locator":"<name>"}. '
        "VERIFICATION TEMPLATE (copy and fill): "
        '{"repository_id":"<id>","request_id":"<new id>",'
        '"context_id":"<context from ask>","kind":"verification",'
        '"run":{"repository_id":"<id>","scope_description":"<what was tested>",'
        '"scope_paths":["<path>"],"observations":["<obs id from ask>"],'
        '"command":"<command>","scenario":"<scenario>","outcome":"PASS",'
        '"observed_at":"<ISO 8601>","observer":"<agent>"}} '
        "run.observations takes the obs: ids ask returned for that context; to "
        'cite a locator instead, add "evidence":[{"locator":"<path>"}] to run '
        "and keep the same context_id. A run applies only to the surfaces in "
        "its declared scope, so record it against the surface it verifies. "
        "Do not choose a record variant; kind is a field.",
        rw.RecordRequestWire,
        m.RecordResult,
    ),
    ToolSpec(
        "reconsider",
        "Call this after editing files or when disputing a conclusion. "
        "Returns every surface that must be re-examined, why, what to "
        "re-establish, and the context for doing so. Start from `examples` in "
        "the input schema.",
        m.ReconsiderRequest,
        m.ReconsiderResult,
    ),
)

TOOL_NAMES: tuple[str, ...] = tuple(spec.name for spec in TOOL_SPECS)
TOOL_DESCRIPTIONS: dict[str, str] = {spec.name: spec.description for spec in TOOL_SPECS}
TOOL_REQUEST_TYPES: dict[str, object] = {spec.name: spec.request for spec in TOOL_SPECS}
TOOL_OUTPUT_TYPES: dict[str, object] = {spec.name: spec.result for spec in TOOL_SPECS}
TOOL_SCHEMAS: dict[str, dict] = {
    spec.name: schema_for_request(spec.request, description=spec.description)
    for spec in TOOL_SPECS
}
TOOL_OUTPUT_SCHEMAS: dict[str, dict] = {
    spec.name: schema_for_result(spec.result) for spec in TOOL_SPECS
}

_CONCLUSION_EXAMPLE = {
    "conclusion_id": "c1",
    "statement": "The value is loaded from config/settings.yaml.",
    "assertion_nature": "DESCRIPTIVE",
    "scope_paths": ["src/a.py"],
    "scope_evidence_refs": [],
    "support": [
        {
            "$type": "AdmittedSourceSupportWire",
            "observation_id": "obs:...",
        }
    ],
    "basis_derivation": "EXPLICIT_EVIDENCE",
    "basis_summary": "read src/a.py",
    "basis_input_refs": [],
}

#: Exact minimal call shapes. A host that copies one of these succeeds; the
#: prose description alone is not enough on a real task.
TOOL_EXAMPLES: dict[str, list[dict]] = {
    "ask": [
        {
            "repository_id": "repo-1",
            "request_id": "ask-1",
            "surface": {"kind": "FILE", "locator": "src/a.py"},
            "question": "What does A do?",
        },
        {
            "repository_id": "repo-1",
            "request_id": "ask-2",
            "reference": "src/a.py",
        },
    ],
    "record": [
        {
            "repository_id": "repo-1",
            "request_id": "rec-1",
            "kind": "understanding",
            "question": "What does A do?",
            "scope_paths": ["src/a.py"],
            "conclusion": "The value is loaded from config/settings.yaml.",
            "locator": "src/a.py",
        },
        {
            "repository_id": "repo-1",
            "request_id": "rec-2",
            "kind": "understanding",
            "understanding_id": "u:rec-1",
            "expected_version": 1,
            "actions": {"add": [dict(_CONCLUSION_EXAMPLE)]},
        },
        {
            "repository_id": "repo-1",
            "request_id": "surf-1",
            "kind": "surface",
            "action": "create",
            "surface": {
                "kind": "SERVICE",
                "locator": "billing",
                "boundary": {"paths": ["src"], "symbols": []},
                "parent": None,
            },
        },
        {
            "repository_id": "repo-1",
            "request_id": "ver-1",
            "context_id": "ctx-1",
            "kind": "verification",
            "run": {
                "repository_id": "repo-1",
                "scope_description": "src/a.py behaviour",
                "scope_paths": ["src/a.py"],
                "observations": ["obs:..."],
                "command": "pytest tests/test_a.py",
                "scenario": "configured override",
                "outcome": "PASS",
                "observed_at": "2026-11-03T00:00:00Z",
                "observer": "agent",
            },
        },
        {
            "repository_id": "repo-1",
            "request_id": "rec-3",
            "kind": "understanding",
            "surface": {"kind": "SERVICE", "locator": "billing"},
            "question": "How is the value determined?",
            "scope_paths": ["src/a.py"],
            "conclusion": "The value is loaded from config/settings.yaml.",
            "locator": "src/a.py",
        },
    ],
    "reconsider": [
        {
            "repository_id": "repo-1",
            "changed_paths": ["src/a.py"],
        }
    ],
}

for _name, _examples in TOOL_EXAMPLES.items():
    TOOL_SCHEMAS[_name]["examples"] = _examples

#: Retired tool names reject with an exact replacement and no side effects.
REMOVED_TOOLS: dict[str, str] = {
    "understand_question": "use ask",
    "understand_retrieve": "use ask with an exact selector",
    "reassess": "use ask; support is in every answer",
    "verification_support": "use ask; the run and support are in every answer",
    "start_context": "removed; context is issued inside ask and record",
    "evidence_start": "removed; evidence is admitted inside ask and record",
    "evidence_extend": "removed; evidence is admitted inside ask and record",
    "record_create": "use record with conclusion and locator or observation_id",
    "record_add": "use record with actions.add",
    "record_confirm": "use record with actions.confirm",
    "record_correct": "use record with actions.correct",
    "record_replace": "use record with actions.replace",
    "record_withdraw": "use record with actions.withdraw",
    "record_challenge": "use reconsider with a challenge",
    "record_update": "use record with an actions object",
    "record_verification": 'use record with kind="verification"',
    "initialize_repository": "run the installer (span-install) to bind the repository",
    "locate": "use the host's own file navigation; this build registers no structural tool",
    "neighbors": "use the host's own file navigation; this build registers no structural tool",
    "explain": "use ask",
    "trace": "use the host's own file navigation; this build registers no structural tool",
    "impact": "use ask, then reconsider after editing",
    "authority": "authority is qualified inside ask",
    "status": "use ask; status is in every answer",
    "refresh": "re-record the affected conclusions with record",
    "initialize_target": "run the installer (span-install) to bind the repository",
    "submit_interpretation": "use record",
}
