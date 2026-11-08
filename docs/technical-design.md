# Span technical design — layer 4

**Status: stated decisions are binding; unresolved portions remain open.**
Implementation may proceed only where its applicable inputs are settled;
activation is blocked by the required open items in §6. This is layer 4. It records the
implementation baseline, what is retained from the two existing codebases, and
the proposed refactoring boundary for layers 0–3. It chooses mechanisms; it
adds no product requirement. Where it conflicts with a higher layer, the higher
layer governs.

**Release identity (2026-11-07).** The current public release is **0.10.0**
(2026-11-07), a public-grammar and identity-ownership release over 0.9.4. The
prior internal pre-release artifacts were withdrawn and were never public.
References below to the withdrawn internal baseline describe that artifact, not
the public release.

**Baseline measured at:** withdrawn internal baseline = repository revision `aa580b3`; 0.8.3 = tag
`v0.8.3`. Counts below are measurements of those trees, not estimates.

**Review update: 2026-11-01.** Part A (§1–§8) records source assessments;
Part B (§9–§16) records implementation choices. Authority and migration decisions
are recorded in §6, §10, §12, and §14 (see §6, resolved 2026-11-01); the
remaining evidence is delivery and measurement (O-2, O-3, O-6), which the forward
plan schedules. Part B is **PARTIAL**: no runtime, schema, host configuration, or
release is changed by this document.

The [requirements pyramid](requirements-pyramid.md) governs placement and
precedence. Product and behavioural rules remain in layers 0–3; this document
cites their IDs instead of defining replacements. Execution ordering and gate
ownership live in the
[implementation plan dated 2026-11-01](../.context/plans/2026-11-01-implementation-plan.md).

## 1. Baseline decision

Neither existing version is the requirement baseline, and neither is discarded
wholesale.

- **The withdrawn internal baseline is the codebase base.** Its support evaluation, evidence binding,
  contexts, receipts, versioning, installer, hooks, and structural provider
  supply reusable mechanisms. Compliance is assessed per boundary in §3;
  retaining an algorithm does not retain its current public grammar or keys.
- **0.8.3 supplies five algorithms**, not a second codebase. Its campaign,
  interpretation, and exchange stack is retired by layer 2.
- The new contract is the baseline; both codebases are suppliers to it.

## 2. Inventory and overlap

| | withdrawn baseline | 0.8.3 |
| --- | --- | --- |
| Source files | 79 | 152 |
| Source lines | 20,430 | 34,326 |
| Test files | 32 | 65 |
| Test lines | 12,616 | 38,201 |
| Shared module paths | 53 | 53 |

The 53 shared paths are mostly scaffolding: schema and paging, ports, discovery,
navigation, shell, install, MCP transport, and the structural provider. Four are
central to the rewrites, not scaffolding: `shell/mcp/schemas.py` (the public
surface, rewritten), `core/model/primitives.py` (identity and version carriers),
`core/model/claims.py` (conclusion carriers), and `service/bounds.py` (removed
from the API). The divergence is the semantic core.

**There is no surface concept in the withdrawn baseline.** `grep -r Surface src/span` returns
nothing; `test_lifecycle_surface.py` tests the tool surface, not code surfaces.
That is the largest genuine gap.

## 3. Compliance by functional area

| FD area | withdrawn baseline evidence | Decision | 0.8.3 source |
| --- | --- | --- | --- |
| FD-1 surface identity | none; `Understanding.scope` is an `EvidenceScope` | **New** | `service/resolution/selector.py` |
| FD-2 request/context | `contexts.issue_context` recovers by request identity and digest; its payload currently includes caller-managed bounds | **Adapt binding; keep recovery mechanism** | — |
| FD-3 submission/replay | `recording.receipt_decision` is reusable; `RecordingIdentity` and SQLite receipt keys use context/submission | **Adapt carrier, key, lookup, and transaction** | — |
| FD-4 receipt survival | `replay_expires_at`; `LifecycleRetention`; old receipt selector | **Adapt retrieval and measured policy** | — |
| FD-5–8 containment/status | none | **New** | `operations/status/coverage.py` |
| FD-9–16 support | four dependency kinds and recursive evaluation exist; withdrawal differs; `_revision_eval` collapses dependency states into reason strings | **Adapt withdrawal and typed dependency findings; O-5 blocks ambiguous propagation** | `freshness/` (superseded) |
| FD-17–22 propagation | no `reconsider`; fingerprints and premise walk exist | **New operation + adapt** | `refresh/scan.py` |
| FD-23–29 composition | `understand` returns candidates and `DiscoveryLimit`, not `Answer`/`Gap` | **Adapt** | `answers/assembly.py`, `core/requirements.py` |
| FD-30–37 transitions | immutable versions/membership exist; confirm shares correction's revision path; no surface/question uniqueness or dependent effects in results | **Adapt creation, confirmation, and result composition** | — |
| FD-38–41 failure | transport `ToolError`; `_validation_kind` classifies exception text | **Adapt canonical outcomes and structured failure details** | — |
| FD-42–45 retention | operational reaping; O-2 settled at a 7-day replay promise / 1-day context | **Keep** | — |
| FD-46–48 concurrency | transactions, `expected_version`, old-key conflict/replay | **Keep mechanisms; reverify changed keys and create/no-op paths** | — |
| FD-49–53 host contract | 19 tools; historical Codex/OpenCode captures; new grammar not captured | **Replace grammar and obtain candidate-specific delivery evidence** | — |
| FD-54–57 bounds | `bounds` in the API; `_fit_result` | **Adapt** | `answers/assembly.py` `ResponseBudget` |

## 4. Retention decisions

### Keep from the withdrawn baseline

Keep mechanisms, not whole-file exemptions: canonical serialization, paging,
source/discovery identity checks, receipt comparison, immutable membership,
compare-and-set, exact evidence access, navigation, and observational readiness.
Continue using the existing evidence source, structural provider, transaction
owner, installer, and transition command. Their affected interfaces still adapt
under §3 and Part B.

### Adapt from the withdrawn baseline

`core/model/{understanding,investigation,outcomes,commands}.py` (add surfaces,
answers, gaps), `core/identity.py` (surface-aware identity derivation),
`core/model/{recording,support,primitives}.py` (request-keyed identity and typed
dependency findings), `core/{recording,support_rules}.py` (transition/support
corrections),
`core/schema/{wire,record_wire,projection}.py`,
`service/{contexts,evidence,support,lifecycle,understand,answer,reconsider,discovery,bounds}.py`
(bounds: default moves to layer 4; remove the API parameter),
`ports/lifecycle.py`, `shell/{sqlite_store/lifecycle,policy,context,mcp/*,mcp_server,store_transition}.py`,
and directly affected installer, packaged-skill, and managed-instruction sources.
Verification carriers change only if O-7 proves it necessary; do not create a
second run model.

### Borrow from 0.8.3 — five algorithms, not modules

