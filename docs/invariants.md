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
| I-02 | Strict ingress | Test | `ConstructionValidationTest`; `SerializationRoundTripTest` (unknown tags/values/fields rejected); `IngressTest` over the wire |
| I-03 | Closed semantic vocabulary | Test | `ClosedVocabularyTest` (member sets); `ProviderVocabularyTest` (provider-local vocabulary refused) |
| I-04 | One semantic carrier | Test | `PortShapeTest` (`ChangeKind` single home); `SchemaSyncTest` (schema is the carrier's projection) |
| I-05 | Evidence integrity | Test | `CandidateValidationTest` (missing/unresolving evidence rejected); `SemanticOutcomeTest` (valid delivery served) |
| I-06 | Authority integrity | Test | `CandidateValidationTest` (UNKNOWN status, structural derivation, verbatim quote, resolvable sections) |
| I-07 | Ownership integrity | Test | `RetiredOwnerTest`; `S02CustodyTest` (owner vs consumer population) |
| I-08 | Conflict integrity | Test | `ConflictDetectionTest` (core + recorded conflicts); `SelectionAtomicityTest` (conflict pairs never split) |
| I-09 | Ambiguity integrity | Test | `StoreResolutionTest` (ambiguity never overridden); `ContextualResolutionTest` (multiple roots stay ambiguous) |
| I-10 | Freshness preflight | Test | `FreshnessClassificationTest` (stale/current/unverifiable); `HookBoundednessTest` (hook read-only proof) |
| I-11 | Partial-refresh integrity | Test | `RefreshExchangeTest` (failed unit preserved as stale); `RetiredOwnerTest` (history preserved) |
| I-12 | Verification integrity | Test | `DerivedCurrencyTest` (record projects pass/fail/stale/unknown); `ExecutionIngressTest` (identity derives from the link); `MigrationPayloadRewriteTest` (a stored asserted pass becomes an unknown link) |
| I-13 | Structural separation | Review | Store holds canonical JSON + query columns only; no graph duplication |
| I-14 | Provider neutrality | Test | `GraftMappingTest` (unknown vocabulary errors); `ProviderVocabularyTest` (generic port protocol) |
| I-15 | No semantic reconstruction | Review | Composers project stored state; MCP/adapter/store add no judgments |
| I-16 | Boundedness | Test | `BoundsPolicyTest` (rejection never clamped); `BoundednessTest` (truncation categories) |
| I-17 | Publication isolation | Test | `IsolationGateTest` (hermetic tree; no enclosing-workspace coupling) |
| I-18 | No semantic `Any` | Test | `SemanticTypingTest` (annotation scan clean; canonical decode refuses untyped collections) |
| I-19 | Success-path completeness | Test | `ExchangeTest` (first pass settles); `DriverServiceTest` (validation is a backstop, not the path) |
| I-20 | Demand-driven indexing | Test | `InitializeTest` (init performs no interpretation); `InventorySnapshotTest` (bounded paged walk); `DemandDrivenIndexingTest` (service layer enumerates no filesystem) |
| I-21 | Reconstructible rebuild only | Review | §10.4 rule; rebuild paths preserve required history (retired tables) |
| I-22 | Missing authority remains missing | Test | `CandidateValidationTest` (UNRESOLVED + resolver requirement); `GhostSubjectTest` (absence stated, not invented) |
| I-23 | Skill non-authority | Test | `SkillNonAuthorityTest` (no second authorities, scores, or lifecycle actions) |
| I-24 | Skill/API consistency | Test | `test_only_canonical_operations` (canonical ops only, across all skills) |
| I-25 | Skill optionality | Test | `test_implementation_ignores_skills` (no implementation file depends on skill content) |
| I-26 | Lifecycle placement | Test | `ImpactTest` (pre-change brief); `RefreshExchangeTest` (explicit refresh suspends and resumes) |
| I-27 | Offline bootstrap isolation | Test | `InitializationContractTest` (no implicit bootstrap site); `AP09NoPersistentStoreTest` (read creates no store) |
| I-28 | Interactive hook boundedness | Test | `HookBoundednessTest` (one page under hook bounds, no continuation) |
| I-29 | No automatic semantic interpretation | Test | `HookBoundednessTest` (hook paths never suspend); `HookSafetyTest` (hook dispatches read-only status only) |
| I-30 | No automatic refresh | Test | `HookSafetyTest` (hooks report only); `RefreshExchangeTest` (refresh explicit with suspension) |
| I-31 | Readiness/trust separation | Test | `StatusTest` (ready qualifier separate from semantic coverage); `InitializeTest` (ready despite truncation) |
| I-32 | Irrelevant-change silence | Test | `HookRunnerTest` (unchanged/outside-repository silence); `ClaudeMappingTest` (unknown hook silent) |
| I-33 | Trust/freshness singularity | Test | `ClosedVocabularyTest` (enum-exactness, no STALE in trust); `SerializationRoundTripTest` (separate dimensions round-trip) |
| I-34 | Tagged reference ingress | Test | `S3SchemaTest` (union positions use tagged definitions); `S4QuestionSelectionTest` (ref resolution) |
| I-35 | Canonical operational bounds | Test | `BoundsPolicyTest` (policy defaults, maxima, hook bounds, rejection) |
| I-36 | Answer self-containment | Test | `SelectionAtomicityTest` (pair-atomic selection); `DispatchTest` (refs resolve inside the answer over the wire) |
| I-37 | Coverage-scoped atomic reconciliation | Test | `WithdrawalTest`; `SupersedingEvidenceTest`; `RetiredOwnerTest` (withdrawal, retire history, supersession, latest-wins) |
| I-38 | Proposal-typed change classification | Test | `ImpactTest` (proposal rows need typed assertions; change-kind gating) |
| I-39 | Continuation/pagination separation | Test | `PaginationContinuationTest`; `ContinuationIdentityTest`; `StaleContinuationEnvelopeTest` |

Downstream-compensation check (no silent repairs, no salvage, no
fallback parsing): validation rejects whole units; strict decode has
no fallback branch; service never synthesizes summaries, quotes, or
identifiers (auto-keys are deterministic intra-result labels, not
semantic content).
