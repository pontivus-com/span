# Host trigger and delivery status

The active lifecycle is documented in [lifecycle](../../docs/lifecycle.md).
Hooks deliver lifecycle reminders. The agent follows [the required lifecycle](../../docs/lifecycle-contract.md#required-agent-completion)
for investigation, retention and reassessment. Lifecycle operations check
declared support independently of hook delivery.

Beta-3 T14-H2–H6 lifecycle-hook implementation and executable acceptance are
present on the correction branch. T14-H7 owns the exact-head CI closure. The
tables below describe the delivered managed wiring; they do not promote
configured wiring or automated acceptance into an authenticated live-model
delivery claim.

## Managed integration

| Host | Implemented integration | Version-1 delivery qualification |
| --- | --- | --- |
| Codex | MCP registration, skills, managed repository snippet; `SessionStart` plus canonical `apply_patch` `PostToolUse` hooks are appended to an existing `~/.codex/hooks.json` with the same configured Span data directory as the MCP registration. The post-tool adapter reads documented `tool_input.command`, normalizes exact patch file markers, evaluates the canonical changed-scope preview and returns structured `additionalContext`. | Managed wiring and native-payload translation are executable-tested. Authenticated Beta-3 model-delivered hook behavior remains **UNVERIFIED**. |
| OpenCode | MCP registration, skills, managed snippet, and the installer-deployed lifecycle plugin: a bounded MCP readiness wait, one composed session-entry notice, documented `edit`/`write`/`patch` normalization, retained complete changed-scope accumulation and completion handoff. Unsupported native shapes are diagnosed as incomplete rather than guessed. | The wheel-bundled plugin has an executable deployed-wrapper/real-`span-hooks`/temporary-store acceptance path. Authenticated Beta-3 live-model delivery remains **UNVERIFIED**. |
| Claude Code | User-scope MCP registration, skills under an existing `~/.claude` root, and lifecycle hooks in `~/.claude/settings.json`. | Registration/health and installer behavior are verified. Authenticated Beta-3 model-delivered grammar and caller identity remain **UNVERIFIED**. |

The supported managed hosts are Codex, OpenCode, and Claude Code. Current
Beta-3 documentation claims only the delivery evidence actually observed for
the assembled candidate; historical captures remain evidence for their named
candidate and are never promoted into current live-model delivery proof. Other MCP hosts can connect manually; no universal
compatibility or model-delivery claim follows from stdio compatibility.

## Hook entries

The canonical installer implementation is
`src/span/shell/install/hosts.py`; the runtime is `src/span/shell/hooks.py`.

| Host event | Managed behavior |
| --- | --- |
| Codex `SessionStart` | `span-hooks session-start` |
| Codex `PostToolUse` matching canonical `apply_patch` | `span-hooks codex-post-tool`; reads documented `tool_input.command`, normalizes exact add/update/delete/move patch markers, evaluates the canonical changed-scope projection, and emits structured `hookSpecificOutput.additionalContext` when action is required |
| Claude Code `SessionStart` | `span-hooks session-start` |
| Claude Code `PostToolUse` for `Write|Edit|MultiEdit` | `span-hooks source-changed` |
| Claude Code `Stop` | `span-hooks session-stop` |
| OpenCode session creation / first-context fallback | `span-hooks session-start`; both delivery paths share the same composed entry obligation and do not emit competing primers |
| OpenCode `tool.execute.after` for documented `edit`, `write` or `patch` | normalize `input.path` or `input.patchText`, preserve the complete per-session union, then invoke `span-hooks source-changed` |
| OpenCode `session.idle` | invoke `span-hooks session-stop` only for retained changed paths that have not yet been handed off |

Every installer-managed command carries the configured Span data-directory
identity; a non-default installation does not fall through to the platform
default. OpenCode's deployed wrapper already provides this identity, Claude
commands already carry it explicitly, and Beta-3 applies the same rule to
Codex.

### Pre-investigation event qualification

The current managed hosts expose before-tool interception APIs, but Beta 3 does
not claim a pre-investigation hook for any of them. A compliant reminder must be
non-blocking *and* visible to the agent before source access so the agent can
still choose the existing `ask` lifecycle action. The currently supported
managed delivery paths do not establish that combination without turning the
hook into a blocker or approval mechanism, which FD-58 forbids.

Accordingly, pre-investigation remains guidance-only for Codex, Claude Code and
OpenCode in Beta 3. This is an explicit unsupported interception point, not a
silent compatibility promise. No shell-command text is inspected to infer
reads.

For OpenCode edit/write interception, the V2 adapter consumes only documented
`event.tool`, `event.sessionID` and `event.input` fields. `edit`/`write` use
`input.path`; `patch` uses `input.patchText` and the host's exact add/update/delete
patch sections (including the move target carried by the native patch grammar).
Missing or adjacent legacy-shaped fields are not guessed into a changed-scope
carrier; the plugin emits an explicit incomplete-scope reminder instead. The
per-session path union has no arbitrary capacity eviction or correctness-bearing
notice truncation and is released only after successful handoff/no-action
projection or explicit session deletion.

For Codex, the managed post-edit interception point is canonical `apply_patch`
`PostToolUse`. The adapter consumes documented `tool_name` and
`tool_input.command`, parses only the native patch file markers, and returns
model-visible structured `additionalContext`. Plain PostToolUse stdout is not
used. Span does not install a Codex `Stop` hook because this adapter retains no
host-local changed-scope state after the immediate post-tool handoff.

The OpenCode plugin scope is explicit: `--opencode-plugin-scope
global|local|none`. Under `global` the plugin is deployed under Span's own data
root and registered in the host's global `opencode.json`; it writes nothing into
a target. A Span plugin found in an explicitly inspected target is reported as
a conflict and left untouched. Under `local` and `none`, the target plugin is
user-managed: Span removes its own global registration and reports the local
copy without modifying it. Only targets passed with `--repo` are mutable;
receipt targets not selected are inspected read-only and yield `conflict` if a
Span-owned copy remains.

| Scope | Selected target (`--repo`) | Receipt-only target | Global registration |
| --- | --- | --- | --- |
| `global` | report `conflict`; leave copy in place | read-only; `conflict` if present | update |
| `local` | report only | read-only; report only | remove Span-owned |
| `none` | report only | read-only; report only | remove Span-owned |

A fresh install defaults to `global`; an upgrade uses the receipt scope and
stops if it is absent or ambiguous. The authoritative full matrix is in
[install](../../docs/install.md#opencode).

The edit-time support notice fires when a
changed path affects recorded understanding. Session notices select the
registered root containing the working directory. Changed paths route to their
longest matching registered root. Missing hook settings files or absent CLIs
lead to an explicit skipped-wiring result. Foreign entries are preserved;
reinstall replaces Span entries whose binary path or matcher changed instead of
accumulating them. Claude settings are read and modified only within the
Span-owned registration and hook entries; foreign settings remain untouched.

Wiring and source tests establish merge/registration and notice content, not
live arrival. The historical 0.11.0 direct stdio lane exercises exact
recorded-question selection, but it does not certify Version-1 host argument
preservation. Capture
configured, invoked, scoped, submitted arguments, server-received JSON and
delivered observations separately. A quiet
hook proves neither complete coverage nor global currency.

## Agent procedure without hooks

For governed work, resolve Functional Pyramid participation/health first. Then
call `ask` for current shared understanding or inspectable evidence and
`record` supported conclusions when established. New or changed semantic
meaning is CAPTURED and remains pending until a separate reviewer curates the
exact CURRENT revision for shared reuse. Before editing, ask for current
orientation; after it, call changed-scope `reconsider`, use external tests,
and record explicit dispositions. Use the challenge branch of `reconsider`
for disputes. Keep unsupported scope and open disputes visible.
See the [router skill](../../skills/span-router/SKILL.md) and
[usage](../../docs/usage.md).
