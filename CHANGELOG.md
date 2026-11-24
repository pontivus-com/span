# Changelog

## 1.0.0b3 — 2026-11-24

### Beta 3 corrective integrity

- Enforce repository authority ingress as the strict canonical boundary:
  authority seed and binding files must carry their canonical discriminators;
  the installer no longer synthesizes missing `$type` values before decoding.
- Make publication an explicit release-owner action. Merging or pushing to
  `master` does not publish; the release workflow is manual-only and requires
  the exact package version to be supplied when it is deliberately dispatched.


### Qualified reuse and explicit curation

- Separate evidence-near semantic capture from shared-reuse qualification.
  New or semantically changed conclusions begin `CAPTURED`; ordinary shared
  Answer content requires the exact revision to remain support-`CURRENT` and
  be explicitly `CURATED`.
- Add deterministic pending-curation discovery and exact-revision curation
  through the existing `ask` and `record` lifecycle. Semantic corrections
  reset curation; semantic-preserving confirmation may inherit it.
- Keep failed review on the existing semantic lifecycle: correct, replace or
  withdraw the meaning first. Span does not add a rejected-curation state,
  infer semantic truth, or run a built-in/background curator model.
- Preserve exactly three public MCP tools: `ask`, `record`, and
  `reconsider`.

### Installer, governance and external-integration correction

- Fix B2-D01 at the owning setup seam: `span-install` now accepts
  repository-qualified authority seed/binding files and invokes the existing
  canonical repository-initialization owner once per selected repository.
- Fix B2-D02 at the acceptance seam: installed cold-start coverage now proves
  repository initialization instead of manufacturing lifecycle/binding state
  behind the installer.
- Keep Functional Pyramid participation separate from repository
  initialization. Curation cannot create or alter governance participation,
  authority, applicability, routes or health.
- Revalidate the private first adopter from committed root-correct authority
  inputs: cold installation, Functional Pyramid activation/projection,
  CAPTURED/pending behavior, explicit curation and fresh-process shared reuse
  all passed. Raw adopter evidence remains private.

### Storage, migration and product boundary

- Move the repository lifecycle store to schema **15** with one immutable
  `conclusion_curations` owner. The explicit schema-14→15 transition retains
  Beta-1 semantic history but creates **zero automatic curation** dispositions.
- Keep the installation Functional Pyramid store at schema **1**.
- Position Span as the evidence-backed software knowledge layer in a broader
  knowledge-factory operating model: working agents capture, reviewers curate,
  and Span maintains support/currentness/governance lifecycle state. Span does
  not claim to implement an organization's entire knowledge factory.
- Live authenticated model delivery through supported managed hosts remains
  unverified; installer/registration support is not promoted into that claim.

## 1.0.0b1 — 2026-11-22

### Complete working context

- Version 1 gives an agent both sides of the context for the exact software
  surface it is working on: retained understanding of what the implementation
  does, and the applicable project guidance that tells it what that
  implementation is supposed to follow.
- Add the Functional Pyramid to connect that same scope to the declared path
  from goals and first principles through rules, contracts, functional design,
  and technical design. Canonical documents remain with their owners, including
  across repositories; Span keeps their identity, applicability, relationships,
  and change consequences explicit.
- Keep implementation evidence and governing authority as separate proof.
  NORMATIVE conclusions receive server-derived Functional Pyramid route and
  canonical authority support; current implementation evidence never substitutes
  for declared authority.
- Make participation explicit as `UNCONFIGURED`, `EXCLUDED`, or `ACTIVE`.
  ACTIVE repositories return the applicable guiding path alongside ordinary
  retained understanding for the same software scope.

### Lifecycle and public contract

- Preserve exactly three public MCP tools: `ask`, `record`, and
  `reconsider`. Functional Pyramid status, candidate validation and receipt
  retrieval are `ask` branches; participation writes are a
  `record(kind="functional_pyramid")` branch.
- Add the result-driven adoption/revision lifecycle:
  STATUS → DISCOVER/VALIDATE → DECLARE when needed → re-align →
  ACTIVATE/REVISE → VERIFY → re-establish actionable effects.
- Make accepted participation writes return their actual dependent effects and
  re-establishment contexts. Acceptance is not task completion while required
  effects or NORMATIVE conclusions remain non-current.
- Propagate implementation and governance changes through the same
  repository-qualified effect model, including declared cross-repository
  normative dependents.

### Storage, migration and compatibility

- Move the repository lifecycle store to schema 14 and add the separate
  installation-owned Functional Pyramid store for participation, versions,
  exclusions and installation-scoped receipts.
- Keep migration explicit and offline. Existing schema-7–13 stores use the
  inspect/apply/verify/rollback path; runtime open never performs an implicit
  migration. Schema-13→14 preserves durable semantic/audit state and does not
  fabricate historical Functional Pyramid support.
- Registered or transitioned repositories begin `UNCONFIGURED` until
  participation is explicitly recorded. Repository-portable backups remain
  repository-scoped; full-installation recovery also carries Functional Pyramid
  installation state.
- Existing hosts must reconnect/refresh their cached tool schemas for the
  Version-1 public contract. Historical host captures do not prove Version-1
  model delivery.

### Verification and beta limits

- T10 generic Version-1 acceptance passed on GitHub Actions run
  `44977899970` at
  `15dc6ab8264d6a4fbeeff75b80eae360eaabb80b`: build/distribution,
  Ruff/Black, the zero-error typing ratchet, the complete pytest suite
  (`919 passed, 1 skipped, 144 subtests`), installed non-editable MCP and the
  FA-01–FA-44 matrix.
- T11 external integration acceptance passed on 2026-11-22 using integration-owned
  gitignored evidence. Raw adopter topology and captures remain outside Span
  Git; only the sanitized pass result is published.
- The assembled `1.0.0b1` candidate passed the repository-verifiable T13
  closure gates: non-editable package install, schema-14/installation-schema-1
  identity, transition/backup/recovery, installed MCP, public-boundary leakage
  checks, the FA/Part-C architecture matrix, post-T10 semantic-drift audit,
  release-note generation and MCP Registry metadata validation.
