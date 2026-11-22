# Repository overview

Span is a local MCP server that gives a coding agent the complete working
context for the exact part of the software it is working on. It combines
retained understanding of the implementation with the applicable chain of
project guidance from goals and principles through contracts, functional
design, and technical design. The agent still owns interpretation, edits, and
test execution; Span keeps the supporting evidence, canonical guidance links,
history, and change effects explicit.

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
MCP request → strict ingress → installation/repository composition
            → lifecycle service → typed ports and pure rules
            → repository-qualified support / Functional Pyramid orientation
            → atomic store operation when requested → canonical result → MCP
```

For Version 1, the installation runtime owns registered-repository resolution,
the installation-scoped Functional Pyramid state and the single shared
cross-repository effect capability. Repository `ServiceContext` instances are
composed from that installation runtime; shell transport never becomes a second
semantic owner. ACTIVE governance therefore cannot disagree between a status
selector and an ordinary repository operation.

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
