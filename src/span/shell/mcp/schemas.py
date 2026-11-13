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
        "Call this before reading or grepping source to understand a "
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
        "Required when you establish a supported semantic conclusion from source or "
        "tests. After edits, call reconsider before revising affected conclusions; "
        "use its returned identities/version for the update. Creates, updates, or "
        "verifies understanding, or declares a "
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
        "Create evidence is exactly one of locator, observation_id, or "
        "non-empty support; scope is supplied or derived independently. Use "
        "observation_id instead of locator when the ask Gap gave you one. Use "
        "support when you already hold the complete dependency set; then do "
        "not also send observation_id. Omit surface; Span derives it from one "
        "scope_path, or from the context. With a context, omit question and "
        "scope_paths. "
        "Semantic scope describes the conclusion's subject; support names what "
        "established it. Multiple support files do not create owners. A supplied "
        "context has fixed complete scope: new in-scope evidence may be admitted "
        "during record. Empty scope means repository-wide. Discovery boundaries "
        "must fit completely. When investigation expands, omit context_id and "
        "supply direct scope/evidence; Span derives a new operational context. "
        "Repository-wide discovery makes it repository-wide without widening "
        "semantic scope. Admitted references remain context-bound. "
        "When revising an existing conclusion, update its returned understanding/version; "
        "do not create it again. UPDATE TEMPLATE (copy and fill): "
        '{"repository_id":"<id>","request_id":"<new id>",'
        '"kind":"understanding","understanding_id":"<returned id>",'
        '"expected_version":1,"actions":{"correct":[{"conclusion_id":"<returned id>",'
        '"conclusion":"<updated statement>","locator":"<path>"}]}} '
        "actions is an object whose values are lists. Omit top-level action, "
        "question, scope_paths and conclusion on updates. Span derives new lineage identities, old "
        "revisions, unchanged content, and the mechanical basis. Each action "
        "names exactly one evidence mode: locator, observation_id, or support. "
        "add takes conclusion; confirm, correct, replace, and withdraw name the "
        "existing conclusion_id returned by Span; replace takes conclusion and "
        "reason; withdraw takes reason and optional evidence; confirm preserves "
        "the current content. Do not send conclusion_id on add or "
        "new_conclusion_id on replace. "
        "SURFACE TEMPLATE (only when the conclusion describes that declared boundary): "
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
        "A run requires at least one observation or evidence item; both may coexist. "
        "run.observations requires the context that admitted those IDs. "
        "run.evidence may admit new locators inside that context's fixed scope. "
        "For evidence beyond it, omit context_id and supply run.scope_paths and "
        "run.evidence. A run applies to surfaces within its declared scope "
        "and is not widened by a broader question, so record it against the "
        "surface it verifies. "
        "Do not choose a record variant; kind is a field.",
        rw.RecordRequestWire,
        m.RecordResult,
    ),
    ToolSpec(
        "reconsider",
        "Required after editing files or when disputing a conclusion. Investigate "
        "affected non-current conclusions and record supported dispositions before "
        "completing the work. "
        "Returns every surface that must be re-examined, why, what to "
        "re-establish, and the context for doing so. `surfaces` is the complete "
        "containment set: a surface with no `conclusions` is containment-only, "
        "not a finding. Act only on conclusions whose support state is "
        "`REASSESSMENT_REQUIRED` or `UNVERIFIABLE`; a `CURRENT` conclusion in "
        "the set needs no work. The order is deterministic and must not be "
        "re-sorted. Start from `examples` in the input schema.",
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
            "request_id": "rec-add",
            "kind": "understanding",
            "understanding_id": "u:rec-1",
            "expected_version": 1,
            "actions": {
                "add": [
                    {
                        "conclusion": "B performs Y.",
                        "locator": "src/b.py",
                    }
                ]
            },
        },
        {
            "repository_id": "repo-1",
            "request_id": "rec-confirm",
            "context_id": "ctx-from-reconsider",
            "kind": "understanding",
            "understanding_id": "u:rec-1",
            "expected_version": 2,
            "actions": {
                "confirm": [
                    {
                        "conclusion_id": "<id returned by Span>",
                        "locator": "src/a.py",
                    }
                ]
            },
        },
        {
            "repository_id": "repo-1",
            "request_id": "rec-correct",
            "context_id": "ctx-from-reconsider",
            "kind": "understanding",
            "understanding_id": "u:rec-1",
            "expected_version": 2,
            "actions": {
                "correct": [
                    {
                        "conclusion_id": "<id returned by Span>",
                        "conclusion": "A now performs Z.",
                        "locator": "src/a.py",
                    }
                ]
            },
        },
        {
            "repository_id": "repo-1",
            "request_id": "rec-replace",
            "kind": "understanding",
            "understanding_id": "u:rec-1",
            "expected_version": 2,
            "actions": {
                "replace": [
                    {
                        "conclusion_id": "<id returned by Span>",
                        "conclusion": "The replacement behaviour is Z.",
                        "reason": "The prior implementation was superseded.",
                        "locator": "src/a.py",
                    }
                ]
            },
        },
        {
            "repository_id": "repo-1",
            "request_id": "rec-withdraw",
            "kind": "understanding",
            "understanding_id": "u:rec-1",
            "expected_version": 2,
            "actions": {
                "withdraw": [
                    {
                        "conclusion_id": "<id returned by Span>",
                        "reason": "The implementation no longer has this behaviour.",
                    }
                ]
            },
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
