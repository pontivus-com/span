---
name: span-change-context
description: Assess a planned material code change with Span impact analysis before editing: blast radius, conditions, authority, verification, and blockers.
---

# Span — pre-change context for material edits

Use this specialization when a proposed change is material: it crosses a
boundary, changes ownership or representation, affects configuration or
lifecycle, changes a public contract, or touches an unfamiliar component.
The primary `skills/span/SKILL.md` is authoritative for operation selection,
repository identity, readiness, evidence admission, continuation recovery,
target accounting, freshness, and closeout.

## Before editing

1. Establish the exact target and proposal. Confirm the canonical registered
   `repository_id`; a filesystem path is never an ID. If the repository is
   `UNINITIALIZED`, use the primary skill's dedicated
   `initialize_repository` workflow before semantic calls.
2. Call `impact` with the target, `change_kind`, concise
   `change_description`, and — where known — `affected_assertions` naming
   established claim or relationship references. `impact` prepares a bounded
   brief; it never approves the change.
3. Follow only the required pending units. Use `trace` for established
   producer/carrier/consumer and lifecycle relationships, `authority` for
   governing sources, `explain` for behavior, `locate`/`neighbors` for
   structural discovery, and `status` for read-only currency. Structural
   reach is possibility, not established impact.
4. Resolve blockers before relying on the brief: missing authority,
   `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`, `UNRESOLVED`, `STALE`, and
   `UNVERIFIABLE` findings remain visible and require the bounded action named
   by Span. Do not treat change-condition dimensions as scores or weights.

## Impact result and implementation boundary

Separate semantically established downstream effects from structural-only
possibilities. Preserve the owner/custodian, governing sources, invariants,
representation, verification currency, and unresolved requirements exactly as
evidenced. `impact` is not authorization, and Span never edits the target,
runs application tests, or selects an LLM/provider.

Use the primary skill's pending quality card for impact follow-ups:
objective; exact scope and exclusions; evidence and authority; input →
producer → transformation/state → consumer/output → terminal/failure path;
typed result; adversarial check; explicit disposition; and fresh readback.
Submit through the canonical `submit_interpretation` path and use its
diagnostic recovery matrix. Do not invent a second change DTO or semantic
policy.

## After editing and expansion

Close the exact affected scope with the primary sequence: scoped `status`
on the exact mutated scope, external tests/review, explicit scoped `refresh`
with a substantive re-submission where required, then scoped `status` again.
A bare `refresh` does not prove correctness or currency.

If the proposal surfaces an unknown participant, contract, dependency, or
authority question, establish that precise question before relying on it and
submit it through the canonical path. Structural adjacency is evidence only;
it never determines ownership or semantic impact. Keep unresolved facts
`OPEN`/`PENDING` rather than converting them into certainty.
