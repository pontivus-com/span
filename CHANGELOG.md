# Changelog

## 0.6.2 — 2026-10-24

- Rust sources index again. The provider reports `mod` and `const` nodes,
  which had no mapping, so the whole structural load failed with "unknown
  structural node kind". `module` now maps to COMPONENT (a code container,
  like a file) and `constant` to CODE_SYMBOL (a named declaration, like a
  type), which is where `enum`, `type`, and `struct` already sat.
- A provider-vocabulary lane runs the pinned indexer against a Rust fixture,
  so a newly emitted node kind fails in CI rather than in a user's first
  `initialize_repository`.

## 0.6.1 — 2026-10-24

- README images and documentation links are absolute. The relative logo path
  rendered as an empty image on the PyPI project page, which cannot fetch
  repository-relative URLs.
- Carries the 0.6.0 work: canonical structured MCP results with advertised
  output schemas, a 16,000-byte ceiling on evidence delivered to the model,
  live pending work reported by `status` without exposing continuation
  tokens, the corrected `refresh` lifecycle, and status reads that fail
  rather than borrow a semantic state.

## 0.6.0 — 2026-10-23

First public release.

- Local MCP server for maintained codebase understanding.
- Eleven public operations: `initialize_repository`, `initialize_target`,
  `explain`, `impact`, `trace`, `authority`, `status`, `refresh`,
  `submit_interpretation`, `locate`, and `neighbors`.
- Evidence-backed claims with explicit authority, trust, and freshness.
- Partial staleness: a change marks the affected claim stale without
  discarding unaffected understanding.
- Scoped refresh and predecessor history.
- Managed structural indexer provisioning; no separate indexer download.
- Codex and OpenCode setup, Agent Skills, and report-only lifecycle hooks.
- Apache-2.0 licence.