- Version-1 live model delivery through Codex, OpenCode and Claude Code remains
  **UNVERIFIED** and is not advertised as verified Beta-1 delivery. Historical
  host captures and registration health are not promoted into Version-1 proof.
- Beta 1 does not require a synthetic G5/F8 comparative score before
  publication. Product-value validation continues through real-world use in the
  legal project, with follow-up Beta patch releases used to correct defects and
  workflow friction found in practice. Universal time/token-saving claims remain
  out of scope without separate evidence.

### Release identity

- Canonical package/PyPI version: `1.0.0b1`.
- Git tag: `v1.0.0b1`; GitHub title: `Span 1.0.0 Beta 1`.
- MCP Registry server SemVer: `1.0.0-beta.1`; registry PyPI package entry:
  `1.0.0b1`.
- The release workflow derives these identities from the canonical package
  version and treats Beta 1 as a prerelease.

## 0.11.0 — 2026-11-19

### Maintained lifecycle and schema-13 candidate

- Correct the public lifecycle, evidence, verification, reconsideration and
  structural-ingress boundaries identified by the 0.11 implementation plan.
- Deliver the canonical context binding and schema-12 to schema-13 transition
  implementation, including refusal, preservation, interruption and rollback
  behavior in disposable verification stores.
- Keep exact selectors, challenge settlement, replay/conflict handling and
  source-currentness behavior on their owning boundaries.

### Verification and release status

- Source candidate verification: GitHub Actions run `44448034572`, including
  build/distribution, Ruff, Black, zero-error typing, `798 passed, 1 skipped,
  125 subtests`, plugin notice delivery and 85% aggregate statement coverage.
- The packaged MCP and cross-cutting architecture and requirements audits are
  verified for the implementation candidate.
- Candidate-specific G5/F8 comparative measurement and managed-host T09/T10
  captures are intentionally outside this PR gate; no cost or managed-host
  delivery claim is made.
- The separately authorized schema-12 to schema-13 operational cutover was
  executed and verified on the installed 0.11.0 store.

## 0.10.5 — 2026-11-16

### Evidence references, not source copies

- Remove `source_observations.excerpt`: Span stores the source reference, the
  calculated content hash and the delivered ranges, not a copy of the source.
  This fixes whole-file admission of large files and removes the duplicated
  source storage measured in the live databases.
- Admission binds a reference without applying the delivery bound. Delivery
  re-reads the source, verifies the stored hash and pages large content; a
  changed source is a typed stale outcome and is never presented as admitted
  content.
- Store schema 12 drops the excerpt column. The offline transition supports
  7–11 → 12; the schema-11 mapping copies every semantic table and drops the
  column.
- Support evaluation continues to re-read and compare hashes; it never needed
  the stored bytes.

### Repository-portable backup and load

- Add `span-install --backup-repository <REPO_ROOT>`, which writes one
  deployable artifact into `<REPO_ROOT>/.span/backups/<UTC timestamp>/`:
  the repository's `<id>.db`, a `span-repository-backup/1` manifest and its
  SHA-256 digest. The artifact is intended to be committed with the
  repository.
- Add `--verify-repository-backup` and `--load-repository-backup`. Load
  verifies the artifact, snapshots the current data directory, replaces the
  repository store and explicitly rebinds its recorded root from the
  artifact's source root to the clone's canonical root.
- Add `--reap-repository-backups KEEP`; the count is explicit and Git history
  remains the durable retention.
- The artifact contains only the repository's store. `install.json`,
  `structural/` and `transitions/` are excluded; install-first and index
  rebuild remain the deployment steps.
- The full data-directory backup commands from 0.10.4 remain for global
  disaster recovery and are not committed.

### Policy and rules

- Amend `AGENTS.md` and `docs/recovery.md`: repository-portable artifacts are
  intentional Git content; all other raw captures, receipts and ad-hoc
  manifests remain out of Git.
- State the confidentiality consequence: the store contains recorded
  conclusions and evidence text, which become available to everyone with
  repository access and in history.

### Compatibility

- Store schema is 12. A 0.10.4 runtime cannot open a schema-12 store; run the
  documented offline transition when upgrading an existing installation.
- No public MCP operation change.
- Clones must keep the repository directory basename; renamed clones are
  refused because Span's repository identity is the basename.
- A 0.10.5 artifact is not loadable by 0.10.4.
- Historical source bytes are no longer retained. The content hash and ranges
  identify the source state; Git history is the archive.

### Verification

- Full suite: **763 passed, 1 skipped, 125 subtests passed**.
- Ruff, Black and the zero-error typing ratchet pass.
- Disposable CLI proof: artifact manifest SHA-256
  `9c068a66e11c4dfd2d386df691f4d5df07e4bdc7f0acee5edc4fa25da422ebac`,
  schema 12, 204,800 bytes. It verified, loaded into a clone at a different
  absolute path with the same basename, rebound to the clone, and reported
  ready. The loaded store has no `excerpt` column.
- The 134 KB whole-file admission case and the 11 → 12 transition are covered
  by tests. No live-store transition or live restore was performed.

## 0.10.4 — 2026-11-16

### Data backup and recovery

- Add an operator-facing recovery surface to the installer: `--backup`,
  `--verify-backup`, `--restore-backup` and `--reap-backups`. The reinstall
  backup path delegates to the same writer, so there is one artifact format and
  no second backup behaviour.
- A recovery artifact contains every top-level database (copied through the
  SQLite online backup API), `install.json`, `structural-indexer.json`, and a
  manifest of sizes, SHA-256 digests, per-database `schema_version`, integrity
  result and highest conclusion revision. `structural/` and `transitions/` are
  excluded with the reason recorded in the manifest.
- Introduce the canonical typed manifest carrier
  (`shell/install/manifest.py`) shared by creation, verification and restore.
  Unknown manifest formats and unknown keys are rejected rather than interpreted.
