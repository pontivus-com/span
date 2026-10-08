# MCP reference (plan Phase 4.2–4.4; Addendum B)

Thin transport over stdio (`span-mcp --data-dir DIR
[--repo graft:/path ...]`). Exactly eight tools, one per canonical
operation: `initialize_repository`, `explain`,
`impact`, `trace`, `authority`, `status`,
`refresh`, `submit_interpretation`. `explain` accepts one optional
`establish_baseline` flag (default false) for a bounded root audit;
no ninth operation exists.

## Ingress

Each tool takes its canonical service request as canonical JSON
(without `$type`; complex fields carry their `$type`-tagged
encoding). `bounds` may be omitted for service defaults. Unknown
tools/fields/enums and missing required fields fail closed.
`submit_interpretation` additionally takes the routing key
`repository_id` (transport-level, never parsed as semantics).

## Egress

Deterministic canonical JSON of exactly what the service returned:
`SemanticAnswer`, `PendingInterpretation` (keep submitting until an
answer returns), `HookStatusNotice`, or the init result. Failures are
typed error envelopes (`unknown_tool`, `ingress`, `unknown_repository`,
`unavailable`, `validation`, `rejected`, `transport`) — never invented
semantics. A JSON ingress failure never consumes the continuation:
resubmit the corrected result under the same continuation.

## Boundaries

No semantic rule lives in transport: descriptions are
capability-oriented; skill/hook guidance lives outside the server.
Filesystem skill distribution is canonical; MCP Skills-extension
exposure is deferred until a proven consumer exists.
