# Span — semantic documentation of a scope

Produce governed understanding of one scope (directory, subsystem, or
workflow): level by level, with evidence, ending in an explicit gap
ledger — never false completeness. Span answers from indexed
evidence; it never edits code, runs tests, or decides for you.

## The cold-start order (structure before meaning)

A fresh scope is a chicken-and-egg problem: interpretation needs
targets, and targets come from the map. So map first, interpret
second, synthesize last. Never top-down: no synthesis before member
knowledge exists.

```
map         orient with existing repository context plus bounded trace
            edges (the structural port has no repository-wide
            enumerate/map; `status` never enumerates subjects)
symbols     explain each key symbol, submit, verify served
modules     explain each key file, submit purpose plus responsibility
subsystem   explain(establish_baseline=True) on the exact root for the
            CQ-01–CQ-09 audit, then admitted member questions in
            dependency order; register semantic-only scope subjects
            through evidence-backed CandidateSubject on an existing
            structural entrypoint; synthesize only on established
            member evidence, verify served by exact locator
govern      explain authority subjects as found; record ownership
            only where evidence names it
verify      status scoped to the finished subjects; refresh if stale;
            ledger every remaining requirement as the completeness record
```

Use `explain` to orient, `submit_interpretation` to close each unit
(a submit may return the next unit; keep submitting until an answer
returns), `trace` / `authority` where the question needs them,
`status` to verify, `refresh` explicitly to close. Claims alone never
complete a question: each answering submission carries explicit
`ANSWERED` coverage for its bound question (Addendum C C-05).
Setup stays explicit: an `UNINITIALIZED` repository needs
`initialize_repository` in a dedicated setup session.

## Granular levels (what to record where)

- **Symbol** (function, class): what it is for, with a verbatim
  quote; plus verification currency where a test pins it.
- **Module** (file): what it is for plus what belongs in it and why.
- **Subsystem** (workflow, directory): register it as a subject under
  its scope path, then record one synthesis covering kickoff,
  execution, validation, and conclusion, citing member evidence.
  Membership is stated alongside, never assumed.
- **Governance** (methodology, envelopes, rules): governing bindings
  as found, with their standing exactly as evidenced. Ownership only
  where evidence names it; otherwise it stays explicitly unresolved.

## Completeness-correctness (the bar)

Complete means every key subject in scope has a stored answer or an
explicit unresolved requirement naming what would resolve it.
Correct means every stored item is quote-backed, trust-calibrated,
and freshness-tracked. All-green is not the bar: an honest
`UNRESOLVED` with a requirement beats an invented answer, and stale
items need `refresh`, not reinterpretation by hand.

## Rules

- Uncertainty is never certainty: `PARTIAL`, `AMBIGUOUS`,
  `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` results must
  be reported as such and never reinterpreted into a firm answer.
  Missing authority stays missing.
- Decline irrelevant units explicitly: anchor search can return noise
  (logs, bundles); say so in the submission diagnostics and cite only
  what the question needs. Never stretch a quote to cover more than
  it states.
- Targets are canonical selectors with exact ids once known; bounds
  may be omitted for service defaults. A listing token pages one
  truncated listing; a continuation resumes one suspended
  interpretation — never substitute one for the other.
- Agree scope size with the user first: one subsystem per pass is
  plenty. Stop when key subjects are covered and gaps are ledgered;
  record what was deliberately left out.

## Expansion identification

Documenting a scope often surfaces materially new knowledge (an
unnamed owner, an undocumented consumer, a shadow contract). When it
does: establish the precise material question first, admit it under
the existing identity/scope rules through the canonical submission
path, and retrieve it later to confirm. See the Expansion section of
`skills/span/SKILL.md`. Never broaden territory silently; never invent
a second store, writer, or quality bar for expansions.