- Restore requires the artifact directory name as explicit confirmation,
  refuses a store held by a live process through the shared exclusive-ownership
  rule, snapshots the current data directory, clears stale WAL/SHM/journal files
  and re-hashes every restored file.
- Reaping is explicit (`KEEP`), deletes only directories carrying a valid Span
  manifest, and has no default retention interval.
- Document the policy and operator runbook in `docs/recovery.md`; link it from
  `docs/install.md` and `docs/README.md`.
- Record the running code version in the manifest, not an unrelated installed
  distribution version.

### Verification

- Full suite: **747 passed, 1 skipped, 125 subtests passed**.
- Ruff, Black and the zero-error typing ratchet pass.
- Isolated restore proof: artifact `20261116T030031630758`, manifest SHA-256
  `1bd6b1b19c8acea0776aafbd44c4c8503efa70668d1b77ef0d77de10e57fed3b`. All
  seven artifacts matched their recorded identity; restoring the artifact into a
  disposable data directory returned `u:rec-docgov-r00-20261116` at revision 4
  and `u:rec-docgov-inventory-20261116` at revision 1, both `CURRENT`, through
  the public `ask` operation. No live-store restore was performed.

### Compatibility

- No change to the public MCP operations or the schema-11 store; no migration.
- Backup artifacts are operator data and are not committed to Git.

## 0.10.3 — 2026-11-14

### Low-friction lifecycle

- Make pure `ask` surface-first: ordinary reuse takes an exact surface or
  unambiguous reference with no free question string, request identity, context,
  or automatic evidence delivery. The surface document view groups current
  conclusions by their recorded question.
- Add exact `RecordedQuestionSelector`, current-understanding, snapshot and
  receipt selectors without semantic question matching or historical/current
  conflation.
- Make source delivery explicit. Evidence admission selects exact locators/ranges,
  returns one bound `InvestigationContextRef`, preserves original positions and
  uses stable continuation over canonical `EvidenceDelivery` fragments.
- Keep direct first-attempt recording cheap: locator, ranged support, admitted
  observation and multi-support creates flow through the canonical lifecycle
  path; replay, stale versions, scope/owner/binding conflicts and challenge
  settlement remain atomic and typed.
- Keep default results compact without losing truth. Oversized grouped answers
  trim individual conclusions while preserving omission/reference recovery;
  historical gaps name exact snapshot retrieval and ordinary acceptance returns
  compact receipt selectors while durable receipts remain retrievable.
- Repair context/failure ownership end to end. Changed-scope reconsider issues a
  fresh Span-owned bounded context; concealed binding/store failures no longer
  become semantic gaps; post-commit qualification failures do not leak internal
  diagnostics; unusable continuations use typed `CONTINUATION_INVALID`.
- Generate advertised structural grammar and typed decoding from the same
  canonical declarations. Public schema names/discriminators are explicit
  protocol vocabulary and do not expose runtime `*Wire` class names.
- Align README, MCP/usage/lifecycle/query/onboarding/FAQ/glossary/acceptance
  guidance, packaged skills, managed AGENTS snippet, MCP examples and lifecycle
  reminders to the same surface-first procedure.

### Verification

- Final repository/installable candidate before metadata preparation:
  `b04eb533ad6eb87fc6499a25a378b9d80e2c0196`.
- GitHub Actions run `43587605351` passed build/distribution, Ruff/Black,
  zero-error typing, full pytest (**723 passed, 1 skipped, 125 subtests passed**),
  packaged plugin-notice delivery and coverage upload.
- The retained regression matrix covers schema/decoder equivalence, pure
  context-free obtain, precise evidence/continuation behavior, replay/restart,
  concurrent/binding conflicts, fresh changed-scope contexts, stale updates,
  public-discriminator stability and internal-diagnostic containment.
- Hard architecture/code-budget invariants remain intact: zero core-layer
  violations, zero duplicate helper/source groups, zero mutable module tables and
  one evidence-selection implementation.

### Compatibility and verification limits

The public grammar is intentionally breaking. Consumers must reconnect/refresh
the 0.10.3 tool schemas and managed guidance coherently; no legacy alias/parser,
TTL increase, retry shim, DTO compatibility layer or second semantic writer is
provided. Retained understanding, version history and durable receipt recovery
remain compatible; this change introduces no store migration.

Candidate-specific live Codex, OpenCode and Claude model-delivery captures were
not executable from the available GitHub-only implementation environment and no
repository workflow performs those runs. They are therefore **UNVERIFIED for
0.10.3**; earlier host captures are not reused as this release's evidence.
Likewise, no fresh comparative full-task cost run was executed, so 0.10.3 makes
no universal time/token, break-even or product-usability acceptance claim.

Package and MCP registry metadata are prepared at **0.10.3**. Tagging,
publication, registry push and user-host upgrades have not been performed.

## 0.10.2 — 2026-11-13

**Governed understanding as ordinary agent work.** The corrected functional
pyramid requires consultation, retention of established conclusions and
reconsideration after edits. Skills, managed instructions, tool descriptions,
host notices and public guides project that lifecycle consistently.

### Changed

- Remove discretionary-retention exemptions and irrelevant campaign disclaimers.
  Distinguish valid direct-record ingress from required consultation before
  deriving understanding, and hook-independent support safety from agent conduct.
- Align the public contract and current guides on exactly `ask`, `record`, and
  `reconsider`. Setup belongs to the installer; navigation belongs to the host.
  Replace obsolete term-overlap discovery advice with surface-first reuse and
  exact recorded-question lookup.
- Preserve useful safeguards for evidence, authority, uncertainty, replay,
  explicit setup, owned host configuration and truthful delivery claims.

### Fixed

- Deliver the lifecycle primer to registered operational cold repositories too.
- Forward unconsumed edit-notice paths to the OpenCode stop handler through
  JSON stdin and read native event session IDs. Consume notices only when
  delivered; clear session notices on deletion and plugin disposal. Stop-time
  reporting covers pending notice paths, not a new session-wide edit ledger.
