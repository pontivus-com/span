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
2. Check readiness with normal `status` when the repository is registered.
   `READY` means operational storage readiness, not semantic coverage.
3. If readiness is `UNINITIALIZED`, run `initialize_repository` once in its
   dedicated setup workflow. If the repository is already initialized, do not initialize it again just to orient a session.
4. For an exact user-supplied directory plus objective, call
   `initialize_target` with that complete exact boundary. For ordinary
   orientation, call `status` with no target and then question-local
   `explain`; use `explain(establish_baseline=True)` only for an ordinary
   selected root, never as a substitute for exact-target onboarding.
5. When a call returns `PendingInterpretation`, inspect that one bounded
   request, use admissible canonical evidence, submit the typed
   `SemanticInterpretationResult`, and follow the returned next unit until an
   answer or truthful terminal state is returned.
6. Use `status` for read-only coverage and freshness readback. Status
   never initiates interpretation, allocates continuations, or persists
   freshness. Inventory accounting and semantic-question coverage are
   separate. Preserve every `OPEN`, `PENDING`, `PARTIAL`, `AMBIGUOUS`,
   `CONFLICTED`, `UNRESOLVED`, `STALE`, and `UNVERIFIABLE` state.
   Schemas are generated from canonical types: construct submissions
   from `tools/list` schemas without reading implementation. Narrow
   questions accept `question_selection` (slice/basis/anchors only);
   anchors are literal substrings. Excerpts carry ranges and omissions;
   answers carry `state_explanation` with descriptive/normative counts.
7. For material edits, call `impact` before editing; after external
   verification, perform scoped `status` → explicit `refresh` and re-submit
   where required → scoped `status` again. `impact` is preparation, not
   approval; `refresh` alone proves nothing.

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
| Assess a proposed change | `impact` | A material change has a target, `change_kind`, description, and affected assertions where known | Read the bounded pre-change brief and blockers; it never authorizes implementation |
| Re-examine stale or explicitly challenged understanding | `refresh` | A scoped answer is stale, or an exact persisted question is explicitly challenged | Reinterpret only the supplied scope; examine, submit, and read back the corrected result |
| Submit a pending interpretation | `submit_interpretation` | You hold a live continuation and a typed result for its exact request | Correct validation/evidence problems and resubmit under the same continuation; success consumes it and returns an answer or next unit |
| Reissue an identical interpretation task | `reissue_interpretation` | The original interpretation task failed at eligible MCP ingress | Use at most once; submit the identical returned task under its new continuation |

`initialize_repository` is not routine session orientation. `status` is
read-only and differs in `NORMAL` and `HOOK_FAST`: `NORMAL` `status` reports a
bounded persisted coverage inventory, while `HOOK_FAST` reports only the
event-local notice. `HOOK_FAST` sees event-local scope only; it never means the repository is clean. A `HOOK_FAST` `0/0 READY` notice does not describe
the repository inventory.

The twelve public operations are exactly the operations in the table. There are no semantic aliases. `locate` and `neighbors` return structural
navigation evidence, not semantic claims. `page_token` values (`pg:*`) page
one truncated listing and continuation tokens (`cont-*`) resume one pending
interpretation; they cannot be interchanged.

## Entry decision

Pick one branch before making a semantic call:

1. **Ordinary orientation:** normal `status` with no target, then `explain` on
   the chosen target. Never `refresh` on first contact.
2. **Exact user-supplied directory plus objective:** preserve the complete
   exact boundary and call `initialize_target` once with the exact
   `EvidenceScope` and objective. Process every returned unit.
3. **Post-change closeout:** run scoped `status` on the exact mutated scope;
   refresh only the noncurrent scope, re-examine and submit its task, then run
   scoped `status` again.

If the MCP runtime returns `UNINITIALIZED`, stop normal work and use the
dedicated repository setup workflow first. If it returns readiness only,
report the known runtime coverage-inventory gap; do not infer that semantic
knowledge is absent.

## Repository identity and readiness

`repository_locator` identifies a repository during setup. It is not the
value used by repository-scoped operations. Never pass a filesystem path as
`repository_id`. Obtain the exact canonical registered ID from MCP
`tools/list`, or from the successful repository-initialization response, and
reuse that ID unchanged. Registered-ID examples are illustrations, not fixed
global identifiers. Do not add aliases or translate paths to IDs.

The lifecycle is:

1. Discover the registered canonical identity.
2. Determine readiness.
3. Use the registered repository directly when it is initialized.
4. If it is `UNINITIALIZED`, perform `initialize_repository` in its dedicated
   setup session.
5. Begin the requested semantic operation or exact-target campaign only
   after readiness is established.

Initialization provisions identity, structural source, evidence inventory,
authority seeds, and store schema. It performs no semantic interpretation.
`READY` proves operational readiness only; it does not prove semantic
coverage, correctness, target accounting, or completeness.

## Exact-target establishment and accounting

An exact directory supplied by the user remains the complete target boundary,
even when it is large. Structural anchors are execution aids and never grant
permission to narrow that boundary. `initialize_target` returns a bounded
frontier. Partition it into coherent material areas outside the MCP call and
account for every current inventory member. A mapping unit has
`question=None`; it is not itself a semantic question.

Each member gets exactly one target-accounting outcome:

- assign its current `evidence_ref` to one or more admitted area subjects;
- provide an evidence-backed exclusion using `exclusion_basis`; or
- keep it explicitly unresolved with typed `resolution_requirements`.

The three related result components have different jobs:

- `proposed_target_inventory_accounting` accounts for target inventory
  members;
- `proposed_question_coverages` admits or updates semantic-question
  coverage; first admission of a material area requires `PENDING` coverage;
