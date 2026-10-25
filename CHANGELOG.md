# Changelog

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
