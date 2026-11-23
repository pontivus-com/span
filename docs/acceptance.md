# Acceptance and evidence

The current lifecycle is evaluated at three distinct boundaries: deterministic
contracts, delivered host behavior, and useful real-task reuse. Passing a
local suite proves neither host conversion nor comparative product value.

## Version 1 Beta 2 candidate acceptance

Beta 2 extends the generic Version-1 functional-acceptance authority through
FA-64 in
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance),
mapped case-by-case in [the FA-01–FA-64 matrix](functional-acceptance.md).
The architecture guard requires each acceptance row exactly once and keeps
curation on the existing lifecycle writer/support/Answer paths.

The completed Beta-2 implementation head
`b80fd8a154d8f7785e37fbbc6e74deb017ba6e60` passed exact-head GitHub
Actions CI run `45177585406`: build/distribution, Ruff/Black, the zero-error
typing ratchet, `977 passed, 1 skipped, 148 subtests`, 85% aggregate coverage,
standalone plugin-notice delivery and the installed production-topology
acceptance surface.

Private first-adopter revalidation passed on 2026-11-24 against the committed
Legal product revision
`d4e4e45189041de3e960e1d2d0904c7c5f63adfb` and root-correct
repository-qualified seed/binding configuration. From an empty Span data
directory, `span-install` created repository schema 15 and the separate
installation Functional Pyramid schema 1 through the canonical provisioning
path. The public server exposed exactly `ask`, `record`, and `reconsider`.
The adopter Functional Pyramid candidate was activation-ready with no
validation or graph findings; the real Clause Workbench kickoff surface
returned a RESOLVED governing path through its accepted P1/P0 authority chain.
A representative NORMATIVE conclusion was support-CURRENT but withheld as
`pending_curation`, appeared in pending discovery, became reusable only after
an explicit exact-revision curation disposition, and returned as an Answer from
a fresh MCP process with the same RESOLVED governing projection.

The first-adopter result is intentionally sanitized. Raw transcripts, receipts,
local data stores and manifests remain outside Span Git. Exact-byte validation
also caught incorrect initial adopter content fingerprints before the passing
run; the configuration was corrected rather than weakening support/currentness
evaluation.

The assembled Beta-2 release identity is package `1.0.0b2`, registry
`1.0.0-beta.2`, repository lifecycle schema 15, and installation Functional
Pyramid schema 1. Schema-14 migration does not fabricate curation for retained
Beta-1 conclusions. Span has no built-in curator model and does not treat
curation as semantic truth or Functional Pyramid authority.

Live authenticated model delivery through supported managed hosts remains
**UNVERIFIED**. Registration, installer and hook support are not promoted into
a model-delivery claim. Final exact-head T14 CI and publication receipts are
recorded on the Beta-2 execution PR/release surfaces so recording them does not
mutate the candidate after its gate.

## Historical Version 1 Beta 1 candidate acceptance

The current generic Version-1 acceptance authority is
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance),
mapped executable-case-by-case in [the FA-01–FA-44 matrix](functional-acceptance.md).
`tests/unit/test_invariant_matrix.py` requires every FA row exactly once and
each row to name live, unambiguous boundary tests.

Post-C08 GitHub Actions run `44977899970` on
`15dc6ab8264d6a4fbeeff75b80eae360eaabb80b` passed build/distribution,
Ruff/Black, the zero-error typing ratchet, the complete pytest suite
(`919 passed, 1 skipped, 144 subtests`), standalone plugin-notice delivery and
coverage upload. That suite includes the non-editable installed MCP lane and
the physically separate repository-A / repository-B / installation-database
governance journey required by Technical Design §22.

This establishes the **generic** Version-1 functional/architecture candidate.
Private first-adopter acceptance also passed on 2026-11-22 using the
adopter-owned gitignored corpus. Raw adopter evidence remains outside Span Git;
only this sanitized outcome is published. T11 is therefore closed. By explicit
release-owner direction, that approved T11 result carries into the assembled
`1.0.0b1` candidate because the post-T11 diff contains no semantic/runtime
implementation change; documentation, release identity and tests do not reopen
the private acceptance gate.

The assembled `1.0.0b1` repository candidate passed exact-head CI run
`45035881725` on `e3d9e99fc89896373cb6a90f8d16e63d210fea5c`:
build/distribution, Ruff/Black, zero-error typing, `923 passed, 1 skipped,
144 subtests`, 85% aggregate coverage, plugin notice delivery, and the complete
generic acceptance surface.