- Budget declared ranged evidence after extraction rather than rejecting its
  enclosing file. Re-evaluate that range on subsequent reads/reconsideration;
  whole-file and admitted-excerpt limits remain enforced.
- Preserve retrieval after withdrawal: withdrawn revisions remain explicit
  snapshot/status content rather than being misprojected as supported statements.
- Supply a complete update template in the tool description: `actions` is an
  object of lists, `action` belongs to surface declarations, and edits update
  the returned understanding/version after reconsideration.

### Upgrade

Rerun `span-install` for the target and restart/reconnect the host so it receives
current skills, the managed agent block, plugin and MCP descriptions. A package
upgrade alone does not refresh every running host. Storage remains schema 11;
there are no new public operations or runtime dependencies.

### Verification

- Full standalone suite with pinned Graft 0.25.0: 709 passed, 101 subtests
  passed, no skips. Node plugin tests: 4 passed. Ruff, Black and type checking
  pass with zero type errors.
- Built-wheel installation and source/asset checks passed. Natural Codex and
  OpenCode journeys exercised consultation, retention and edit/reconsider/update;
  fresh-session Codex reused understanding without rereading source.
- The measured test-line ratchet grows from 20,516 to 20,765 for range,
  withdrawal, field-guidance and cold-start regressions; operational limits and
  existing assertions remain intact.
- Live-agent limitations: Codex still sent one invalid action before recovering;
  OpenCode reread source during a warm lookup.
- Acceptance artifacts are untracked and ignored. Release documentation retains
  sanitized verification summaries; raw captures and receipts stay local.

Live captures establish only their named host/task journeys, not universal
agent compliance or a hard final-answer veto.

## 0.10.1 — 2026-11-08

**A recording and scope-correctness bug-fix release.** This release removes
recording friction while keeping the public operations exactly `ask`, `record`,
and `reconsider`.

### Fixed

- Separate a conclusion's semantic scope from its support evidence. Multiple
  source files can establish one FILE conclusion without becoming additional
  owners. One complete semantic scope now drives owner validation, target
  construction, and the stored understanding, version, and conclusion.
- Resolve retained receipts before context creation, evidence admission, or
  discovery work. Exact retries remain replayable after context reaping and
  source changes; changed accepted retries remain `REPLAY_CONFLICT`.
- Report uncommitted request/context binding conflicts as
  `CONTEXT_BINDING_CONFLICT`, with original-content or new-request recovery,
  instead of misleading version-conflict instructions.
- Keep supplied contexts fixed in scope while allowing new in-scope source and
  discovery evidence. Out-of-scope evidence reports `CONTEXT_SCOPE_CONFLICT`.
  Context-free recording derives a complete operational scope; repository-wide
  discovery broadens that context without widening the conclusion's scope.
- Preserve exact evidence references throughout scope composition and
  reconsideration. Refs-only discovery no longer matches unrelated changes,
  and challenge contexts no longer widen to repository scope after dropping
  refs. Context-admitted references remain context-bound.
- Validate every semantic member against its owner, including FILE/SYMBOL
  self-membership and declared SERVICE/DOMAIN boundaries. A matching member
  does not permit additional out-of-owner scope.
- Return canonical live owner status in `UnderstandingRecorded.status`, using
  the same status composer as `ask`. Operational post-commit support or status
  failures preserve the accepted receipt and report explicit unavailability;
  programming errors still propagate. Exact-reference scopes no longer mark
  unrelated files as examined.
- Name forbidden update root fields in one ingress error. Align MCP and skill
  guidance on semantic scope versus support, expanded verification evidence,
  and the supported combination of observations and direct evidence.
- Keep the schema-10 migration receipt test on its fixture clock when reopening
  the store, so receipt retention does not make it fail as calendar time passes.

### Measured budget growth

- Record the release's measured ratchet growth: concrete carriers 174 → 175
  for explicit status unavailability; longest module 1,876 → 1,881 lines for
  the store's declared operational errors and binding-conflict classification;
  test lines 19,600 → 20,516 for recording/scope/replay regressions and the
  migration fixture clock. The budget comparison and all assertions remain
  unchanged. These measurements record the cost of the release fixes.

### Verification

- Focused recording, containment, reconsideration, and MCP regression suite:
  109 passed, with 37 subtests passed.
- Full suite: 701 passed, 101 subtests passed, no skips. The measured budget
  baseline is recorded above, and the receipt migration fixture uses its own
  clock. Both previously reported failures are resolved.
- Type checking: zero errors. Ruff, Black, Node delivery tests, installed-MCP
  checks, and independent live MCP journeys passed.

## 0.10.0 — 2026-11-07

**A public-grammar and identity-ownership release.** 0.10.0 makes the compact
`record` grammar the only recording grammar, derives new conclusion lineage
identities on the server, makes `reconsider` complete the continuation into
`record`, and removes the legacy parallel create/challenge/verification wire
path. The public surface is still exactly `ask`, `record`, and `reconsider`.

### Public record contract

- Understanding create takes one conclusion and exactly one evidence mode:
  `locator`, `observation_id`, or non-empty `support`. Scope is supplied or
  derived independently through `scope_paths`, the bound context, or a single
  carried path. A context-bound support create uses the context's bound scope;
  a declared surface name is never treated as an evidence path.
- Update actions are compact semantic deltas. `add` and `correct` carry
  `conclusion`, `confirm` carries only the existing target, `replace` carries
  `conclusion` and `reason`, and `withdraw` carries `reason`. `confirm`,
  `correct`, `replace`, and `withdraw` name the existing `conclusion_id`
  returned by Span; `add`, create, and the replacement lineage accept no
  caller-created identity.
- Span derives new conclusion lineage identities from
  `(repository_id, request_id, role, ordinal)` through the pure identity owner.
  `expected_version` remains mandatory and compare-and-set.
