<h1 align="center">
  <img src="https://raw.githubusercontent.com/pontivus-com/span/master/assets/span-logo-plate-dark.png" alt="Span" width="360">
</h1>

<p align="center">
  <strong>Build a knowledge factory for your codebase.</strong>
</p>

<p align="center">
  Span gives coding agents a maintained software-knowledge layer: what is already
  understood about the code, what project guidance applies to it, and what needs
  another look after either one changes.
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
  <a href="#context-is-temporary-knowledge-should-compound"><strong>Why Span</strong></a> ·
  <a href="#how-the-loop-works"><strong>How it works</strong></a> ·
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="https://github.com/pontivus-com/span/tree/master/docs"><strong>Docs</strong></a>
</p>

## Context is temporary. Knowledge should compound

Coding agents are good at gathering context for the task in front of them:
source, tests, configuration, documentation, and the current conversation. The
problem is what happens after the task ends. Useful understanding is often lost,
so the next agent starts again from raw context and reconstructs the same
knowledge.

The emerging **knowledge factory** model separates those two things. Context is
what an agent has for a task. Knowledge is reusable understanding that is
collected, curated, and maintained so it can improve future work. LangChain
describes this as a loop in which agents surface what is missing or wrong while
a separate curation process maintains reusable knowledge for later agents.

Span applies that model specifically to software engineering.

A working coding agent can capture what it establishes about an exact file,
symbol, service, or domain while the evidence is fresh. A separate reviewer can
curate a stable revision for shared reuse. Later agents can start from that
maintained knowledge instead of rebuilding it from scratch.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

Span does not include a background curator model. Curation may be done by
another agent session, a dedicated workflow, or a human. Span provides the
software-specific knowledge layer and the deterministic lifecycle around it.

## Why software knowledge needs its own lifecycle

Software knowledge has an additional problem: the thing being understood keeps
changing.

An explanation of a subsystem can stop being reliable after a source change.
And code can remain unchanged while the requirements, contracts, or design that
govern it change.

Span therefore maintains two distinct parts of the working context:

- **what the implementation is understood to do**, supported by the source,
  tests, configuration, executions, or other evidence used to establish it; and
- **what is supposed to guide it**, through the applicable goals, principles,
  contracts, functional design, and technical design declared by the project.

Span keeps those relationships explicit. It does not turn a recorded
interpretation into truth, and it does not invent authority from repository
structure or document prominence.

The result is a software knowledge factory that can answer three practical
questions when an agent starts work:

1. **What do we already know about this part of the system?**
2. **What project guidance applies to it?**
3. **What needs to be reconsidered because something changed?**

## How the loop works

### 1. Start from maintained knowledge

Ask about the exact part of the system you are working on. Span returns reusable
knowledge for that surface when it is eligible for shared reuse and its recorded
support still holds.

For repositories that participate in the Functional Pyramid, the same working
context can also include the applicable path through the project's governing
documents.

### 2. Investigate normally and capture what you establish

The coding agent still reads source, searches, edits, runs tests, and makes the
engineering judgment.

When that work establishes useful understanding, Span can retain the conclusion
with the evidence that supported it. Capture happens close to the work, while
the reasoning and evidence are still available.

### 3. Curate stable knowledge for reuse

Captured knowledge is not automatically promoted to shared knowledge.

A separate reviewer evaluates the exact captured revision and decides whether it
is suitable for future reuse. Curation records that decision; it does not claim
that Span has independently proved the interpretation semantically true.

### 4. Reconsider only what change affected

When implementation or governing guidance changes, Span identifies the retained
understanding that depends on it.

The agent revisits that affected knowledge while unrelated knowledge remains
reusable. If the meaning changes, the new revision returns through capture and
review before it becomes shared knowledge again.

That closes the loop: **doing the work creates better knowledge for the next
piece of work, while change keeps that knowledge accountable to reality.**

## Three tools, one lifecycle

Span runs locally as an MCP server beside the coding agent. Its public surface
has exactly three operations:

- **`ask`** — start from what Span already knows about the software surface you
  are working on;
- **`record`** — retain supported understanding and perform the explicit
  lifecycle actions that qualify it for reuse; and
- **`reconsider`** — after change, identify and re-establish the understanding
  that may no longer hold.

The exact request and result grammar lives in the
[MCP reference](docs/mcp.md). The user workflow is explained in
[Using Span](docs/usage.md).

## Functional Pyramid: know what governs the code

Reusable implementation knowledge is only half of the problem. Agents also need
to know which project decisions are supposed to govern the code they are
changing.

For participating repositories, Span's **Functional Pyramid** resolves the
declared path from project goals and principles through contracts, functional
design, and technical design to the software surface being worked on.

The original project documents remain canonical. Span maintains their declared
identity, applicability, relationships, and change effects so the agent does not
have to infer authority from filenames, search results, or repository layout.

This lets the same task context answer both:

- **what this software is understood to do**; and
- **what it is supposed to follow**.

See the [documentation index](docs/README.md) for the concepts and binding
authority behind that model.

## What Span does not replace

Span is deliberately narrow. It does not replace your coding agent, choose a
model, edit the target repository, or run tests on the agent's behalf. The agent
continues to own engineering reasoning and semantic judgment.

Span maintains the reusable result of that work: captured software
understanding, its support and history, curation state, declared governing
relationships, and the consequences of change.

## Quick start

The currently verified installation path is Linux with Python 3.12+, Node.js,
and npm.

From a source checkout:

```bash
python3 scripts/install-span.py --repo /path/to/your/repo
span-install --verify-only
```

For a published package release, install `span-mcp` with your Python package
manager and run:

```bash
span-install --repo /path/to/your/repo
```

Reconnect your coding agent after installation or upgrade, then start with the
exact file, symbol, service, or domain from the engineering task in front of
you. See [Install and connect](docs/install.md) for host configuration,
migration, and operator detail, and [First investigation](docs/onboarding-runbook.md)
for the first end-to-end workflow.

## Beta 3 status

This branch is the **Version 1 Beta-3 execution candidate**. Repository,
installer, Functional Pyramid, capture/curation, and installed stdio MCP
verification are recorded in [acceptance](docs/acceptance.md).

Live model-host delivery for the Version-1 candidate remains **UNVERIFIED** and
is not inferred from successful registration or hook configuration. Publication
is a separate release-owner decision; a green candidate does not authorize a
release.

For exact host status and operational limits, see
[host integration](integrations/hosts/triggers.md).

## Documentation

Use the [documentation index](docs/README.md) as the single entry point. It
separates:

- user guidance;
- concepts;
- operator and protocol reference;
- contributor/developer reference;
- binding product authority;
- verification evidence; and
- programme history.

The [Beta-3 implementation plan](docs/implementation-plans/1.0.0-beta3.md) is a
programme record, not user documentation.

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
