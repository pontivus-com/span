# Agent Skills integration

The packaged skills guide the agent through the public lifecycle. They do not
run inside the semantic core, originate authority, or decide correctness.
The installed tool schemas and [MCP reference](mcp.md) own request grammar;
[lifecycle](lifecycle.md) owns the procedure.

| Canonical source | Responsibility |
| --- | --- |
| `skills/span/SKILL.md` | Ask, investigate, admit, record, reuse, and reassess; preserve identities and limits. |
| `skills/span-change-context/SKILL.md` | Prepare a material change using applicable saved understanding and current support. |
| `skills/span-document/SKILL.md` | Explain one scope, record coherent supported conclusions and gaps, then read back. |
| `docs/agents-snippet.md` | The managed lifecycle block copied into a target's `AGENTS.md`. |

Skills use the nineteen public tools. They do not require a campaign, a
semantic-question taxonomy, or an interpretation continuation. A real
investigation can span files and record directly from an evidence-only context.
They must keep missing authority, failed admission, omissions, disputes, and
noncurrent support explicit.

## Distribution and upgrades

Canonical skills and the snippet are copied into package assets by the build
owner, `scripts/sync_assets.py` through `setup.py`. Generated copies are never
edited manually. The installer deploys the managed assets and preserves
foreign configuration. See [install](install.md).

Restart/reconnect hosts after upgrading and check that active skills and
managed rules describe the same surface as the installed binary. A stale
host-local skill can still teach the retired procedure even when tools were
upgraded. This repository's source/package updates do not claim that every
existing host-local copy has been replaced.

`tests/unit/test_skills.py`, `test_agents_snippet.py`, and the asset cases in
`test_install.py` exercise the source/asset boundaries. Skills remain
optional; ordinary retrieval and recording check support without them or hooks.
