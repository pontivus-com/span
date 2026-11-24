# Agent Skills integration

Agent work follows [the required Span lifecycle](lifecycle-contract.md#required-agent-completion).
The skills project that lifecycle into the moments a coding agent or reviewer
recognizes; they do not create another semantic or requirements owner.

The skills do not run inside the semantic core, originate authority, or decide
correctness. The installed tool schemas and [MCP reference](mcp.md) own request
grammar; [Agent lifecycle](lifecycle.md) explains the product model.

| Canonical source | Responsibility |
| --- | --- |
| `skills/span-router/SKILL.md` | Moment → tool; the default-reflex table. Start here. |
| `skills/span-before-you-read/SKILL.md` | `ask`, exact surface selection, ambiguity, continuation, surface-first reuse, explicit evidence admission, and exact recorded-question lookup. |
| `skills/span-after-change/SKILL.md` | `reconsider` after editing, then re-establish actual loss. |
| `skills/span-record/SKILL.md` | Capture/update understanding, curate stable captured revisions, record verification, declare a service/domain boundary, and consume post-record qualification. |
| `skills/span-functional-pyramid/SKILL.md` | Adopt/initialize Functional Pyramid participation and apply governing orientation inside the ordinary lifecycle. |
| `docs/agents-snippet.md` | The managed lifecycle block copied into a target's `AGENTS.md`. |

Skills use exactly `ask`, `record`, and `reconsider`.

For governed repositories, the router resolves Functional Pyramid participation
before ordinary governed work: ACTIVE + VALID proceeds, ACTIVE + DEGRADED
requires governance repair, UNCONFIGURED routes to the Functional Pyramid
lifecycle when governed use is intended, and EXCLUDED is the explicit
descriptive-only path.

The working-agent path captures supported meaning through `record`. The
reviewer path discovers pending captures and uses the curation action inside the
same `record` tool; there is no fourth curation operation.

Functional Pyramid status, candidate validation, receipts, and participation
writes are likewise branches inside the same three tools.

Skills must not treat a gap as failure, invent a context identifier, collapse
missing authority into certainty, or hide failed admission, omissions, disputes,
pending review, or noncurrent support. `reconsider` is an after-edit
operation; "before editing" is `ask`.

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
