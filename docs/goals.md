# Span goals — layer 0

**Status: binding.** This is the top of the pyramid. It states why Span exists,
what outcome it is judged on, and what it is deliberately not trying to do.
Layers 1–3 derive from it. A design that satisfies every principle but not these
goals is still wrong. Authority and derivation between layers are defined in the
[requirements pyramid model](requirements-pyramid.md).

## 1. The problem

Documentation fails statement by statement.

Within a single document, some statements remain true while others quietly stop
being true. Nothing announces the change. The file still looks valid, the reader
still trusts it, and the next session starts from the same uncertainty. Staleness
is not a property of a document; it is a property of each statement, and it is
invisible until someone re-derives everything to check.

The cost is paid twice: either the reader re-derives what was already known, or
the reader acts on something that is no longer true. Both are expensive, and the
second is dangerous.

## 2. What Span exists to do

Span makes semantic understanding of code. The goals in §3 state the outcomes it
must produce; the two sections below explain why the shape is right.

### Why it can replace documentation

Code is checked by execution. It runs, or it does not. A failure forces a change,
so code carries an execution state tied to its source state.

Documentation has nothing of the kind. It is written once and read forever, and
nothing fails when it stops being true. That is why it rots: there is no check,
so there is no consequence.

Span gives semantic understanding the property code has — a mechanical check
against the exact source it describes. A conclusion is supported or it is not,
and a change to that source invalidates it. Understanding therefore becomes a
critically checkable artifact that must sustain under code change, and can
replace documentation instead of accumulating beside it.

This is the point of the product, not a side effect: fewer unchecked documents,
and a checked surface description where the semantic content used to live.

### Why the understanding is layered

A codebase does not become understandable at one scale. A domain, the services
inside it, and the files inside those are different scopes answering different
questions, and flattening them loses exactly the boundary that makes each one
checkable.

Span applies the same discipline to a target repository that this corpus applies
to its own requirements: distinct levels, clear boundaries, and no level
restating the one below. Understanding can begin at a domain and descend into
detail without the levels blurring. The mechanics are already stated in the
layers below — surfaces and containment in layer 2, status at granularity in F9,
and the aggregation rule that keeps a parent's conclusions separate from its
children's.

The method is not invented here. The evidence that it rests on established,
validated practice — and the limits of that claim — is recorded in the
[method grounding](method-grounding.md).

## 3. Goals

| ID | Goal | Meaning | Enforced by |
| --- | --- | --- | --- |
| **G1** | **Never present stale as current** | A reader who asks must learn what is current and what is not. No answer, summary, or status may blur the two. | F2, F9, L2, L9 |
| **G2** | **Never re-derive what is retained** | Established understanding is found and reused without the conversation that produced it. | F3, F7 |
| **G3** | **Never outlive the code silently** | When the code a conclusion rests on changes, the conclusion stops being usable and the change is named. | F2, F4, L2 |
| **G4** | **Audit any surface at its own granularity** | A file, a service, and a domain each report their own status, and a larger surface may honestly contain both current and stale understanding. | F9, L9, L10 |
| **G5** | **Cost less than the alternative** | Using Span must beat re-reading the code or maintaining documentation by hand, or it has no claim over the task. | F8 |
| **G6** | **Replace unchecked documentation** | Surface-bound semantic content lives as checked understanding, not as Markdown that nothing validates. Classic documentation for covered surfaces shrinks; what remains is content that cannot be tied to code. | F1, F2, F4 |

These six are the whole product intent. Everything in layers 1–2 exists to make
them true, and nothing may be added that does not.

## 4. What Span is not trying to do

- It does not produce unchecked documents (G6). The agent authors meaning; Span
  keeps its support current and findable. A Markdown file is only warranted for
  content that cannot be tied to code.
- It does not answer from first principles. A surface that has never been
  investigated returns a gap, not a generated answer.
- It does not judge semantic truth. It judges support against code.
- It does not mandate coverage or per-surface documentation (A9). Status is
  reported; compliance is not the product.
- It is not a search engine, model runtime, editor, or test runner.

## 5. What success looks like

A fresh agent, in a session with no memory, asks about a familiar surface and
receives a current answer with its status in one call. After a change, it learns
exactly which conclusions became stale, at every enclosing granularity, without
re-reading the code. Nothing stale is ever presented as current. The
documentation that remains for covered surfaces is smaller, and what remains is
checked. The whole exchange costs less than the alternative it replaced.

## 6. The pyramid

```text
Layer 0   goals.md               why: the problem, the outcomes, success
Layer 1   foundations.md         truths: axioms A1–A9, principles F1–F10
Layer 2   lifecycle-contract.md  contract: surfaces, operation families, laws L1–L11
Layer 3   functional-design.md   behaviour: identity, evaluation, propagation, composition
Layer 4   technical-design.md    implementation: baseline, refactoring set, schemas
```

Each layer is a consequence of the one above it. The ownership of each layer,
the placement test for a new statement, and the rule against restatement are
defined in the [requirements pyramid model](requirements-pyramid.md).

## 7. Why this document exists

A previous release built a coherent, well-tested store for agent-authored
conclusions and removed the operations that answered questions. Every local gate
passed. The product could not perform its job, because no document stated the
outcomes it was supposed to produce.

The goals are the first thing a change is judged against. Everything below them
is a means.
