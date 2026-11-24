# Repository overview

Use this page when you are about to change Span and need to find the right
implementation area.

For the architectural reasoning behind these boundaries, read
[Architecture](architecture.md).

## Repository layout

```text
src/span/core/      canonical domain types, strict schema, pure identity/transition/support rules
src/span/ports/     typed capability boundaries
src/span/service/   lifecycle and cross-repository composition
src/span/shell/     filesystem, Git, SQLite, provider, installation, host and MCP effects

tests/              unit, integration, acceptance and installed-process coverage
docs/               user guides, concepts, reference, authority and verification material
skills/             packaged agent-side lifecycle guidance
integrations/       host adapters and delivery/reference integration material
scripts/            packaging, asset synchronization and quality/release checks
```

The repository is intentionally layered so semantic decisions do not drift into
transport, persistence, or host-specific code.

## Where a change belongs

| If the change is about… | Start in… |
| --- | --- |
| Canonical carrier/domain vocabulary | `src/span/core/model/` or `core/schema/` |
| Identity, replay, state transition, support or graph rule | `src/span/core/` |
| A capability needed by services but implemented through effects | `src/span/ports/` |
| Sequencing several capabilities into one lifecycle behavior | `src/span/service/` |
| Filesystem, SQLite, Git, structural provider, clocks, installation, host wiring or MCP transport | `src/span/shell/` |
| Public product explanation or operating guidance | `docs/` |
| Agent-delivered lifecycle procedure | `skills/` and the managed snippet |
| Host-specific integration behavior | `integrations/` and the owning shell/install code |
| Verification of an existing requirement | the test layer matching the owning behavior |

A change should not be placed downstream merely because that is where the
symptom becomes visible. Follow the root-cause ownership rules in
[AGENTS.md](../AGENTS.md).

## Follow a request through the code

A repository-scoped MCP request generally follows:

```text
MCP ingress
  → installation/repository composition
  → lifecycle service
  → typed ports + pure core rules
  → repository or installation persistence when needed
  → canonical result
  → MCP egress
```

That flow is useful when locating responsibility:

- **Ingress/egress problem?** Start at the shell transport boundary.
- **Wrong orchestration?** Start in the owning service.
- **Wrong decision?** Find the core rule that should own it.
- **Missing capability?** Add or change the typed port, then its shell adapter.
- **Persistence defect?** Fix the owning repository or installation store
  implementation without moving semantic decisions into SQL.

[Architecture](architecture.md) gives the full ownership model.

## Repository state versus installation state

Do not assume all persistence belongs to one repository database.

Repository lifecycle state is repository-local. Installation-level Functional
Pyramid participation and other cross-repository composition state are owned by
the installation runtime/store.

This distinction matters when tracing:

- governance participation;
- cross-repository support/effects;
- repository registration; and
- backup/transition behavior.

See [Architecture](architecture.md#installation-and-repository-composition) and
[Port contracts](ports.md).

## Tests

The test suite follows the same ownership structure.

At a high level:

- **unit tests** exercise pure/core rules, carriers, ports, shells, and small
  service boundaries;
- **integration tests** exercise vertical composition and transport/runtime
  interactions;
- **acceptance tests** trace public product requirements through delivered
  behavior; and
- **installed-process tests** exercise the packaged, non-editable runtime and
  integration topology.

A behavior change should be tested at the layer that owns the behavior rather
than only through a broad downstream test.

See [Contributing](contributing.md) for the current commands and release gates.

## Documentation and requirements

Public documentation is not one undifferentiated corpus.

Use the [documentation index](README.md) to identify whether a change belongs
to:

- user guidance;
- concepts;
- protocol/operator reference;
- contributor/developer reference;
- binding Functional Pyramid authority;
- verification evidence; or
- programme history.

Do not turn a guide or implementation plan into a competing requirements owner.

## Suggested contributor reading order

For a code change:

1. read the governing [AGENTS.md](../AGENTS.md);
2. identify the owning requirement/design through the
   [requirements pyramid](requirements-pyramid.md);
3. use this repository map to locate the implementation area;
4. read [Architecture](architecture.md) when the change crosses layers;
5. use [Port contracts](ports.md) when capabilities cross the core/effect
   boundary; and
6. follow [Contributing](contributing.md) for verification.

For exact public MCP behavior, use [MCP reference](mcp.md) rather than inferring
the contract from implementation layout.
