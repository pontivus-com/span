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

## opencode (skill-driven fallback; no plugin deployment)

Per Addendum E §3/E-02 the installer does not deploy
`.opencode/plugins/span-hooks.js` into registered repositories. It does
synchronize the managed lifecycle block in `AGENTS.md`; the reference
implementation is retained at
`hosts/opencode/span-hooks.js`; the `span-hooks` CLI commands
(`session-start`, `source-changed`, `session-stop`) remain tested via
`test_hooks_runner.py`. Lifecycle notices are not claimed for OpenCode
sessions; the agent follows the skill-driven lifecycle instead.

| Duty | Agent action |
|---|---|
| orient | call the semantic operation the task needs; `explain` for ordinary orientation, `status` only when freshness/coverage is the objective |
| material change | `impact` before editing; scoped `status` → tests → scoped `refresh` → scoped `status` after |

Prior live plugin arrival evidence (`hook_arrivals_opencode.json`) is
retained as history; it does not support a current deployment claim.

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

## claude (managed: MCP registration, skills, report-only hooks)

When the Claude Code CLI is present, the installer registers Span at user
scope (`claude mcp add --scope user --transport stdio`), so the server is
available in every project rather than only where the installer ran. It
deploys skills to `~/.claude/skills` and appends report-only entries to
`~/.claude/settings.json` for the three events the Claude-style adapter
maps: `SessionStart` (readiness and baseline), post-edit `PostToolUse`
(`Write`, `Edit`, `MultiEdit` → changed-path scope), and `Stop` (session
closeout scope). Hooks are added to an existing settings file and never
created from nothing; when `~/.claude/settings.json` is absent the wiring
is reported as skipped and re-running after Claude Code has created the
file wires them. The file is backed up once to `settings.json.bak-span`,
foreign hooks and every other setting are preserved, and re-running the
installer adds no duplicates. Registration is skipped with `--no-claude`
or when the CLI is absent; installation never fails because Claude's own
configuration is broken.

Closeout remains the agent's obligation: hooks report, they never
initialize, interpret, refresh, or expand. Where a host cannot enforce
closeout, the agent states that limitation in its closeout report rather
than assuming it away.

## Out of scope for every host

Hooks never initialize, interpret, rebuild, expand, refresh, or invoke
a model (report-only, enforced by the hook runner's read-only
design). A `refresh` call without re-examination proves nothing;
adequacy is in resubmitted content (C-11).
