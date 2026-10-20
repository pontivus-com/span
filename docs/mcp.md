# MCP reference (plan Phase 4.2–4.4; Addendum E correction over B–D)

Thin transport over stdio (`span-mcp --data-dir DIR
[--repo /path ...]`). Exactly twelve tools, one per canonical
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

Each tool takes its canonical service request as compact wire JSON.
`$type` is absent at statically unambiguous field positions and is
required only where a genuine multi-dataclass union needs a discriminator;
redundant tags are rejected. `bounds` may be omitted for service defaults.
Unknown
tools/fields/enums and missing required fields fail closed. One
ingress failure reports every shape fault it found, so a single
correction round suffices.
`submit_interpretation` additionally takes the routing key
`repository_id` (transport-level, never parsed as semantics).

## Egress

Deterministic canonical JSON of exactly what the service returned:
`SemanticAnswer`, `PendingInterpretation` (keep submitting until an
answer returns), `HookStatusNotice`, or the init result. Failures are
typed error envelopes (`unknown_tool`, `ingress`, `unknown_repository`,
`unavailable`, `validation`, `rejected`, `transport`,
`stale_continuation`) — never invented semantics. A stale structural
listing continuation (`stale_continuation`) names the new listing version
and directs a restart of that listing from page one with
`page_token: null`; no snapshot is persisted and no continuation is
recovered. A JSON ingress failure never consumes the continuation:
resubmit the corrected result under the same continuation. A semantic
validation rejection (`validation`) likewise retains the live
continuation: correct and resubmit under the same continuation. Only a
successful commit consumes it; repeating a successful submission is
rejected without duplicates (Addendum H §4).

## Repository discovery

`tools/list` appends the sorted registered canonical repository IDs to
repository-scoped tool descriptions at list time, so agents discover
identity before the first repository-scoped call. `initialize_repository`
also returns the canonical ID. Unknown IDs fail closed with the
registered list. Filesystem paths are never accepted as IDs.

## Status reporting modes

Normal `status(target=None)` is the repository-level Point 4 report. It
returns the existing canonical answer envelope with a bounded, read-only
projection of persisted semantic coverage: covered/current knowledge,
`PENDING`/`OPEN` or otherwise incomplete work, stale/unverifiable items,
unassessed semantic items in the returned frontier, and explicit bounds,
pagination, or outstanding scope. It does not enumerate structural
subjects, invoke interpretation, write state, or claim repository
completeness. Status never initiates interpretation, allocates
continuations, or persists freshness (Addendum I S2 observational).

Normal `status` with an exact target returns the same coverage semantics
narrowed to that target with live freshness qualifications and
next-operation guidance. `HOOK_FAST` remains a compact readiness/event
notice and does not return the repository inventory.

## Question selection, schemas, excerpts, and state explanation (Addendum I)

- `explain`, `trace`, `authority` (SubjectSelector only), and `impact`
  accept narrowed `question_selection` (slice/basis/anchors only). The
  service derives root/subject/class, canonicalizes verbatim, appends
  TRACE/IMPACT discriminators, and rejects full-scope supply, baseline
  conflicts, and ClaimRef-with-selection. Anchors pass verbatim as
  `question_terms`. Pages use `pgq:<digest>:<claims>:<rels>:<questions>`;
  old service cursors are rejected.
- Input schemas are generated from the canonical dataclasses with
  `$defs`, `$type` constants, and `additionalProperties: false`.
  Candidate nature exposes only `DESCRIPTIVE | NORMATIVE`. The pending
  brief carries a task-bound PENDING submission template.
- Narrow answers deliver bounded excerpts (`EvidenceLineRange`) with
  full-source fingerprints and explicit `excerpt omitted …` plus summary
  lines. Validation uses full provider content. Every answer carries
  `state_explanation` with the exact nature-sentence syntax.

## Worked exchange (schematic)

One complete target campaign over the twelve tools (exact carriers in
`tests/acceptance/test_addendum_e_acceptance.py`; full procedure in
`docs/onboarding-runbook.md`):

1. Discover the registered canonical `repository_id` through `tools/list`.
   If readiness is `UNINITIALIZED`, call `initialize_repository` once in its
   dedicated setup session and reuse the returned ID; an already initialized
   repository is used directly. `READY` is operational storage readiness
   only.
2. `initialize_target` with the exact `EvidenceScope` and objective →
   deterministic `TargetId` plus a `PendingInterpretation` carrying one
   `target_inventory_items` (`question=None`: mapping work, not a semantic
   question). The batch members carry provider-enriched evidence for
   orientation; their stable `EvidenceId` values are the agent's mapping
   input.
