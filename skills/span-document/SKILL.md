---
name: span-document
description: Build evidence-backed understanding of one scope level by level with Span, ending in an explicit gap ledger.
---

# Span — semantic documentation of a scope

Use this specialization for directory, subsystem, workflow, or governed
document understanding. The primary `skills/span/SKILL.md` is authoritative
for operation selection, repository identity, readiness, evidence admission,
continuation recovery, target accounting, freshness, and closeout. This file
adds only the documentation-area procedure.

## Procedure

1. If the user supplied an exact directory, preserve that complete target boundary. Do not ask for a smaller representative root or silently narrow
   the work. Follow the primary skill's readiness and `initialize_target`
   path; an `UNINITIALIZED` repository needs `initialize_repository` in its
   dedicated setup session.
2. Map the target structurally before assigning meaning. Use `locate` for the
   file outline, symbol inventory, and `TARGET_MEMBERS`; use `neighbors` for
   bounded structural adjacency. These operations provide navigation evidence
   only. Do not treat a caller/callee edge as semantic causality, ownership,
   authority, or completeness.
3. Partition the complete boundary into coherent areas: subsystem,
   workflow/composition slice, service boundary, governed document area, or
   cross-boundary path. Grouping is an execution aid that must cover
   every material area. Split where ownership,
   authority, lifecycle, or material input-to-terminal paths diverge; merge
   only where one bounded analysis can substantiate the areas together.
4. Account for every target inventory member through the canonical
   `proposed_target_inventory_accounting` field. A member with no indexed
   subject may have `subject: null`; keep it as a full inventory member and
   assign, evidence-back exclude, or record an unresolved mapping requirement.
   Do not drop it because it lacks an anchor.
5. Admit each new material area with a `PENDING`
   `proposed_questions` entry, or reuse an identical persisted
   `SemanticQuestionScope` through `proposed_target_questions`. A semantic
   question's `NOT_APPLICABLE` disposition never excludes its inventory
   member. Use the primary skill's canonical submission and recovery path.
6. Interpret one bounded area at a time. Explain purpose, participants,
   material paths, authority boundaries, lifecycle, contracts, failures, and
   verification only from admissible evidence. Missing authority,
   contradictions, stale evidence, and unresolved mapping stay explicit.
7. Verify served knowledge with fresh `status(TargetId)` and exact-area
   `explain`/`trace`/`authority` readback. Do not claim completeness from one
   answer, a populated store, `READY`, a representative root, or structural
   `UNVERIFIED` evidence. The final gap ledger must list every remaining
   `OPEN`, `PENDING`, `UNRESOLVED`, `STALE`, `UNVERIFIABLE`, and unaccounted
   requirement.

## Area quality card

For each pending unit, use its brief and the primary skill's shared card:
objective; exact scope and exclusions; evidence and governing authority;
input-to-terminal path; typed result; adversarial check; explicit disposition;
and fresh readback. Claims alone do not complete a question. A paraphrase-only
result must remain unsubmitted or be recorded as `OPEN`/`PENDING` with its
requirement. Never convert uncertainty into certainty.

The supplied directory is the host-owned boundary, not automatically a Span
subject. Use an exact resolved file or symbol as the semantic anchor when the
provider exposes only those subjects, and preserve the rest of the coherent
area in the evidence scope. Never fabricate a directory or unresolvable
document identity; record a provider limitation as `OPEN`/`PENDING`.

## Expansion and closeout

If documentation reveals a material participant, contract, dependency, or
authority question outside the current area, establish that precise question
and submit it through the same canonical mechanism. Do not broaden the target
silently or create a second store, ledger, or quality policy.

After external verification, use the primary closeout sequence: scoped
`status`, scoped `refresh` with substantive re-submission where required, and
scoped `status` again. Report incomplete coverage honestly. Span never edits
code, runs tests, or selects a model.
