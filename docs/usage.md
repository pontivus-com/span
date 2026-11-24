# Using Span

Use Span as part of the engineering work you were already going to do.

The day-to-day loop is:

1. **ask before you derive understanding**;
2. **investigate with your normal tools**;
3. **capture useful conclusions while the evidence is fresh**;
4. **review stable captures before sharing them broadly**; and
5. **reconsider maintained knowledge after relevant change**.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

This guide explains that workflow. The [MCP reference](mcp.md) owns exact
request/result grammar, selectors, fields, and error shapes.

## Start a task with what is already known

Choose the exact file, symbol, service, or domain you are about to understand or
change.

Before deriving its behavior from source, ask Span about that surface.

If reusable knowledge already exists, Span gives the agent a maintained starting
point. If it does not, Span returns an explicit gap rather than inventing an
answer. Either result tells you where the task actually starts.

For repositories that participate in Span's project-governance model, the same
task-time result can also include the project guidance that applies to the
selected software surface.

You do not need a previous conversation or saved internal understanding ID to
start from the surface again in a later session.

Exact `ask` forms, evidence admission, selectors, and continuations are in
[MCP reference — ask](mcp.md#ask).

## Investigate with the tools you already use

Span does not replace source search, code reading, debugging, tests, or
engineering judgment.

When the current task needs new understanding, investigate normally:

- read the implementation and its consumers;
- inspect relevant tests and configuration;
- run the checks needed for the task; and
- read governing project sources when they matter.

The purpose of Span is not to create a second documentation task around that
work. It is to keep useful understanding that the work establishes.

When you need source content selected through Span itself, follow the evidence
path returned by `ask`. Exact evidence-admission mechanics belong to the
[MCP reference](mcp.md#ask).

## Capture useful understanding while it is fresh

When the investigation establishes something that would help future work, record
it before the task context disappears.

A useful captured conclusion should:

- answer a real question about the software surface;
- distinguish observed behavior from governing intent when that distinction
  matters;
- identify the evidence that supports the conclusion; and
- keep unresolved questions explicit instead of turning them into certainty.

Capture retains the knowledge. It does not automatically publish the conclusion
as shared knowledge for every future agent.

Exact `record` grammar, update actions, evidence forms, replay identity, and
receipts are in [MCP reference — record](mcp.md#record).

## Review captured knowledge before broad reuse

A working agent is optimizing for the task in front of it. A useful task-local
conclusion is not automatically the right durable knowledge for every future
agent.

Review is therefore a separate step.

A reviewer — another agent session, a dedicated workflow, or a human — inspects
captured knowledge and asks whether the statement is accurate enough, stable
enough, and scoped appropriately for shared reuse.

If the meaning is wrong, incomplete, duplicated, disputed, or badly scoped,
repair it through the normal understanding lifecycle first. When the exact
revision is suitable for reuse, curate that revision through `record`.

Curation means the revision has been accepted for shared reuse. It does not make
the statement authoritative, and it does not replace the evidence the statement
depends on.

Exact pending-review selection and curation actions are in the
[MCP reference](mcp.md).

## Reuse knowledge in another session

A later agent can ask about the same software surface and start from maintained
knowledge without the original conversation.

That is the main reuse test:

> **Did work in an earlier session improve the starting point for this one?**

Span only serves shared knowledge while the revision remains eligible for reuse.
If a conclusion is still pending review, its support no longer holds, or the
requested surface has no reusable knowledge, the result stays explicit instead
of being silently promoted into an answer.

Use exact historical snapshots or receipts only when you need audit detail.
Ordinary work should start from the software surface.

## After code or project guidance changes

Use your normal tools to edit and test.

Then call `reconsider` with the changed paths.

Span identifies retained knowledge that may depend on what changed. The result
separates knowledge that actually needs reassessment from knowledge that remains
usable.

For each affected conclusion:

- if the meaning still holds, re-establish it against current support;
- if the meaning changed, record the corrected understanding;
- if the old conclusion no longer applies, replace or withdraw it; and
- if the conclusion is disputed, keep the disagreement explicit until it is
  resolved.

A semantic change produces new captured knowledge, which must be reviewed again
before it becomes shared knowledge.

Exact `reconsider` results and update grammar are in
[MCP reference — reconsider](mcp.md#reconsider).

## Project guidance and the Functional Pyramid

Span can maintain two useful parts of the task context:

- what the implementation is understood to do; and
- what project guidance is supposed to govern it.

The **Functional Pyramid** is Span's mechanism for the second part. When a
repository participates, ordinary task-time use can include the applicable path
through declared goals, principles, contracts, functional design, and technical
design.

You do not need Functional Pyramid participation to use the ordinary descriptive
capture/review/reuse lifecycle.

If you are responsible for governance setup or revision, use the exact
Functional Pyramid selectors and lifecycle actions documented in the
[MCP reference](mcp.md) and the [concept documentation](README.md#concepts).
That administrative workflow is deliberately separate from ordinary first-use
guidance.

## Verification, disputes, and recovery

Some tasks need more than a retained explanation.

- **Verification:** when an external test or review produced evidence you want
  to retain, record that verification independently from the semantic
  conclusion it tested.
- **Disputes:** if a retained explanation is challenged even though its sources
  have not changed, keep the challenge explicit and settle it through the
  normal lifecycle rather than treating a passing test or new version as an
  implicit resolution.
- **Lost responses or retries:** preserve the original request identity and
  follow the MCP replay rules rather than guessing whether a write happened.
- **Backup and restore:** use [Backup and recovery](recovery.md) for durable
  operational state.

The [MCP reference](mcp.md) contains the exact recovery, replay, continuation,
and verification contracts.

## The operating rule to remember

You do not need to memorize Span's internal model.

For ordinary engineering work, remember the lifecycle:

> **Ask before deriving → investigate normally → capture what you establish →
> review for shared reuse → reconsider after change.**

That is how ordinary coding work becomes maintained knowledge for the next
agent.
