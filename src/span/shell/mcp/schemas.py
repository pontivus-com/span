"""MCP tool vocabulary: names, descriptions, and generated schemas."""

from __future__ import annotations

from span.core import model as m
from span.core import schema as _schema
from span.ports.interpretation import PendingInterpretation
from span import service as ops
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY

__all__ = [
    "TOOL_NAMES",
    "TOOL_SCHEMAS",
    "TOOL_OUTPUT_SCHEMAS",
    "TOOL_DESCRIPTIONS",
]


TOOL_DESCRIPTIONS: dict[str, str] = {
    "initialize_repository": (
        "Prepare a repository for semantic queries in a dedicated "
        "setup session (operational storage readiness only). No semantic "
        "interpretation happens here. Pass the plain `repository_locator` "
        "and, optionally, `authority_seeds`; provider selection stays "
        "shell-owned."
    ),
    "initialize_target": (
        "Establish the semantic campaign for an exact directory or "
        "evidence scope (deterministic TargetId). Returns the next typed "
        "interpretation unit; advance the target frontier through "
        "submit_interpretation. Procedure lives in the skill/runbook."
    ),
    "explain": (
        "Explain what a subject is, what it does, and what governs it, "
        "with evidence, authority, and freshness."
    ),
    "impact": (
        "Pre-change semantic brief for a proposed material change: "
        "impacts, conditions, authority, verification, blockers."
    ),
    "trace": (
        "Producers, carriers, consumers, boundaries, and lifecycle path "
        "for a target, upstream/downstream/both."
    ),
    "authority": (
        "Governing sources with status, applicability, precedence, and "
        "conflicts shown side-by-side."
    ),
    "status": (
        "Normal no-target status reports bounded persisted semantic "
        "coverage: current, incomplete, stale/unverifiable, and "
        "unassessed subjects. Entry guidance names the next exact step: "
        "stale or unverifiable work uses refresh with an exact "
        "SubjectSelector; unassessed work uses a question-local explain only "
        "when no owning operation is live; otherwise continue its returned "
        "continuation. "
        "pending question work continues only through the continuation "
        "returned by the suspending operation. Exact targets report "
        "detailed freshness; store_readiness READY means Span "
        "storage/runtime availability only, not semantic completeness. "
        "HOOK_FAST "
        "returns a compact notice only: event-local scope, never "
        "repository inventory, so READY 0/0 never means clean."
    ),
    "refresh": (
        "Explicitly reinterpret a scoped semantic target. For stale "
        "work, use an exact SubjectSelector or EvidenceScope. Challenging "
        "an otherwise CURRENT subject requires stale_only=false with an "
        "exact SubjectSelector and an already-persisted question. "
        "UNASSESSED subjects require question-local explain only when no "
        "owning operation is live. Never automatic."
    ),
    "submit_interpretation": (
        "Submit the host-produced typed interpretation result for a "
        "pending continuation; the agent performs interpretation, Span "
        "validates and atomically persists it. Returns the answer, or "
        "the next pending unit while frontiers remain. Pending tasks use "
        "the SA_1_7_V1 interpretation profile; satisfy its evidence, "
        "scope, typed-disposition, adversarial, and fresh-readback "
        "obligations before submitting. Target membership is admitted "
        "deterministically and is never submitted. An OPEN "
        "question_decision carries resolution_requirements; ANSWERED "
        "requires at least one claim or relationship and Span derives completion; "
        "NOT_APPLICABLE carries a basis and no result refs. A "
        "verification link is the claim; an execution record carries the "
        "run (command, exit status, observed revision/time) and takes its "
        "verified scope from that link, so never send a scope fingerprint."
    ),
    "locate": (
        "Read-only structural find, file outline, or target member "
        "listing (structural navigation). SYMBOL requires query and accepts an "
        "optional target scope; match EXACT resolves an exact locator to "
        "its declaration/name and never returns partial hits, while "
        "CONTAINS returns substring matches in provider order. "
        "FILE_OUTLINE requires one file locator and takes no target scope "
        "or match mode. TARGET_MEMBERS requires the exact target scope and "
        "takes no query; it lists the same members the target frontier "
        "reconciles against. Resume a page by passing the returned page "
        "token unchanged to the same operation with the same arguments. "
        "Navigation evidence only — never a semantic claim. Procedure "
        "lives in the skill/runbook."
    ),
    "neighbors": (
        "Read-only bounded structural adjacency, upstream/downstream/"
        "both, with resumable traversal (structural navigation). Navigation "
        "evidence only — never a semantic claim."
    ),
}


