# Span — pre-change context for material edits

Before a material code change (cross-boundary, ownership,
representation, configuration, lifecycle, public-contract, or
unfamiliar-component work), call `span_impact` with the target, the
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

## Rules

- `span_impact` prepares; it does not approve. Change conditions are
  descriptive dimensions only — they carry no weight.
- Structural reach is possibility, not established impact. Do not
  treat every caller or importer as materially affected.
- Uncertainty is never certainty: `PARTIAL`, `AMBIGUOUS`,
  `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` states in
  the brief must be reported as such and never reinterpreted into a
  firm answer. Resolve blockers first (authority lookup, refresh, or
  narrower investigation with `span_trace` / `span_authority`).
- Proposal-sensitive conditions fire only for typed affected
  assertions resolved against current state. The description is
  context for interpretation, not a field to mine for conclusions.
- After implementation, verify with `span_status` plus external
  tests/review, then close with explicit `span_refresh`.
- This skill orchestrates canonical operations only
  (`span_impact`, then `span_trace` / `span_authority` /
  `span_status` / `span_refresh` where required). It defines no
  semantic rules of its own.
