# Architecture (plan §3, §14, §17)

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
`src/span/service_operations.py` coordinates ports and core but owns
no semantic rules.

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
