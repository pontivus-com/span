---
name: span
description: Understand a repository with Span before changing it: orient, establish, prepare, investigate, verify, and close through the canonical operations, keeping unresolved knowledge explicit.
---

# Span — semantic repository lifecycle

Use Span's canonical operations to understand a repository before you
change it. Span answers from indexed evidence; it never edits code,
runs tests, or decides for you.

## Operation lifecycle

```
orient      explain <target>
establish   initialize_target <exact boundary + objective>
prepare     impact <target + change>
investigate trace / authority (only where required)
implement   external editing tools (Span never edits)
verify      status + external tests/review
close       refresh, then status
```

Exact onboarding path: `docs/onboarding-runbook.md` (Addendum E §§4A/6).

## Uniform semantic-quality card (every lifecycle write)

Use the same short sequence for establishment, ordinary questions,
impact/trace/authority follow-ups, expansion, refresh, maintenance, and
closeout. Follow the pending request's `brief`; it is the canonical projection
of this sequence for the exact admitted slice:

1. **Objective:** what user decision or engineering question must this answer
   support?
2. **Scope:** exact root, subjects, boundaries, exclusions, and question.
3. **Evidence / authority:** evidence examined, governing sources, and the
   difference between observed behavior and intended rule.
4. **Material path:** input → producer → transformation/state →
   consumer/output → terminal/failure.
5. **Semantic result:** existing typed claims and relationships only, each
   supported by admissible evidence.
6. **Adversarial check:** alternate owner, contradiction, omitted participant,
   unsupported route, stale premise, and missing verification.
7. **Disposition and readback:** `ANSWERED`, `OPEN`, `PENDING`, or
   `NOT_APPLICABLE` with requirements for gaps; then verify what a fresh query
   can retrieve.

This is a working projection, not a second schema, hidden reasoning record, or
claim-count test. Keep it as small as the bounded question permits. Never
silently broaden the slice, turn missing work into completion, or present stale
or unverifiable knowledge as current.

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

Bind the user's explicit onboarding intent first — exactly these four,
no second onboarding skill exists:

For first-value work, bind the user's explicit target and objective. An exact directory or repository path supplied by the user is already the semantic
scope: do not ask the user to choose a smaller representative root and do not
silently reduce the target to one file or one subsystem. A request with no
target, or with an ambiguous target, needs a small scope choice before
establishment. Installation alone never starts this procedure.

- **Installation only:** complete A1 and report the host-exchange and
  establishment steps not performed.
- **Installation plus first-value:** complete A1, execute A2 through
  actual host MCP calls, and proceed into B.
- **Existing installation with first-value request:** check readiness
  and existing coverage, then begin at A2/B as appropriate without
  reinstalling.
- **Existing partial baseline:** reuse persisted coverage and continue
  the unresolved material work; never re-establish what is already
  durably answered.

For an explicit directory target, establish the complete target scope. The
directory is bounded by the user's path, even when it is large. Use structural
and filesystem discovery to partition the target into manageable material
areas; the partition is an execution technique, not a semantic exclusion.
Every contained material area must receive an answer, an explicit
`NOT_APPLICABLE` disposition, or an `OPEN`/`PENDING` requirement. Any
exclusion must be evidence-backed and reported. Never claim completion from a
single representative root.

### Semantic-analysis granularity

Use three levels, with no fixed file or claim count:

1. **Map level:** enumerate the supplied target's directories, modules, files,
   symbols, contracts, tests, configuration, and material entry/exit paths.
   This is structural orientation, not semantic completion.
2. **Baseline level:** choose a semantic architectural unit—a subsystem,
   workflow/composition slice, service boundary, or governed document area—with
   a coherent purpose, participants, material path, owner/authority boundary,
   and lifecycle. Establish one bounded root for that unit and record its
   member areas and exclusions.
3. **Member-question level:** descend to a file, symbol, relationship, or
   cross-boundary path when it carries a material claim, participant,
   contract, failure path, authority dependency, or unresolved requirement.
   Use the existing question-local exchange for that exact slice.

Do not create one semantic subject per file merely because it exists, and do
not compress unrelated units into one root merely to reduce work. Split a
partition when ownership, authority, lifecycle, or material input-to-terminal
paths diverge; merge only when one bounded analysis can substantiate them
together. Every mapped area still receives semantic coverage or an explicit
`NOT_APPLICABLE`/`OPEN`/`PENDING` disposition.

