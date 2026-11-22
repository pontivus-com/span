# Host trigger and delivery status

The active lifecycle is documented in [lifecycle](../../docs/lifecycle.md).
Hooks deliver lifecycle reminders. The agent follows [the required lifecycle](../../docs/lifecycle-contract.md#required-agent-completion)
for investigation, retention and reassessment. Lifecycle operations check
declared support independently of hook delivery.

## Managed integration

| Host | Implemented integration | Version-1 delivery qualification |
| --- | --- | --- |
| Codex | MCP registration, skills, managed repository snippet; hooks appended to an existing `~/.codex/hooks.json`. | Managed integration remains supported. Historical 0.9.1 delivery captures do not certify Version 1. Candidate-specific live model delivery is **UNVERIFIED** until T13 captures the assembled `1.0.0b1` candidate. |
| OpenCode | MCP registration, skills, managed snippet, and the installer-deployed lifecycle plugin: a bounded MCP readiness wait plus the FD-58 adoption notice. | Managed integration and packaged notice delivery are verified. Historical 0.9.1/0.11 captures remain historical evidence only; candidate-specific live model delivery is **UNVERIFIED** until T13. |
| Claude Code | User-scope MCP registration, skills under an existing `~/.claude` root, and lifecycle hooks in `~/.claude/settings.json`. | Registration/health and installer behavior are verified; authenticated Version-1 model-delivered grammar and caller identity remain **UNVERIFIED** pending T13. |

The supported managed hosts are Codex, OpenCode, and Claude Code. Version-1
delivery is claimed only from an assembled-candidate T13 capture. Historical
captures remain evidence for their named candidate and are never promoted into
Version-1 delivery proof. Other MCP hosts can connect manually; no universal
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

Call `ask` for current understanding or inspectable evidence, then `record`
supported conclusions when established, with the evidence you hold. Before editing, ask for
current support; after it, call `reconsider`, use external tests, and record
explicit updates. Keep unsupported scope and open disputes visible.
See the [router skill](../../skills/span-router/SKILL.md) and
[usage](../../docs/usage.md).
