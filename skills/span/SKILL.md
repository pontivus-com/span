---
name: span
description: Understand a repository with Span before changing it: orient, establish, prepare, investigate, verify, and close through the canonical operations, keeping unresolved knowledge explicit.
---

# Span — semantic repository lifecycle

Span answers from indexed evidence and owns the task contract, validation,
freshness, and persistence. Span never edits a repository, runs application
tests, selects or invokes an LLM/provider, or decides semantic claims for the
agent.

## Agent quick reference

Use this path for every non-trivial Span interaction:

1. Discover the exact registered `repository_id` from MCP `tools/list` (or
   from a successful `initialize_repository` result). A filesystem path is
   never a repository ID; preserve the registered ID unchanged.
2. Semantic operations check store readiness and return canonical
   uninitialized/unavailable results themselves. Call normal `status` only
   when store readiness, coverage, or freshness is the actual objective.
   `store_readiness: READY` means operational storage readiness, not
   semantic coverage.
3. If `store_readiness` is `UNINITIALIZED`, run `initialize_repository` once in its
   dedicated setup workflow. If the repository is already initialized, do not initialize it again just to orient a session.
4. For an exact user-supplied directory plus objective, call
   `initialize_target` with that complete exact boundary. For ordinary
   orientation, call question-local `explain` directly; use
   `explain(establish_baseline=True)` only for an ordinary
   selected root, never as a substitute for exact-target onboarding.
5. When a call returns `PendingInterpretation`, inspect that one bounded
   request, use admissible canonical evidence, submit the typed
   `SemanticInterpretationResult`, and follow the returned next unit until an
   answer or truthful terminal state is returned.
6. Use `status` for read-only coverage and freshness readback. Status
   never initiates interpretation, allocates continuations, or persists
   freshness. Follow its entry guidance: stale/unverifiable → `refresh`
   with the exact `SubjectSelector` it names; `UNASSESSED` →
   question-local `explain` only when no owning operation is live; otherwise
   continue the returned continuation. Pending question work → only the
   continuation returned by the suspending operation. Inventory
   accounting and semantic-question coverage are separate. Preserve
   every `OPEN`, `PENDING`, `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`,
   `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` state.
   Schemas are generated from canonical types: construct submissions
   from `tools/list` schemas without reading implementation. Narrow
   questions accept `question_selection` (slice/basis/anchors only);
   anchors are literal substrings. Excerpts carry ranges and omissions;
   answers carry `state_explanation` with descriptive/normative counts.
7. For material edits, call `impact` before editing. Close out in one
   order: scoped `status` on the exact mutated scope, external tests/review,
   explicit scoped `refresh` and re-submit where required, then scoped
   `status` again. `impact` is preparation, not approval; `refresh` alone
   proves nothing.

Refresh lifecycle: `UNASSESSED → explain` only when no owning operation is
live; `STALE`/`UNVERIFIABLE → refresh` unless that refresh is already live;
an explicit CURRENT challenge uses `refresh(stale_only=false)` only for an
already-persisted question. Refresh never establishes first coverage.

MCP success results have both canonical text and structured output derived
from the same Span carrier. Status identifies live pending question state and
its owning operation without revealing continuation tokens. `READY` means
storage/runtime availability, not semantic completeness.

### Operation selection

| Agent intent | Operation | Select it when | Result/next action |
| --- | --- | --- | --- |
| Dedicated repository setup | `initialize_repository` | Readiness is `UNINITIALIZED`; use the setup workflow only | Reuse the returned canonical repository ID and check `READY`; no interpretation occurs |
| Establish exact user-supplied target | `initialize_target` | The user supplied a complete exact target and objective | Receive a `TargetId` and bounded mapping/semantic unit; preserve the complete boundary and submit units serially |
| Determine persisted understanding and currency | `status` | You need read-only repository, target, subject, or hook state | Examine coverage, counts, freshness, requirements, and bounds; it does not interpret or refresh |
| Understand behavior or purpose | `explain` | You need a semantic explanation of an established or selected subject | Retrieve the answer or interpret the bounded pending task |
| Find a file, symbol, or inventory member | `locate` | You need structural identity, outline, or target members | Use navigation evidence to choose an investigation slice; it does not establish meaning or completeness |
| Explore structural adjacency | `neighbors` | You need bounded callers, callees, or related structural edges | Use adjacency as evidence only; it is not semantic causality |
| Investigate established execution relationships | `trace` | You need producers, carriers, consumers, boundaries, or lifecycle | Retrieve or interpret that established relationship question; do not use it for raw structural enumeration |
| Identify governing sources | `authority` | You need normative sources, applicability, precedence, or conflicts | Retrieve or interpret authority evidence; never infer authority from adjacency |
| Assess a proposed change | `impact` | A material change has a target and `change_kind`; description and affected assertions are optional | Read the bounded pre-change brief and blockers; it never authorizes implementation |
| Re-examine stale or explicitly challenged understanding | `refresh` | A scoped answer is stale, or an exact persisted question is explicitly challenged | Reinterpret only the supplied scope; examine, submit, and read back the corrected result |
| Submit a pending interpretation | `submit_interpretation` | You hold a live continuation and a typed result for its exact request | Correct validation/evidence problems and resubmit under the same continuation; success consumes it and returns an answer or next unit |

