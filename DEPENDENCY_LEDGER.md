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
| MCP SDK (Python) — `modelcontextprotocol/python-sdk` (`mcp` on PyPI) | MCP transport (Phase 4.1) | SELECTED | Official SDK: `https://github.com/modelcontextprotocol/python-sdk`; PyPI `mcp==2.3.0` (this selection). License: **MIT** (verified 2026-10-07 from PyPI `License:` metadata field + repo LICENSE; same MIT as the Phase 0.4 check). Distribution role: MCP stdio transport only — protocol framing for the 8 thin tools; no semantic content. GPL-compatibility basis: MIT is GPL-compatible permissive; paired with
the selected GPL-3.0-only publication license (2026-10-08 owner
decision). Why necessary: protocol-correct MCP server without hand-rolling the wire protocol. Viable alternative: hand-written JSON-RPC over stdio (rejected: protocol drift risk, no benefit; transport would still be thin). Span uses only `mcp.server` (low-level Server); no Span semantic type is a pydantic model — canonical dataclasses cross via strict canonical JSON only (I-04/I-18). |
| MCP SDK transitive closure (`mcp-types==2.3.0`, `pydantic>=2.12`, `anyio`, `httpx2`, `jsonschema`, `opentelemetry-api`, `pyjwt`, `python-multipart`, `starlette`, `sse-starlette`, `uvicorn`) | Transport support libraries (no direct Span imports) | SELECTED (with parent) | All OSI-approved permissive licenses (MIT/Apache-2.0/BSD family); no copyleft in closure (verified 2026-10-07 from PyPI metadata). Paired with
the selected GPL-3.0-only publication license, same as parent. |
| Production structural provider — Graft (`@nanonets/graft@0.21.1`, source `NanoNets/context-graph-engine`) | Structural source (Phase 2.1) | SELECTED (plan-directed first provider; owner confirms at publication) | Identity/license verified Phase 0.4 (MIT, 2026-10-07); version pinned 0.21.1 (latest at 2026-10-13, npm registry). Suitability evaluated Phase 2.1: serves all five §5.2 operations from the wiring graph + git + target file reads; closed node-kind/relation mapping tables with explicit errors for unknown vocabulary (no semantic shaping); separately installable npm package, no Pontivus code. Implemented in `shell/structural/graft.py` against §5.2 only. Provisioning: installer auto-installs the pinned version into Span's tools directory (`npm install --prefix <tools>`); users never install or name it. Runtime requirement: node + npm at install time only; the managed binary thereafter (pointer at `<data-dir>/structural-indexer.json`). Version bumps update the installer constant, this row, and the install receipt in the same change. |
| SQLite (stdlib `sqlite3`) | Canonical persistence (Phase 1.7) | SELECTED | Stdlib module, no third-party binding. Selected by Phase 1.7 implementation (`shell/sqlite_store.py`); zero license burden. |

## Test runner decision (Phase 0, amended Phase 4)

`python3 -m unittest` (stdlib) was the Phase 0 test runner. The suite
grew onto `pytest` (MIT, OSI-approved; no license burden) for
fixture-style integration coverage — this entry records that
adoption per the Phase 0 rule. Tests remain `unittest.TestCase`
style and runnable under both runners. A span-local pytest config
(`pyproject.toml [tool.pytest.ini_options]`) keeps span runs
independent of any enclosing workspace pytest config (MI-13/L).

## Provenance-first publication gate (plan Phase 0.5)

- Every file currently in this repository is project-authored for Span
  (skeleton, governance, tests) or is an input/governance document carried
  under `.context/` — no third-party source, fixture, example, or generated
  artifact is present.
- Build/test/runtime require no private workspace access: `python3 -m
  unittest discover -s tests` runs from the Span root with no `PYTHONPATH`,
  no parent imports, no network.
- `LICENSE`: **RESOLVED 2026-10-08** — GPL-3.0-only selected by explicit
  product-owner decision. Verbatim GPL-3.0 license text installed at
  repository root; `pyproject.toml` declares `GPL-3.0-only`. Publication
  (Phase 5, MI-11 M) is unblocked on licensing.

## Private-name/path scanning (plan Phase 0.6)

Supplemental backstop only (does not replace MI-11 isolation acceptance):
`tests/unit/test_isolation_gate.py` fails on absolute workspace paths,
parent-relative references, Pontivus imports, required symlinks outside
Span, or parent-generated artifacts used as required inputs.
