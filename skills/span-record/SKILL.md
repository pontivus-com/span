---
name: span-record
description: Record a supported conclusion, an independent verification run, or a service/domain surface after investigating. Use when an investigation produced a statement worth retaining, a test result worth citing, or a boundary the agent chose.
---

# Record what you established

Call `record` with one `kind`. A create is one conclusion; updates use actions.

## Understanding

Use `kind="understanding"` for a supported conclusion.

```json
{
  "repository_id": "repo-1",
  "request_id": "write-1",
  "kind": "understanding",
  "question": "How is the retention value determined?",
  "scope_paths": ["src/service.py"],
  "conclusion": "The service resolves retention from config through the loader.",
  "locator": "src/service.py"
}
```

A create is one conclusion. `locator` is the file it is about; the
`observation_id` from an `ask` gap may replace it. `surface` is optional and is
derived from the carried scope. A multi-file answer needs a declared
service/domain surface first.

Update an existing understanding with `understanding_id`, `expected_version`,
and one or more of `add`, `confirm`, `correct`, `replace`, `withdraw`. Multiple
actions apply atomically.

A create may supply the `context_id` from `ask` instead of the question and
scope; do not send both — the conflict is rejected. Without a context, a create
issues its own evidence-only context from the scope and cited locators.

## Verification

Use `kind="verification"` with a `run` carrying the command, scope, outcome,
observed time, and the evidence it actually tested. `run.observations` takes the
`obs:` ids that `ask` returned for the request context; to cite a source
instead, put its locator in `run.evidence` with the same `context_id`. The run
applies to the surfaces in its declared scope; record it against the surface it
verifies.

## Surface

Use `kind="surface"` with `action="create"` to declare a service or domain and
its boundary. Use `action="update"` with `expected_boundary_version` to change a
boundary. A declared surface must exist before understanding is recorded
against it. A parent must be an already declared service/domain in the same
repository; a stale boundary version is a rejection with the current version.

Span derives context, observation identity, submission identity, revisions, and
the create identity. You supply the request identity, compare-and-set version,
semantic content, and the evidence you hold. `action` is used only for a
surface declaration; an understanding create has no action.

Detail: [MCP reference](../../docs/mcp.md), [interpretation](../../docs/interpretation.md).