- The public understanding grammar no longer exposes `scope_evidence_refs`;
  internal evidence references remain. Old full-snapshot update payloads and
  old nested replacement payloads fail as unknown fields.

### Reconsideration and multi-file ownership

- Each actionable `ChangedConclusion` now carries the understanding's current
  `expected_version`, so `reconsider → record` needs no intervening `ask`.
- Historical revisions remain traversable as dependencies but are not emitted
  as actionable update targets.
- Declared SERVICE/DOMAIN multi-file ownership is proven end to end; multiple
  paths without an owning surface still fail closed.

### Architecture and response fitting

- The legacy `ConclusionWire`, `RecordCreateWire`, `RecordChallengeWire`,
  `RecordVerificationWire`, `create_command`, `challenge_command`,
  `verification_command`, and the parallel `LifecycleService.create/challenge/
  verification` entrypoints are removed. `LifecycleService.record()` is the one
  recording composition path.
- The evidence-page fitter now measures the real continuation token and the
  omission list it will carry, closing a reproduced post-edit CSS case where a
  page exceeded the configured budget.

### Verification

- Targeted gate: 173 passed and 35 subtests passed.
- Installed MCP lane: 3 passed.
- Full suite: 666 passed, 1 skipped, and 55 subtests passed.
- Ruff, Black, and `git diff --check`: passed.
- Candidate evidence:
  `.context/evidence/host-contract/2026-11-07-server-derived-identity/`.
- OpenCode: valid compact create/add/correct/replace lifecycle observed; strict
  unknown-field preservation is not established because the host removed an
  old-form field before delivery. Codex: current-candidate smoke create
  observed; the full compact update journey was not re-observed. Claude Code
  remains **UNVERIFIED** for authenticated model delivery.

## 0.9.4 — 2026-11-04

**A host-contract and legacy-boundary release.** 0.9.4 completes the current
three-tool Span contract, repairs installer-produced host state, restores
managed Claude Code support, and removes executable compatibility residue that
contradicted the current lifecycle.

### Lifecycle and MCP contract

- The registered MCP surface is exactly `ask`, `record`, and `reconsider`.
  Retired operation names are ordinary `unknown_tool` failures; no replacement
  map or compatibility alias is retained.
- The current `record` contract remains explicit: understanding creation is a
  flat conclusion with `locator` or `observation_id`, update actions are
  update-only, and surface actions are surface-only. Guidance and wire schemas
  are aligned with the first-pass request shapes.
- The explicit offline store transition remains the supported path for schema
  7, 8, 9, and 10 stores. Runtime/store transition semantics, persisted
  observation identities, replay digests, and schema-10 mapping behavior are
  unchanged; hidden migration-only command paths are not parsed.

### Installer and host state

- A default/global OpenCode install selects one configuration for both the
  lifecycle plugin and `mcp.servers.span`. Explicit `--opencode-config`, the
  prior receipt path, an intentional local `./opencode.json`, and the global
  configuration are resolved in that order.
- Selected OpenCode paths are recorded as absolute receipt identities. Bare
  repeat installs reuse the recorded path across working directories. Explicit
  relocation validates the previous target, writes the new registration first,
  then removes the old Span registration.
- `--verify-only` reuses the receipt-selected MCP path. Uninstall removes MCP
  registration and plugin wiring from their independently recorded
  configurations, preserving foreign entries and supporting legitimate split
  installations.
- `--no-hooks` disables lifecycle hook and plugin wiring only; it does not
  disable MCP registration. The selected MCP configuration is still rewritten
  with the current data directory and all `--repo` bindings.
- MCP inspection distinguishes `unselected`, `unreadable`, `missing`,
  `mismatched`, and `matched`. A global configuration that Span did not select
  is not silently inspected.
- Current receipts are a single versioned contract. Invalid, unsupported,
  unsafe-relative, or historical-layout receipts fail closed; historical receipt
  fields are not interpreted as migration authority.
- Explicitly inspected target-local Span plugins are reported as conflicts and
  left in place. The installer does not create `.opencode/span-retired` or
  migrate obsolete target-plugin copies.

### Managed hosts, hooks, and skills

- Claude Code is restored as a supported managed host with automatic detection,
  `--with-claude`/`--no-claude`, user-scope registration, read-only inspection,
  report-only hooks, ownership-marked skills, receipt coverage, and scoped
  uninstall. Foreign Claude settings, hooks, and skills remain untouched.
- Codex, OpenCode, and Claude hook wiring uses the canonical host-neutral hook
  contract. Hook commands carry the installed data directory, and missing host
  files or CLIs are reported as skipped rather than treated as successful
  delivery.
- Stale skill reconciliation and uninstall are ownership-based. A strict
  current `.span-origin.json` marker must match the directory name, install
  mode, and mode-specific provenance before Span removes anything; foreign,
  malformed, mismatched, and historical-looking directories are preserved.
- Authenticated Claude model delivery remains **UNVERIFIED** and is not claimed
  by this release. Codex registration remains manual, and host delivery is
  claimed only where the documented capture exists.

### Legacy-residue cleanup

- The unreferenced host roster and executable historical host-contract probe are
  removed, along with test-only retired-operation catalogs and the vacuous
  retired-name conformance test.
- Hook repository access uses the canonical versioned receipt reader; an
  unversioned or invalid receipt cannot route a hook into a repository.
- Structural indexer resolution accepts only the explicit contributor override
  or the installer-managed pointer. The pre-managed `PATH` fallback is gone.
- Current host documentation, MCP wording, ownership comments, schema-11 target
  wording, release metadata, and public version fields are aligned with the
  implementation. Historical changelog entries remain historical records.

### Verification

- `.venv/bin/pytest -q`: 629 passed, 1 skipped, and 20 subtests passed.
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, and
  `.venv/bin/python scripts/typecheck.py`: passed; typing ratchet at 0 errors.
- `node --test tests/plugin/test_span_hooks_notice.mjs`: 2 passed.
- `git diff --check` and the release quality-delta check: passed.

