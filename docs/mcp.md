# MCP reference

Thin transport over stdio (`span-mcp --data-dir DIR
[--repo /path ...]`). Exactly eleven tools, one per canonical
operation: `initialize_repository`, `initialize_target`, `explain`,
`impact`, `trace`, `authority`, `status`,
`refresh`, `submit_interpretation`, `locate`, and `neighbors`. Read-only
structural navigation (`locate`, `neighbors`) is served by Span itself; no
separate structural MCP exists.
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
rejected without duplicates.

Successful tools expose the same canonical result twice: the model-facing
JSON text and the application-facing MCP structured result. Both are
projections of one canonical Span carrier and are not separate contracts.
Errors keep readable JSON text and have no structured success payload.

Continuation tokens remain opaque and are never exposed by `status`. Normal
status names the recovery action for a pending question. When a continuation
is live it names the operation holding the question; when none is live it
names the originating operation and the inputs stored with the question; a
question with no recorded origin is recovered with `refresh` on its subject.
A lost or expired continuation is never reconstructed, and `READY` is
storage/runtime availability, never semantic completeness.

## Repository discovery

`tools/list` appends the sorted registered canonical repository IDs to
repository-scoped tool descriptions at list time, so agents discover
identity before the first repository-scoped call. `initialize_repository`
also returns the canonical ID. Unknown IDs fail closed with the
registered list. Filesystem paths are never accepted as IDs.
`--repo` startup registration is identity-only; `tools/list` opens no
repository context, and the working context opens once on the first
repository-scoped call.

## Status reporting modes

Normal `status(target=None)` is the repository-level Point 4 report. It
returns the existing canonical answer envelope with a bounded, read-only
projection of persisted semantic coverage: covered/current knowledge,
`PENDING`/`OPEN` or otherwise incomplete work, stale/unverifiable items,
unassessed semantic items in the returned frontier, and explicit bounds,
pagination, or outstanding scope. It does not enumerate structural
subjects, invoke interpretation, write state, or claim repository
completeness. Status never initiates interpretation, allocates
continuations, or persists freshness.

Normal `status` with an exact target returns the same coverage semantics
narrowed to that target with live freshness qualifications and
next-operation guidance. `HOOK_FAST` remains a compact readiness/event
notice and does not return the repository inventory.

## Question selection, schemas, excerpts, and state explanation

- `explain`, `trace`, `authority` (SubjectSelector only), and `impact`
  accept narrowed `question_selection` (slice/basis/anchors only). The
  service derives root/subject/class, canonicalizes verbatim, appends
  TRACE/IMPACT discriminators, and rejects full-scope supply, baseline
  conflicts, and ClaimRef-with-selection. Anchors pass verbatim as
  `question_terms`. A selected question with persisted `PENDING` coverage is
  still unexamined: reissue the operation to receive a fresh task when no live
  continuation exists. Page tokens are opaque; pass the returned token
  unchanged to the same operation with the same arguments.
- Input schemas are generated from the canonical dataclasses with
  `$defs`, `$type` constants, and `additionalProperties: false`.
  Candidate nature exposes only `DESCRIPTIVE | NORMATIVE`. The pending
  brief carries a task-bound PENDING submission template.
- Narrow answers deliver bounded excerpts (`EvidenceLineRange`) with
  full-source fingerprints and explicit `excerpt omitted …` plus summary
  lines. If a complete evidence unit cannot fit the delivery ceiling, the
  task carries `MISSING_EVIDENCE` instead of claiming it was examined.
  Validation uses full provider content. Every answer carries
  `state_explanation` with the exact nature-sentence syntax.

## Worked exchange (schematic)

One complete target campaign over the eleven tools (exact carriers in
`tests/acceptance/test_addendum_e_acceptance.py`; full procedure in
`docs/onboarding-runbook.md`):

1. Discover the registered canonical `repository_id` through `tools/list`.
   If `store_readiness` is `UNINITIALIZED`, call `initialize_repository` once in its
   dedicated setup session and reuse the returned ID; an already initialized
   repository is used directly. `store_readiness: READY` is operational storage readiness
   only; `READY != semantic completeness`. Use coverage and disposition for
   semantic currency.
2. `initialize_target` with the exact `EvidenceScope` and objective →
   deterministic `TargetId`, the persisted `TargetAssociation`, and a
   `PendingInterpretation` carrying the area's first semantic question.
   Span enumerates the current inventory, assigns every member to the target's
   area, and creates the first-admission `PENDING` CQ-01 seed when no reusable
   question exists. Membership is never an agent submission.
3. The host examines the bound question slice with its own model and submits
   `ANSWERED`/`OPEN`/`NOT_APPLICABLE`/`PENDING` question decisions
   until an answer returns. Span derives the canonical persisted coverage.
5. `status` with `target=TargetId` → `StatusContent` with
   `target_association`, `target_disposition`, and read-only
   `target_total/accounted/unaccounted_count` from the same snapshot
   (`INCOMPLETE` while work remains; `CURRENT` only when every member
   is accounted, every area has terminal coverage, and all dependencies
   are current and verifiable; `None` counts exactly on
   `UNVERIFIABLE`/`UNASSESSED`).
