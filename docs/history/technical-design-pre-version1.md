# Historical technical-design record — pre-Version 1

> **Document role: historical design evidence.** This file preserves the former
> Part A of the binding technical design: baseline comparison, retention
> decisions, work-package framing, resolved/open observations, and historical
> evidence limits. It is not current Layer-4 authority.
>
> Current mechanism authority is [technical-design.md](../technical-design.md).

The material below is preserved substantially as it stood before the F14
documentation restructuring. Dated implementation/status statements retain
their historical meaning and must not be read as the current Beta-3 baseline.

# Span technical design — layer 4

**Status: stated decisions are binding; historical unresolved items remain
explicitly scoped. Version-1 Part C mechanisms are implementation-complete
through T10; T13 owns assembled-candidate release verification. Post-release
Beta use owns ongoing product-value validation.**
This is layer 4. It records the implementation baseline, what is retained from
the historical codebases, and the mechanisms that realize layers 0–3. Historical
open items in §6 do not override the Version-1 Part C implementation status
unless Part C explicitly cites them. It chooses mechanisms; it adds no product
requirement. Where it conflicts with a higher layer, the higher layer governs.

**Historical release identity (2026-11-07).** That capture identified **0.10.0**
(2026-11-07), a public-grammar and identity-ownership release over 0.9.4. The
prior internal pre-release artifacts were withdrawn and were never public.
References below to the withdrawn internal baseline describe that artifact, not
the public release.

**Baseline measured at:** withdrawn internal baseline = repository revision `aa580b3`; 0.8.3 = tag
`v0.8.3`. Counts below are measurements of those trees, not estimates.

**Review update: 2026-11-01.** Part A (§1–§8) records source assessments;
Part B (§9–§16) records implementation choices. Authority and migration decisions
are recorded in §6, §10, §12, and §14 (see §6, resolved 2026-11-01); the
remaining historical evidence items are delivery and measurement (O-2, O-3,
O-6), which later release plans may supersede or close. Part B is **PARTIAL**: no runtime, schema, host configuration, or
release is changed by this document.

The [requirements pyramid](requirements-pyramid.md) governs placement and
precedence. Product and behavioural rules remain in layers 0–3; this document
cites their IDs instead of defining replacements. Current Version-1 execution ordering and gate ownership live in the
[1.0.0 Beta implementation plan](implementation-plans/1.0.0-beta.md).

**0.10.3 target amendment (2026-11-14).** Active mechanism choices below follow
the amended lifecycle/functional contracts. Its dated runtime, host-delivery,
and comparative-acceptance statements are historical evidence for that candidate,
not current Version-1 release gates.

**Version-1 Functional Pyramid amendment (2026-11-21).** Parts A/B remain the
historical/current Span mechanism baseline. Part C (§17–§22) is the binding
Layer-4 mechanism amendment for the Version-1 Functional Pyramid target and
supersedes any earlier mechanism statement where the new FD-61–FD-94 contract
changes that boundary. It preserves the existing semantic lifecycle mechanisms
and adds only the storage, resolution, support and public-projection machinery
required by Layers 0–3.

**Version-1 implementation update (2026-11-23).** T01–T10 implemented and
verified the Part-C mechanisms and generic functional acceptance on the
reconciled release branch. T11 external integration acceptance passed and is
closed. T13 owns assembled-`1.0.0b1` release verification, candidate-specific
managed-host qualification where claimed, and the Part-C derivation audit.
G5/F8 product-value validation continues after release through real integration use;
it is not a publication gate.

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
`SurfaceBoundary`, `SurfaceStatus`), schema 12 tables, a containment resolver,
path and declared surfaces, `unexamined`, and descendant status.

A schema-12 transition path is required at the same boundary; see §14 and O-4.

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

### O-1 — Withdrawn premise (resolved and implemented)

FD-13, FD-19, and FD-34 govern. `support_rules.premise_membership_state`
distinguishes withdrawal from supersession, and `SupportService._premise_eval`
detects a `WithdrawnConclusion` before evaluating the referenced revision.
`test_premise_withdrawal_is_unverifiable` verifies the distinction. The
earlier proposal to amend layer 3 to preserve the old behaviour remains
withdrawn; no higher-layer amendment was required.

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
Claude has supported registration, inspection, skills, and lifecycle
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
- Replace the retired tool inventory with the three lifecycle operations.
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

Historical host evidence is retained as internal working evidence, including
the withdrawn beta ledger and the 2026-10-31 G-0 capture. Those private captures
are not public repository links. A fixture README's `UNVERIFIED` label does not
erase those captures, and those captures do not establish delivery of a
different grammar.


