# Span onboarding runbook — new-user semantic extraction (Addendum E E-12)

Canonical path for an exact user-supplied target. Steps and stopping
conditions are copied from `docs/semantic-governance-addendum-e.md` §§4A
and 6. Guides describe; they never define semantics. No new operation,
store, writer, score, or background process is introduced here; target
accounting uses the canonical target-association/result contract.

## 0. Preflight (host, fail closed)

Confirm and record: installed Span source revision, registered host, data
directory outside every target repo, and the exact repository root.
Installation provisions the managed structural indexer, so no separate
indexer download is needed — no separate structural server is
registered; structural navigation is served by Span itself under
Addendum F. Missing prerequisites stop the run. Record the
preflight in the receipt and acceptance evidence with a target artifact
snapshot proving the target tree is unchanged.

## 0.1 Authority seeds convention

Governing sources enter only as user-supplied seeds, never invented by
Span or the installer. Repositories carry their seeds in a checked-in
JSON file (a list of canonical `EvidenceRef` items); the operator passes
it via `span-install --authority-seeds-file PATH`, and a setup-session
`initialize_repository` call provisions them. Seed files live with the
target repo they govern; unknown seed locators fail closed.

## 1. Operational setup

Discover the exact registered canonical `repository_id` through MCP
`tools/list`. If the repository is `UNINITIALIZED`, call
`initialize_repository` once for the repository root with
one plain `repository_locator` and only user-supplied
`authority_seeds` (unknown seeds fail closed); provider selection stays
shell-owned. Provisioning runs the one
bounded provider build when the cache is missing or stale; a failed
build is an actionable setup failure. Reuse the returned canonical
ID unchanged. If it is already initialized, do not initialize it again for a
new target session. Expected: `READY` operational status and schema/store
identity. This proves storage readiness only; it is not semantic completion.

## 2. Target admission

Pass the exact user target and objective to `initialize_target` with the
exact `EvidenceScope` and a non-empty objective. Expected: the deterministic
`TargetId` campaign handle plus the next typed task. Record the exact semantic
boundary, canonicalized per Addendum E §4C.6A (not verbatim text).
`initialize_target` creates or resumes the deterministic
`TargetAssociation`. Mapping tasks carry `question=None` with a bounded
`target_inventory_items` batch. The provider-enriched items are orientation
evidence; the agent submits stable `EvidenceId`-based
`CandidateTargetInventoryAccount` outcomes, and Span resolves the canonical
provider `EvidenceRef`. The anchor is a candidate and evidence input, never a
semantic area. Membership changes re-enter here; content changes use `refresh`.

## 3. Semantic mapping

Inspect the admitted target, group structural evidence into coherent
material areas (subsystem, workflow/composition slice, service boundary,
governed document area, or cross-boundary path), and account for every
area. No area disappears because it is inconvenient, small, duplicated, or
structurally difficult. `target_scope` alone does not prove grouping; see
the E-13 constraint in `docs/lifecycle.md`.

Coverage-dimension checklist (convention, not a second model): when
substantiating completeness for a bounded area, walk identity
(subjects via structural discovery), structure (adjacency via
`neighbors`), dataflow (producer-to-consumer via `trace`),
composition (area membership and boundary crossings), authority
(governing sources plus seeds), verification (linked tests with
currency, never test-existence-as-pass), registration (manifest-
declared units as candidate subjects), execution routing (declared
routes as evidence, never runtime claims), governance (ownership and
constraint claims), state provenance (evidence fingerprints and
freshness), and declared configuration (config evidence marked
declared-not-observed). Record each as ordinary questions,
requirements, and claims — dimensions organize the work, the existing
coverage contract records it.

Recording convention: submit typed target-inventory accounting for every
current inventory member: assign it to one or more admitted area
subjects, provide an evidence-backed target exclusion (`SemanticBasis`), or record an explicit
unresolved mapping requirement. Submit exactly one accounting decision for
every inventory member bound in the mapping task. Span creates the
first-admission `PENDING` CQ-01 itself for a newly admitted area; reuse
persisted coverage via `proposed_target_questions` when an identical scope
already exists. This is
separate from admitting one question per coherent area with the area anchor as
`scope_root` and the area's complete evidence in that question's
`SemanticQuestionDecision.evidence_scope`. `NOT_APPLICABLE` answers a
semantic question; it does not exclude that area's inventory from the target.
Admitted area subjects stay queryable by exact id. `status(TargetId)` (`NORMAL`
only) then reports target accounting and semantic coverage separately; unresolved or
unaccounted inventory prevents `CURRENT`. No second store, ledger, or
progress model exists.

### Worked structural orientation (`locate` → `neighbors` → admit)

After `initialize_target` returns the campaign handle, orient with
structure before grouping areas (Addendum F §3 rows 3b/4/7b):

1. `locate` with `TARGET_MEMBERS` and the exact `EvidenceScope` → the
   full member list (the same enumeration the frontier reconciles
   against). A member without an indexed subject carries a null
   subject and stays a full member.