6. Fresh session, no host memory: `status` with `target=TargetId`, then
   exact-area `explain`/`trace`/`authority` on the returned `SubjectId`s.

## Correction

A challenged but `CURRENT` explanation is reassessed through `refresh`
with an exact `SubjectSelector` and explicit `stale_only=False` (the
default `True` only re-examines stale scope). The suspension carries
the persisted question identities; the agent nominates exactly one
already-persisted original question via one
`proposed_questions` entry with that exact scope, plus
evidence-grounded withdrawals and replacements in the same canonical
submission. A second distinct non-bound correction question, or a
withdrawal without the nominated question decision, rejects the unit. `explain`
is not a correction entry; `status` is read-only.

## Structural-provider boundary

Span resolves a plain repository locator to its internal structural
provider. The provider-owned index lives outside every target:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

`initialize_repository` provisioning and installer verification run at
most one bounded provider-owned build into the cache when it is missing
or stale (wiring-only, no credentials, no target writes), then reload and
validate. `--repo` at MCP process startup registers repository identity
only: it does not initialize semantic state and does not call
`ensure_current`. Explicit `initialize_repository`, installer
verification, and explicit `refresh` are the only provider-currency
owners. A failed or malformed build is an actionable setup failure,
never a usable provider. A dirty tree after a successful build still
provisions: the provider is available but freshness is UNVERIFIABLE.
Explicit `refresh` performs the same single bounded rebuild for its
scoped target. `status`, `explain`, `locate`, `neighbors`, hooks, and
all other ordinary reads never build. Span stores and continuations live
outside the target in the configured data directory. The installer may
update only the managed Span lifecycle block in the target `AGENTS.md`;
per-target plugins and all other target artifacts are not written.
`initialize_repository` takes one plain `repository_locator` and optional
`authority_seeds`; provider selection stays shell-internal and the core
never interprets provider paths or commands. The configured authority
seeds persist with repository state in one atomic row and are rehydrated
after a process or host restart. Omitting `authority_seeds` preserves
the seeds already configured; an explicit empty tuple clears them; a
non-empty tuple replaces them. Unknown seed locators fail closed. The
semantic store supports schema 9 only: a fresh store is created at
schema 9, an existing schema-9 store opens normally, and any other store
version fails closed with no runtime migration; `span-install
--migrate-store <repository-id>` upgrades a schema-7 or schema-8 store to
schema 9 explicitly. There is no separate structural MCP server:
structural navigation (`locate` for find/ outline/member listing,
`neighbors` for bounded adjacency) is served by Span itself, with two-tier
freshness (entry verification plus scope coverage) and version-bound
pagination. The onboarding preflight is the read-only structural-artifact
census (the managed `AGENTS.md` guidance block is the intentional installer
exception) recorded in the receipt and acceptance evidence. Exact onboarding
path: `docs/onboarding-runbook.md`.

The only Span-owned structural-index writer is the bounded
managed-indexer build on explicit `initialize_repository` provisioning
and explicit `refresh` (cache under the data directory, never target
writes); no manual offline index preparation is required —
provisioning builds when needed and fails with an actionable setup
error when the indexer cannot build. (Contributor note: the adapter
module documents the indexer invocation.)

## Operation intents and selection

Eleven operations, retained because their contracts differ. Grouped by
agent intent; setup is separate from ordinary queries:

- Setup: `initialize_repository` (dedicated setup session, storage
  store readiness only; never semantic completion).
- Structural discovery: `locate` (file, symbol, or member list),
  `neighbors` (structural callers, callees, adjacency as evidence).
- Semantic investigation: `explain` (what a subject does),
  `authority` (what governs it), `trace` (established
  producer-to-consumer semantics, boundaries, lifecycle).
- Proposed-change assessment: `impact` (needs `change_kind`;
  `change_description` and `affected_assertions` are optional).
- State inspection: `status` (`NORMAL` repository or exact-target
  coverage; `HOOK_FAST` event-local notice only, never inventory).
  Status entry requirements name the next exact step: stale or
  unverifiable → `refresh` with the exact `SubjectSelector`; `UNASSESSED`
  → question-local `explain` only when no owning operation is live; otherwise
  continue the returned continuation. Pending question work → continue with
  the continuation returned by the suspending operation when one is live;
  otherwise follow the recovery action status names (the stored originating
  inputs, or `refresh` on the subject).
- Knowledge maintenance: `initialize_target` (exact `EvidenceScope`
  plus user-directed objective; admits a campaign), `refresh` (ordinary
  stale refresh accepts a scoped `SubjectSelector` or `EvidenceScope`;
  an unchanged-source/CURRENT challenge requires `stale_only=false` with
  an exact `SubjectSelector` only; never repo-wide without enumeration).
- Interpretation exchange: `submit_interpretation`
  (`continuation` plus typed result; retained on malformed or validation
  failure, consumed only on successful commit). An unknown, expired, or
  lost continuation recovers from the question's stored recovery inputs when
  recorded, or with `refresh` on the subject otherwise; there is no reissue
  operation.

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
no query. Pages resume by passing the returned page token unchanged.