## Historical Part-B material removed from active Layer 4

The following sections were retained during the F14 technical-design cleanup
because they contain dated candidate evidence, superseded transition targets, or
verification-state material rather than current mechanism authority.

### 9.1 Delivered public surface (2026-11-02; historical)

This dated subsection records that delivered candidate. The current target
operation contract is lifecycle §4.1–§4.3 and its implementation choices are §9.2.
Do not use the old shapes below to generate new schemas or guidance.


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

### 9.3 Release and consumer compatibility disposition — 0.10.3

The release identifier remains the user's selected **0.10.3**. This is a bugfix
release with intentionally breaking request grammar; it is not described as a
backward-compatible protocol patch. Repository release mechanics are owned by
contributing.md §Releases. No unrecorded version-number compatibility guarantee
is inferred, and no version metadata is changed by this documentation amendment.

| Consumer | Required delivery before release |
| --- | --- |
| MCP tool clients (Codex/OpenCode/Claude where support is claimed) | Refresh tools/list against the same candidate; replace retired input grammar; capture actual branch delivery and results |
| Managed skills, snippet and lifecycle notices | Ship the same surface-only obtain, direct-capture and bound-context grammar through existing packaging/install owners |
| Existing configured/running MCP processes | Resolve pending accepted outcomes before upgrade; restart/reconnect and refresh cached schemas; do not silently run old and new grammar as peers |
| Direct/custom clients | Explicit protocol upgrade required; reject retired fields through the canonical decoder with actionable new-schema guidance, not aliases |
| Retained receipts, revisions and contexts | Preserve store identity/history and promised retention; use existing exact audit selectors for old acceptance, bound references for still-live contexts; no re-execution or store migration inferred |

The supported delivery boundary is one identified package candidate plus its
managed projections and a refreshed host session. Source declarations or prior
host captures alone do not certify it. Existing packaging/install owners deliver
the managed assets; candidate-specific captures verify each claimed host. Unverified host versions are reported
as unverified; no new compatibility parser, pinned old semantic writer or shape
adapter may compensate. Failure to deliver this boundary blocks publication,
not the structural contract correction.

Preserve replay meaning through original repository/request keys and full
immutable receipts. Before a grammar switch, resolve accepted old operations
through their retained receipt selectors. Do not re-encode a historical write
as a new one or assume a new wire digest equals the old request. New direct
writes still use stable caller-owned identities. Registration refresh and
publication require separate authorization; this disposition performs neither.

## 14. Offline schema transition

**Authority:** F3, F7, L4; FD-1, FD-6, FD-35–FD-36, FD-42–FD-45.

Extend `shell/store_transition.py` and the existing installer transition command.
For 0.11.0 the target is schema 13 and `SUPPORTED_SOURCE_SCHEMAS` contains
7–12. The runtime never migrates at open. Historical schemas 7–9 retain their
export-only treatment; schema 10 and 11 keep their documented semantic mappings
into the current target; schema 12 has the dedicated mapping below. Retain
historical old-format exports without a second active decoder or semantic writer
in the MCP runtime.

**Schema-12 to schema-13 mapping (0.11.0).** Schema 13 changes the meaning and
name of the context digest from whole-request `request_digest` to the canonical
`binding_digest` defined in §9.2. A schema-12 context cannot be mechanically
rebound because the persisted row does not retain every original source
selection. Therefore the transition is an offline drain, not a context rewrite.

Before staging, inspect every schema-12 `investigation_contexts` row. Refuse
while any context is `LIVE` and either has no expiry or has an expiry at or
after the transition clock. Expired or non-live contexts do not block the
transition and are not copied. The staged schema-13 store copies every repository
and durable semantic/audit table for the selected repository, including source
and discovery observations, surfaces and boundary history, understandings,
versions, conclusions, support dependencies and membership, challenges,
verification runs and verification-observation membership, and retained
`record_receipts`. It deliberately copies no `investigation_contexts`,
`context_evidence`, or `context_discovery_evidence` rows. Receipt
`RecordingIdentity.context_id` values remain immutable historical coordinates;
they do not require the operational context row to survive (FD-42).

