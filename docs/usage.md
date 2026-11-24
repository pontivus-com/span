# Using Span

Span has two related lifecycles.

For **governed use**, Functional Pyramid initialization/adoption comes first;
the ordinary engineering lifecycle then consumes that governing orientation.
The governance lifecycle is revisited when project governance changes.

For **descriptive-only use**, the ordinary semantic lifecycle remains available
without an ACTIVE Functional Pyramid. EXCLUDED records an explicit
non-participation decision; UNCONFIGURED remains descriptive-capable but is not
a completed governance setup.

## Before governed work: resolve Functional Pyramid participation

Check the repository's Functional Pyramid status.

- **ACTIVE + VALID** — ordinary governed work can proceed.
- **ACTIVE + DEGRADED** — repair the governing declarations/availability before
  treating governance as complete.
- **UNCONFIGURED** — initialize/adopt the Functional Pyramid when governed use
  is intended.
- **EXCLUDED** — use the descriptive Span lifecycle without a governing
  projection unless adoption is later intended.

A registered repository is not automatically governed. Initialization/adoption
establishes which canonical goals, principles, contracts, functional design, and
technical design apply to which software scope. Span records their declared
relationships and applicability; it does not copy their normative meaning into a
second authority store.

For first-time setup, follow [First investigation](onboarding-runbook.md).
The exact Functional Pyramid selectors and lifecycle actions are in the
[MCP reference](mcp.md).

## The ordinary engineering loop

Normal semantic work follows:

1. **ask before you derive understanding**;
2. **investigate with your normal tools**;
3. **capture useful conclusions while the evidence is fresh**;
4. **review stable captures before sharing them broadly**; and
5. **reconsider maintained knowledge after relevant change**.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

## Start a task with what is already known

Choose the exact file, symbol, service, or domain you are about to understand or
change.

Before deriving its behavior from source, ask Span about that surface.

If reusable knowledge already exists, Span gives the agent a maintained starting
point. If it does not, Span returns an explicit gap rather than inventing an
answer.

For ACTIVE repositories, the same task-time result includes the applicable
governing projection for that software scope. Inspect that projection before
making a normative or conformance judgment.

Exact `ask` forms, evidence admission, selectors, and continuations are in
[MCP reference — ask](mcp.md#ask).

## Investigate with the tools you already use

Read the implementation and its consumers, inspect relevant tests and
configuration, run the checks needed for the task, and follow canonical
governing sources when their substantive meaning is required.

Span does not replace source search, code reading, debugging, tests, or
engineering judgment. It retains useful understanding established by that work.

When source content selected through Span is needed, follow the evidence path
returned by `ask`. Exact evidence-admission mechanics are in the
[MCP reference](mcp.md#ask).

## Capture useful understanding while it is fresh

When the investigation establishes something that would help future work, record
it before the task context disappears.

A useful captured conclusion should:

- answer a real question about the software surface;
- distinguish observed behavior from governing intent when that distinction
  matters;
- identify the evidence that supports the conclusion; and
- keep unresolved questions explicit.

For ACTIVE repositories, a conformance judgment is normative; Span derives the
applicable Functional Pyramid route and authority support for the selected
semantic scope.

Capture retains the knowledge. It does not automatically publish the conclusion
as shared knowledge for every future agent.

Exact `record` grammar, update actions, evidence forms, replay identity, and
receipts are in [MCP reference — record](mcp.md#record).

## Review captured knowledge before broad reuse

A working agent is optimizing for the task in front of it. A useful task-local
conclusion is therefore a candidate for shared knowledge, not automatic shared
truth.

A reviewer — another agent session, a dedicated workflow, or a human — inspects
captured knowledge and repairs wrong, incomplete, duplicated, disputed, or badly
scoped meaning through the ordinary lifecycle.

When the exact revision is suitable for reuse, curate it through `record`.

Curation accepts the exact revision for shared reuse. It does not create project
authority or replace the evidence/governing support the statement depends on.

Exact pending-review selection and curation actions are in the
[MCP reference](mcp.md).

## Reuse knowledge in another session

A later agent can ask about the same software surface and start from maintained
knowledge without the original conversation.

For ACTIVE repositories, governing applicability is resolved again on that ask,
so reused semantic knowledge and current project guidance remain independently
checkable.

Span serves shared knowledge only while the revision remains eligible for reuse.
Pending review, lost support, and unassessed scope remain explicit.

## After code or project guidance changes

Use your normal tools to edit and test, then call `reconsider` with the changed
paths for each directly edited repository.

Span identifies retained knowledge that may depend on the change. For each
affected conclusion:

- if the meaning still holds, re-establish it against current support;
- if the meaning changed, record the corrected understanding;
- if the old conclusion no longer applies, replace or withdraw it; and
- if the conclusion is disputed, keep the disagreement explicit until resolved.

A semantic change produces a new CAPTURED revision that must be reviewed again
before shared reuse.

Functional Pyramid participation writes already return their own dependent
effects and re-establishment contexts. Dispose those effects directly rather
than calling `reconsider` again for the participation write itself.

Exact `reconsider` results and update grammar are in
[MCP reference — reconsider](mcp.md#reconsider).

## Verification, disputes, and recovery

- **Verification:** retain an external test or review independently from the
  semantic conclusion it tested.
- **Disputes:** keep a challenge explicit and settle it through the semantic
  lifecycle rather than treating a passing test or new version as an implicit
  resolution.
- **Lost responses or retries:** preserve the original request identity and
  follow the MCP replay rules.
- **Backup and restore:** use [Backup and recovery](recovery.md).

The [MCP reference](mcp.md) contains the exact recovery, replay, continuation,
and verification contracts.

## The operating rule

For governed work, complete the required governance initialization first. The
repeating semantic lifecycle is:

> **Ask before deriving → investigate normally → capture what you establish →
> review for shared reuse → reconsider after change.**

That is how ordinary coding work becomes maintained knowledge for the next
agent.