No new MCP operation, lifecycle phase, host-directory scan, semantic truth
scoring, Codex registration inspector, store schema, or target-repository
write path is introduced by this release.

## 0.9.2 — 2026-11-04

**A bug-fix release. It makes upgrades from 0.9.0/0.9.1 safe, returns the
historical and stale content the lifecycle contract already required, and
accepts evidence-only verification runs. No public operation is added or
renamed.**

### Upgrade from 0.9.0/0.9.1

A bare package upgrade does not migrate the host. Run the installer once with
an explicit OpenCode plugin scope and the target to migrate, then restart the
host:

```bash
span-install --repo <TARGET_REPO> --opencode-plugin-scope global
```

- The scope is an explicit end-user choice: `global`, `local`, or `none`. A
  fresh install defaults to `global` and prints it. An upgrade uses the scope in
  the install receipt; if the receipt records no unambiguous scope, the
  installer stops and names the flag rather than guessing.
- Under `global`, the installer deploys the plugin under Span's own data root
  and moves a legacy `<target>/.opencode/plugins/span-hooks.js` copy to
  `<target>/.opencode/span-retired/`. It never deletes it. That directory is
  operator-owned; Span has no TTL, reaper, or restore path for it.
- Only targets passed with `--repo` are migrated. A receipt target that was not
  selected is inspected read-only; a remaining Span-owned copy yields
  `conflict`, never `wired`.
- `local` and `none` leave the target plugin to the user, remove Span's global
  registration, and report each local copy with a hash match/mismatch. Exactly
  one user-managed copy is `external`; more than one is `conflict`; none is
  `absent` (`local`) or `disabled` (`none`).
- Result statuses are explicit: `wired`, `conflict`, `external`, `absent`,
  `disabled`, `unreadable`. A known duplicate never reports `wired`.

### Installer and host integration

- Duplicate Span-owned plugin registrations and legacy config entries are
  detected and removed only inside Span's own data root. A Span-owned copy in a
  user-managed global directory is reported as a conflict and left untouched.
- The receipt records `host_integration_migration`: the effective
  `opencode_plugin.scope`, every `retired_target_plugins` entry (`from`, `to`,
  `sha256`), and every `removed_config_entries` entry.
- Codex `span-hooks` entries are replaced with the current three, so an upgrade
  does not accumulate stale paths or matchers.
- Legacy Span-owned Claude hooks are removed from `~/.claude/settings.json`.

### Lifecycle conformance

- `Gap.historical` now carries historical **content**: the exact conclusion
  revision, the understanding version that holds it, the statement, the
  evidence references, and the present non-current support state. Historical
  content is never mixed into `conclusions`. The prior statement is recoverable
  without the transcript, and the list is bounded with the rest of the response.
- `SurfaceStatus.stale_refs` names each stale conclusion by exact revision,
  understanding version, and present non-current state. The count and the
  references describe the same set; descendant statuses carry their own refs.
  The status remains references and counts, never statement content.

### Verification

- A verification run requires `observations` or `evidence`; either is accepted.
  Only sending neither is rejected, with the exact cause and both remedies.
- A run applies to the surfaces **within** its declared scope (a scope path
  covers a surface path when it is equal or an ancestor). A multi-file run is
  now visible on each file it covers; a one-file run is not widened to a
  broader service; a symbol matches through its containing file or is excluded.
- The typed and wire verification submissions share one canonical write path.

### Results

- The `reconsider` description and the MCP reference example state the filter
  rule: `surfaces` is the complete containment set; a surface with no
  `conclusions` is containment-only; act only on `REASSESSMENT_REQUIRED` or
  `UNVERIFIABLE` conclusions; keep the deterministic order. No new response
  field was added.

### Compatibility

- Store schema 11 is unchanged. No store migration is required.
- The changes to `Gap.historical` and `SurfaceStatus` are additive/enriched wire
  fields; the host reconnects and reads the new shape. No wire payload is
  persisted, and no compatibility-flattened shape is introduced.
- No new MCP tool or operation family. `ask`, `record`, and `reconsider` remain
  the complete public surface.

### Known limitations

- A bare package upgrade does not migrate the host; run `span-install` once as
  above.
- Receipt-only and unregistered targets are reported, not changed.
- `local` scope requires the user to manage the local plugin.
- `none` removes the Span-managed plugin; a user-managed Span copy may remain
  and is reported as `external` or `conflict`.
- The `reconsider` noise is reduced by its description; the complete `surfaces`
  set is still returned.
- `.opencode/span-retired/` is operator-owned; there is no TTL or reaper.
- Codex notice delivery is not claimed in this release until a capture proves
  it. OpenCode edit-time notice delivery is proven by
  `tests/plugin/test_span_hooks_notice.mjs`.
- Foundations §1 is interpreted as binding the MCP server, not the installer;
  the server still makes no target edits.

### Not in this release

No `actionable` field, no `span_version` receipt field, no doctor listing of
retired files, no per-status resolution string, no admin stale report, no
Span-managed local plugin deployment, no machine-wide scan, no target deletion,
no store schema change, and no new MCP tool.

## 0.9.1 — 2026-11-03

**This 0.9.1 carries the replacement for the withdrawn internal pre-release
artifacts. They were never public; their changelog sections are removed.**

**Breaking request shape: an understanding create is flat. Guidance, recovery,
and the rejection vocabulary are corrected; no tool is added or renamed.**

### Request shape (breaking)

- `record(kind="understanding")` creates with one `conclusion` plus `locator` or
  `observation_id`. `actions` is update-only and `action` is surface-only;
  `create` is no longer an action. A create that sends `action` or a non-empty
  `actions` is an ingress error.
- The `record` description carries create, update, surface, and verification
  templates, so a host can copy one and succeed on the first call.
- `ask` without a question returns the document view in `groups`. The top-level
  `conclusions` is empty by design, and a targeted answer needs the exact
  recorded question.
