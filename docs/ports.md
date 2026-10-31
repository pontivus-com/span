# Port contracts

Ports carry canonical domain types directly. Services compose these contracts;
shell implementations own effects. Public JSON grammar belongs to
[MCP reference](mcp.md).

## Lifecycle store and authority

`LifecycleStorePort` in `src/span/ports/lifecycle.py` owns repository bindings,
request-bound contexts, source/discovery observations, understanding/version
reads, conclusion history, challenges, verification runs, and receipt lookup.
Its recording operations accept canonical commands and commit the transition
with its receipt atomically. SQLite implements schema 10; semantic decisions
are made by core rules rather than by SQL or transport.

`LifecycleAuthorityResolver` resolves declared authority references. Source
selection and filenames never manufacture a binding. Both ports are required
at composition; there is no optional-manager or legacy-store fallback.

## Evidence source

`EvidenceSource` in `src/span/ports/evidence.py` supplies bounded inventory,
exact reads, selection, membership listing, and fingerprints. Exact requests
carry a locator and optional ranges. Admission returns a typed outcome for
each item, preserves successful observations, and distinguishes failures
from omissions. Exact source can be admitted without structural symbols.

A source observation retains its content identity and delivered excerpt
boundary. Source support checks the observed content; a small excerpt does
not imply that only those lines participate in the fingerprint. Selection
finds relevant evidence and grants no authority.

## Structural source

`StructuralSource` supplies repository state, subject resolution, locations,
edges, reach, symbol search, file outlines, file verification, and explicit
provider currency. `StructuralResult[T]` preserves typed items, coverage,
limits, and version-bound page cursors. Unsupported capability and unverified
coverage are explicit; an empty page cannot prove absence by itself.

The production provider is the pinned Graft adapter; the in-memory provider
supports deterministic tests. Their shared paging helpers preserve the item
type. Closed node/edge mappings reject unknown vocabulary. Structural
adjacency is evidence for investigation, never inferred ownership or policy.

## Effect boundaries

Filesystem evidence, SQLite, provider processes, clocks, and MCP transport
belong in the shell. Repository setup may run the provider's bounded currency
operation. Ordinary queries, hooks, and recording do not select or invoke
models, edit target source, run tests, or rebuild structure automatically.
