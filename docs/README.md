# Span documentation

Product scope and non-goals live in the README (plan §20: scope and
non-goals are stated once, here by reference — Span answers
repository-understanding questions from indexed evidence for arbitrary
software repositories; it never edits code, runs tests, orchestrates
workflows, or originates authority).

- `architecture.md` — FCIS/SoC/DRY/strict-typing ownership
- `taxonomy.md` — subjects, claims, relationships, values
- `ports.md` — structural, evidence, and store contracts
- `interpretation.md` — agent-exchange contract and failure policy
- `authority-trust.md` — evidence/authority/trust/freshness model
- `indexing.md` — demand-driven incremental indexing lifecycle
- `freshness.md` — preflight, refresh, reconciliation
- `queries.md` — intents, answers, boundedness, pagination
- `invariants.md` — I-01–I-39 audit matrix with test evidence
- `mi-trace.md` — MI-01–MI-13 requirements-to-code trace
- `v05-v06-delta.md` — v0.5→v0.6 contract delta register
- `mcp.md` — MCP transport reference
- `acceptance.md` — fixtures and the MI-11/S-01/S-02 model
- `contributing.md` — testing, ledger, publication/provenance policy
- `skills.md` — Agent Skills integration guide
- `lifecycle.md` — agent execution lifecycle, init/readiness, examples
- `hooks.md` — lifecycle-hook integration, matrix, reference adapter
- `semantic-governance-addendum.md` — adopted v0.6 addendum: query-time
  store-subject resolution (F1), cross-unit established-evidence
  citation (F2), validation tests, operational prerequisites
- `semantic-governance-addendum-b.md` — bootstrap, review ceremony,
  and quality baseline: lifecycle placement, manifest, review fields,
  section-aware reads, payload helpers, drift notes, validation tests

Governing authority: `.context/requirements/` and the v0.6
implementation plan. If any guide below disagrees with those, they
win. Guides describe; they never define semantics.
