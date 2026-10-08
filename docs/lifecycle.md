# Agent execution lifecycle

```
OFFLINE (dedicated setup session)
  span_initialize_repository → READY (no interpretation happens here)

NORMAL CODING SESSION (enter anywhere)
  ORIENT        span_explain
  PREPARE       span_impact  (material changes: always before editing)
  INVESTIGATE   span_trace / span_authority (where required)
  IMPLEMENT     external editing tools
  VERIFY        span_status + external tests/review
  CLOSE         span_refresh + span_status
```

Span never edits, generates patches, runs tests, or orchestrates
workflows. When stored semantics are insufficient, the operation
suspends with a bounded task: interpret it with your own model,
submit via `span_submit_interpretation`, and continue — a submit may
return the answer or the next pending unit.

## Initialization and readiness

Initialization is explicit and administrative: identity, repository
state, structural source, evidence inventory, authority seeds, store
schema — then a readiness report. Uninitialized repositories answer
`UNINITIALIZED` plus a setup requirement on every path; hooks and
queries never bootstrap implicitly. Readiness is operational state,
never semantic truth.

## Workflow examples

- Investigate: `span_explain` unfamiliar target → `span_trace`
  upstream/downstream → `span_authority` on the governing claim.
- Implement: `span_impact` with change kind + affected assertions →
  resolve blockers → edit → `span_status` → external tests →
  `span_refresh` → `span_status`.
- Test/review: `span_status` for verification currency (candidate vs
  current pass/fail) — Span reports currency; it never runs tests.
- Change-context: see `skills/span-change-context/SKILL.md`.
