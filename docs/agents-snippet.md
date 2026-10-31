## Span lifecycle (MCP only)

When work touches unfamiliar code, cross-boundary effects, or saved meaning: use Span. Skip it for trivial local edits.

- Ask `understand_question` first with the question and an exact scope. It returns saved candidates with live support, inspectable evidence, or an explicit limit. No status preflight is required. `READY` means the store works, not that the repository is understood.
- Before any repository-scoped call, obtain the exact registered `repository_id` from `tools/list` or an `initialize_repository` result. Never pass a filesystem path as the ID. `understand_retrieve`, `reassess`, `verification_support`, and `evidence_extend` also take `repository_id` as a transport routing key.
- When no store exists: stop ordinary work. `initialize_repository` runs once in a dedicated setup session; it binds the root and declared authority seeds and creates no understanding.
- To record: `start_context` (or `evidence_start` for evidence-only work) issues a recoverable server context; admit exact sources with `evidence_start`/`evidence_extend`; then call the one matching `record_create`, `record_add`, `record_confirm`, `record_correct`, `record_replace`, or `record_withdraw` tool. Recording is atomic and returns a receipt. Reuse the same identity when retrying a lost response.
- Disputes: `record_challenge` creates an explicit challenge; settle or carry it forward through `record_update` with named challenge dispositions. Challenges never settle implicitly.
- Independent verification: `record_verification` records what was actually tested; `verification_support` qualifies that run. An unsupported attestation never becomes a proven pass.
- When support may have changed: `reassess` the exact understanding and version. Before a material edit, understand the scope and reassess relevant records.
- `locate` and `neighbors` provide structural navigation only; cite them as evidence, never as authority. In-body content search stays with grep.
- Use outside tools to edit and test. Span never edits, runs tests, selects models, or writes the target.
- Hooks are optional event-local notices. They never record, reassess, interpret, or rebuild; a missed hook never makes stale understanding current.
- Keep `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` verbatim. Missing authority stays missing.

Detail: [lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md),
[onboarding runbook](https://github.com/pontivus-com/span/blob/master/docs/onboarding-runbook.md),
[Span skill](https://github.com/pontivus-com/span/blob/master/skills/span/SKILL.md).
