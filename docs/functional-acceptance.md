# Version 1 Beta functional acceptance matrix

> **Document role: executable verification traceability.** Use this matrix when
> you need to see which live tests demonstrate each Functional Design acceptance
> case. For the current candidate verdict, start with [Acceptance and evidence](acceptance.md).

This matrix is the executable traceability surface for
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance).
It does not redefine the acceptance cases. Each row names live boundary tests
that support the corresponding behavior. The test suite validates that FA-01
through FA-64 are present exactly once and that every named test still exists.

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

**Total-resolution amendment (2026-11-25).** The Functional Design now retires
member functional scope, PARTIAL/COMPLETE coverage, context applicability and the
outside/covered/uncovered/mixed relation. Rows FA-05, FA-06, FA-10, FA-11,
FA-12, FA-14, FA-32, FA-33 and FA-34 below still name their pre-amendment tests
so the matrix stays traceable, but those tests exercise retired behavior and are
not evidence for the current acceptance cases. Replacement tests are pending with
the implementation change; until they exist, those rows are pending, not passing.

| ID | Functional acceptance case | Live test evidence |
|---|---|---|
| FA-01 | Unconfigured versus excluded | `test_status_projects_inactive_and_live_active_health`; `test_record_exclude_has_no_semantic_effect_projection`; `test_descriptive_recording_does_not_gain_route_support` |
| FA-02 | Pure action-aware candidate validation | `test_valid_activate_candidate_is_ready`; `test_candidate_accepts_explicit_p2w_to_p2s_edge`; `test_revision_candidate_reports_unknown_and_stale_target`; `test_candidate_reports_duplicate_unregistered_and_other_active_members` |
| FA-03 | Activation and replay | `test_record_activate_commits_members_effects_and_receipt`; `test_invalid_activation_leaves_participation_state_unchanged`; `test_record_replay_preserves_receipt_without_new_effect_discovery`; `test_installed_lifecycle_over_stdio`; `test_installed_cross_repository_governance_journey` (fresh processes for activation and retained-effect replay) |
| FA-04 | Revision and removal | `test_record_revise_only_reports_actual_participation_changes`; `test_record_revise_enforces_version_cas`; `test_revision_candidate_reports_unknown_and_stale_target` |
| FA-05 | Root totality | Pending replacement; the prior `test_partial_uncovered_path_is_route_unresolved_but_health_valid` and `test_wholly_outside_scope_is_resolved_empty_governance` exercise retired behavior |
| FA-06 | Inheritance without per-directory declaration | Pending replacement; the prior `test_complete_coverage_remainder_is_candidate_validation_finding` and `test_complete_uncovered_scope_degrades_health` exercise retired behavior |
| FA-07 | Degraded-health recovery | `test_degraded_health_recovers_without_participation_change`; `test_degraded_instance_can_resolve_unaffected_local_route` |
| FA-08 | Cold governed path | `test_cold_governed_path_returns_gap_with_governing_view` |
| FA-09 | Same semantic scope | `test_exact_question_selector_does_not_paraphrase_match`; `test_surface_kind_prevents_filename_heuristic_scope_inference`; `test_declared_symbol_boundary_is_exact_functional_pyramid_scope` |
| FA-10 | Additive composition | Pending replacement; the prior `test_overlapping_direct_contexts_precede_inherited_contexts` exercises retired context ordering |
| FA-11 | Disconnected applicability | Pending replacement; the prior `test_one_context_can_cover_disconnected_paths` exercises retired context membership |
| FA-12 | Multi-path and broad semantic scope | Pending replacement; the prior `test_broad_scope_crossing_boundary_is_mixed_and_resolved_when_covered` and `test_overlapping_direct_contexts_precede_inherited_contexts` exercise retired behavior |
| FA-13 | Membership is not applicability | `test_route_identity_ignores_instance_version_and_unrelated_member` |
| FA-14 | Cross-repository authority | Pending replacement; the prior `test_unavailable_member_is_distinct_from_unknown_context` names the retired context identity; `test_rule_owner_uses_existing_authority_resolver` remains conceptually applicable |
| FA-15 | Authority graph defects | `test_authority_graph_defects_are_explicit`; `test_explicit_p2w_to_p2s_governing_edge_is_valid`; `test_reverse_p2s_to_p2w_governing_edge_is_invalid`; `test_same_p2s_governing_edge_is_invalid`; `test_same_p2w_governing_edge_is_invalid`; `test_joint_p2_applicability_does_not_create_governing_edge` |
| FA-16 | Route versus authority currency | `test_authority_currency_does_not_change_route_identity_or_health`; `test_authority_support_status_and_presence` |
| FA-17 | Normative create | `test_normative_create_derives_route_and_all_applicable_authorities`; `test_unresolved_governance_is_retained_but_qualified_unverifiable`; `test_mixed_answer_excludes_noncurrent_normative_conclusion` |
| FA-18 | Descriptive create | `test_descriptive_recording_does_not_gain_route_support` |
| FA-19 | Authority-content change | `test_authority_currency_does_not_change_route_identity_or_health`; `test_authority_source_change_is_considered_not_forced_stale`; `test_authority_support_status_and_presence` |
| FA-20 | Applicability change | `test_material_applicability_changes_change_route_identity`; `test_functional_route_support_distinguishes_route_states`; `test_governance_only_change_crosses_physical_repository_boundary` |
| FA-21 | Reverse authority navigation | `test_exact_canonical_rule_owner_scope_exposes_reverse_graph`; `test_explicit_p2w_to_p2s_governing_edge_is_valid`; `test_installed_cross_repository_governance_journey` |
| FA-22 | Cross-repository reconsideration | `test_governance_only_change_crosses_physical_repository_boundary` |
| FA-23 | Implementation change | `test_changed_path_maps_containment_direct_and_indirect`; `test_discovery_membership_change_is_direct` |
| FA-24 | Mixed answer | `test_descriptive_answer_survives_unresolved_governing_route`; `test_mixed_answer_excludes_noncurrent_normative_conclusion`; `test_unresolved_governance_is_retained_but_qualified_unverifiable` |
| FA-25 | Canonical-source singularity | `test_functional_pyramid_carries_references_not_governing_prose` |
| FA-26 | Runtime lifecycle preservation | `test_three_tool_journey_and_restart`; `test_reconsider_record_succeeds_without_an_intervening_ask`; `test_challenge_raised_by_reconsider_is_settled_by_record` |
| FA-27 | Governance-source edit lifecycle | `test_authority_source_change_is_considered_not_forced_stale`; `test_governance_only_change_crosses_physical_repository_boundary`; `test_normative_confirm_reestablishes_changed_server_route_support` |
| FA-28 | Lifecycle-compliance hooks | `test_session_entry_composes_four_participation_health_branches_once`; `test_changed_scope_projection_receives_complete_input_before_render_bound`; `test_changed_scope_preview_reuses_projection_without_context_issuance`; `test_governance_only_change_crosses_physical_repository_boundary`; `test_codex_merge_adds_entries_and_dedupes`; `test_codex_apply_patch_parser_uses_only_documented_patch_markers`; `test_codex_post_tool_emits_structured_context_for_complete_native_scope`; `test_codex_post_tool_keeps_reconsider_obligation_when_preview_is_clean`; `test_codex_post_tool_reports_incomplete_native_scope_without_guessing`; `test_claude_post_tool_uses_documented_absolute_path_and_structured_context`; `test_claude_post_tool_reports_incomplete_native_scope_without_guessing`; `test_packaged_opencode_plugin_reaches_real_installed_hook_store`; `test_packaged_assets_are_generated_from_canonical_sources`; `test_hook_source_uses_canonical_changed_scope_projection`; `test_hook_source_has_no_semantic_writer_or_builder`; `tests/plugin/test_span_hooks_notice.mjs` (multi-edit union, native multi-file patch, explicit incomplete input, no session eviction, clean-preview/clean-completion handoff, stale-notice invalidation with retained-union retry, singular delivery) |
| FA-29 | Initialization handoff | `test_activation_handoff_status_matches_committed_result`; `test_record_revise_only_reports_actual_participation_changes`; `test_installed_lifecycle_over_stdio` |
| FA-30 | One active instance per repository | `test_candidate_reports_duplicate_unregistered_and_other_active_members`; `test_concurrent_overlapping_activation_serializes_to_one_active_instance` |
| FA-31 | Three-tool host surface | `test_only_the_three_core_tools_are_registered`; `test_installed_lifecycle_over_stdio` |
| FA-32 | No uncovered answer | Pending replacement; the prior `test_wholly_outside_scope_is_resolved_empty_governance` and `test_outside_functional_scope_records_resolved_empty_route_only` exercise retired behavior |
| FA-33 | Explicit scope, no placement inference | Pending replacement; the prior `test_broad_scope_crossing_boundary_is_mixed_and_resolved_when_covered` and `test_mixed_scope_preserves_covered_uncovered_and_outside_provenance` exercise retired behavior |
| FA-34 | Health iff structural findings | Pending replacement; `test_status_keeps_participation_and_health_distinct` and `test_degraded_health_recovers_without_participation_change` remain applicable; `test_partial_uncovered_path_is_route_unresolved_but_health_valid` and `test_authority_currency_does_not_change_route_identity_or_health` require review against the retired uncovered state |
| FA-35 | Activation of pre-existing normative understanding | `test_newly_active_repository_reassesses_pre_route_normative_revision`; `test_retained_activation_effect_stays_actionable_without_route_support`; `test_installed_cross_repository_governance_journey` |
| FA-36 | Functional Pyramid write propagation | `test_installation_effect_engine_uses_repository_runtime`; `test_governance_only_change_crosses_physical_repository_boundary`; `test_installed_cross_repository_governance_journey` |
| FA-37 | Deactivation/removal route state | `test_deliberately_inactive_repository_reassesses_recorded_route`; `test_functional_route_support_distinguishes_route_states`; `test_record_deactivate_moves_all_members_to_excluded` |
| FA-38 | Operational route failure while ACTIVE | `test_functional_route_support_distinguishes_route_states`; `test_repository_unavailability_is_graph_state_not_unknown_identity` |
| FA-39 | Pyramid-write replay projection | `test_retained_activation_effect_stays_actionable_without_route_support`; `test_installed_cross_repository_governance_journey` |
| FA-40 | Pyramid concurrency | `test_concurrent_overlapping_activation_serializes_to_one_active_instance`; `test_concurrent_revise_and_deactivate_obey_version_cas`; `test_record_revise_enforces_version_cas`; `test_record_deactivate_enforces_version_cas` |
| FA-41 | Initialization declaration edits use ordinary re-alignment | `test_functional_pyramid_skill_covers_result_driven_lifecycle`; `test_governance_only_change_crosses_physical_repository_boundary` |
| FA-42 | Conformance uses the normative input contract | `test_conformance_uses_existing_normative_assertion_contract`; `test_normative_create_derives_route_and_all_applicable_authorities` |
| FA-43 | Acceptance is not runtime completion | `test_unresolved_governance_is_retained_but_qualified_unverifiable`; `test_owner_read_failure_reports_unavailable_without_rejecting_acceptance`; `test_functional_pyramid_skill_covers_result_driven_lifecycle` |
| FA-44 | Participation-write acceptance is not initialization completion | `test_retained_activation_effect_stays_actionable_without_route_support`; `test_installed_cross_repository_governance_journey`; `test_functional_pyramid_skill_covers_result_driven_lifecycle` |
| FA-45 | New capture is not shared reuse | `test_current_capture_is_pending_until_curated` |
| FA-46 | Pending-capture gap | `test_current_capture_is_pending_until_curated`; `test_noncurrent_capture_is_stale_not_pending` |
| FA-47 | Pending-curation discovery | `test_pending_curation_keyset_paging_has_no_skip_or_duplicate`; `test_pending_curation_keyset_paging_resumes_after_restart` |
| FA-48 | Curation does not rewrite or bypass support | `test_curate_accepts_exact_current_revision_and_replays`; `test_curate_rejects_non_current_target_before_mutation`; `test_curation_storage_is_exact_version_aware_and_immutable` |
| FA-49 | Curated reuse | `test_current_capture_is_pending_until_curated` |
| FA-50 | Curation cannot override later support loss | `test_changed_source_is_an_invalidated_gap` |
| FA-51 | Correction resets curation | `test_confirm_inherits_curation_but_semantic_change_does_not` |
| FA-52 | Replacement resets curation | `test_replace_after_curation_starts_replacement_captured` |
| FA-53 | Addition begins captured | `test_add_after_curation_starts_new_lineage_captured` |
| FA-54 | Confirm preserves curated meaning | `test_normative_confirm_reestablishes_changed_server_route_support`; `test_confirm_inherits_curation_but_semantic_change_does_not` |
| FA-55 | Confirm does not invent curation | `test_confirm_of_captured_predecessor_remains_uncurated` |
| FA-56 | Withdrawal is never reusable | `test_withdrawn_curated_lineage_is_not_reusable` |
| FA-57 | Curation is a separate act | `test_curate_cannot_share_actions_with_semantic_mutation` |
| FA-58 | Curation is not governance | `test_normative_confirm_reestablishes_changed_server_route_support`; `test_curated_revision_reconsiders_without_mutating_curation` |
| FA-59 | Normative reuse requires both planes | `test_installed_cross_repository_governance_journey`; `test_mixed_answer_excludes_noncurrent_normative_conclusion` |
| FA-60 | Failed review repairs meaning first | `test_installed_cross_repository_governance_journey` |
| FA-61 | Schema-14 migration fabricates no curation | `test_schema14_state_is_preserved_and_curation_starts_empty` |
| FA-62 | Migrated current knowledge is pending | `test_schema14_current_revision_migrates_as_pending_capture` |
| FA-63 | Three-tool host surface remains exact | `test_only_the_three_core_tools_are_registered` |
| FA-64 | Installed lifecycle closes the loop | `test_installed_cross_repository_governance_journey` |

The matrix names enforcement boundaries; the CI execution receipt remains the
evidence that those tests passed for a particular candidate.
