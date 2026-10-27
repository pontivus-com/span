# Agent interpretation exchange

Span never selects, configures, authenticates to, or invokes a model.
When stored/current semantics are insufficient, the operation
suspends with a `PendingInterpretation{continuation, request}`; the
invoking LLM-connected agent interprets under the bounded contract
and submits via `submit_interpretation`; Span validates,
materializes, and resumes — returning the final `SemanticAnswer`, or
the next `PendingInterpretation` while frontiers remain.

## Request (`SemanticInterpretationRequest`)

Repository id, target subjects, bounded evidence units, bounded
structural observations, allowed kinds, live identity bindings,
operation intent, question slice, optional typed proposal, output
cardinality limits. The exchange adds the immutable
`question: SemanticQuestionScope`, bounded `prior_claims` /
`prior_relationships` context, and service-owned
`analysis_obligations` (SA-1–SA-7). It also adds the service-built
`brief` (`TaskBrief`): the compact objective, exact scope, evidence/authority,
material-path, typed-result, adversarial-check, disposition, and fresh-readback
guidance, plus C-04 material aspects and recorded OPEN/PENDING requirements.
The exact user-directed `target_scope` is carried separately from the
current structural anchor, so a bounded candidate is never mistaken for the
whole semantic target. Target-mode work carries the target association:
membership is computed at admission from the provider inventory and is never
submitted, so there is no inventory-accounting proposal in the result
exchange. It is distinct from semantic-question `NOT_APPLICABLE` coverage.
The brief is guidance, never validated content and never submitted back (the
result carrier has no brief field). Nothing else crosses.

## One analysis contract (SA-1–SA-7)

SA-1 scope the exact subject/question; SA-2 establish evidence
(observed vs governing intent); SA-3 trace behavior and terminal
paths; SA-4 establish meaning in existing kinds only; SA-5
adversarial check; SA-6 submit one canonical result with explicit
disposition; SA-7 close with fresh question-scoped readback. `ANSWERED`
means recorded analysis, never reviewer truth. CQ-01–CQ-09 are question
classes with CQ-10 cross-cutting, not claim kinds.

The same contract applies at target initialization and during ordinary
question-local work. When a user supplies an exact directory, the active
host partitions that directory for execution but analyzes every material
partition. It does not substitute one representative root, silently exclude
areas, or treat structural readiness as semantic completion.

## Entry modes

Question-local (default) answers the operation's applicable
questions. Baseline (`explain(establish_baseline=True)`) audits
CQ-01–CQ-09 for an explicitly selected root, admits bounded
`PENDING`/`OPEN`/`NOT_APPLICABLE` follow-ups, and resumes them in
deterministic order. `refresh` never silently expands scope.
Exact user-supplied directory targets use `initialize_target` per
`docs/onboarding-runbook.md`, not the baseline path.

## Result (`SemanticInterpretationResult`)

Typed candidate claims/relationships (unique keys), candidate
subjects, candidate conflicts, governing-source refs, target-inventory
accounting proposals for target-mode tasks, and diagnostics.
Question semantics travel in `question_decision` for the already-bound
question and `proposed_questions` for questions the agent introduces or
explicitly nominates; `InterpretationCoverage` is never the agent command.
No new kinds. Authority arrives as `CandidateAuthority`: binding plus
`AuthoritySupport` (verbatim quote + locating sections) — the core
checks the account mechanically (resolves, belongs, quote substring,
sections resolve, no structural/confidence promotion) and never
verifies prose truth. Empty basis summaries fail the unit.

## Explicit completion

Claims alone never complete a question. A submission answers its
bound question only with an explicit `ANSWERED` `question_decision`
(the service derives result refs and question evidence from validated
candidates and admitted evidence). Without
explicit decision the unit persists `PENDING` and its claims stay
unassigned output. Explicit `ANSWERED` with zero validated material
rejects the whole unit.
Only complete replacement retires unshared prior outputs;
`PENDING`/`OPEN`/`NOT_APPLICABLE` never retire by omission, and the
store refuses `ANSWERED` rows with empty result refs. A semantic question's
`NOT_APPLICABLE` disposition does not exclude an inventory member from an
exact target; target exclusion is target-inventory accounting with its own
evidence basis.

## Failure classes (Span-observable only)

`InterpretationSuccess` · `InterpretationUnavailable` (unknown/expired
continuation; re-issue the idempotent original op, including a selected
operation whose persisted question is still `PENDING`) ·
`SemanticValidationFailure` (whole unit rejected, no salvage; the live
continuation remains usable for a corrected submission). There is no
reissue operation and no ingress-failure exchange class. Provider transports,
HTTP statuses, and model errors belong to the agent's environment and
never enter Span's failure model. Continuations are single-use,
TTL-bounded (30 min default), never persisted, never authoritative.

## Interpretation profile

- The static SA obligations live in the tool contract, not in every unit.
- Target admission computes `TargetInventoryAccount` from the provider
  snapshot and assigns every member to the target's area; membership is never
  an agent submission.
- A newly admitted area with no reusable current question receives exactly
  one service-owned `PENDING` CQ-01 first-admission seed; the agent is never
  required to manufacture it.
- Mapping binds a bounded batch of inventory members per unit; every bound
  member receives exactly one disposition, atomically.