A temporary T13 repository-validation workflow then passed run `45036708682`
on `752ba74cb196083a4f9d95725ccc373be2e93ed2`. It built and installed the
non-editable `1.0.0b1` wheel, verified repository schema 14 and installation
schema 1, and ran 167 focused transition/backup/recovery, installed-MCP,
public-boundary, FA/Part-C and architecture tests with 64 subtests. It also
proved there was no semantic/runtime implementation drift from the T10 accepted
SHA, re-exercised release-note/version mapping, and passed the release-time MCP
Registry `server.json` validator. The temporary workflow was removed after the
receipt was captured.

Version-1 live model delivery through Codex, OpenCode and Claude Code is
**UNVERIFIED**. No verified managed-host delivery claim is made for Beta 1;
registration/installer support is not promoted into model-delivery evidence.
No comparative G5/F8 score is required to publish Beta 1. Product-value
validation continues through real-world use in the legal project, where cold
investigation, fresh-session reuse, implementation and governance changes,
re-establishment, recovery, and ordinary failures can be observed in the actual
workflow. Findings become inputs to follow-up Beta patch releases. Historical
0.10/0.11 measurements and the two blocked GitHub Actions calibration attempts
from 2026-11-22 remain background evidence only and are not a Version-1 release
verdict.

The current repository lifecycle store is schema 14. Functional Pyramid
participation/versions/exclusions/receipts are installation-owned in
`installation/functional-pyramid.db`; repository-portable backups deliberately
do not claim to carry that installation participation state.

## Behavioral scenarios

The functional scenario set covers:

| ID | Behavior | Representative current tests |
| --- | --- | --- |
| F-01 | A cold surface obtain returns an honest unassessed gap with source pointers; selected evidence is admitted explicitly. | `test_unknown_surface_is_unassessed`, evidence-admission and continuation tests |
| F-02 | Record a real supported investigation, retain the compact receipt selector, and retrieve the immutable receipt when exact audit/replay detail is needed. | `test_create_records_and_replays`, receipt-selector retrieval, installed MCP lane |
| F-03 | Fresh-session reuse of a recorded answer without a supplied saved ID. | installed MCP fresh-process lane, host capture |
| F-04 | Relevant support change requires reassessment. | `test_source_support_current_changed_missing` |
| F-05 | Unrelated change preserves independent support. | `test_unrelated_source_change_keeps_current` |
| F-06 | Confirm/correct preserves revisions and version history. | `test_full_update_chain_preserves_history` |
| F-07 | Explicit challenges retain unresolved state and settlement history. | `test_record_settles_a_challenge_through_dispositions`, challenge transition and lifecycle-store tests |
| F-08 | Exact CSS/config evidence works without symbols. | `test_cross_file_batch_admits_each_source` |
| F-09 | Retry, restart, lost-response, and concurrent identities recover safely. | lifecycle service/store replay and concurrency tests |
| F-10 | Independent verification remains tied to the observations or evidence it tested. | `test_verification_runs_are_independent_and_source_aware`, `test_verification_accepts_evidence_only`, `test_record_verification_accepts_evidence_only` |
| F-11 | Correctness holds without hooks. | lifecycle tests, hooks-disabled Codex capture |
| F-12 | Batch outcomes, reference reuse, and membership changes remain explicit. | evidence/discovery/support service tests |
| F-13 | Missing, ambiguous, failed, expired, and truncated outcomes differ. | `test_multiple_granularities_are_ambiguous`, `test_budget_below_minimum_is_refused`, evidence and lifecycle tests |
| F-14 | Operational retention preserves accepted semantic history. | lifecycle-store reaping and replay-retention tests |
| F-15 | An ambiguous reference is resolved by copying an exact surface candidate. | `test_ambiguity_requires_distinct_candidates`, lifecycle MCP lane |
| F-16 | A service/domain surface is declared, used, and boundary-updated with compare-and-set. | `test_surface_declaration_create_and_update` |
| F-17 | Evidence selected by explicit admission is recovered through public continuation with bounded progress, replay, restart, typed unusable-reference rejection, and oversized-unit refusal. | `test_gap_continuation_returns_an_evidence_page`, `test_continuation_survives_a_fresh_process`, continuation lifecycle tests |
| F-18 | A discovery membership change is included directly by `reconsider`, not only by a premise walk. | `test_discovery_membership_change_is_direct`, lifecycle MCP tests |
| F-19 | Historical snapshot and receipt retrieval never become current answer content. | `test_snapshot_selector_returns_history_not_an_answer`, `test_receipt_selector_returns_history_not_an_answer` |

