# Agent execution lifecycle

```
OFFLINE (dedicated setup session)
  initialize_repository → READY (no interpretation happens here)

NORMAL CODING SESSION (enter anywhere)
  ORIENT        explain
  PREPARE       impact  (material changes: always before editing)
  INVESTIGATE   trace / authority (where required)
  IMPLEMENT     external editing tools
  VERIFY        status + external tests/review
  CLOSE         refresh + status
```

Span never edits, generates patches, runs tests, or orchestrates
workflows. When stored semantics are insufficient, the operation
suspends with a bounded task: interpret it with your own model,
submit via `submit_interpretation`, and continue — a submit may
return the answer or the next pending unit.

## Refresh ownership (Addendum C C-06)

The agent that changes implementation or governing semantic evidence
owns the close-out sequence for the scope it affected (edit → scoped
status → external verification → explicit scoped refresh → scoped
status) in the same change. Hooks stay report-only and never refresh.
Neglected stale scopes remain visibly noncurrent; Span never presents
a stored `ANSWERED` as effectively current where required support is
stale or unverifiable.

## Initialization and readiness

Initialization is explicit and administrative: identity, repository
state, structural source, evidence inventory, authority seeds, store
schema — then a readiness report. Uninitialized repositories answer
`UNINITIALIZED` plus a setup requirement on every path; hooks and
queries never bootstrap implicitly. Readiness is operational state,
never semantic truth.

## Workflow examples

- Investigate: `explain` unfamiliar target → `trace`
  upstream/downstream → `authority` on the governing claim.
- Baseline a subsystem: `explain(establish_baseline=True)` on the
  exact root → work admitted PENDING questions in order → synthesize
  only on established member evidence → report qualified sufficiency.
- Implement: `impact` with change kind + affected assertions →
  resolve blockers → edit → `status` → external tests →
  `refresh` → `status`. `refresh` reuses persisted question scope;
  it never starts a new baseline audit.
- Test/review: `status` for verification currency (candidate vs
  current pass/fail) — Span reports currency; it never runs tests.
- Change-context: see `skills/span-change-context/SKILL.md`.

Root selection uses existing repository context plus bounded
structural operations; the structural port has no repository-wide
enumerate/map, and `status` never enumerates subjects. Skills are
guidance only, never semantic authority.
