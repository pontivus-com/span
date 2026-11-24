# Scope and product boundaries

Span retains software understanding for the exact scope an agent is dealing
with and separately qualifies exact semantic revisions for shared reuse. At task
time, supported and curated knowledge becomes working context: retained
understanding of the implementation and, for participating repositories, the
project guidance that applies to the same scope. The task determines the scope;
Span keeps captured meaning, curation state, support, governing relationships and
later change effects attached to it through the required lifecycle.

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

The intended benefit is maintained software knowledge that can be projected as
complete working context for the exact software scope once the semantic revision
is both curated and supported: retained implementation understanding, the
applicable canonical project guidance, and focused review when either side
changes. Net time/token savings depend on the task, recording
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

Beta 3 repository runtime state uses schema 15 in the external data directory.
Installation-level Functional Pyramid participation and receipts remain in the
separate installation database under `<DATA_DIR>/installation/` at installation
schema 1. Recoverable contexts and observation admission are operational state;
recording creates semantic history and curation dispositions qualify exact
semantic revisions for shared reuse. Context expiry does not erase accepted conclusions, challenges,
verification runs, or retained receipts. Receipt expiry ends that replay
window, not the existence of the recorded understanding.

The managed structural artifact lives under
`<DATA_DIR>/structural/<repository-id>/.graph/wiring.json`. Explicit setup owns
provider currency work. Ordinary lifecycle operations and hooks do not build
it. Runtime operation does not write target source or provider artifacts into
the target repository. Installation may write a managed `AGENTS.md` block and
host configuration as described in [install](install.md).

Existing schema-7–14 repository stores use the separately invoked offline
inspect/apply/verify/rollback protocol into schema 15. The Beta-3 schema-14→15
mapping preserves durable semantic/audit/governance state and the existing route
lookup projection while creating zero curation dispositions. Earlier schemas
retain their documented preservation/mapping boundaries before the final
schema-15 transition. See the
[transition procedure](install.md#upgrade-an-existing-store).

## Beta delivery boundary

Generic Beta-3 behavior is verified through the full FA-01–FA-64 functional
acceptance matrix and installed stdio MCP lane. Codex, OpenCode and Claude Code
remain managed integration targets, but live model delivery for the current
Beta-3 candidate is **UNVERIFIED**. Registration, configured hooks and observed
model behavior remain separate facts. Private first-adopter cold-install/governance/capture-curation revalidation
has passed against committed adopter inputs. Beta 3 remains unpublished until
its corrective exact-head gates pass and the release owner separately
authorizes publication.

See [usage](usage.md), [freshness](freshness.md), and [FAQ](faq.md).