This maps representative coverage; a named test does not certify every clause
of a scenario or claim a host executed it. Read test assertions and execution
receipts for the exact demonstrated boundary.

### Historical 0.11 remediation scenarios

These rows record the completed 0.11 remediation campaign and remain historical
evidence for that candidate. They are not Version-1 proof; Version-1 acceptance
is owned by the functional matrix and the T10/T11/T13 gates above.

| ID | Behavior | Status | Evidence |
| --- | --- | --- | --- |
| F-20 | Surface-first document view is the normal reuse path; `RecordedQuestionSelector` is exact and surface-scoped, and a non-matching or paraphrased selector returns `Gap/unassessed` without semantic ranking. | implemented | `test_exact_question_without_membership_is_unassessed`, `test_exact_question_selector_does_not_paraphrase_match`, `test_surface_document_view_is_reuse_path` |
| F-21 | A rejection carries the exact cause, required action, and structured current version or boundary version; recognized lifecycle structural faults remain typed results rather than transport errors. | implemented — source CI verified | `test_version_conflict_names_the_current_version`, `test_surface_conflict_is_rejected_with_the_current_boundary_version`, `test_structural_lifecycle_ingress_is_a_rejected_result`, `test_structural_ingress_reports_independent_sibling_faults`, `test_malformed_ingress_is_a_transport_error`; GitHub Actions `44448034572` |
| F-22 | A create with a question context uses the bound target; supplying an explicit question or scope is rejected. | implemented | `test_context_bound_create_rejects_an_explicit_target`, `test_question_context_rejects_an_explicit_target` |
| F-23 | A stale surface boundary version or surface kind conflict is `Rejected`, not `Unavailable`. | implemented | `test_surface_update_stale_boundary_returns_rejected`, `test_surface_kind_conflict_returns_rejected` |
| F-24 | A declared surface parent must be declared, same-repository, and acyclic. | implemented | `test_surface_parent_must_be_declared`, `test_surface_update_rejects_a_parent_cycle` |
| F-25 | A verification run appears only on the surfaces in its declared scope. | implemented | `test_verification_run_appears_only_on_its_scope`, `test_multi_file_run_is_visible_on_each_file`, `test_one_file_run_is_not_visible_on_a_broader_service`, `test_service_wide_run_is_visible_on_service_and_files`, `test_directory_scoped_run_covers_files_under_it`, `test_symbol_run_matches_through_containing_file`, `test_symbol_without_a_file_prefix_is_excluded`, `test_multi_file_verification_run_is_visible_on_each_file` (installed MCP lane) |
| F-26 | With the delivered product surface (server plus installer-managed pre-read notice and readiness wait), the first Span call precedes the first source read; bare registration is not claimed. | implemented — OpenCode 5/5 | `natural-use/F10-2026-11-03.md`; Codex 5/5 pre-remediation in `natural-use/realistic/REALISTIC.md` |
| F-27 | Cost is claimed only for a named task class with positive measured value. | implemented | `five-task/MATRIX.md` (reuse, break-even 2), `g5/REUSE.md` (break-even 11); single-use cross-file is negative and not claimed |
| F-29 | A create without a surface derives it from one scope path or the question context; multiple paths are rejected with the candidates, and a supplied surface must agree with the carried scope. | implemented | `test_create_without_surface_derives_from_one_scope_path`, `test_create_without_surface_uses_the_question_context_scope`, `test_create_without_surface_rejects_multiple_paths`, `test_create_surface_must_agree_with_the_carried_scope`, `five-task/DERIVED-SURFACE.md` |
| F-30 | A create states one conclusion with dependency evidence from `locator`, `observation_id`, or non-empty `support`; a locator may accompany support as carried scope without adding a dependency, while observation remains exclusive. Span stores explicit support as supplied and derives the basis, new lineage id, and surface. | implemented — source CI verified | `test_create_accepts_locator_with_explicit_support`, `test_create_observation_remains_exclusive`, `test_record_create_through_the_one_request`, `test_record_accepts_every_support_kind`, `five-task/TASK1-FLAT.md`; GitHub Actions `44448034572` |

