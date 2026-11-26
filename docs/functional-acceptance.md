# Version 1 Beta functional acceptance matrix

> **Document role: executable verification traceability.** Use this matrix when
> you need to see which live tests demonstrate each Functional Design acceptance
> case. For the current candidate verdict, start with [Acceptance and evidence](acceptance.md).

This matrix is the executable traceability surface for
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance).
It does not redefine the acceptance cases. Each row names live boundary tests
that support the corresponding behavior. The test suite validates that FA-01
through FA-66 are present exactly once and that every named test still exists.

FA-28 was strengthened during the reopened Beta-3 T14 lifecycle-hook review.
The branch now carries the hook-specific executable evidence for composed
session entry, complete changed-scope evaluation, multi-edit accumulation,
canonical read-only preview parity, managed data-directory identity, Codex
native `apply_patch` PostToolUse translation including clean-preview handoff,
Claude Code native `Write|Edit` absolute-path translation/incomplete-input
diagnostics, OpenCode native patch/incomplete-scope handling, clean-preview and
clean-completion handoff, no session eviction, stale-notice invalidation with
full-union retry, and a wheel-bundled OpenCode -> installed span-hooks ->
temporary-store path. Exact-head release closure remains owned by T14-H7.

**Total-resolution amendment (2026-11-25).** The Beta-5 executable
matrix now follows Functional Design cases 1–66 exactly. The document-placement
replacement tests prove root totality, ancestor inheritance, exact directory
selection, additive and disconnected applicability, multi-path aggregation,
cross-repository document authority, explicit-scope selection and structural
health. The former member-scope/coverage/context acceptance rows are retired
rather than translated into compatibility behavior.

**Version-3 source amendment (2026-11-26).** The same FA cases additionally
prove the Version-3 source model: one repository-kind source at root scope, area
and shared-ancestor sources, explicit membership consistency, placement-scope
equality, typed duplicate detection before deduplication, Version-2 candidate
rejection and ACTIVE degradation, and placement-less finding relevance to the
affected route only.

**End-to-end initialization amendment.** FD-88A–C and functional acceptance
cases 67–72 specify the single document-driven governed installation, strict
preflight, replay/revision, metadata ownership, public projection and paging.
These new acceptance rows are pending until the installed tests land; historical
partial V3 verification does not close them.

