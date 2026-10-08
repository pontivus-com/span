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

## opencode (`hosts/opencode/span-hooks.js`, deployed as a plugin)

| Trigger | span-hooks command | Status | Evidence |
|---|---|---|---|
| `session.created` | `session-start` | implemented + tested | `test_hooks_runner.py` covers the command; plugin event mapping verified live 2026-10-08 against a fixture store (silent-when-clean, exception lines, scratch node harness — no committed JS runner) |
| `tool.execute.after` (`edit`, `write`) | `source-changed <paths>` | implemented + tested | same as above (unchanged-silence + moved-notice both observed) |
| `session.idle` | `session-stop` | implemented + tested | same as above (clean-close silence + dirty-close counts both observed) |
| other events | — | unsupported | plugin ignores them by construction |

Fallback: events the host does not emit are covered by the
skill-driven lifecycle (`skills/span/SKILL.md` operation lifecycle +
closeout duty below): the agent runs `status`/`refresh` explicitly.

## codex (`~/.codex/hooks.json`, wired by `install.py:wire_codex_hooks`)

| Trigger | span-hooks command | Status | Evidence |
|---|---|---|---|
| `SessionStart` (`startup\|resume\|compact`) | `session-start` | implemented; wiring tested dry | `wire_codex_hooks` appends the entry; `test_install.py` covers merge/dedupe paths |
| `PostToolUse` (`apply_patch\|Write\|Edit\|MultiEdit`) | `source-changed` | implemented; wiring tested dry | same as above |
| `Stop` | `session-stop` | implemented; wiring tested dry | same as above |
| absent CLI / absent `hooks.json` | — | unsupported (installer skips, never fails) | `register_codex`/`wire_codex_hooks` skip paths |

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