The mapping artifact classifies those three context tables as
`drained_not_copied` and every other target table as `preserved`, recording
source/target counts. Verification requires zero staged operational contexts,
exact preserved counts, SQLite integrity, support/dependency reconciliation,
verification-observation references, and every receipt's accepted understanding,
challenge and verification references. A refused drain leaves schema 12
untouched. Rollback before schema-13 writes restores schema 12 through the
existing owner; after schema-13 writes the existing rollback preservation rule
keeps the new-format store rather than discarding accepted writes.

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
the lifecycle notice for every registered operational repository, including
a cold repository.
The plugin pushes the text into `event.system` once per session and stays silent
on any failure. The text names the required lifecycle actions and direct tools, and makes no
claim that retained understanding exists or is current. The installer deploys the plugin under Span's
own data root and registers it once in the host's global `opencode.json`; it
never writes the plugin into a target. Codex continues to use the managed
`AGENTS.md` block. The notice's bytes are counted in the F8 class measurement.
FD-53 applies: the notice is not claimed delivered until captured. An edit-time
notice is computed on a tool edit, held once per session, and delivered by the
next `context` hook; it names the changed paths and the exact
`reconsider(changed_paths=[...])` call. It asserts support state only and is
silent on failure.

**0.10.2 pending notice lifecycle.** Extend the existing pending notice with the
paths of its producing edit event; do not create a session edit ledger. Native
lifecycle events use `data.sessionID`. Idle refresh forwards unconsumed paths as
`[{"file_path": path}]` to the stop runner's JSON stdin. Successful context
injection consumes the notice; failed injection/reporting retains it. Deletion
and plugin disposal clear notice state. The existing bounded notice cache reaps
abandoned entries with an explicit diagnostic at capacity. A missing session ID
is diagnosed; no shared cross-session fallback is used. Previously delivered
notices are not replayed at idle. Answer support remains checked by operations.

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

Retain comparative measurements as optional product research, not as a
Version-1 release gate. G5/F8 are demonstrated for Beta through real integration use
on ordinary engineering work. The pre-release candidate must still pass the
deterministic contract, packaging, migration, recovery, public-boundary, and
functional-acceptance gates; Beta publication does not wait for an artificial
equivalent-task score.

Post-release evaluation should capture the product behavior that matters in
practice: cold investigation, fresh-session reuse, implementation and governance
changes, re-establishment, recovery, and failure. Findings from that use are
inputs to follow-up Beta patches. No telemetry service or numeric acceptance
threshold is introduced.

Historical comparative captures from 2026-11-02/03 remain calibration material
only. They do not certify Version 1 and they are not required to publish it.
Any future public time/token/cost claim must be supported by evidence scoped to
that claim.

## 16. Verification ownership and completion

The forward plan owns execution dependencies and receipts. This matrix maps
FD coverage to mechanisms and the existing test owners to extend; it is not a
second declaration of those requirements.