| Source | Use | Adaptation note |
| --- | --- | --- |
| `service/answers/assembly.py` | `AnswerAssembler`, `ResponseBudget`, item selection, `coverage_counts_for`, `_distribution_sentence` | Rebuild on the new carriers; it depends on retired answer types |
| `core/requirements.py` | gap and missing-item builders (`ambiguous_identity`, `missing_evidence`, `stale_evidence`, `unverifiable_freshness`, …) | Informs FD-25 |
| `service/resolution/selector.py` | identity resolution over structural evidence; ambiguity never overridden | Informs FD-1, FD-5, FD-26 |
| `service/operations/status/coverage.py` | scoped status distribution and repository report | Informs FD-8, FD-23 |
| `service/operations/refresh/scan.py` → `_expand_premise_dependents` | indirect propagation concept (a stale premise needs reassessment even when its own file is unchanged) | Reimplement; the original swallows exceptions |

### Retire from 0.8.3

`establishment`, `interpretation/*`, `questions/*`, `exchange/*`,
`shell/agent_exchange`, `core/continuations`, `ports/{continuation,interpretation}`,
operations `explain` / `impact` / `trace` / `authority` / `refresh` /
`initialize_target`, and schema 9 plus its migrations. This is the campaign
protocol that layer 2 removes.

### Retire from the withdrawn baseline

The 19-tool public grammar and its required caller bookkeeping. Retain service
mechanisms through the adaptations above; do not run old and new public
protocols side by side. Registered tool count is a host-delivery choice under L8.

## 5. Proposed refactoring boundary

WP identifiers here group mechanisms; they are not an execution sequence or a
size estimate. The forward plan owns dependency order and gate evidence.

**Implementation state (2026-11-03).** WP-1–WP-6 are delivered as the
three-tool surface; §9.1 records its final shape and conformance gate. The
subsections below remain the mechanism map. The 2026-11-02 three-tool captures
and the 2026-11-03 flat-create re-capture are the current delivery evidence; the
older twenty-tool captures are historical/void (§6 O-6, §15).

### WP-1 — Surface model, containment, and status *(largest)*

Covers FD-1 and FD-5–FD-8. New carriers (`Surface`, `SurfaceKind`,
`SurfaceBoundary`, `SurfaceStatus`), schema 11 tables, a containment resolver,
path and declared surfaces, `unexamined`, and descendant status.

A schema-11 transition path is required at the same boundary; see §14 and O-4.

Reuse: 0.8.3 resolution and coverage. No existing surface tests; new tests are
required.

### WP-2 — Answer/Gap composition and document view

Covers FD-23–FD-29. Adapt `understand.py`; add `Answer`, `Gap` with four reasons,
the surface status view, and the document view. Depends on WP-1 for surface
resolution (FD-26).

Reuse: 0.8.3 assembly and requirement builders.
Adapt discovery to surface ownership, and replace current snapshot projection
with the canonical result composition in §11. Independent verification remains
source-bound under O-7.

### WP-3 — `reconsider`

Covers FD-17–FD-22. New service: path-to-surface mapping, direct and premise
closure, inclusion with reasons, deduplication, deterministic order, bounded
unaffected reporting.

Reuse: the premise-expansion concept from 0.8.3.

### WP-4 — Write-path alignment

Covers FD-2–FD-4, FD-9–FD-16, FD-30–FD-37, and FD-46–FD-48. Adapt identity
carriers, request-keyed receipt lookup/storage, internal admission, surface/question
creation, confirmation, and the shared support evaluator. Preserve transaction
and compare-and-set mechanisms. Place dependent effects in the canonical recorded
result; §12 distinguishes immutable acceptance from live qualification. O-5
blocks only the unresolved propagation-state case, not unrelated work.

### WP-5 — Public surface and host contract

Covers FD-38–FD-41 and FD-49–FD-53. Replace the grammar, generate schemas from
canonical contracts, adapt structured failure projection, and coordinate
packaged instructions with binary cutover. §15 owns delivery evidence.

### WP-6 — Retention, bounds, fitness

Covers FD-42–FD-45, FD-54–FD-57, and F8. Adapt policy inputs and response fitting;
measure recovery horizons, host budgets, and comparative fitness. FD-44 does not
require introducing history reaping. If introduced, its owning implementation
and reference effects belong in this package, not an unrelated subsystem.

## 6. Open items

### O-1 — Withdrawn premise (design decision closed; implementation pending)

FD-13, FD-19, and FD-34 govern. Adapt `support_rules.premise_membership_state`
and `SupportService._premise_eval` to distinguish withdrawal from supersession;
the present helper conflates them. The earlier proposal to amend layer 3 to
preserve existing behaviour is withdrawn. WP-4 changes implementation against
the existing authority; no higher-layer amendment is assumed.

### O-2 — Retention policy value

`LifecycleRetention` enforces `replay_retention >= context_lifetime`. FD-43
requires the window to be at least the longest supported session suspension. The
policy value must be derived from that bound and recorded here once measured.
First, the product/host owner must establish the supported recovery promise and
whether its suspension horizon is finite. That decision precedes measurement and
duration selection. If FD-43 cannot be satisfied for the proposed host scope,
refer the conflict to its owning layer; do not label an arbitrary timeout a
measurement or silently narrow the promise. O-10 owns the host-scope decision.
Status: **RESOLVED — owner direction 2026-11-02.** The supported recovery
promise is: a host process may stop and restart at any time; Span state is on
disk, not in the session. A recording retry is supported for **7 days** after
commit (`replay_retention`); a context is live for **1 day**, after which a new
ask issues a new context and a retry is still recovered receipt-first. A
suspension longer than 7 days is outside the promise and starts a new request
identity. The window is therefore finite and at least the longest supported
suspension, satisfying FD-43. `shell/policy.py` carries these settled values.

### O-3 — Default budget

FD-54 makes response size server-owned; this layer stores the measured default
per host. Status: **RESOLVED — measured 2026-11-02.** Delivered-wire observations
against the 0.10 candidate:

- OpenCode delivered a 51,133-byte result inline and saved a 62,589-byte result
  to a file; the budget is **51,133** bytes.
- Codex delivered a 62,589-byte result inline; the budget is **62,589** bytes.

The installer writes the measured value for the host being registered
(`--response-budget-bytes`), and the server applies it as
`ServiceBoundsPolicy.max_response_bytes` to the delivered wire projection. The
no-flag default is the smaller measured value, so an unconfigured server is safe
for both supported hosts. This resolves FG-4; the values are observations, not
invented thresholds.

**Fitting defect reproduced and repaired (2026-11-07).** A post-edit `ask` on a
2,000-rule CSS surface under the OpenCode-sized 51,133-byte budget delivered a
continuation `EvidencePage` of 51,203 bytes. The line-split fitter measured a
candidate page without the omission label it then carried, so the final page
exceeded the configured budget. The evidence-page fitter now measures the real
continuation token and the final omission list, with a final backstop, and the
same scenario delivers 51,107 bytes. The per-host budgets above are unchanged:
this was a fitting defect, not a new host measurement. The regression is
`test_continuation_page_fits_the_budget_with_its_omission`.

### O-4 — Schema-10 transition mappings (resolved 2026-11-01)

Status: **RESOLVED**. §14 records the mapping rule: each schema-10 understanding
maps to the path surface named by its `EvidenceScope` when that scope names
exactly one path that is a file; a scope naming several paths, none, or a
directory is classified `unresolved` with a named reason and preserved in the
archive, never assigned a fabricated service or domain surface. Receipt
identities map through their context's recorded request identity. Every table is
classified preserved, mechanically transformed with verified references, or
unresolved with a named reason. The reviewed per-record counts and hashes remain
§14 evidence obligations, not an open design question.

