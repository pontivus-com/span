# Span — semantic repository lifecycle

Use Span's canonical operations to understand a repository before you
change it. Span answers from indexed evidence; it never edits code,
runs tests, or decides for you.

## Operation lifecycle

```
orient      explain <target>
prepare     impact <target + change>
investigate trace / authority (only where required)
implement   external editing tools (Span never edits)
verify      status + external tests/review
close       refresh, then status
```

Enter at any phase. Trivial local work needs no Span call. Unfamiliar
components and cross-boundary changes should orient first; material
changes should run `impact` before implementation.

## The eight operations (only these exist)

`initialize_repository`, `explain`, `impact`,
`trace`, `authority`, `status`, `refresh`,
`submit_interpretation`. No other semantic operation exists.

## Rules

- Repository setup is explicit: if readiness is `UNINITIALIZED`, run
  `initialize_repository` in a dedicated setup session. Normal
  queries and hooks never initialize. Readiness is operational, never
  semantic completeness.
- Entry modes: default `explain` is question-local and never claims
  baseline sufficiency. Use `explain(establish_baseline=True)` only
  on an explicitly selected root for a bounded CQ-01–CQ-09 audit;
  work admitted PENDING questions in order; `refresh` never expands
  scope silently.
- When an operation returns a pending interpretation unit, perform the
  bounded SA-1–SA-7 task with your own model and submit the typed
  result via `submit_interpretation`. A submit may return the
  final answer or the next pending unit; keep submitting until an
  answer returns. `submit_interpretation` is exchange, never a
  question class.
- Claims alone never complete a question (Addendum C C-05). Every
  submission that answers the bound question must carry an explicit
  `ANSWERED` coverage for that exact question (with `declared_complete`
  set; the service derives result refs from validated candidates).
  Submissions without explicit completion persist `PENDING` and leave
  claims unassigned. An explicit `ANSWERED` with zero validated
  material is rejected; only complete replacement retires unshared
  prior outputs, and `PENDING`/`OPEN`/`NOT_APPLICABLE` never retire
  by omission.
- A listing token (`page_token`, now `pg:<claims>:<rels>:<questions>`)
  pages truncated listings including question coverage. A
  continuation resumes one suspended interpretation. They are
  different mechanisms; never substitute one for the other.
- Uncertainty is never certainty: `PARTIAL`, `AMBIGUOUS`,
  `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` results must
  be reported as such and never reinterpreted into a firm answer.
  Missing authority stays missing; conflicts stay side-by-side until
  declared precedence resolves them.
- `refresh` is explicit. Hooks only report readiness/staleness
  (`status` with `HOOK_FAST`) and never refresh, interpret,
  rebuild, or initialize.
- Targets are canonical selectors: `{"$type": "SubjectSelector", ...}`
  with an exact id, name/locator, or kinds. Bounds may be omitted for
  service defaults.

## Reading answers

Every answer carries evidence pointers, per-claim freshness, and
requirements describing what would resolve incomplete knowledge.
Follow `resolution_requirements` before treating partial knowledge as
complete. Stale items need `refresh`, not reinterpretation by
hand.
