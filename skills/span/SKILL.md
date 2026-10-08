# Span — semantic repository lifecycle

Use Span's canonical operations to understand a repository before you
change it. Span answers from indexed evidence; it never edits code,
runs tests, or decides for you.

## Operation lifecycle

```
orient      span_explain <target>
prepare     span_impact <target + change>
investigate span_trace / span_authority (only where required)
implement   external editing tools (Span never edits)
verify      span_status + external tests/review
close       span_refresh, then span_status
```

Enter at any phase. Trivial local work needs no Span call. Unfamiliar
components and cross-boundary changes should orient first; material
changes should run `span_impact` before implementation.

## The eight operations (only these exist)

`span_initialize_repository`, `span_explain`, `span_impact`,
`span_trace`, `span_authority`, `span_status`, `span_refresh`,
`span_submit_interpretation`. No other semantic operation exists.

## Rules

- Repository setup is explicit: if readiness is `UNINITIALIZED`, run
  `span_initialize_repository` in a dedicated setup session. Normal
  queries and hooks never initialize.
- When an operation returns a pending interpretation unit, perform the
  bounded interpretation task with your own model and submit the typed
  result via `span_submit_interpretation`. A submit may return the
  final answer or the next pending unit; keep submitting until an
  answer returns. `span_submit_interpretation` is exchange, never a
  question class.
- A listing token (`page_token`) pages one truncated listing. A
  continuation resumes one suspended interpretation. They are
  different mechanisms; never substitute one for the other.
- Uncertainty is never certainty: `PARTIAL`, `AMBIGUOUS`,
  `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` results must
  be reported as such and never reinterpreted into a firm answer.
  Missing authority stays missing; conflicts stay side-by-side until
  declared precedence resolves them.
- `span_refresh` is explicit. Hooks only report readiness/staleness
  (`span_status` with `HOOK_FAST`) and never refresh, interpret,
  rebuild, or initialize.
- Targets are canonical selectors: `{"$type": "SubjectSelector", ...}`
  with an exact id, name/locator, or kinds. Bounds may be omitted for
  service defaults.

## Reading answers

Every answer carries evidence pointers, per-claim freshness, and
requirements describing what would resolve incomplete knowledge.
Follow `resolution_requirements` before treating partial knowledge as
complete. Stale items need `span_refresh`, not reinterpretation by
hand.
