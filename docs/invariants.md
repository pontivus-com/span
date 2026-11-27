# Invariant audit matrix

> **Document role: architectural verification traceability.** Use this matrix
> when you need to see how cross-layer invariants are mechanically enforced or
> explicitly review-enforced. For the current candidate verdict, start with
> [Acceptance and evidence](acceptance.md).

Method: each invariant traced from canonical ingress through
storage, service composition, and MCP output to its tests. Verdict
`Test` = mechanically test-enforced; `Review` = code-inspection
enforced (no meaningful runtime probe exists). Every `Test` row names
at least one live boundary test; `tests/unit/test_invariant_matrix.py`
fails when a named test disappears, when a row claims no test, or when
a `Review` row claims test enforcement. Named tests identify enforcement boundaries; they do not certify every
semantic interpretation or every host. Execution receipts are separate.

## Version-1 Functional Pyramid verification

The invariant table below remains the cross-version architectural matrix.
Version-1 Functional Pyramid behavior is additionally traced case-by-case in
`docs/functional-acceptance.md` (FA-01–FA-64), and the invariant test suite
requires every FA row to name the tests that currently evidence it. A row whose
behaviour is retired by a governing amendment is marked pending replacement and
is not reported as passing. Static architecture guards
also reject shell semantic coordination, optional production Functional
Pyramid dependencies, repository-local effect-engine construction, skipped
route-impact traversal, external-authority local fallback, and semantic hooks
that bypass `InstallationRuntime`.

These are executable consequences of the canonical L0–L4 requirements; this
document does not add a second Functional Pyramid contract.

