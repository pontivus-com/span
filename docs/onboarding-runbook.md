# First investigation and fresh-session reuse

The first successful Span flow is:

1. install and verify Span;
2. resolve project-governance participation;
3. ask what is already known about a real engineering task;
4. investigate what is missing;
5. capture useful understanding;
6. review stable knowledge for shared reuse;
7. prove reuse in a fresh session; and
8. reconsider affected knowledge after change.

## 1. Install and verify Span

Follow [Install and connect](install.md), then verify the setup:

```bash
span-install --verify-only
```

Keep the reported repository ID. Ordinary installation verifies operational
readiness, not semantic understanding or governed participation.

## 2. Resolve project guidance before governed work

For governed work, supply the repository's Functional Pyramid classification
and request governed initialization as specified in [Install](install.md).
Span establishes and verifies participation automatically. The owner repairs
only genuine input defects; the agent handles any returned semantic obligations
through the existing lifecycle. No generated setup inputs or manual candidate/
activation sequence are required. The Beta-5 governed command is a target until
its installed acceptance passes.

- **ACTIVE + VALID** — proceed when outstanding semantic obligations are disposed.
- **ACTIVE + DEGRADED** — repair the reported governance/operational defect.
- **UNCONFIGURED** — request governed initialization if intended.
- **EXCLUDED** — descriptive lifecycle unless adoption is explicitly requested.

## 3. Pick a real engineering task

Choose the exact file, symbol, service, or domain you are about to understand or
change.

Ask Span about that surface before deriving the behavior yourself.

For an ACTIVE repository, the result can include both maintained software
understanding and the governing projection for the same scope.

Two outcomes are useful:

- **reusable knowledge exists** — start from it and verify that it is relevant
  to the task;
- **Span has a gap** — use the returned pointers and governing orientation as
  inputs to the investigation.

## 4. Investigate normally

Read the implementation and its consumers. Check tests, configuration, runtime
behavior, and canonical project guidance when they matter.

If source content selected through Span is needed, follow the evidence path
returned by `ask`. Exact evidence-admission and continuation mechanics are in
[Using Span](usage.md#start-a-task-with-what-is-already-known) and the
[MCP reference](mcp.md#ask).

The investigation establishes the understanding the task actually requires.

## 5. Keep what the work established

When the investigation establishes something that would help future work,
record it while the evidence and reasoning are still fresh.

A useful retained conclusion answers a real question about the selected software
surface and identifies the evidence that supports it. Keep unresolved questions
explicit.

This is **capture**. The knowledge is retained, but it is not automatically
shared with every future agent.

See [Using Span — Capture useful understanding](usage.md#capture-useful-understanding-while-it-is-fresh)
and [MCP reference — record](mcp.md#record).

## 6. Review the captured knowledge for reuse

Use a separate reviewer context — another agent session, a dedicated review
workflow, or a human reviewer — to inspect the captured conclusion.

Repair wrong, incomplete, duplicated, disputed, or badly scoped meaning through
the ordinary lifecycle. When the exact captured revision is suitable for shared
reuse, curate it through `record`.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

See [Using Span — Review captured knowledge](usage.md#review-captured-knowledge-before-broad-reuse).

## 7. Prove reuse in a fresh session

Start a new coding-agent session with no previous conversation and ask Span
about the same software surface.

The new session should be able to start from the reviewed knowledge without the
old transcript or a saved internal understanding ID. For ACTIVE repositories,
the same ask also resolves the current governing projection.

If the knowledge is not reusable, follow the returned state: it may still be
pending review, its support may no longer hold, or the requested surface may
still be unassessed.

## 8. See what happens after change

After changing source or relevant project guidance, call `reconsider` with the
changed paths.

Revisit the retained knowledge that actually requires reassessment. Unrelated
maintained knowledge remains reusable.

If the meaning still holds, re-establish it against current support. If the
meaning changed, record the corrected understanding and send the new revision
through review before shared reuse.

For a Functional Pyramid declaration or participation change, use the dependent
effects and re-establishment contexts returned by that governance write; do not
invent a second change-analysis path.

See [Using Span — After code or project guidance changes](usage.md#after-code-or-project-guidance-changes).

## Continue with normal work

Use [Using Span](usage.md) for the repeating engineering lifecycle,
[Evidence, authority, and interpretation](authority-trust.md) for the governance
model, and the [MCP reference](mcp.md) for exact request/result grammar.
