# Changelog

## 0.8.1 — 2026-10-26

**The defects 0.8.0's own gate exposed.**

The gate recorded five tasks, three arms, two hosts. Its result for 0.8.0 was
**not solved**: T2 (cold start costs 1.81× no Span) and T4 (zero assertions
stored) failed. T3 and T7 are **void**, not failed: the warm arm is defined
over subjects the first session asserted, and the first session asserted
nothing, so recall was never measured. This release fixes the defects that
produced the two valid failures. It does not claim the economics; a probe and a
re-run with the populated-store prerequisite are still owed.

### Wire contract

- **One schema projector.** The top-level request schema was projected by a
  second, reduced copy that omitted the `$type` guidance and the defaults. The
  decoder required a rule the schema never stated, which produced 13 rejected
  calls at `target` in a 48-call session. Root and `$defs` now use one
  per-field projection.
- **Bounds advertise their ceiling.** `QueryBounds` properties carry the
  `maximum` the service enforces, read from the same policy object, so the two
  cannot drift.
- **The path rule is stated.** `EvidenceScope.paths` says repository-relative;
  a leading `/` fails closed.
- **A redundant `$type` is accepted when it names the only candidate carrier.**
  A tag naming anything else still fails. The wire rule is unchanged where
  ambiguity exists.

### Refresh

- **No partial refresh.** A refresh scope is a set of subjects, not a frontier,
  so a cut item list has no honest cursor. An oversized scope now fails closed
  with `RefreshScopeError` naming the ceiling and the remedy. It never returns
  `truncated` without a continuation.
- `SemanticRefreshRequest.page_token` is removed; it was accepted and never read.

### Assertion yield

- **The brief states the completion rule.** A claim supported by cited file
  evidence is a complete assertion; missing governing authority is recorded as a
  resolution requirement on the claim, not a reason to withhold the assertion or
  leave the question `OPEN`. Same wording in the shipped skill.

### Internal

- Removed `declared_complete` entirely: the field, its two guards, the
  parameter path (`suspend` → `SuspendedOperation` → `materialize`), and the
  construction arguments. Completion is the disposition; the derive stage's
  material check is the rule that actually rejects an empty `ANSWERED`.
- The schema shaper is one ordered entry point (`_shape_tool_schema`) rather
  than four steps at one call site, so a step cannot be skipped.
- The duplicate-body gate now treats a body that is a single call as a
  delegation to the rule's owner, not as a second copy. The two remaining
  reports were one-line `__post_init__` validators; the count is now zero by
  definition, and multi-statement duplication is still caught.
- `scripts/build_identity.py` excludes its own output from the digest, so the
  identity is idempotent and a checkout install reports the revision it built.
- A retired `pgq:` cursor grammar is no longer documented as live.

### Verification

- `939 passed, 1 skipped`; ruff, black, and the typing ratchet (84) clean.
- New `tests/unit/test_schema_contract.py` pins the multi-tag guidance, the
  bounds maxima, the path rule, honest refresh truncation, and redundant-tag
  handling. These are the contracts 0.8.0 did not meet; the path assertion was
  observed failing before the fix.
- The code-budget gate holds: zero duplicate source bodies, zero mutable module
  tables, zero functions over 150 lines.

### Breaking

- `refresh` no longer accepts `page_token` (it was ignored).
- A redundant `$type` at an unambiguous position is accepted instead of
  rejected. This is additive for callers; it removes one error class.

### Retained

- **Host-authored `question_selection` is retained.** Removing it deletes the
  cursor-binding acceptance phase (EC-13), which proves a page token issued for
  one question is rejected for another. The zero-assertion result is a brief and
  behaviour question, not a reason to remove a tested capability.

### Not claimed

- The economics: T2 and T4 were recorded against 0.8.0 and are not re-measured
  here. T3/T7 were void, not failed.
- That the brief wording changes agent behaviour; the probe is still owed.
- Establishment cost (B3) and the second establishment entry `initialize_target`
  (B4) are untouched; they are design changes, not defects.

## 0.8.0 — 2026-10-26

**One architecture, one behaviour: the establishment root cause removed.**

0.8.0 is the single release for the architecture remediation and the
deterministic establishment design. It is a breaking release: the store schema
moves to 9, question-bound page cursors change once, and the mapping-era surface
is deleted. The eleven MCP operations keep their names and their request and
response meanings.

