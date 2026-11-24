# First investigation and fresh-session reuse

This guide is for your first real Span workflow.

By the end, you should have seen the complete value loop once:

1. start a coding task with whatever Span already knows;
2. investigate normally when knowledge is missing;
3. retain useful understanding produced by the work;
4. review that knowledge before sharing it broadly;
5. start a fresh session and reuse it; and
6. see how Span responds when the things that knowledge depends on change.

You do not need to learn Span's internal data model or exact MCP payload grammar
to follow this guide. [Using Span](usage.md) explains the day-to-day workflow;
the [MCP reference](mcp.md) owns exact request and result shapes.

## 1. Install and verify Span

Follow [Install and connect](install.md) for your coding agent and repository.

After installation, verify the setup:

```bash
span-install --verify-only
```

Keep the reported repository ID. Span uses that stable identity in its lifecycle
operations.

A successful installation means Span is ready to work with the repository. It
does **not** mean the repository has already been understood.

## 2. Pick a real engineering task

Use a task you were already going to do.

Choose the exact part of the system you are about to understand or change: a
file, symbol, service, or domain. Starting from the real task is important
because Span is intended to turn ordinary engineering work into maintained
knowledge, not create a separate documentation exercise.

Before deriving the behavior yourself, ask Span about that surface.

Two outcomes are useful:

- **Span already has reusable knowledge.** Start from it and verify that it is
  relevant to the task.
- **Span has a gap.** Use the returned pointers as a starting point and
  investigate with your normal source, search, test, and debugging tools.

Either outcome tells you where the task actually starts.

## 3. Investigate normally

Do the engineering work as you normally would.

Read the implementation and its consumers. Check tests, configuration, runtime
behavior, and project guidance when they matter. Span does not replace those
tools or make the engineering judgment for you.

If you need source content selected through Span itself, follow the evidence
path returned by `ask`. Exact evidence-admission and continuation mechanics
are documented in [Using Span](usage.md#ask-a-surface) and the
[MCP reference](mcp.md#ask).

The goal of this step is not to produce notes for Span. It is to establish the
understanding the task actually requires.

## 4. Keep what the work established

When the investigation establishes something that would help a future agent,
record it while the evidence and reasoning are still fresh.

A useful retained conclusion should answer a real question about the selected
software surface and identify the evidence that supports it. Record unresolved
questions as unresolved rather than turning them into certainty.

This is **capture**: the knowledge is retained so it does not disappear with the
session.

Capture does not automatically make the conclusion shared knowledge for every
future agent. That separation is deliberate.

See [Using Span — Investigate and record](usage.md#investigate-and-record) for
the operating procedure and [MCP reference — record](mcp.md#record) for exact
grammar.

## 5. Review the captured knowledge for reuse

Use a separate reviewer context — another agent session, a dedicated review
workflow, or a human reviewer — to inspect the captured conclusion.

The reviewer should ask whether the retained statement is a useful, stable
piece of shared knowledge for future work. If it is wrong, incomplete,
duplicated, or badly scoped, repair the meaning through the normal lifecycle
before accepting it for reuse.

When the exact captured revision is suitable for shared reuse, curate it through
the existing `record` lifecycle.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

See [Using Span — Curate captured knowledge](usage.md#curate-captured-knowledge)
for the review workflow.

## 6. Prove reuse in a fresh session

Start a new coding-agent session with no previous conversation.

Ask Span about the same software surface again.

The important test is simple: the new session should be able to start from the
reviewed knowledge without the old transcript or a saved internal understanding
ID.

If the knowledge is not returned for reuse, treat the returned status as
information rather than working around it. It may still be pending review, its
support may no longer hold, or the requested surface may not have reusable
knowledge yet.

At this point you have demonstrated the first half of the knowledge-factory
loop: **work in one session improved the starting point for another.**

## 7. See what happens after change

When you later change source or relevant project guidance, call
`reconsider` with the changed paths.

Span identifies retained knowledge that may depend on what changed. Revisit the
reported knowledge that actually requires reassessment; unrelated maintained
knowledge remains reusable.

If the meaning is still correct, re-establish it against current support. If
the meaning changed, record the corrected understanding and send the new
revision through review before it becomes shared knowledge again.

This is the second half of the loop: **maintained knowledge stays accountable to
the software and guidance it depends on.**

See [Using Span — After a change](usage.md#after-a-change) for the operating
procedure.

## If your repository uses project governance

Span can also provide the project guidance that applies to the software surface
being worked on.

Repositories do not have to participate in that governance model to use the
ordinary descriptive knowledge lifecycle above. When a repository does
participate, the same task-time workflow can include the applicable path through
its declared goals, principles, contracts, functional design, and technical
design.

If you are responsible for configuring that participation, follow
[Using Span — Check Functional Pyramid participation](usage.md#check-functional-pyramid-participation)
and the exact reference material linked from there. It is setup/governance work,
not a prerequisite for learning the basic Span workflow.

## What to do next

Once this first loop makes sense:

- keep [Using Span](usage.md) as the normal workflow guide;
- use the [MCP reference](mcp.md) only when you need exact grammar or result
  semantics;
- read the [concept documentation](README.md#concepts) when you want to
  understand why Span behaves this way; and
- use [Backup and recovery](recovery.md) when you need to move or protect
  retained Span state.
