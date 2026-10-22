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
- `agents-snippet.md` — canonical lifecycle block copied by the installer into the managed `AGENTS.md` block (guidance only, never semantics)
- `semantic-governance-addendum.md` — adopted v0.6 addendum: query-time
  store-subject resolution (F1), cross-unit established-evidence
  citation (F2), validation tests, operational prerequisites
- `semantic-governance-addendum-b.md` — bootstrap, review ceremony,
  and quality baseline: lifecycle placement, manifest, review fields,
  section-aware reads, payload helpers, drift notes, validation tests
- `semantic-governance-addendum-e.md` — binding corrective chapter for
  target-boundary semantics, read-only structural consumption, MCP/runtime
  alignment, generated-artifact prevention, and acceptance closure;
  §9 records adopted tier-1 operational remediation (verify-fast-path,
  census diff, backup on install, seeds convention)
- `semantic-governance-addendum-f.md` — adopted single-MCP direction:
  Span absorbs read-only structural navigation (`locate`, `neighbors`),
  graft MCP deregistered, E-14 scan deleted; implementation pending
  authorization (E governs until F-7 passes)
- `semantic-governance-addendum-j-locality-derivation-and-wire-projection.md`
  — adopted locality (scoped discovery freshness, operation-local structural
  completeness), service-owned derivation (default question slices, candidate
  target accounts, first-admission seed, bounded mapping batches), the
  one-grammar compact MCP wire codec, and the interpretation profile
- `semantic-governance-addendum-m-agent-facing-mcp-friction-and-release-closure.md`
  — governing closeout for the public MCP friction/release boundaries:
  eleven-operation roster, continuation recovery, one setup locator,
  minimal task templates, batch-complete mapping accounting, opaque
  tokens, one OpenCode V2 registration, provider-owned structural
  currency, synchronized managed guidance, and the external-client gate
- `semantic-governance-addendum-l-agent-command-boundary.md` — adopted
  command/persistence ownership correction: the agent decides meaning through
  `question_decision` / `proposed_questions`; Span derives and persists the
  canonical `InterpretationCoverage`; wire-ceremony and installer corrections
  ship in the same change

Governing authority: `.context/requirements/`, the v0.6 implementation plan,
and Addendum E for the corrective boundaries named there; Addendum L governs
the agent command boundary, and Addendum M governs the public
friction/release boundaries it names. If any historical
guide or Addenda B–D passage disagrees with E on those boundaries, E wins.
Guides describe; they never define semantics.