### Behaviour

- **Target admission is deterministic.** Area membership is computed from the
  admitted manifest; the model no longer maps inventory items to accounts.
  Every admitted area receives a service-owned `CQ_01` seed when it has no
  current question, and the returned unit is a question, not an accounting
  template.
- **`ANSWERED` must assert something.** An explicit `ANSWERED` decision is
  completion intent, not completion proof; a unit with no validated assertion
  cannot close a question. `NOT_APPLICABLE` remains the terminal disposition for
  a question that genuinely needs no assertion.
- **One establishment path.** `explain`, `initialize_target`, and both
  submission resumes delegate to one establishment path instead of four
  near-copies.
- **One evidence body per task.** A task brief carries each evidence body once
  per `(locator, fingerprint)`; omitted bodies are named rather than repeated.
- **Question currency no longer fails silently.** A precomputed discovery
  snapshot is consumed in the shape it is produced, so a currency check can no
  longer fall through a broad exception to `UNVERIFIABLE`.
- **Stale listings fail closed with a remedy.** Every version-bound cursor
  names its version and offset count; a token bound to another query restarts
  the listing instead of skipping.

### Architecture

- `core/model.py` is a package split by domain; `validation.py` and `schema.py`
  are packages; no module carries mixed responsibilities.
- `service/` is split into one-owner packages: `answers`, `resolution`,
  `questions`, `freshness`, `discovery`, `interpretation`, `exchange`,
  `establishment`, and the operation packages.
- `shell/install.py`, `shell/mcp.py`, and `shell/sqlite_store.py` are packages.
  The store has one writer per table group inside one batch transaction.
- One evidence source (`shell/evidence_source.py`) owns inventory, selection,
  and bounded reads over four storage seams; the test double supplies seams
  only.
- The two structural providers share repository binding, version-bound paging,
  and the adjacency-selection skeleton in `shell/structural/support.py`.
- The service depends on `ContinuationPort`, not the shell store;
  `SuspendedOperation` lives in `core/continuations.py`; paging lives in
  `core/paging.py`.
- `core/requirements.py` owns requirement construction;
  `freshness.with_freshness` is the one live-currency projection.
- Historical design-note identifiers are resolved through
  [`docs/design-references.md`](docs/design-references.md) rather than repeated
  in code comments.

### Breaking changes

- **Store schema 8 → 9.** Persisted target accounts lose
  `exclusion_basis` and `resolution_requirements`, which had no producer once
  admission became deterministic. A store at any other version still fails
  closed. Upgrade explicitly:
  `span-install --migrate-store <repository-id>` (schema 7 and 8 are upgraded
  in one transaction; the command is idempotent at schema 9).
- **Question-bound page cursors.** The `pgq:` grammar is retired. Every
  version-bound cursor now uses `pgv:<version>:<offset>[:<offset>…]`.
  `0.7.x` question cursors are rejected with the restart diagnostic; restart
  the listing with `page_token: null`.
- **Removed mapping surface.** `count_target_inventory_outcomes` is gone from
  the store port and implementation; `CandidateTargetInventoryAccount`,
  `proposed_target_inventory_accounting`, and the mapping submission template
  are gone; `TargetInventoryAccount` keeps membership and loses the two outcome
  fields.
- **Removed answer counts.** The two mapping-era target count fields are gone
  from status content; current accounting is derived from the association and
  the live diff.
- **Test doubles moved out of the shipped package.** `FixtureEvidenceSource`,
  `FixtureCandidates`, and `FixtureAgent` now live under `tests/support/`.
- **Internal module paths changed.** `span.shell.install`, `span.shell.mcp`,
  and `span.shell.sqlite_store` remain importable facades over their packages;
  deep imports into the old single modules are not preserved.

### Migration

1. Merge or install 0.8.0.
2. Upgrade each existing store before opening it:
   `span-install --migrate-store <repository-id>`.
3. Discard page tokens issued by `0.7.x` question listings and restart from
   the first page. Tokens issued by 0.8.0 are stable for the listing that
   produced them.
4. Re-run the installer to refresh host entries and deployed skills.

### Verification

