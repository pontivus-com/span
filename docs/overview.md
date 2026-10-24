# Repository overview

A short map for a first-time reader. The code and its tests are the authority for
what Span does; this page only tells you where to look.

## What Span is

Span is a local MCP server that stores codebase understanding together with the
evidence that supports it, and reports whether that evidence is still current.
It does not call a model, edit a repository, or run tests. When understanding is
missing, it suspends and hands a bounded interpretation task to the calling
agent, then validates what the agent submits.

## Layout

```text
src/span/core/      deterministic semantic core
src/span/ports/     typed interfaces (no effects)
src/span/service/   operation composition and orchestration
src/span/shell/     effects: git, filesystem, SQLite, structural index, MCP
tests/              unit, integration, acceptance
docs/               contracts and operating guides
skills/             Agent Skills shipped with Span
integrations/       host adapters and lifecycle hooks
scripts/            installer shim, build identity, maintenance checks
```

Allowed imports follow the same order: `core` imports stdlib value modules only;
`ports` holds typed interfaces; `service` coordinates ports and core but owns no
semantic rules; `shell` owns every effect, including MCP transport and persistence.

## Request path

```text
MCP tool call
  → shell/mcp.py          parse once into a canonical request
  → service/operations/*  pick the operation and its bounds
  → core/*                validate, reconcile, decide freshness
  → ports/*               store, structural source, evidence
  → shell/*               read/write, transport
  → SemanticAnswer
```

Two outcomes are possible for an operation that needs interpretation:

- a typed `SemanticAnswer` when current understanding already exists;
- a `PendingInterpretation` carrying a continuation and a bounded task. The agent
  investigates and calls `submit_interpretation`; Span validates the submission
  and either answers or returns the next pending unit.

## Where changes belong

| Change | Location |
| --- | --- |
| A semantic rule, validation, freshness decision | `src/span/core/` |
| A new boundary or capability behind an interface | `src/span/ports/` |
| Operation sequencing, bounds, request composition | `src/span/service/` |
| Git, filesystem, SQLite, structural provider, MCP wire | `src/span/shell/` |
| A public contract or its explanation | `docs/` and the matching tests |
| Host setup or lifecycle hooks | `integrations/`, `skills/`, `src/span/shell/install.py` |

## Reading order

1. [README](../README.md) — what it is and how to install it.
2. This page — the map.
3. [Architecture](architecture.md) — functional core, isolated shell, ownership.
4. [Lifecycle](lifecycle.md) — how Span fits into agent work.
5. [Taxonomy](taxonomy.md) — subjects, claims, relationships.
6. [Agent interpretation exchange](interpretation.md) — suspension and submission.
7. [MCP reference](mcp.md) — the eleven operations and wire shapes.
8. [Glossary](glossary.md) — terms used across the docs.

## Running the tests

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test,dev]'
pytest
```

The installed-MCP acceptance lane also needs `uv`, Node, and npm. Lint and format
gates are `ruff check .` and `black --check .`.