3. The host maps every batch member with a
   `CandidateTargetInventoryAccount` (assignment, evidence-backed
   exclusion, or unresolved mapping) and calls `submit_interpretation`.
   Span resolves the provider-owned `EvidenceRef`, persists the durable
   account, and creates the first-admission `PENDING` CQ-01 seed when no
   reusable question exists.
4. `initialize_target` then yields `PENDING` semantic questions per
   admitted area; the host examines each slice with its own model and
   submits `ANSWERED`/`OPEN`/`NOT_APPLICABLE`/`PENDING` coverage until an
   answer returns.
5. `status` with `target=TargetId` → `StatusContent` with
   `target_association`, `target_disposition`, and read-only
   `target_total/accounted/unaccounted_count` from the same snapshot
   (`INCOMPLETE` while work remains; `CURRENT` only when every member
   is accounted, every area has terminal coverage, and all dependencies
   are current and verifiable; `None` counts exactly on
   `UNVERIFIABLE`/`UNASSESSED`).
6. Fresh session, no host memory: `status` with `target=TargetId`, then
   exact-area `explain`/`trace`/`authority` on the returned `SubjectId`s.

## Correction (Addendum H §6)

A challenged but `CURRENT` explanation is reassessed through `refresh`
with an exact `SubjectSelector` and explicit `stale_only=False` (the
default `True` only re-examines stale scope). The suspension carries
the persisted question identities; the agent nominates exactly one
already-persisted original question via one
`proposed_question_coverages` entry with that exact scope, plus
evidence-grounded withdrawals and replacements in the same canonical
submission. A second distinct non-bound correction question, or a
withdrawal without the nominated coverage, rejects the unit. `explain`
is not a correction entry; `status` is read-only.

## Structural-provider boundary

Span resolves a plain repository locator to its internal structural
provider. The provider-owned index lives outside every target:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

`initialize_repository` provisioning (including server startup
registration and installer verification) runs at most one bounded
provider-owned build into the cache when it is missing or stale
(wiring-only, no credentials, no target writes), then reloads and
validates. A failed or malformed build is an actionable setup failure,
never a usable provider. A dirty tree after a successful build still
provisions: the provider is available but freshness is UNVERIFIABLE.
Explicit `refresh` performs the same single bounded rebuild for its
scoped target. `status`, `explain`, `locate`, `neighbors`, hooks, and
all other ordinary reads never build. Span stores and continuations live
outside the target in the configured data directory. The installer may
update only the managed Span lifecycle block in the target `AGENTS.md`;
per-target plugins and all other target artifacts are not written.
`initialize_repository` takes a plain `repository_locator`
plus `structural_provider_config` (a plain repository path; provider
selection stays shell-internal); the core never interprets provider
paths or commands. There is no separate structural MCP server:
structural navigation (`locate` for find/ outline/member listing,
`neighbors` for bounded adjacency) is served by Span itself under
Addendum F, with two-tier freshness (entry verification plus scope
coverage) and version-bound pagination. The onboarding preflight is the
read-only structural-artifact census (the managed `AGENTS.md` guidance
block is the intentional installer exception) recorded in the receipt
and acceptance evidence. Exact onboarding path:
`docs/onboarding-runbook.md` and Addendum E §4A.

Migration from a pre-F install (one time, operator): the installer
removes an obsolete structural MCP registration from opencode host
configs and attempts the equivalent Codex cleanup, both reported in the
receipt (a `manual` codex status means the operator finishes that
removal by hand). Removing configuration never stops an already-running
server: stop any such process out of band before relying on sole-MCP
operation. The only Span-owned structural-index writer is the bounded
managed-indexer build on explicit `initialize_repository` provisioning
and explicit `refresh` (cache under the data directory, never target
writes); no manual offline index preparation is required —
provisioning builds when needed and fails with an actionable setup
error when the indexer cannot build. (Contributor note: the adapter
module documents the indexer invocation.)

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
  Status entry requirements name the next exact step: stale or
  unverifiable → `refresh` with the exact `SubjectSelector`; `UNASSESSED`
  → question-local `explain`; pending question work → only the
  continuation returned by the suspending operation, never an invented
  `cont-*` token.
- Knowledge maintenance: `initialize_target` (exact `EvidenceScope`
  plus user-directed objective; admits a campaign), `refresh` (ordinary
  stale refresh accepts a scoped `SubjectSelector` or `EvidenceScope`;
  an unchanged-source/CURRENT challenge requires `stale_only=false` with
  an exact `SubjectSelector` only; never repo-wide without enumeration).
