# Historical acceptance evidence

> **Document role: historical verification evidence.** This page preserves
> acceptance records for superseded candidates and campaigns. It is not the
> current Beta-4 release verdict and it does not create product authority.
> Start with [current acceptance](acceptance.md) for the active candidate.

The material below is retained for provenance and audit. Version- and
candidate-specific statements are historical in their original context; they
must not be read as the current Span baseline.

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
External integration acceptance also passed on 2026-11-22 using the
repository-controlled external integration corpus. Raw external integration evidence remains outside Span Git;
only this sanitized outcome is published. T11 is therefore closed. By explicit
release-owner direction, that approved T11 result carries into the assembled
`1.0.0b1` candidate because the post-T11 diff contains no semantic/runtime
implementation change; documentation, release identity and tests do not reopen
the external integration acceptance gate.

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
validation continues through real-world integration use, where cold
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

## Historical Beta 3 candidate acceptance

The current functional acceptance authority is
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance).
FA-01–FA-64 remain the numbered acceptance set. The corrected FA-28
lifecycle-hook case now has executable boundary evidence in the
[functional-acceptance matrix](functional-acceptance.md), and the
[Invariant audit matrix](invariants.md) names the corresponding architectural
guards. T14-H7 remains the exact-head verification gate for the assembled
candidate.

### Semantic/runtime baseline

The Beta-3 semantic/runtime baseline was exercised at
`b80fd8a154d8f7785e37fbbc6e74deb017ba6e60` by GitHub Actions CI run
`45177585406`:

- build/distribution passed;
- Ruff and Black passed;
- the zero-error typing ratchet passed;
- pytest reported `977 passed, 1 skipped, 148 subtests`;
- aggregate coverage was 85%;
- standalone plugin-notice delivery passed; and
- the installed production-topology acceptance surface passed.

This establishes the semantic/runtime baseline used by the Beta-3 corrective
work.

### External integration revalidation

External integration revalidation passed on 2026-11-24 using
repository-controlled integration inputs whose identities and contents remain
outside this public repository.

From an empty Span data directory, the run demonstrated:

- canonical `span-install` provisioning of repository schema **15**;
- separate installation Functional Pyramid schema **1**;
- exactly the public `ask`, `record`, and `reconsider` MCP operations;
- an activation-ready Functional Pyramid candidate with no validation/graph
  findings;
- a real governed integration surface with a resolved governing path;
- a representative normative conclusion withheld from shared reuse while
  captured/pending review;
- explicit curation of the exact revision; and
- fresh-process reuse of that reviewed conclusion with the same resolved
  governing projection.

Only generic acceptance outcomes are retained in Span Git. External repository
identities, revisions, paths, authority identifiers, configuration payloads,
transcripts, receipts, local stores, and manifests remain outside this public
repository.

The run also detected incorrect initial integration content fingerprints. The
external configuration was corrected; Span's support/currentness rules were not
weakened to make the run pass.

### Corrective baseline

The Beta-3 corrective baseline at
`f797c049917c0d3e70d402e2f4fed714dfd6efd5` passed push CI
`45296868951` and pull-request CI `45296879433`.

That evidence demonstrated:

- package build/install as `span_mcp-1.0.0b3`;
- Ruff/Black success;
- zero typing errors;
- `980 passed, 1 skipped, 150 subtests`;
- 85% aggregate coverage;
- plugin notice delivery;
- strict rejection of missing canonical authority discriminators; and
- the Beta-3 release-identity guard.

This SHA is the last fully recorded **pre-documentation-remediation corrective
baseline**. It must not be described as the current branch head after the
documentation remediation that followed it.

### Documentation-remediation verification

The first F14 documentation/authority restructuring was verified at
`f3ca2065a7bbee1af02ef9bd61006f210f0952c9` by GitHub Actions CI run
`45329316520`.

A second F14 refinement then audited the public corpus against the actual
product dependency order. That refinement identified two remaining
documentation defects:

- public pages still contained non-operational commentary about their own
  organization/disclosure strategy; and
