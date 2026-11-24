# Evidence, authority, and interpretation

A coding agent often needs to answer two different questions:

1. **What does the software appear to do?**
2. **What is the software supposed to do?**

Those questions can point to different sources and require different proof.

Source code, tests, configuration, and executions can support an explanation of
the implementation. Project goals, contracts, policies, and design documents can
govern what that implementation is supposed to satisfy.

Span keeps those roles separate even when both are relevant to the same task.

## Evidence supports an interpretation of the implementation

An investigator reads source, tests, configuration, runtime observations, or
other material and reaches a conclusion about the software.

Span can retain that conclusion together with the evidence used to establish it.
Later, Span can check whether the recorded evidence still matches the present
state.

That gives a future agent a maintained explanation rather than an unsupported
note.

But evidence does not make the interpretation infallible. An agent may still
have misunderstood the code, missed relevant evidence, or drawn a conclusion
that is too broad.

That is why semantic judgment remains with the investigator and reviewer.

## Governing authority answers a different question

A document is not authoritative merely because it looks important or contains
relevant words.

For Span to treat project guidance as governing, its ownership and applicability
must be declared by the project.

That means Span does not infer authority from:

- filenames such as `requirements.md` or `architecture.md`;
- directory position;
- search ranking or semantic similarity;
- document age or prominence; or
- a model's preferred interpretation.

Repository owners decide what the canonical governing sources are. Span
maintains the declared identities and relationships needed to apply them to
software work.

## Why the distinction matters

Implementation and governing guidance can drift independently.

For example:

- the code can change while the governing requirement stays the same;
- a requirement can change while the implementation stays byte-for-byte
  identical;
- a governing document can remain unchanged while its applicability changes;
  or
- the code and requirement can both remain unchanged while an earlier
  interpretation is shown to be wrong.

If evidence and authority were collapsed into one concept, those cases would be
easy to misrepresent.

Span therefore keeps them as different dependency classes and lets change on
either side trigger reassessment where appropriate.

## The Functional Pyramid makes governing applicability explicit

For participating repositories, Span uses the **Functional Pyramid** to connect
the software scope being worked on to its declared project guidance.

The path can run from project goals and principles through contracts, functional
design, and technical design to the relevant software scope.

The canonical rule text stays at its owning source. Span maintains the declared
relationships and applicability rather than copying that material into a second
authority store.

This also allows declared governance to cross repository boundaries without
assuming that repository layout defines the knowledge boundary.

## A normative conclusion still belongs to the investigator

Sometimes the engineering conclusion itself is normative, for example:

> this implementation conforms to the governing contract.

The investigator or reviewer still authors that judgment.

Span can ensure that the applicable governing route and required authority are
part of the conclusion's support. It does not make the conformance judgment on
the investigator's behalf.

That keeps a useful separation:

- repository owners provide governing authority;
- investigators and reviewers provide semantic/conformance judgment; and
- Span maintains the declared support, relationships, history, and change
  consequences around them.

## Current support is not semantic truth

A conclusion whose support is `CURRENT` has dependencies that still pass their
checks.

A conclusion whose exact revision is `CURATED` has been accepted by a reviewer
for shared reuse.

Neither label means that Span has mathematically proved the statement true.

Gaps can remain. Disputes can remain. A reviewer can later discover a semantic
error even when every recorded dependency still matches.

See [Support currency and reassessment](freshness.md) for how change affects
recorded support.

## Verification is separate again

A test run or external review records what was observed during that execution.

That evidence can support engineering judgment, but the run is not itself the
semantic explanation of the software and does not become project authority.

A recorded failing test remains a failing observation even when its supporting
source is still current. A passing test does not silently settle a disputed
interpretation.

Keeping verification, interpretation, and authority separate preserves what
each one actually proves.

## Go deeper

- [Agent lifecycle](lifecycle.md) explains how captured knowledge moves through
  review, reuse, and reassessment.
- [Interpretation and recording](interpretation.md) explains what makes a useful
  retained conclusion.
- [MCP reference](mcp.md) owns the exact evidence, authority, and Functional
  Pyramid request/result grammar.
