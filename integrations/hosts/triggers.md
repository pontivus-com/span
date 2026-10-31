# Host trigger and delivery status

The active lifecycle is documented in [lifecycle](../../docs/lifecycle.md).
Hooks are optional notices; the agent still owns investigation, recording,
reassessment, edits, and tests. No host trigger is required to make ordinary
retrieval or new recording check declared support.

## Managed integration

| Host | Implemented integration | Delivery qualification |
| --- | --- | --- |
| Codex | MCP registration, skills, managed repository snippet; hooks appended to an existing `~/.codex/hooks.json`. | Live beta MCP conformance uses the non-editable 0.9.0 package with hooks disabled. Hook arrival is not established by that trial. |
| OpenCode | MCP config when an `opencode.json` is present; skills and managed snippet. Reference hook plugin retained without active deployment. | Earlier lifecycle trial evidence exists; final beta package delivery was not revalidated. |
| Claude Code | User-scope MCP registration, skills, report-only hooks appended to existing settings. | Live model-delivered grammar/identity remain UNVERIFIED under the owner waiver; registration health is a separate observation. |

Codex alone is the live beta acceptance target by owner direction. This does
not relabel OpenCode or Claude as tested and does not remove their implemented
integration. Other MCP hosts can connect manually; no universal compatibility
or model-delivery claim follows from stdio compatibility.

## Hook entries

The canonical installer implementation is
`src/span/shell/install/hosts.py`; the runtime is `src/span/shell/hooks.py`.

| Event | Command |
| --- | --- |
| `SessionStart` | `span-hooks session-start` |
| `PostToolUse` for configured edit tools | `span-hooks source-changed` |
| `Stop` | `span-hooks session-stop` |

Session notices select the registered root containing the working directory.
Changed paths route to their longest matching registered root. Missing hook
settings files or absent CLIs lead to an explicit skipped-wiring result.
Foreign entries are preserved; reinstallation avoids duplicate Span entries.

Wiring tests establish merge/registration behavior, not live arrival. Capture
configured, invoked, scoped, and delivered observations separately. A quiet
hook proves neither complete coverage nor global currency.

## Agent procedure without hooks

Ask a scoped `understand_question`, inspect applicable saved understanding,
admit exact evidence, and record useful findings. Before a material edit,
qualify the relevant records; after it, use external tests, `reassess`, and
explicit recording updates. Keep unsupported scope and open disputes visible.
See the [Span skill](../../skills/span/SKILL.md) and [usage](../../docs/usage.md).
