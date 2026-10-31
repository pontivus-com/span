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
skills/             optional agent-side lifecycle guidance
integrations/       host-side adapters and reference integrations
scripts/            packaging, asset synchronization, quality checks
```

## Follow a request

```text
MCP request → strict ingress → lifecycle service → typed ports and pure rules
            → atomic store operation when requested → canonical result → MCP
```

`understand_question` discovers qualified candidates or returns an investigation
gap with evidence. `evidence_start` and `evidence_extend` admit exact sources.
`record_*` operations accept supported understanding, explicit disputes, or
independent verification. `understand_retrieve`, `reassess`, and
`verification_support` read saved state with its current qualifications.
`locate` and `neighbors` provide structural navigation.

A question is not a suspended task. An agent can record an investigation that
began outside Span. The store holds recoverable contexts and immutable
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
