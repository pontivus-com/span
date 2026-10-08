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

## Semantic closeout duty (editing agent, same change, exact scope)

You own closeout for every scope you mutate (code, contracts,
evidence) — in the same change, not a later session (C-11):

1. Verify first with external tests/review. Passing tests confirm
   behavior; they never prove semantics.
2. Run `status` on the exact mutated scope; identify the stale scope.
3. Run scoped `refresh` and re-examine what is stale: replace,
   withdraw, or reopen explicitly with typed requirements. A bare
   `refresh` call proves nothing — adequacy is in the resubmitted
   content, never the invocation.
4. Run `status` again to confirm; report incomplete closeout
   explicitly (what stays OPEN/stale and its requirements) instead
   of implying completeness. Where the host cannot enforce this
   sequence, say so in the report (see `integrations/hosts/triggers.md`).

## Expansion (deliberate, bounded, question-scoped)

When an investigation surfaces materially new knowledge (owner,
participant, contract, representation, transformation, consumer,
lifecycle, failure, dependency, verification):

1. Establish the precise material question and its relevance first —
   not every file read becomes a record.
2. Admit it under the existing identity/scope rules (evidence-backed
   `CandidateSubject` for unknown roots on an exact structural
   entrypoint; never a fresh generic question where a persisted
   identity exists) and submit through the same canonical mechanism.
3. Never broaden repository territory silently; no separate command,
   store, writer, or quality policy exists for expansion.
4. Retrieve later to confirm the knowledge persisted usefully.

Enter at any phase. Trivial local work needs no Span call. Unfamiliar
components and cross-boundary changes should orient first; material
changes should run `impact` before implementation.

## Establishing a scope (first value)

To establish a bounded architectural scope (entry points, contracts,
tests, explicit exclusions — never the whole repository): select one
root with structural discovery plus your own judgment (candidates
propose, you dispose — propose territories with the roster at
`integrations/hosts/roster.py`, which lists structural neighborhoods
without ranking them); run `explain(establish_baseline=True)` on that
root for a worklist, or question-local `explain` otherwise; work the
admitted questions in dependency order, preserving unexamined aspects
as OPEN/PENDING; close with an independent readback (fresh
`explain`/`status` on the scope) plus a reuse check (representative
questions answered from persisted coverage). A populated store alone
is not success — demonstrate retrieval. READY means operational, never
known.

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
  result via `submit_interpretation`. The unit carries a `brief`
  (`material_aspects` from the C-04 class row, scope boundaries,
  OPEN handling, submission rules): follow it for *this slice* and
  never broaden the slice silently. The brief is guidance, not
  authority — a wrong brief followed faithfully still yields a wrong
  answer, and validation never blesses content because the brief
  says so. A submit may return the
  final answer or the next pending unit; keep submitting until an
  answer returns. `submit_interpretation` is exchange, never a
  question class.
- Hosts embedding this loop (rather than hand-rolling continuation
  handling) use the canonical driver
  (`integrations/hosts/exchange_driver.py`: `drive()`): it runs
  serial submit-until-answer with measured cost, reports validation
  rejections without retrying them, and reissues only expired
  continuations through the idempotent original operation.
- Review every unit as a skeptic before submitting (host review,
  pre-submit): reject paraphrase-only results that reword without
  advancing knowledge — return them unsubmitted, or submit the
  question as OPEN/PENDING, rather than persisting motion without
  meaning. Check every material leg of the admitted slice is
  substantiated; leg-open what is not instead of declaring a partial
  answer complete. Validation cannot do this for you: it checks
  shape, refs, and quotes, never leg coverage or entailment.
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
