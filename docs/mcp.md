# MCP reference (plan Phase 4.2–4.4; Addendum E correction over B–D)

Thin transport over stdio (`span-mcp --data-dir DIR
[--repo graft:/path ...]`). Exactly twelve tools, one per canonical
operation: `initialize_repository`, `initialize_target`, `explain`,
`impact`, `trace`, `authority`, `status`,
`refresh`, `submit_interpretation`, `reissue_interpretation`,
`locate`, and `neighbors` (Addendum F: read-only structural navigation
served by Span itself; no separate structural MCP exists).
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
notice and does not return the repository inventory. ACT-D-10 is
implemented in source; D-ACCEPT-08 is the installed-runtime verification
gate; until it passes for the deployed revision, readiness-only repository
status is an identified activation gap rather than
evidence of empty semantic state.

## Worked exchange (schematic)

One complete target campaign over the twelve tools (exact carriers in
`tests/acceptance/test_addendum_e_acceptance.py`; full procedure in
`docs/onboarding-runbook.md`):

1. `initialize_repository` once per repository (dedicated setup session) →
   `READY` operational status. Storage readiness only.
2. `initialize_target` with the exact `EvidenceScope` and objective →
   deterministic `TargetId` plus a `PendingInterpretation` carrying one
   `target_inventory_item` (`question=None`: mapping work, not a semantic
   question).
3. The host maps that member (assign to area, evidence-backed exclusion,
   or unresolved mapping) and calls `submit_interpretation` with the typed
   result → the next `PendingInterpretation`, until every inventory member
   is accounted for.
4. `initialize_target` then yields `PENDING` semantic questions per
   admitted area; the host examines each slice with its own model and
   submits `ANSWERED`/`OPEN`/`NOT_APPLICABLE`/`PENDING` coverage until an
   answer returns.
5. `status` with `target=TargetId` → `StatusContent` with
   `target_association` and `target_disposition` (`INCOMPLETE` while work
   remains; `CURRENT` only when every member is accounted, every area has
   terminal coverage, and all dependencies are current and verifiable).
6. Fresh session, no host memory: `status` with `target=TargetId`, then
   exact-area `explain`/`trace`/`authority` on the returned `SubjectId`s.

## Structural-provider boundary

Span reads the existing machine-readable Graft index at
`<target>/graft/.graph/wiring.json`. It never invokes `graft build`, creates
`graft/`, or generates Graft Markdown cards. A missing or invalid index is a
fail-closed installation/provider error; the offline `graft build` step must
produce the index before Span installation. Span stores and continuations live
outside the target in the configured data directory; no Span path writes
target artifacts (per-target plugin and AGENTS.md deployment are removed).
There is no graft MCP server: structural navigation (`locate` for find/
outline/member listing, `neighbors` for bounded adjacency) is served by
Span itself under Addendum F, with two-tier freshness (entry verification
plus scope coverage) and version-bound pagination. The onboarding preflight
is index-presence plus the read-only artifact census recorded in the
receipt and acceptance evidence. Exact onboarding path:
`docs/onboarding-runbook.md` and Addendum E §4A.

Migration from a pre-F install (one time, operator): the installer
removes `graft` entries from opencode host configs and attempts
`codex mcp remove graft`, both reported in the receipt (a `manual`
codex status means the operator finishes that removal by hand).
Removing configuration never stops an already-running graft server:
stop any such process out of band before relying on sole-MCP
operation. There are no Span-owned graft writers to disable — no
Span path builds, invokes, or writes through graft; the offline
`graft build` prerequisite stays a manual operator step performed
before installation.

## Operation intents and selection (Addendum G §4.7)

Twelve operations, retained because their contracts differ. Grouped by
agent intent; setup is separate from ordinary queries:

- Setup: `initialize_repository` (dedicated setup session, storage
  readiness only; never semantic completion).
- Structural discovery: `locate` (file, symbol, or member list),
  `neighbors` (structural callers, callees, adjacency as evidence).
- Semantic investigation: `explain` (what a subject does),
  `authority` (what governs it), `trace` (established
  producer-to-consumer semantics, boundaries, lifecycle).
- Proposed-change assessment: `impact` (needs `change_kind`,
  `change_description`, and `affected_assertions` naming established
  assertions).
- State inspection: `status` (`NORMAL` repository or exact-target
  coverage; `HOOK_FAST` event-local notice only, never inventory).
- Knowledge maintenance: `initialize_target` (exact `EvidenceScope`
  plus user-directed objective; admits a campaign), `refresh` (scoped
  `SubjectSelector` or `EvidenceScope`; never repo-wide without
  enumeration).
- Interpretation exchange: `submit_interpretation`
  (`continuation` plus typed result) versus `reissue_interpretation`
  (`continuation` only, expired or lost, once).

Selection rules: need a file, symbol, or member list → `locate`; need
structural adjacency → `neighbors`; need established semantics →
`trace`; need behavior → `explain`; need governance → `authority`;
need change consequences → `impact`. Structural adjacency is evidence,
never a semantic trace. `status` never triggers `refresh`. No generic
router exists; apparent overlap is resolved by these rules.

## Error recovery (Addendum G §4.1)

`unknown_repository` lists the sorted registered ids. Bounds rejection
names the received value, the maximum, and the omission default.
`page_token` (`pg:*`) versus `continuation` (`cont-*`) misuse names both
mechanisms. Campaign status under `HOOK_FAST` requires `NORMAL`.
Null `refresh` names the scoped selector or scope plus `status`.
Stale listing continuations name the new version and direct restart from
page one. Canonical decode failures carry dotted field paths with
indices. Validation failures name `collection[index] (key=...)` and keep
whole-unit atomic rejection.

## Freshness transparency (Addendum G §4.2)

Structural pages carry `coverage` plus `coverage_detail` (closed tokens:
`clean-verified`, `dirty-tree`, `index-older-than-head`,
`touched-file-mismatch`, `unverifiable-file`, `non-git-tree`,
`injected-index`). Missing or unparseable indexes fail closed with no
report. Repository `status` orders its current page deterministically
and guarantees every non-current repository entry carries an actionable
canonical requirement; campaign `UNASSESSED`/`UNVERIFIABLE` paths keep
their designed responses. `UNVERIFIED` empty results prove nothing.

## Boundaries

No semantic rule lives in transport: descriptions are
capability-oriented; skill/hook guidance lives outside the server.
Filesystem skill distribution is canonical; MCP Skills-extension
exposure is deferred until a proven consumer exists.
