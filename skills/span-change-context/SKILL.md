# Span — pre-change context for material edits

Before a material code change (cross-boundary, ownership,
representation, configuration, lifecycle, public-contract, or
unfamiliar-component work), call `impact` with the target, the
change kind, a short description, and — where known — the
`affected_assertions` references naming the established assertions the
proposal would alter.

## What you get back

A bounded pre-change brief: relevant identity and purpose, the
established owner/custodian, governing authority and invariants,
boundary and representation context, derived change conditions,
downstream impacts split into semantically established versus
structural-only possibilities, verification currency, and blockers
(conflicts, stale evidence, unresolved authority) with requirements
for resolving them.

Use the same pending-task quality card when investigating or updating the
change context: objective; exact scope and exclusions; evidence and authority;
input → producer → transformation/state → consumer/output → terminal/failure;
typed result; adversarial check; explicit disposition with requirements; and
fresh readback. The card applies equally to impact follow-ups, expansion,
refresh, and closeout. It is compact guidance over the canonical submission
path, not a second quality model or a substitute for evidence.

## Rules

- `impact` prepares; it does not approve. Change conditions are
  descriptive dimensions only — they carry no weight.
- Structural reach is possibility, not established impact. Do not
  treat every caller or importer as materially affected.
- Uncertainty is never certainty: `PARTIAL`, `AMBIGUOUS`,
  `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` states in
  the brief must be reported as such and never reinterpreted into a
  firm answer. Resolve blockers first (authority lookup, refresh, or
  narrower investigation with `trace` / `authority`).
- Proposal-sensitive conditions fire only for typed affected
  assertions resolved against current state. The description is
  context for interpretation, not a field to mine for conclusions.
- After implementation, verify with `status` plus external
  tests/review, then close with explicit `refresh`.
- This skill orchestrates canonical operations only
  (`impact`, then `trace` / `authority` /
  `status` / `refresh` where required). It defines no
  semantic rules of its own.

## Expansion identification

Pre-change investigation that surfaces unknown participants,
contracts, or dependencies material to the proposal: establish the
precise material question, admit it under the existing identity/scope
rules, and submit through the canonical path — before relying on it
in change conditions. See the Expansion section of
`skills/span/SKILL.md`. Structural reach is possibility, never
admission; no silent broadening.