| Authority | Mechanism section | Test owner / required scenario family | Present status |
| --- | --- | --- | --- |
| FD-1, FD-5–FD-8 | §10–§11 | `test_lifecycle_store.py`, `test_answer_service.py`; identity, boundaries, ownership, overlap, partial inventory, computed `unexamined`, descendant status | computed status tested; boundary enumeration is store-known members with the limit reported |
| FD-2–FD-4 | §9–§12 | `test_lifecycle_service.py`, `test_lifecycle_store.py`, `test_record_wire.py`, `test_store_transition.py`; canonical request binding, restart/expiry and schema transition | 0.11 canonical `ContextBinding`, caller request identity, replay/restart, schema-12 live/no-expiry refusal and exact post-cutover receipt/run retrieval verified |
| FD-9–FD-16 | §9, §11 | `test_support_service.py`; dependency findings, mixed states, withdrawal, cycles | adapt; O-5 AMBIGUOUS |
| FD-17–FD-22 | §11 | `test_reconsider.py` plus the installed MCP lane; cross-boundary closure, bounded traversal, challenge raise and re-establishment | bounded walk, fresh changed-support context, exact evidence membership, ordinary re-establishment and packaged challenge resolution verified; T08 comparative measurement remains separate |
| FD-23–FD-29 | §11 | `test_answer_service.py`; mixed-support answers, gap variants, ambiguity, document view | candidate tests added |
| FD-30–FD-37 | §10, §12 | `test_lifecycle_service.py`, `test_lifecycle_store.py`; duplicate create, confirm no-op, dependent effects, disputes | dependent effects named on the receipt; tested |
| FD-38–FD-41 | §9, §12 | `test_record_wire.py`, `test_lifecycle_surface.py`, `tests/integration/test_lifecycle_mcp.py`; closed unions, rejection identity/action/version, post-commit failure | packaged MCP exercises all declared result families including `Unavailable`; structural faults are typed `Rejected`, unknown tools remain transport errors, and malformed ingress is separately contained |
| FD-42–FD-45 | §13–§14 | `test_lifecycle_store.py`, `test_store_transition.py`; expiry boundaries, restart recovery, context drain and preserved references | expiry/replay verified; schema-12 live and no-expiry contexts refuse cutover without mutation; drained activation preserves exact retained receipt and verification history; interruption/rollback paths are verified |
| FD-46–FD-48 | §10, §12 | `test_lifecycle_store.py`, `test_lifecycle_service.py`; concurrent first write, duplicate create, CAS and replay | same-identity replay/conflict, receipt-first concurrent acceptance, and distinct request identities racing one expected version are verified |
| FD-49–FD-53 | §15 | `test_host_contract.py`, installed stdio lifecycle coverage, raw live-host capture | 0.11 packaged stdio exact selectors, public grammar, structural rejection and result families are verified. Candidate-specific managed-host schema/argument/server-receipt capture and session handoff remain T09 external acceptance; older host captures do not substitute for it |
| FD-54–FD-57 | §13, §15 | `test_answer_service.py`; result fitting, explicit omission, minimum-result refusal | O-3 measured per host and applied as the delivered-wire budget |
| FD-58 | §15 | `test_lifecycle_hooks.py`, `test_install.py`, `test_skills.py`; cold/warm lifecycle notice, plugin deploy/remove, skill vocabulary | canonical native/shell guidance, hooks, skills and plugin notice-delivery lane are verified; 0.11 candidate-specific managed-host native/search/shell captures remain T10 external acceptance |
| F1, F7; verification variant in layer 2 §4.2 | §9, §12 | independent run before source mutation, then ingestion/reuse with original observation identity | O-7 resolved for source-observation ingestion; external execution authenticity remains a separate, not-yet-designed workstream |
| F8, G5 | §15 | real integration use across the ordinary lifecycle; optional scoped comparative research | prior measurements remain historical evidence only for their named candidates. Version 1 validates practical value through post-release Beta use; no synthetic comparative score is required for publication |
| FD-61–FD-74, FD-86–FD-91 | Part C §17–§18, §20.1 | Functional Pyramid core/service tests plus installed MCP; FunctionalScope algebra, outside/covered/uncovered/mixed projection, overlapping/inherited/cross-repository graph resolution, deterministic provenance, health iff structural findings | implemented; T10 generic acceptance verified on exact-head CI, T13 re-verifies the assembled candidate |
| FD-75–FD-81 | Part C §18, §20.2–§20.3 | support/record/reconsider tests; FunctionalRouteSupport derivation/evaluation, authority separation, pre-existing normative activation effects, deliberate participation removal vs operational unavailability | implemented; covered by T10 generic acceptance, T13 re-verifies the assembled candidate |
| FD-82–FD-85, FD-93 | Part C §19–§20.4 | lifecycle store/service/schema tests; installation-level receipts, activation/revision/deactivation atomicity, participation effects, dependent effects, replay with fresh contexts, pyramid CAS and one-ACTIVE-instance uniqueness | implemented; covered by T10 generic acceptance, T13 re-verifies the assembled candidate |
| FD-92, FD-94; L8, L13–L16 | Part C §20–§22 | generated schema, MCP integration, hooks/skills and host capture; exact three tools, candidate/status/receipt selectors, FunctionalPyramidRecorded affected projection, result-driven initialization through DECLARE→reconsider/disposition→VALIDATE→ACTIVATE/REVISE→VERIFY→effect disposition and matching runtime qualification gates | implementation and generic installed-MCP evidence complete; candidate-specific managed-host delivery remains T13 |
| Functional design §15 cases 32–44 | Part C §18–§22 | generic acceptance plus installed MCP; outside scope, MIXED scope, structural health equivalence, activation of pre-existing normative understanding, participation-write propagation, deactivation/removal route state, replay/context recovery, concurrency, initialization re-alignment, conformance-as-NORMATIVE, accepted-non-current runtime gating and participation-write effect completion | T10 generic acceptance complete; T11 private acceptance passed; T13 reruns the assembled candidate |

The matrix covers both the established Part-B baseline and the Part-C
Version-1 target. Part-B historical/current mechanism claims remain governed by
their existing evidence and open measurements. Part C is design-complete because
its derivation map has no unmapped FD owner or unowned mechanism, and its
implementation is complete through the T10 generic acceptance evidence recorded
above. Candidate-specific managed-host delivery remains unverified unless separately
claimed, and final Part-C derivation re-verification remains release-verification
work. G5/F8 product-value validation is post-release Beta work and does not
reopen the implemented mechanism or block publication.