`initialize_repository` is not routine session orientation. `status` is
read-only and differs in `NORMAL` and `HOOK_FAST`: `NORMAL` `status` reports a
bounded persisted coverage inventory, while `HOOK_FAST` reports only the
event-local notice. `HOOK_FAST` sees event-local scope only; it never means the repository is clean. A `HOOK_FAST` `0/0 READY` notice does not describe
the repository inventory.

The eleven public operations are exactly the operations in the table. There are no semantic aliases. `locate` and `neighbors` return structural
navigation evidence, not semantic claims. Pagination is opaque: pass a returned page token unchanged to the same
operation with the same request arguments. Interpretation is opaque: pass
the returned `continuation` unchanged to `submit_interpretation`. Never
decode, edit, increment, or synthesize either value.

`locate` takes exactly one mode. `SYMBOL` requires `query` and accepts an
optional `target` scope; `EXACT` resolves an exact locator to its
declaration/name with no partial matches, while `CONTAINS` returns
substring matches in provider order. `FILE_OUTLINE` requires one file
locator and takes no target scope or match mode. `TARGET_MEMBERS`
requires the exact `target` scope and takes no query.

## Entry decision

Pick one branch before making a semantic call:

1. **Ordinary orientation:** `explain` on the chosen target. Use `status`
   only when status or freshness is the actual objective; no status preflight
   is required because semantic operations check initialization themselves.
   Never `refresh` on first contact.
2. **Exact user-supplied directory plus objective:** preserve the complete
   exact boundary and call `initialize_target` once with the exact
   `EvidenceScope` and objective. Process every returned unit.
3. **Post-change closeout:** run scoped `status` on the exact mutated scope;
   refresh only the noncurrent scope, re-examine and submit its task, then run
   scoped `status` again.

If the MCP runtime returns `UNINITIALIZED`, stop normal work and use the
dedicated repository setup workflow first. An automatic `HOOK_FAST` notice
is event-local by design. A normal `status` or semantic operation that
returns store readiness only where coverage is expected is unexpected: record it,
do not infer that semantic knowledge is absent, and do not treat it as
cleanliness.

## Repository identity and store readiness

`repository_locator` identifies a repository during setup. It is not the
value used by repository-scoped operations. Never pass a filesystem path as
`repository_id`. Obtain the exact canonical registered ID from MCP
`tools/list`, or from the successful repository-initialization response, and
reuse that ID unchanged. Registered-ID examples are illustrations, not fixed
global identifiers. Do not add aliases or translate paths to IDs.

The lifecycle is:

1. Discover the registered canonical identity.
2. Determine store readiness.
3. Use the registered repository directly when it is initialized.
4. If it is `UNINITIALIZED`, perform `initialize_repository` in its dedicated
   setup session.
5. Begin the requested semantic operation or exact-target campaign only
   after store readiness is established.

Initialization provisions identity, structural source, evidence inventory,
authority seeds, and store schema. It performs no semantic interpretation.
`store_readiness: READY` proves operational readiness only; it does not
prove semantic
coverage, correctness, target accounting, or completeness.

## Exact-target establishment and accounting

An exact directory supplied by the user remains the complete target boundary,
even when it is large. Structural anchors are execution aids and never grant
permission to narrow that boundary.

`initialize_target` admits the target deterministically: Span enumerates
every current inventory member, assigns each to the target's area subject,
records the membership, and returns the area's first semantic question. Membership is
computed from the provider manifest; it is never submitted and never asked for
as a model unit. There is no mapping unit and no mapping payload.

The result components have different jobs:

- `question_decision` answers the bound semantic question. `ANSWERED` requires
  at least one claim or relationship; a claim supported by cited file evidence
  is a complete assertion, and missing governing authority is recorded as a
  resolution requirement rather than a reason to withhold it.
  `NOT_APPLICABLE` with a basis is the terminal form for "no assertion is
  warranted".
- `proposed_questions` admits or updates genuinely additional semantic
  questions; Span creates the first-admission CQ-01 seed itself.
- `proposed_target_questions` associates an identical already-persisted
  `SemanticQuestionScope` with the target.