- `932 passed, 1 skipped` on the full suite; characterization pinned at 9/9.
- `ruff` and `black` clean; typing ratchet at 84 errors (down from 120).
- Code-budget gate green: zero source functions over 150 lines, zero duplicate
  source bodies except the two declarative `__post_init__` validator
  delegations, zero `service → shell` imports, zero mutable module tables.
- The frozen five-task product gate (`GATE.md`) is the next step; its T1–T7
  thresholds are ratified before that run. This release note claims
  architecture and contract correctness, not a product-economics verdict.

## 0.7.1 — 2026-10-26

**Pagination resumes; failures name their cause.**

Patch release for the defects found by running 0.7.0 in real agent sessions,
plus one more in the same pagination path found while fixing them. No
operation was added or renamed, no carrier changed shape, and the store
schema is unchanged (schema 8), so no migration is needed.

### Fixes

- **Scoped `status` resumes where it stopped.** The page cursor was checked
  against a digest built from the page it had just returned, so the next call
  resolved different subjects and every resume was rejected as
  `stale_continuation`. The cursor is now bound to the scope's fingerprint, and
  it names two positions: where the subject frontier resumes and, when a page
  had to cut its own items, how far into that subject's claims, relationships,
  and questions it reached. A page that cuts items stays on its subject instead
  of advancing the frontier past them, so nothing is skipped and membership
  drift still restarts the listing.
- **`NOT_FOUND` stops diagnosing the caller.** The requirement stated that
  locators are relative to the repository root, "not the workspace root",
  without inspecting the locator. It now states the rule and leaves the cause
  to the evidence.
- **A byte-budget failure names the budget.** The provider's precise error —
  `evidence exceeds max_evidence_bytes (N)` — is kept instead of being replaced
  by a selection message, and the remedy lists raising the bound as well as
  narrowing the target.
- **Ingress errors name the accepted alternatives.** A missing `$type` lists
  the members the position accepts; an unexpected `$type` names the shape the
  position takes. The arity rule is unchanged: one accepted type forbids the
  tag, a union requires it.

Cursors issued before 0.7.1 by scoped `status` are invalid. They never resumed,
so nothing is lost: restart the listing with `page_token: null`.

A page that carries one subject whole may exceed `max_results` by that
subject's requirements. This is the same declared exception that has always
admitted a coverage entry whole: a page is never cut where the cursor cannot
name the position.

## 0.7.0 — 2026-10-25

**Bounded answers, labeled staleness, recorded verification.**

Scoped questions return a page, not the repository. Reported counts match the
payload. `impact` and `trace` say when structure no longer matches the tree. A
current pass comes from an execution record and goes stale when the revision
moves.

Breaking release. Existing stores need one explicit
`span-install --migrate-store <repository-id>`. The eleven public operations are
unchanged; no operation was added or renamed.

### Highlights

- **Answers stay on budget.** Narrow questions return a narrow, resumable page;
  counts match payloads; a truncated answer always includes the way forward.
- **Stale structure is labeled.** `impact` and `trace` qualify structural input
  that no longer matches the tree.
- **Verification you can check.** `CURRENT_PASS` comes from a recorded execution
  against the current revision and verified scope; when the code moves it reads
  `STALE`, not "passed".
- **Identity is safe and removal is explicit.** Two roots cannot silently share
  a store; `--uninstall`, `--purge <id>`, and `--list-orphans` give installation
  a real terminal.

### Full changes

- **Coverage reports are scoped by type.** `coverage_report` is now either a
  repository report or a scoped report, and each nests its numbers by what they
  measure: repository-wide totals separately from the current page. Counts that
  follow from the entries (`returned_subject_count`, the per-disposition subject
  counts, `stale_effective_question_count`) are no longer sent — compute them
  from `entries`.
- **A scoped answer cannot report a repository-global number.** Scoped status
  carries its own scope totals only; question and target-burden totals stay on
  repository status. The five aggregate-scope labels are gone, because the
  carrier now says which scope a number belongs to.
- **`status.unresolved` is removed.** Resolution requirements live on the answer
  envelope, in one list, with one owner.
- **Page tokens use one grammar.** Tokens are `pga1:…`; `pg:` and `pgq:` are
  rejected with the restart diagnostic. A token survives a process restart; a
  `submit_interpretation` continuation does not, and re-running the originating
  operation is the documented recovery.
