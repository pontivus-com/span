# Contributing, testing, publication

## Testing

`PYTHONPATH=src:. python3 -m pytest tests` (span-local config keeps
runs independent of any enclosing workspace). All tests are
`unittest.TestCase` style and also run under
`python3 -m unittest discover -s tests`. In-cluster/serial rules of
any enclosing workspace do not apply here: Span is standalone and has
no cluster path.

Coverage expectations: unit (core rules, carriers, serialization,
ports, shells, paging, skills scan, init contract, isolation gate),
integration (slices, MCP transport incl. SDK round-trip, hooks),
acceptance (vertical slice, S-01/S-02, v0.6 contract paths). New
carriers require construction/serialization tests; new behavior
requires the owning phase's tests; contract changes update the plan
doc in the same change (workers never invent semantics — open
questions need a contract amendment, not inference).

## Dependencies and licenses

`DEPENDENCY_LEDGER.md` is binding: no runtime dependency without a
verified identity/license row (MI-13). Current: Python ≥3.12 stdlib,
`setuptools` (build), MCP SDK `mcp==2.3.0` (MIT) + permissive closure,
managed structural indexer `@nanonets/graft@0.21.1` (MIT, provisioned by
the installer into Span's tools dir — never a user prerequisite),
`pytest` (MIT, test runner).

## Publication and provenance (MI-13)

No proprietary Pontivus material in build, test fixtures, schemas,
docs, or runtime deps; no public schema encodes proprietary concepts;
no test requires a proprietary repo or service. Each public
source/fixture has project-authored or verified redistributable
provenance. **Resolved 2026-10-08**: GPL-3.0-only selected by explicit
product-owner decision; verbatim license text at repository root
(`LICENSE`), declared in `pyproject.toml`.
