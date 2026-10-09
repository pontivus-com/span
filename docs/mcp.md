# MCP reference (plan Phase 4.2–4.4; Addendum E correction over B–D)

Thin transport over stdio (`span-mcp --data-dir DIR
[--repo graft:/path ...]`). Exactly ten tools, one per canonical
operation: `initialize_repository`, `initialize_target`, `explain`,
`impact`, `trace`, `authority`, `status`,
`refresh`, `submit_interpretation`, and `reissue_interpretation`.
`initialize_target` accepts an exact `EvidenceScope` and user objective,
then returns the next typed interpretation unit with the exact boundary and
its current structural anchor carried separately. Each submission advances
that bounded candidate frontier; Span never invokes a model.

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

## Status reporting modes

Normal `status(target=None)` is the repository-level Point 4 report. It
returns the existing canonical answer envelope with a bounded, read-only
projection of persisted semantic coverage: covered/current knowledge,
`PENDING`/`OPEN` or otherwise incomplete work, stale/unverifiable items,
unassessed semantic items in the returned frontier, and explicit bounds,
pagination, or outstanding scope. It does not enumerate structural
subjects, invoke interpretation, write state, or claim repository
completeness.

Normal `status` with an exact target returns the same coverage semantics
narrowed to that target. `HOOK_FAST` remains a compact readiness/event
notice and does not return the repository inventory. ACT-D-10/D-ACCEPT-08
is the implementation and installed-runtime verification gate; until it
passes, readiness-only repository status is an identified gap rather than
evidence of empty semantic state.

## Structural-provider boundary

Span reads the existing machine-readable Graft index at
`<target>/graft/.graph/wiring.json`. It never invokes `graft build`, creates
`graft/`, or generates Graft Markdown cards. A missing or invalid index is a
fail-closed installation/provider error; the independent Graft workflow must
prepare the index before Span installation. Span stores and continuations live
outside the target in the configured data directory; no Span path writes
target artifacts. Onboarding preflight must fail closed unless independent
Graft activity is disabled or demonstrably read-only for the run, recorded in
the receipt and acceptance evidence with a target artifact snapshot proving
only the data store changed. Exact onboarding path:
`docs/onboarding-runbook.md` and Addendum E §4A.

## Boundaries

No semantic rule lives in transport: descriptions are
capability-oriented; skill/hook guidance lives outside the server.
Filesystem skill distribution is canonical; MCP Skills-extension
exposure is deferred until a proven consumer exists.