- **Verification currency is derived, never asserted.** A submission can carry
  `CANDIDATE` or `UNKNOWN`. `CURRENT_PASS` / `CURRENT_FAIL` are computed from a
  stored verification record against the current revision and scope, so a pass
  stops being current when what it verified changes. `VerificationValue` splits
  into the link and the execution record; the record takes its verified scope
  from the link, so the agent supplies no internal fingerprint.
- **Store schema 8.** `span-install --migrate-store <repository-id>` upgrades a
  version-7 store in place; the store still refuses to open a mismatched
  version. The write-only `retired_claims` and `retired_relationships` tables are
  removed.
- **Repository identity is proven, not guessed.** Registration rejects two
  canonical roots that resolve to one ID and rejects a store whose recorded root
  differs. `initialize_repository` reports the canonical root and, when nested,
  the containing root.
- **Install has a terminal.** `span-install --uninstall` reverses the install
  writes, `--purge <repository-id>` removes one repository's store and structural
  cache, and `--list-orphans` reports stores no receipt claims. Nothing is
  deleted without an explicit ID.
- **Scoped answers are bounded.** Exact-scope `status`, `refresh`, and the
  lifecycle hook resolve a page of the scope instead of scanning the repository.
  A scope that previously returned every entry now returns up to `max_subjects`
  of them with a continuation.
- **Reported counts match payloads.** Requirements are counted against the same
  ceiling as items, `truncated: true` always comes with a continuation token, and
  repository status no longer drops requirements above the ceiling silently.
- **Stale structure is not presented as current.** `impact` and `trace` qualify
  structural input whose index no longer matches the tree; `neighbors` keeps
  filtering it.
- **Responses say what they are.** Status declares which mode answered
  (`resolved_mode`); handles carry their lifespan (`kind`, `scope`,
  `expires_at`, `recovery`); a campaign handle that has expired names the
  recovery instead of reading as one that never existed. Readiness is
  `store_readiness` (`StoreReadiness`), so the field says it measures the
  store/runtime rather than semantic completeness.
- **Concurrency is stated.** Several processes may read one store; SQLite
  serializes writes with a declared busy-timeout; continuations are private to
  a process and a second session re-runs the operation; page cursors are
  stateless. The contract is documented, not inferred.
- **Documentation matches enforcement.** `docs/acceptance.md` now says attested
  execution with verifiable currency, which is what Span can enforce. It never
  ran tests, and it no longer implies it does.

## 0.6.2 — 2026-10-24

- Rust sources index again. The provider reports `mod` and `const` nodes,
  which had no mapping, so the whole structural load failed with "unknown
  structural node kind". `module` now maps to COMPONENT (a code container,
  like a file) and `constant` to CODE_SYMBOL (a named declaration, like a
  type), which is where `enum`, `type`, and `struct` already sat.
- A provider-vocabulary lane runs the pinned indexer against a Rust fixture,
  so a newly emitted node kind fails in CI rather than in a user's first
  `initialize_repository`.

## 0.6.1 — 2026-10-24

- README images and documentation links are absolute. The relative logo path
  rendered as an empty image on the PyPI project page, which cannot fetch
  repository-relative URLs.
- Carries the 0.6.0 work: canonical structured MCP results with advertised
  output schemas, a 16,000-byte ceiling on evidence delivered to the model,
  live pending work reported by `status` without exposing continuation
  tokens, the corrected `refresh` lifecycle, and status reads that fail
  rather than borrow a semantic state.

## 0.6.0 — 2026-10-23

First public release.

- Local MCP server for maintained codebase understanding.
- Eleven public operations: `initialize_repository`, `initialize_target`,
  `explain`, `impact`, `trace`, `authority`, `status`, `refresh`,
  `submit_interpretation`, `locate`, and `neighbors`.
- Evidence-backed claims with explicit authority, trust, and freshness.
- Partial staleness: a change marks the affected claim stale without
  discarding unaffected understanding.
- Scoped refresh and predecessor history.
- Managed structural indexer provisioning; no separate indexer download.
- Codex and OpenCode setup, Agent Skills, and report-only lifecycle hooks.
- Apache-2.0 licence.