### Historical 0.11.0 remediation candidate

The 0.11.0 implementation is verified on source candidate
`00b4eb358b8e794f855a5de09eeb01efd72cd3c9`. GitHub Actions run
`44448034572` passed build/distribution, Ruff, Black, the zero-error typing
ratchet, `798 passed, 1 skipped, 125 subtests`, plugin notice delivery, and
85% aggregate statement coverage. The packaged stdio lane now covers the
reported challenge-resolution journey, structural rejection at the actual MCP
boundary, every declared result family including `Unavailable` for all three
public operations, exact-selector reuse, and unknown-tool transport failure.

The disposable transition lane additionally proves schema-12 refusal with both
expiring and no-expiry live contexts while preserving the old store, exact
post-cutover receipt/verification-run retrieval, interruption recovery, active
writer refusal, and rollback preservation. The CAS lane proves both
same-identity replay/conflict behavior and distinct request identities racing
one expected version. Reconsider re-establishment proves already-admitted
unchanged support is present in the returned context and is reused by exact
observation identity while changed support is re-observed.

#### Finding dispositions

| Finding | Status | Root cause / owning producer and consumers | Authority | Verification and observed result |
| --- | --- | --- | --- | --- |
| #1 / T01 | **closed** | Public `SurfaceReference` and ingress rules admitted repository identity in the wrong nested location; `AnswerService`, strict wire decoding and exact selectors consume the corrected carrier. | A8, A9, F7, F10; lifecycle §4.1; FD-26, FD-41 | `SurfaceReference` is exactly `{kind, locator}`; nested repository values including explicit null reject; the packaged MCP round-trips an ambiguity candidate as an exact surface. |
| #2 / T02 | **closed** for implementation | Context issuance used submission-shaped binding and non-canonical request identity; persisted binding semantics therefore required schema 13. `service/contexts.py` is the sole binding/issuance owner and the store/continuation/receipt paths consume it. | A2, L4, L7; FD-2–FD-4, FD-40, FD-42–FD-45, FD-59 | One typed `ContextBinding` with explicit origin, canonical scope/source/discovery selection and caller request identity is verified. Disposable schema-12→13 tests cover live/no-expiry refusal, preservation, activation, exact receipt/run retrieval, interruption and rollback. The authorized operational cutover is now complete and verified. |
| #3 / T03 | **closed** | Structural decoding previously lost actionable public coordinates into generic validation failure. Core wire/constraint decoding now produces one internal `StructuralFault` representation; the rejection owner and MCP adapter consume it without exception-text parsing or a new public result shape. | A8, A9; lifecycle §§4.1–4.3; FD-27, FD-38–FD-41 | Packaged MCP rejects nested surface repository placement, stray verification `run.repository_id`, and an unauthorized resolved-disposition result coordinate as typed `Rejected`; the write/challenge remain unchanged. Unit ingress tests cover sibling faults and malformed envelopes; unknown tools remain transport errors. |
| #4 / T05 | **closed** | Verification repository identity was duplicated inside the run instead of being owned by the enclosing record/context. Canonical verification wire and command construction now derive it from the recording identity; store/qualification/audit consume the derived value. | F7, L7; lifecycle §4.2; FD-3–FD-4 | Public verification schema has no nested repository; direct/context-bound recording, qualification and replay are tested. Schema-12→13 transition verification now retrieves the exact retained receipt and immutable verification run after activation. |
| #5 / T07 | **closed** | Reconsider re-establishment contexts carried path scope without the actionable conclusions' exact source/discovery memberships, while resolved dispositions exposed caller-authored result bookkeeping. Reconsider context membership and record/challenge settlement are the corrected owners. | F4, F5, F7, F9, L7, L10; lifecycle §§4.2–4.3; FD-17–FD-22, FD-37, FD-59 | Packaged MCP resolves the reported challenge with new ADR support outside the original context while preserving semantic scope and deriving exact result coordinates. A separate packaged journey proves unchanged admitted support is present in the reconsider context and reused by observation identity without re-observation. |
| #6 / T08 | **closed for PR scope** | Range currentness needed exact delivered-range evaluation with conservative whole-file fallback when rebinding is unreliable. The source/currentness path is corrected; comparative product value is intentionally not claimed. | G1, G3, G5, A5, F1, F2, F8; lifecycle §10; FD-10, FD-18 | Deterministic tests cover unrelated edits, cited edits, insertion above the range and unbindable fallback. The candidate-specific G5/F8 steps/tokens comparison is outside this PR gate and is not claimed. |
| #7 / T04 | **closed** | Context-free update scope derivation could perform exact-version lookup before the authoritative version outcome, turning absence into an operational store failure. Update snapshot ordering, typed lookup classification, receipt-first replay and store CAS are the owners. | A2, A3, A8, L4; lifecycle §§4.1–4.3; FD-19, FD-27, FD-38–FD-41, FD-46–FD-48 | The verified pre-fix path is closed by isolated reconstruction rather than a claim about unavailable raw session state: unknown identities are actionable, missing requested versions return the structured current version without issuing a context, replay races resolve receipt-first, and distinct request identities racing one version yield exactly one acceptance and one version conflict. |
| #8 / T09 | **closed for PR scope** | Span's installed stdio exact-selector grammar is working; managed-host delivery is intentionally outside this PR gate. | G2, F3, F10, L2, L8; lifecycle §4.1; FD-49–FD-53 | `test_exact_recorded_question_selector_through_stdio` is green on the packaged candidate. Candidate-specific host-visible schema/arguments/server-receipt capture and session-handoff proof are not claimed. |
| #9 / T10 | **closed for PR scope** | Canonical native/shell lifecycle guidance and notice machinery are delivered; candidate-specific host delivery is intentionally outside this PR gate. | A4, A8, F8, F10, L5; lifecycle §7; FD-52, FD-53, FD-58 | Hook/skill/managed-asset tests and the plugin notice-delivery CI lane are green. Candidate-specific native read/search and shell read/search captures are not claimed. |
| #10 / T06 | **closed** | Flat-create structural rules incorrectly treated carried semantic locator and explicit dependency support as mutually exclusive. The canonical record wire owns the grammar; lifecycle scope/owner derivation and docs consume it. | F5, F7, L7; lifecycle §4.2; FD-30 | Locator, observation, support-only and locator+support forms are tested; observation stays exclusive; carried locator adds no dependency; support-only/multi-file scope and owner behavior are covered, and current guidance/managed skills state the same rule. |