For example, during exact-target onboarding Span admits the area and asks its
purpose. If another target already has the exact same persisted question scope, reuse
that scope in `proposed_target_questions`; do not manufacture a duplicate
question. A question's `NOT_APPLICABLE` disposition answers only
that semantic question.

Use `status(TargetId)` in `NORMAL` mode for the campaign snapshot. Its
`target_total_count` and `target_association` are read-only projections of the
same disposition snapshot; the total is `None` when the disposition is
`UNVERIFIABLE` or `UNASSESSED`, never a fabricated zero. Do not count a
campaign by walking `locate` pages. `CURRENT` requires complete, current,
verifiable semantic coverage over the admitted members.

## Pending interpretation, evidence, and submission

When an operation returns `PendingInterpretation`, handle only that bounded
unit. Follow its `request` and `brief`: objective, exact scope and
exclusions, evidence/authority, material path, typed result, adversarial
check, disposition, and fresh readback. A brief guides the agent; it does not make a wrong interpretation correct.

Build an admissible submission as follows:

1. Inspect the pending `request`, including `evidence_units`, subjects,
   question scope, structural observations, identity bindings, and task
   brief.
2. Extract the canonical `EvidenceRef` values from the admitted evidence
   units; every unit is a semantic question, so cite the evidence you read.
3. Cite current source files directly for observed behavior where applicable.
   Use only references admitted by the provider and task scope. Preserve the
   provider's identity and provenance; Span resolves canonical target
   `EvidenceRef` fields server-side.
4. Never fabricate a locator, fingerprint, section/span, subject identity,
   or authority citation. Current provider-backed evidence may be admitted
   through the existing validation/normalization path even when it was not
   previously persisted by Span. Submitted fingerprints are not authority.
5. Construct the existing typed `SemanticInterpretationResult` with its
   candidate claims/relationships/subjects as applicable, and include the
   explicit `question_decision` required by this unit. Authority claims require qualifying authority evidence; source code
   evidence supports observed behavior but does not become normative merely
   by being nearby.
6. Review the result before submitting: check alternate owners, omitted
   participants, contradictions, unsupported routes, stale premises, missing
   authority, and every material leg. Use leg-open for any unsupported material leg;
   a paraphrase-only result must remain unsubmitted or be marked
   `OPEN`/`PENDING` with its requirement.
7. Call `submit_interpretation`, follow its returned next unit if any, and
   perform fresh `status`/`explain` readback after the operation reaches an
   answer. One answer, a populated store, or `READY` is never completion.

### Worked typed submission excerpt

This is adapted from the accepted exchange contract test for a semantic
question unit, not a target-inventory mapping unit. The evidence identity is
taken from the pending request, the claim cites that evidence, and the
decision binds the result to the request's exact question. Identity,
completion, result refs, and question evidence are Span-owned; the agent
supplies only the disposition and basis. The submission boundary is the typed
`SemanticInterpretationResult` passed to `submit_interpretation`:

```python
request = pending.request
evidence_ref = request.task_evidence.evidence_units[0].evidence_ref
subject = request.subjects[0].subject_id

claim = m.CandidateSemanticClaim(
    candidate_key="purpose",
    subject=subject,
    kind=m.ClaimKind.PURPOSE,
    value=m.PurposeValue("Sorts seeds", ()),
    evidence=(evidence_ref,),
    basis=m.SemanticBasis(
        m.DerivationKind.SEMANTIC_INTERPRETATION,
        "seed module states the seed purpose",
    ),
)
decision = m.SemanticQuestionDecision(
    disposition=m.SemanticQuestionDisposition.ANSWERED,
    disposition_basis="examined the admitted seed module",
)
result = m.SemanticInterpretationResult(
    claims=(claim,),
    relationships=(),
    candidate_subjects=(),
    candidate_conflicts=(),
    question_decision=decision,
    candidate_withdrawals=(),
)
answer = ops.submit_interpretation(
    pending.continuation,
    result,
    structural=structural,
    evidence=evidence,
    store=store,
    continuations=continuations,
)
```

The same typed result is the MCP submit payload; MCP adds only routing such
as the registered `repository_id`. Span validates the evidence identity,
question binding, and disposition before persistence and derives persisted
result references at the commit boundary.

Claims alone do not complete a question. An answering submission needs an
explicit `ANSWERED` `question_decision` for the exact bound question. Span
derives completion, canonical result references, question evidence, and the
persisted canonical question state. Unresolved work remains visibly `OPEN` or
`PENDING` with requirements. Do not reinterpret `PARTIAL`, `AMBIGUOUS`,
`CONFLICTED`, `UNRESOLVED`, `STALE`, or `UNVERIFIABLE` as certainty.

## Continuation recovery

Use this matrix next to every pending submission. Diagnose the returned
failure; do not blindly retry.