- Interpretation exchange: `submit_interpretation`
  (`continuation` plus typed result; retained on validation failure,
  consumed only on successful commit) versus `reissue_interpretation`
  (`continuation` only, an explicitly eligible interpretation-task ingress
  failure exactly once; malformed or validation responses reuse the existing
  continuation, and expired tokens recover via idempotent re-entry to the
  original operation).

Selection rules: need a file, symbol, or member list → `locate`; need
structural adjacency → `neighbors`; need established semantics →
`trace`; need behavior → `explain`; need governance → `authority`;
need change consequences → `impact`. Structural adjacency is evidence,
never a semantic trace. `status` never triggers `refresh`. No generic
router exists; apparent overlap is resolved by these rules.

`locate` modes carry distinct arguments. `SYMBOL` requires `query` and
accepts an optional `target` scope; `match=EXACT` resolves an exact
locator to its declaration/name and never returns partial hits, while
`match=CONTAINS` returns substring matches in provider order.
`FILE_OUTLINE` requires one file locator and takes no target scope or
match mode. `TARGET_MEMBERS` requires the exact `target` scope and takes
no query. Pages resume with the returned `pgv:*` token.

## Error recovery (Addendum G §4.1)

`unknown_repository` lists the sorted registered ids. Bounds rejection
names the received value, the maximum, and the omission default.
`page_token` and `continuation` (`cont-*`) misuse names both mechanisms.
Service answer pages use the returned opaque `pgq:<digest>:<claims>:<rels>:<questions>`
token; normal repository `status(target=null)` uses the same grammar with
the subject offset in the first position and zero relationship/question
offsets. Structural `locate` pages use their returned versioned `pgv:*`
token and `neighbors` uses its resumable `pgn:*` traversal token. These
page-token families are not interchangeable, and
`pg:<offset>` is an internal store cursor, not an agent-facing token.
Campaign status under `HOOK_FAST` requires `NORMAL`.
Null `refresh` names the scoped selector or scope plus `status`.
Stale listing continuations name the new version and direct restart from
page one. Canonical decode failures carry dotted field paths with
indices. Validation failures name `collection[index] (key=...)` and keep
whole-unit atomic rejection.

## Freshness transparency (Addendum G §4.2)

Structural pages carry `coverage` plus `coverage_detail` (closed tokens:
`non-git-tree`, `injected-index`, `dirty-tree`, `touched-file-mismatch`,
`unverifiable-file`, `index-older-than-head`,
`repository-population-unverified`, `clean-verified`). Missing or
unparseable indexes fail closed with no
report. Repository `status` orders its current page deterministically
and guarantees every non-current repository entry carries an actionable
canonical requirement; campaign `UNASSESSED`/`UNVERIFIABLE` paths keep
their designed responses. `UNVERIFIED` empty results prove nothing.

## Boundaries

No semantic rule lives in transport: descriptions are
capability-oriented; skill/hook guidance lives outside the server.
Filesystem skill distribution is canonical; MCP Skills-extension
exposure is deferred until a proven consumer exists.

## Compact wire grammar and interpretation profile (Addendum J, S6–S9)

- The agent-facing request grammar is a deterministic projection of the
  canonical carriers. `$type` is a property of the field **position**: it is
  absent (and rejected if supplied) where the expected type is statically
  unique, and required only at genuine multi-dataclass unions. Root result
  tags are retained; nested unambiguous tags are compacted.
- Omitted `bounds` uses the service default; repository-wide `status`
  accepts an omitted `target`.
- Pending interpretation units carry an `interpretation_profile`
  (`SA_1_7_V1`) naming the immutable SA-1..SA-7 obligations documented once in
  the `submit_interpretation` tool description. The static handbook, the
  default bounds, and the base task-brief rules are not repeated per unit;
  dynamic question/evidence/requirements remain.
- `submit_interpretation` maps target inventory with a
  `CandidateTargetInventoryAccount` (stable `EvidenceId` + exactly one
  semantic outcome). Span resolves the provider-canonical `EvidenceRef`,
  constructs the durable account, and creates the service-owned
  first-admission `PENDING` CQ-01 seed for a newly admitted area.
- Coverage shape is fixed per disposition: `OPEN` carries
  `resolution_requirements`, `ANSWERED` sets `declared_complete`, and
  `NOT_APPLICABLE` carries empty `result_refs`.
