# Span host trigger support (addendum D LIFE-D-01)

Evidence-backed per-host capability record: which lifecycle triggers
each host implements, what falls back to skill-driven procedure, and
what is unsupported. Sources are the implemented integrations in this
directory and `src/span/shell/install.py`; nothing here is claimed
without an implemented counterpart. The no-trigger fallback path is
exercised by D-ACCEPT-06 R-02 (ACCEPT-D-01).

Status key: implemented (code present) · tested (automated coverage
named) · unsupported (host cannot do it) · planned (cleanly missing,
no claim). No row claims tested without a named test.

Session lifecycle notices are scoped to the registered repository
containing the host process working directory. OpenCode passes that root
explicitly; Codex relies on the hook process working directory. A hook
outside every registered target is silent. `source-changed` continues to
route each changed path to its longest matching registered root.

## opencode (`hosts/opencode/span-hooks.js`, deployed as a plugin)

| Trigger | span-hooks command | Status | Evidence |
|---|---|---|---|
| `session.created` | `session-start` | implemented + tested | `test_hooks_runner.py` covers the command; plugin event mapping verified live 2026-10-08 against a fixture store (silent-when-clean, exception lines, scratch node harness — no committed JS runner); installed-CLI arrival re-demonstrated 2026-10-09 (exit 0 silent on CURRENT store; uninitialized-scope notice on empty data dir, no mutation) |
| `tool.execute.after` (`edit`, `write`) | `source-changed <paths>` | implemented + tested | same as above (unchanged-silence + moved-notice both observed; installed-CLI no-op on unchanged path 2026-10-09) |
| `session.idle` | `session-stop` | implemented + tested | same as above (clean-close silence + dirty-close counts both observed; installed-CLI clean-close silence 2026-10-09) |
| other events | — | unsupported | plugin ignores them by construction |

Vendor-app event→plugin dispatch remains outside observable boundary
(verified to plugin code + installed hook CLI + MCP wire). Arrival
evidence: `hook_arrivals_opencode.json` (adoption-ledger live section).

Fallback: events the host does not emit are covered by the
skill-driven lifecycle (`skills/span/SKILL.md` operation lifecycle +
closeout duty below): the agent runs `status`/`refresh` explicitly.

## codex (`~/.codex/hooks.json`, wired by `install.py:wire_codex_hooks`)

| Trigger | span-hooks command | Status | Evidence |
|---|---|---|---|
| `SessionStart` (`startup\|resume\|compact`) | `session-start` | implemented; wiring covered by tests (no live arrival observed) | `wire_codex_hooks` appends the entry; `test_install.py` covers merge/dedupe paths |
| `PostToolUse` (`apply_patch\|Write\|Edit\|MultiEdit`) | `source-changed` | implemented; wiring covered by tests | same as above |
| `Stop` | `session-stop` | implemented; wiring covered by tests | same as above |
| absent CLI / absent `hooks.json` | — | unsupported (installer skips, never fails) | `register_codex`/`wire_codex_hooks` skip paths |

Live session note (2026-10-09, CLI 0.162.0 standalone `codex exec` against a temp
`span-actd` registration, since removed): the transcript shows `PreToolUse` and
`Stop` hook events around a `span-actd` `explain` that completed as
`SemanticAnswer`; entry-level attribution to span's wired entries (vs the user's
other hooks) is not established from the transcript, and no `SessionStart`
arrival was observed. The live MCP exchange itself is evidenced in the adoption
ledger (`a2_codex.json`). Event-name check (2026-10-09): the 0.162.0
standalone binary contains both `PreToolUse` and `PostToolUse` event
names, so the configured `PostToolUse` entry names a real event; firing
of span's entry specifically remains unobserved.

Wiring is skipped when no `hooks.json` exists or the codex CLI is
absent (installer reports, never fails). Fallback: identical
skill-driven procedure; where a host cannot enforce closeout, that
limitation is stated by the agent in its closeout report rather than
assumed away.

## Out of scope for every host

Hooks never initialize, interpret, rebuild, expand, refresh, or invoke
a model (report-only, enforced by the hook runner's read-only
design). A `refresh` call without re-examination proves nothing;
adequacy is in resubmitted content (C-11).
