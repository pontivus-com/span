# Span onboarding runbook — new-user semantic extraction (Addendum E E-12)

Canonical path for an exact user-supplied target. Steps and stopping
conditions are copied from `docs/semantic-governance-addendum-e.md` §§4A
and 6. Guides describe; they never define semantics. No new operation,
carrier, writer, score, or background process is introduced here.

## 0. Preflight (host, fail closed)

Confirm and record: installed Span source revision, registered host, data
directory outside every target repo, exact repository root, existing
structural index at `<target>/graft/.graph/wiring.json`, and that
independent Graft activity is disabled or demonstrably read-only for the
run. Missing or writable-unsafe prerequisites stop the run. Record the
preflight in the receipt and acceptance evidence with a target artifact
snapshot proving only the configured data store changed.

## 1. Operational setup

Call `initialize_repository` once for the repository root with
`repository_locator`, `structural_provider_config`, and only user-supplied
`authority_seeds` (unknown seeds fail closed). Expected: `READY`
operational status and schema/store identity. This proves storage readiness
only; it is not semantic completion.

## 2. Target admission

Pass the exact user target and objective to `initialize_target` with the
exact `EvidenceScope` and a non-empty objective. Expected: a resumable
exchange containing the complete target boundary, the current structural
anchor, and the next typed interpretation task. Record the boundary
verbatim. An anchor is a candidate and evidence input, never a semantic
area.

## 3. Semantic mapping

Inspect the admitted target, group structural evidence into coherent
material areas (subsystem, workflow/composition slice, service boundary,
governed document area, or cross-boundary path), and account for every
area. No area disappears because it is inconvenient, small, duplicated, or
structurally difficult. `target_scope` alone does not prove grouping; see
the E-13 constraint in `docs/lifecycle.md`.

Recording convention (guidance, not a new carrier): admit one question per
coherent area with the area anchor as `scope_root`, keep the area's complete
evidence in that question's `evidence_scope`, and name member anchors and
exclusions in `disposition_basis`. Admitted area subjects stay queryable by
exact id. Exact-target `status` then reports one typed disposition per
frontier subject (`coverage_report` entries: `CURRENT`, `INCOMPLETE`,
`STALE`, `UNVERIFIABLE`, or explicitly `UNASSESSED`) — that report is the
whole-target accounting. No second store, ledger, or progress model exists.

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

## 5. Persistence and advance

Call `submit_interpretation` with the typed result under its continuation.
Use `reissue_interpretation` once and only for an expired transport
continuation, then submit the returned identical task. Continue until no
unprocessed target work remains. One representative answer is never
completion. Each submission persists canonical results plus the next task
or a truthful terminal result.

## 6. Normal retrieval

Use `status`, `explain`, `impact`, `trace`, and `authority` for bounded
questions. Results distinguish persisted coverage from new pending
interpretation. Retrieval never invents, widens, or substitutes an answer.

## 7. Change maintenance

After source changes, call scoped `refresh`, inspect stale/unverifiable
coverage, and repeat the same quality card for affected areas. A stale
answer is not presented as current; `refresh` alone manufactures nothing.

## 8. Fresh-session closeout

Start a new agent session. Read target `status` and representative
`explain` answers. Expected: reusable claims/relationships/questions,
explicit gaps, and a completion report listing every material area with
its persisted disposition. Completion requires whole-target accounting
plus fresh retrieval evidence — not merely `READY`, a populated store, or
a successful transport call.

## Stopping rule (binding)

Every material area is accounted for; every accounted area has a persisted
disposition. `PENDING` means the campaign is not complete. `OPEN` means an
unresolved requirement is recorded, not hidden. `NOT_APPLICABLE` states
why the area is outside the objective. Never collapse states into a single
coverage score, count, percentage, or threshold.

## Boundaries

Span never edits code, runs tests, selects models, or invokes providers.
No whole-repo crawl. Hooks call only `status` with `HOOK_FAST` and never
initialize, interpret, refresh, rebuild, or decide. Refresh is always
scoped; repo-wide refresh is rejected fail-closed.
