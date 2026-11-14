# Repository overview

Span is a local MCP server for keeping useful codebase investigations reusable.
The agent investigates and records conclusions; Span stores exact support,
preserves revisions and disputes, and qualifies reuse against present evidence.
The agent owns the model and all repository edits and test execution.

## Layout

```text
src/span/core/      canonical carriers, strict schema, pure transition/support rules
src/span/ports/     typed evidence, structural, store, and authority interfaces
src/span/service/   investigation, admission, discovery, recording, qualification
src/span/shell/     filesystem, git, SQLite, provider, installation, MCP transport
tests/              carrier, service, persistence, transport, installed-process tests
docs/               public contracts and guides
skills/             agent-side required lifecycle guidance
integrations/       host-side adapters and reference integrations
scripts/            packaging, asset synchronization, quality checks
```

## Follow a request

```text
MCP request → strict ingress → lifecycle service → typed ports and pure rules
            → atomic store operation when requested → canonical result → MCP
```

`ask` is surface-first. Pure surface/reference obtain returns the current
document view grouped by recorded question, with status and applicable
verification; a genuinely unassessed surface returns a Gap with source pointers,
not unsolicited source bodies. The surface status names stale conclusions as
`stale_refs`; historical content and stale references are never current-answer
content. Exact targeted reuse uses `RecordedQuestionSelector` and exact
surface-scoped equality; unmatched selection is `Gap/unassessed`. Source bytes
are delivered only by explicit evidence admission.
`record` accepts supported understanding, a declared service/domain boundary, or
an independent verification run. `reconsider` maps a changed scope to every
surface that must be re-examined, with per-conclusion support state. Exact
snapshots and receipts are retrieved through `ask`'s selector form; they are
historical and never current-answer content. The host supplies structural navigation.

Agents follow [the required lifecycle](lifecycle-contract.md#required-agent-completion).
Direct-create ingress accepts pre-existing understanding. The store holds recoverable contexts and immutable
receipts; no process-local interpretation continuation is needed.

## Where changes belong

| Change | Owner |
| --- | --- |
| Transition, identity, validation, support decisions | `src/span/core/` |
| Typed capability boundary | `src/span/ports/` |
| Sequencing and evidence/state composition | `src/span/service/` |
| Filesystem, database, provider, transport effects | `src/span/shell/` |
| Agent procedure and product explanation | `docs/`, `skills/`, and canonical snippet |

Read [architecture](architecture.md), [lifecycle](lifecycle.md), and
[MCP reference](mcp.md), then the [glossary](glossary.md). Development commands
and verification requirements are in [contributing](contributing.md).
