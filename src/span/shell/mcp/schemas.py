"""MCP tool vocabulary: the shipped lifecycle surface and generated schemas.

Every tool is exactly one canonical request → one canonical result. The record
family stays separate tools because the combined union was proven undeliverable
to supported hosts (G-0 evidence); it is not a second grammar, because every
tool decodes the same canonical carriers.

``initialize_repository``, ``locate`` and ``neighbors`` keep their separate
administrative or navigation roles.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core.schema import record_wire as rw
from span.core.schema import schema_for_request, schema_for_result
from span.service.navigation import (
    SemanticStructuralLocateRequest,
    SemanticStructuralNeighborsRequest,
)

__all__ = [
    "REMOVED_TOOLS",
    "TOOL_DESCRIPTIONS",
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
        "initialize_repository",
        "Prepare a repository for lifecycle use in a dedicated setup "
        "session: bind the root and declared authority seeds. No semantic "
        "interpretation and no understanding are created.",
        m.InitializeRepositoryRequest,
        m.InitializeRepositoryResult,
    ),
    ToolSpec(
        "start_context",
        "Issue or recover the one server-owned investigation context bound "
        "to a caller request identity. Recovery is safe after a lost "
        "response or process restart.",
        m.StartContextRequest,
        m.InvestigationContext,
    ),
    ToolSpec(
        "understand_question",
        "Discover saved understanding matching a question and exact scope, "
        "or return inspectable evidence and an explicit investigation gap. "
        "Lexical rank never establishes applicability; the agent judges it.",
        m.UnderstandQuestionRequest,
        m.UnderstandQuestionResult,
    ),
    ToolSpec(
        "understand_retrieve",
        "Return one exact understanding snapshot with live support, one "
        "context with its admitted observations, or one retained receipt. "
        "Each selector carries `repository_id`.",
        m.RetrieveRequest,
        m.RetrieveResult,
    ),
    ToolSpec(
        "reassess",
        "Qualify one understanding version against present source, authority, "
        "premise and discovery support. Requires `repository_id`.",
        m.ReassessRequest,
        m.UnderstandingSupport,
    ),
    ToolSpec(
        "verification_support",
        "Qualify one independent verification run against the observations it "
        "actually tested. Requires `repository_id`.",
        m.VerificationSupportRequest,
        m.VerificationSupport,
    ),
    ToolSpec(
        "evidence_start",
        "Start one evidence-only context from a bounded batch of exact "
        "source/range requests. No semantic question is required.",
        m.EvidenceStartRequest,
        m.EvidenceAdmissionResult,
    ),
    ToolSpec(
        "evidence_extend",
        "Admit further exact sources into one live context and report every "
        "admission, reuse, failure and omission. Requires `repository_id`.",
        m.EvidenceExtendRequest,
        m.EvidenceAdmissionResult,
    ),
    ToolSpec(
        "record_create",
        "Create one understanding from admitted evidence through the "
        "canonical reference-only wire. Returns an atomic receipt.",
        rw.RecordCreateWire,
        m.UnderstandingRecorded,
    ),
    ToolSpec(
        "record_add",
        "Add one conclusion to an existing understanding version.",
        rw.RecordAddWire,
        m.UnderstandingRecorded,
    ),
    ToolSpec(
        "record_confirm",
        "Confirm one existing conclusion at its exact revision.",
        rw.RecordConfirmWire,
        m.UnderstandingRecorded,
    ),
    ToolSpec(
        "record_correct",
        "Correct one existing conclusion at its exact revision.",
        rw.RecordCorrectWire,
        m.UnderstandingRecorded,
    ),
    ToolSpec(
        "record_replace",
        "Replace one existing conclusion at its exact revision.",
        rw.RecordReplaceWire,
        m.UnderstandingRecorded,
    ),
    ToolSpec(
        "record_withdraw",
        "Withdraw one existing conclusion at its exact revision with a basis.",
        rw.RecordWithdrawWire,
        m.UnderstandingRecorded,
    ),
    ToolSpec(
        "record_challenge",
        "Create one explicit challenge bound to exact conclusion revisions. "
        "Creation does not settle the dispute.",
        rw.RecordChallengeWire,
        m.ChallengeRecorded,
    ),
    ToolSpec(
        "record_update",
        "Apply one combined update and named challenge dispositions "
        "atomically; partial settlement is rejected.",
        rw.RecordUpdateWire,
        m.UnderstandingRecorded,
    ),
    ToolSpec(
        "record_verification",
        "Record one independent verification run against the observations it "
        "actually tested.",
        rw.RecordVerificationWire,
        m.VerificationRecorded,
    ),
    ToolSpec(
        "locate",
        "Read-only structural find, file outline, or target member listing. "
        "Navigation evidence only; not an authority claim.",
        SemanticStructuralLocateRequest,
        m.StructuralLocateResult,
    ),
    ToolSpec(
        "neighbors",
        "Read-only bounded structural adjacency, upstream, downstream or both. "
        "Navigation evidence only; not an authority claim.",
        SemanticStructuralNeighborsRequest,
        m.StructuralNeighborsResult,
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

#: Retired tool names reject with an exact replacement and no side effects.
REMOVED_TOOLS: dict[str, str] = {
    "explain": "use understand_question, then understand_retrieve",
    "trace": "use neighbors for structural adjacency",
    "impact": "use understand_question, then reassess recorded understanding",
    "authority": "authority is qualified by reassess and understand_question",
    "status": "use reassess for recorded understanding; hooks are optional",
    "refresh": "re-record the affected conclusions with record_*",
    "initialize_target": (
        "use initialize_repository, then start_context or evidence_start"
    ),
    "submit_interpretation": "record directly with record_*",
}