### O-5 — Unsupported-premise state (resolved 2026-11-01)

Status: **RESOLVED (layer 3)**. FD-13 and FD-19 now state the case directly: an
in-membership premise whose own support cannot be checked is inherited as
`UNVERIFIABLE`, inheritance never converts an uncheckable premise into a definite
finding (FD-10, FD-15), and a premise that was checked and is no longer supported
is `REASSESSMENT_REQUIRED`. The evaluator's recursion already produces the stated
result for an uncheckable source (`SupportService._premise_eval` →
`_revision_eval`); WP-4 changes no behaviour for that case, and no carrier,
handler, or fixture originates the rule. O-1's withdrawal case is stated
separately by FD-13 and is not reopened.

### O-6 — Host grammar and invocation identity

Status: **PARTIAL for the compact-update/server-derived-identity schema (Codex
and OpenCode)**. §15 requires an identified candidate, supported host/version,
invocation-identity owner, and raw delivery capture. Codex and OpenCode have
three-tool captures, and the 2026-11-07 candidate adds a valid compact journey
and a host-coercion finding. OpenCode delivered the valid create/add/correct/
replace lifecycle but did not preserve strict unknown-field rejection for an
old-form `add`. Codex delivered a current-candidate smoke create with a
server-derived identity; its full add/correct/replace journey was not
re-observed. Claude's managed-host registration and health evidence is covered
by O-10, but its authenticated model-delivery grammar and caller identity remain
unverified. The older twenty-tool captures are historical/void and do not
certify the current `ask`/`record`/`reconsider` surface.

**Observed 2026-11-01 (OpenCode).** A candidate-specific capture established
the declared 20-tool schema exactly, a cold→record→warm journey on the real
server, same-request-identity replay after a fresh process, and forced-retry
identity reuse. It also exposed a schema-projection defect: the structural
operation's defaults carried a dataclass instance. Raw captures and gate
dispositions are in `.context/evidence/host-contract/2026-11-01/RECEIPTS.md`.

**Observed 2026-11-02 (Codex, `gpt-5.6-luna`).** The real candidate delivered
the exact generated grammar, a cold→record→warm journey, same-identity replay
after a fresh process, forced-retry identity reuse, and concurrent
same-identity calls that both returned one retained receipt.

**Re-observed after contract closure (2026-11-02).** Codex and OpenCode both
delivered the closed result unions (`Rejected` as a structured result), a
context-free recording that issued its own context, a challenge through
`reconsider` returning `Challenged`, and an identical replay. The historical
20-tool capture schemas matched the then-packaged schemas; that evidence is
retained for its historical scope and does not describe the current public
surface. Evidence:
`.context/evidence/host-contract/2026-11-02-closure/RECEIPTS.md`. Codex inlined the
full 62,589-byte truncated answer, so O-3 has a Codex lower bound at that size.
The earlier capture is in
`.context/evidence/host-contract/2026-11-02-codex/RECEIPTS.md`.

**Observed 2026-11-07 (compact create/update, server-derived identity).**
Candidate evidence is in
`.context/evidence/host-contract/2026-11-07-server-derived-identity/RECEIPTS.md`.
OpenCode (`2.2.5`, `opencode-go/deepseek-v4.1-flash`) delivered the valid
compact create/add/correct/replace lifecycle, with `reconsider` supplying the
context and `expected_version`. Its old-form `add` probe is a host-contract
limitation: OpenCode removed the unknown `conclusion_id` before delivery, so
Span accepted the resulting valid request; the same payload over direct MCP
stdio is rejected by the server. The OpenCode lane therefore proves the valid
lifecycle, not strict unknown-field preservation. Codex (`codex-cli 0.162.0`,
`gpt-5.6-luna`) delivered a smoke journey: cold `Gap` → create without
`conclusion_id` → `UnderstandingRecorded` with a derived identity → `Answer`;
its full add/correct/replace journey remains unobserved. Claude remains
**UNVERIFIED** for authenticated model delivery. The FD-49–FD-53 disposition is
therefore: valid compact lifecycle observed on OpenCode and Codex smoke;
strict host preservation of unknown fields not established on OpenCode.

### O-7 — Verification ingestion (resolved 2026-11-01)

Status: **RESOLVED**. §12 records the accepted path: a run cites the
`SourceObservationId`s actually exercised, which are the observations admitted
for the operation's context — the context returned by a preceding
`ask`/`reconsider`, or the locators/ranges the operation admits internally before
recording. The wire accepts `run.observations` and/or `run.evidence`; evidence
locators are admitted before the same command path. The exact IDs are stored
with the run, so the run names what it actually exercised. No separate public
admission step and no inferred run provenance is introduced.

O-7 resolves **source-observation ingestion** only. It does not authenticate an
external execution, bind a command/argv/cwd, or prove that a host actually ran
the test. Authenticated execution receipts remain a separate,
not-yet-designed workstream and introduce no mechanism here.

### O-8 — Boundary-update encoding and historical references (resolved 2026-11-01)

Status: **RESOLVED**. §10 records the encoding: the update input is the declared
surface carrying the new boundary and `expected_boundary_version`; persistence
appends an immutable boundary version and advances the surface pointer in one
transaction; each understanding version records the boundary version it was
assessed against, so a historical reference identifies the boundary it describes.
FD-1, FD-6–FD-8, and FD-35–FD-36 constrain it. This is distinct from O-4's
mapping of existing schema-10 records.

### O-9 — Package release version

Status: **RESOLVED — owner direction 2026-11-03: `0.9.1`; 2026-11-04:
`0.9.2`, `0.9.4`; 2026-11-07: `0.10.0`.** The 0.9.1 decision restored D-17: the
replacement ships as 0.9.1, and the prior internal pre-release artifacts are
withdrawn and were never public. 0.9.2 (2026-11-04) was a bug-fix release over
0.9.1 and changed no public operation. 0.9.4 (2026-11-04) is a bug-fix release
over 0.9.2 and also changes no public operation. 0.10.0 (2026-11-07) is a
public-grammar release over 0.9.4: it replaces full-snapshot update payloads
with compact actions, derives new conclusion lineage identities on the server,
and removes the legacy parallel recording wire path. It adds no public
operation. FP-6 freezes release metadata against the current value.

### O-10 — Supported host set and recovery scope (resolved 2026-11-01)

Status: **RESOLVED — corrected 2026-11-04.** The supported managed hosts are
**Codex, OpenCode, and Claude Code** (see `docs/install.md` §Supported hosts).
Claude has supported registration, inspection, skills, and optional lifecycle
hook integration. Its registration/health evidence is available, but its
authenticated model-delivered grammar and caller identity remain
**UNVERIFIED** because no usable authenticated capture exists. That state is
not `UNSUPPORTED` and does not remove Claude from the managed-host set. The
earlier 2026-11-02 statement that Claude was unsupported is explicitly
retracted and superseded. Recovery claims remain conditional per FD-50: replay
safety is claimed only where the host preserves request identity, and the
replay window is measured per host at FP-4a (O-2) rather than assumed.

