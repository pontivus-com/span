# Agent interpretation exchange (plan §5.4, §7, §11.12; Addendum B)

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
cardinality limits. Addendum B adds the immutable
`question: SemanticQuestionScope`, bounded `prior_claims` /
`prior_relationships` context, and service-owned
`analysis_obligations` (SA-2–SA-5). Nothing else crosses.

## One analysis contract (SA-1–SA-7)

SA-1 scope the exact subject/question; SA-2 establish evidence
(observed vs governing intent); SA-3 trace behavior and terminal
paths; SA-4 establish meaning in existing kinds only; SA-5
adversarial check; SA-6 submit one canonical result; SA-7 close with
question-scoped coverage. `ANSWERED` means recorded analysis, never
reviewer truth. CQ-01–CQ-09 are question classes with CQ-10
cross-cutting, not claim kinds.

## Entry modes

Question-local (default) answers the operation's applicable
questions. Baseline (`explain(establish_baseline=True)`) audits
CQ-01–CQ-09 for an explicitly selected root, admits bounded
`PENDING`/`OPEN`/`NOT_APPLICABLE` follow-ups, and resumes them in
deterministic order. `refresh` never silently expands scope.

## Result (`SemanticInterpretationResult`)

Typed candidate claims/relationships (unique keys), candidate
subjects, candidate conflicts, governing-source refs, diagnostics.
No new kinds. Authority arrives as `CandidateAuthority`: binding plus
`AuthoritySupport` (verbatim quote + locating sections) — the core
checks the account mechanically (resolves, belongs, quote substring,
sections resolve, no structural/confidence promotion) and never
verifies prose truth. Empty basis summaries fail the unit.

## Explicit completion (Addendum C C-05)

Claims alone never complete a question. A submission answers its
bound question only with an explicit `ANSWERED` coverage for that
exact question (`declared_complete` set; the service derives result
refs from validated candidates). Without explicit coverage the unit
persists `PENDING` and its claims stay unassigned output. Explicit
`ANSWERED` with zero validated material rejects the whole unit.
Only complete replacement retires unshared prior outputs;
`PENDING`/`OPEN`/`NOT_APPLICABLE` never retire by omission, and the
store refuses `ANSWERED` rows with empty result refs.

## Failure classes (Span-observable only)

`InterpretationSuccess` · `InterpretationUnavailable` (unknown/expired
continuation; re-issue the idempotent original op) ·
`InterpretationIngressFailure` (identical task reissued at most once;
second failure abandons) · `SemanticValidationFailure` (whole unit
rejected, no salvage, continuation abandoned). Provider transports,
HTTP statuses, and model errors belong to the agent's environment and
never enter Span's failure model. Continuations are single-use,
TTL-bounded (30 min default), never persisted, never authoritative.
