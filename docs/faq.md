# Frequently asked questions

## What does an agent actually do with Span?

Ask a scoped engineering question, inspect current answers or source evidence,
investigate material gaps, and record useful conclusions. A later session can
ask its own question, find applicable understanding, and check its support.
After changes, the agent reconsiders affected explanations and updates actual loss.
See [usage](usage.md).

## Does installation explain the whole repository?

Installation establishes operational readiness. Understanding comes from
explicit investigations and recording. A ready store, populated database, or
successful call does not prove repository completeness.

## Must every file be documented first?

No. An understanding is a coherent explanation and can span several files.
The agent chooses the scope for the real task. There is no mandatory campaign,
internal question classification, or one-file-at-a-time semantic submission.

## Can I record work that began without Span?

Yes. `record` issues its own context from the supplied scope and cited
evidence, then creates understanding with an explicit question and scope, or
records an independent verification run. A prior question/answer exchange is
optional.

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

Hooks are optional notices. Retrieval and recording check support without
them. A configured hook, a quiet event, and an observed delivery are different
facts. See [hooks](hooks.md).

## What happens after a lost response?

Retry exactly the same recording identity and content. A retained receipt
recovers acceptance, even if its context expired or the sources later changed.
Inspect history when retention has expired; missing replay state does not
prove the original commit failed.

## Which clients are verified for this beta?

Codex and OpenCode are supported live targets with three-tool captures of the
declared grammar, request identity, and recovery behavior. The 2026-11-07
candidate adds an OpenCode compact create/add/correct/replace journey and a
Codex flat-create smoke journey; Codex's full compact add/correct/replace
journey is still pending. OpenCode removes an unknown old-form field before
delivery, so strict unknown-field rejection is not established through that
host. Claude Code is a supported managed host for registration,
health inspection, and installer behavior, but its authenticated
model-delivery grammar and caller identity remain **UNVERIFIED**. Registration
health alone is not model-delivery evidence.

## Does Span save time or tokens?

It is designed to preserve useful investigations and focus reassessment. The
amount saved depends on workload, reuse, recording overhead, and host delivery.
The beta does not claim a universal saving or a completed comparative ACCEPT.

## Where is state stored, and how do upgrades work?

In an external data directory. The active store is schema 11; older supported
stores use the explicit offline archive/export/stage/activate transition.
[Install](install.md) documents verification, rollback, removal, and retention.

A bare package upgrade does not migrate the host. Rerun `span-install` for the
target and restart the host after configuration changes. A current 0.10.0
receipt preserves its absolute OpenCode MCP and plugin paths; the installer
does not migrate obsolete target-plugin copies. See [install](install.md) for
the current selection, verification, and uninstall behavior.
