# Lifecycle-hook integration

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
is the all-current statement. It keeps no status policy of its own:
each command opens the canonical shell context (never provisioning,
never creating a store or schema) and makes exactly one
`status(..., mode=HOOK_FAST)` call, then renders only the returned
notice. Session-start and session-stop select the
registered repository containing the active working directory; callers
may override it with `--repo-root`. A working directory outside every
registered repository is a silent no-op. Per-host trigger support
(opencode, codex, claude): `integrations/hosts/triggers.md`.

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

---

## What hooks surface

Span can integrate with host lifecycle events such as:

```text
session-start
source-changed
session-stop
```

Hooks are report-only.

They can surface conditions such as:

- uninitialized state;
- unavailable repository;
- stale or unverifiable understanding in the changed scope;
- moved dependents whose recorded evidence no longer matches.

They do not report coverage inventories, open questions, or pending work:
those belong to normal `status`. An automatic notice is event-local.

They do not:

- initialize semantic knowledge;
- interpret repository meaning;
- invoke a model;
- run a semantic refresh;
- rebuild the structural index;
- make implementation decisions.

When nothing relevant needs attention, hooks stay quiet.

See [`integrations/hosts/triggers.md`](../integrations/hosts/triggers.md).

---
