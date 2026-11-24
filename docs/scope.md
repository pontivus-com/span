# Scope and product boundaries

Span has a deliberately narrow job:

> **maintain reusable software understanding for coding agents, keep it connected
> to the things it depends on, and identify what needs another look after
> change.**

It does not replace the coding agent, the source of project authority, or the
engineering tools used to do the work.

This page explains where that boundary sits.

## What Span owns

Span owns the lifecycle around maintained software knowledge.

That includes:

- retaining useful understanding established during engineering work;
- keeping that understanding associated with the software scope it describes;
- keeping its declared supporting evidence and history;
- separating task-time capture from review for shared reuse;
- checking whether required support still holds when knowledge is reused;
- identifying retained knowledge affected by implementation or governance
  change; and
- for participating repositories, resolving the declared project guidance that
  applies to the software scope being worked on.

The coding task determines what needs to be understood. Span maintains what that
work establishes so future work can start better informed.

## What Span does not own

Span does **not**:

- choose or run the coding model;
- replace source search, code reading, debugging, editing, or test execution;
- decide whether an agent-authored interpretation is semantically true;
- autonomously promote every task conclusion into shared knowledge;
- originate product requirements, policy, professional authority, or project
  design;
- infer authority from filenames, directory layout, search relevance, or model
  preference;
- turn installation into automatic semantic understanding of a repository; or
- crawl a repository and manufacture explanations simply because files exist.

Repository owners remain the source of governing authority. Investigators and
reviewers remain responsible for semantic judgment. Span maintains the
relationships, lifecycle, and change consequences around those decisions.

## The working scope follows the task

Span works against an explicit software surface: a **file, symbol, service, or
domain**.

That lets knowledge be retained at the level the engineering task actually
needs. A conclusion about a service may depend on several files and tests; a
file or symbol may be only one piece of the supporting evidence.

The important distinction is:

- **scope** says what the conclusion is about;
- **support** says what established it.

Span does not widen a local investigation into an automatic repository-wide
claim. If the work needs a broader scope, the agent must actually investigate
that broader scope.

This keeps a useful local conclusion from being mistaken for complete knowledge
of a larger system.

## Reuse is qualified, not automatic

Retained knowledge is useful only when it is appropriate to share and the things
it depends on still hold.

That is why Span separates:

- **capture** — keep useful understanding produced during work;
- **review/curation** — decide whether an exact revision is suitable for shared
  reuse; and
- **support currency** — determine whether its recorded dependencies still
  hold.

These qualifications do not mean Span has proved the explanation true. They
make the state of reusable knowledge explicit instead of silently treating old
or unreviewed material as trustworthy context.

See [Agent lifecycle](lifecycle.md) and
[Support currency and reassessment](freshness.md) for the deeper model.

## Project guidance is declared, not guessed

For repositories that participate in the Functional Pyramid, Span can also tell
the agent which project guidance applies to the software scope being worked on.

That governing path is explicitly declared. Span does not make a document
authoritative because it has a promising filename, appears high in a repository,
or looks semantically relevant.

The canonical project documents remain where their owners maintain them. Span
keeps their declared identity, applicability, relationships, and change effects
available to the task.

This keeps two questions separate:

- **What is this software understood to do?**
- **What is it supposed to follow?**

See [Evidence, authority, and interpretation](authority-trust.md).

## Span keeps uncertainty bounded and visible

A gap is not evidence that an entire repository is undocumented. It means the
requested understanding is not currently available for the selected scope.

Likewise, inspecting part of a service or repository does not establish that
everything outside the inspected boundary is absent or understood.

Span keeps those limits explicit rather than turning incomplete investigation
into a completeness claim.

This is also why change reassessment is dependency-focused: a relevant change
can make dependent knowledge require another look without invalidating all
retained knowledge everywhere.

See [Questions, retrieval, and bounds](queries.md) for retrieval and boundedness
details.

## Verification is evidence, not meaning

A test run, review, or other external verification can be retained as evidence
of what was observed.

That record does not automatically create or rewrite the semantic explanation
of the software. A passing test is not the same thing as an interpretation of
what the implementation means, and it does not silently settle a disagreement.

Span keeps verification and semantic understanding separate so each can retain
the scope and evidence appropriate to it.

## Operational concerns live elsewhere

Installation, host registration, storage layout, schema transitions, backups,
and recovery are necessary operational details, but they are not the product
scope model.

Use:

- [Install and connect](install.md) for setup, hosts, and upgrades;
- [Backup and recovery](recovery.md) for state protection and restore;
- [MCP reference](mcp.md) for exact protocol behavior; and
- [Acceptance and evidence](acceptance.md) for the current Beta candidate's
  verified delivery boundary.

For ordinary engineering work, start with [Using Span](usage.md).
