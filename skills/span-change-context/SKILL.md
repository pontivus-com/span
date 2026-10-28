---
name: span-change-context
description: Assess a planned material code change with Span impact analysis before editing: blast radius, conditions, authority, verification, and blockers.
---

# Span — pre-change context for material edits

Use this when a change is material: it crosses a boundary, changes ownership or
representation, affects configuration or lifecycle, changes a public contract,
or touches an unfamiliar component. The primary span skill is authoritative for
operation selection, repository identity, readiness, evidence, recovery, target
accounting, freshness, and closeout.

1. Confirm the registered `repository_id` and the exact target. If readiness is
   `UNINITIALIZED`, use the primary skill's setup path first.
2. Call `impact` with the target, `change_kind`, a concise
   `change_description`, and `affected_assertions` naming established claim or
   relationship references where known. The result is a bounded brief, never
   approval.
3. Follow only the required pending units. Use `trace` for established
   producer/carrier/consumer and lifecycle relationships, `authority` for
   governing sources, `explain` for behavior, and `locate`/`neighbors` for
   structural discovery. Structural reach is possibility, not established
   impact.
4. Resolve blockers before relying on the brief: missing authority, `PARTIAL`,
   `AMBIGUOUS`, `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE`
   findings stay visible and require the bounded action Span names. Change
   conditions are dimensions, not scores.

Keep semantically established effects separate from structural-only
possibilities. Preserve ownership, governing sources, invariants,
representation, verification currency, and unresolved requirements exactly as
evidenced. Submit through `submit_interpretation` using the primary skill's
pending procedure and recovery matrix; do not invent a second change shape or
semantic policy. Never convert uncertainty into certainty.

If the proposal reveals an unknown participant, contract, dependency, or
authority question, establish that precise question first and submit it through
the same canonical path. Structural adjacency is evidence only; it never
determines ownership or semantic impact.

After editing, close out in the primary skill's order: scoped `status` on the
exact mutated scope, outside tests/review, scoped `refresh` with a substantive
re-submission where required, then scoped `status` again. A bare `refresh`
proves nothing.
