"""MCP transport adapter (plan Phase 4.2–4.4). Transport only.

Maps the canonical public operations (§11.3) to MCP tools
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
from span.core import schema as _schema
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import (
    InterpretationUnavailable,
)
from span.ports.store import SemanticStore
from span.ports.structural import StaleContinuationError
from span.ports.structural import StructuralSource
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.agent_exchange.continuations import ContinuationStore
from span import service as ops

try:  # Shell-owned provider-error mapping (I S1 §5.1): graft failure maps
    # to the existing unavailable envelope. The generic port gains no new
    # result and the service catches no shell-specific exception.
    from span.shell.structural.graft import GraftUnavailableError
except Exception:  # pragma: no cover - import-time fallback
    GraftUnavailableError = None  # type: ignore[assignment,misc]

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


def _canonical(description: str, *, nullable: bool = False) -> dict:
    return {
        "type": ["object", "null"] if nullable else "object",
        "description": (
            description + " Canonical JSON: the exact canonical "
            "encoding of the named carrier, including its $type tag."
        ),
    }


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
        "SubjectSelector; unassessed work uses a question-local explain; "
        "pending question work continues only through the continuation "
        "returned by the suspending operation. Exact targets report "
        "detailed freshness; HOOK_FAST "
        "returns a compact notice only: event-local scope, never "
        "repository inventory, so READY 0/0 never means clean."
    ),
    "refresh": (
        "Explicitly reinterpret a scoped semantic target. For stale "
        "work, use an exact SubjectSelector or EvidenceScope. Challenging "
        "an otherwise CURRENT subject requires stale_only=false with an "
        "exact SubjectSelector. Never automatic."
    ),
    "submit_interpretation": (
        "Submit the host-produced typed interpretation result for a "
        "pending continuation; the agent performs interpretation, Span "
        "validates and atomically persists it. Returns the answer, or "
        "the next pending unit while frontiers remain. Pending tasks use "
        "the SA_1_7_V1 interpretation profile; satisfy its evidence, "
        "scope, typed-disposition, adversarial, and fresh-readback "
        "obligations before submitting. Each target inventory account "
        "carries exactly one outcome: assigned_area_subjects, "
        "exclusion_basis, or resolution_requirements. An OPEN "
        "question_decision carries resolution_requirements; ANSWERED "
        "requires validated material and Span derives completion; "
        "NOT_APPLICABLE carries a basis and no result refs."
    ),
    "locate": (
        "Read-only structural find, file outline, or target member "
        "listing (Addendum F). SYMBOL requires query and accepts an "
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
        "both, with resumable traversal (Addendum F). Navigation "
        "evidence only — never a semantic claim."
    ),
}

def _generated_tool_schemas() -> dict[str, dict]:
    """Generate input schemas from canonical dataclasses (Addendum I S3).

    Uses the same dataclasses and enums used by canonical decoding.
    Referenced definitions for nested types and tagged unions. Retains
    the canonical decoder as the only ingress parser. A generated
    schema is a projection, not a second domain contract. Top-level
    transport requests omit the carrier tag; nested carriers retain
    theirs. Only the reachable definition closure per operation.
    Defaults advertised equal canonical decoder defaults, including
    omitted bounds. repository_id for submit remains a transport
    routing field.
    """
    from span.core import schema as _schema

    mapping: dict[str, type] = {
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
    out: dict[str, dict] = {}
    for tool, cls in mapping.items():
        # Fail fast: schema projection is the advertised ingress
        # contract. A generation failure is a programming defect and
        # must break the build, never serve a degraded schema.
        generated = _schema.schema_for_request(
            cls, description=TOOL_DESCRIPTIONS[tool]
        )
        # Transport-owned routing fields explicitly without duplicating
        # semantic request types: submit carries repository_id as
        # routing only (its canonical carrier lacks it).
        if tool == "submit_interpretation":
            props = dict(generated.get("properties", {}))
            props["repository_id"] = {"type": "string"}
            generated["properties"] = props
            required = list(generated.get("required", []))
            if "repository_id" not in required:
                required.append("repository_id")
            generated["required"] = sorted(required)
        # Bounds are never required at the boundary: omitted bounds
        # decode to the service default (see decode_request). Advertise
        # that exact decoder default so schema and decoder agree (§5.3).
        props = dict(generated.get("properties", {}))
        if "bounds" in props:
            bound_prop = dict(props["bounds"])
            bound_default = m.to_canonical(
                DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds
            )
            if isinstance(bound_default, dict):
                # Ingress forbids the tag at a sole QueryBounds position.
                # The advertised default must be copy-paste valid.
                bound_default = {
                    k: v for k, v in bound_default.items() if k != "$type"
                }
            bound_prop["default"] = bound_default
            props["bounds"] = bound_prop
            generated["properties"] = props
            generated["required"] = sorted(
                r for r in generated.get("required", []) if r != "bounds"
            )
        # The target projection already carries its nullability through
        # `$ref`/`anyOf`; no extra type marker is added (a marker would
        # render as a meaningless intersection in the consumer).
        if tool == "initialize_target":
            # The operation rejects an exact target with neither paths
            # nor evidence. Advertise the non-empty object shape at this
            # use site only; the shared EvidenceScope carrier is used
            # where an empty scope is valid.
            target_prop = dict(generated["properties"]["target"])
            target_prop["minProperties"] = 1
            generated["properties"] = dict(generated["properties"])
            generated["properties"]["target"] = target_prop
        # affected_assertions item schemas are generated by the canonical
        # projection (require-wrapped ClaimRef/RelationshipRef union); no
        # shell-side override remains (J-8: schema == decoder grammar).
        # Claim kind/value compatibility reuses CLAIM_VALUE_TYPE (§5.3):
        # each claim definition gains kind-gated value alternatives so
        # the schema rejects the mismatched pairs the canonical
        # constructor would reject. No mapping is copied here.
        _defs = generated.get("$defs")
        if isinstance(_defs, dict):
            for _claim_def in (
                "CandidateSemanticClaim",
                "CandidateSemanticClaim__tag",
                "SemanticClaim",
                "SemanticClaim__tag",
            ):
                _definition = _defs.get(_claim_def)
                if not isinstance(_definition, dict):
                    continue
                _branches = []
                for _kind in sorted(
                    m.CLAIM_VALUE_TYPE, key=lambda k: k.value
                ):
                    _value_cls = m.CLAIM_VALUE_TYPE[_kind]
                    _branches.append({
                        "if": {
                            "properties": {
                                "kind": {"const": _kind.value}
                            },
                            "required": ["kind"],
                        },
                        "then": {
                            "properties": {
                                "value": {
                                    "$ref": (
                                        "#/$defs/"
                                        f"{_value_cls.__name__}__tag"
                                    )
                                }
                            },
                        },
                    })
                _definition = dict(_definition)
                _existing_allof = _definition.get("allOf")
                _definition["allOf"] = (
                    list(_existing_allof)
                    if isinstance(_existing_allof, list)
                    else []
                ) + _branches
                _defs[_claim_def] = _definition
            _kind_map = "; ".join(
                f"{kind.value}={value_cls.__name__}"
                for kind, value_cls in sorted(
                    m.CLAIM_VALUE_TYPE.items(), key=lambda kv: kv[0].value
                )
            )
            for _claim_def in (
                "CandidateSemanticClaim",
                "CandidateSemanticClaim__tag",
                "SemanticClaim",
                "SemanticClaim__tag",
            ):
                _definition = _defs.get(_claim_def)
                if not isinstance(_definition, dict):
                    continue
                _props = dict(_definition.get("properties", {}))
                _value = _props.get("value")
                if not isinstance(_value, dict):
                    continue
                _value = dict(_value)
                _existing = _value.get("description")
                _mapping = f"Kind/value classes: {_kind_map}."
                _value["description"] = (
                    f"{_existing} {_mapping}" if _existing else _mapping
                )
                _props["value"] = _value
                _definition = dict(_definition)
                _definition["properties"] = _props
                _required = set(_definition.get("required", []))
                # Validation requires a run-bound subject and a value
                # compatible with the kind; advertise both as required
                # rather than letting the agent rely on unset defaults.
                _required.update(("subject", "value"))
                _definition["required"] = sorted(_required)
                _defs[_claim_def] = _definition
            for _kind, _value_cls in m.CLAIM_VALUE_TYPE.items():
                for _value_name in (
                    _value_cls.__name__,
                    f"{_value_cls.__name__}__tag",
                ):
                    _value_def = _defs.get(_value_name)
                    if not isinstance(_value_def, dict):
                        continue
                    _value_def = dict(_value_def)
                    _value_def["description"] = (
                        f"Claim value for kind {_kind.value}."
                    )
                    _defs[_value_name] = _value_def
            for _result_def in (
                "SemanticInterpretationResult",
                "SemanticInterpretationResult__tag",
            ):
                _definition = _defs.get(_result_def)
                if not isinstance(_definition, dict):
                    continue
                _props = dict(_definition.get("properties", {}))
                _ptq = _props.get("proposed_target_questions")
                if not isinstance(_ptq, dict):
                    continue
                _ptq = dict(_ptq)
                _ptq["description"] = (
                    "Reuse only: every scope root and subject must already "
                    "be persisted. New areas receive a service-owned "
                    "PENDING CQ-01 seed; do not propose a new question here."
                )
                _props["proposed_target_questions"] = _ptq
                _definition = dict(_definition)
                _definition["properties"] = _props
                _defs[_result_def] = _definition
            generated["$defs"] = _defs
        out[tool] = generated
    return out


TOOL_SCHEMAS: dict[str, dict] = _generated_tool_schemas()

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
        return _schema.from_wire(
            ops.SemanticInitializeRepositoryRequest, arguments
        )
    except (m.CanonicalDecodeError, ValueError) as exc:
        raise ValueError(
            f"invalid initialize_repository arguments: {exc}"
        ) from None


def encode_result(result: object) -> str:
    """Deterministic compact JSON for the discriminated result (S6.4/S7).

    Pending units carry unit-specific content plus the immutable
    interpretation profile (J-9); the static SA handbook, full default
    vocabularies, default bounds, and base task-brief rules are omitted
    when they equal the profile defaults.
    """
    compact = _schema.to_wire_root(type(result), m.to_canonical(result))
    if isinstance(compact, dict) and compact.get("$type") == (
        "PendingInterpretation"
    ):
        compact = _omit_static_profile(compact)
    return _json.dumps(compact, sort_keys=True)


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
        m.to_canonical(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds
        ),
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
        dynamic_rules = submission_rules[len(base_rules):]
        if dynamic_rules:
            brief["submission_rules"] = dynamic_rules
        else:
            brief.pop("submission_rules")
    return brief


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
            registered = sorted(self.contexts)
            raise ValueError(
                f"unknown repository: {repository_id!r}; "
                f"registered: {registered}"
            ) from None

    def dispatch(
        self, tool_name: str, arguments: dict
    ) -> ToolResult:
        """Invoke one canonical operation; transport errors stay typed."""
        if tool_name == "initialize_repository":
            return self._dispatch_init(arguments)
        if tool_name not in _REQUEST_CLASS:
            return _error("unknown_tool", f"unknown tool: {tool_name}")
        try:
            request = decode_request(tool_name, arguments)
        except ValueError as exc:
            return _error("ingress", str(exc))
        if tool_name == "submit_interpretation":
            repository_id = arguments.get("repository_id")
            continuation = arguments.get("continuation")
            if isinstance(continuation, str) and continuation.startswith(
                ("pg:", "pgq:", "pgv:", "pgn:")
            ):
                return _error(
                    "ingress",
                    "a page token was supplied where an interpretation "
                    "continuation was expected; pass the continuation "
                    "returned by the operation that suspended",
                )
        else:
            repository_id = request.repository_id  # type: ignore[union-attr]
            page_token = arguments.get("page_token")
            if isinstance(page_token, str) and page_token.startswith(
                ("cont-", "cont")
            ):
                return _error(
                    "ingress",
                    "an interpretation continuation was supplied where a "
                    "page token was expected; pass the page token returned "
                    "by the operation being paged",
                )
        if not isinstance(repository_id, str) or not repository_id:
            return _error("ingress", "repository_id must be non-empty")
        try:
            context = self._context(repository_id)
        except ValueError as exc:
            return _error("unknown_repository", str(exc))
        try:
            if tool_name == "explain":
                result = ops.explain(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "initialize_target":
                result = ops.initialize_target(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "impact":
                result = ops.impact(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "trace":
                result = ops.trace(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "authority":
                result = ops.authority(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "status":
                result = ops.status(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "refresh":
                result = ops.refresh(
                    request, structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                    authority_seeds=context.authority_seeds,
                )
            elif tool_name == "submit_interpretation":
                result = ops.submit_interpretation(
                    request.continuation,  # type: ignore[union-attr]
                    request.result,  # type: ignore[union-attr]
                    structural=context.structural,
                    evidence=context.evidence, store=context.store,
                    continuations=context.continuations,
                )
            elif tool_name == "locate":
                result = ops.locate(
                    request,  # type: ignore[arg-type]
                    structural=context.structural,
                    evidence=context.evidence, store=context.store,
                )
            elif tool_name == "neighbors":
                result = ops.neighbors(
                    request,  # type: ignore[arg-type]
                    structural=context.structural,
                    store=context.store,
                )
            else:  # Unreachable: guarded above.
                return _error("unknown_tool", f"unknown tool: {tool_name}")
        except InterpretationUnavailable as exc:
            return _error("unavailable", str(exc))
        except StaleContinuationError as exc:
            return _error(
                "stale_continuation",
                f"{exc}; restart the listing from page one with "
                f"page_token null",
            )
        except ops.InterpretationUnitRejected as exc:
            return _error("validation", "; ".join(exc.diagnostics) + "; correct the result and resubmit using the same continuation.")
        except (ops.AuthorityTargetError, ops.StatusTargetError,
                ops.RefreshScopeError, ValueError) as exc:
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
                "initialize_repository needs a provisioned "
                "server data directory",
            )
        try:
            context, result = self.provisioner(request)
        except ValueError as exc:
            return _error("rejected", str(exc))
        self.register(result.repository_id, context)
        return ToolResult(content=encode_result(result))
