---
name: span
description: Understand a repository with Span before changing it: orient, establish, prepare, investigate, verify, and close through the canonical operations, keeping unresolved knowledge explicit.
---

# Span — semantic repository lifecycle

Use Span's canonical operations to understand a repository before you
change it. Span answers from indexed evidence; it never edits code,
runs tests, or decides for you.

## Entry decision (read first)

Three branches, no others. Pick one before calling anything:

1. **Ordinary orientation** (browsing, understanding, no user-given
   target): `status` with no target, then `explain` on the chosen
   target. Never `refresh` on first contact.
2. **Exact user-supplied directory plus objective**: `initialize_target`
   once with the exact `EvidenceScope` and objective; process each
   returned unit until the target operation answers.
3. **Post-change closeout** (you mutated code): scoped `status` on the
   exact mutated scope; `refresh` only the scope that reads noncurrent;
   `status` again to confirm.

`locate`/`neighbors` enter when structural orientation is actually
needed (find a symbol, outline a file, walk adjacency). Everything
else (`trace`, `authority`, `impact`, submit/reissue) follows the
admitted question, never curiosity.

## Operation lifecycle

```
orient      status (no target), then explain <target>
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
directory is bounded by the user's path, even when it is large. Call
`initialize_target` with the exact scope and objective; it returns the
deterministic `TargetId` campaign handle and mapping work for unaccounted
inventory (`question=None`). Partition into coherent areas (multiple files may
map to one area; one file may map to more than one area); the partition is an
execution technique, not a semantic exclusion. First admission of an area to
this target requires a `PENDING` question or reuse of persisted coverage via
`proposed_target_questions`. Every contained material area must receive an answer, an explicit
`NOT_APPLICABLE` disposition, or an `OPEN`/`PENDING` requirement, with
no unvisited material partition left unrecorded. Any
exclusion must be evidence-backed target accounting (not question
`NOT_APPLICABLE`) and reported. Read campaign state only via
`status(TargetId)` (`NORMAL` only); retrieve areas via exact `SubjectId`s.
Membership changes re-enter via `initialize_target`; content changes use
`refresh`. Never claim completion from a single representative root.

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
partition and record the target boundary, material participants, and typed
target-inventory accounting separately from canonical question coverage.
Structural centrality never determines semantic importance. Where
no defensible partition can be selected, report the evidence or decision
required and leave the area `OPEN`; never fabricate or silently omit it.

Execution: initialize the repository root for operational readiness
(`initialize_repository`, operational only), then call `initialize_target`
with the user's exact `EvidenceScope` and objective → investigate the
returned typed unit →
`submit_interpretation` until it returns the next unit or final target status.
For target-mode submissions, use the typed result's target-inventory
accounting component for assignment, evidence-backed target exclusion, or
unresolved mapping. A semantic question's `NOT_APPLICABLE` disposition does
not exclude its inventory member. Span validates and persists accounting,
admitted subjects, semantic results, and target-bound coverage atomically.
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
submit_interpretation, reissue_interpretation,
locate, and neighbors.

Structural questions go to Span, not to a separate tool: `locate` finds
symbols, outlines files, and lists target members; `neighbors` walks
bounded caller/callee adjacency. Both return navigation evidence only —
cite it as evidence, never as authority. Arbitrary in-body content
search stays with your own grep; Span does not duplicate it.

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
- Target-inventory accounting and semantic-question coverage are separate.
  Every material inventory member must be assigned to an admitted area,
  evidence-backed excluded from the exact target, or left with an explicit
  unresolved mapping requirement. `NOT_APPLICABLE` applies only to its bound
  semantic question and cannot serve as a target-exclusion record.
- A listing token (`page_token`, now `pg:<claims>:<rels>:<questions>`)
  pages truncated listings including question coverage. A
  continuation resumes one suspended interpretation. They are
  different mechanisms; never substitute one for the other.
  Inventory sweeps stay few-round by requesting wider bounds
  (`max_results` up to 250) instead of walking default pages;
  defaults stay small to protect every caller's token budget.
- Uncertainty is never certainty: `PARTIAL`, `AMBIGUOUS`,
  `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` results must
  be reported as such and never reinterpreted into a firm answer.
  Missing authority stays missing; conflicts stay side-by-side until
  declared precedence resolves them.
- `refresh` is explicit. Hooks only report readiness/staleness
  (`status` with `HOOK_FAST`) and never refresh, interpret,
  rebuild, or initialize. `HOOK_FAST` sees event-local scope only:
  a `0/0 READY` notice never means the repository is clean — use
  `NORMAL` `status` for the persisted coverage inventory.
- Targets are canonical selectors: `{"$type": "SubjectSelector", ...}`
  with an exact id, name/locator, or kinds. Bounds may be omitted for
  service defaults.

## Reading answers

Every answer carries evidence pointers, per-claim freshness, and
requirements describing what would resolve incomplete knowledge.
Follow `resolution_requirements` before treating partial knowledge as
complete. Stale items need `refresh`, not reinterpretation by
hand.

Two freshness planes, never one condition. Structural `UNVERIFIED`
(dirty tree, old index) is still usable as positive orientation
evidence — a found caller is a real caller — but never proves
completeness or absence ("no other callers" needs `VERIFIED`).
Semantic `STALE` shows what was previously known; read it for
orientation, refresh it before relying on it for change. A dirty
tree alone never stales claims whose evidence is unchanged.

## Appendix G-A: operation selection (Addendum G §4.7)

Twelve operations, no merger. Setup (`initialize_repository`) is
separate from ordinary queries. Structural discovery (`locate`,
`neighbors`) returns evidence only, never semantic claims. Semantic
investigation (`explain`, `authority`, `trace`) answers from persisted
coverage or suspends honestly. Change assessment (`impact`) needs a
proposal with `change_kind`, `change_description`, and
`affected_assertions`. State inspection (`status`) is read-only;
maintenance (`initialize_target`, `refresh`) is explicit and scoped.
Exchange (`submit_interpretation`, `reissue_interpretation`) advances
one bounded unit at a time.

Rules: file, symbol, or member list → `locate`; structural adjacency →
`neighbors`; established semantics → `trace`; behavior → `explain`;
governance → `authority`; change consequences → `impact`; campaign with
exact scope plus objective → `initialize_target`; stale scope →
`refresh`; coverage check → `status`. Baseline
(`explain(establish_baseline=True)`) audits an ordinary selected root;
`initialize_target` campaigns an exact user-supplied directory. Do not
substitute one for the other.

## Appendix G-B: evidence and authority quality (Addendum G §4.4)

Code first, always: purpose, implementation, consumption, production,
and flow are established from code spans plus bounded interpretation
alone — no document required, and their reliability never depends on
documentation. Authority enters only for normative claims (ownership,
governance, must-not-reconstruct): cite the record or leave the claim
explicitly unresolved; never infer it from structure.
Prefer function or block spans over whole-file citation where the
provider supplies per-span excerpt and signature text. Cite tests,
contracts, and docs alongside code with existing `EvidenceSourceKind`
values. Whole-file
citation needs a basis stating the file-wide scope. Seeds enter only as
user-supplied `EvidenceRef` lists; unknown locators fail closed.
`CONTRACT_SPECIFICATION` supports representation and boundary,
`DECISION_RECORD` supports ownership and precedence,
`TEST_VERIFICATION` supports `VERIFIED_BY`. Link `VERIFIED_BY` only on
executed evidence with observed revision; candidate tests stay
`CANDIDATE`. Absent authority stays `PARTIAL`/`UNRESOLVED` with
`MISSING_AUTHORITY`. `trace`/`authority`/`impact` on uncovered subjects
suspend by design; follow the brief, do not invent a preview.

## Appendix G-C: OpenCode submit-until-answer loop (Addendum G §4.5)

Serial only, one repository scope per drive. Invoke the operation; while
the result is `PendingInterpretation`, interpret the bounded unit and
call `submit_interpretation` under its continuation. Validation
rejection halts with diagnostics for repair, never blind retry. Ingress
failure halts. Unknown or expired continuation reissues the idempotent
original operation once via `reissue_interpretation`, then submits the
returned identical task. Unexpected exceptions propagate visibly.
Caller states an explicit round budget; exhaustion halts. Installing a
skill and reading the driver never proves a host connection; only an
observed host MCP request and response does.