- A verification run takes the `obs:` ids `ask` returned for the request
  context, or `run.evidence` with a locator. An id that was never admitted is
  `Rejected` with `cause_kind=observation_not_admitted`, and the required action
  names both remedies.
- A refusal never names an operation this build does not register: the retired
  navigation and setup names point to the host's navigation and the installer.

### Adoption (OpenCode)

- The installer deploys the lifecycle plugin under Span's own data root and
  registers it once in the host's global `opencode.json`; it writes nothing into
  a target repository.
- The plugin waits a bounded three seconds at prompt admission for the local MCP
  connection. OpenCode otherwise dispatches the first request without the Span
  tools, so the agent cannot ask before reading even when it intends to.
- The plugin injects one advisory session notice when the repository has
  recorded understanding. It names the direct tools, asserts existence rather
  than currency, names no surface, never blocks, and is silent on failure
  (FD-58). Measured: 5/5 first `ask` before the first source read.

### Storage and upgrade

- 0.9.1 uses **schema 11**. The runtime never migrates at open; an older store
  fails closed with a transition action.
- A store at schema 7, 8, 9, or 10 moves offline, one phase at a time:
  `span-install --transition-store <repository-id> --transition-phase
  inspect|apply|verify --transition-root <target-repo>`. `apply` archives a
  WAL-consistent copy, writes a lossless export, stages schema 11, maps a
  schema-10 understanding to the path surface named by its scope when that
  scope names exactly one file, records wider or empty scopes as unresolved,
  verifies, and activates atomically. `rollback` is available before and after
  activation.
- A store created by a withdrawn artifact is schema 10 and needs this
  transition. The version number is unchanged across the replacement, so
  reinstall from this release (`pip install --force-reinstall
  span-mcp==0.9.1`, or run `span-install` from the checkout) instead of relying
  on `pip install -U`.