#### Cross-cutting compliance audit

**Public boundary — closed for the implementation candidate.** The packaged MCP
exercises `ask`, `record`, and `reconsider` over their surface/reference,
exact-selector, continuation, understanding create/update, verification,
surface-declaration, changed-scope and challenge branches. Its observed result
coverage includes `Answer`, `AmbiguousSurface`, `Gap`, `EvidencePage`,
`RetrievedUnderstanding`, `UnderstandingRecorded`,
`VerificationRecorded`, `SurfaceDeclared`, `Changed`, `Challenged`,
`Rejected`, and `Unavailable`; unknown tool names remain transport errors.
Strict unit ingress separately drives a malformed transport payload that the
typed MCP client itself cannot construct. Schema/egress tests reject internal
carrier names, diagnostics, filesystem/store paths, binding digests and
administrative state from the public result surface.

**Architecture — closed.** The complete 0.11 source diff was checked against
`AGENTS.md`. The measured architecture baseline is identical to v0.10.5 for
every non-test metric: `any_count=6`, `broad_excepts=14`,
`concrete_carriers=185`, zero core-layer violations, zero service→shell
imports, zero duplicate source/helper groups, zero mutable semantic-layer
tables, one evidence-selection implementation, nine `getattr` uses, 22
`type: ignore` sites and 103 untyped defs. The suspicious broad catches and
import-time fallback markers in canonical decoding/hooks/MCP adapter are
pre-existing at exactly the same counts; 0.11 introduced none. The semantic
annotation invariant and zero-error mypy ratchet pass. The only ratchet growth
is test coverage, now measured at 23,634 lines.

**Requirements pyramid — closed.** T01/T03/T04 derive ingress and rejection
mechanics from lifecycle §§4.1–4.3 and FD-27/FD-38–FD-48; T05/T06 derive
verification ownership and flat-create semantics from lifecycle §4.2 and
FD-3/FD-4/FD-30; T07's public resolved-disposition payload is owned by lifecycle
§4.2 and its deterministic mapping by FD-37, while membership/issuance mechanics
remain Layer 4; T02's `ContextBinding` and schema-13 transition are Layer-4
mechanisms deriving from FD-2–FD-4/FD-59. T08–T10 retain their existing
G/A/F/L/FD authority; their optional external observations are not release gates
for this PR. No 0.11 mechanism requires a new Layer-0–3 requirement and no Layer-4
mechanism invents a public payload.

