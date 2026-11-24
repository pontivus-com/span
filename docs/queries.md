# Questions, retrieval, and bounds

Span is designed to help an agent start from the **software surface it is
working on**, not from a saved internal ID or a remembered query.

That keeps retrieval aligned with the engineering task:

> **What do we currently know about this file, symbol, service, or domain?**

If reusable knowledge exists, Span returns it. If the surface has not been
assessed or its knowledge cannot currently be reused, Span keeps that limitation
explicit.

## Start from the software surface

For normal work, ask Span about the exact surface you are about to understand or
change.

A surface can be a file, symbol, service, or domain.

You can also use an unambiguous reference when Span can resolve it to one exact
surface. If the reference could mean several surfaces, Span returns the
candidates rather than guessing.

Surface-first retrieval is the normal reuse path because it does not require the
new session to know anything about the previous session's internal identities.

Exact request forms are in [MCP reference — ask](mcp.md#ask).

## Use an exact recorded question only when you already know it

Span can retrieve knowledge by an exact previously recorded question, but that
is a targeted lookup rather than semantic search.

It does not:

- paraphrase the question;
- similarity-rank alternative questions;
- embed the query and choose the nearest answer; or
- guess that two differently worded questions mean the same thing.

If you already know the exact recorded question, use that selector. Otherwise,
start from the software surface and inspect the maintained knowledge associated
with it.

This avoids presenting a semantically similar but wrong answer as if it were the
same question.

## A gap is useful information

A gap does not mean “Span knows nothing about this repository.”

It means the requested knowledge is not currently available for the selected
scope in the requested form.

Depending on the situation, the agent may need to:

- investigate the surface for the first time;
- revisit knowledge whose support changed;
- resolve unavailable evidence or project authority; or
- choose an exact surface when a reference was ambiguous.

The important point is that Span reports the limitation instead of filling it
with plausible text.

## Source retrieval is separate from semantic knowledge

Sometimes the maintained answer is not enough and the investigator needs exact
source content.

That is a different operation from asking what Span already knows.

Explicit evidence admission lets the agent request selected source material for
the investigation while keeping that evidence separate from the semantic answer.

When selected evidence does not fit in one response, Span can return a
continuation so the agent can retrieve the remaining selected content without
changing the original selection.

The exact evidence and continuation contract is in
[MCP reference — ask](mcp.md#ask).

## Historical detail is not current knowledge

Span preserves history for audit and recovery.

An investigator can retrieve an exact historical understanding revision or a
recording receipt when that detail is needed.

Historical retrieval does not make old content current again and is not merged
into the normal shared answer.

That distinction prevents “we once believed this” from silently becoming “this
is what the agent should use now.”

## Project guidance follows the same task scope

For a repository participating in the Functional Pyramid, ordinary task-time
retrieval can also include the project guidance that applies to the same
software scope.

Administrative queries can inspect participation, validate proposed governance
changes, and retrieve exact governance receipts.

Those are exact lifecycle operations, not semantic discovery. Span does not
infer governance from the text of the user's question.

See [Evidence, authority, and interpretation](authority-trust.md) for the
concept and the [MCP reference](mcp.md) for exact selectors.

## Bounded results stay honest

Large or incomplete results must not look complete merely because a response
ended.

Span therefore keeps bounds and omissions explicit.

If a result is truncated, it identifies that truncation. If a response cannot
carry the minimum information needed to represent the result honestly, Span
reports operational inability rather than returning a misleading fragment.

Likewise, an incomplete source inventory is not proof that something does not
exist outside the inspected boundary.

This is part of a broader rule: **bounded investigation must not become an
unbounded claim.**

## Continuations continue one selected investigation

A continuation is used to retrieve the next part of evidence already selected
for an investigation.

It is not a general repository cursor and it is not interchangeable with other
references.

Treat continuation tokens as opaque. Pass them back to Span as returned rather
than constructing or editing them.

Expired, invalid, or mismatched continuations remain explicit instead of being
silently redirected to different evidence.

## Verification retrieval does not rerun verification

Span can return retained verification records that apply to a software scope and
show whether their recorded support still holds.

Retrieval does not rerun the command or reinterpret the outcome.

A historical `PASS`, `FAIL`, or `INCONCLUSIVE` remains the outcome that
was actually observed.

See [Interpretation and recording](interpretation.md) for why verification and
semantic understanding are kept separate.

## The retrieval rule to remember

For ordinary work:

> **Start from the software surface. Use exact identities for exact history.
> Request source evidence explicitly when you need it. Treat bounds and gaps as
> information, not as permission to guess.**

For exact result types, selectors, continuations, and error behavior, use the
[MCP reference](mcp.md).
