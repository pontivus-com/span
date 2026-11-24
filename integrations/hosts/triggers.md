# Host trigger and delivery status

The active lifecycle is documented in [lifecycle](../../docs/lifecycle.md).
Hooks deliver lifecycle reminders. The agent follows [the required lifecycle](../../docs/lifecycle-contract.md#required-agent-completion)
for investigation, retention and reassessment. Lifecycle operations check
declared support independently of hook delivery.

Beta-3 lifecycle-hook closure is currently reopened under programme tasks
T14-H2–T14-H7. The tables below describe the managed wiring that exists today;
they are not a claim that the corrected FD-58/FD-94 lifecycle-compliance
contract is fully implemented. In particular, final closure still requires
complete changed-scope handling, session edit accumulation, installation-identity
parity, singular session-entry composition and expanded executable acceptance.

## Managed integration

| Host | Implemented integration | Version-1 delivery qualification |
| --- | --- | --- |
| Codex | MCP registration, skills, managed repository snippet; hooks appended to an existing `~/.codex/hooks.json` with the same configured Span data directory as the MCP registration. | Managed wiring is supported and installer-tested. Authenticated Beta-3 model-delivered hook behavior remains **UNVERIFIED**. |
| OpenCode | MCP registration, skills, managed snippet, and the installer-deployed lifecycle plugin: a bounded MCP readiness wait plus the FD-58 adoption notice. | Managed integration and packaged notice delivery are verified by the automated plugin lane. Authenticated Beta-3 live-model delivery remains **UNVERIFIED**. |
| Claude Code | User-scope MCP registration, skills under an existing `~/.claude` root, and lifecycle hooks in `~/.claude/settings.json`. | Registration/health and installer behavior are verified. Authenticated Beta-3 model-delivered grammar and caller identity remain **UNVERIFIED**. |

The supported managed hosts are Codex, OpenCode, and Claude Code. Current
Beta-3 documentation claims only the delivery evidence actually observed for
the assembled candidate; historical captures remain evidence for their named
candidate and are never promoted into current live-model delivery proof. Other MCP hosts can connect manually; no universal
compatibility or model-delivery claim follows from stdio compatibility.

## Hook entries

The canonical installer implementation is
`src/span/shell/install/hosts.py`; the runtime is `src/span/shell/hooks.py`.

| Event | Command |
| --- | --- |
| `SessionStart` | `span-hooks session-start` |
| OpenCode prompt admission | bounded wait for the MCP connection, then `span-hooks adoption-primer` through the `context` hook |
| `PostToolUse` for configured edit tools | `span-hooks source-changed` |
| `Stop` | `span-hooks session-stop` |

Every installer-managed command carries the configured Span data-directory
identity; a non-default installation does not fall through to the platform
default. OpenCode's deployed wrapper already provides this identity, Claude
commands already carry it explicitly, and Beta-3 H4 now applies the same rule
to Codex.

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

For OpenCode edit/write interception, the V2 adapter consumes only the
documented `event.tool`, `event.sessionID`, and `event.input.path` fields.
Adjacent legacy-shaped fields are not guessed into a changed-scope carrier.

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
