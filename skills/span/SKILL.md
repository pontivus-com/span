---
name: span
description: Understand a repository with Span before changing it: orient, establish, prepare, investigate, verify, and close through the canonical operations, keeping unresolved knowledge explicit.
---

# Span — semantic repository lifecycle

Span answers from indexed evidence and owns the task contract, validation,
freshness, and persistence. The agent owns interpretation and every edit. Span
never edits the target, runs application tests, selects a model, or decides a
semantic claim. `store_readiness: READY` proves operational readiness only; it
is never semantic coverage, correctness, or completeness.

## Start here

Pick one branch. No status preflight is required: semantic operations check
initialization themselves.

1. **Ordinary orientation** — `explain` on the chosen target. Use `status`
   only when coverage or freshness is the actual objective. Never `refresh`
   on first contact.
2. **Exact user-supplied directory plus objective** — `initialize_target` once
   with the complete exact `EvidenceScope` and objective; process every
   returned unit.
3. **Post-change closeout** — scoped `status` on the exact mutated scope,
   outside tests/review, scoped `refresh` and re-submission where required,
   then scoped `status` again.

Discover the exact canonical registered `repository_id` from MCP `tools/list`
or a successful `initialize_repository` response. Never pass a filesystem path
as the ID, and never translate one. If `store_readiness` is `UNINITIALIZED`,
run `initialize_repository` once in its dedicated setup session; do not
initialize it again to orient a session. An automatic `HOOK_FAST` notice is
event-local scope only and never means the repository is clean.

## Operations

| Agent intent | Operation | Use it when | You get |
| --- | --- | --- | --- |
| Dedicated repository setup | `initialize_repository` | Readiness is `UNINITIALIZED` | Canonical repository ID; no interpretation |
| Establish an exact user target | `initialize_target` | The user supplied a complete exact target and objective | `TargetId` and bounded units covering every inventory member |
| Read coverage and freshness | `status` | Currency or coverage is the objective | Read-only inventory, requirements, freshness; never interpretation |
| Understand behavior or purpose | `explain` | You need meaning for a subject | Answer, or one bounded pending unit |
| Find structure | `locate` | You need identity, an outline, or target members | Navigation evidence only |
| Explore adjacency | `neighbors` | You need bounded callers, callees, or edges | Navigation evidence only, never causation |
| Established execution flow | `trace` | You need producers, carriers, consumers, boundaries, or lifecycle | Established relationship answer or unit |
| Governing sources | `authority` | You need applicability, precedence, or conflicts | Authority evidence or unit; never inferred from adjacency |
| Proposed change | `impact` | A material change has a target and `change_kind` | Pre-change brief (impacts, conditions, authority, verification, blockers); never approval |
| Re-examine stale or challenged understanding | `refresh` | A scoped answer is stale, or an exact persisted question is challenged | Reinterpretation of only that scope |
| Submit a pending unit | `submit_interpretation` | You hold a live continuation and a typed result for its exact request | Answer or next unit; success consumes the continuation |

There are exactly these eleven public operations and no aliases. `NORMAL`
`status` reports bounded persisted coverage; `HOOK_FAST` reports only the
event-local notice, so a `READY 0/0` notice never describes the repository.
`locate` takes one mode: `SYMBOL` (requires `query`, with `EXACT` or
`CONTAINS`), `FILE_OUTLINE` (one file, no mode), or `TARGET_MEMBERS` (exact
target, no query). Page and continuation tokens are opaque: pass each
unchanged to the same operation with the same arguments, and never decode,
edit, or synthesize one.

## Exact target

A user-supplied exact directory is the complete target boundary, even when it
is large; structural anchors never narrow it. `initialize_target` admits the
target deterministically: Span assigns every current inventory member to the
target's area, records membership, and returns the area's first question.
Membership is never submitted, and there is no mapping unit or payload. Span
creates the first-admission CQ-01 seed itself; do not manufacture it.

`proposed_target_questions` associates an identical already-persisted
`SemanticQuestionScope` with the target; do not manufacture a duplicate
question. `status(TargetId)` in `NORMAL` mode is the campaign snapshot: its
`target_total_count` is `None` when the disposition is `UNVERIFIABLE` or
`UNASSESSED`, never a fabricated zero. Do not count a campaign by walking
`locate` pages. `CURRENT` requires complete, current, verifiable coverage over
the admitted members.

## One pending unit

When an operation returns `PendingInterpretation`, do only that bounded unit.

1. Read its `request` and `brief`: objective; exact scope and exclusions;
   admitted evidence and authority; material path; typed result; adversarial
   check; disposition; fresh readback. The brief guides; it does not make a
   wrong interpretation correct.
