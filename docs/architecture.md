# Architecture

Span keeps agent-authored understanding attached to its declared support.
The interpreting agent owns meaning; deterministic core rules validate state
transitions and classify support; the shell owns effects.

```mermaid
flowchart LR
  A[Coding agent] --> M[MCP ingress]
  M --> I[Installation runtime]
  I --> S[Repository lifecycle services]
  S --> C[Pure core rules]
  S --> P[Typed ports]
  P --> E[Filesystem and structural evidence]
  P --> D[Repository schema-14 SQLite store]
  I --> F[Installation Functional Pyramid store]
  S --> M
  M --> A
```

## Ownership

| Boundary | Responsibility |
| --- | --- |
| Target repository and its owners | Implementation, tests, contracts, declared governance. |
| Coding agent | Investigation, interpretation, applicability, edits, external verification. |
| `core/model` and `core/schema` | Canonical immutable carriers, strict parsing, reference-only recording wire. |
| `core/identity.py`, `core/recording.py` | Digests, receipt replay decisions, validated version/challenge transitions. |
| `core/support_rules.py` | Pure support aggregation; Functional Pyramid graph/route rules remain pure core behavior. |
| `ports/` | Typed evidence, structural, lifecycle-store, authority, declaration and repository-qualified Functional Pyramid boundaries. |
| `service/` | Semantic composition: evidence/recording/qualification plus Functional Pyramid orientation and the single shared cross-repository effect engine. |
| `shell/` | Filesystem, clocks, git, structural provider, repository/installation SQLite transactions, installation, MCP transport. |

The functional core imports no filesystem, database, MCP SDK, network, or
model provider. Services call core rules; adapters do not duplicate semantic
decisions. One canonical typed carrier crosses each internal boundary.
Wire projection resolves references once into that contract; it does not
introduce a second domain representation or compatibility writer.

## Version-1 composition boundary

A raw repository runtime contains only repository identity/root, its lifecycle
store and exact evidence/structural capabilities. The installation runtime owns
the registered-repository resolver, installation Functional Pyramid store,
declaration and repository-qualified authority/evidence access, one
Functional Pyramid service, and the factory that composes repository
`ServiceContext` instances.

Production semantic services receive these installation capabilities
mandatorily. There is no reduced repository-local support/effect mode and no
shell-side Functional-Pyramid semantic coordinator. Ordinary changed-scope
`reconsider` and participation writes use the same service-owned,
repository-qualified dependency-effect engine.

## Request and persistence path

Strict MCP ingress parses a canonical request. The service reads typed state
and evidence, calls core rules, and invokes the owning persistence operation.
The SQLite shell commits semantic transitions and receipts atomically.
MCP serializes the result as text and structured content from one result.

Questions and evidence admission may persist recoverable operational contexts
and immutable observations. They do not author conclusions. Recording writes
understanding versions, conclusion revisions, explicit challenges, and
independent verification runs. Ordinary startup and navigation do not build
structural state; explicit setup owns provider currency work.

## Shared state and recovery

Repository schema 14 holds repository contexts, semantic/audit history and
ordinary receipts across process/session restarts. Functional Pyramid
participation, versions, exclusions and installation receipts live in the
separate installation store. The reasoning caller preserves its request identity before
dispatch. Matching receipt replay precedes new-write checks, including checks
that could fail after context expiry or source changes. Compare-and-set
versions and challenge revisions reject conflicting concurrent updates.
SQLite transactions serialize the actual commits.

The store owns recoverable operational context and semantic history. Earlier stores use a separately invoked offline
archive/export/stage/activate protocol; startup never migrates them.

## Currency and limits

Support is checked from declared source observations, authority declarations,
exact premise revisions, recorded discovery membership, and Functional Pyramid
route support. Changed support
requires agent reassessment; deterministic rules do not rewrite the meaning.
Challenges and gaps remain separate from support currency. A current snapshot
may be incomplete or disputed.

Hooks deliver reminders; lifecycle operations evaluate currentness. Skills guide the
agent and have no runtime semantic authority. See [lifecycle](lifecycle.md),
[ports](ports.md), and [MCP reference](mcp.md).
