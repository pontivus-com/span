# Changelog

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
