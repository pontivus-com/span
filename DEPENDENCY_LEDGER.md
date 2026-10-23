# Dependency and licence ledger

This ledger records every runtime and build dependency, its licence, and why
it is present. A dependency is not added without a verified identity and a
licence compatible with Span's Apache-2.0 release.

Status values: `UNSELECTED` (candidate only) · `VERIFYING` · `VERIFIED` ·
`SELECTED`. Only `SELECTED` dependencies may appear in `pyproject.toml`.

## Runtime and build dependencies

| Dependency | Role | Status | Identity and licence |
|---|---|---|---|
| Python 3.12+ standard library | Runtime | SELECTED | Language runtime and standard library; no third-party code. |
| `setuptools>=61` | Build backend | SELECTED | Build-time only; never imported by `span` at runtime. OSI-approved. |
| MCP Python SDK (`mcp==2.3.0`) | MCP transport | SELECTED | [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk); MIT. Used only for protocol framing over stdio; it carries no semantic content. |
| MCP SDK transitive closure | Transport support | SELECTED (with parent) | MIT/Apache-2.0/BSD-family licences; no copyleft. |
| Graft (`@nanonets/graft@0.23.0`) | Structural source | SELECTED | [NanoNets/context-graph-engine](https://github.com/NanoNets/context-graph-engine); MIT. The installer provisions this pinned version into Span's tools directory; users do not install or name it. Node and npm are required at install time. |
| SQLite (`sqlite3`) | Persistence | SELECTED | Standard-library module; no third-party binding. |
| `pytest` | Test runner | SELECTED | MIT. Tests also run under the standard-library `unittest` runner. |

## Why these dependencies

- **MCP SDK.** Span is an MCP server. The official SDK provides protocol-correct
  stdio framing, which is not worth hand-rolling.
- **Graft.** Span deliberately does not own a second structural index. Graft
  supplies wiring-graph facts, and Span maps the vocabulary it understands.
  Unknown node kinds and relations fail explicitly rather than being guessed.
- **SQLite.** One local store, no service, no database server, no credential.

## Licence basis

Span is released under **Apache-2.0**. Every selected dependency is
permissive (MIT, Apache-2.0, or BSD-family). No copyleft dependency is
required to build, test, or run Span.

`LICENSE` contains the verbatim Apache-2.0 text and `NOTICE` carries the
project notice. Both are part of the distribution.

## Provenance

Every file in this repository is project-authored or is a fixture written for
Span. No third-party source, proprietary fixture, or generated artifact is
required to build, test, or run the project.

The isolation test (`tests/unit/test_isolation_gate.py`) is a backstop: it
fails on absolute workspace paths, parent-relative references, proprietary
imports, symlinks outside Span, or parent-generated artifacts used as
required inputs.
