# Span documentation

Span is the evidence-backed knowledge layer for coding agents working on a
software system. It retains supported understanding captured during engineering
work, records which exact revisions have been curated for shared reuse, and
maintains the applicable path through the project's canonical goals, principles,
contracts, functional design, and technical design. At task time, supported and
curated knowledge becomes working context for the exact software surface the
agent is handling. Empirical support, curation and governing relationships remain
distinct, so Span can show what is reusable, what is pending review, and what a
code or guidance change makes require another look. Span is this software
knowledge layer inside a broader knowledge-factory topology; it is not a claim
to own the organization's complete knowledge system.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

## Foundations

- [Requirements pyramid model](requirements-pyramid.md) — how the layers are
  structured, what each owns, and where a new requirement belongs.
- [Goals](goals.md) — layer 0: why Span exists, the outcomes it is judged on,
  including replacing unchecked documentation, and what it deliberately does
  not do.
- [Foundations](foundations.md) — layer 1: binding axioms and principles that
  govern every Span design, contract, implementation, test, and release.
- [Lifecycle contract](lifecycle-contract.md) — layer 2: surfaces and status,
  the three public lifecycle operations, the payloads the agent sends and receives, the
  contract laws, and the boundary between the agent's work and Span's internals.
- [Functional design](functional-design.md) — layer 3: identity, containment,
  support evaluation, propagation, response composition, state transitions,
  retention, concurrency, host expectations, and truncation.
- [Technical design](technical-design.md) — layer 4: the implementation baseline,
  retained historical mechanisms, and the Version-1 Functional Pyramid mechanisms
  that realize the layer-0–3 contract.
- [Method grounding](method-grounding.md) — the evidence that the method rests on
  established, validated practice, and what is not claimed.

## Implementation

- [1.0.0 Beta 3 implementation plan](implementation-plans/1.0.0-beta3.md) —
  one reconciled campaign covering capture/curation, repository schema 15,
  B3-D01/B3-D02 installer and production-topology remediation, Functional
  Pyramid-preserving implementation, first-adopter revalidation, public
  knowledge-factory narrative alignment and release gates. The canonical
  behavior/mechanisms are owned by the layer-0–4 documents above; the plan
  derives from them.
- [1.0.0 Beta 1 implementation plan](implementation-plans/1.0.0-beta.md) —
  historical Version-1 Functional Pyramid implementation and Beta-1 release
  campaign.
- [0.10.3 implementation plan](implementation-plans/0.10.3.md) —
  low-friction lifecycle work package, ordered tasks, decision gates and
  verification; released 2026-11-14.
- [0.10.2 implementation plan](implementation-plans/0.10.2.md) — prior
  remediation tasks and verification. Older plans in `.context/plans/` are historical.

## Start with the lifecycle

- [Using Span](usage.md) — ask, record, reuse, and re-align after change.
- [First investigation](onboarding-runbook.md) — setup through fresh-session discovery.
- [Lifecycle](lifecycle.md) — contexts, recording, recovery, support, and transition.
- [Install and connect](install.md) — installation, host limits, verification, upgrade, and removal.
- [Backup and recovery](recovery.md) — artifact contents, storage, verification, restore, and retention.
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

Guides describe the shipped contracts; code and observed execution establish
behavior. A local pass is not host-delivery or comparative-value acceptance.