| Outcome | Continuation state | Required action |
| --- | --- | --- |
| Malformed submit payload or schema/transport ingress rejection | Existing continuation remains live | Correct the request and resubmit under the same continuation |
| Semantic validation rejection | Live | Correct the named invalid content and resubmit under the same continuation |
| Unreadable or unverifiable evidence rejection | Live, subject to normal expiry | Correct the evidence or submit an appropriate unresolved disposition under the same continuation |
| In-process persistence failure before successful commit | Retained if the transaction fails | Investigate the error; retry only when safe, under the same continuation |
| Successful commit | Consumed | Process the returned answer or next pending unit; never replay the consumed continuation |
| Unknown, expired, lost, or already consumed continuation | Not reusable | Re-enter through the original idempotent operation |
| Post-commit response loss | Already consumed; semantic state may be durable | Re-enter through the original idempotent operation and inspect persisted progress |
| Process crash with uncertain commit | In-memory continuation lost | Re-enter through the original operation; rely on canonical persisted state |
| Concurrent submission or in-flight token | Ownership unavailable | Do not submit a competitor; resolve the in-flight result/state |

There is no reissue operation. A malformed payload or semantic rejection
reuses the same continuation after correction; an unknown, expired, lost, or
already-consumed continuation is recovered by re-entering the original
idempotent operation. Persisted canonical state determines remaining work.

## Freshness, authority, and closeout

Structural and semantic freshness are separate. Structural `UNVERIFIED` can
support positive orientation (a found caller is useful evidence), but it
cannot prove completeness or absence. Semantic `STALE` can explain what was
previously known, but it is not current authority for an implementation
decision. `CURRENT` means the stored dependencies are current and verifiable;
it is not by itself proof of semantic correctness or sufficient exact-target
coverage. Missing authority, contradictions, and unresolved requirements
remain visible.

For a source change, or an explicitly challenged `CURRENT` explanation,
resolve the exact persisted question from `status`/`explain` coverage and
call scoped `refresh`. An unchanged-source challenge uses
`stale_only=False` with the exact `SubjectSelector`; nominate exactly one
already-persisted original `SemanticQuestionScope` in the submission and
provide evidence-grounded withdrawals/replacements. A second distinct
correction question in the same unit is rejected. `refresh` must be followed
by examination, submission where needed, and readback; the call alone proves
nothing.

The full lifecycle is:

`orientation → store readiness → establishment or question-local investigation →
evidence interpretation → canonical submission → validation/recovery →
persisted readback → material-change assessment when applicable → scoped
`status` → external implementation/verification → explicit refresh and
closeout`.

For material edits, the editing agent owns closeout in the same change:
scoped `status`, external tests/review, scoped `refresh` with a substantive
re-submission where required, then scoped `status` again. Report remaining
`OPEN`, stale, unverifiable, or unaccounted work explicitly. Hooks only call
`status` in `HOOK_FAST`; they never initialize, interpret, refresh, rebuild,
or edit.

## Shared analysis card and boundaries

For establishment, ordinary questions, impact/trace/authority follow-ups,
expansion, refresh, and closeout, use the pending request's compact card:

1. objective;
2. exact scope, boundaries, and exclusions;
3. evidence examined and governing authority, separating observed behavior
   from intended rule;
4. input → producer → transformation/state → consumer/output →
   terminal/failure path;
5. typed semantic result supported by admissible evidence;
6. adversarial check;
7. explicit `ANSWERED`, `OPEN`, `PENDING`, or `NOT_APPLICABLE` disposition
   with requirements; and
8. fresh readback.

Use three bounded levels: map the exact target structurally; establish a
coherent baseline area; then descend to member questions where a claim,
contract, failure path, ownership, authority, lifecycle, or unresolved
requirement matters. Do not create one semantic subject per file merely because it
exists, and do not compress unrelated units into one root. A user-supplied
directory is host-owned scope, not necessarily a resolvable Span subject; do not fabricate a directory/document subject when the provider exposes only a
file or symbol anchor. Record the provider limitation as `OPEN`/`PENDING`.

Specialized skills add task-specific guidance only: `span-document` owns
directory-level mapping and gap reporting, while `span-change-context` owns
pre-change `impact` and change closeout. They defer operation selection,
identity, evidence submission, recovery, and the lifecycle above to this
skill. The runbook and MCP reference are supporting procedures, not alternate
contracts.

## Scoped pagination note

Requests use a compact grammar: supply `$type` only where a field is a
genuine dataclass union; omit it elsewhere (a redundant tag is rejected).
The immutable SA obligations live in the tool contract. Target admission is
deterministic: Span assigns every inventory member, writes the
first-admission question, and returns it. Submit assertions, never
membership.
