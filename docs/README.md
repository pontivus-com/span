# Span documentation

Span answers repository-understanding questions from indexed evidence for
arbitrary software repositories. It never edits code, runs tests,
orchestrates workflows, or originates authority.

## Start here

- [Repository overview](overview.md) — a map of the code and the request path for
  a first-time reader.
- [Install and connect](install.md) — prerequisites, installer, Codex and
  OpenCode setup, verification.
- [Using Span](usage.md) — first use, establishment, freshness, scoped
  re-checking, and the normal development workflow.
- [Lifecycle](lifecycle.md) — how Span fits into coding-agent work.
- [MCP reference](mcp.md) — operations, request/response shapes, and the
  compact wire grammar.
- [Onboarding runbook](onboarding-runbook.md) — establish reusable
  understanding for an exact target.
- [Scope and boundaries](scope.md) — what Span is and is not, how it differs
  from documentation, memory, search, and structural tools.
- [FAQ](faq.md) — common questions about truth, readiness, storage, and
  autonomous behavior.
- [Release notes](../CHANGELOG.md) — what changed in each version, including
  migration.

## Design

- [Architecture](architecture.md) — functional-core/imperative-shell
  ownership, responsibility boundaries, and design principles.

## Contracts

- [Taxonomy](taxonomy.md) — subjects, claims, relationships, values.
- [Ports](ports.md) — structural, evidence, and store contracts.
- [Interpretation](interpretation.md) — the agent-exchange contract and
  failure policy.
- [Authority and trust](authority-trust.md) — evidence, authority, trust,
  and freshness.
- [Indexing](indexing.md) — demand-driven incremental indexing.
- [Freshness](freshness.md) — preflight, refresh, reconciliation.
- [Queries](queries.md) — intents, answers, boundedness, pagination.
- [Invariants](invariants.md) — the invariant audit matrix and test
  evidence.
- [Acceptance](acceptance.md) — fixtures and the public acceptance model.
- [Glossary](glossary.md) — terms used across the docs.

## Integration

- [Skills](skills.md) — Agent Skills integration.
- [Hooks](hooks.md) — lifecycle-hook behavior and the reference adapter.
- [Agent snippet](agents-snippet.md) — the lifecycle block the installer
  copies into a target repository's managed `AGENTS.md` section.
- [Contributing](contributing.md) — development, testing, and dependency
  policy.

## Evidence

- [Acceptance evidence](acceptance-evidence/) — recorded runs and the
  fixtures behind them.

Guides describe behavior. They do not define semantics. The code, its
contracts, and the tests are the authority for what Span actually does.
