# Span goals — layer 0

**Status: binding target for Span 1.0 Beta.** This is the top of the pyramid. It
states why Span exists, what outcomes it is judged on, and what it deliberately
does not do. Layers 1–3 derive from it. A design that satisfies every lower-layer
mechanism but not these goals is still wrong. Authority and derivation between
layers are defined in the [requirements pyramid model](requirements-pyramid.md).

**1.0 Beta product model, 21 November 2026.** Version 1 is the first product
model that covers both maintained empirical understanding and maintained
governing understanding. Beta describes delivery maturity, not an incomplete
product boundary.

**Beta 2 product amendment, 23 November 2026.** Investigation-time capture and
shared reuse are distinct outcomes. Understanding established during engineering
work is retained immediately, but a fresh agent receives it as ordinary shared
knowledge only after that exact semantic revision has been explicitly curated.
This qualification is independent of evidence currency and governing authority.

## 1. The problem

Software work depends on two different classes of knowledge that drift in
different ways.

**Empirical understanding** describes what the implementation currently does.
Source code, configuration, tests and recorded executions can be observed
mechanically, but an explanation of their meaning can still become stale when
its declared evidence changes.

**Governing understanding** describes what the implementation is intended to
satisfy: purpose, invariants, contracts, functional design and technical design.
Those rules are not made authoritative by execution. They are authoritative
because a responsible owner has declared them, their applicability is explicit,
and their derivation is intact. A governing source can remain byte-for-byte
unchanged while becoming inapplicable, superseded, conflicted or disconnected
from the rule that justified it.

A coding agent otherwise pays the cost repeatedly. It must re-derive what the
code does, rediscover which canonical sources govern the work, reconstruct the
path from first principles to implementation, and decide whether prior
conclusions still apply. If it skips that work, it can act on stale empirical
understanding, obsolete authority, or an incomplete governing chain.

The two failure modes require different proof. Execution and source identity can
support empirical currency. Canonical ownership, accepted status, applicability
and derivation establish authority currency. Span exists to maintain both
without pretending that one proves the other.

## 2. What Span exists to do

Span maintains auditable understanding of a software system.

It keeps agent-authored semantic understanding attached to the evidence on which
it rests. It also resolves the repository's declared Functional Pyramid so an
agent can determine which goals, invariants, contracts and designs govern the
surface it is about to understand or change.

Span does not originate those meanings. Repository owners originate governing
authority. The agent or human investigator authors semantic and conformance
judgments. Span keeps identities, applicability, dependencies, currency,
history and change consequences mechanically explicit.

### Why explanatory documentation can shrink

A code explanation that exists only as prose has no mechanical relationship to
the source it describes. Span gives that explanation a checkable dependency on
the exact evidence used to establish it. When the declared support changes, the
understanding stops being served as current.

Surface-bound explanatory documentation can therefore move into retained,
curated and checked understanding instead of accumulating as an unchecked
parallel description.

### Why canonical governing documents remain

A goal, invariant or contract cannot be replaced by executing the implementation.
It is a constitutive decision about what the system is supposed to achieve or
guarantee. Such a source remains canonical.

Span does not replace canonical governing sources. It gives them stable identity,
declared applicability, explicit derivation, current status and downstream
change consequences through the Functional Pyramid.

### Why the understanding is layered

A software system does not become understandable at one scale or from one kind
of proof. A domain, service, file and symbol are different semantic surfaces.
Purpose, invariants, contracts, functional design and technical design are
different authority layers. Flattening either hierarchy loses the boundaries
that make the resulting understanding auditable.

Span therefore maintains semantic surfaces and Functional Pyramid authority as
distinct but composable structures. A conclusion has one semantic owner while
one path may be governed by several functional contexts and several applicable
authority chains.

## 3. Goals

