# Span documentation

Span answers semantic questions about a code repository, retains those answers
with their evidence, and restores their validity when the code changes. The
agent interprets and edits; Span admits evidence, records explicit commands,
and qualifies later reuse.

## Foundations

- [Requirements pyramid model](requirements-pyramid.md) — how the layers are
  structured, what each owns, and where a new requirement belongs.
- [Goals](goals.md) — layer 0: why Span exists, the outcomes it is judged on,
  including replacing unchecked documentation, and what it deliberately does
  not do.
- [Foundations](foundations.md) — layer 1: binding axioms and principles that
  govern every Span design, contract, implementation, test, and release.
- [Lifecycle contract](lifecycle-contract.md) — layer 2: surfaces and status,
  the five operation families, the payloads the agent sends and receives, the
  contract laws, and the boundary between the agent's work and Span's internals.
- [Functional design](functional-design.md) — layer 3: identity, containment,
  support evaluation, propagation, response composition, state transitions,
  retention, concurrency, host expectations, and truncation.
- [Technical design](technical-design.md) — layer 4: the implementation baseline,
  what is retained from 0.8.3 and the withdrawn internal baseline, and the minimal refactoring set.
- [Method grounding](method-grounding.md) — the evidence that the method rests on
  established, validated practice, and what is not claimed.

## Implementation

- [Implementation plan — 2026-11-01](../.context/plans/2026-11-01-implementation-plan.md)
  — ordered stages, gate evidence, and open inputs. Not a pyramid layer.

## Start with the lifecycle

- [Using Span](usage.md) — ask, record, reuse, and re-align after change.
- [First investigation](onboarding-runbook.md) — setup through fresh-session discovery.
- [Lifecycle](lifecycle.md) — contexts, recording, recovery, support, and transition.
- [Install and connect](install.md) — installation, host limits, verification, upgrade, and removal.
- [MCP reference](mcp.md) — three tools and authoritative wire grammar.
- [Scope](scope.md) and [FAQ](faq.md) — product responsibilities and beta limits.

## Contracts and implementation

- [Architecture](architecture.md) and [repository overview](overview.md) — ownership and code map.
- [Ports](ports.md) — canonical typed evidence, structural, store, and authority boundaries.
- [Interpretation and recording](interpretation.md) — agent judgment, atomic commands, disputes, and verification.
- [Support currency](freshness.md) — dependencies and explicit re-alignment.
- [Evidence and authority](authority-trust.md) — declared governance and uncertainty.
- [Questions and bounds](queries.md) — answers, gaps, retrieval references, limits, and cursors.
- [Indexing](indexing.md) — structural setup and demand-driven semantic work.
- [Taxonomy](taxonomy.md) and [glossary](glossary.md) — active lifecycle carriers and terminology.
- [Invariants](invariants.md) — contract intent and named test boundaries.
- [Acceptance](acceptance.md) — functional, host, artifact, and product-value evidence.
- [Design references](design-references.md) — historical note IDs and their current subject owners.

## Agent integration and contribution

- [Skills](skills.md) and [managed agent snippet](agents-snippet.md).
- [Hooks](hooks.md) and [per-host delivery status](../integrations/hosts/triggers.md).
- [Contributing](contributing.md) and [changelog](../CHANGELOG.md).

[Older acceptance transcripts](acceptance-evidence/) remain historical.
Guides describe the shipped contracts; code and observed execution establish
behavior. A local pass is not host-delivery or comparative-value acceptance.
