<h1 align="center">
  <img src="https://raw.githubusercontent.com/pontivus-com/span/master/assets/span-logo-plate-dark.png" alt="Span" width="360">
</h1>

<p align="center">
  <strong>Give your coding agent the complete context for the code it is working on.</strong>
</p>

<p align="center">
  Span is a local MCP server that gives coding agents both sides of the context
  for the exact file, symbol, service, or domain they are working on: what that
  part of the system is understood to do, and the goals, rules, contracts, and
  design documents that guide it.
</p>

<p align="center">
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-server-111B21?style=flat-square" alt="MCP server"></a>
  <a href="https://github.com/pontivus-com/span/actions/workflows/ci.yml"><img src="https://github.com/pontivus-com/span/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/pontivus-com/span/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-Linux%20verified-lightgrey?style=flat-square" alt="Linux verified">
  <img src="https://img.shields.io/badge/status-beta-orange?style=flat-square" alt="Beta">
  <a href="https://github.com/pontivus-com/span/stargazers"><img src="https://img.shields.io/github/stars/pontivus-com/span?style=flat-square" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="#what-span-changes"><strong>Why Span</strong></a> ·
  <a href="#how-it-works"><strong>How it works</strong></a> ·
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="https://github.com/pontivus-com/span/tree/master/docs"><strong>Docs</strong></a>
</p>

## A coding agent needs more than the code

To work safely on part of a software system, an agent needs two kinds of context
at the same time.

It needs to know **what this part of the system does**: the useful understanding
already established about the implementation, how it fits together, what that
understanding was based on, and whether it is still current.

It also needs to know **what guides this part of the system**: the relevant
goals, principles, contracts, functional design, and technical design, in the
right order and linked back to the canonical documents that own them.

Without Span, a fresh agent has to reconstruct both sides. It re-reads code,
searches old conversations and documentation, works out which documents apply,
and decides which guidance takes priority. The relevant material may span
several repositories.

Span gives the agent both sides for the exact software surface it is working on.

## What Span changes

### Start with the complete working context

Ask about a file, symbol, service, or domain. Span returns the current
understanding already established for that surface and, for a participating
repository, the complete applicable path through the project's guiding
documentation.

The agent starts knowing what it is looking at, why it exists, what is already
known about it, and which project rules and designs apply.

### Follow the right guidance from first principles to implementation

Span links the exact software scope to the goals and first principles above it,
then through the applicable rules and contracts to functional and technical
design.

The canonical documents stay where their owners put them. Span keeps their
identity, relationship, applicability, and order explicit, so the agent does not
have to guess from filenames, search results, repository layout, or document
prominence.

### Reuse what is already known about the implementation

When an agent establishes a useful conclusion about the code, Span can retain it
with the evidence that supported it. A later session can find that understanding
from the software surface itself; it does not need the original conversation or
a saved internal ID.

If the support no longer holds, Span does not silently return the old conclusion
as current.

### Recheck only what a change affected

A code change can invalidate what an agent understood about the implementation.
A change to a goal, contract, design, or its applicability can invalidate what
the implementation is supposed to satisfy even when the code itself did not
change.

Span identifies the affected understanding and why it needs another look.
Unrelated understanding stays reusable.

## Keep using the coding agent you already have

Span does not replace your coding agent, choose a model, edit source, or run your
tests. It runs locally as an MCP server beside the agent.

The agent still does the engineering judgment. Span maintains the reusable
result of that work: semantic conclusions, their exact support, version history,
declared governance, and the consequences of change.

Three public tools cover the lifecycle:

- **`ask`** — start from the current understanding and, where declared, the
  governance that applies to the same scope.
- **`record`** — retain a conclusion once the agent has established it, with the
  support it actually used.
- **`reconsider`** — after a change, identify what really needs reassessment and
  carry that work forward without losing history.

## How it works

1. **Ask for the exact part of the system you are working on.** Span returns
   the current retained understanding for that surface and, when the repository
   participates in the Functional Pyramid, the full applicable guidance path
   from first principles down to functional and technical design.
2. **Investigate normally, then keep what you learn.** The agent reads code and
   canonical documents, searches, edits, and tests with its normal tools. When
   it establishes a useful conclusion, `record` retains it with the evidence
   and guidance it depends on.
3. **After change, revisit only what no longer holds.** `reconsider` maps
   implementation or guiding-document changes to the affected conclusions. The
   agent confirms, corrects, replaces, or withdraws only the understanding that
   actually needs work.

A later session starts at step 1 again — but it is no longer starting from zero.

## Functional Pyramid: the path from first principles to the code

The Functional Pyramid is how Span provides the guiding half of the working
context.

For the exact software surface an agent is working on, it resolves the declared
path through the project's canonical goals, principles, contracts, functional
design, and technical design. It shows which guidance applies, how the layers
relate, where the canonical documents live, and which higher-level rules govern
the lower-level design.

Span does not copy those documents or invent missing authority. The original
documents remain canonical. Span keeps the links, applicability, derivation, and
change consequences explicit, including when the path crosses repositories.

The same `ask` that orients the agent on a software surface can therefore show
both:

- **what this part of the system is understood to do**, with its evidence and
  current status; and
- **what is supposed to guide it**, from first principles down to the applicable
  functional and technical design.

If part of that guiding path is missing, conflicted, unavailable, or outside the
declared scope, Span says so instead of guessing.

## What “current” means

Span does not claim that a saved explanation is true merely because it was
recorded. It tells the agent whether the support that explanation depends on
still holds.