The T08 G5/F8 comparative measurement and the combined T09/T10 candidate-specific
managed-host captures remain unclaimed external observations by decision. The
separately authorized schema-12→13 operational cutover and verification are
represented by the installed-store transition evidence and are complete for this
PR. No cost or managed-host delivery claim is made.

## Contract and artifact verification

The suite exercises strict codecs and schemas, pure rules, atomic persistence,
compare-and-set transitions, recovery, support checks, bounds, readiness,
hooks, isolation, skills, and managed assets. The installed-MCP lane builds a
non-editable install and drives `span-mcp` over stdio outside the source tree.
The transition lane uses disposable stores, including archive/export/verify,
interruption recovery, active-writer refusal, and rollback preservation.

0.9.2 adds named coverage for historical `Gap` content and stale surface
references (`test_invalidated_ask_returns_historical_content`,
`test_stale_sibling_is_referenced_in_status`,
`test_descendant_stale_ref_is_not_merged_into_parent`,
`test_truncated_gap_names_the_snapshot_retrieval_path`). The OpenCode edit-time
notice is proven at the `event.system` boundary by
`tests/plugin/test_span_hooks_notice.mjs`, run in CI.

0.9.4 adds named coverage for the installer and host contract: shared default
OpenCode MCP/plugin selection, receipt-backed verification and uninstall,
explicit relocation, `--no-hooks` MCP preservation, fail-closed current
receipts, conflict-preserving target inspection, ownership-based skill cleanup,
restored Claude registration/inspection/hooks/teardown, and removal of the
structural-indexer `PATH` fallback. The representative owners are
`tests/unit/test_install.py`, `tests/unit/test_claude_adapter.py`,
`tests/unit/test_lifecycle_hooks.py`, and
`tests/unit/test_graft_provisioning.py`.

Use [contributing](contributing.md) for commands. The zero-error typing baseline
is the beta gate; a passing ratchet with pre-existing errors is insufficient.
Clean builds, packaged assets, docs, version, and changelog extraction are
separate release checks.

## Host evidence

The installed-MCP lane verifies the build/command, advertised schemas,
requests/results, representation boundaries, and recovery and concurrency
behavior. Candidate-specific managed-host delivery is outside this PR gate and
is not claimed. Codex and OpenCode remain configured supported targets; Claude
Code remains supported for registration, health inspection, and installer
behavior, while its authenticated model-delivery grammar and caller identity
remain **UNVERIFIED**. Hook wiring is separate from observed arrival.

## Product value

Beta product value is evaluated in real engineering use rather than through a
synthetic equivalent-task release score. The legal project is the primary
post-release adopter surface for Version 1. Observe cold investigation,
fresh-session reuse, implementation and governance changes, focused
re-establishment, recovery, failures, omissions, and recording overhead as they
occur in normal work.

A populated store alone is not useful reuse, and a successful release does not
prove universal time or token savings. Any future comparative efficiency claim
needs evidence scoped to that claim. Real-world defects or friction discovered
during Beta are corrected through follow-up patch releases.

### Documentation replacement (G6)

A readable document view is not evidence that Span can replace documentation.
The named scenario is:

1. choose a covered surface that already has a Markdown page;
2. before recording or scoring, freeze a non-empty set of claims from that page,
   with exact claim text and source location;
3. record the surface's current understanding;
4. remove or reduce the duplicate documentation;
5. in a fresh session, obtain the surface document view and map each frozen
   claim to a supported current conclusion; use `RecordedQuestionSelector` only
   when the exact recorded question is part of the frozen evidence;
6. record documentation bytes/lines removed, frozen claims answered, unsupported
   claims caught, and exclusions.

Pass only when every frozen claim maps to a supported current conclusion and no
stale content is served as current. A frozen claim that is unavailable or
excluded is a failure, not an exclusion. Claims outside the frozen set may be
reported as not claimed; they cannot satisfy the gate. An entirely excluded set
fails G6.

## Reporting results

Release notes report sanitized verification outcomes and their limits. Raw
acceptance captures, transcripts, receipts and manifests remain private local
working material, excluded from Git and distributions.
