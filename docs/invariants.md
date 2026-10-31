# Invariant audit matrix

Method: each invariant traced from canonical ingress through
storage, service composition, and MCP output to its tests. Verdict
`Test` = mechanically test-enforced; `Review` = code-inspection
enforced (no meaningful runtime probe exists). Every `Test` row names
at least one live boundary test; `tests/unit/test_invariant_matrix.py`
fails when a named test disappears, when a row claims no test, or when
a `Review` row claims test enforcement. No violations found; first
offending boundary would be recorded here.

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
| I-09 | Ambiguity integrity | Test | `UnderstandServiceTest`; `DiscoveryServiceTest` (candidates stay candidates) |
| I-10 | Freshness preflight | Test | `SupportServiceTest`; `DiscoveryServiceTest` (current/changed/missing membership) |
| I-11 | Version history integrity | Test | `LifecycleStoreTest`; `test_update_cas_and_history` |
| I-12 | Verification integrity | Test | `SupportServiceTest`; `test_verification_runs_are_independent_and_source_aware` |
| I-13 | Structural separation | Review | Store holds canonical JSON plus query columns only; no graph duplication |
| I-14 | Provider neutrality | Test | `GraftMappingTest`; `StructuralCoverageConformanceTest` |
| I-15 | No semantic reconstruction | Review | Composers project stored state; transport/store add no judgments |
| I-16 | Boundedness | Test | `test_total_byte_bound_omits_remainder`; `test_unit_bound_omits_remainder`; `test_truncation_is_explicit` |
| I-17 | Publication isolation | Test | `IsolationGateTest` (hermetic tree; no enclosing-workspace coupling) |
| I-18 | No semantic `Any` | Test | `SemanticTypingTest` (annotation scan clean; canonical decode refuses untyped collections) |
| I-19 | Success-path completeness | Test | `LifecycleMcpTest` (first valid recording on the ordinary path) |
| I-20 | Demand-driven indexing | Test | `ProvisioningLifecycleTest`; `DemandDrivenIndexingTest` |
| I-21 | Reference-safe reaping | Review | Reaping removes operational state only; semantic history stays reference-safe |
| I-22 | Missing authority remains missing | Test | `test_declared_authority_resolution`; `SupportServiceTest` (unverifiable stays unverifiable) |
| I-23 | Skill non-authority | Test | `SkillNonAuthorityTest` (no second authorities, scores, or lifecycle actions) |
| I-24 | Skill/API consistency | Test | `test_only_canonical_operations` (canonical operations only, across all skills) |
| I-25 | Skill optionality | Test | `test_implementation_ignores_skills` (no implementation file depends on skill content) |
| I-26 | Lifecycle placement | Test | `UnderstandServiceTest`; `test_cold_question_admits_inspectable_evidence` |
| I-27 | Offline bootstrap isolation | Test | `InitializationContractTest`; `test_cs07_uninitialized_context_creates_no_store` |
| I-28 | Interactive hook boundedness | Test | `LifecycleHooksTest` (one event-local notice; no inventory scan) |
| I-29 | No automatic semantic interpretation | Test | `LifecycleHooksTest`; `test_hooks_never_build` (hook paths never build or record) |
| I-30 | No automatic refresh | Test | `LifecycleHooksTest` (hooks report only) |
| I-31 | Readiness/trust separation | Test | `StartupRegistrationTest`; `SupportServiceTest` (readiness is not currency) |
| I-32 | Irrelevant-change silence | Test | `LifecycleHooksTest` (unrelated paths stay silent) |
| I-33 | Trust/freshness singularity | Test | `ClosedVocabularyTest`; `SerializationRoundTripTest` |
| I-34 | Tagged reference ingress | Test | `CanonicalRoundTripTest`; `RecordWireSchemaTest` (tagged union positions) |
| I-35 | Canonical operational bounds | Test | `ConstructionValidationTest` (policy defaults and rejection are explicit) |
| I-36 | Answer self-containment | Test | `test_full_lifecycle_and_restart`; `LifecycleMcpTest` (refs resolve inside the answer) |
| I-37 | Explicit withdrawal and supersession | Test | `LifecycleStoreTest`; `test_withdraw_creates_explicit_withdrawal_revision` |
| I-38 | Changed-support investigation stays pre-change | Test | `UnderstandServiceTest` (reconsideration prepares, recording accepts) |
| I-39 | Continuation/pagination separation | Test | `test_stale_token_maps_to_envelope`; `PageTokenTest`; `ScopeTokenTest` |

Downstream-compensation check (no silent repairs, no salvage, no
fallback parsing): validation rejects whole units; strict decode has
no fallback branch; service never synthesizes summaries, quotes, or
identifiers (auto-keys are deterministic intra-result labels, not
semantic content).