## 7. What not to do

- Do not port the 0.8.3 campaign, interpretation, or exchange stack.
- Do not rewrite the support evaluator, evidence source, or store; the withdrawn baseline's are
  closer to layers 1–3 than 0.8.3's.
- Do not keep 19 tools while adding the five-family contract.
- Do not port 0.8.3's schema 9 or its broad exception handling.

## 8. Evidence limits

The initial baseline assessment used module inventory, key functions, and test
inventory, not an executed suite. The 2026-11-01 investigation additionally ran:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_support_service.py tests/unit/test_lifecycle_service.py tests/unit/test_lifecycle_store.py tests/unit/test_understand_service.py tests/unit/test_record_wire.py -q
```

Observed result: **85 passed in 1.77s**, against the unchanged source at
`aa580b302ebb4a8f8c01ddde1aab9cf63e92fc0e`. The duration records that run only,
not a reproducible performance bound. This is current-behaviour evidence,
not a pass for the proposed contract or a full-suite run. No new host capture,
scored fitness run, or schema-11 transition was performed. Not every source
module was read; adaptation cost remains inferred, not an implementation estimate.

Historical host evidence is in the withdrawn beta ledger (internal evidence,
not published) and the
[G-0 capture](../.context/evidence/host-contract/2026-10-31/G-0.md). A fixture
README's `UNVERIFIED` label does not erase those captures, and those captures do
not establish delivery of a different grammar.

## Part B — Implementation mechanisms

The sections below choose owners and persistence/transport mechanisms. Exact
executable schemas and their host proof are deliverables, not existing artifacts.
All proposed carrier/table names below are design targets, not current symbols.

## 9. Canonical carriers and generated wire

**Authority:** FD-1–FD-4, FD-9–FD-16, FD-23–FD-29, FD-38–FD-41; L8.

Continue using the canonical dataclass model and schema generator. Put surface
carriers in `core/model/`, operation commands/results beside existing lifecycle
carriers, and persistence interfaces in `ports/lifecycle.py`. Extend the existing
support carrier with dependency-addressed findings instead of an additional
transport-only support model. Naming decision: reserve `Gap` for the public
operation result. Rename the existing recorded question/basis carrier to
`RecordedQuestionGap` in the canonical model, preserving its meaning and fields.
Update its references and generated schema through the same owner; the persisted
type-name treatment belongs to O-4's migration mapping. Do not retain a runtime
alias, shape adapter, or second writer. These are implementation targets, not
names already changed in code.

`core/schema/` owns strict ingress and generated schemas. Adapt the current
reference-only wire where the new contract needs locator/range or retained-context
inputs; do not wrap the old context/submission protocol in a new public tool.
Freeze each variant's required fields, result union, examples, malformed-input
cases, and serialization through that same owner. O-7 blocks the independent-run
variant. O-5 blocks its named support-state case, not unrelated carrier work.

`shell/mcp/schemas.py` registers the host-delivered projections of those carriers;
`shell/mcp/adapter.py` routes them. Family-variant splitting shares the canonical
command/result grammar. Host-specific duplicate semantic DTOs are excluded.
The deliverable is an executable schema/example set, not this prose table.

### 9.1 Delivered public surface (2026-11-02)

The three-tool surface is implemented in the working tree. `ask`, `record`, and
`reconsider` are the only registered operations. Any other operation name is
unknown. There are no aliases, removed-name compatibility mappings, or dual
grammars.

`ask` accepts exactly one of an exact `surface={kind, locator}`, a `reference`,
a snapshot/receipt selector, or a continuation. With no question, it returns the
surface document view; that is the normal reuse path. An exact question is a
targeted query and matches by exact identity; a paraphrase returns `no_match`
with a recovery that points back to the view. A reference that resolves to
more than one granularity returns `AmbiguousSurface` with exact candidate
identities; the agent copies one candidate back rather than re-resolving the
path. A gap whose evidence was omitted carries a stateless continuation over
the investigation context. The token binds repository, context, request
identity/digest, and the next evidence position; it is valid only while the
context is `LIVE`. Replay and restart work because the context and admitted
evidence are persisted, and every page advances by at least one evidence unit
or exact line range. Historical retrieval is a separate path (FD-38).

`record` is one request selected by `kind` (`understanding`, `verification`, or
`surface`). For understanding, a create carries one `conclusion` with exactly
one evidence mode — `locator`, admitted `observation_id`, or non-empty `support`;
scope is supplied or derived independently. Updates use `actions` with `add`,
`confirm`, `correct`, `replace`, or `withdraw`, and multiple keys apply
atomically. The service derives context, observation identity, submission
identity, current revision, and new lineage identity. A create may cite the
context returned by `ask`; its bound question and scope are used, and the caller
does not re-author them. It preserves the full support union, gaps, provenance, and named
challenge dispositions. `record(kind="surface")` creates or updates a declared
service/domain boundary with an optional parent and compare-and-set
`expected_boundary_version`; cycles, unknown parents, and stale versions are
rejected.

`reconsider` is an after-edit operation. `Changed` carries per-conclusion
support state, so a considered conclusion may still be `CURRENT`; only
`REASSESSMENT_REQUIRED` and `UNVERIFIABLE` mean actual loss. The change walk
includes containment, direct source dependents, direct discovery dependents
whose scope membership changed, and indirect premise dependents to a fixed
point. Challenges are raised by `reconsider` and settled through `record` with
named `challenge_dispositions`.

The conformance gate is `tests/unit/test_surface_conformance.py`. It fails if a
registered name is outside `ask`/`record`/`reconsider` or a host-justified
optional tool, if a per-action or internal-preflight tool is registered, if a
removed name remains, if declared and packaged schemas disagree, if a common
path requires an internal identity the agent must fetch, or if a tool cannot
name the lifecycle verb and agent moment it serves. The G-S2b scenarios live in
`tests/unit/test_lifecycle_service.py`, `tests/unit/test_reconsider.py`,
`tests/unit/test_answer_service.py`, and
`tests/integration/test_lifecycle_mcp.py`.

The friction-remediation mechanisms that refine this surface are in §9.2.

### 9.2 Contract remediation decisions (2026-11-02)

This section selects the mechanisms for the layer-2/3 statements in
`lifecycle-contract` §4.1–§4.2 and `functional-design` FD-25/28/30/39/41/46.
It adds no requirement; each paragraph names the binding statement it realises,
and that statement remains in its owning layer.

**FCIS / SoC / DRY.**

| Concern | Owner | Decision |
| --- | --- | --- |
| Exact question identity and `no_match` classification | `core` | Pure; exact identity only; no embeddings, reranking, or keyword tables |
| Rejection cause kind | `core` | Typed enum; no text classification |
| Current version / boundary version | `shell/sqlite_store` + `service` | Structured values carried through the result; no regex extraction |
| `Gap.recovery` composition | `service` | One builder keyed by gap reason; reuse the `Unavailable.recovery` shape |
| Surface document view | `service` | Reuse the existing composer; no second render or stored document |
| Adapter | `shell/mcp` | Transport only; copies typed results; no semantic or keyword logic |
| Surface conflicts | `shell/sqlite_store` + `service` | Typed conflict with current boundary version; mapped to `Rejected` |
| Parent validation | `service` | One validator for create and update; declared-parent, same-repo, no cycle |
| Descriptions and snippet | `shell/docs` | Layer-4 delivery; no semantic decisions |
| Tests | `tests` | One rejection case per cause; one surface case per conflict; shared fixtures only |

Do not add a parallel `ToolError` cause path, a second question projection, or a
second surface-declaration path. The document-view composer and the rejection
builder are single owners.

**Typed rejection.** Replace adapter text classification with one typed carrier
and one typed cause enum:

```python
class RejectionCauseKind(enum.Enum):
    VALIDATION = "validation"
    SOURCE_DRIFT = "source_drift"
    VERSION_CONFLICT = "version_conflict"
    SURFACE_CONFLICT = "surface_conflict"
    SURFACE_REQUIRED = "surface_required"
    SURFACE_AMBIGUOUS = "surface_ambiguous"
    SURFACE_MISMATCH = "surface_mismatch"
    CONTEXT_TARGET_CONFLICT = "context_target_conflict"
    CONTEXT_REQUIRED = "context_required"
    OBSERVATION_NOT_ADMITTED = "observation_not_admitted"
    REPLAY_CONFLICT = "replay_conflict"
    ALREADY_EXISTS = "already_exists"