| ID | Goal | Meaning | Enforced by |
| --- | --- | --- | --- |
| **G1** | **Never present unsupported or unresolved understanding as current** | A reader who asks must learn what is usable, what is not, and why. No answer, authority route, summary or status may blur current support, unresolved applicability or operational inability. | F2, F9, F11, L1–L3, L9, L12 |
| **G2** | **Retain established understanding for qualified reuse** | Understanding established during work is retained through Span without the conversation that produced it. Capture is immediate; ordinary shared reuse begins only after the exact semantic revision has been explicitly curated. Retention, support currency and reuse qualification remain distinguishable. | F3, F7, F13 |
| **G3** | **Never outlive declared support silently** | When source evidence, governing authority, applicable functional context, discovery membership or a semantic premise changes, dependent understanding stops being usable without reassessment and the cause is named. | F2, F4, F11, L2, L10, L12 |
| **G4** | **Audit semantic scope and governing scope independently** | A file, service and domain report semantic status at their own granularity, while a participating path also reports the complete declared Functional Pyramid route that governs it. Neither hierarchy is substituted for the other. | F9, F11, L9, L12 |
| **G5** | **Earn its place in real software work** | Span must provide enough practical value in real engineering work to justify the lifecycle overhead it adds. Beta validates that value through sustained adopter use and follow-up correction, not through a synthetic pre-release cost score. | F8 |
| **G6** | **Replace unchecked explanation, preserve canonical authority** | Surface-bound explanatory content intended for shared reuse lives as curated, checked understanding tied to support. Canonical governing sources remain authoritative artifacts and are referenced, not copied into a competing Span owner. | F1, F2, F4, F11, F13, L11 |
| **G7** | **Make the governing path from first principles to implementation explicit** | Before interpreting or changing a participating surface, the agent can obtain the declared functional contexts, applicable authority rules, derivation path, provenance and unresolved relationships without inferring them from file names, topology or prose relevance. | F6, F10, F11, L8, L12 |
| **G8** | **Make declared governance adoptable without inventing it** | One or more registered repositories can be explicitly brought into, revised within, excluded from, and recovered as a Functional Pyramid without copying canonical rule content or manufacturing missing authority. Incomplete coverage and unresolved relationships are visible before they can be mistaken for a complete governing model. | F11, F12, L13–L16 |

These eight are the product intent. Everything below them exists to make them
true, and nothing may be added merely because it is convenient to implement.

## 4. What Span is not trying to do

- It does not originate product, professional, legal, security or organizational
  authority. Repository owners and external authorities do that.
- It does not prove that a governing principle is intrinsically true. It can
  establish that the principle is the current declared authority, that its
  governing relationships resolve, and that it applies to a selected scope.
- It does not judge semantic or conformance truth. The agent or human investigator
  authors those judgments; Span validates and maintains their declared support.
- It does not infer authority from repository structure, path names, semantic
  similarity or structural adjacency.
- It does not produce unchecked explanatory documents (G6), but it also does not
  replace canonical governing sources whose function is to originate normative
  meaning.
- It does not answer an uninvestigated semantic question from first principles.
  A surface with no retained understanding returns a gap even when its governing
  route is fully resolved.
- It is not a model runtime, source editor, application test runner or general
  search engine.

## 5. What success looks like

A repository set can first be adopted into a Functional Pyramid through an explicit,
validated lifecycle. Registration alone does not imply participation, repository
membership does not imply rule applicability, and a partial migration remains
explicitly partial rather than being represented as complete governance.

A fresh agent with no conversation memory asks about a surface and receives, in
one lifecycle interaction, supported and curated retained semantic understanding
or an actionable gap/status when no shared knowledge is eligible for reuse.
Pending captured understanding remains explicit non-Answer state. When the
repository is ACTIVE in the Functional Pyramid, the same interaction also
returns the declared governing route from applicable first principles to
implementation.

After implementation evidence changes, dependent semantic understanding is
identified for reassessment. After a functional-context declaration, authority
owner, authority content, status or governing relationship changes, dependent
normative understanding is likewise identified without requiring an
implementation edit.

A conformance conclusion is reusable only while both the empirical support it
cites and the governing route it depended on remain usable. Canonical governing
sources remain single owners rather than being copied into Span. Explanatory
documentation for covered surfaces shrinks.

For Beta, practical product value is established through real adopter use: the
tool must be useful enough to remain in the engineering workflow, and observed
friction or defects are corrected in follow-up Beta releases. Comparative
time/token claims require their own evidence, but a synthetic equivalent-task
score is not a pre-release success condition.

## 6. The pyramid

```text
Layer 0   goals.md               why: problem, outcomes, success, non-goals
Layer 1   foundations.md         truths: axioms and product principles
Layer 2   lifecycle-contract.md  contract: surfaces, Functional Pyramid view,
                                  operations, payloads and laws
Layer 3   functional-design.md   deterministic behaviour: semantic support,
                                  authority resolution, propagation and composition
Layer 4   technical-design.md    implementation choices and migration
```

Each layer is a consequence of the one above it. The ownership of each layer,
the placement test for a new statement, and the rule against restatement are
defined in the [requirements pyramid model](requirements-pyramid.md).

## 7. Why Version 1 begins here

Earlier Span releases solved the maintained-understanding lifecycle for code
surfaces and already contained explicit authority-support primitives. Span's own
development nevertheless required a separate requirements pyramid to answer
which goals, foundations, contracts and designs governed an implementation
decision.

That is product-discovery evidence: a class of indispensable software
understanding existed outside the product's maintained model.

Version 1 incorporates that missing class through the Functional Pyramid. The
result is one product that maintains empirical understanding, governing
understanding and the supported relationship between them while preserving the
different proof each requires.
