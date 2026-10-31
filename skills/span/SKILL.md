---
name: span
description: Understand a repository with Span before changing it: ask a scoped question, admit exact evidence, record supported understanding atomically, and reassess when support changes while keeping unresolved knowledge explicit.
---

# Span — maintained understanding lifecycle

Span answers from recorded understanding and exact source evidence. It owns
validation, identity, freshness, and persistence. The agent owns interpretation
and every edit. Span never edits the target, runs application tests, selects a
model, or decides a semantic claim. A ready store proves operational
availability only, never semantic coverage or correctness.

## Start here

No status preflight is required. Ask `understand_question` with the question
and an exact scope. The result is one of:

- saved candidates with live support qualifications;
- `InvestigationNeeded` with admitted, inspectable evidence and the material gap;
- `DiscoveryLimit` when there is no usable scope or overlap. That is a request
  for a concrete scope, not a claim that no understanding exists.

Discover the exact registered `repository_id` from `tools/list` or an
`initialize_repository` result. Never pass a filesystem path as the ID. When no
store exists, stop ordinary work: `initialize_repository` runs once in a
dedicated setup session and creates no understanding.

## Operations

| Intent | Tool | Use it when | Result |
| --- | --- | --- | --- |
| Ask a scoped question | `understand_question` | You need saved understanding or inspectable evidence | Candidates, investigation gap, or an explicit discovery limit |
| Retrieve an exact snapshot | `understand_retrieve` | You have an understanding ID | Exact version, conclusion bodies, challenges; takes `repository_id` |
| Start a context | `start_context` | You will record after investigating | A recoverable server-issued context |
| Admit exact sources | `evidence_start` / `evidence_extend` | You need canonical observations, with or without a question | Per-item admitted/reused/failed/omitted outcomes |
| Record | `record_create`, `record_add`, `record_confirm`, `record_correct`, `record_replace`, `record_withdraw` | You established supported conclusions | Atomic receipt and accepted version |
| Dispute | `record_challenge`, `record_update` | A conclusion is questioned or a disposition is due | Atomic challenge/receipt; no implicit settlement |
| Verify independently | `record_verification`, `verification_support` | You executed or want to qualify a run | Accepted run and support qualification |
| Reassess | `reassess` | Source, authority, premise, or discovery support may have changed | Current, reassessment-required, or unverifiable |
| Navigate structure | `locate`, `neighbors` | You need symbols, outlines, or adjacency | Navigation evidence only; never authority |

## Recording rules

- Admit evidence first. Record cites canonical observation IDs; it does not
  resend source bodies or invent fingerprints.
- Every recording call is atomic. A validation, identity, conflict, or source
  drift failure changes nothing and names the exact offending identity.
- Reuse the same `context_id` and `submission_id` when retrying a lost
  response. A matching committed receipt replays even after the context expired.
- An update states whether it confirms, corrects, replaces, or withdraws an
  exact conclusion revision. Omission is not deletion.
- Challenges are settled only through named dispositions in `record_update`.
  A new version or passing test never settles a dispute silently.
- A verification records the observations actually tested. Later reads cannot
  reconstruct that run, and an unsupported attestation never becomes a pass.

## After the change

When the edit touches sources a recorded conclusion cites, run `reassess` on
that exact understanding and version. Report current, reassessment-required, and
unverifiable outcomes as they are. Re-record only what you can support now,
with a new submission identity.

Use outside tools to edit and test. Hooks are optional event-local notices:
they never record, reassess, interpret, or rebuild, and a missed hook never
makes stale understanding current.

Keep `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`, `UNRESOLVED`, `STALE`, and
`UNVERIFIABLE` verbatim. Missing authority stays missing.

Detail: [lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md),
[MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md),
[onboarding runbook](https://github.com/pontivus-com/span/blob/master/docs/onboarding-runbook.md).
