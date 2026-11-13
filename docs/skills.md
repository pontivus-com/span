# Agent Skills integration

Agent work follows [the required Span lifecycle](lifecycle-contract.md#required-agent-completion).

The packaged skills guide the agent through the three public lifecycle moments.
They do not run inside the semantic core, originate authority, or decide
correctness. The installed tool schemas and [MCP reference](mcp.md) own request
grammar; [lifecycle](lifecycle.md) owns the procedure.

| Canonical source | Responsibility |
| --- | --- |
| `skills/span-router/SKILL.md` | Moment → tool; the default-reflex table. Start here. |
| `skills/span-before-you-read/SKILL.md` | `ask`, exact surface selection, ambiguity, continuation, surface-first reuse, and `no_match` recovery. |
| `skills/span-after-change/SKILL.md` | `reconsider` after editing, then re-establish actual loss. |
| `skills/span-record/SKILL.md` | Record/update/verify and declare a service/domain boundary. |
| `docs/agents-snippet.md` | The managed lifecycle block copied into a target's `AGENTS.md`. |

Skills use exactly `ask`, `record`, and `reconsider`. They do not choose a
record variant, fetch a context id, or treat a gap as a failure. They must keep
missing authority, failed admission, omissions, disputes, and noncurrent
support explicit. `reconsider` is described as an after-edit operation;
"before editing" is `ask`.

## Distribution and upgrades

Canonical skills and the snippet are copied into package assets by the build
owner, `scripts/sync_assets.py` through `setup.py`. Generated copies are never
edited manually. The installer deploys the canonical current skill set and
removes only stale skill directories with valid Span ownership metadata;
foreign or unowned directories are preserved. See [install](install.md).

Restart/reconnect hosts after upgrading and check that active skills and managed
rules describe the same surface as the installed binary. A stale host-local
skill can still teach a retired procedure even when tools were upgraded. This
repository's source/package updates do not claim that every existing host-local
copy has been replaced.

`tests/unit/test_skills.py`, `test_agents_snippet.py`, and the asset cases in
`test_install.py` exercise the source/asset boundaries. The runtime does not read skill text to evaluate support.
Agent-facing guidance projects the required lifecycle in the contract; absent reminders do not waive it.
