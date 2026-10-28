---
name: span-document
description: Build evidence-backed understanding of one scope level by level with Span, ending in an explicit gap ledger.
---

# Span — semantic documentation of a scope

Use this for directory, subsystem, workflow, or governed-document understanding.
The primary span skill is authoritative for operation selection, repository
identity, readiness, evidence, recovery, target accounting, freshness, and
closeout; this file adds only the documentation procedure.

1. Preserve the complete target boundary. If the user supplied an exact
   directory, do not ask for a smaller representative root. Follow the primary
   skill's readiness and `initialize_target` path.
2. Map the target structurally first with `locate` (`FILE_OUTLINE`,
   `TARGET_MEMBERS`) and `neighbors`. These return navigation evidence only; a
   caller/callee edge is not semantic causality, ownership, authority, or
   completeness.
3. Partition the complete boundary into coherent areas: subsystem,
   workflow/composition slice, service boundary, governed-document area, or
   cross-boundary path. Grouping must cover every material area. Split where
   ownership, authority, lifecycle, or material input-to-terminal paths
   diverge; merge only where one bounded analysis can substantiate the areas
   together.
4. Membership is admitted for you: `initialize_target` assigns every inventory
   member to the area and returns its question. A member with no indexed
   subject is still a member; do not invent a subject for it and do not submit
   membership.
5. Admit a genuinely additional material question through `proposed_questions`
   (never inside a refresh unit, where a proposal must already be persisted);
   Span creates each new area's first-admission CQ-01 seed itself; do not manufacture it. Use
   `proposed_target_questions` only to reuse an identical persisted
   `SemanticQuestionScope`. A question's `NOT_APPLICABLE` disposition never
   excludes its inventory member.
6. Interpret one bounded area at a time. Explain purpose, participants,
   material paths, authority boundaries, lifecycle, contracts, failures, and
   verification only from admissible evidence. Keep missing authority,
   contradictions, stale evidence, and unresolved questions explicit.
7. Verify with fresh `status(TargetId)` and exact-area
   `explain`/`trace`/`authority` readback. One answer, a populated store,
   `READY`, a representative root, or structural `UNVERIFIED` evidence never
   proves completeness. The final gap ledger lists every remaining `OPEN`,
   `PENDING`, `UNRESOLVED`, `STALE`, `UNVERIFIABLE`, and unaccounted
   requirement.

For each pending unit, use its brief and the primary skill's pending procedure:
objective; scope and exclusions; evidence and authority; input-to-terminal
path; typed result; adversarial check; explicit disposition; fresh readback.
Claims alone never complete a question. A paraphrase-only result stays
unsubmitted or is recorded as `OPEN`/`PENDING` with its requirement. Never
convert uncertainty into certainty.

The supplied directory is host-owned scope, not automatically a Span subject.
Use an exact resolved file or symbol as the semantic anchor when the provider
exposes only those, and preserve the rest of the coherent area in the evidence
scope. Never fabricate a directory or unresolvable document identity; record a
provider limitation as `OPEN`/`PENDING`.

If documentation reveals a material participant, contract, dependency, or
authority question outside the current area, establish that precise question and
submit it through the same canonical mechanism. Do not broaden the target
silently or create a second store, ledger, or quality policy.

Close out in the primary skill's order: scoped `status` on the exact affected
scope, outside tests/review, scoped `refresh` with substantive re-submission
where required, then scoped `status` again. Report incomplete coverage honestly.
Span never edits code, runs tests, or selects a model.