**Span subject anchors:** the user-supplied directory is the host-owned
boundary, not necessarily a structural `SubjectId`. With the Graft provider,
an exact semantic exchange normally anchors on a resolved source file or code
symbol; the architectural baseline may use that anchor while its evidence
scope names the complete coherent unit. Do not fabricate a directory/document
subject when the provider cannot resolve one. Record the unmapped area as an
explicit `OPEN`/`PENDING` requirement (or `NOT_APPLICABLE` with evidence), and
continue only after selecting a real anchor or recording the provider
limitation. A generated graph/index is derived evidence and cannot replace its
source-owned anchor.

For a request without an exact target, establish one bounded architectural
scope (entry points, contracts, tests, explicit exclusions) only after the
user selects it:

At normal session orientation, call `status` with no target and read the
repository-level semantic-coverage inventory when the ACT-D-10 gate is
available. Use it to distinguish persisted/current knowledge from
`PENDING`/`OPEN`, stale/unverifiable, and unassessed frontier state before
choosing an exact target. The report is bounded and does not enumerate
structural subjects. If the runtime returns readiness only, report that as
the known Point 4 activation gap; do not infer that no semantic knowledge
exists, and continue with exact-target `status`/`explain` where needed.

Root and partition selection: use the user's stated objective, the exact
target boundary, existing structural candidates, authoritative contracts and
evidence, and `roster.py::propose_territories()` only as structural support
(no ranking and no importance judgment). For a directory target, cover every
partition and record the target boundary, material participants, and
evidence-backed exclusions in the session report and canonical question
coverage. Structural centrality never determines semantic importance. Where
no defensible partition can be selected, report the evidence or decision
required and leave the area `OPEN`; never fabricate or silently omit it.

Execution: initialize the repository root for operational readiness
(`initialize_repository`, operational only), then call `initialize_target`
with the user's exact `EvidenceScope` and objective → investigate the
returned typed unit →
`submit_interpretation` until it returns the next unit or final target status.
The MCP returns a bounded structural candidate frontier; do not recreate it
with an unbounded host-side file loop. Each target pending task carries the
exact target boundary separately from its structural anchor. Use that full
boundary to choose and report coherent semantic areas; an anchor is evidence
input, not a semantic-completion claim. Use `trace`, `authority`, `impact`,
and ordinary `explain` only where the admitted question requires them.
Preserve exact questions and unresolved aspects; do not discard a pending
continuation, listing page, or unresolved requirement. If a continuation expires, call
`reissue_interpretation` once, then submit the returned identical task.
Continue until the target operation returns its final status. Then
perform independent fresh-session `status`/`explain` readback and a reuse
check for representative questions from each material area. A
`PendingInterpretation`, a populated store, or `READY` is never completion.

## The MCP operation surface

initialize_repository, initialize_target, explain, impact,
trace, authority, status, refresh,
submit_interpretation, and reissue_interpretation.

## Rules

- Repository setup is explicit: if readiness is `UNINITIALIZED`, run
  `initialize_repository` in a dedicated setup session. Normal
  queries and hooks never initialize. Readiness is operational, never
  semantic completeness.
- Entry modes: default `explain` is question-local and never claims
  baseline sufficiency. For an explicit directory initialization, use initialize_target once on the exact target and objective.
  process each target unit returned by the MCP frontier. For an ordinary
  selected root, use `explain(establish_baseline=True)` only for that scope.
  `refresh` never expands scope silently.
- When an operation returns a pending interpretation unit, perform the
  bounded SA-1–SA-7 task with your own model and submit the typed
  result via `submit_interpretation`. The unit carries a `brief`
  (the uniform objective/scope/evidence/material-path/result/adversarial/
  disposition/readback card, plus C-04 material aspects and recorded
  requirements): follow it for *this slice* and never broaden the slice
  silently. The brief is guidance, not
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
  continuations through the idempotent original operation. The driver
  is a helper for Python host integrations only — OpenCode and Codex
  agents call the registered `span` MCP tools directly (Addendum D
  §6). Neither installing a skill nor running the driver proves a
  real host connection; only an observed host MCP request/response
  does.
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