- the first-use/usage path did not consistently present Functional Pyramid
  initialization/adoption before ordinary **governed** runtime use, even though
  lifecycle §7 already owns that ordering.

F14 was amended at Layer 1 to require dependency-ordered information and to
forbid unnecessary self-commentary without restating Layer-2 participation
states or transitions.

The refined content head is
`ef0ff8f4bc0352c4f52cf2254163d7f1da8ac27a`.
GitHub Actions CI run `45333961735` passed on that exact tree:

- build/distribution passed;
- Ruff and Black passed;
- typing remained at **0 errors**;
- pytest reported **980 passed, 1 skipped, 150 subtests**;
- aggregate coverage remained **85%**;
- plugin notice delivery passed; and
- the coverage artifact uploaded successfully.

The refinement changed documentation and managed agent guidance only; no
`src/` or `tests/` file changed.

The resulting public order is:

1. install and verify Span;
2. for governed use, initialize/adopt the Functional Pyramid and establish
   governance readiness;
3. complete the first investigation and capture/review/reuse loop;
4. use the repeating semantic lifecycle during normal engineering work; and
5. consult concepts/reference only when deeper detail is needed.

The ordinary descriptive semantic lifecycle remains available without ACTIVE
Functional Pyramid participation. UNCONFIGURED is therefore not misrepresented
as a runtime failure, while it is also no longer presented as completed
governance setup.

README, documentation index, install, first investigation, usage, lifecycle,
FAQ, managed AGENTS guidance and packaged router/before-read guidance now share
that ordering. The active primary navigation was rechecked on the refined tree:
repository-relative file links and referenced section anchors resolve.

This acceptance file and the Beta-3 programme record are closure receipts for
that verified F14 content tree.

A subsequent substantive review of all five shipped `SKILL.md` files and the
agentic hook path found defects that structural presence/JSON-decoding tests had
not detected. The corrections are part of Beta 3 rather than a post-release
workstream:

- skill prose now preserves the CURRENT + CURATED Answer boundary, bounded
  PendingCuration pagination, Functional Pyramid `exclude`, NORMATIVE
  conformance examples, exact action grammar, challenge-context alternatives,
  and the current lifecycle authority anchor;
- the hook runtime no longer maintains a parallel SOURCE-only dependent scan.
  Change notices use a read-only preview of the same canonical changed-scope
  projection as `reconsider`, including containment, source/discovery,
  authority/route, premise and cross-repository effects, without issuing
  re-establishment contexts;
- native host adapters evaluate complete changed scope before notice bounding:
  Codex translates canonical `apply_patch` PostToolUse input to structured
  additional context; Claude Code translates documented `Write|Edit`
  PostToolUse absolute `file_path` input to the same structured lifecycle
  handoff; and OpenCode retains documented edit/write/patch scope until
  handoff, including clean previews and retry after helper failure, while
  diagnosing incomplete native payloads rather than guessing. Host-trigger
  documentation no longer carries stale Beta-1/T13 candidate claims; and
- the new semantic skill/hook regressions increased the measured
  `test_lines` ratchet from **32,443 to 32,486**. No production/source-quality
  ceiling or product gate was weakened.

The earlier F14 and skill/hook runs remain evidence only for their exact trees.
The deeper lifecycle review corrected FD-58/FD-94 and Technical Design §22.
T14-H2–H6 now implement complete changed-scope evaluation, session edit
accumulation without arbitrary eviction/truncation, managed data-directory
identity, documented native Codex/Claude/OpenCode event mapping, mandatory
post-edit handoff even when preview finds no affected retained conclusion,
stale-notice invalidation without path loss, singular session-entry/completion
composition, representative preview purity/parity, and the minimum executable
hook acceptance set. The installed lane now builds from the canonical packaging
inputs and proves the wheel-bundled OpenCode plugin can be deployed through the
real installed `span-hooks` path. The post-audit executable evidence raises
only the measured Python `test_lines` ratchet, from **32,771 to 33,110**; no
source-quality ceiling or product gate is weakened.

The authoritative Beta-3 T14 closure proof is the required GitHub CI check
attached to the exact H7 candidate commit. Its run identifier is intentionally
not embedded in the candidate tree because doing so would create another head.
A green check closes T14 without creating a second evidence-only commit; a
failed check leaves T14 open.

