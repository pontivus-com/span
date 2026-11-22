<h1 align="center">
  <img src="https://raw.githubusercontent.com/pontivus-com/span/master/assets/span-logo-plate-dark.png" alt="Span" width="360">
</h1>

<p align="center">
  <strong>Stop making every coding agent rediscover your codebase.</strong>
</p>

<p align="center">
  Span is a local MCP server that lets coding agents reuse evidence-backed
  understanding of what the code does, see the declared rules that govern the
  code they are changing, and revisit only what a change actually affected.
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

## Every new session can repeat work you already paid for

A coding agent traces a request across services, reads the tests, finds the
contract, and works out why the implementation behaves the way it does. A fresh
session can end up doing the same investigation again.

The same problem exists on the other side of the code: the agent also needs to
know which goals, invariants, contracts, and designs actually apply to the thing
it is about to change. Those rules may live in another repository, and their
applicability can change even when the code itself does not.

Without a maintained link between understanding, evidence, and governance, the
choice is poor: spend time reconstructing the same context, or risk working from
an explanation or rule that is no longer applicable.

## What Span changes

### Start with established understanding, not a blank slate

The next agent can ask about the code it is working on and reuse the conclusions
previous investigations established. It does not need the old chat, a saved
understanding ID, or a separate hand-written explanation just to discover what
is already known.

Span keeps each conclusion attached to the evidence that supported it. If that
support no longer holds, the conclusion is not silently returned as current.

### Know what applies before you change the code

For repositories with declared Functional Pyramid governance, the same lookup
shows the governing path for the exact code surface: the applicable goals,
invariants, contracts, functional design, and technical design remain linked to
their canonical owners.

The agent does not have to infer authority from filenames, search relevance, or
repository layout. Span resolves what the repository has explicitly declared to
govern that scope.

### Recheck the blast radius, not the whole codebase

After code or governing authority changes, Span identifies the understanding
that actually depends on what changed. Unrelated conclusions stay current;
affected conclusions are returned with the reason they need another look.

That turns reassessment into focused work instead of another full-codebase
rediscovery pass.

## A maintained context layer for the coding agent you already use

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

1. **Ask before re-deriving.** Start with the file, symbol, service, or domain
   you are working on. Span returns current retained understanding or an honest
   gap. In an ACTIVE Functional Pyramid repository, it also returns the declared
   governing view for that same semantic scope.
2. **Investigate normally, then keep the useful result.** The agent reads code,
   searches, edits, and tests with its normal tools. When it establishes a
   conclusion, `record` stores that conclusion with its evidence and history.
   NORMATIVE conclusions also receive the applicable declared governance support
   from Span.
3. **After change, revisit only what lost support.** `reconsider` maps changed
   implementation or governance to the affected conclusions. The agent confirms,
   corrects, replaces, or withdraws only the understanding that actually needs
   work.

A later session starts at step 1 again — but it is no longer starting from zero.

## Functional Pyramid: see the rules behind the code

Code tells an agent what the implementation does. It does not, by itself, tell
the agent what the implementation is supposed to satisfy.

The Functional Pyramid connects implementation scope to the repository's
declared authority chain without copying that authority into Span. Canonical
goals, invariants, contracts, functional design, and technical design stay in
the repositories that own them. Span maintains their identities, applicability,
derivation, and change consequences.

That means an agent can see both sides of a change in one place:

- **what the code is understood to do**, with evidence and currentness; and
- **what the code is declared to satisfy**, with the governing path back to its
  canonical sources.

Governance remains explicit. A registered repository is not automatically
governed: participation is `UNCONFIGURED`, `EXCLUDED`, or `ACTIVE`, and
unresolved relationships stay unresolved rather than being guessed.

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

The intended benefit is continuity between sessions and a focused review of
changed support. Recording and host delivery have costs. Measured cost is
class-specific: repeated reuse of a covered surface breaks even at two uses on
the tested tasks, while single-use implementation is currently more expensive
than reading. This beta makes no universal time/token-saving claim or completed
comparative product-fitness ACCEPT claim. See [acceptance](docs/acceptance.md).

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
