# Host trigger and delivery status

The active lifecycle is documented in [lifecycle](../../docs/lifecycle.md).
Hooks are optional notices; the agent still owns investigation, recording,
reassessment, edits, and tests. No host trigger is required to make ordinary
retrieval or new recording check declared support.

## Managed integration

| Host | Implemented integration | Delivery qualification |
| --- | --- | --- |
| Codex | MCP registration, skills, managed repository snippet; hooks appended to an existing `~/.codex/hooks.json`. | 0.9.1: three-tool delivery captured (`gpt-5.6-luna`), including closed-union rejection, flat create, verification, replay, and restart. The flat-create re-capture is pending (account quota). Hook arrival is not established. |
| OpenCode | MCP registration, skills, managed snippet, and the installer-deployed lifecycle plugin: a bounded MCP readiness wait plus the FD-58 adoption notice. | 0.9.1: three tools; flat-create delivery captured including verification and replay; with the plugin the first `ask` precedes the first source read in 5/5 measured runs. |

The supported registration targets are Codex and OpenCode. Delivery is claimed
only for a host with a recorded capture; both supported hosts have a three-tool
capture, and OpenCode has the flat-create re-capture. Other MCP hosts can
connect manually; no universal compatibility or model-delivery claim follows
from stdio compatibility.

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
a target. A legacy per-target `.opencode/plugins/span-hooks.js` copy is moved to
`<target>/.opencode/span-retired/`, never deleted, so only the installed plugin
declares the `span-hooks` id. Only targets passed with `--repo` are migrated;
receipt targets not selected are inspected read-only and yield `conflict` if a
Span-owned copy remains. Under `local` and `none`, the target plugin is
user-managed: Span removes its own global registration and reports the local
copy.

| Scope | Selected target (`--repo`) | Receipt-only target | Global registration |
| --- | --- | --- | --- |
| `global` | retire Span-owned copies | read-only; `conflict` if present | update |
| `local` | report only | read-only; report only | remove Span-owned |
| `none` | report only | read-only; report only | remove Span-owned |

A fresh install defaults to `global`; an upgrade uses the receipt scope and
stops if it is absent or ambiguous. The authoritative full matrix is in
[install](../../docs/install.md#opencode).

The notices are advisory and the edit-time notice fires only when a
changed path affects recorded understanding. Session notices select the
registered root containing the working directory. Changed paths route to their
longest matching registered root. Missing hook settings files or absent CLIs
lead to an explicit skipped-wiring result. Foreign entries are preserved;
reinstall replaces Span entries whose binary path or matcher changed instead of
accumulating them. Claude Code is not a supported target; Span-owned hook
entries left in `~/.claude/settings.json` by an earlier version are removed on
install and uninstall.

Wiring tests establish merge/registration behavior, not live arrival. Capture
configured, invoked, scoped, and delivered observations separately. A quiet
hook proves neither complete coverage nor global currency.

## Agent procedure without hooks

Call `ask` for current understanding or inspectable evidence, then `record`
useful findings with the evidence you hold. Before a material edit, ask for
current support; after it, call `reconsider`, use external tests, and record
explicit updates. Keep unsupported scope and open disputes visible.
See the [router skill](../../skills/span-router/SKILL.md) and
[usage](../../docs/usage.md).