| ID | Functional acceptance case | Live test evidence |
|---|---|---|
| FA-01 | Unconfigured versus excluded | `test_status_projects_unconfigured_excluded_and_rejects_unknown`; `test_exclude_is_explicit_nonparticipation`; `test_descriptive_recording_does_not_gain_route_support` |
| FA-02 | Pure action-aware candidate validation | `test_valid_candidate_is_pure_and_ready`; `test_explicit_p2w_to_p2s_governing_edge_is_valid`; `test_revision_candidate_reports_unknown_and_stale_target`; `test_duplicate_unregistered_and_other_active_members_accumulate`; `test_recoverable_bad_scope_is_graph_only`; `test_candidate_v2_source_is_validation_error_only` |
| FA-03 | Activation and replay | `test_activation_commits_members_effects_and_receipt`; `test_activation_replay_is_idempotent_and_conflict_is_rejected`; `test_installed_lifecycle_over_stdio`; `test_installed_cross_repository_governance_journey` |
| FA-04 | Revision and removal | `test_revision_compare_and_set_and_deactivate`; `test_revision_candidate_reports_unknown_and_stale_target` |
| FA-05 | Root totality | `test_root_totality_and_additive_ancestor_composition`; `test_missing_root_is_structural_health_finding`; `test_missing_root_placement`; `test_valid_candidate_is_pure_and_ready` |
| FA-06 | Inheritance without per-directory declaration | `test_directory_without_own_placement_inherits_all_ancestors`; `test_directory_lookup_returns_document_placements` |
| FA-07 | Degraded-health recovery | `test_status_keeps_active_v1_instance_active_but_degraded`; `test_status_keeps_active_v2_instance_active_but_degraded`; `test_unaffected_route_can_resolve_while_health_is_degraded` |
| FA-08 | Cold governed path | `test_cold_governed_path_returns_gap_with_governing_view` |
| FA-09 | Directory obtain | `test_directory_lookup_returns_document_placements`; `test_directory_lookup_rejects_non_directory`; `test_neutral_example_is_structurally_valid_and_resolves`; `test_installed_cross_repository_governance_journey` |
| FA-10 | Same semantic scope | `test_exact_question_selector_does_not_paraphrase_match`; `test_declared_symbol_boundary_is_exact_functional_pyramid_scope`; `test_document_locator_never_infers_applicability` |
| FA-11 | Additive composition | `test_root_totality_and_additive_ancestor_composition`; `test_directory_without_own_placement_inherits_all_ancestors` |
| FA-12 | Sibling and descendant exclusion | `test_descendant_placement_does_not_apply_to_ancestor`; `test_root_totality_and_additive_ancestor_composition` |
| FA-13 | Disconnected scope and unique placement | `test_disconnected_placements_apply_only_at_their_declared_scopes`; duplicate placement evidence in FA-17 |
| FA-14 | Multi-path and broad semantic scope | `test_multi_path_summary_is_union_not_intersection_or_last_path`; `test_repository_wide_semantic_scope_selects_all_placements` |
| FA-15 | Membership is not applicability | `test_unrelated_member_does_not_change_route_identity`; `test_route_identity_tracks_applicability_not_pyramid_version` |
| FA-16 | Cross-repository authority | `test_installed_cross_repository_governance_journey` |
| FA-17 | Document and placement defects | `test_invalid_scope_is_graph_finding_not_source_failure`; `test_narrower_governing_scope_is_invalid`; `test_reverse_p2s_to_p2w_governing_edge_is_invalid`; `test_same_contract_sublayer_governing_edges_are_invalid`; `test_missing_root_is_structural_health_finding`; `test_mismatch_missing_and_unlisted_coexist`; `test_duplicate_membership_within_one_source`; `test_duplicate_membership_across_sources`; `test_duplicate_layer_and_scope`; `test_repeated_placement_identity_is_duplicate_whether_identical`; `test_duplicate_source_identity_and_scope_are_invalid`; `test_multiple_repository_kind_sources_are_invalid`; `test_repository_kind_source_must_be_root_and_area_must_not` |
| FA-18 | Route versus authority currency | `test_authority_currency_does_not_change_route_identity_or_health`; `test_authority_support_status_and_presence` |
| FA-19 | Normative create | `test_normative_create_derives_route_and_all_applicable_authorities`; `test_unresolved_governance_is_retained_but_qualified_unverifiable`; `test_mixed_answer_excludes_noncurrent_normative_conclusion` |
| FA-20 | Descriptive create | `test_descriptive_recording_does_not_gain_route_support` |
| FA-21 | Authority-content change | `test_authority_currency_does_not_change_route_identity_or_health`; `test_authority_source_change_is_considered_not_forced_stale`; `test_authority_support_status_and_presence` |
| FA-22 | Applicability change | `test_material_applicability_change_changes_route_identity`; `test_functional_route_support_distinguishes_route_states`; `test_governance_only_change_crosses_physical_repository_boundary` |
| FA-23 | Internal reverse dependency traversal; no public impact selector | `test_installed_cross_repository_governance_journey`; preserve the Beta-5 over-fetch remediation R-1–R-6 (no reverse/internal fields on public views) |
| FA-24 | Cross-repository reconsideration | `test_governance_only_change_crosses_physical_repository_boundary` |
| FA-25 | Implementation change | `test_changed_path_maps_containment_direct_and_indirect`; `test_discovery_membership_change_is_direct` |
| FA-26 | Mixed answer | `test_descriptive_answer_survives_unresolved_governing_route`; `test_mixed_answer_excludes_noncurrent_normative_conclusion`; `test_unresolved_governance_is_retained_but_qualified_unverifiable` |
| FA-27 | Canonical-source singularity | `test_valid_declaration_round_trips_canonical_carriers`; `test_installed_cross_repository_governance_journey` |
| FA-28 | Runtime lifecycle preservation | `test_three_tool_journey_and_restart`; `test_reconsider_record_succeeds_without_an_intervening_ask`; `test_challenge_raised_by_reconsider_is_settled_by_record` |
| FA-29 | Governance-source edit lifecycle | `test_authority_source_change_is_considered_not_forced_stale`; `test_governance_only_change_crosses_physical_repository_boundary`; `test_normative_confirm_reestablishes_changed_server_route_support` |
| FA-30 | Lifecycle-compliance hooks | `test_session_entry_composes_four_participation_health_branches_once`; `test_changed_scope_projection_receives_complete_input_before_render_bound`; `test_changed_scope_preview_reuses_projection_without_context_issuance`; `test_governance_only_change_crosses_physical_repository_boundary`; `test_codex_merge_adds_entries_and_dedupes`; `test_codex_apply_patch_parser_uses_only_documented_patch_markers`; `test_codex_post_tool_emits_structured_context_for_complete_native_scope`; `test_codex_post_tool_keeps_reconsider_obligation_when_preview_is_clean`; `test_codex_post_tool_reports_incomplete_native_scope_without_guessing`; `test_claude_post_tool_uses_documented_absolute_path_and_structured_context`; `test_claude_post_tool_reports_incomplete_native_scope_without_guessing`; `test_packaged_opencode_plugin_reaches_real_installed_hook_store`; `test_packaged_assets_are_generated_from_canonical_sources`; `test_hook_source_uses_canonical_changed_scope_projection`; `test_hook_source_has_no_semantic_writer_or_builder`; `tests/plugin/test_span_hooks_notice.mjs` (multi-edit union, native multi-file patch, explicit incomplete input, no session eviction, clean-preview/clean-completion handoff, stale-notice invalidation with retained-union retry, singular delivery) |
| FA-31 | Initialization handoff | `test_activation_commits_members_effects_and_receipt`; `test_installed_lifecycle_over_stdio`; `test_installed_cross_repository_governance_journey`; document-only installed handoff pending FA-67 |
| FA-32 | One active instance per repository | `test_concurrent_overlapping_activation_serializes_to_one_active_instance`; `test_duplicate_unregistered_and_other_active_members_accumulate` |
| FA-33 | Three-tool host surface | `test_only_the_three_core_tools_are_registered`; `test_installed_lifecycle_over_stdio` |
| FA-34 | No uncovered answer | `test_root_totality_and_additive_ancestor_composition`; `test_directory_without_own_placement_inherits_all_ancestors`; `test_installed_cross_repository_governance_journey` |
| FA-35 | Explicit scope, no placement inference | `test_document_locator_never_infers_applicability`; `test_descendant_placement_does_not_apply_to_ancestor`; `test_invalid_scope_is_graph_finding_not_source_failure`; `test_mismatched_placement_is_reported_at_its_actual_scope` |
| FA-36 | Health iff structural findings | `test_status_keeps_active_v1_instance_active_but_degraded`; `test_status_keeps_active_v2_instance_active_but_degraded`; `test_unaffected_route_can_resolve_while_health_is_degraded`; `test_authority_currency_does_not_change_route_identity_or_health`; `test_placement_less_finding_affects_its_area_only`; `test_unrelated_member_defect_does_not_unresolve_a_route`; `test_cross_source_duplicate_reaches_every_affected_route` |
| FA-37 | Activation of pre-existing normative understanding | `test_newly_active_repository_reassesses_pre_route_normative_revision`; `test_retained_activation_effect_stays_actionable_without_route_support`; `test_installed_cross_repository_governance_journey` |
| FA-38 | Functional Pyramid write propagation | `test_installation_effect_engine_uses_repository_runtime`; `test_governance_only_change_crosses_physical_repository_boundary`; `test_installed_cross_repository_governance_journey` |
| FA-39 | Deactivation/removal route state | `test_revision_compare_and_set_and_deactivate`; `test_functional_route_support_distinguishes_route_states` |
| FA-40 | Operational route failure while ACTIVE | `test_functional_route_support_distinguishes_route_states`; `test_repository_unavailability_is_graph_state` |
| FA-41 | Pyramid-write replay projection | `test_activation_replay_is_idempotent_and_conflict_is_rejected`; `test_installed_cross_repository_governance_journey` |
| FA-42 | Pyramid concurrency | `test_concurrent_overlapping_activation_serializes_to_one_active_instance`; `test_revision_compare_and_set_and_deactivate` |
| FA-43 | External governance edits use ordinary re-alignment | `test_governance_only_change_crosses_physical_repository_boundary`; generated initialization effect integration pending FA-69/70 |
| FA-44 | Conformance uses the normative input contract | `test_normative_create_derives_route_and_all_applicable_authorities`; `test_governed_normative_record_never_uses_empty_uncovered_route` |
| FA-45 | Acceptance is not runtime completion | `test_unresolved_governance_is_retained_but_qualified_unverifiable`; `test_owner_read_failure_reports_unavailable_without_rejecting_acceptance`; `test_functional_pyramid_skill_covers_result_driven_lifecycle` |
| FA-46 | Participation-write acceptance is not initialization completion | `test_installed_cross_repository_governance_journey`; `test_functional_pyramid_skill_covers_result_driven_lifecycle` |
| FA-47 | New capture is not shared reuse | `test_current_capture_is_pending_until_curated` |
| FA-48 | Pending-capture gap | `test_current_capture_is_pending_until_curated`; `test_noncurrent_capture_is_stale_not_pending` |
| FA-49 | Pending-curation discovery | `test_pending_curation_keyset_paging_has_no_skip_or_duplicate`; `test_pending_curation_keyset_paging_resumes_after_restart` |
| FA-50 | Curation does not rewrite or bypass support | `test_curate_accepts_exact_current_revision_and_replays`; `test_curate_rejects_non_current_target_before_mutation`; `test_curation_storage_is_exact_version_aware_and_immutable` |
| FA-51 | Curated reuse | `test_current_capture_is_pending_until_curated` |
| FA-52 | Curation cannot override later support loss | `test_changed_source_is_an_invalidated_gap` |
| FA-53 | Correction resets curation | `test_confirm_inherits_curation_but_semantic_change_does_not` |
| FA-54 | Replacement resets curation | `test_replace_after_curation_starts_replacement_captured` |
| FA-55 | Addition begins captured | `test_add_after_curation_starts_new_lineage_captured` |
| FA-56 | Confirm preserves curated meaning | `test_normative_confirm_reestablishes_changed_server_route_support`; `test_confirm_inherits_curation_but_semantic_change_does_not` |
| FA-57 | Confirm does not invent curation | `test_confirm_of_captured_predecessor_remains_uncurated` |
| FA-58 | Withdrawal is never reusable | `test_withdrawn_curated_lineage_is_not_reusable` |
| FA-59 | Curation is a separate act | `test_curate_cannot_share_actions_with_semantic_mutation` |
| FA-60 | Curation is not governance | `test_normative_confirm_reestablishes_changed_server_route_support`; `test_curated_revision_reconsiders_without_mutating_curation` |
| FA-61 | Normative reuse requires both planes | `test_installed_cross_repository_governance_journey`; `test_mixed_answer_excludes_noncurrent_normative_conclusion` |
| FA-62 | Failed review repairs meaning first | `test_installed_cross_repository_governance_journey` |
| FA-63 | Schema-14 migration fabricates no curation | `test_schema14_state_is_preserved_and_curation_starts_empty` |
| FA-64 | Migrated current knowledge is pending | `test_schema14_current_revision_migrates_as_pending_capture` |
| FA-65 | Three-tool host surface remains exact | `test_only_the_three_core_tools_are_registered` |
| FA-66 | Installed lifecycle closes the loop | `test_installed_cross_repository_governance_journey` |
| FA-67 | Document-only governed initialization | Pending — S-VERIFY-02 |
| FA-68 | Strict preflight | Pending — S-INIT-01/02, S-VERIFY-02 |
| FA-69 | Repeat and revise; authority-only delta effects | Pending — S-INIT-02/03, S-VERIFY-02 |
| FA-70 | Exclusive administrative ownership, existing-binding reuse and durable interruption recovery | Pending — S-INIT-02/03, S-VERIFY-02 |
| FA-71 | Public findings | Pending — S-PUBLIC-01 |
| FA-72 | Complete bounded retrieval | Pending — S-PUBLIC-02 |
The matrix names enforcement boundaries; the CI execution receipt remains the
evidence that those tests passed for a particular candidate.
