---
name: span-document
description: Build evidence-backed understanding of one scope level by level with Span, ending in an explicit gap ledger.
---

# Span — semantic documentation of a scope

Produce governed understanding of one scope (directory, subsystem, or
workflow): level by level, with evidence, ending in an explicit gap
ledger — never false completeness. Span answers from indexed
evidence; it never edits code, runs tests, or decides for you.

## The cold-start order (structure before meaning)

A fresh scope is a chicken-and-egg problem: interpretation needs bounded
evidence, while semantic areas must be established by the host agent. So
discover structure first, establish canonical area subjects and target
accounting second, interpret questions third, and synthesize last. Never
top-down: no synthesis before member knowledge exists. When the user supplies
an exact directory, that directory is the complete target boundary; structural
discovery partitions it for execution and must not silently narrow it.

```
map         orient with existing repository context plus structural and
            filesystem discovery inside the explicit target; partition
            every material area for execution (normal `status` still
            reports persisted coverage, never structural subject enumeration)
symbols     explain each key symbol, submit, verify served
modules     explain each key file, submit purpose plus responsibility
subsystem   for an explicit directory, call initialize_target once with the exact target and objective,
            use the bounded discovery context to establish canonical area
            subjects and typed target-inventory accounting, then process
            every admitted area question in dependency order; register
            semantic-only scope subjects through evidence-backed
            CandidateSubject on an existing structural entrypoint; synthesize
            only on established member evidence, verify served by exact
            locator
govern      explain authority subjects as found; record ownership
            only where evidence names it
verify      status the bounded persisted frontier and finished subjects;
            refresh if stale;
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

- **Map:** enumerate directories, modules, files, symbols, contracts, tests,
  configuration, and material entry/exit paths inside the exact target. This
  establishes the structural frontier but is not semantic completion.
- **Baseline unit:** use a coherent subsystem, workflow/composition slice,
  service boundary, or governed document area with one purpose, participant
  set, material path, authority/ownership boundary, and lifecycle. Establish
  one bounded root, record target-inventory assignment or evidence-backed
  exclusion separately, and record semantic-question coverage for the area.
- **Member question:** descend to a symbol, module, relationship, or
  cross-boundary path when it carries a material claim, contract, failure path,
  authority dependency, or unresolved requirement. Use the exact question-local
  exchange and cite the member evidence.
- Do not create one semantic subject per file merely because it exists, and do
  not merge unrelated units merely to reduce work. Split when ownership,
  authority, lifecycle, or material input-to-terminal paths diverge; merge only
  when one bounded analysis can substantiate the units together.
- **Governance** (methodology, envelopes, rules): governing bindings
  as found, with their standing exactly as evidenced. Ownership only
  where evidence names it; otherwise it stays explicitly unresolved.

## Completeness-correctness (the bar)

Complete means every material inventory member in the explicit target has a
target-accounting assignment, an evidence-backed target exclusion, or an
unresolved requirement naming what would resolve the mapping, and every
admitted area has semantic-question coverage. A semantic question's
`NOT_APPLICABLE` disposition does not itself exclude inventory. A
representative root is not the target. No area or inventory member may be
silently omitted because the directory is large.
Correct means every stored item is quote-backed, trust-calibrated,
and freshness-tracked. All-green is not the bar: an honest
`UNRESOLVED` with a requirement beats an invented answer, and stale
items need `refresh`, not reinterpretation by hand.

## The same analysis card for every submitted unit

For symbols, modules, subsystems, governance, expansion, refresh, and
closeout, use the pending request's brief in this order: objective; exact
scope and exclusions; evidence and governing authority; input-to-terminal
material path; typed semantic result; adversarial check; explicit disposition
with requirements; and fresh readback. This is one compact working projection
of SA-1–SA-7, not a second schema or a claim-count test. Keep the scope
bounded, preserve OPEN/PENDING and stale or unverifiable state, and do not
declare useful coverage until a fresh query can retrieve it.

The supplied directory is the host boundary, not automatically a Span subject.
Use an exact resolved file or symbol as the semantic anchor when the structural
provider exposes only those subjects; include the rest of the coherent unit in
the evidence scope. Never invent a directory or unresolvable document identity.
If a material area has no structural anchor, preserve it as an explicit
`OPEN`/`PENDING` provider-boundary requirement rather than silently omitting it.

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
- If the user supplied an exact directory, do not ask them to reduce it
  to one subsystem and do not stop after one representative root. Work
  through all material partitions, preserving page tokens and pending
  continuations. Record every deliberate target-inventory exclusion with its
  evidence-backed accounting basis, separately from semantic-question
  dispositions. If no exact target was supplied, agree a bounded scope
  with the user first.

## Expansion identification

Documenting a scope often surfaces materially new knowledge (an
unnamed owner, an undocumented consumer, a shadow contract). When it
does: establish the precise material question first, admit it under
the existing identity/scope rules through the canonical submission
path, and retrieve it later to confirm. See the Expansion section of
`skills/span/SKILL.md`. Never broaden territory silently; never invent
a second store, writer, or quality bar for expansions.
