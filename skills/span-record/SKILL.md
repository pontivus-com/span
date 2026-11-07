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

A create is one conclusion with exactly one evidence mode. `locator` is the
file it is about; the `observation_id` from an `ask` gap may replace it; non-empty
`support` is the complete typed dependency set you already hold. A locator may
accompany support as the carried scope, but an observation id may not. `surface`
is optional and derived from the carried scope. A multi-file answer needs an
explicit `scope_paths` or a declared service/domain surface first.

Update an existing understanding with `understanding_id`, `expected_version`,
and one or more of `add`, `confirm`, `correct`, `replace`, `withdraw`. Multiple
actions apply atomically. Actions are compact deltas: `add` takes no identity;
`confirm`, `correct`, `replace`, and `withdraw` name the existing
`conclusion_id` returned by Span. Each action that supplies evidence names
exactly one of `locator`, `observation_id`, or non-empty `support`; `withdraw`
may supply one or none:

```json
{
  "repository_id": "repo-1",
  "request_id": "rec-add",
  "kind": "understanding",
  "understanding_id": "u:rec-1",
  "expected_version": 1,
  "actions": {"add": [{"conclusion": "B performs Y.", "locator": "src/b.py"}]}
}
```

```json
{
  "repository_id": "repo-1",
  "request_id": "rec-confirm",
  "context_id": "ctx-from-reconsider",
  "kind": "understanding",
  "understanding_id": "u:rec-1",
  "expected_version": 2,
  "actions": {"confirm": [{"conclusion_id": "<id returned by Span>", "locator": "src/a.py"}]}
}
```

```json
{
  "repository_id": "repo-1",
  "request_id": "rec-correct",
  "context_id": "ctx-from-reconsider",
  "kind": "understanding",
  "understanding_id": "u:rec-1",
  "expected_version": 2,
  "actions": {"correct": [{"conclusion_id": "<id returned by Span>", "conclusion": "A now performs Z.", "locator": "src/a.py"}]}
}
```

```json
{
  "repository_id": "repo-1",
  "request_id": "rec-replace",
  "kind": "understanding",
  "understanding_id": "u:rec-1",
  "expected_version": 2,
  "actions": {"replace": [{"conclusion_id": "<id returned by Span>", "conclusion": "The replacement behaviour is Z.", "reason": "The prior implementation was superseded.", "locator": "src/a.py"}]}
}
```

```json
{
  "repository_id": "repo-1",
  "request_id": "rec-withdraw",
  "kind": "understanding",
  "understanding_id": "u:rec-1",
  "expected_version": 2,
  "actions": {"withdraw": [{"conclusion_id": "<id returned by Span>", "reason": "The implementation no longer has this behaviour."}]}
}
```

`confirm` preserves the current statement, assertion nature, and scope;
`correct` and `replace` preserve an omitted nature or scope; Span derives the
new lineage identity on `add` and `replace`, the old revision, and the
mechanical basis. `reconsider` already returns the `expected_version` and
context, so the update follows without another `ask`.

A create may supply the `context_id` from `ask` instead of the question and
scope; do not send both — the conflict is rejected. Without a context, a create
issues its own evidence-only context from the scope and cited locators.

## Verification

Use `kind="verification"` with a `run` carrying the command, scope, outcome,
observed time, and the evidence it actually tested. A run requires
`observations` or `evidence`; either is accepted. `run.observations` takes the
`obs:` ids that `ask` returned for the request context; to cite a source
instead, put its locator in `run.evidence` with the same `context_id`. The run
applies to the surfaces within its declared scope; a single-file run is not
widened to a broader service. Record it against the surface it verifies.

## Surface

Use `kind="surface"` with `action="create"` to declare a service or domain and
its boundary. Use `action="update"` with `expected_boundary_version` to change a
boundary. A declared surface must exist before understanding is recorded
against it. A parent must be an already declared service/domain in the same
repository; a stale boundary version is a rejection with the current version.

Span derives context, observation identity, submission identity, revisions, and
the new conclusion lineage identity. You supply the request identity,
compare-and-set version, semantic content, and the evidence you hold. `action` is used only for a
surface declaration; an understanding create has no action.

Detail: [MCP reference](../../docs/mcp.md), [interpretation](../../docs/interpretation.md).
