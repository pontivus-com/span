<h1 align="center">
  <img src="https://raw.githubusercontent.com/pontivus-com/span/master/assets/span-logo-plate-dark.png" alt="Span" width="360">
</h1>

<p align="center">
  <strong>Build a knowledge factory for your codebase.</strong>
</p>

<p align="center">
  Span is the evidence-backed software knowledge layer for coding agents, not
  the entire organizational knowledge-factory topology. Working agents capture
  what they establish while the evidence is fresh; a separate curation step
  decides what becomes shared reusable knowledge. Span keeps that knowledge tied
  to the evidence and governing guidance it depends on and shows what needs
  another look when either changes.
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

## Context is temporary. Knowledge should compound

A coding agent needs context for the task in front of it: source, tests,
configuration, design, requirements, and the current conversation. But useful
understanding established while doing the work should not disappear with the
session.

Span turns that work into maintained software knowledge without equating one
task agent's conclusion with shared truth. The working agent retains what it
established about an exact file, symbol, service, or domain with the support it
actually used. A separate reviewer/curator accepts the exact stable revision for
shared reuse; later sessions receive it only while that support still holds.

LangChain's [knowledge-factory article](https://www.langchain.com/blog/knowledge-factory)
describes task agents surfacing knowledge gaps and a curator agent running in
the background to maintain a broader organizational knowledge store. Span uses
the same important separation between task-time work and curation, but at a
narrower software boundary: working agents capture evidence-near semantic
conclusions, reviewers explicitly curate exact revisions, and deterministic
support/currentness plus declared governance remain server-owned. Span does not
run a background curator, claim semantic correctness, or claim that a separate
reviewer/curator role is unnecessary.

Software makes this harder than ordinary memory. The thing being understood
keeps changing. A source edit can invalidate an explanation. A change to a
goal, contract, design, or its applicability can invalidate what the
implementation is supposed to satisfy even when the code itself did not change.

Span therefore keeps two kinds of software knowledge distinct:

- **what the implementation is understood to do** — useful empirical
  understanding tied to source, tests, configuration, executions, premises,
  and other declared support; and
- **what is supposed to guide it** — applicable goals, principles, contracts,
  functional design, and technical design linked back to their canonical
  owners.

Span does not confuse evidence with authority, and it does not silently serve
noncurrent or uncurated understanding as shared knowledge. Together, these
capabilities provide the maintained software-knowledge layer of a software
knowledge factory: real engineering work can leave future agents better informed
without treating one task agent's conclusion as shared truth.

## What Span changes

### Start with maintained knowledge, not a blank session

Ask about a file, symbol, service, or domain. Span returns the current curated
understanding eligible for shared reuse on that surface and, for a participating
repository, the complete applicable path through the project's guiding
documentation. Current captured-but-uncurated understanding remains explicit
pending knowledge rather than ordinary Answer content.

The agent starts from maintained knowledge rather than reconstructing the same
understanding from raw evidence every session. That maintained knowledge becomes
part of the working context for the task in front of it.

### Follow the right guidance from first principles to implementation

Span links the exact software scope to the goals and first principles above it,
then through the applicable rules and contracts to functional and technical
design.

The canonical documents stay where their owners put them. Span keeps their
identity, relationship, applicability, and order explicit, so the agent does not
have to guess from filenames, search results, repository layout, or document
prominence.

### Reuse what is already known about the implementation

When an agent establishes a useful conclusion about the code, Span retains that
capture with the evidence that supported it. A separate reviewer can then curate
the exact stable revision for shared reuse. A later session can find curated
knowledge from the software surface itself without the original conversation or
a saved internal ID.

If the support no longer holds—or the revision has not yet been curated—Span
does not silently return it as shared current knowledge.

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

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

The agent still does the engineering judgment. Span maintains the reusable
result of that work: semantic conclusions, their exact support, version history,
declared governance, and the consequences of change.

Three public tools cover the lifecycle:

- **`ask`** — start from current curated shared knowledge, pending/stale status,
  and, where declared, the governance that applies to the same scope.
- **`record`** — capture supported conclusions and, in a separate reviewer act,
  curate exact stable revisions for shared reuse.
- **`reconsider`** — after a change, identify what really needs reassessment and
  carry that work forward without losing history.

## How it works

1. **Ask for the exact part of the system you are working on.** Span returns
   current curated shared knowledge for that surface, pending/stale status, and,
   when the repository participates in the Functional Pyramid, the applicable
   guidance path from first principles down to functional and technical design.
2. **Investigate normally, then capture what you establish.** The working agent
   reads code and canonical documents, searches, edits, and tests with its normal
   tools. When it establishes a supported conclusion, `record` retains that
   exact revision as captured knowledge.
3. **Curate stable captures for shared reuse.** A separate reviewer—another
   agent session, a dedicated curator workflow, or a human—reviews the exact
   capture and uses the same `record` lifecycle to curate it only when it is
   suitable for future shared reuse.
4. **After change, revisit only what no longer holds.** `reconsider` maps
   implementation or guiding-document changes to affected conclusions. The
   agent confirms, corrects, replaces, or withdraws only the understanding that
   actually needs work; semantic changes return to captured state and require
   curation again.

A later session starts at step 1 with reusable knowledge that is both curated
and still supported.

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
  → retained CAPTURED revision + current support qualification

ask(PendingCurationSelector)
  → exact CURRENT captures awaiting review

reviewer record(actions.curate)
  → exact revision becomes CURATED
  → ordinary shared Answer content requires CURRENT + CURATED

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

## Beta 3 host status

The Beta-3 execution candidate carries the verified Version-1 semantic/runtime,
non-editable installed stdio MCP, FA-01–FA-64, installer, Functional Pyramid and
capture/curation production-topology baseline. Beta 3 additionally closes
strict canonical authority ingress and the release-authorization boundary.
Live model-host delivery remains
**UNVERIFIED** and is not inferred from registration, configured hooks, or
historical captures.

| Host | Beta-3 candidate status |
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

The intended benefit is maintained software knowledge that can become complete
working context for the exact software surface: what is already understood about
the implementation, the canonical project guidance that applies to it, and a
focused view of what needs another look after either side changes. Beta product value is validated through real-world adopter
use rather than a synthetic pre-release score. This release therefore makes no
universal time/token-saving claim; follow-up Beta patches will address defects
and friction found in normal use. See [acceptance](docs/acceptance.md).

## Status and documentation

This checkout is the **Version 1 Beta-3 execution line**. The implemented
repository storage contract is schema 15 plus the separate installation
Functional Pyramid store at installation schema 1. Existing schema-7–14
repositories use the explicit offline transition; registration alone leaves
them `UNCONFIGURED` until participation is declared. The public operations
remain exactly `ask`, `record`, and `reconsider`.

Beta-3 repository, installer, Functional Pyramid, capture/curation and installed
production-topology acceptance are green at their recorded gates. Publication is
a separate owner decision: merging or pushing does not publish, and no release
workflow may be dispatched without explicit release authorization. See
[the Beta-3 implementation plan](docs/implementation-plans/1.0.0-beta3.md),
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
