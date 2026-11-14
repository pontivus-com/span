---
name: span-record
description: Record a supported conclusion, an independent verification run, or a service/domain surface after investigating. Use when an investigation produced a supported semantic conclusion, an independent test result, or a boundary the agent chose.
---

# Record what you established

Complete the applicable lifecycle before task completion; report named operational
blockers explicitly. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#required-agent-completion).


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

A create is one conclusion with exactly one evidence mode. `locator` cites
source evidence; `observation_id` may replace it when you hold an admitted
observation; non-empty `support` is the complete typed dependency set you
already hold. These evidence modes are mutually exclusive. `surface` is
optional and semantic scope is supplied or derived independently from support.

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
  "request_id": "rec-confirm",
  "context": {
    "repository_id": "repo-1",
    "context_id": {"value": "ctx-from-reconsider"}
  },
  "kind": "understanding",
  "understanding_id": "u:rec-1",
  "expected_version": 2,
  "actions": {"confirm": [{"conclusion_id": "<id returned by Span>", "locator": "src/a.py"}]}
}
```

```json
{
  "request_id": "rec-correct",
  "context": {
    "repository_id": "repo-1",
    "context_id": {"value": "ctx-from-reconsider"}
  },
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

A create may supply the `context` reference returned by explicit evidence admission or `reconsider` instead of the question and
scope; do not send both — the conflict is rejected. Without a context, a create
issues its own evidence-only context from the scope and cited locators.

Semantic scope describes what the conclusion is about; support identifies what
established it. Multiple support files do not create multiple owning surfaces.
Declare SERVICE/DOMAIN only when the conclusion describes that declared boundary.
Its semantic scope must fit that boundary. Support locators do not create
independent retained conclusions; author per-file conclusions when needed.

A supplied context has fixed scope. New source or discovery evidence can be
admitted during record inside that scope; it need not already be admitted.
Empty evidence scope means repository-wide. Discovery must fit completely:
a broader ancestor or repository-wide discovery cannot fit a restricted context.

When investigation expands, omit `context` and supply explicit semantic/run
scope and direct evidence. Span derives a new operational context. Repository-wide
discovery makes that context repository-wide while the semantic scope stays
narrow. Admitted evidence references and observation IDs remain context-bound; supply that context or use direct evidence.

```json
{
  "repository_id": "repo-1",
  "request_id": "plan-status-1",
  "kind": "understanding",
  "question": "Is this plan implemented?",
  "scope_paths": ["docs/implementation-plan.md"],
  "conclusion": "The implementation described by the plan is complete.",
  "support": [
    {"$type": "source", "locator": "src/a.py", "ranges": []},
    {"$type": "source", "locator": "tests/a.py", "ranges": []}
  ]
}
```

## Verification

Use `kind="verification"` with a `run` carrying the command, scope, outcome,
observed time, and the evidence it actually tested. A run requires at least one observation or evidence item; both may coexist.
Use context + run.observations only for observations admitted to that context.
Use context + run.evidence for new direct evidence inside its fixed scope.
For evidence beyond it, omit context and supply run.scope_paths/run.evidence.
Do not substitute scenario text for structural evidence.

```json
{
  "repository_id": "repo-1",
  "request_id": "verify-ui-1",
  "kind": "verification",
  "run": {
    "repository_id": "repo-1",
    "scope_description": "UI form suite",
    "scope_paths": ["ui/"],
    "evidence": [{"locator": "ui/tests/form.test.ts", "ranges": []}],
    "command": "pnpm exec vitest run tests/form.test.ts --pool=forks --maxWorkers=1 --no-file-parallelism",
    "scenario": "UI form suite",
    "outcome": "PASS",
    "observed_at": "2026-11-07T00:00:00Z",
    "observer": "agent"
  }
}
```

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

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md), [interpretation](https://github.com/pontivus-com/span/blob/master/docs/interpretation.md).