def _request_classes() -> dict[str, type]:
    """The canonical request carrier for each tool (one mapping)."""
    return {
        "initialize_repository": ops.SemanticInitializeRepositoryRequest,
        "initialize_target": ops.SemanticInitializeTargetRequest,
        "explain": ops.SemanticExplainRequest,
        "impact": ops.SemanticImpactRequest,
        "trace": ops.SemanticTraceRequest,
        "authority": ops.SemanticAuthorityRequest,
        "status": ops.SemanticStatusRequest,
        "refresh": ops.SemanticRefreshRequest,
        "submit_interpretation": ops.SemanticSubmitInterpretationRequest,
        "locate": ops.SemanticStructuralLocateRequest,
        "neighbors": ops.SemanticStructuralNeighborsRequest,
    }


def _mapping(value: object) -> dict[str, object]:
    """One JSON-schema object node, or an empty node when absent."""
    return dict(value) if isinstance(value, dict) else {}


def _strings(value: object) -> list[str]:
    """One JSON-schema string array, or no entries when absent."""
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]


def _with_transport_fields(tool: str, generated: dict[str, object]) -> None:
    """Add transport-owned routing fields and decoder-equal defaults.

    Submit carries ``repository_id`` as routing only (its canonical carrier
    lacks it). Bounds are never required at the boundary: omitted bounds
    decode to the service default, so the schema advertises that exact
    default. The target projection carries its nullability through ``$ref``;
    only the use site that rejects an empty exact target adds ``minProperties``.
    """
    if tool == "submit_interpretation":
        props = _mapping(generated.get("properties"))
        props["repository_id"] = {"type": "string"}
        generated["properties"] = props
        required = _strings(generated.get("required"))
        if "repository_id" not in required:
            required.append("repository_id")
        generated["required"] = sorted(required)
    props = _mapping(generated.get("properties"))
    if "bounds" in props:
        bound_prop = _mapping(props["bounds"])
        bound_default = m.to_canonical(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds
        )
        if isinstance(bound_default, dict):
            # Ingress forbids the tag at a sole QueryBounds position. The
            # advertised default must be copy-paste valid.
            bound_default = {k: v for k, v in bound_default.items() if k != "$type"}
        bound_prop["default"] = bound_default
        props["bounds"] = bound_prop
        generated["properties"] = props
        generated["required"] = sorted(
            item for item in _strings(generated.get("required")) if item != "bounds"
        )
    if tool == "initialize_target":
        properties = _mapping(generated["properties"])
        target_prop = _mapping(properties["target"])
        target_prop["minProperties"] = 1
        properties["target"] = target_prop
        generated["properties"] = properties


def _claim_definitions() -> tuple[str, ...]:
    return (
        "CandidateSemanticClaim",
        "CandidateSemanticClaim__tag",
        "SemanticClaim",
        "SemanticClaim__tag",
    )


def _with_claim_value_unions(generated: dict[str, object]) -> None:
    """Make each claim definition reject a mismatched kind/value pair.

    The canonical projection already derives the item schemas; this adds the
    kind-gated value alternatives and states the mapping in prose. No second
    contract is copied here.
    """
    definitions = generated.get("$defs")
    if not isinstance(definitions, dict):
        return
    claim_defs = _claim_definitions()
    for claim_def in claim_defs:
        definition = definitions.get(claim_def)
        if not isinstance(definition, dict):
            continue
        branches = []
        for kind in sorted(m.CLAIM_VALUE_TYPE, key=lambda k: k.value):
            value_cls = m.CLAIM_VALUE_TYPE[kind]
            branches.append(
                {
                    "if": {
                        "properties": {"kind": {"const": kind.value}},
                        "required": ["kind"],
                    },
                    "then": {
                        "properties": {
                            "value": {"$ref": f"#/$defs/{value_cls.__name__}__tag"}
                        },
                    },
                }
            )
        definition = dict(definition)
        existing_allof = definition.get("allOf")
        definition["allOf"] = (
            list(existing_allof) if isinstance(existing_allof, list) else []
        ) + branches
        definitions[claim_def] = definition
    kind_map = "; ".join(
        f"{kind.value}={value_cls.__name__}"
        for kind, value_cls in sorted(
            m.CLAIM_VALUE_TYPE.items(), key=lambda kv: kv[0].value
        )
    )
    mapping = f"Kind/value classes: {kind_map}."
    for claim_def in claim_defs:
        definition = definitions.get(claim_def)
        if not isinstance(definition, dict):
            continue
        props = dict(definition.get("properties", {}))
        value = props.get("value")
        if not isinstance(value, dict):
            continue
        value = dict(value)
        existing = value.get("description")
        value["description"] = f"{existing} {mapping}" if existing else mapping
        props["value"] = value
        definition = dict(definition)
        definition["properties"] = props
        required = set(definition.get("required", []))
        # Validation requires a run-bound subject and a value compatible with
        # the kind; advertise both rather than letting the agent rely on unset
        # defaults.
        required.update(("subject", "value"))
        definition["required"] = sorted(required)
        definitions[claim_def] = definition
    for kind, value_cls in m.CLAIM_VALUE_TYPE.items():
        for value_name in (value_cls.__name__, f"{value_cls.__name__}__tag"):
            value_def = definitions.get(value_name)
            if not isinstance(value_def, dict):
                continue
            value_def = dict(value_def)
            value_def["description"] = f"Claim value for kind {kind.value}."
            definitions[value_name] = value_def
    generated["$defs"] = definitions


