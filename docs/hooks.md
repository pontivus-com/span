# Lifecycle-hook integration (plan §11.11, Phase 4.9–4.10)

## Contract

Host adapters map native events onto three host-neutral intents
(`integrations/hooks/contract.py`): `SESSION_START` (no target:
readiness + baseline only) · `SOURCE_CHANGED` (changed-path evidence
scope: fingerprint + dependency lookup + freshness classification) ·
`SESSION_STOP` (session scope: closure classification only). Adapters
keep only ephemeral session-local bookkeeping (changed paths) — not
semantic state, not authoritative, never persisted.

Automatic hooks may call **only** `status(..., mode=HOOK_FAST)`
and return its compact notice. They never initialize, explain,
impact, trace, authority-check, refresh, interpret, rebuild, or do
repository-size work. New files with no dependants stay silent
(I-32); queries surface them through coverage. Seed changes report
because seeds are explicitly relied upon. Irrelevant changes produce
no notice; uninitialized repositories produce a setup notice.

The `span-hooks` CLI runner (`src/span/shell/hooks.py`) is
exception-oriented on top of this contract: it prints only scopes
needing action and stays silent when everything is current. Silence
is the all-current statement. Session-start and session-stop select the
registered repository containing the active working directory; callers
may override it with `--repo-root`. A working directory outside every
registered repository is a silent no-op. Per-host trigger support
(opencode, codex, fallback): `integrations/hosts/triggers.md`.

## Responsibility matrix

| Concern | Owner | Cannot |
|---|---|---|
| Semantic truth | functional core | MCP, skills, hooks |
| Transport | MCP shell (`shell/mcp*.py`) | define semantics |
| Orchestration guidance | skills | establish/reinterpret semantics |
| Lifecycle detection | host adapters | semantic/refresh/init work |
| Freshness classification | core + service | hooks (report only) |
| Model access | invoking agent | Span (no endpoints/keys/selection) |

## Reference adapter (Claude-style)

`integrations/hooks/hosts/claude/adapter.py`: `SessionStart` →
`SESSION_START`; post-edit `Write`/`Edit`/`MultiEdit` →
`SOURCE_CHANGED`; `Stop` → `SESSION_STOP`; anything else (reads,
unknown hooks, malformed events) → silence (`None`). `run_automatic_hook`
executes the HOOK_FAST status call and asserts the notice type.
`tests/integration/test_hooks.py` pins mapping, safety, silence, and
the adapter's operation allowlist structurally.
