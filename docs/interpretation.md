# Interpretation and recording

Span can maintain software knowledge, but it does not decide what the software
means.

The investigator — an agent or human — still does the engineering work, reads
the evidence, and authors the conclusion. Span's job is to retain that
conclusion with its scope and support so future work can reuse it responsibly.

## A useful retained conclusion starts with a real engineering question

Good retained knowledge should answer something that future work may otherwise
have to rediscover.

For example:

- Why does this request take this path?
- What responsibility does this service own?
- Which behavior does this configuration control?
- Does this implementation satisfy the governing contract?

The conclusion should be scoped to what was actually established, not to what
the investigator hopes is true about the rest of the system.

A conclusion can depend on several files, tests, configuration values, runtime
observations, or governing sources. Those dependencies are support; they are not
automatically the semantic scope of the conclusion.

## Evidence should support the statement you actually make

Retain the evidence that materially supports the conclusion.

That may include implementation source, tests, configuration, observations,
other retained conclusions, or declared project authority.

The goal is not to attach every file the agent happened to read. It is to make
the claimed meaning accountable to the things that established it.

If an important question remains unresolved, keep it as a gap rather than
turning uncertainty into a clean explanation.

Span validates and maintains the declared support, but it does not certify that
the investigator selected every relevant dependency or interpreted the evidence
correctly.

## Descriptive and normative conclusions are different

A **descriptive** conclusion explains what the implementation is understood to
do.

A **normative** conclusion makes a claim about what the implementation should do
or whether it conforms to governing project guidance.

For repositories using the Functional Pyramid, Span can derive the applicable
governing route and required authority support for a normative conclusion from
the conclusion's software scope.

That prevents an investigator from making a governance-dependent claim appear
current simply by omitting the relevant authority.

The investigator still authors the judgment. Span does not automatically turn a
descriptive observation into a normative one merely because project guidance is
available.

See [Evidence, authority, and interpretation](authority-trust.md).

## Capture is the first step, not publication

When an investigation establishes useful understanding, capture it while the
evidence and reasoning are fresh.

A newly created or semantically changed conclusion is retained as captured
knowledge. It still needs separate review before it becomes shared reusable
knowledge for later agents.

This separation lets ordinary task work contribute to the knowledge factory
without making every task-local conclusion immediately global.

See [Agent lifecycle](lifecycle.md).

## Correct knowledge explicitly

Software understanding evolves. Span preserves that history rather than silently
rewriting it.

Conceptually, an existing conclusion can be:

- **confirmed** when reassessment shows the same meaning still holds;
- **corrected** when the same underlying subject was stated incorrectly;
- **replaced** when a different explanation supersedes the old one;
- **withdrawn** when the old conclusion no longer applies; or
- accompanied by additional conclusions when the understanding needs to grow.

These are explicit changes to maintained knowledge. Earlier revisions remain
available for audit rather than disappearing.

The [MCP reference](mcp.md#record) owns the exact update actions, identities, and
compare-and-set grammar.

## Disagreements stay explicit

A source file can remain unchanged while an interpretation becomes disputed.

That is why a semantic challenge is not the same thing as stale support.

If a reviewer or investigator believes a retained explanation is wrong,
incomplete, or unsupported, preserve that disagreement explicitly and resolve it
through the knowledge lifecycle.

A later code version, matching source bytes, or a passing test does not silently
settle the dispute. Resolution requires an explicit semantic disposition.

This preserves the difference between **the evidence still exists** and **we
agree on what it means**.

## Verification records what happened, not what it means

Tests, reviews, and other external executions can be retained independently from
semantic conclusions.

A useful verification record says what was run, what scope/evidence was tested,
what outcome was observed, and any material limitations.

That record can support later engineering judgment, but Span does not convert
the test result into a semantic explanation automatically.

A passing run is evidence of a pass under the recorded conditions. A failing run
is evidence of a failure. Neither one is project authority.

## Recording is designed to survive ordinary failure

Writes use stable request identity so an accepted recording can be safely
retried after a lost response.

That operational contract matters because knowledge capture should not become
fragile bookkeeping. The investigator should be able to preserve the conclusion
without guessing whether a previous attempt committed.

Exact replay, receipt, context, and error semantics belong to the
[MCP reference](mcp.md#replay-identity-and-retention).

## The principle to remember

Span keeps the durable result of engineering judgment; it does not replace that
judgment.

A good retained conclusion is:

- about a clear software scope;
- supported by the evidence that established it;
- explicit about unresolved questions;
- descriptive or normative as appropriate;
- corrected or withdrawn explicitly when meaning changes; and
- reviewed separately before broad reuse.

That is what turns a task-time interpretation into maintained software
knowledge.