## Release identity and authorization

The assembled Beta-3 identity remains:

| Surface | Identity |
| --- | --- |
| Package/PyPI | `1.0.0b3` |
| Git tag | `v1.0.0b3` |
| GitHub Release | `Span 1.0.0 Beta 3` |
| MCP Registry | `1.0.0-beta.3` |
| Repository lifecycle schema | **15** |
| Installation Functional Pyramid schema | **1** |

Schema-14 migration fabricates no curation approval for retained Beta-1
conclusions.

Publication remains a separate owner decision. The release workflow is
manual-only, runs from `master`, and requires exact package-version
confirmation.

**Beta 3 is not authorized for publication.** Green CI or implementation
completion does not authorize tagging, PyPI publication, GitHub Release
creation, or MCP Registry publication.

## Host-delivery evidence

The installed-MCP lane verifies the packaged command, advertised schemas,
request/result boundaries, recovery, and concurrency behavior.

Managed-host registration/support and authenticated model delivery are different
claims.

For the current Version-1 candidate:

- Codex remains a managed integration target;
- OpenCode managed integration has a wheel-bundled plugin → installed
  `span-hooks` → temporary-store acceptance path;
- Codex managed hook acceptance covers canonical `apply_patch` PostToolUse
  payload normalization and structured `additionalContext` output;
- Claude Code managed hook acceptance covers documented `Write|Edit`
  PostToolUse absolute-path normalization, structured `additionalContext`,
  clean-preview handoff and explicit incomplete-input diagnostics; and
- authenticated live Version-1 model delivery remains **UNVERIFIED** unless a
  separate recorded acceptance run establishes it.

Hook wiring is likewise not proof that a notice reached a model.

See [host trigger support](../integrations/hosts/triggers.md) for the current
host-specific evidence.

## Functional and architectural traceability

Do not use this page as a second requirements catalog.

- [Functional acceptance](functional-acceptance.md) maps FA-01–FA-64 to live
  boundary tests, including the expanded FA-28 hook boundaries added under
  T14-H2–H6.
- [Invariant audit matrix](invariants.md) maps architecture invariants to tests
  or explicit review enforcement.
- [Method grounding](method-grounding.md) explains external industry/method
  evidence without turning that evidence into Span authority.

Passing tests demonstrate the boundaries their assertions cover. A named test
does not by itself prove every semantic interpretation or every host delivery
claim.

## Product value

Beta product value is evaluated through real engineering use rather than a
synthetic equivalent-task release score.

Useful evidence includes:

- cold investigation;
- fresh-session reuse;
- implementation change and focused reassessment;
- governance change;
- recovery;
- ordinary operational failure;
- omissions/gaps; and
- the overhead of capture and review.

A populated store is not itself useful reuse. A successful release also does not
prove universal time or token savings.

Any comparative efficiency claim requires evidence scoped to that specific
claim.

### Documentation replacement (G6)

A readable Span answer is not enough to prove that Span can replace duplicated
surface-bound explanatory documentation.

The named scenario is:

1. choose a covered surface that already has explanatory Markdown;
2. freeze a non-empty set of claims from that page before recording/scoring;
3. establish and retain the surface's current understanding;
4. remove or reduce the duplicated explanation;
5. in a fresh session, obtain the maintained surface knowledge and map each
   frozen claim to supported current understanding; and
6. record what documentation was removed, which frozen claims were answered,
   which unsupported claims were caught, and any exclusions.

The scenario passes only when every frozen in-scope claim maps to supported
current understanding and stale content is not served as current.

An unavailable frozen claim is a failure, not an exclusion. Claims outside the
frozen set cannot be used to satisfy the gate.

## Reporting evidence

Release/verification records publish sanitized outcomes and their limits.

Raw external-integration captures, transcripts, receipts, local stores, and
manifests remain outside Span Git and distributions, except for the explicitly
defined repository-portable backup artifact.

Historical candidate evidence is retained in
[Historical acceptance evidence](acceptance-history.md).
