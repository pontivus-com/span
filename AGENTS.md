# Span — Agent Operating Rules

This repository is the standalone **Span** project: semantic repository
intelligence for coding agents.

## 1. Governing authority

The finalized v0.6 implementation plan and its generalized FACT /
pre-implementation documents govern product semantics and scope:

- `.context/requirements/`
- `.context/plans/span-standalone-semantic-repository-implementation-plan-v0.6.md`
  (v0.5 retained byte-identical as the reviewed record; v0.6 governs)

If this file conflicts with those documents on product semantics, the
requirements package and plan win.

The v0.6 plan remains subordinate to MI-01..MI-13 where the plan explicitly
establishes that precedence.

## 2. Standalone independence

Span is independent of Pontivus, Pontivus Legal, and Pontivus Graph.

The enclosing workspace (`<workspace>`) may be used as private
development/reference context only. It is a development enclosure, not an
architectural dependency.

No required Span implementation may import from, load from, execute from, or
depend on parent-workspace files. All required paths resolve from the Span
repository root, an explicitly supplied target-repository path, or explicit
external configuration.

## 3. Engineering standards (binding)

FCIS, SoC, DRY, and strict typing are binding. They determine implementation
ownership and boundaries; they are not advisory style guidance.

- One canonical typed carrier exists per semantic boundary.
- No ad-hoc DTOs, duplicate semantic representations, compatibility bridges,
  fallback parsing, or parallel semantic writers are permitted.

## 4. Authority rules

- Code first: what code does, contains, consumes, produces, and how it
  flows is established from code evidence plus bounded interpretation
  alone. No document is required, and reliability never depends on
  documentation for these claims.
- Authority precedes inference — for normative claims only (who owns,
  what governs, what must not be reconstructed). Such claims require
  a cited record or stay explicitly unresolved; they are never
  inferred from structure.
- Structural evidence does not establish semantic authority or ownership.
- Missing, ambiguous, conflicted, stale, or unverifiable knowledge remains
  explicit. It is never coerced into certainty.

## 5. Working-tree and version-control rules

- The parent Pontivus working tree must not be modified unless a separate
  task explicitly authorizes it.
- Git commits require separate explicit authorization. A request to
  implement, edit, test, or report does not by itself authorize a commit.

## 6. Semantic decisions

- Implementation workers must not invent unresolved semantic or product
  decisions. Physical-design questions resolved in the v0.6 plan are binding;
  anything the plan leaves open requires a contract amendment, not worker
  inference.
- The v0.5 phase order (Phase 0 → 1 → 2 → 3 → 4 → 5) and acceptance gates
  are binding.

## 7. Product identity

- **Span** is the concrete product, repository, package (`span`), and MCP
  server identity.
- **semantic repository** is the architectural category and is used where the
  system class or internal architecture is meant.
- Public MCP operations are exactly `initialize_repository`,
  `initialize_target`, `explain`, `impact`, `trace`, `authority`,
  `status`, `refresh`, `submit_interpretation`, `locate`, `neighbors`.
  No `semantic_*` public aliases exist. Where Addenda B–C historical text
  says eight, Addendum E governs the semantic operations, Addendum F adds
  the two read-only structural-navigation operations, and Addendum M
  removes the dead reissue operation (eleven current operations).
- Semantic interpretation is executed by the invoking LLM-connected agent;
  Span owns the task contract, strict ingress, validation, authority, trust,
  freshness, persistence, and answers — never model selection, endpoints,
  credentials, or provider invocation.
- Canonical `Semantic*` domain types (e.g. `SemanticClaim`,
  `SemanticAnswer`, `SemanticExplainRequest`) are domain concepts and retain
  their names.
