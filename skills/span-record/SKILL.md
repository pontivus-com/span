---
name: span-record
description: Record a supported conclusion, an independent verification run, or a service/domain surface after investigating. Use when an investigation produced a supported semantic conclusion, an independent test result, or a boundary the agent chose.
---

# Record what you established

Complete the applicable lifecycle before task completion; report named operational
blockers explicitly. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#required-agent-completion).


Call `record` with one `kind`. A create is one conclusion; updates use actions.
Semantic create/add/correct/replace records evidence-near CAPTURED meaning. That
is not shared publication: a separate reviewer/curator act must accept the exact
stable CURRENT revision before it becomes shared reusable knowledge.

A conformance judgment is a NORMATIVE conclusion. For an ACTIVE Functional
Pyramid repository Span derives its governing route/authority support. An
accepted NORMATIVE result is not task completion while its returned qualification
is non-current.

Functional Pyramid participation also uses this same `record` tool with
`kind="functional_pyramid"`; use the `span-functional-pyramid` skill for its
activate/revise/deactivate/exclude lifecycle rather than duplicating that
procedure here.

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

A create is one conclusion with dependency evidence from `locator`,
`observation_id`, or non-empty `support`. Support is the complete typed
dependency set you already hold. A locator may accompany support solely as
carried semantic scope and adds no dependency in that form; observation remains
exclusive. `surface` is optional and semantic scope is supplied or derived
independently from support.

Update an existing understanding with `understanding_id`, `expected_version`,
and one or more semantic actions: `add`, `confirm`, `correct`, `replace`,
`withdraw`. Compatible semantic actions apply atomically. Curation is a separate
review action and cannot share an update with semantic mutation. Actions are
compact deltas: `add` takes no identity;
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
mechanical basis. A semantic-preserving confirm of a CURATED predecessor may
inherit that curation; add/correct/replace produce CAPTURED meaning that requires
separate review. `reconsider` already returns the `expected_version` and
context, so the update follows without another `ask`.

To settle a challenge in the same update, add `challenge_dispositions`.
A resolved disposition supplies `challenge_id`, `expected_challenge_revision`,
`reasoning`, optional `target_conclusion_ids`, and optional context-bound
`evidence_refs`. Omit targets to resolve the challenge's own lineages. Never
send the resulting understanding/version/revision; Span derives those from the
same atomic update.

A create may supply the `context` reference returned by explicit evidence admission or `reconsider` instead of the question and
scope; do not send both — the conflict is rejected. Without a context, a create
issues its own evidence-only operational context from the scope and cited
locators. That internal context does not replace the create's explicit semantic
question/scope.

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

## Curate stable captures for shared reuse

Curation is reviewer judgment over an already retained exact revision; it is not
support evidence, Functional Pyramid authority, or certification of semantic
truth. First obtain the deterministic repository-local queue through `ask`:

```json
{
  "selector": {
    "$type": "PendingCurationSelector",
    "repository_id": "repo-1"
  }
}
```

Retrieve the exact owning understanding and inspect broader retained
knowledge/governance as needed. If review finds the meaning wrong, incomplete,
duplicated, or wrongly scoped, use challenge/correct/replace/withdraw first.
Curate only a stable revision whose required support is CURRENT:

```json
{
  "repository_id": "repo-1",
  "request_id": "curate-1",
  "kind": "understanding",
  "understanding_id": "u:rec-1",
  "expected_version": 2,
  "actions": {
    "curate": [
      {
        "conclusion_id": "<id returned by Span>",
        "reasoning": "Reviewed for shared reuse."
      }
    ]
  },
  "provenance": "reviewer-session"
}
```

Curation advances understanding history without changing semantic content or
support. Later support loss still withholds the revision from Answer content and
does not erase the curation disposition.

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