2. `locate` with `FILE_OUTLINE` for one file, or `SYMBOL` for a
   name/locator (`EXACT` resolves that exact locator to its
   declaration/name with no partial matches; `CONTAINS` returns
   substring matches in provider order) → symbols, spans, signatures.
   `FILE_OUTLINE` takes one file locator and no target scope or match
   mode; `SYMBOL` accepts an optional target scope. In-body content
   (error strings, config keys) stays with grep; Span does not
   duplicate it.
3. `neighbors` with the exact subject and `UPSTREAM` / `DOWNSTREAM` /
   `BOTH` at a bounded `max_depth` → caller/callee adjacency for
   partition grouping and pre-change blast radius. Multi-hop pages
   are a discovery tree; resume with the continuation token.
4. Admit: group members into coherent areas and account every member
   through `submit_interpretation` (assign to an area,
   evidence-backed target exclusion, or explicit unresolved mapping).

All four return navigation evidence only — cite it as evidence refs,
never as authority. Stale entries are excluded and counted
(`stale_omitted`); `UNVERIFIED` coverage, including an empty page,
proves nothing about absence.

## 4. Area interpretation (one coherent area at a time)

For the current task, follow its `brief` through the uniform card:

1. objective; 2. exact scope and exclusions; 3. evidence examined plus
governing sources, separating observed behavior from governing intent;
4. material input → producer → transformation/state → consumer/output →
terminal/failure path; 5. typed claims/relationships in existing kinds
only; 6. adversarial check (alternate owner, contradiction, omitted
participant, unsupported route, stale premise, missing verification);
7. explicit `ANSWERED`, `NOT_APPLICABLE`, `OPEN`, or `PENDING` disposition
with requirements; 8. fresh readback stating what is reusable and what
still needs interpretation.

No fixed file count, claim count, score, representative-root shortcut, or
populated-store check satisfies this.

Evidence quality (Addendum G): prefer function or block spans over
whole-file citation where `span_text` and `signature_text` exist; cite
tests, contracts, and docs alongside code with existing
`EvidenceSourceKind` values. Link `VERIFIED_BY` only on executed
evidence with observed revision. Entry modes: `initialize_target` with
an exact `EvidenceScope` plus user objective campaigns an exact
user-supplied directory; `explain(establish_baseline=True)` audits an
ordinary selected root. Do not substitute one for the other.

## 5. Persistence and advance

Call `submit_interpretation` with the typed result under its continuation.
For target-mode work, the result may include bounded target-inventory
accounting proposals; ordinary question-local results leave that component
empty. Span validates and writes accepted accounting, subjects, semantic
results, and target-bound coverage atomically through the canonical batch.
A malformed payload or returned `validation` error keeps the existing
continuation: correct and resubmit it under that same continuation. An
unknown, expired, or lost continuation is recovered by re-running the
idempotent original operation; there is no reissue operation. Continue until no
unprocessed target work remains. One representative answer is never
completion. Each submission persists canonical results plus the next task
or a truthful terminal result.

## 6. Normal retrieval

Use `status(TargetId)` for campaign readback; then `explain`, `impact`,
`trace`, and `authority` on exact area `SubjectId`s for bounded
questions. Results distinguish persisted coverage from new pending
interpretation. Retrieval never invents, widens, or substitutes an answer.
`TargetId` is rejected under `HOOK_FAST`; hooks use `EvidenceScope` only.

## 7. Change maintenance

After source changes, call scoped `refresh`, inspect stale/unverifiable
coverage, and repeat the same quality card for affected areas. A stale
answer is not presented as current; `refresh` alone manufactures nothing.

To challenge a `CURRENT` explanation without a source change, resolve
the exact persisted question from `status`/`explain` question coverage,
then call `refresh` with the exact `SubjectSelector` and explicit
`stale_only=False`. Nominate exactly one already-persisted original
question through `proposed_questions`, with evidence-grounded withdrawals and
replacements; a second distinct correction question in the same unit
is rejected.

## 8. Fresh-session closeout

Start a new agent session. Read `status(TargetId)` and representative
`explain` answers for exact area ids. Expected: reusable claims/relationships/questions,
explicit gaps, and a completion report listing every inventory accounting
state and material area with its persisted semantic-question disposition.
Completion requires whole-target accounting plus fresh retrieval evidence —
not merely `READY`, a populated store, or a successful transport call.

## Stopping rule (binding)

Every current inventory member is assigned, evidence-backed excluded, or
explicitly unresolved, and every admitted area has persisted semantic
question coverage for this target. `PENDING` means the campaign is not complete. `OPEN` means
an unresolved requirement is recorded, not hidden. `NOT_APPLICABLE` states
why a bound semantic question does not apply; it does not establish target
exclusion. Never collapse these facts into a single coverage score, count,
percentage, or threshold.

## Boundaries

Span never edits code, runs tests, selects models, or invokes providers.
No whole-repo crawl. Hooks call only `status` with `HOOK_FAST` and never
initialize, interpret, refresh, rebuild, or decide. Refresh is always
scoped; repo-wide refresh is rejected fail-closed.