- Complete commands and the mapping rules are in
  [install and connect](docs/install.md#upgrade-an-existing-store).

### Results

- `Rejected` carries `cause_kind` (typed), `cause` (the server's exact
  message), `required_action` (derived from the kind), and the structured
  `current_version` or `current_boundary_version` when one exists. The adapter
  no longer derives a cause or an action from message text.
- `Gap` always carries `recovery`. A `no_match` gap points to the surface
  document view; `invalidated` and `unverifiable` point to re-reading the cited
  evidence; `unassessed` points to reading the evidence and recording.
- A stale surface boundary version, a surface kind conflict, and a duplicate
  boundary are `Rejected`, not `Unavailable`. A schema-version failure remains
  `Unavailable`.

### Recording

- A create against a question context rejects an explicit `question` or
  `scope_paths` as a conflict instead of ignoring them.
- A declared surface parent must be an existing declared service or domain in
  the same repository; self-parent and cycles are rejected.
- A verification run applies only to the surfaces in its declared scope.

### Guidance

- The `ask` description leads with surface-first reuse: omit the question to
  read the surface document view; supply an exact question only when the
  recorded key is known. A paraphrase returns `no_match`.
- The `record` description states the context-bound create form, the
  verification scope rule, and the surface declaration.

## 0.8.3 — 2026-10-28

**Durable work can be picked up again.**

0.8.2 made reissuing `explain`, `authority`, `impact`, or `trace` re-suspend a
persisted `PENDING` question after its continuation was lost. It matched the
persisted identity but did not record the inputs that produced the question, so
`status` could name a live unit but could not tell a caller how to reissue a
question whose unit was gone; a question with no originating operation had no
recovery action at all.

0.8.3 stores the recovery inputs with the question, preserves them across
rewrites, and projects them into `status`. Recovery now names the originating
operation and its stored inputs when recorded, and `refresh` on the subject
otherwise.

### Pending questions

- **A pending question survives the loss of its continuation.** A question
  admitted by `explain`, `impact`, `trace`, or `authority` now stores the
  operation and the resolved inputs that produced it, so recovery no longer
  depends on the caller remembering inputs it was never given.
- **`refresh` and `initialize_target` needed no new storage.** A refresh
  question is re-examined by calling `refresh` on its subject, and a target
  campaign is recovered from its durable target association. Both were already
  recoverable; only the status message was missing.
- **`status` names the recovery action.** A pending question with no live
  continuation now produces a requirement that says how to pick it up: the
  originating operation and its stored inputs when the question records them,
  and `refresh` on the subject otherwise. This extends 0.8.2's live-unit
  reporting; a row written before this release decodes with no stored recipe
  and takes the `refresh` path.

### Refresh

- **Refresh drains a subject before advancing.** The frontier is
  question-level; the closeout unit was subject-level. A subject with two
  pending questions used to answer one and report completion.
- **Each question is attempted once per refresh chain.** The eligible questions
  for a subject are snapshotted when the chain reaches it, and each is
  attempted at most once. A question that becomes eligible during the chain —
  for example, one reopened by a withdrawal — is deferred to the next `refresh`
  call rather than extending this one, so the chain always terminates.
- **An explicit `PENDING` is reported, not hidden.** `PENDING` is a legal
  submission outcome. A refresh may return while a deliberately pending
  question remains, or while a question that became eligible mid-chain is
  deferred, and the answer says so rather than implying completion.
- **A brand-new question cannot enter a chain by proposal.** A non-bound
  question submitted during refresh is a correction nomination and is rejected
  before persistence unless that exact scope is already stored. The rejection
  is explicit, persists nothing, and leaves the continuation and snapshot
  usable; the only mid-chain growth is a question reopened by a withdrawal,
  which is deferred and reported.

### Documentation

- The store schema is documented as 9, and `span-install --migrate-store` is
  documented as migrating schema 7 or 8 to 9. Five places previously said 7,
  and one described a 7→8 migration that does not exist.
- Status documentation describes what `status` actually reports for a pending
  question.
- The agent skills were rewritten for concision: the primary skill is about
  half its previous length, and the two specialty skills now carry only their
  task-specific steps and point at the primary. Every operation, contract, and
  state vocabulary is unchanged. The hand-maintained Python submission example
  was removed because the pending brief already returns the authoritative
  template, and the old example had drifted into an invalid construction.
- The packaged skills and lifecycle snippet are generated at build time from
  `skills/` and `docs/agents-snippet.md`. The repository no longer carries a
  second committed copy of any skill or the snippet; a wheel and a wheel built
  from the sdist both contain byte-identical assets.
- The obsolete mapping vocabulary is gone from the status requirement, the
  lifecycle guide, and the onboarding runbook: target membership is computed at
  admission and is never submitted, and there is no mapping unit, exclusion, or
  unresolved-mapping decision. Recovery guidance in the MCP reference and the
  architecture guide now names both paths: stored recovery inputs when
  recorded, otherwise `refresh` on the subject.

### Not in this release

- No gate re-run. The five-task economics remain unmeasured since 0.8.1, and
  this release does not claim them.
- No change to the continuation contract. Continuations stay ephemeral,
  process-scoped, and single-use; no token is persisted.
- No new question disposition. Whether withdrawal needs a state distinct from
  `NOT_APPLICABLE` with a basis is an open decision.
- No evidence-nomination surface. An agent still cannot cite an exact source it
  found outside the discovered set; that is a separate public-input capability.
- No machine-readable action on `ResolutionRequirement` beyond the recovery
  text status needs.
- No change to status payload weight. The scoped path is already bounded; the
  atomic single-subject page is by design. Measurement comes first.
## 0.8.2 — 2026-10-27

**Durable work can be picked up again.**

0.8.1 fixed what the 0.8.0 gate measured. This release fixes a defect the gate
could not see: a question Span had already decided to ask could outlive the
information needed to examine it again.

A pending question is durable. The continuation that answers it is not: it is
process-local, single-use, and expires after thirty minutes. Span's stated
recovery for a lost continuation is to re-run the originating operation. For
`explain`, `impact`, `trace`, and `authority` that instruction was not
executable, because what produced the question was not stored with it.

Recovery now re-runs the originating operation with the inputs stored on the
question. Questions that no operation can recreate — those an agent proposed,
and the service-owned seed for a newly admitted area — are re-examined through
`refresh` under their persisted identity instead.

`status` now names which of the two applies.

No `0.8.2` release exists; the numbering skips it rather than inventing a
release that was never cut.

### Pending questions

- **A pending question survives the loss of its continuation.** A question
  admitted by `explain`, `impact`, `trace`, or `authority` now stores the
  operation and the resolved inputs that produced it, so recovery no longer
  depends on the caller remembering inputs it was never given.
- **`refresh` and `initialize_target` needed no new storage.** A refresh
  question is re-examined by calling `refresh` on its subject, and a target
  campaign is recovered from its durable target association. Both were already
  recoverable; only the status message was missing.
- **`status` names the recovery action.** A pending question with no live
  continuation now produces a requirement that says how to pick it up: the
  originating operation and its stored inputs when the question records them,
  and `refresh` on the subject otherwise. A row written before this release
  decodes with no stored recipe and takes the `refresh` path.

### Refresh

- **Refresh drains a subject before advancing.** The frontier is
  question-level; the closeout unit was subject-level. A subject with two
  pending questions used to answer one and report completion.
- **Each question is attempted once per refresh chain.** The eligible questions
  for a subject are snapshotted when the chain reaches it, and each is
  attempted at most once. A question that becomes eligible during the chain —
  for example, one reopened by a withdrawal — is deferred to the next `refresh`
  call rather than extending this one, so the chain always terminates.
- **An explicit `PENDING` is reported, not hidden.** `PENDING` is a legal
  submission outcome. A refresh may return while a deliberately pending
  question remains, or while a question that became eligible mid-chain is
  deferred, and the answer says so rather than implying completion.
- **A brand-new question cannot enter a chain by proposal.** A non-bound
  question submitted during refresh is a correction nomination and is rejected
  before persistence unless that exact scope is already stored. The rejection
  is explicit, persists nothing, and leaves the continuation and snapshot
  usable; the only mid-chain growth is a question reopened by a withdrawal,
  which is deferred and reported.

### Documentation

- The store schema is documented as 9, and `span-install --migrate-store` is
  documented as migrating schema 7 or 8 to 9. Five places previously said 7,
  and one described a 7→8 migration that does not exist.
- Status documentation describes what `status` actually reports for a pending
  question.
- The agent skills were rewritten for concision: the primary skill is about
  half its previous length, and the two specialty skills now carry only their
  task-specific steps and point at the primary. Every operation, contract, and
  state vocabulary is unchanged. The hand-maintained Python submission example
  was removed because the pending brief already returns the authoritative
  template, and the old example had drifted into an invalid construction.
- The packaged skills and lifecycle snippet are generated at build time from
  `skills/` and `docs/agents-snippet.md`. The repository no longer carries a
  second committed copy of any skill or the snippet; a wheel and a wheel built
  from the sdist both contain byte-identical assets.
- The obsolete mapping vocabulary is gone from the status requirement, the
  lifecycle guide, and the onboarding runbook: target membership is computed at
  admission and is never submitted, and there is no mapping unit, exclusion, or
  unresolved-mapping decision. Recovery guidance in the MCP reference and the
  architecture guide now names both paths: stored recovery inputs when
  recorded, otherwise `refresh` on the subject.

### Not in this release

- No gate re-run. The five-task economics remain unmeasured since 0.8.1, and
  this release does not claim them.
- No change to the continuation contract. Continuations stay ephemeral,
  process-scoped, and single-use; no token is persisted.
- No new question disposition. Whether withdrawal needs a state distinct from
  `NOT_APPLICABLE` with a basis is an open decision.
- No evidence-nomination surface. An agent still cannot cite an exact source it
  found outside the discovered set; that is a separate public-input capability.
- No machine-readable action on `ResolutionRequirement` beyond the recovery
  text status needs.
- No change to status payload weight. The scoped path is already bounded; the
  atomic single-subject page is by design. Measurement comes first.

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