**Beta-5 public-boundary amendment (OPEN).** TD §9.2 and the existing
[implementation plan §3B](implementation-plans/functional-pyramid-governance-implementation-plan.md#3b-public-lifecycle-boundary-remediation--2026-11-27)
own the PUB architectural construction and task gates. Extend the existing
I-01/I-02/I-04/I-07/I-13/I-15/I-16/I-18/I-21/I-28/I-39/I-40–I-48 enforcement
at their current test/review boundaries; preserve every existing invariant.
The new continuation, routing, migration and accepted-effect obligations are
not certified by prior tests. Add actual test names and code-review evidence
at the owning task and reconcile this matrix in PUB-09/10. No new ordinal or
claimed passing test is introduced here.

The reopened T14 hook review strengthened FD-58/FD-94 and the corresponding
hook invariants. I-28 now names live complete-input, canonical-preview,
composed-entry, native Codex and Claude Code translation and deployed
packaged-host evidence; the Node plugin lane additionally proves native
multi-file patch normalization, explicit incomplete input, no silent session
eviction, multi-edit union, clean-preview/clean-completion handoff and
stale-notice invalidation with retained-union retry. Exact-head release closure
remains separate under T14-H7.

| ID | Invariant | Verdict | Evidence |
|---|---|---|---|
| I-01 | Functional-core purity | Test | `CorePurityTest` (stdlib + `span.core` only, AST scan) |
| I-02 | Strict ingress | Test | `ConstructionValidationTest`; `SerializationRoundTripTest`; `RecordWireMalformedTest` (unknown fields/tags/values rejected) |
| I-03 | Closed semantic vocabulary | Test | `ClosedVocabularyTest` (member sets); `RecordWireSchemaTest` (closed branches) |
| I-04 | One semantic carrier | Test | `CanonicalRoundTripTest`; `RecordWireCodecTest` (wire is the carrier's projection) |
| I-05 | Evidence integrity | Test | `EvidenceServiceTest`; `test_missing_and_unreadable_are_distinct_and_success_survives` |
| I-06 | Authority integrity | Test | `SupportServiceTest`; `test_authority_support_status_and_presence` |
| I-07 | Ownership integrity | Test | `BindingTest`; `LifecycleStoreTest` (one root binding, no rebinding) |
| I-08 | Conflict integrity | Test | `LifecycleStoreTest` (challenge settlement); `ChallengeTransitionTest` |
| I-09 | Ambiguity integrity | Test | `AnswerServiceTest`; `test_multiple_granularities_are_ambiguous` (ambiguity is a separate result) |
| I-10 | Freshness preflight | Test | `SupportServiceTest` (current/changed/missing membership) |
| I-11 | Version history integrity | Test | `LifecycleStoreTest`; `test_update_cas_and_history` |
| I-12 | Verification integrity | Test | `SupportServiceTest`; `test_verification_runs_are_independent_and_source_aware`, `test_verification_accepts_evidence_only` |
| I-13 | Structural separation | Review | Store holds canonical JSON plus query columns only; no graph duplication |
| I-14 | Provider neutrality | Test | `GraftMappingTest`; `StructuralCoverageConformanceTest` |
| I-15 | No semantic reconstruction | Review | Composers project stored state; transport/store add no judgments |
| I-16 | Boundedness | Test | `test_admission_does_not_bound_delivery_bytes`; `test_unit_bound_omits_remainder`; `test_bound_reports_truncation_not_unaffected` |
| I-17 | Publication isolation | Test | `IsolationGateTest` (hermetic tree; no enclosing-workspace coupling) |
| I-18 | No semantic `Any` | Test | `SemanticTypingTest` (annotation scan clean; canonical decode refuses untyped collections) |
| I-19 | Success-path completeness | Test | `LifecycleMcpTest` (first valid recording on the ordinary path) |
| I-20 | Demand-driven indexing | Test | `ProvisioningLifecycleTest`; `DemandDrivenIndexingTest` |
| I-21 | Reference-safe reaping | Review | Reaping removes operational state only; semantic history stays reference-safe |
| I-22 | Missing authority remains missing | Test | `test_declared_authority_resolution`; `SupportServiceTest` (unverifiable stays unverifiable) |
| I-23 | Skill non-authority | Test | `SkillNonAuthorityTest` (no second authorities, scores, or lifecycle actions) |
| I-24 | Skill/API consistency | Test | `test_only_canonical_operations` (canonical operations only, across all skills); `test_json_examples_decode_through_the_mcp_wire` (each skill example decodes as its tool); `test_record_description_carries_every_call_template`; `test_contract_action_vocabulary_matches_the_wire` |
| I-25 | Runtime independence from skill text | Test | `test_implementation_ignores_skills` (no implementation file depends on skill content) |
| I-26 | Lifecycle placement | Test | `AnswerServiceTest`; `test_unknown_surface_is_unassessed` |
| I-27 | Offline bootstrap isolation | Test | `InitializationContractTest`; `test_cs07_uninitialized_context_creates_no_store` |
| I-28 | Hook canonical-effect reuse, complete-input evaluation and read-only preview | Test | `test_session_entry_composes_four_participation_health_branches_once`; `test_changed_scope_projection_receives_complete_input_before_render_bound`; `test_changed_scope_preview_reuses_projection_without_context_issuance`; `test_governance_only_change_crosses_physical_repository_boundary`; `test_codex_post_tool_emits_structured_context_for_complete_native_scope`; `test_codex_post_tool_keeps_reconsider_obligation_when_preview_is_clean`; `test_codex_post_tool_reports_incomplete_native_scope_without_guessing`; `test_claude_post_tool_uses_documented_absolute_path_and_structured_context`; `test_claude_post_tool_reports_incomplete_native_scope_without_guessing`; `test_packaged_opencode_plugin_reaches_real_installed_hook_store`; `tests/plugin/test_span_hooks_notice.mjs` (native patch, incomplete input, no eviction, multi-edit union, clean handoff, stale-notice retry) |
| I-29 | No automatic semantic interpretation | Test | `LifecycleHooksTest`; `test_hooks_never_build` (hook paths never build or record) |
| I-30 | No automatic refresh | Test | `LifecycleHooksTest`; `test_changed_scope_preview_reuses_projection_without_context_issuance` (preview leaves persisted lifecycle state unchanged) |
| I-31 | Readiness/trust separation | Test | `StartupRegistrationTest`; `SupportServiceTest` (readiness is not currency) |
| I-32 | Irrelevant-change silence | Test | `LifecycleHooksTest` (unrelated paths stay silent) |
| I-33 | Trust/freshness singularity | Test | `ClosedVocabularyTest`; `SerializationRoundTripTest` |
| I-34 | Tagged reference ingress | Test | `CanonicalRoundTripTest`; `RecordWireSchemaTest` (tagged union positions) |
| I-35 | Canonical operational bounds | Test | `ConstructionValidationTest` (policy defaults and rejection are explicit) |
| I-36 | Qualified result with publicly retrievable detail | Test | `test_three_tool_journey_and_restart`; `test_current_content_is_an_answer`; `test_changed_source_is_an_invalidated_gap` (omitted content resolves through public retrieval) |
| I-37 | Explicit withdrawal and supersession | Test | `LifecycleStoreTest`; `test_withdraw_creates_explicit_withdrawal_revision` |
| I-38 | Changed-support investigation stays pre-change | Test | `UnderstandServiceTest` (reconsideration prepares, recording accepts) |
| I-39 | Cursor routing and stable request binding | Test | `PageTokenTest` |
| I-40 | Canonical curation carrier singularity | Test | `test_curation_carriers_have_one_canonical_definition` |
| I-41 | One curation persistence writer | Test | `test_curation_persistence_has_one_writer` |
| I-42 | One pending/reuse Answer composer | Test | `test_pending_reuse_has_one_answer_composer` |
| I-43 | Curation reuses the canonical support evaluator | Test | `test_curation_reuses_the_single_support_evaluator` |
| I-44 | Shell does not decide curation semantics | Test | `test_shell_has_no_curation_semantic_decision` |
| I-45 | Missing curation never means approval | Test | `test_missing_curation_never_defaults_to_approval` |
| I-46 | No parallel curate operation or rejected-curation state | Test | `test_no_parallel_curate_operation_or_rejected_state` |
| I-47 | No curation compatibility grammar | Test | `test_curation_rejects_compatibility_action_aliases` |
| I-48 | Governing-edge admissibility has one semantic owner and is independent from route presentation order | Test | `test_governing_edge_admissibility_has_one_core_owner` |

Downstream-compensation check (no silent repairs, no salvage, no
fallback parsing): validation rejects whole units; strict decode has
no fallback branch; service never synthesizes summaries, quotes, or
semantic statements. Server-owned context/receipt identities are operational
identities, not semantic content.

## Lifecycle transfer

I-36 deliberately replaces the earlier all-detail-in-one-answer requirement:
qualifications, omissions, and next actions stay explicit while large bodies
may be retrieved through public references. I-39 now concerns listing cursors
and request binding; process-local interpretation continuations are retired.
Operational context/admission writes are distinct from semantic recording.
Support currency does not establish truth or complete repository coverage.
