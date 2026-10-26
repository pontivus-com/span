# Architecture

## Functional Core / Isolated Shell

```
ISOLATED SHELL (filesystem / git / structural provider / agent task
                framing / SQLite / MCP / configuration / process env)
        strict typed ingress
CANONICAL TYPED BOUNDARY
FUNCTIONAL CORE (identity, validation, authority, trust, freshness,
                 conflict, composition, impact, bounds)
        canonical typed result
CANONICAL TYPED BOUNDARY
ISOLATED SHELL (persist / retrieve / expose / invoke)
```

The core (`src/span/core/`) imports stdlib value modules only — no
filesystem, network, database, provider, or MCP imports. Effects live
in `src/span/shell/`; `src/span/ports/` holds typed interfaces only;
`src/span/service/` coordinates ports and core but owns
no semantic rules. Each responsibility is a package or module with one
owner: `bounds`, `requests`, `refs`, `answers`, `repository`,
`resolution`, `discovery`, `freshness`, `questions`, `interpretation`,
`exchange`, `establishment`, and `operations/*`. Shell adapters follow
the same rule: `install`, `mcp`, and `sqlite_store` are packages split by
responsibility; the structural providers keep their adapter size exception
while sharing cursor, repository-binding, and adjacency mechanics in
`structural/support.py`; one `evidence_source.py` owns evidence retrieval
over storage seams.

## Separation of concerns (exclusive ownership)

Repository shell (raw state/fingerprints) · structural source
(structural observations only) · evidence selection (relevance only,
never authority) · agent-interpretation boundary (task contract +
strict ingress/validation; no model selection, endpoints, credentials,
or provider invocation) · functional core (all semantic decisions) ·
persistence shell (canonical state only) · MCP shell (transport only).

## DRY / strict typing

One canonical typed carrier per semantic boundary, one writer per
decision, no parallel shapes, no DTO/mapping layers, no compatibility
shims, no fallback parsing. External input parses once at ingress
into canonical contracts. `Any`, untyped semantic dicts, dual-key
aliases, and legacy fallbacks are forbidden inside semantic logic.

---

## Responsibility boundaries

Span is implemented as a standalone semantic repository-intelligence system with a functional core and isolated effects.

At a high level:

```text
repository
   +
structural evidence
   +
governing sources
        ↓
bounded evidence selection
        ↓
agent interpretation task
        ↓
coding agent investigates
        ↓
typed semantic submission
        ↓
validation + reconciliation
        ↓
persistent semantic state
        ↓
freshness / premise checks
        ↓
future agent retrieval
```

Responsibilities remain deliberately separated.

### The target repository owns

- implementation;
- tests;
- contracts;
- configuration;
- governing documentation;
- authority.

### The coding agent owns

- semantic investigation;
- model reasoning;
- implementation work;
- external verification.

### Span owns

- canonical semantic contracts;
- bounded task exchange;
- validation;
- persistence;
- relationships;
- semantic dependencies;
- evidence references;
- authority bindings;
- freshness;
- reconciliation;
- query responses;
- MCP exposure.

Span does not become another implementation or authority source.

---

## Design principles

### Current is earned, not assumed

Persisted understanding is history until its required support is known to remain current.

### Preserve uncertainty

Missing, ambiguous, conflicting, partial, stale, and unverifiable knowledge remain visible.

### Evidence is not authority

Finding a source does not make it governing.

### Authority is not inference

Span does not create project authority because an AI interpretation sounds plausible.

### Concurrency and shared state

The semantic store is the shared durable medium; continuations are not shared.

- Several processes may read one repository store. SQLite serializes writes; a
  second writer waits for the single writer lock (`busy_timeout`) and fails
  rather than corrupting state. One logical writer per repository is the
  supported pattern.
- Each process owns a private continuation store. A continuation is single-use,
  process-local, and expires; a second session cannot resume it and re-runs the
  originating operation, which is idempotent by contract.
- Campaign handles (`TargetId`) are durable and repository-scoped, so a second
  session can read campaign progress through `status`.
- Page cursors are stateless and restart-safe; they carry no process state.

### Structural facts are evidence

A call graph or symbol index can support reasoning without being semantic truth.
Every structural page carries its coverage, so changed or unverifiable
structure is presented as qualified evidence rather than current fact.

### Invalidate narrowly

Relevant changes should affect dependent understanding, not unrelated knowledge.

### Reassess instead of pretending to repair

Stale semantics require interpretation.

They are not deterministically patched from changed filenames or call edges.

### Reading does not write

A query does not silently manufacture durable semantic knowledge.

### History remains history

Corrections and supersession do not erase the fact that earlier understanding existed.

### The agent does the thinking

Span deliberately owns no LLM provider, prompt execution service, or autonomous semantic-maintenance process.

---
