# Changelog

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
