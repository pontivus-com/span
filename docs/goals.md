# Span goals — layer 0

**Status: binding target for Span 1.0 Beta.** This is the top product layer. It
owns the problem Span exists to solve, the outcomes it must achieve, its
non-goals, and its success conditions.

It does **not** own lifecycle mechanics, public payloads, deterministic
procedures, or implementation choices. Those derive through the lower layers.
Placement and no-restatement rules are defined in the
[requirements pyramid](requirements-pyramid.md).

## 1. The problem

Coding agents repeatedly pay to reconstruct software understanding that earlier
engineering work already established.

The problem has two independent sides:

- useful understanding of the implementation is easily lost between sessions or
  becomes unreliable after the evidence it depended on changes; and
- the project guidance that is supposed to govern a piece of software can be
  distributed, layered, cross-repository, or changed independently from the
  implementation.

Without maintained knowledge, a new agent must repeatedly rediscover what the
software does, which guidance applies, and whether earlier conclusions still
hold. If it skips that work, it can act on stale understanding, obsolete
guidance, or an incomplete governing path.

Span exists so useful software knowledge can compound across real engineering
work without silently outliving the things it depends on.

## 2. Product intent

Span maintains reusable understanding of a software system while keeping
implementation understanding and governing project guidance independently
auditable.

The exact domain definitions and invariants that make that outcome safe belong
to [Foundations](foundations.md). The goals below are the product outcomes those
principles must serve.

## 3. Goals

| ID | Goal | Meaning | Enforced by |
| --- | --- | --- | --- |
| **G1** | **Never present unsupported or unresolved understanding as current** | A reader who asks must learn what is usable, what is not, and why. No answer, authority route, summary or status may blur current support, unresolved applicability or operational inability. | F2, F9, F11, L1–L3, L9, L12 |
| **G2** | **Retain established understanding for qualified reuse** | Understanding established during work is retained through Span without the conversation that produced it. Capture is immediate; ordinary shared reuse begins only after the exact semantic revision has been explicitly curated. Retention, support currency and reuse qualification remain distinguishable. | F3, F7, F13 |
| **G3** | **Never outlive declared support silently** | When source evidence, governing authority, applicable document placement, discovery membership or a semantic premise changes, dependent understanding stops being usable without reassessment and the cause is named. | F2, F4, F11, L2, L10, L12 |
| **G4** | **Audit semantic scope and governing scope independently** | A file, service and domain report semantic status at their own granularity, while a participating path also reports the complete declared Functional Pyramid route that governs it. Neither hierarchy is substituted for the other. | F9, F11, L9, L12 |
| **G5** | **Earn its place in real software work** | Span must provide enough practical value in real engineering work to justify the lifecycle overhead it adds. Beta validates that value through sustained adopter use and follow-up correction, not through a synthetic pre-release cost score. | F8, F14 |
| **G6** | **Replace unchecked explanation, preserve canonical authority** | Surface-bound explanatory content intended for shared reuse lives as curated, checked understanding tied to support. Canonical governing sources remain authoritative artifacts and are referenced, not copied into a competing Span owner. | F1, F2, F4, F11, F13, F14, L11 |
| **G7** | **Make the governing path from first principles to implementation explicit** | For any directory in a participating repository, and before interpreting or changing a participating surface, the agent can obtain the relevant canonical documents from P0 through the deepest applicable layer, including their declared relationships, provenance and unresolved branches. | F6, F10, F11, L8, L12 |
| **G8** | **Make declared governance adoptable without inventing it** | One or more registered repositories can be explicitly brought into, revised within, excluded from, and recovered as a Functional Pyramid without copying canonical documents or manufacturing missing authority. What is declared and what is absent is visible at any location before it can be mistaken for a complete governing model. | F11, F12, L13–L16 |

These eight are the product intent. Everything below Layer 0 exists to make
them true. A lower-layer mechanism that cannot be justified by these outcomes
does not belong in the product merely because it is convenient to implement.

## 4. Non-goals

Span is not trying to:

- originate product, professional, legal, security, or organizational
  authority;
- prove a governing principle intrinsically true;
- judge semantic or conformance truth on behalf of the investigator/reviewer;
- infer governing authority from repository structure, path names, semantic
  similarity, or structural adjacency;
- create an unchecked parallel explanatory-documentation corpus;
- replace canonical governing sources whose job is to originate normative
  meaning;
- answer an uninvestigated semantic question merely because project guidance is
  available; or
- become a model runtime, source editor, application test runner, or general
  search engine.

The lower layers define how those boundaries are realized. This layer owns only
the intended product boundary.

## 5. What success looks like

Span succeeds when a fresh agent can begin real software work with maintained
knowledge rather than automatically reconstructing prior understanding, while
missing, pending, stale, conflicted, or unavailable knowledge remains explicit.

For participating repositories, the same work can be oriented by the declared
governing path from first principles to implementation without turning
repository structure or prose relevance into authority.

When implementation evidence or governing guidance changes, only the dependent
knowledge is made subject to reassessment; unrelated maintained knowledge
remains reusable.

Surface-bound explanatory material can shrink when its useful claims are
successfully maintained through Span, while canonical governing sources remain
single authoritative owners.

For Beta, practical product value is established through sustained use on real
engineering work. Observed friction, omissions, and defects become inputs to
follow-up correction. Comparative time, token, or cost claims require evidence
for the specific claim; they are not presumed from the design.

The exact lifecycle states, operations, and deterministic rules that realize
these success conditions belong to the lower Functional Pyramid layers.
