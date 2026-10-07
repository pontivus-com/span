# Span — Dependency / License Ledger (plan Phase 0.3)

Binding rule (plan MI-13, Phase 5 exit): no selected runtime dependency
without verified identity + license suitability. Workers must not select
dependencies by inference.

Status values: `UNSELECTED` (candidate only) · `VERIFYING` · `VERIFIED` ·
`SELECTED`. Only `SELECTED` dependencies may appear in `pyproject.toml`.

## Runtime / build dependencies

| Dependency | Role | Status | Identity / license evidence |
|---|---|---|---|
| Python >= 3.12 (stdlib only) | Runtime | SELECTED | Language runtime + stdlib; no third-party code. `unittest` is the Phase 0 test runner — stdlib, no install, no license burden. |
| `setuptools>=61` | Build backend | SELECTED | Build-time only; never imported by `span` at runtime. Ubiquitous, OSI-approved build backend. Pinned minimum only. |
| MCP SDK (Python) — `modelcontextprotocol/python-sdk` (`mcp` on PyPI) | MCP transport (Phase 4.1) | VERIFIED (candidate; selection at Phase 4.1) | Identity: official SDK, `github.com/modelcontextprotocol/python-sdk`. License: **MIT** (verified 2026-10-07 from `LICENSE` at repo main + repo About page). Permissive license; final GPL-variant pairing subject to owner LICENSE selection. Not selected; nothing added to `pyproject.toml`. |
| Production structural provider — Graft (`@nanonets/graft`, source `NanoNets/context-graph-engine`) | Structural source (Phase 2.1) | SELECTED (plan-directed first provider; owner confirms at publication) | Identity/license verified Phase 0.4 (MIT, 2026-10-07). Suitability evaluated Phase 2.1: serves all five §5.2 operations from `graft/.graph/wiring.json` + git + target file reads; closed node-kind/relation mapping tables with explicit errors for unknown vocabulary (no semantic shaping); separately installable npm package, no Pontivus code. Implemented in `shell/structural/graft.py` against §5.2 only. Runtime requirement: node + graft CLI wherever the provider is used (recorded here, not inferred). |
| SQLite (stdlib `sqlite3`) | Canonical persistence (Phase 1.7) | SELECTED | Stdlib module, no third-party binding. Selected by Phase 1.7 implementation (`shell/sqlite_store.py`); zero license burden. |

## Test runner decision (Phase 0)

`python3 -m unittest` (stdlib) is the Phase 0 test runner. Adopting
`pytest` or any third-party runner later requires a ledger entry plus
identity/license verification first. Rationale: zero-dependency bootstrap
keeps the Phase 0 exit ("builds/tests without private access") trivially
auditable.

## Provenance-first publication gate (plan Phase 0.5)

- Every file currently in this repository is project-authored for Span
  (skeleton, governance, tests) or is an input/governance document carried
  under `.context/` — no third-party source, fixture, example, or generated
  artifact is present.
- Build/test/runtime require no private workspace access: `python3 -m
  unittest discover -s tests` runs from the Span root with no `PYTHONPATH`,
  no parent imports, no network.
- `LICENSE`: **BLOCKED** — the exact GPL variant must be explicitly
  selected by the product owner/legal authority (plan Phase 0.1). Workers
  must not choose it by inference. Publication (Phase 5, MI-11 M) cannot
  pass until this row is resolved.

## Private-name/path scanning (plan Phase 0.6)

Supplemental backstop only (does not replace MI-11 isolation acceptance):
`tests/unit/test_isolation_gate.py` fails on absolute workspace paths,
parent-relative references, Pontivus imports, required symlinks outside
Span, or parent-generated artifacts used as required inputs.