2. Cite only admitted evidence. Take the canonical `EvidenceRef` from
   `request.task_evidence.evidence_units`; never fabricate a locator,
   fingerprint, subject, or authority citation. Provider-backed current
   evidence may be admitted through validation even when it was not previously
   persisted.
3. Build the typed result (`SemanticInterpretationResult`) in the shapes
   `tools/list` publishes, starting from the minimal template in
   `request.brief.submission_rules`. Every claim needs `assertion_nature` and
   admitted evidence; source code supports observed behavior, not a normative
   rule merely because it sits nearby. Include the explicit `question_decision`
   this unit requires.
4. Before submitting, check alternate owners, omitted participants,
   contradictions, unsupported routes, stale premises, missing authority, and
   every material leg. A paraphrase-only result stays unsubmitted, or is
   `OPEN`/`PENDING` with its requirement.
5. Submit under the continuation, follow the next unit if one returns, and read
   the persisted result back. One answer, a populated store, or `READY` is
   never completion.

Outside `refresh`, `proposed_questions` admits genuinely additional questions.
Inside a `refresh` unit, a non-bound question is a correction nomination and
must already be persisted; a new question enters through the operation that
binds it, not through refresh. `proposed_target_questions` reuses an identical
persisted scope. `ANSWERED`
needs at least one claim or relationship; missing governing authority is a
resolution requirement, not a reason to withhold a supported assertion.
`NOT_APPLICABLE` with a basis is the terminal form for "no assertion is
warranted". Claims alone never complete a question: the explicit decision
completes it. Keep `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`, `UNRESOLVED`, `STALE`,
and `UNVERIFIABLE` verbatim. Never convert uncertainty into certainty.

## Continuation recovery

| Outcome | Continuation | Action |
| --- | --- | --- |
| Malformed payload or schema/transport rejection | live | Correct and resubmit under the same continuation |
| Semantic validation rejection | live | Correct the named content and resubmit |
| Unreadable or unverifiable evidence | live until expiry | Correct the evidence, or submit an unresolved disposition |
| In-process persistence failure before commit | retained | Investigate; retry only when safe, same continuation |
| Successful commit | consumed | Use the answer or next unit; never replay it |
| Unknown, expired, lost, or consumed | not reusable | Recover from the question's stored recovery inputs when recorded; otherwise `refresh` on the subject |
| Post-commit response loss | consumed; state may be durable | Re-run the original operation, or `refresh`, then inspect persisted progress |
| Crash with uncertain commit | lost | Same as above; trust canonical persisted state |
| Concurrent submission or in-flight token | unavailable | Do not compete; resolve the in-flight result |

There is no reissue operation. A malformed or rejected unit reuses the same
continuation after correction; a lost continuation is never reconstructed.
`status` names which recovery applies.

## Freshness, authority, and closeout

Structural and semantic freshness are separate. Structural `UNVERIFIED` can
support a positive orientation, but it cannot prove completeness or absence.
Semantic `STALE` explains what was previously known; it is not current
authority for a decision. `CURRENT` means stored dependencies are current and
verifiable, not that the meaning is correct or the target complete.

For a source change or an explicitly challenged `CURRENT` explanation, resolve
the exact persisted question and call scoped `refresh`. An unchanged-source
challenge uses `stale_only=false` with the exact `SubjectSelector` and exactly
one already-persisted original question. A refresh must be followed by
examination, submission where needed, and readback; the call alone proves
nothing. `impact` is preparation, not approval.

For a material edit, close out in this order: scoped `status` on the exact
mutated scope, external tests/review, scoped `refresh` with a substantive
re-submission where required, then scoped `status` again. Report remaining
`OPEN`, stale, unverifiable, or unaccounted work explicitly. Hooks only call
`status` in `HOOK_FAST`; they never initialize, interpret, refresh, rebuild, or
edit.

## Granularity and boundaries

Map the exact target structurally; establish a coherent baseline area; then
descend to member questions where a claim, contract, failure path, ownership,
authority, lifecycle, or unresolved requirement matters. Do not create one
semantic subject per file, and do not compress unrelated units into one root.

A user-supplied directory is host-owned scope, not automatically a resolvable
Span subject. When the provider exposes only a file or symbol anchor, use that
anchor and keep the rest in the evidence scope; record the provider limitation
as `OPEN`/`PENDING` rather than fabricating a directory or document subject.

`span-document` owns directory-level mapping and gap reporting;
`span-change-context` owns pre-change `impact` and change closeout. Both defer
operation selection, identity, evidence, recovery, and this lifecycle to the
present skill.