## Error recovery

`unknown_repository` lists the sorted registered ids. Bounds rejection
names the received value, the maximum, and the omission default.
`page_token` and `continuation` misuse states the conceptual mismatch and
the remedy without teaching the internal encoding. Page tokens are opaque:
pass a returned token unchanged to the same operation with the same request
arguments. A continuation is opaque: pass it unchanged to
`submit_interpretation`. The two mechanisms are not interchangeable.
Campaign status under `HOOK_FAST` requires `NORMAL`.
`refresh` requires a scoped target (`SubjectSelector` or `EvidenceScope`);
`status` remains the read-only way to find the stale scope.
Stale listing continuations name the new version and direct restart from
page one. Canonical decode failures carry dotted field paths with
indices. Validation failures name `collection[index] (key=...)` and keep
whole-unit atomic rejection.

## Verification

A verification claim is a link: which subject is verified, by what kind, and
whether the agent attests `CANDIDATE` or `UNKNOWN`. The execution record is a
separate State carrying the command, exit status, observed revision, time, and
observer. Its verified scope is the link's evidence scope, so the agent never
supplies an internal fingerprint. Status derives `CURRENT_PASS`,
`CURRENT_FAIL`, `STALE`, or `UNKNOWN` from that record; an asserted pass cannot
be submitted.

## Freshness transparency

Structural tool results (`locate`, `neighbors`) carry `coverage` plus
`coverage_detail` (closed tokens:
`non-git-tree`, `injected-index`, `dirty-tree`, `touched-file-mismatch`,
`unverifiable-file`, `index-older-than-head`,
`repository-population-unverified`, `clean-verified`). The claim is
type-enforced by `StructuralPageCoverageTest`, which enrolls every
structural tool result from the output map. When the page behind
`impact` or `trace` is not current, the answer carries a resolution
requirement naming the reason and `refresh`, so stale structure is
never presented as current. Missing or
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

## Compact wire grammar and interpretation profile

- The agent-facing request grammar is a deterministic projection of the
  canonical carriers. `$type` is a property of the field **position**: it is
  absent (and rejected if supplied) where the expected type is statically
  unique, and required only at genuine multi-dataclass unions. Root result
  tags are retained; nested unambiguous tags are compacted.
- Omitted `bounds` uses the service default; repository-wide `status`
  accepts an omitted `target`.
- The immutable SA-1..SA-7 obligations are documented once in the
  `submit_interpretation` tool description. The static handbook, the default
  bounds, and the base task-brief rules are not repeated per unit; dynamic
  question/evidence/requirements remain.
- `initialize_target` admits membership deterministically: Span enumerates the
  current inventory, assigns every member to the target's area, persists the
  association, and creates the service-owned first-admission `PENDING` CQ-01
  seed. Membership is never submitted by the agent.
- Coverage shape is fixed per disposition: `OPEN` carries
  `resolution_requirements`, `ANSWERED` requires validated material and
  Span derives `result_refs` and `question_evidence`,
  and `NOT_APPLICABLE` carries a basis and no result refs.

---

## Operation map

Span exposes eleven canonical MCP operations. No semantic_* aliases exist.

| Need | Operation |
| --- | --- |
| Set up repository storage and identity | `initialize_repository` |
| Establish an exact bounded target | `initialize_target` |
| Understand what something is, does, or means | `explain` |
| Assess what a proposed change may affect | `impact` |
| Follow established producer → transformation → consumer semantics | `trace` |
| Determine what governs something | `authority` |
| Inspect store readiness, coverage, and currency | `status` |
| Re-check established understanding | `refresh` |
| Submit agent interpretation | `submit_interpretation` |
| Find files, symbols, outlines, or target members | `locate` |
| Inspect bounded structural adjacency | `neighbors` |

Every non-current `status` entry names the next exact step: stale or
unverifiable work uses `refresh` with that entry's exact `SubjectSelector`;
unassessed work uses a question-local `explain` only when no owning operation
is live; live first-time work continues only through the continuation returned
by the suspending operation. Pass every returned page token or continuation unchanged; never
decode, edit, or synthesize either opaque value.


---

## Structural navigation

Span includes structural navigation because structural information is useful evidence.

Use:

```text
locate
```

for:

- files;
- symbols;
- file outlines;
- target members.

Use:

```text
neighbors
```

for bounded relationships such as:

- callers;
- callees;
- upstream adjacency;
- downstream adjacency.

`locate` takes exactly one mode: `SYMBOL` (requires `query`, optional
target scope; `EXACT` resolves an exact locator to its declaration/name
with no partial matches, `CONTAINS` returns substring matches in provider
order), `FILE_OUTLINE` (one file locator, no target scope or match mode),
or `TARGET_MEMBERS` (exact target scope, no query).

These operations answer structural questions.

They do not establish semantic truth by themselves.

For semantic questions, use:

```text
explain
trace
authority
impact
```

The distinction matters.

A call edge can be mechanically observed.

Ownership, purpose, responsibility, governance, and lifecycle meaning still require interpretation against the relevant evidence and authority.

---
