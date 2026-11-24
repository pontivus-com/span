# Agent lifecycle

Span exists so useful understanding produced during software work can improve
future work without becoming stale, unreviewed memory.

The lifecycle is easiest to understand as one loop:

```text
start a task
  ↓
ask what is already known
  ↓
investigate what is missing
  ↓
capture useful understanding
  ↓
review stable knowledge for shared reuse
  ↓
future tasks start better informed
  ↓
code or project guidance changes
  ↓
reconsider affected knowledge
  ↺
```

This page explains that model. [Using Span](usage.md) explains what to do during
ordinary work, and the [MCP reference](mcp.md) owns exact operation grammar.

## Start from maintained knowledge

A task begins with the exact part of the system the agent is about to understand
or change: a file, symbol, service, or domain.

Span can return maintained knowledge already associated with that surface. If no
reusable knowledge exists, it returns an explicit gap rather than pretending the
system is understood.

The point is to make previous engineering work part of the next task's starting
context, not to replace investigation when new work is still required.

## Capture what the work establishes

The coding agent investigates with its normal tools and remains responsible for
the engineering judgment.

When that work establishes understanding that could help future tasks, the
conclusion can be captured with the evidence that supported it.

Capture happens close to the work because that is when the evidence, reasoning,
and scope are clearest. It prevents useful understanding from disappearing with
the session.

Captured knowledge is retained, but it is not automatically shared with every
future agent.

## Review before shared reuse

A task agent is optimizing for the task in front of it. That makes its
conclusions useful candidates for shared knowledge, not automatic shared truth.

A separate reviewer therefore decides whether a captured revision is suitable
for reuse. The reviewer may be another agent session, a dedicated workflow, or
a human.

If the meaning is wrong, incomplete, duplicated, disputed, or badly scoped, it
is repaired through the normal understanding lifecycle first. Once a stable
revision is accepted for reuse, later agents can receive it as maintained
working knowledge while its required support still holds.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

Review and support answer different questions:

- review asks whether this exact piece of understanding is suitable for shared
  reuse; and
- support asks whether the things that understanding depends on still hold.

Neither is a claim that Span has independently proved the interpretation true.

## Reuse in later work

A later session starts from the software surface, not from the previous
conversation or a saved internal identifier.

If reviewed knowledge is still usable, it becomes part of the new task's
starting context. If it is still awaiting review, has lost required support, or
does not exist for that surface, Span keeps that state explicit.

This is the compounding effect the lifecycle is designed to create:

> **work done now can improve the starting point for work done later.**

## Change creates reassessment work

Software knowledge cannot be treated as permanent memory because its
dependencies change.

A source edit may affect what an explanation means. A project requirement,
contract, or design decision may change even when the implementation does not.

After relevant change, Span identifies retained knowledge that may depend on
what changed. The agent revisits the affected conclusions rather than
re-investigating every piece of retained knowledge.

If the meaning still holds, it can be re-established against current support.
If the meaning changed, the corrected revision is captured and reviewed again
before shared reuse.

[Support currency and reassessment](freshness.md) explains this part of the
model in more detail.

## Project guidance travels with the same task

For repositories that participate in Span's governance model, the task context
can include not only what the software is understood to do, but also the project
guidance that applies to it.

Span calls this governing structure the **Functional Pyramid**. It connects the
software scope to explicitly declared goals, principles, contracts, functional
design, and technical design.

The knowledge lifecycle and the governing model remain distinct:

- captured software understanding comes from engineering investigation;
- governing meaning remains at the project's canonical authority sources; and
- a change to either side can make dependent knowledge require reassessment.

[Evidence, authority, and interpretation](authority-trust.md) explains why
those two kinds of knowledge need different proof.

Repository participation and governance administration are separate setup work.
They are documented in the [MCP reference](mcp.md) rather than in this
conceptual lifecycle.

## Gaps, disputes, and verification remain explicit

The lifecycle does not force uncertainty into a clean answer.

A gap means the required understanding has not been established. A dispute means
an interpretation is contested. A verification record says what an external
test or review actually observed.

Those facts can coexist with retained knowledge and are maintained separately.
A passing test does not automatically settle a semantic dispute, and a current
dependency check does not prove an explanation complete.

See [Interpretation and recording](interpretation.md) for the deeper model.

## The lifecycle in one sentence

For ordinary work:

> **Ask before deriving → investigate normally → capture what you establish →
> review for shared reuse → reconsider after change.**

The exact states, payloads, replay behavior, contexts, continuations, hooks, and
storage transitions are reference concerns. Follow the [MCP reference](mcp.md),
[Hooks](hooks.md), [Install and connect](install.md), and
[Backup and recovery](recovery.md) when you need those details.
