# Agent interpretation exchange (plan §5.4, §7, §11.12)

Span never selects, configures, authenticates to, or invokes a model.
When stored/current semantics are insufficient, the operation
suspends with a `PendingInterpretation{continuation, request}`; the
invoking LLM-connected agent interprets under the bounded contract
and submits via `span_submit_interpretation`; Span validates,
materializes, and resumes — returning the final `SemanticAnswer`, or
the next `PendingInterpretation` while frontiers remain.

## Request (`SemanticInterpretationRequest`)

Repository id, target subjects, bounded evidence units, bounded
structural observations, allowed kinds, live identity bindings,
operation intent, question slice, optional typed proposal, output
cardinality limits. Nothing else crosses.

## Result (`SemanticInterpretationResult`)

Typed candidate claims/relationships (unique keys), candidate
subjects, candidate conflicts, governing-source refs, diagnostics.
No new kinds. Authority arrives as `CandidateAuthority`: binding plus
`AuthoritySupport` (verbatim quote + locating sections) — the core
checks the account mechanically (resolves, belongs, quote substring,
sections resolve, no structural/confidence promotion) and never
verifies prose truth. Empty basis summaries fail the unit.

## Failure classes (Span-observable only)

`InterpretationSuccess` · `InterpretationUnavailable` (unknown/expired
continuation; re-issue the idempotent original op) ·
`InterpretationIngressFailure` (identical task reissued at most once;
second failure abandons) · `SemanticValidationFailure` (whole unit
rejected, no salvage, continuation abandoned). Provider transports,
HTTP statuses, and model errors belong to the agent's environment and
never enter Span's failure model. Continuations are single-use,
TTL-bounded (30 min default), never persisted, never authoritative.
