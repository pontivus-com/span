# Scope and product boundaries

Span gives an agent working context for the exact software scope it is dealing
with. That context can include retained understanding of the implementation and,
for participating repositories, the project guidance that applies to the same
scope. The task determines the scope; Span keeps established understanding,
support, and later change effects attached to it through the required lifecycle.

## The unit is an explanation

An understanding answers a question over a declared scope. Its immutable
versions contain exact conclusion revisions and explicit gaps. An understanding
may span source, tests, configuration, and contracts. A file or symbol is an evidence anchor.

An agent can select an exact `FILE`, `SYMBOL`, `SERVICE`, or `DOMAIN` surface.
A service or domain surface is declared through `record(kind="surface")` with a
boundary and optional parent; its identity survives boundary updates, which use
compare-and-set. A file or symbol surface needs no declaration. The service
never auto-declares a surface from an understanding.

Ordinary coding work can start with saved answers, a cold investigation,
or evidence gathered outside Span. Recording is an explicit action, with an
inspectable receipt. Follow [the required lifecycle](lifecycle-contract.md#required-agent-completion).

## Reuse has qualifications

The surface document view groups current conclusions by recorded question;
a targeted query matches the exact recorded question. The agent
judges applicability and meaning. A `CURRENT` qualification establishes only
that declared support still passes its checks. It does not prove semantic
correctness, full coverage, or the absence of an unresolved dispute.

A relevant source/authority change, superseded premise, or changed recorded
membership boundary can require reassessment. Unsupported or missing evidence
remains explicit. Changes outside a declared dependency boundary do not make
all saved understanding noncurrent.

The intended benefit is continuity between investigations and focused review
of affected explanations. Net time/token savings depend on the task, recording
effort, reuse, and host delivery. The beta does not claim a measured universal
saving or a comparative product-fitness ACCEPT result.

## Declared governance is scoped, not inferred

The Functional Pyramid connects the exact software scope to the project
guidance that applies to it. An ACTIVE member declares its Functional Scope and
governing graph explicitly. Ordinary `ask` resolves that guidance from the same
scope used for retained implementation understanding. A scope outside the
declared Functional Scope receives a resolved empty governing projection, while
covered, uncovered, and mixed scopes remain distinct.

For NORMATIVE recording in an ACTIVE repository, Span derives one functional
route dependency plus every applicable canonical authority dependency. The
agent cannot make a normative conclusion current by omitting governance.
DESCRIPTIVE understanding remains independent unless it explicitly cites
authority.

## Agent and server responsibilities

The agent owns semantic judgment, source investigation, applicability, edits,
and external tests. The repository's owners supply authority. Span validates
commands, admits evidence, preserves versions and receipts, qualifies support,
and returns bounded discovery with explicit omissions.

Source search and structural tools remain useful for new investigation.
Span's structural navigation describes locations and adjacency; it cannot
assign ownership, policy, intent, or professional authority from topology.

## Scope and boundedness

A surface reports its unexamined members as a bounded status, never as
completeness. Source inventory and evidence batches expose their limits.
An unexamined file or truncated result is not proof of absence. A complete
membership observation must actually cover its stated boundary. See
[queries](queries.md).

Investigation scope is explicit. Broader work requires the agent to choose
and examine the broader scope; Span does not turn a local question into an
automatic semantic crawl. Installation establishes readiness; investigation establishes understanding.

Verification has its own declared scope. A run applies to the surfaces within
that scope: a single-file run is not widened to a broader service, and a
service-wide run applies to the files it covers.

## Local storage and operational effects

Repository runtime state uses schema 14 in the external data directory.
Installation-level Functional Pyramid participation and receipts use the
separate installation database under `<DATA_DIR>/installation/`. Recoverable
contexts and observation admission are operational state; recording creates
semantic history. Context expiry does not erase accepted conclusions, challenges,
verification runs, or retained receipts. Receipt expiry ends that replay
window, not the existence of the recorded understanding.

The managed structural artifact lives under
`<DATA_DIR>/structural/<repository-id>/.graph/wiring.json`. Explicit setup owns
provider currency work. Ordinary lifecycle operations and hooks do not build
it. Runtime operation does not write target source or provider artifacts into
the target repository. Installation may write a managed `AGENTS.md` block and
host configuration as described in [install](install.md).

Existing schema-7–13 repository stores use the separately invoked offline
inspect/apply/verify/rollback protocol into schema 14. The schema-13 transition
preserves its durable semantic/audit rows and derives only the route lookup
projection from already-retained FunctionalRouteSupport; it does not invent
participation, authority support or historical routes. Earlier schemas keep the
documented preservation/mapping boundary. See the
[transition procedure](install.md#upgrade-an-existing-store).

## Beta delivery boundary

Generic Version-1 behavior is verified through the full functional acceptance
matrix and installed stdio MCP lane. Codex, OpenCode and Claude Code remain
managed integration targets, but final-candidate live model delivery is not
claimed until T13 captures it. Registration, configured hooks and observed
model behavior remain separate facts.

See [usage](usage.md), [freshness](freshness.md), and [FAQ](faq.md).
