# Port contracts

Ports carry canonical domain types directly. Services compose these contracts;
shell implementations own effects. A port is not a place to introduce a second
DTO/domain shape or to relocate semantic decisions into an adapter.

Public JSON grammar belongs to [MCP reference](mcp.md); the higher-level
ownership model is in [Architecture](architecture.md).

## Lifecycle store and authority

`LifecycleStorePort` in `src/span/ports/lifecycle.py` owns repository bindings,
request-bound contexts, source/discovery observations, understanding/version
reads, conclusion history, challenges, verification runs, and receipt lookup.
Its recording operations accept canonical commands and commit the transition
with its receipt atomically. SQLite implements repository schema 15; semantic
decisions are made by core/service rules rather than by SQL or transport.

`LifecycleAuthorityResolver` resolves declared authority references. Source
selection and filenames never manufacture a binding. Both ports are required
at composition; there is no optional-manager or legacy-store fallback.

## Functional Pyramid and repository-qualified access

`src/span/ports/functional_pyramid.py` carries the typed declaration/state
capabilities used by the current installation runtime. Repository access is
qualified by repository identity; a conclusion in repository A may therefore
evaluate canonical authority/evidence owned by repository B without copying B
state into A.

The declaration port reads only exact whole-document Version-3 declaration
sources and the optional Version-2 navigation bootstrap. It does not infer source
kind, scope or membership, and it does not own validation. Source-set,
membership and graph validation is one pure core/service owner; the installer
consumes that same structural outcome rather than introducing a second validator
port.

The installation composition supplies the Functional Pyramid route evaluator,
route-impact resolver, registered-repository resolver and repository-qualified
support resolver to the semantic services that need them. Missing production
composition is an invariant/programming error, not UNCONFIGURED participation,
an empty route, or an operational support result.

The installation Functional Pyramid store is a distinct persistence owner from
`LifecycleStorePort`: repository semantic/audit state remains repository-local,
while participation/version/exclusion/install-receipt state is installation-
scoped.

## Evidence source

`EvidenceSource` in `src/span/ports/evidence.py` supplies bounded inventory,
exact reads, selection, membership listing, and fingerprints. Exact requests
carry a locator and optional ranges. Admission returns a typed outcome for
each item, preserves successful observations, and distinguishes failures
from omissions. Exact source can be admitted without structural symbols.

A source observation retains its content identity, content hash and delivered
range boundary; source bytes are not stored. Source support checks the declared range when it reliably binds, otherwise the
whole file (FD-18). A delivery slice alone does not narrow a declared dependency.
Admission binds the reference without a delivery budget; delivery budgets the
declared content, including all requested ranges, and re-reads the source to
verify the stored hash. Binding may inspect the enclosing source without
admitting it as whole-file evidence. Selection
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
