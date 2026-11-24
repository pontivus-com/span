# Span documentation

## Start here

1. [Install and connect](install.md).
2. [First investigation](onboarding-runbook.md) — resolve Functional Pyramid
   participation for governed use, then complete the first knowledge loop.
3. [Using Span](usage.md) — continue with the ordinary engineering lifecycle.

The [project README](../README.md) gives the product overview and
knowledge-factory problem framing.

## Find what you need

| I want to… | Start here |
| --- | --- |
| Try Span for the first time | [First investigation](onboarding-runbook.md) |
| Use Span during normal coding work | [Using Span](usage.md) |
| Understand the knowledge lifecycle | [Agent lifecycle](lifecycle.md) |
| Understand how Span keeps knowledge aligned with change | [Support currency and reassessment](freshness.md) |
| Understand how project guidance applies to code | [Evidence, authority, and interpretation](authority-trust.md) |
| Look up the exact MCP request/result grammar | [MCP reference](mcp.md) |
| Back up, restore, or move Span state | [Backup and recovery](recovery.md) |
| Troubleshoot a common product question | [FAQ](faq.md) |
| Contribute to Span | [Architecture](architecture.md) → [Repository overview](overview.md) → [Contributing](contributing.md) |
| Verify a product requirement or design decision | [Binding authority](#binding-authority) |
| Inspect what the current Beta candidate actually demonstrated | [Acceptance and evidence](acceptance.md) |

## Concepts

- [Agent lifecycle](lifecycle.md) — how maintained knowledge moves from use,
  through capture and review, to reuse and reassessment after change.
- [Support currency and reassessment](freshness.md) — how Span decides when
  retained knowledge needs another look.
- [Evidence, authority, and interpretation](authority-trust.md) — why knowing
  what the code does is different from knowing what it is supposed to follow.
- [Interpretation and recording](interpretation.md) — how agent judgment,
  evidence, disputes, and retained conclusions fit together.
- [Questions, retrieval, and bounds](queries.md) — how exact retrieval,
  references, limits, and continuations work.
- [Scope and product boundaries](scope.md) — what Span owns and what remains the
  responsibility of the coding agent, reviewer, or repository owner.

## Operator and protocol reference

Use these when you need an exact operational answer.

- [Install and connect](install.md) — installation, host setup, upgrades, and
  verification.
- [MCP reference](mcp.md) — exact public request/result grammar.
- [Backup and recovery](recovery.md) — backup, deployment, restore, and
  retention.
- [Lifecycle hooks](hooks.md) — host lifecycle notices and their boundaries.
- [Glossary](glossary.md) — exact Span terminology.
- [Offline initialization and readiness contract](../INITIALIZATION_CONTRACT.md)
  — derived installer/readiness contract used by operator tests; not a
  Functional Pyramid authority layer.

## Contributor and developer reference

These pages explain how Span is built and where implementation changes belong.

- [Architecture](architecture.md) — implementation ownership and composition.
- [Repository overview](overview.md) — code layout and change locations.
- [Port contracts](ports.md) — typed boundaries between the core and effects.
- [Structural evidence and indexing](indexing.md) — structural navigation and
  demand-driven semantic work.
- [Lifecycle vocabulary](taxonomy.md) — canonical carriers and internal
  vocabulary.
- [Agent skills integration](skills.md) and [managed agent snippet](agents-snippet.md).
- [Historical design references](design-references.md).
- [Contributing](contributing.md).

## Binding authority

Span uses a Functional Pyramid so product decisions have one canonical owner and
lower-level design remains traceable to the outcome it serves:

1. [Requirements pyramid](requirements-pyramid.md) — how requirements are
   placed, derived, and kept single-source.
2. [Goals](goals.md) — layer 0: the problem, outcomes, success, and non-goals.
3. [Foundations](foundations.md) — layer 1: axioms and principles.
4. [Lifecycle contract](lifecycle-contract.md) — layer 2: public lifecycle
   requirements and contract laws.
5. [Functional design](functional-design.md) — layer 3: deterministic product
   behavior.
6. [Technical design](technical-design.md) — layer 4: implementation
   mechanisms.

[Method grounding](method-grounding.md) provides supporting evidence for the
method; it is not a requirements layer.

## Verification and evidence

These documents answer **what has been demonstrated**, not **what Span is
required to do**.

- [Acceptance and evidence](acceptance.md) — current Beta-3 candidate verdict and evidence.
- [Historical acceptance evidence](acceptance-history.md) — superseded candidate and campaign evidence retained for audit.
- [Functional acceptance matrix](functional-acceptance.md) — traceability from
  functional requirements to executable tests.
- [Invariant audit matrix](invariants.md) — cross-layer verification boundaries.
- [Method grounding](method-grounding.md) — external grounding and claim limits.

## Programme records and history

Implementation plans track release campaigns. They are useful for programme
history and audit, but they are not product documentation.

The active Beta-3 programme record is:

- [Span 1.0.0 Beta 3 implementation plan](implementation-plans/1.0.0-beta3.md)

Completed campaigns are listed in the
[implementation-plan index](implementation-plans/README.md).

Historical technical-design baseline analysis, superseded transition/release
mechanisms, and dated delivery evidence are preserved in
[Technical-design history](history/technical-design-pre-version1.md). They are
provenance, not current Layer-4 authority.
