# Frequently asked questions

## What problem does Span solve?

Coding agents often have to rediscover understanding that previous engineering
work already established. Span turns useful task-time understanding into
maintained software knowledge that later agents can reuse, while keeping that
knowledge connected to the things it depends on.

See the [project README](../README.md) for the product overview.

## Is Span a knowledge factory?

Span is the **software-engineering knowledge layer** of a knowledge-factory
workflow.

The broader knowledge-factory idea is that real work should produce reusable
knowledge that is curated and maintained for future agents. LangChain describes
that industry pattern in
[How to build a knowledge factory](https://www.langchain.com/blog/knowledge-factory).

Span specializes it for software: engineering work can produce retained
understanding, review qualifies stable knowledge for shared reuse, and changes
to code or project guidance can trigger focused reassessment.

Span does not require or include a background curator model. Review can be
performed by another agent session, a dedicated workflow, or a human.

## How is Span different from a context engine or agent memory?

A context engine helps assemble material relevant to the current task. General
agent memory may preserve facts or interactions across tasks.

Span focuses on **maintained software understanding**: what was established
about a software surface, what supports it, which project guidance applies, and
whether change means it needs another look.

These capabilities can complement each other.

## What does an agent actually do with Span?

For governed use, first resolve Functional Pyramid participation so the project
guidance is ACTIVE + VALID. Then ordinary work follows:

> **Ask before deriving → investigate normally → capture what you establish →
> review for shared reuse → reconsider after change.**

An explicitly EXCLUDED repository uses the same descriptive lifecycle without a
governing projection.

Start with [First investigation](onboarding-runbook.md), then use
[Using Span](usage.md) for normal work.

## Does installation explain my repository automatically?

No.

Installation makes Span operational for the repository. Understanding is
created through actual engineering investigation and retained from that work.

A successful install is readiness, not proof that the repository has been
understood.

## Must every file be documented first?

No.

Span follows the scope of real engineering work. A useful conclusion can be
about a file, symbol, service, or domain and may depend on several sources.

You do not need to create a parallel documentation project before Span becomes
useful.

## What is the Functional Pyramid?

It is Span's mechanism for answering:

> **What project guidance is supposed to govern this code?**

For participating repositories, Span can connect the software scope being worked
on to explicitly declared goals, principles, contracts, functional design, and
technical design.

The original documents remain canonical. Span maintains their declared
relationships and applicability rather than guessing authority from filenames or
search relevance.

See [Evidence, authority, and interpretation](authority-trust.md).

## Do I have to configure the Functional Pyramid before using Span?

If the repository is intended to use project governance, yes: resolve
Functional Pyramid participation before relying on governed Span work.

A governed repository proceeds as ACTIVE + VALID. A repository deliberately
outside the governance model can be explicitly EXCLUDED and use the descriptive
semantic lifecycle without a governing projection.

UNCONFIGURED is a real state, but it is not a completed governance setup.

Start with [First investigation](onboarding-runbook.md). Exact Functional
Pyramid operations are in the [MCP reference](mcp.md).

## What happens when project guidance changes in another repository?

If the repositories are connected through declared governance, a change to a
goal, contract, design, or its applicability can make dependent knowledge in
another repository require reassessment.

Span follows the declared relationship rather than assuming repository
boundaries are knowledge boundaries.

## Do CURRENT or CURATED mean an explanation is true?

No.

**CURRENT** means the required recorded support still passes its checks.

**CURATED** means a reviewer accepted that exact revision for shared reuse.

Neither is a truth certificate. Semantic judgment remains with the investigator
and reviewer.

See [Support currency and reassessment](freshness.md) and
[Agent lifecycle](lifecycle.md).

## What happens when code changes?

Call `reconsider` with the changed paths.

Span identifies retained knowledge that may depend on the change. Reassess what
actually lost support; unrelated maintained knowledge can remain reusable.

See [Using Span — After code or project guidance changes](usage.md#after-code-or-project-guidance-changes).

## What if I disagree with retained knowledge even though the sources have not changed?

Keep the disagreement explicit as a challenge and resolve it through the
understanding lifecycle.

A matching source fingerprint, a later version, or a passing test does not
silently settle a semantic disagreement.

See [Interpretation and recording](interpretation.md).

## Can I retain useful work that began outside Span?

Yes.

Span can record supported understanding from work that already has a clear
scope and evidence. That does not change the normal operating rule that agents
should consult Span before re-deriving understanding when working with Span.

Exact recording forms are in the [MCP reference](mcp.md#record).

## Does Span run my coding agent, edit code, or execute tests?

No.

Your coding agent keeps its own model, tools, editor, search, and test runner.
Span maintains the reusable software knowledge produced around that work.

## Do I need hooks?

No.

Hooks provide lifecycle reminders at useful moments. The lifecycle itself does
not depend on a hook being delivered.

See [Lifecycle hooks](hooks.md).

## What happens if a recording response is lost?

Retry with the same recording identity and the same content. Span's replay
contract is designed so a retained acceptance can be recovered safely.

Do not guess that a missing response means the write failed.

See [MCP reference — Replay, identity, and retention](mcp.md#replay-identity-and-retention).

## Does Span save time or tokens?

That is the intended effect of reusing valuable investigations and focusing
reassessment, but the amount depends on the workload, how often knowledge is
reused, and the lifecycle overhead.

Span does not make a universal time- or token-saving claim without evidence for
that specific claim.

## Which coding-agent hosts are supported?

Managed integration exists for Codex, OpenCode, and Claude Code. Other MCP hosts
can use the stdio server manually.

For the current Beta candidate, registration/integration support and verified
live model delivery are different claims. See
[Acceptance and evidence](acceptance.md) and
[host integration](../integrations/hosts/triggers.md) for the current verified
status rather than relying on this FAQ as a release-status record.

## Where is Span state stored, and how do upgrades work?

Span keeps its runtime state outside the target source tree, with repository
backup support where explicitly configured.

Storage schemas, offline transitions, host upgrades, and recovery procedures are
operator concerns and change over releases. Follow
[Install and connect](install.md) and [Backup and recovery](recovery.md) for the
current procedure.
