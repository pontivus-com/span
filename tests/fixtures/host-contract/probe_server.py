"""Test-only MCP server exposing the 0.9.0 candidate record grammar.

This is the G-0 probe's local server. It is not a shipped Span operation and
must not be installed as one. It uses the canonical N-01 carriers and the
normal generated schema/wire codec; a host that cannot deliver this grammar
is evidence against the candidate contract, not a reason to add a second
host-specific model.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import fcntl
import json
import os
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from span.core import model as m
from span.core.identity import payload_digest, record_content_digest
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    apply_update,
    build_receipt,
    create_understanding,
    receipt_decision,
)
from span.core.schema import (
    from_wire,
    schema_for_request,
    schema_for_result,
    to_wire_root,
)
from span.core.schema import record_wire as rw

__all__ = ["build_server", "main"]

LOG_PATH = os.environ.get("SPAN_HOST_CONTRACT_LOG", "")
STATE_PATH = os.environ.get("SPAN_HOST_CONTRACT_STATE", "")
INLINE_SCHEMA = os.environ.get("SPAN_HOST_CONTRACT_INLINE_SCHEMA", "") == "1"
REQUIRE_SERVER_CONTEXT = (
    os.environ.get("SPAN_HOST_CONTRACT_REQUIRE_SERVER_CONTEXT", "") == "1"
)
DROP_START_REQUEST = os.environ.get("SPAN_HOST_CONTRACT_DROP_START_REQUEST", "")
DROP_CREATE_SUBMISSION = os.environ.get("SPAN_HOST_CONTRACT_DROP_CREATE_SUBMISSION", "")
CRASH_START_REQUEST = os.environ.get("SPAN_HOST_CONTRACT_CRASH_START_REQUEST", "")
CRASH_CREATE_SUBMISSION = os.environ.get(
    "SPAN_HOST_CONTRACT_CRASH_CREATE_SUBMISSION", ""
)
SCOPE_PATH = os.environ.get("SPAN_HOST_CONTRACT_SCOPE", "src/probe.py")
SERVER_VERSION = "0.9.0-probe"

_CONTEXTS: dict[str, m.InvestigationContext] = {}
_REQUESTS: dict[tuple[str, str], str] = {}
_DROPS: set[str] = set()
_STATE: dict[
    str,
    tuple[m.Understanding, m.UnderstandingVersion, tuple[m.ConclusionRevision, ...]],
] = {}
_RECEIPTS: dict[tuple[str, str, str], m.RecordReceipt] = {}


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _log(event: dict[str, object]) -> None:
    if not LOG_PATH:
        return
    path = pathlib.Path(LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _receipt_key(identity: m.RecordingIdentity) -> tuple[str, str, str]:
    return (
        identity.repository_id,
        identity.context_id.value,
        identity.submission_id.value,
    )


def _context_for(identity: m.RecordingIdentity) -> m.InvestigationContext:
    key = identity.context_id.value
    existing = _CONTEXTS.get(key)
    if existing is not None:
        if existing.repository_id != identity.repository_id:
            raise RecordingValidationError("context belongs to another repository")
        return existing
    if REQUIRE_SERVER_CONTEXT:
        raise RecordingValidationError(
            "unknown server-issued context; call probe_start_context first"
        )
    now = _now()
    context = m.InvestigationContext(
        context_id=identity.context_id,
        repository_id=identity.repository_id,
        request_id=m.RequestId(f"probe-request:{key}"),
        request_digest=m.ContentDigest(f"sha256:probe:{key}"),
        origin=m.ContextOrigin.EVIDENCE_ONLY,
        state=m.ContextState.LIVE,
        scope=m.EvidenceScope(paths=(SCOPE_PATH,)),
        created_at=now,
        purpose="host-contract probe",
        expires_at=now + datetime.timedelta(hours=1),
    )
    _CONTEXTS[key] = context
    return context


def _replay_or_none(
    identity: m.RecordingIdentity,
    digest: m.ContentDigest,
) -> m.RecordReceipt | None:
    existing = _RECEIPTS.get(_receipt_key(identity))
    decision = receipt_decision(existing, identity, digest)
    if decision.kind is m.ReceiptDecisionKind.REPLAY:
        return decision.receipt
    if decision.kind is m.ReceiptDecisionKind.CONFLICT:
        raise RecordingConflict(decision.reason)
    return None


def _state_document() -> dict[str, object]:
    return {
        "contexts": [m.to_canonical(item) for item in _CONTEXTS.values()],
        "receipts": [m.to_canonical(item) for item in _RECEIPTS.values()],
        "drops": sorted(_DROPS),
        "requests": [
            {
                "repository_id": repository_id,
                "request_id": request_id,
                "context_id": context_id,
            }
            for (repository_id, request_id), context_id in _REQUESTS.items()
        ],
        "states": [
            {
                "understanding": m.to_canonical(understanding),
                "version": m.to_canonical(version),
                "conclusions": [m.to_canonical(item) for item in conclusions],
            }
            for understanding, version, conclusions in _STATE.values()
        ],
    }


def _load_state() -> None:
    _CONTEXTS.clear()
    _REQUESTS.clear()
    _DROPS.clear()
    _RECEIPTS.clear()
    _STATE.clear()
    if not STATE_PATH:
        return
    path = pathlib.Path(STATE_PATH)
    if not path.is_file():
        return
    document = json.loads(path.read_text(encoding="utf-8"))
    for item in document.get("contexts", []):
        context = m.from_canonical(m.InvestigationContext, item)
        _CONTEXTS[context.context_id.value] = context
    _DROPS.update(document.get("drops", []))
    for item in document.get("requests", []):
        _REQUESTS[(item["repository_id"], item["request_id"])] = item["context_id"]
    for item in document.get("receipts", []):
        receipt = m.from_canonical(m.RecordReceipt, item)
        _RECEIPTS[_receipt_key(receipt.identity)] = receipt
    for item in document.get("states", []):
        understanding = m.from_canonical(m.Understanding, item["understanding"])
        version = m.from_canonical(m.UnderstandingVersion, item["version"])
        conclusions = tuple(
            m.from_canonical(m.ConclusionRevision, value)
            for value in item["conclusions"]
        )
        _STATE[understanding.understanding_id.value] = (
            understanding,
            version,
            conclusions,
        )


def _save_state() -> None:
    if not STATE_PATH:
        return
    path = pathlib.Path(STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_state_document(), sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


@contextlib.contextmanager
def _locked_state():
    if not STATE_PATH:
        yield
        return
    path = pathlib.Path(STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / (path.name + ".lock")).open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _load_state()
        try:
            yield
        finally:
            _save_state()
            fcntl.flock(lock, fcntl.LOCK_UN)


def _start_context_unlocked(arguments: dict[str, object]) -> dict[str, object]:
    request = from_wire(m.StartContextRequest, arguments)
    digest = payload_digest(request)
    key = (request.repository_id, request.request_id.value)
    existing_id = _REQUESTS.get(key)
    if existing_id is not None:
        context = _CONTEXTS[existing_id]
        if context.request_digest != digest:
            raise RecordingConflict(
                "this request identity was already bound to different context content"
            )
        return to_wire_root(m.InvestigationContext, m.to_canonical(context))
    now = _now()
    context = m.InvestigationContext(
        context_id=m.InvestigationContextId(f"ctx-srv-{uuid.uuid4().hex}"),
        repository_id=request.repository_id,
        request_id=request.request_id,
        request_digest=digest,
        origin=(
            m.ContextOrigin.QUESTION
            if request.question is not None
            else m.ContextOrigin.EVIDENCE_ONLY
        ),
        state=m.ContextState.LIVE,
        scope=request.scope,
        created_at=now,
        question=request.question,
        purpose="host-contract probe",
        expires_at=now + datetime.timedelta(hours=1),
    )
    _CONTEXTS[context.context_id.value] = context
    _REQUESTS[key] = context.context_id.value
    if CRASH_START_REQUEST == request.request_id.value:
        _save_state()
        os._exit(17)
    drop_key = f"start:{request.request_id.value}"
    if DROP_START_REQUEST == request.request_id.value and drop_key not in _DROPS:
        _DROPS.add(drop_key)
        raise RecordingConflict("simulated lost response after context commit")
    return to_wire_root(m.InvestigationContext, m.to_canonical(context))


def _start_context(arguments: dict[str, object]) -> dict[str, object]:
    with _locked_state():
        return _start_context_unlocked(arguments)


def _create_domain(command: m.CreateUnderstandingCommand) -> dict[str, object]:
    digest = record_content_digest(command)
    replay = _replay_or_none(command.identity, digest)
    if replay is not None:
        return to_wire_root(m.RecordReceipt, m.to_canonical(replay))
    context = _context_for(command.identity)
    understanding_id = m.UnderstandingId(
        f"u:{command.identity.context_id.value}:{command.identity.submission_id.value}"
    )
    transition = create_understanding(understanding_id, command, context, _now())
    _STATE[understanding_id.value] = (
        transition.understanding,
        transition.new_version,
        transition.new_conclusions,
    )
    receipt = build_receipt(
        command.identity,
        digest,
        _now(),
        understanding=(understanding_id, transition.new_version.version),
    )
    _RECEIPTS[_receipt_key(command.identity)] = receipt
    if CRASH_CREATE_SUBMISSION == command.identity.submission_id.value:
        _save_state()
        os._exit(17)
    drop_key = f"create:{command.identity.submission_id.value}"
    if (
        DROP_CREATE_SUBMISSION == command.identity.submission_id.value
        and drop_key not in _DROPS
    ):
        _DROPS.add(drop_key)
        raise RecordingConflict("simulated lost response after create commit")
    return to_wire_root(m.RecordReceipt, m.to_canonical(receipt))


def _update_domain(command: m.UpdateUnderstandingCommand) -> dict[str, object]:
    digest = record_content_digest(command)
    replay = _replay_or_none(command.identity, digest)
    if replay is not None:
        return to_wire_root(m.RecordReceipt, m.to_canonical(replay))
    state = _STATE.get(command.understanding_id.value)
    if state is None:
        raise RecordingValidationError(
            f"probe has no current understanding {command.understanding_id.value}"
        )
    understanding, version, revisions = state
    transition = apply_update(
        understanding,
        version,
        revisions,
        command,
        _context_for(command.identity),
        _now(),
    )
    all_revisions = tuple(
        {
            (item.conclusion_id, item.revision): item
            for item in (*revisions, *transition.new_conclusions)
        }.values()
    )
    _STATE[command.understanding_id.value] = (
        transition.understanding,
        transition.new_version,
        all_revisions,
    )
    receipt = build_receipt(
        command.identity,
        digest,
        _now(),
        understanding=(command.understanding_id, transition.new_version.version),
    )
    _RECEIPTS[_receipt_key(command.identity)] = receipt
    return to_wire_root(m.RecordReceipt, m.to_canonical(receipt))


def _verification_domain(command: m.RecordVerificationCommand) -> dict[str, object]:
    digest = record_content_digest(command)
    replay = _replay_or_none(command.identity, digest)
    if replay is not None:
        return to_wire_root(m.RecordReceipt, m.to_canonical(replay))
    run_id = m.VerificationRunId(
        f"run:{command.identity.context_id.value}:{command.identity.submission_id.value}"
    )
    receipt = build_receipt(
        command.identity,
        digest,
        _now(),
        verification_run_id=run_id,
    )
    _RECEIPTS[_receipt_key(command.identity)] = receipt
    return to_wire_root(m.RecordReceipt, m.to_canonical(receipt))


def _create_unlocked(arguments: dict[str, object]) -> dict[str, object]:
    return _create_domain(from_wire(m.CreateUnderstandingCommand, arguments))


def _update_unlocked(arguments: dict[str, object]) -> dict[str, object]:
    return _update_domain(from_wire(m.UpdateUnderstandingCommand, arguments))


def _verification_unlocked(arguments: dict[str, object]) -> dict[str, object]:
    return _verification_domain(from_wire(m.RecordVerificationCommand, arguments))


def _wire_resolver(repository_id: str) -> rw.RecordWireResolver:
    def reference(value: str) -> m.EvidenceRef:
        return m.EvidenceRef(
            evidence_id=m.EvidenceId(value),
            repository_id=repository_id,
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator=value,
        )

    def authority(value: str) -> m.AuthorityBinding:
        return m.AuthorityBinding(
            evidence_ref=reference(value),
            authority_kind=m.AuthorityKind.OTHER,
            status=m.AuthorityStatus.ACCEPTED,
        )

    return rw.RecordWireResolver(reference=reference, authority=authority)


def _wire_create(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordCreateWire, arguments)
    with _locked_state():
        return _create_domain(
            rw.create_command(wire, _wire_resolver(wire.identity.repository_id))
        )


def _wire_update(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordUpdateWire, arguments)
    with _locked_state():
        return _update_domain(
            rw.update_command(wire, _wire_resolver(wire.identity.repository_id))
        )


def _wire_verification(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordVerificationWire, arguments)
    with _locked_state():
        return _verification_domain(rw.verification_command(wire))


def _wire_add(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordAddWire, arguments)
    with _locked_state():
        return _update_domain(
            rw.add_command(wire, _wire_resolver(wire.identity.repository_id))
        )


def _wire_confirm(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordConfirmWire, arguments)
    with _locked_state():
        return _update_domain(
            rw.confirm_command(wire, _wire_resolver(wire.identity.repository_id))
        )


def _wire_correct(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordCorrectWire, arguments)
    with _locked_state():
        return _update_domain(
            rw.correct_command(wire, _wire_resolver(wire.identity.repository_id))
        )


def _wire_replace(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordReplaceWire, arguments)
    with _locked_state():
        return _update_domain(
            rw.replace_command(wire, _wire_resolver(wire.identity.repository_id))
        )


def _wire_withdraw(arguments: dict[str, object]) -> dict[str, object]:
    wire = from_wire(rw.RecordWithdrawWire, arguments)
    with _locked_state():
        return _update_domain(
            rw.withdraw_command(wire, _wire_resolver(wire.identity.repository_id))
        )


def _create(arguments: dict[str, object]) -> dict[str, object]:
    with _locked_state():
        return _create_unlocked(arguments)


def _update(arguments: dict[str, object]) -> dict[str, object]:
    with _locked_state():
        return _update_unlocked(arguments)


def _verification(arguments: dict[str, object]) -> dict[str, object]:
    with _locked_state():
        return _verification_unlocked(arguments)


_TOOLS = (
    (
        "probe_start_context",
        "Start one server-issued investigation context.",
        m.StartContextRequest,
        _start_context,
    ),
    (
        "probe_record_create",
        "Create one understanding through the canonical reference-only wire.",
        rw.RecordCreateWire,
        _wire_create,
    ),
    (
        "probe_record_add",
        "Add one conclusion through the canonical reference-only wire.",
        rw.RecordAddWire,
        _wire_add,
    ),
    (
        "probe_record_confirm",
        "Confirm one conclusion through the canonical reference-only wire.",
        rw.RecordConfirmWire,
        _wire_confirm,
    ),
    (
        "probe_record_correct",
        "Correct one conclusion through the canonical reference-only wire.",
        rw.RecordCorrectWire,
        _wire_correct,
    ),
    (
        "probe_record_replace",
        "Replace one conclusion through the canonical reference-only wire.",
        rw.RecordReplaceWire,
        _wire_replace,
    ),
    (
        "probe_record_withdraw",
        "Withdraw one conclusion through the canonical reference-only wire.",
        rw.RecordWithdrawWire,
        _wire_withdraw,
    ),
    (
        "probe_record_verification",
        "Record one verification through the canonical reference-only wire.",
        rw.RecordVerificationWire,
        _wire_verification,
    ),
)


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


def _request_schema(root: type) -> dict:
    schema = schema_for_request(root)
    if not INLINE_SCHEMA:
        return schema
    return _inline_refs(schema, schema.get("$defs", {}), set())


def _result_schema(root: object) -> dict:
    schema = schema_for_result(root)
    if not INLINE_SCHEMA:
        return schema
    return _inline_refs(schema, schema.get("$defs", {}), set())


def _tool_specs() -> list[types.Tool]:
    return [
        types.Tool(
            name=name,
            description=description,
            inputSchema=_request_schema(root),
            outputSchema=_result_schema(
                m.InvestigationContext
                if name == "probe_start_context"
                else m.RecordReceipt
            ),
        )
        for name, description, root, _handler in _TOOLS
    ]


async def _list_tools(_context: object, _params: object) -> types.ListToolsResult:
    return types.ListToolsResult(tools=_tool_specs())


async def _call_tool(
    _context: object, params: types.CallToolRequestParams
) -> types.CallToolResult:
    arguments = params.arguments or {}
    handler = next(
        (item[3] for item in _TOOLS if item[0] == params.name),
        None,
    )
    if handler is None:
        return types.CallToolResult(
            content=[types.TextContent(text=f"unknown probe tool: {params.name}")],
            isError=True,
        )
    _log({"event": "call", "tool": params.name, "arguments": arguments})
    try:
        result = handler(arguments)
    except Exception as exc:  # noqa: BLE001 - probe returns failures as evidence
        _log(
            {
                "event": "error",
                "tool": params.name,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return types.CallToolResult(
            content=[types.TextContent(text=f"{type(exc).__name__}: {exc}")],
            isError=True,
        )
    _log({"event": "result", "tool": params.name, "result": result})
    return types.CallToolResult(
        content=[types.TextContent(text=json.dumps(result, sort_keys=True))],
        structuredContent=result,
        isError=False,
    )


def build_server() -> Server:
    return Server(
        "span-host-contract-probe",
        version=SERVER_VERSION,
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