class Rejection(ValueError):
    cause_kind: RejectionCauseKind
    cause: str                       # the server's exact message
    required_action: str             # one function of cause_kind only
    current_version: int | None = None
    current_boundary_version: int | None = None
```

Every raise site selects its kind; one cause-to-action function is the only place
that maps a kind to a remedy. `SOURCE_DRIFT`, `CONTEXT_REQUIRED`,
`OBSERVATION_NOT_ADMITTED`, and `ALREADY_EXISTS` exist because the prior text
classifier distinguished them and folding any into `VALIDATION` would misname the
conflict. `OBSERVATION_NOT_ADMITTED` is the remedy gap a flat-create host hit:
the field was right and the value was an id `ask` never returned, so “correct the
named field” sent it back to the same call.

The service and store raise a `Rejection`; the adapter copies it into the
public `Rejected` result and adds the request identity. The adapter must not
parse the cause, call `re.search`, or choose an action from words such as
“context”, “drift”, or “current”.

**Gap recovery.** `Gap.recovery: str` is required and is produced by one
`gap_recovery(reason)` helper. Each reason has a fixed next action, so no reason
has a lawful empty recovery:

- `no_match` → ask the same surface without a question to read its current
  document view;
- `invalidated` / `unverifiable` → re-read the cited evidence and record against
  the current revision;
- `unassessed` → read the cited evidence and record the conclusion.

The text is fixed and server-owned. `Gap.available_questions` is deferred until
the recovery path is measured.

**Closed result unions.** `TOOL_OUTPUT_SCHEMAS` projects FD-38;
`test_result_union_declarations_agree` asserts the reference and the runtime
union. There is no second declaration.

**Surface-first reuse.** Use the existing no-question `ask` form; add no new
operation. The `ask` description names the document view as the normal reuse
path, and the managed snippet keeps the same five lines with the `no_match`
recovery folded into the continuation line. The document view remains assembled
on read by the one composer.

**Delivered surface (F10).** The product surface tested for F10 is the MCP
server plus the installer-managed pre-read notice in `docs/agents-snippet.md`.
The bare server is a component, not the product: the evidence records zero of
five first-move use with bare registration and five of five with the installed
notice. F10 states the condition; this section owns the configuration that
demonstrates it.

**Context-bound create.** The service chooses `ContextBoundTarget` or
`ExplicitTarget` once from the context origin (FD-30). The adapter does not
infer it.

**Derived create surface.** `_resolve_create_surface` is the one resolver; the
service passes its key to `record_command` as `derived_surface`. The three
surface rejection causes are the FD-30 cases.

**Flat create.** The service derives one complete semantic `EvidenceScope` from
the question context or explicit paths/locator/FILE surface and passes it to
`flat_conclusion`, owner resolution, and `record_command(derived_scope=...)`.
The canonical `ExplicitTarget` uses that carrier, never raw wire scope again.
Owner agreement projects the complete semantic scope through
`containment.scope_surfaces` and validates every member with
`containment.surface_contains`, including path-surface self-membership (FD-5).
Support dependencies never participate in owner agreement.

**Reconsider scope preservation (FD-17, FD-59).** Discovery impact checks use
`evidence_scope_contains` over the complete observation scope. Challenge contexts
union the complete version scope with actual owner/evidence requirements through
`evidence_scope_union`; exact references are never flattened into paths.

**Scope algebra and context derivation (FD-59).** Canonical pure
`evidence_scope_contains` and `evidence_scope_union` live alongside
`evidence_scope_allows` in `core/model/primitives.py`. Empty scope is
repository-wide; it absorbs union and cannot fit inside a restricted outer
scope. Union deterministically preserves paths and exact references. Only
actual requirements participate; absent optional data is not an empty operand.
`_resolve_record_request` remains the sole context builder. It unions complete
semantic/version scopes, direct evidence, action scopes, and complete discovery
boundaries. Context-free discovery with context-admitted reference strings
rejects before context issuance; references are never globally resolved.
Source admission checks locator membership for restricted contexts. Discovery
checks full containment before inventory. EvidenceService keeps its admission
backstop. Neither path widens a supplied context.

**Surface conflicts.** `SurfaceConflict` carries the current boundary version.
`put_surface` and `update_surface` raise it for a kind conflict, a changed
boundary under the existing version, and a stale compare-and-set. The service
maps it to `Rejected` with `current_boundary_version`. `LifecycleStoreError`
stays for operational store failures and maps to `Unavailable`.

**Parent validation.** `_require_valid_parent` is the single validator for
create and update; it enforces the parent rule in `lifecycle-contract` §4.2
(declared parent, same repository, no self-parent or cycle).

**Verification scope.** The run's `scope_paths` remains the applicability key.
`AnswerService` selects runs whose scope matches the asked surface. No new
carrier and no widening by a broader question.

**Test ownership.** Typed rejection cases live in
`tests/unit/test_lifecycle_surface.py` and
`tests/unit/test_lifecycle_service.py`; `Gap.recovery` and document-view cases
live in `tests/unit/test_answer_service.py`; context-bound and surface-conflict
cases live in `tests/unit/test_lifecycle_service.py` and
`tests/integration/test_lifecycle_mcp.py`; description and snippet cases live in
`tests/unit/test_surface_conformance.py`, `tests/unit/test_agents_snippet.py`,
and `tests/unit/test_skills.py`.

## 10. Schema-11 layout and indexes

**Authority:** FD-1–FD-8, FD-30, FD-35–FD-36, FD-42–FD-48.

Keep SQLite and `shell/sqlite_store/lifecycle.py` as the transaction owner.
Canonical JSON remains the payload; relational columns/indexes project its keys.
The proposed physical changes are:

| Storage owner | Key/index change | Canonical payload / treatment |
| --- | --- | --- |
| `surfaces` (new) | repository plus canonical surface key; declared-name uniqueness and kind-conflict validation | `Surface`, including boundary and parent reference; no persistent currency flag |
| `understandings` | add owning surface reference and unique repository/surface/question index | adapt `Understanding`; preserve stable IDs and version pointers |
| `understanding_versions`, `conclusions`, `understanding_membership` | retain immutable revision and membership keys; bind ownership through the understanding | adapt canonical payload references; no duplicated conclusion bodies |
| `investigation_contexts` | retain repository/request uniqueness; adapt binding digest inputs | existing context carrier with surface-aware scope; remove budget input from binding |
| `record_receipts` | replace repository/context/submission key with repository/request key | adapted acceptance identity, digest, effects, and expiry; no cascading dependence on live context |
| `support_dependencies` | retain reverse index and exact revision keys | project dependencies from canonical revisions in the acceptance transaction |
| source/discovery observations, challenges, verification runs | retain canonical records and their reference integrity | only required ownership/identity adaptations; run-ingress mapping is the resolved O-7 path recorded in §12 |
| `meta` | advance expected schema to 11 | existing runtime format check; no migration on ordinary open |

Resolve path containment from canonical boundaries and existing inventory/locator
capabilities. Compute surface status on read; do not add a second maintained
containment graph, status ledger, or document store. Indexes can accelerate exact
lookups but cannot define semantic ownership.

**Boundary updates (O-8).** The update input is the declared surface carrying the
new boundary and `expected_boundary_version`; a mismatch rejects the write with
the current version (FD-46). One transaction appends an immutable
`surface_boundary_versions` row `(surface, boundary_version, boundary_json,
digest)` and advances the surface's current pointer. Each understanding version
records the `surface_boundary_version` it was assessed against, so a historical
reference identifies the boundary it describes. FD-35–FD-36 govern history, and
no second containment graph or status ledger is introduced.

Schema fixtures must exercise foreign/cross-repository references, overlapping
boundaries, conflicting kinds, duplicate creates, and referenced history. O-4
blocks the old-row backfill; adding nullable runtime surface ownership is not a
transition solution. Exact DDL is verified with those fixtures before activation.

## 11. Read composition and change traversal

**Authority:** FD-5–FD-29, FD-54–FD-57.

Resolve the canonical surface in the answer composition. The recorded question
is the membership key: FD-25 makes `no_match` the result when understanding
exists for the surface but not for that question, so lexical candidate ranking
is retired with the candidate result. Build the operation result from exact
membership plus shared support evaluations; the 0.9 snapshot projection is not
the new answer composer. The no-question view uses the same composition path,
grouped by recorded question, rather than another writer or stored rendering.

The read composer returns historical `Gap` content through
`HistoricalConclusion` and stale surface references through
`StaleConclusionRef`; both are read-time projections over stored revisions, not
a second stored shape. Verification applicability uses the shared containment
rule: a run applies when the asked surface is within its declared scope, and a
single-file run is not widened to a broader service.

Implement one containment resolver shared by query resolution, status, and
change mapping. Add `service/reconsider.py` for the operation composition. Use
`source_observation_ids_for_locator` and `support_dependents` as lookup building
blocks; expand premise references through a visited-set worklist to a fixed
point. Resolve owning surfaces after dependency traversal, not only through the
changed path's boundaries. Group the result by canonical surface key, collecting
reason sets and stable recorded sequence information. No swallowed lookup failure
becomes an empty affected set. The unresolved state selection is O-5.

Represent individual failing dependency evaluations in the canonical support
carrier. Reuse the core precedence calculation after collecting those results;
do not recover dependency identities by parsing `_revision_eval`'s reason text.
Use the same evaluator for reads, writes, verification qualification, and notices.
Range binding follows FD-18; delivered excerpts alone do not prove a reliable
range identity and do not justify widening the implementation into a new parser.

## 12. Acceptance, replay, and transition composition

**Authority:** FD-2–FD-4, FD-30–FD-41, FD-46–FD-48; L4, L7.

Extend `RecordingIdentity`, its wire ingress, receipt selectors, and store port
together. Retain `receipt_decision` and the existing `BEGIN IMMEDIATE`
transaction. Both service lookup and in-transaction lookup address the adapted
request key; neither derives a new retry identity from a fresh context. Derive
understanding IDs through the core identity owner, while the surface/question
unique index enforces creation arbitration.

**Compact update grammar.** `RecordActionsWire` carries action-specific compact
deltas (`AddConclusionWire`, `ConfirmConclusionWire`, `CorrectConclusionWire`,
`ReplaceActionWire`, `WithdrawActionWire`) rather than a full conclusion
snapshot. The public caller supplies no new conclusion lineage identity on
create, `add`, or `replace`; `span.core.identity.conclusion_identity` derives it
from `(repository_id, request_id, role, ordinal)` for roles `create`, `add`,
and `replace`, projected as `c:<digest>`. The function is pure and replay-stable;
no database allocator, counter, context, version, or source content participates.
`LifecycleService.record()` reads the exact understanding version the caller
names, derives the old revision identity, the unchanged assertion nature or
scope, the mechanical basis, and the complete supplied support, and builds the
existing canonical action carriers and `UpdateUnderstandingCommand`. The
existing atomic store transition and compare-and-set remain the only acceptance
owner; no second command representation, grammar, or writer is introduced.

Compute the original wire digest and call `_replay` before any context or
evidence work, for both understanding and verification. Reuse `receipt_decision`.
`CONTEXT_BINDING_CONFLICT` and `CONTEXT_SCOPE_CONFLICT` have canonical actions;
context binding is not a version conflict.

Compose internal context issuance and `EvidenceService` admission inside the
operation service, after receipt lookup. There is no required public admission
or context-fetch step. Candidate-specific host identity preservation remains
O-6. On conflicting updates, carry the observed current version as structured
rejection data rather than requiring the caller to parse an exception sentence.

**Verification ingestion (O-7).** A run cites the `SourceObservationId`s the
independent run actually exercised. Those are the observations admitted for the
operation's context: the context returned by a preceding `ask`/`reconsider`, or
the locators/ranges the operation admits internally before recording. The service
stores those exact IDs with the run, so the run names what it actually exercised.
The wire accepts `run.observations` and/or `run.evidence`; evidence locators are
admitted before the same command path. No separate public admission step and no
inferred run provenance is introduced.

Split the core confirm/correct branches in `_apply_action`. The service supplies
the prior and newly observed support needed by FD-31; the core transition selects
the appropriate effect. The store can persist a receipt for a no-op result without
writing an unnecessary revision/version. Test that path with both identical retry
identity and a new intentional identity. Preserve challenge dispositions through
the existing atomic transition owner.

**Live owner status (FD-60).** One functional `service/surface_status.py`
composer owns the existing AnswerService algorithm. Both ask and understanding
record qualification use it. `UnderstandingRecorded.status` is `SurfaceStatus`
or transient `SurfaceStatusUnavailable(reason, surface?)`; neither is persisted.
Expected operational read failures preserve accepted receipts; programming and
contract defects are not normal unavailability. `LifecycleStorePort.operational_errors`
is the store-owned classification of operational exception types; SQLite declares
`LifecycleStoreError` and `sqlite3.OperationalError`. Post-commit qualification
catches those types and provider `OSError` independently for support and status,
without importing the SQLite shell into the service or catching every `ValueError`.
Status coverage retains complete conclusion scopes and checks members through
canonical scope containment: exact refs do not imply repository-wide coverage.
A repository-wide semantic scope cannot agree with a FILE owner. Surface declaration receipt
semantics are outside this remediation.

Use the reverse dependency index to compose FD-37 effects against the accepted
transition. Store immutable acceptance facts in the receipt, and expose the
affected references through the canonical recorded result. Live support and
surface status remain freshly qualified, not cached truth inside that receipt.
The result representation must preserve known committed acceptance even if
post-commit qualification is unavailable. This is a schema/probe obligation in
§9 and §15; a generic rejection cannot represent it.

## 13. Operational lifetime and bounded results

**Authority:** FD-42–FD-45, FD-54–FD-57.

Keep `LifecycleRetention`, injected clocks, and the operational reaper. O-2 owns
the evidence for deployment durations; the one-day/seven-day defaults are not
silently adopted. Define request/context/receipt recovery at both sides of expiry
in the schema fixtures. Do not copy the old plan's expired-context safety claim
onto a different request-key protocol without checking its actual lifecycle.

Retain accepted semantic history and its referenced observations. No new history
reaper is selected by this design. If one is separately justified, extend the
existing persistence owner with the FD-44 cases and a reference-safe lifecycle;
do not infer that requirement from an operational TTL.

Move response budgeting from public request carriers into the existing composition
boundary. Continue using core paging and `_fit_result` mechanisms where applicable,
but fit every new result variant through its canonical projection. O-3 supplies
per-host values. Include omitted identities and recovery references in the fitted
result; those references resolve through `ask(reference)`, with no public budget
or new retrieval family. No response-size limit is allowed to change support
classification or hide a traversal limit.

**Implementation state (2026-11-01).** All public request carriers are free of
response budgets and traversal bounds; services apply the server-owned policy.
`AnswerService` fits every result variant, names each omission, and refuses a
budget below the minimum result. Expiry and restart fixtures cover context,
receipt, and accepted-history survival. The O-2 duration and O-3 per-host value
remain unmeasured, so FG-4 stays `OPEN`.

## 14. Offline schema-10 transition

**Authority:** F3, F7, L4; FD-1, FD-6, FD-35–FD-36, FD-42–FD-45.

Extend `shell/store_transition.py` and the existing installer transition command.
The current `SUPPORTED_SOURCE_SCHEMAS` contains 7–10, and staging imports binding
and seeds into an otherwise empty schema-11 store. A schema-10 input needs its
own mapping and staged verification; the old export mechanism alone is not that
mapping. Retain historical old-format exports without a second active decoder
or semantic writer in the MCP runtime.

**Schema-10 mapping rule (O-4).** Each schema-10 understanding maps to the path
surface named by its recorded `EvidenceScope` when that scope names exactly one
path that is a file. A scope naming several paths, none, or a directory is
classified `unresolved` with reason `scope does not identify one file surface`,
and preserved in the archive; no service or domain surface is inferred from an
evidence scope, and no conclusion is split across surfaces (FD-6). A receipt
identity maps through its context's recorded request identity; a receipt whose
context is gone is preserved as unresolved with its recorded digest and effects.
The persisted `$type: Gap` tag maps to `RecordedQuestionGap` during staging; no
runtime alias or second decoder is retained.

The transition specification must enumerate each schema-10 table and classify its
rows as preserved canonically, mechanically transformed with verified references,
or unresolved with a named reason. Record source IDs, target IDs, counts, hashes,
and the provenance of each mapping. Surface assignments and old receipt keys are
O-4: this document does not choose a fabricated service, domain, or request ID.
An incomplete mapping cannot activate the new runtime or silently downgrade
accepted understanding to an empty active store. Any proposed different
preservation policy requires the owning authority decision first.

**Implementation state (2026-11-01).** Schema 10 is accepted by the existing
transition path. `shell/store_transition_schema10.py` performs the raw per-table
mapping, records `mapping.json` with source/target identities, counts, hashes,
and provenance, and verifies counts and every source/discovery/premise
reference before activation. Schemas 7–9 keep their export-only treatment. A
disposable-store fixture covers understandings, versions, conclusions, gaps,
challenges, verification runs, and mapped receipts. No live user store was
transitioned and the per-table mapping still needs its owner review.

Reuse inspect/archive/export/stage/verify/activate/rollback and the manifest
owner. Add schema-10 fixtures for nonempty understanding history, cross-surface
premises after assigned mapping, outstanding challenges, verification runs,
retained/expired receipts, and restart after interrupted staging/activation.
Verify archive integrity, reference reconciliation, new-format writes on rollback,
and active-writer refusal. Prior journal/platform observations remain limited to
the platforms tested. Ordinary store open still only checks format; transition
execution against any user store is outside this documentation change.

## 15. Host delivery, assets, and measured fitness

**Authority:** FD-38–FD-41, FD-49–FD-58; F7, F8, L8.

Keep stdio transport and the existing host adapters. Select registered variant
splits only from captures of the generated §9 candidate, including required error
and post-commit-result branches. Capture exact source/build/schema digests,
host/model/version, delivered declarations, calls/replies, request-identity
preservation, retry/restart, and truncation. A callable tool with opaque required
fields is not complete declaration evidence. O-6 remains open until the actual
identity owner and delivery boundary are observed.

Record the supported host set before evaluation. Historical Codex/OpenCode runs
retain their original scope; no broader support claim follows from this
document. Measure result-size limits
and supported suspension bounds for O-2/O-3. An unbounded or unobservable host
resume horizon needs an explicit supported-recovery decision, not an invented
finite measurement.

Update `skills/`, `docs/agents-snippet.md`, affected public guides, registration
descriptions, and installer-owned assets with the new binary/schema cutover.
Generate packaged copies from their canonical sources; preserve foreign host
configuration. Test installation/reconnect using isolated profiles and disposable
stores. Updating source does not claim deployed host-local copies changed.

**Adoption notice (FD-58, 2026-11-03).** Two mechanisms are required, and the
first is the actual cause of the first-move failure: OpenCode dispatches the
first model request before a local MCP server has connected (the first request
carried 66 tools with no Span; the second carried 69 with all three). The plugin
therefore registers `session.hook("prompt")`, which waits a bounded three seconds
until a Span `_ask` tool appears in the tool list, then proceeds whether or not
it did. Without that wait the agent cannot ask before reading even when it
intends to. The notice itself is delivered through `session.hook("context")`:
the plugin calls `span-hooks adoption-primer --repo-root <root>`, which prints
the notice only when that repository has at least one recorded understanding.
The plugin pushes the text into `event.system` once per session and stays silent
on any failure. The text names the direct tools, asserts existence rather than
currency, and names no surface. The installer deploys the plugin under Span's
own data root and registers it once in the host's global `opencode.json`; it
never writes the plugin into a target. Codex continues to use the managed
`AGENTS.md` block. The notice's bytes are counted in the F8 class measurement.
FD-53 applies: the notice is not claimed delivered until captured. An edit-time
notice is computed on a tool edit, held once per session, and delivered by the
next `context` hook; it names the changed paths and the exact
`reconsider(changed_paths=[...])` call. It asserts support state only and is
silent on failure.

**OpenCode plugin scope (0.9.4).** The lifecycle plugin is managed under an
explicit `--opencode-plugin-scope global|local|none`; the installer never infers
the scope from disk. `global` deploys the canonical plugin and reports a
conflict when an explicitly inspected target contains another Span plugin; it
does not move or delete that target-owned artifact. `local` and `none` remove
Span's global registration and leave target plugins to the user, reporting each
copy. Receipt targets not selected with `--repo` are inspected read-only and
yield `conflict`, never `wired`. A fresh install defaults to `global`; an
upgrade uses the current receipt's scope and a receipt with no unambiguous scope
stops and names the flag. The authoritative full scope matrix is in
[install](install.md#opencode).
Foundations §1 binds the MCP **server**, which still makes no target edits; host
integration and the upgrade migration are installer behaviour. Under the global
scope, the installer uses that same fixed global configuration for the MCP
registration unless an explicit, prior-receipt, or local MCP path takes
precedence. Selected paths are absolute receipt identities; an explicit
relocation removes the prior Span registration after the new registration
succeeds. The receipt retains the MCP and plugin configuration paths independently; doctor reuses the
recorded MCP path and uninstall removes each owned artifact from its recorded
configuration. See
[install](install.md#upgrading-from-09091).

**Measured 2026-11-03 (OpenCode):** with the readiness wait and the notice,
**5/5** clean runs put the first `ask` before the first source read; without the
wait the first tool list had no Span and the rate was 2/5. Evidence:
`.context/evidence/fitness/2026-11-02-three-tool/natural-use/F10-2026-11-03.md`.

Retain the
[2026-10-30 rebuild plan §10.4 comparative protocol](../.context/plans/2026-10-30-span-lifecycle-rebuild-implementation-plan.md#104-comparative-fitness-protocol-and-binding-decision)
as an evaluation mechanism, with G5/F8 remaining the product authority. The
[2026-11-01 implementation plan, FP-7](../.context/plans/2026-11-01-implementation-plan.md#fp-7--product-fitness-and-completion)
owns the new candidate's frozen-manifest and evidence references. Identify the new
candidate and freeze its workloads and decision rule before scoring. Record cold
capture, fresh reuse, change/re-establishment, recovery, and failed attempts;
separate mandated conformance from natural use. No telemetry service or new
numeric acceptance threshold is introduced. §8's historical calibration is not
scored evidence for this candidate.

**Core-value and cost (2026-11-02, extended 2026-11-03).** F8/G5 requires both
halves: retained, current, reusable understanding with exact change isolation,
*and* a per-class comparative cost result measured in the same unit. The
scorecard is `.context/evidence/fitness/2026-11-02/CORE-VALUE.md`; the cost
classes are `five-task/MATRIX.md` and `g5/REUSE.md`. Cost is reported per named
class, never as a universal ratio; the single-use cross-file class is negative.

**Frozen candidate manifest (2026-11-03).** The scored surface is frozen in
`.context/fitness/2026-11-03-post-fix-candidate-manifest.json`. The
2026-11-02 candidate and core-value manifests, the 2026-11-03 pre-fix manifest,
and the 2026-11-01 manifest are `VOID`: their host scope or request schema no
longer matches the delivered surface. The post-fix manifest freezes the three
tools and their request schemas and carries no cost numbers; the measured
classes attach to the pre-fix surface they were run on. FG-7 stays `OPEN` until
the F10 adoption receipt exists.

## 16. Verification ownership and completion

The forward plan owns execution dependencies and receipts. This matrix maps
FD coverage to mechanisms and the existing test owners to extend; it is not a
second declaration of those requirements.

| Authority | Mechanism section | Test owner / required scenario family | Present status |
| --- | --- | --- | --- |
| FD-1, FD-5–FD-8 | §10–§11 | `test_lifecycle_store.py`, `test_answer_service.py`; identity, boundaries, ownership, overlap, partial inventory, computed `unexamined`, descendant status | computed status tested; boundary enumeration is store-known members with the limit reported |
| FD-2–FD-4 | §9–§12 | `test_lifecycle_service.py`, `test_lifecycle_store.py`, `test_record_wire.py`; new request key and restart/expiry | old-key baseline only |
| FD-9–FD-16 | §9, §11 | `test_support_service.py`; dependency findings, mixed states, withdrawal, cycles | adapt; O-5 AMBIGUOUS |
| FD-17–FD-22 | §11 | `test_reconsider.py` plus the installed MCP lane; cross-boundary closure, bounded traversal, challenge raise | bounded walk and `Challenged` tested; live lane revalidation is FP-6 |
| FD-23–FD-29 | §11 | `test_answer_service.py`; mixed-support answers, gap variants, ambiguity, document view | candidate tests added |
| FD-30–FD-37 | §10, §12 | `test_lifecycle_service.py`, `test_lifecycle_store.py`; duplicate create, confirm no-op, dependent effects, disputes | dependent effects named on the receipt; tested |
| FD-38–FD-41 | §9, §12 | `test_record_wire.py`, `test_lifecycle_surface.py`, `tests/integration/test_lifecycle_mcp.py`; closed unions, rejection identity/action/version, post-commit failure | closed `RecordResult`/`ReconsiderResult` wired; rejections carry identity, action, current version |
| FD-42–FD-45 | §13–§14 | `test_lifecycle_store.py`, `test_store_transition.py`; expiry boundaries, restart recovery, and preserved references | O-2 settled at a 7-day replay promise / 1-day context; expiry and replay tested |
| FD-46–FD-48 | §10, §12 | `test_lifecycle_store.py`; concurrent first write, duplicate create, CAS and replay | request-key tests added |
| FD-49–FD-53 | §15 | `test_host_contract.py`, `test_installed_mcp.py`, raw live-host capture | the three-tool surface is implemented and locally gated. 2026-11-07: OpenCode delivered the valid compact create/add/correct/replace lifecycle but removed an unknown old-form field before delivery; Codex delivered a current-candidate smoke create with a derived identity; Claude remains unverified. Strict unknown-field preservation through OpenCode is not established |
| FD-54–FD-57 | §13, §15 | `test_answer_service.py`; result fitting, explicit omission, minimum-result refusal | O-3 measured per host and applied as the delivered-wire budget |
| FD-58 | §15 | `test_lifecycle_hooks.py`, `test_install.py`, `test_skills.py`; notice only with understanding, plugin deploy/remove, skill vocabulary | 84 input tokens per session; OpenCode first `ask` before first source read 5/5; Codex pending |
| F1, F7; verification variant in layer 2 §4.2 | §9, §12 | independent run before source mutation, then ingestion/reuse with original observation identity | O-7 resolved for source-observation ingestion; external execution authenticity remains a separate, not-yet-designed workstream |
| F8, G5 | §15 | frozen comparative task captures and scorecards | core value accepted on Codex and OpenCode (retained, current, reusable understanding; exact change isolation). Two reuse classes are positive with capture counted (break-even 2 and 11); the single-use cross-file class is negative (1.74× billed). No universal cost claim |

Part B is complete only after its executable contracts, reviewed migration
mappings, authority decisions, and measured deployment inputs are present.
Implementation/host/fitness passes need their own observed receipts. Writing this
matrix, or passing the 85 baseline tests in §8, closes neither category.
