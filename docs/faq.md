# Frequently asked questions

## What does an agent actually do with Span?

Ask for the file, symbol, service, or domain the agent is working on. Span
returns current curated shared knowledge for that surface, explicit pending or
stale status, and, for an ACTIVE Functional Pyramid repository, the project
guidance that applies to the same scope from first principles down to functional
and technical design.

The working agent investigates gaps and captures supported conclusions when
established. A separate reviewer curates stable exact revisions for shared reuse.
A later session can ask the same surface without the old conversation or a saved
internal ID. After code or guidance changes, `reconsider` identifies the
understanding that actually needs another look.
See [usage](usage.md).

## Is Span a knowledge factory?

A software knowledge factory is the broader loop in which engineering work
produces candidate understanding, shared knowledge is curated for future reuse,
and changes feed back into maintenance. Span is the evidence-backed knowledge
layer in that loop: it retains agent-established software understanding with its
declared support, records which exact revisions have been curated for shared
reuse, resolves applicable governing guidance, and identifies what needs
reassessment after change.

The working coding agent or engineer remains the semantic author at capture
time. Curation is a separate reviewer role that may be another agent session, a
dedicated curator agent, a human reviewer, or a team workflow. Span records and
enforces that lifecycle but does not run a background curator model or
autonomously decide semantic quality.

This is deliberately narrower than the organizational topology described in
LangChain's [knowledge-factory article](https://www.langchain.com/blog/knowledge-factory).
That article separates task agents from a curator agent that can run in the
background over broader raw sources and traces. Span separates evidence-near
capture from explicit review for software understanding, while deterministic
support/currentness and declared governance stay inside the Span server. Span
does not claim that curation certifies truth, that curation must be autonomous,
or that a separate curator/reviewer role is unnecessary.

## How is Span different from a context engine or agent memory?

A context engine primarily helps an agent retrieve the source and organizational
material relevant to the task in front of it. Agent memory can preserve facts,
interactions, preferences, or other information across tasks.

Span focuses on the interpretation layer produced by software work: what an
agent established about an exact software surface, what supported that
conclusion, which governing guidance applied, whether those dependencies still
hold, and what must be reconsidered after change. These capabilities can be
complementary rather than mutually exclusive.

## Does installation explain the whole repository?

Installation establishes operational readiness. Understanding comes from
explicit investigations and recording. A ready store, populated database, or
successful call does not prove repository completeness.

## What is the Functional Pyramid?

The Functional Pyramid is how Span knows which project guidance applies to the
exact part of the software an agent is working on. It links that scope to the
relevant goals and first principles, then through the applicable rules and
contracts to functional and technical design.

Those documents remain in their canonical locations, including other
repositories. Span keeps their relationships, applicability, and order
explicit. It does not guess from filenames, search relevance, or document type,
and it does not copy the governing documents into Span.

## Do I have to activate a repository before using Span?

No. A registered repository begins `UNCONFIGURED`; it can still use the
ordinary descriptive lifecycle. `EXCLUDED` is an explicit opt-out. An `ACTIVE`
repository receives Functional Pyramid orientation, and NORMATIVE recording
derives its applicable route and authority support automatically.

## What happens when governance changes in another repository?

Span follows the declared guidance chain across repositories. If a goal,
contract, design, or its applicability changes in one repository, `reconsider`
can identify understanding in another repository that depended on it and now
needs another look.

## Must every file be documented first?

No. An understanding is a coherent explanation and can span several files.
The agent chooses the scope for the real task. Retain the supported conclusions established in that scope.

## Can I record work that began without Span?

Yes. `record` issues its own context from the supplied scope and cited
evidence, then creates understanding with an explicit question and scope, or
records an independent verification run. This direct-create capability preserves imported work; agents consult Span
before deriving understanding under [the required lifecycle](lifecycle-contract.md#required-agent-completion).

## Do CURRENT or CURATED mean the explanation is true?

No. `CURRENT` means the revision's required support still passes its owning
checks. `CURATED` means an explicit reviewer accepted that exact semantic
revision for shared reuse. Neither is a truth certificate: the interpretation
may still be incomplete or wrong, and semantic judgment remains with the
investigator/reviewer.

## What happens when code changes?

Dependent support can become `REASSESSMENT_REQUIRED` or `UNVERIFIABLE`.
`reconsider` names the affected surfaces and each conclusion's current
qualification. The agent investigates and records a
confirm/correct/replace/withdraw update; history remains intact.
Changes outside a declared dependency boundary leave other support alone.

## What if sources match but I disagree?

Record an explicit challenge. Resolve it or carry it forward through named
challenge dispositions in `record`. A new version or passing test does
not silently settle it.

## Does Span run the agent, change code, or execute tests?

The coding agent uses its own model and tools for reasoning, edits, and tests.
Span stores and qualifies what is recorded. It has no model provider or
provider credentials and does not autonomously reinterpret source.

## Do I need hooks?

Hooks deliver lifecycle reminders. Retrieval and recording check support without
them. A configured hook, a quiet event, and an observed delivery are different
facts. See [hooks](hooks.md).

## What happens after a lost response?

Retry exactly the same recording identity and content. A retained receipt
recovers acceptance, even if its context expired or the sources later changed.
Inspect history when retention has expired; missing replay state does not
prove the original commit failed.

## Which clients are verified for this beta?

The Beta-3 product is verified through source CI, the non-editable installed
stdio MCP lane, and the FA-01–FA-64 functional acceptance matrix, including the
combined installer + Functional Pyramid + capture/curation topology. Managed
registration/integration exists for Codex, OpenCode and Claude Code, but live
model-host delivery for the current Beta-3 candidate remains **UNVERIFIED** and
is not inferred from registration health, configured hooks, or historical
captures. Private first-adopter cold-install/governance/capture-curation revalidation
has passed against committed adopter inputs. Beta 3 remains unpublished until
its corrective exact-head gates pass and the release owner separately
authorizes publication.

## Does Span save time or tokens?

It is designed to preserve useful investigations and focus reassessment. The
amount saved depends on workload, reuse, recording overhead, and host delivery.
The beta does not claim a universal saving or a completed comparative ACCEPT.

## Where is state stored, and how do upgrades work?

Beta 3 repository semantic/audit state uses schema 15 in the external data
directory. Functional Pyramid participation, versions, exclusions and
installation-scoped receipts remain in the separate installation database at
`<DATA_DIR>/installation/functional-pyramid.db` with installation schema 1.

The runtime never migrates a store at open. Existing schema-14 repositories use
the explicit offline transition to schema 15; that transition preserves
Beta-1 semantic/audit/governance state and creates zero curation approvals.
Migrated semantic revisions therefore begin CAPTURED under the Beta-3 reuse
contract. Registered repositories remain `UNCONFIGURED` until Functional
Pyramid participation is explicitly recorded.

A bare package upgrade does not migrate host configuration. Rerun
`span-install`, complete any required offline transition, verify the
installation, and reconnect the host. See [install](install.md) and
[recovery](recovery.md).