- `proposed_target_questions` associates an identical already-persisted
  `SemanticQuestionScope` with the target.

For example, during exact-target onboarding, a newly discovered material
area is admitted with an evidence-backed subject and a `PENDING`
`proposed_question_coverages` entry. If another area already has the exact same persisted question scope, reuse that scope in
`proposed_target_questions`; do not manufacture a duplicate question. If an
inventory member cannot yet be assigned or excluded with evidence, submit
its current `evidence_ref` with an explicit mapping requirement. A question's
`NOT_APPLICABLE` disposition answers only that semantic question; it is not a
target-inventory exclusion.

Use `status(TargetId)` in `NORMAL` mode for the campaign snapshot. Its
`target_total_count`, `target_accounted_count`, and
`target_unaccounted_count` are read-only counts from the same disposition
snapshot; they are `None` when the disposition is `UNVERIFIABLE` or
`UNASSESSED`, never fabricated zeros. Do not count a campaign by walking
`locate` pages. `CURRENT` requires both complete target accounting and
complete, current, verifiable semantic coverage.

## Pending interpretation, evidence, and submission

When an operation returns `PendingInterpretation`, handle only that bounded
unit. Follow its `request` and `brief`: objective, exact scope and
exclusions, evidence/authority, material path, typed result, adversarial
check, disposition, and fresh readback. A brief guides the agent; it does not make a wrong interpretation correct.

Build an admissible submission as follows:

1. Inspect the pending `request`, including `evidence_units`, subjects,
   question scope, structural observations, identity bindings, and task
   brief.
2. Extract the canonical `EvidenceRef` values from those evidence units. If
   more structure is needed, use `locate` or `neighbors` and respect their
   returned coverage and freshness; navigation does not establish truth.
3. Cite current source files directly for observed behavior where applicable.
   Use only references admitted by the provider and task scope. Preserve the
   provider's `evidence_id`, `locator`, `source_kind`, and provenance.
4. Never fabricate a locator, fingerprint, section/span, subject identity,
   or authority citation. Current provider-backed evidence may be admitted
   through the existing validation/normalization path even when it was not
   previously persisted by Span. Submitted fingerprints are not authority.
5. Construct the existing typed `SemanticInterpretationResult` with its
   candidate claims/relationships/subjects as applicable, and include the
   explicit question coverage or target-accounting outcome required by this
   unit. Authority claims require qualifying authority evidence; source code
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

This is adapted from the accepted Addendum H exchange test for a semantic
question unit, not a target-inventory mapping unit. The evidence identity is
taken from the pending request, the claim cites that evidence, and the
coverage binds the result to the request's exact question. The submission
boundary is the typed `SemanticInterpretationResult` passed to
`submit_interpretation`:

```python
request = pending.request
evidence_ref = request.evidence_units[0].evidence_ref
question = request.question
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
coverage = m.InterpretationCoverage(
    subjects=(question.subject,),
    question_slice=question.question_slice,
    evidence_scope=m.EvidenceScope(paths=(), evidence_refs=()),
    declared_complete=True,
    question=question,
    disposition=m.SemanticQuestionDisposition.ANSWERED,
    result_refs=(),
    resolution_requirements=(),
    disposition_basis="test explicit completion",
    question_evidence=(),
)
result = m.SemanticInterpretationResult(
    claims=(claim,),
    relationships=(),
    candidate_subjects=(),
    candidate_conflicts=(),
    proposed_question_coverages=(coverage,),
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
explicit `ANSWERED` coverage for the exact bound question with its declared
completion; unresolved work remains visibly `OPEN` or `PENDING` with
requirements. Do not reinterpret `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`,
`UNRESOLVED`, `STALE`, or `UNVERIFIABLE` as certainty.

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
| Eligible one-time interpretation-task ingress failure, explicitly reported before the pending task is admitted for semantic submission | Reissue permitted once | Call `reissue_interpretation`; use the identical returned task under its new continuation |
| Unknown, expired, lost, or already consumed continuation | Not reusable | Re-enter through the original idempotent operation |
| Post-commit response loss | Already consumed; semantic state may be durable | Re-enter through the original idempotent operation and inspect persisted progress |
| Process crash with uncertain commit | In-memory continuation lost | Re-enter through the original operation; rely on canonical persisted state |
| Concurrent submission or in-flight token | Ownership unavailable | Do not submit a competitor or force reissue; resolve the in-flight result/state |

`reissue_interpretation` is not the remedy for a malformed MCP payload, a
returned `ingress` or `validation` error from `submit_interpretation`, expiry,
timeout, process interruption, or uncertain commit. Those cases use the same
continuation when the response says it remains live, or re-enter the original
operation when the continuation is unavailable. Reissue is allowed only when
the transport/host explicitly identifies the separate eligible
interpretation-task ingress failure before semantic submission was admitted;
do not infer it from a generic timeout or from a malformed-payload diagnostic.
It returns the identical bounded task once; a second reissue abandons that
path. A continuation token and a listing page token are separate mechanisms.

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

`orientation → readiness → establishment or question-local investigation →
evidence interpretation → canonical submission → validation/recovery →
persisted readback → material-change assessment when applicable → external
implementation/verification → explicit refresh and closeout`.

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

## Addendum J note

Requests use a compact grammar: supply `$type` only where a field is a
genuine dataclass union; omit it elsewhere (a redundant tag is rejected).
Pending units carry an `interpretation_profile` naming the immutable SA
obligations. Target mapping submits `CandidateTargetInventoryAccount`
(stable `EvidenceId` + one outcome); Span derives the durable account and the
first-admission question. Mapping binds a bounded batch — disposition every
bound member in one atomic unit.
