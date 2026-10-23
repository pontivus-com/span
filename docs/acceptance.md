# Fixtures and acceptance

Span's acceptance model is behavioural. Every case is judged on correctness,
sufficiency, evidence integrity, uncertainty integrity, freshness integrity,
boundedness, and reuse integrity. Fixtures are generic and synthetic; no
proprietary material is required.

## Case classes

- **A — identity and purpose.** A subject's purpose is explainable from
  evidence, not from a name.
- **B — ownership and custody.** Owners are distinguished from consumers;
  structural use is not ownership; a retired owner owns nothing live.
- **C — boundary and representation.** One canonical representation; no
  duplicate carriers, fallback writes, or shadow contracts.
- **D — authority conflict.** Observed behaviour and declared authority are
  separate; declared precedence is used, never invented.
- **E — verification.** Candidate evidence and current pass/fail are
  distinguished; nothing is presented as passed without an executed record.
- **F — lifecycle.** State is created, used, terminal, failed, abandoned,
  replayed, and reaped; persistence points are explicit.
- **G — non-local impact.** Structural possibility is separated from
  established impact; change kind and affected assertions are typed.
- **H — ambiguity.** Multiple candidates stay visible; no arbitrary pick.
- **I — missing authority.** Missing authority yields an explicit unresolved
  state and a resolver requirement.
- **J — staleness and partial refresh.** Only affected claims go stale;
  coverage dependencies are invalidated by new evidence; withdrawal keeps
  history.
- **K — portability.** A held-out repository works with the real structural
  provider; no repository-specific code.
- **L — isolation.** Build, test, and serve without private access.
- **M — publication boundary.** No proprietary artifacts; the licence gate
  passes.

The suite also exercises terminology authority (concept, surfaces, conflict,
and no invented resolution) and publication custody (terminal lifecycle,
copy-only downstream, candidate versus current verification).

## Contract paths

- Multi-unit interpretation chaining.
- Second-page retrieval with an opaque page token.
- Superseding evidence.
- Claim withdrawal with visible history.
- Documentation-only subjects.
- Empty and negative results that reopen rather than silently complete.

## Lifecycle paths

Normal:

```text
orient → impact → trace/authority → modify → status (stale)
       → refresh → status (current)
```

Hook and bootstrap:

```text
UNINITIALIZED setup notice → dedicated init → READY → HOOK_FAST session
→ explicit impact → edit → hook classifies only → explicit refresh → closure
```

Negative paths: irrelevant edits stay silent; no implicit initialization,
interpretation, rebuild, or refresh; no whole-repository crawl.

## Where the tests live

| Area | Tests |
|---|---|
| Core rules and carriers | `tests/unit/` |
| Service operations and exchange | `tests/unit/`, `tests/integration/` |
| MCP transport and installed process | `tests/integration/test_mcp_transport.py`, `tests/integration/test_installed_mcp.py` |
| End-to-end semantics | `tests/acceptance/` |
| Fixtures | `tests/fixtures/`, `docs/acceptance-evidence/` |

Run the suite from the repository root:

```bash
pytest
```

The installed-MCP lane builds a non-editable install in a temporary virtual
environment and drives the installed `span-mcp` over stdio. It needs `uv`,
Node, and npm.

## Recorded evidence

[`docs/acceptance-evidence/`](acceptance-evidence/) contains recorded runs
and the fixtures behind them. Evidence is presented as a transcript, not as a
performance claim.
