# Frequently asked questions

## What does an agent actually do with Span?

Ask for the file, symbol, service, or domain the agent is working on. Span
returns the current understanding already retained for that surface and, for an
ACTIVE Functional Pyramid repository, the project guidance that applies to the
same scope from first principles down to functional and technical design.

The agent investigates any gaps with its normal tools and records useful
conclusions when established. A later session can ask the same surface without
the old conversation or a saved internal ID. After code or guidance changes,
`reconsider` identifies the understanding that actually needs another look.
See [usage](usage.md).

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

## Does CURRENT mean the explanation is true?

It means declared support still passes its checks. The original interpretation
may still be incomplete or wrong. Gaps and challenges remain visible; the
agent judges applicability and semantic correctness.

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

The generic Version-1 product is verified through source CI, the non-editable
installed stdio MCP lane, and the FA-01–FA-44 functional acceptance matrix.
Managed registration/integration exists for Codex, OpenCode and Claude Code,
but candidate-specific live model-host delivery is a separate T13 gate. Until
those captures exist for the final candidate, live Version-1 model delivery is
reported as **UNVERIFIED**, not inferred from registration health or historical
captures.

## Does Span save time or tokens?

It is designed to preserve useful investigations and focus reassessment. The
amount saved depends on workload, reuse, recording overhead, and host delivery.
The beta does not claim a universal saving or a completed comparative ACCEPT.

## Where is state stored, and how do upgrades work?

Repository semantic/audit state uses schema 14 in the external data directory.
Functional Pyramid participation, versions, exclusions and installation-scoped
receipts live in the separate installation database at
`<DATA_DIR>/installation/functional-pyramid.db`.

The runtime never migrates a store at open. Existing schema-13 repositories use
the explicit offline transition to schema 14; the transition preserves their
semantic/audit state and does not fabricate historical Functional Pyramid
support or participation. Registered repositories begin `UNCONFIGURED` until
participation is explicitly recorded. Full-installation recovery includes the
installation database; a repository-portable backup deliberately does not.

A bare package upgrade does not migrate host configuration. Rerun
`span-install`, complete any required offline transition, verify the
installation, and reconnect the host. See [install](install.md) and
[recovery](recovery.md).