def _with_question_guidance(generated: dict[str, object]) -> None:
    """State the reuse-only rule on proposed target questions."""
    definitions = generated.get("$defs")
    if not isinstance(definitions, dict):
        return
    for result_def in (
        "SemanticInterpretationResult",
        "SemanticInterpretationResult__tag",
    ):
        definition = definitions.get(result_def)
        if not isinstance(definition, dict):
            continue
        props = dict(definition.get("properties", {}))
        proposed = props.get("proposed_target_questions")
        if not isinstance(proposed, dict):
            continue
        proposed = dict(proposed)
        proposed["description"] = (
            "Reuse only: every scope root and subject must already be "
            "persisted. New areas receive a service-owned PENDING CQ-01 "
            "seed; do not propose a new question here."
        )
        props["proposed_target_questions"] = proposed
        definition = dict(definition)
        definition["properties"] = props
        definitions[result_def] = definition
    generated["$defs"] = definitions


def _generated_tool_schemas() -> dict[str, dict[str, object]]:
    """Generate input schemas from canonical dataclasses ([design note I](docs/design-references.md#i) S3).

    Uses the same dataclasses and enums used by canonical decoding, retaining
    the canonical decoder as the only ingress parser. A generated schema is a
    projection, not a second domain contract. Top-level transport requests
    omit the carrier tag; nested carriers retain theirs. Only the reachable
    definition closure per operation is emitted.
    """
    from span.core import schema as _schema

    out: dict[str, dict] = {}
    for tool, cls in _request_classes().items():
        # Fail fast: schema projection is the advertised ingress contract. A
        # generation failure is a programming defect and must break the build,
        # never serve a degraded schema.
        generated = _schema.schema_for_request(cls, description=TOOL_DESCRIPTIONS[tool])
        _with_transport_fields(tool, generated)
        _with_claim_value_unions(generated)
        _with_question_guidance(generated)
        out[tool] = generated
    return out


TOOL_SCHEMAS: dict[str, dict] = _generated_tool_schemas()


TOOL_OUTPUT_TYPES: dict[str, object] = {
    "initialize_repository": ops.SemanticInitializeRepositoryResult,
    "initialize_target": m.SemanticAnswer | PendingInterpretation,
    "explain": m.SemanticAnswer | PendingInterpretation,
    "impact": m.SemanticAnswer | PendingInterpretation,
    "trace": m.SemanticAnswer | PendingInterpretation,
    "authority": m.SemanticAnswer | PendingInterpretation,
    "status": m.SemanticAnswer | m.HookStatusNotice,
    "refresh": m.SemanticAnswer | PendingInterpretation,
    "submit_interpretation": m.SemanticAnswer | PendingInterpretation,
    "locate": m.StructuralLocateResult,
    "neighbors": m.StructuralNeighborsResult,
}


TOOL_OUTPUT_SCHEMAS: dict[str, dict] = {
    name: _schema.schema_for_result(result_type)
    for name, result_type in TOOL_OUTPUT_TYPES.items()
}


TOOL_NAMES: tuple[str, ...] = (
    "initialize_repository",
    "initialize_target",
    "explain",
    "impact",
    "trace",
    "authority",
    "status",
    "refresh",
    "submit_interpretation",
    "locate",
    "neighbors",
)


_REQUEST_CLASS: dict[str, type] = {
    "initialize_target": ops.SemanticInitializeTargetRequest,
    "explain": ops.SemanticExplainRequest,
    "impact": ops.SemanticImpactRequest,
    "trace": ops.SemanticTraceRequest,
    "authority": ops.SemanticAuthorityRequest,
    "status": ops.SemanticStatusRequest,
    "refresh": ops.SemanticRefreshRequest,
    "submit_interpretation": ops.SemanticSubmitInterpretationRequest,
    "locate": ops.SemanticStructuralLocateRequest,
    "neighbors": ops.SemanticStructuralNeighborsRequest,
}
