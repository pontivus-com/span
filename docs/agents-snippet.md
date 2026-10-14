## Span lifecycle (MCP only)

When work touches unfamiliar code, cross-boundary effects, or saved meaning: use Span. Skip it for trivial local edits.

- When starting: normal `status` with no target (bounded persisted coverage: current, incomplete, stale/unverifiable, unassessed), then `explain` on target (what it is/does/governs, with evidence, authority, freshness). `READY` means store works, not understood. If the deployed runtime returns readiness only, treat it as the known coverage-inventory gap pending D-ACCEPT-08 and continue with exact-target `status`/`explain`.
- Before any repository-scoped call, obtain the exact canonical registered `repository_id` from `tools/list` or a successful `initialize_repository` response. Never pass a filesystem path as the ID; preserve the registered value unchanged.
- When repo is `UNINITIALIZED`: stop normal work. `initialize_repository` runs once, in a dedicated setup session. No interpretation happens here.
- When user gives an exact directory: `initialize_target` with that exact scope plus objective; it returns the next typed unit, advance via `submit_interpretation`. Cover every material area with a persisted disposition; one answer is never completion; close with fresh `status`/`explain` readback. Otherwise use question-local `explain`; use `establish_baseline=True` only to baseline an ordinary root.
- When edit is material: `impact` with target plus change before editing. Pre-change brief (impacts, conditions, authority, verification, blockers), never approval.
- When path or governance is unclear: `trace` (producers, carriers, consumers, boundaries, lifecycle path) / `authority` (sources with status, applicability, precedence, conflicts side-by-side), only where required.
- When Span returns `PendingInterpretation`: do that one bounded slice with your model, follow its brief for that slice only, then `submit_interpretation`. Returns the answer or the next pending unit; repeat until an answer returns. Use `reissue_interpretation` once only for an explicitly eligible interpretation-task ingress failure before semantic submission is admitted; a malformed payload or returned `ingress`/`validation` response reuses the same continuation. The same task returns unchanged. An expired or lost continuation never reissues: re-run the idempotent original operation instead.
- When editing: use outside tools. Span never edits, runs tests, orchestrates, selects or invokes models, rebuilds the structural index, or writes target.
- When done editing, same change, editing agent owns it: scoped `status`, then outside tests, then scoped `refresh` (explicit reinterpretation of stale scope, never automatic, never expands scope), then scoped `status` again. Bare `refresh` proves nothing.
- When you need structure, not meaning: `locate` (find a symbol, outline a file, list target members) / `neighbors` (bounded callers/callees, upstream/downstream/both). Both return navigation evidence only — cite it as evidence, never as authority. In-body content search stays with grep.
- Hooks only call `status` in `HOOK_FAST` (compact notice only). They never initialize, explain, impact, trace, authority-check, refresh, interpret, or rebuild.
- Keep `PARTIAL`/`AMBIGUOUS`/`CONFLICTED`/`UNRESOLVED`/`STALE`/`UNVERIFIABLE` verbatim. Missing authority stays missing.

Detail: `span/docs/lifecycle.md`, `span/docs/onboarding-runbook.md`, `span/skills/span/SKILL.md`.