| Qualification | What it means |
| --- | --- |
| `CURRENT` | The declared support still passes its checks. The agent still owns semantic judgment. |
| `REASSESSMENT_REQUIRED` | Source, authority, premise, membership, or governance applicability changed. Revisit the affected explanation. |
| `UNVERIFIABLE` | Required support cannot currently be established. The limitation stays explicit. |

Gaps and disputes remain visible independently of support currency. A passing
test does not settle a disagreement, and matching source bytes do not make an
interpretation authoritative.

## See the lifecycle

Illustrative sequence; the installed schemas and
[MCP reference](docs/mcp.md) own the exact wire grammar.

```text
fresh session
ask(surface)
  → current understanding, or an actionable gap
  → declared governing view for the same scope when Functional Pyramid is ACTIVE

agent investigates with its normal coding tools

record(kind="understanding", conclusion, support)
  → retained version + current qualification

later, implementation or governance changes

reconsider(changed_paths)
  → affected conclusions only, with the reason and re-establishment context

agent investigates the changed support and records the disposition
  → history preserved; unaffected understanding remains reusable
```

Pure reuse starts from the surface; no previous conversation or saved ID is
required. Exact historical snapshots and receipts remain available when audit or
replay detail is needed.


## Quick start

The verified installation path is Linux with Python 3.12+, Node.js, and npm.
From a checkout containing the current candidate:

```bash
python3 scripts/install-span.py --repo /path/to/your/repo
```

For a published package release, install `span-mcp` with your Python package
manager and run `span-install --repo /path/to/your/repo`. See
[install and connect](docs/install.md) for registration, verification, and the
offline store transition.

The installer provisions the managed structural indexer, runtime, skills, and
host integration. With the default global OpenCode scope, it registers the
Span lifecycle plugin and MCP server in the same global OpenCode configuration.
Repeat installs use the receipt's absolute MCP path unless
`--opencode-config` explicitly relocates it.
Reconnect your coding agent after upgrade so it receives the new tools and
instructions. Verify operational setup with:

```bash
span-install --verify-only
```

Setup creates no understanding. Begin with the relevant surface from your actual task;
see [using Span](docs/usage.md).

## Beta host status

The Version-1 `1.0.0b1` candidate is verified through the built distribution,
non-editable installed stdio MCP lane, generic Functional Pyramid acceptance,
transition/recovery gates and release-registry validation. Live model-host
delivery is **UNVERIFIED** and is not inferred from registration or historical
captures. No verified managed-host delivery claim is made for Beta 1.

| Host | Version-1 candidate status |
| --- | --- |
| Codex | Managed integration target retained; Version-1 live model-delivery **UNVERIFIED** and not claimed as verified. |
| OpenCode | Managed integration and packaged notice delivery verified; Version-1 live model-delivery **UNVERIFIED** and not claimed as verified. |
| Claude Code | Managed registration/health support retained; authenticated Version-1 model-delivery **UNVERIFIED** and not claimed as verified. |
| Other MCP hosts | Manual stdio connection remains available; host-specific delivery is **UNVERIFIED**. |

Registration, hook configuration, and model-delivered behavior are distinct.
Hooks provide lifecycle reminders; retrieval, governance orientation and support
qualification do not depend on hook delivery. See
[host integration](integrations/hosts/triggers.md).

## Fits around your agent

Span runs locally over stdio and keeps state outside target repositories. Your
agent uses its own model, tools, edits, and test runner. Span does not invoke a
model or store provider credentials. Structural search helps investigation;
recorded conclusions retain the agent's interpretation and declared support.

The intended benefit is complete working context for the exact software surface:
what is already understood about the implementation, the canonical project
guidance that applies to it, and a focused view of what needs another look after
either side changes. Recording and host delivery still have costs, and the
Version-1 same-task-class G5/F8 measurement is not yet complete. This beta
therefore makes no universal time/token-saving or comparative product-fitness
ACCEPT claim. See [acceptance](docs/acceptance.md).

## Status and documentation

This checkout is the **Version 1 Beta candidate line**. The implemented storage
contract is repository schema 14 plus the separate installation Functional
Pyramid store. Existing schema-13 repositories use the explicit offline
transition; registration alone leaves them `UNCONFIGURED` until participation is
declared. The public operations remain exactly `ask`, `record`, and `reconsider`.

T11 private first-adopter acceptance is closed and T12 release assembly is
complete. The repository-verifiable T13 gates have passed for `1.0.0b1`.
Publication remains gated on the Version-1 G5/F8 same-task-class comparative
measurement and its final evidence append. See
[the Version-1 plan](docs/implementation-plans/1.0.0-beta.md),
[acceptance](docs/acceptance.md), and [backup and recovery](docs/recovery.md).

- [Install and connect](docs/install.md)
- [Using Span](docs/usage.md) and [first investigation](docs/onboarding-runbook.md)
- [Agent lifecycle](docs/lifecycle.md) and [MCP reference](docs/mcp.md)
- [Support and reassessment](docs/freshness.md)
- [Evidence and authority](docs/authority-trust.md)
- [Scope and boundaries](docs/scope.md) and [FAQ](docs/faq.md)
- [Architecture](docs/architecture.md), [repository overview](docs/overview.md), and [all docs](docs/README.md)
- [Changelog](CHANGELOG.md)

## Contributing

See [contributing](CONTRIBUTING.md). Preserve the central contract: useful
understanding stays attached to its support, noncurrent or uncertain state
stays explicit, and corrections preserve history. Security reports go through
[SECURITY.md](SECURITY.md); support expectations are in [SUPPORT.md](SUPPORT.md).

## Registry

Official MCP Registry entry: `io.github.pontivus-com/span`

mcp-name: io.github.pontivus-com/span

## License

Span is licensed under **Apache License 2.0** (`Apache-2.0`). See [LICENSE](LICENSE).
