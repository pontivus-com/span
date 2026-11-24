# Structural evidence and demand-driven understanding

Span uses structural indexing to help agents **navigate software**, not to decide
what the software means.

That distinction matters for contributors because structural evidence and
semantic understanding have different owners:

- the structural provider can report symbols, files, locations, and
  relationships; and
- the coding agent investigates meaning and records supported conclusions.

## What structural evidence is for

Structural evidence helps answer navigation questions such as:

- where is this symbol defined?
- which files import or reference it?
- which components are structurally connected?
- what symbols exist in this file?
- what part of the repository should the agent inspect next?

Those observations can make an investigation faster and more focused.

They do not by themselves establish:

- ownership;
- product intent;
- policy;
- governing authority;
- a semantic subsystem boundary; or
- completeness of an explanation.

A current structural graph is therefore useful evidence for investigation, not a
semantic answer.

## When the structural index is built

The installer provisions the pinned structural provider.

Explicit installation/setup may run its bounded currency operation when the
provider cache is missing, stale, or the target working tree is dirty.

Provider artifacts stay in Span's external data directory.

Ordinary runtime operations do not rebuild the index:

- MCP startup registers repository identity without building structure;
- `ask` does not rebuild it;
- `record` does not rebuild it;
- `reconsider` does not rebuild it;
- hooks do not rebuild it; and
- `span-install --verify-only` observes readiness without provisioning.

There is no separate public refresh operation.

See [Install and connect](install.md) for the current setup path.

## Semantic understanding follows real work

Span does not precompute semantic explanations for every structural node.

A normal task starts from the software surface the agent is actually working on.
Span returns maintained knowledge when available or an explicit gap when the
knowledge still needs to be established.

The agent can then use structural navigation, ordinary source search, exact
source evidence, tests, and project guidance as the task requires.

When that work establishes useful understanding, it is captured through the
normal lifecycle.

This demand-driven model avoids turning a structural index into an automatically
generated documentation corpus.

## Governance is not structural inference

The Functional Pyramid is based on explicit project-owned declarations.

Structural layout, filename similarity, search relevance, or graph adjacency do
not create Functional Contexts, Functional Rules, authority owners, or
applicability.

The reverse is also true: a repository participating in the Functional Pyramid
does not make its structural provider an authority source.

Structural evidence answers **where and how things are connected**.
Declared governance answers **what guidance applies**.

Those roles remain separate.

## Content change and membership change are different

Some conclusions depend on exact source content. Others depend on which members
exist inside a declared discovery boundary.

Span tracks those as different support relationships:

- **content change** asks whether recorded source content changed; and
- **membership change** asks whether the members of an observed boundary
  changed.

A truncated inventory cannot establish complete membership and is not promoted
into one.

This distinction lets change affect the conclusions that actually declared the
relevant dependency instead of making every retained conclusion stale.

See [Support currency and reassessment](freshness.md).

## Contributor boundaries

The typed structural capability is documented in [Port contracts](ports.md).
Exact public evidence admission/retrieval belongs to the
[MCP reference](mcp.md).

Provider caches have their own installation/purge lifecycle. Retained semantic
history and receipts have separate persistence and retention rules.

When changing structural integration, preserve the architectural rule:

> **structure may support investigation; it does not author semantic or
> governing meaning.**
