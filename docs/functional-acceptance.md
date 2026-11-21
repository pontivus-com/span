# Version 1 Beta functional acceptance matrix

This matrix is the executable traceability surface for
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance).
It does not redefine the acceptance cases. Each row names the live boundary tests
that demonstrate the corresponding behavior. The test suite validates that FA-01
through FA-44 are present exactly once and that every named test still exists.

| ID | Functional acceptance case | Live test evidence |
|---|---|---|
| FA-01 | Unconfigured versus excluded | `test_status_projects_inactive_and_live_active_health`; `test_record_exclude_has_no_semantic_effect_projection`; `test_descriptive_recording_does_not_gain_route_support` |
| FA-02 | Pure action-aware candidate validation | `test_valid_activate_candidate_is_ready`; `test_revision_candidate_reports_unknown_and_stale_target`; `test_candidate_reports_duplicate_unregistered_and_other_active_members` |
| FA-03 | Activation and replay | `test_record_activate_commits_members_effects_and_receipt`; `test_invalid_activation_leaves_participation_state_unchanged`; `test_record_replay_preserves_receipt_without_new_effect_discovery`; `test_installed_lifecycle_over_stdio` |
| FA-04 | Revision and removal | `test_record_revise_only_reports_actual_participation_changes`; `test_record_revise_enforces_version_cas`; `test_revision_candidate_reports_unknown_and_stale_target` |
| FA-05 | Partial coverage | `test_partial_uncovered_path_is_route_unresolved_but_health_valid`; `test_wholly_outside_scope_is_resolved_empty_governance` |
| FA-06 | Complete coverage | `test_complete_coverage_remainder_is_candidate_validation_finding`; `test_complete_uncovered_scope_degrades_health` |
| FA-07 | Degraded-health recovery | `test_degraded_health_recovers_without_participation_change`; `test_degraded_instance_can_resolve_unaffected_local_route` |
| FA-08 | Cold governed path | `test_cold_governed_path_returns_gap_with_governing_view` |
| FA-09 | Same semantic scope | `test_exact_question_selector_does_not_paraphrase_match`; `test_surface_kind_prevents_filename_heuristic_scope_inference`; `test_declared_symbol_boundary_is_exact_functional_pyramid_scope` |
| FA-10 | Overlapping contexts | `test_overlapping_direct_contexts_precede_inherited_contexts` |
| FA-11 | Distributed context | `test_one_context_can_cover_disconnected_paths` |
| FA-12 | Multi-path and broad semantic scope | `test_broad_scope_crossing_boundary_is_mixed_and_resolved_when_covered`; `test_overlapping_direct_contexts_precede_inherited_contexts` |
| FA-13 | Membership is not applicability | `test_route_identity_ignores_instance_version_and_unrelated_member` |
| FA-14 | Cross-repository authority | `test_unavailable_member_is_distinct_from_unknown_context`; `test_rule_owner_uses_existing_authority_resolver` |
| FA-15 | Authority graph defects | `test_authority_graph_defects_are_explicit` |
| FA-16 | Route versus authority currency | `test_authority_currency_does_not_change_route_identity_or_health`; `test_authority_support_status_and_presence` |
| FA-17 | Normative create | `test_normative_create_derives_route_and_all_applicable_authorities`; `test_unresolved_governance_is_retained_but_qualified_unverifiable` |
| FA-18 | Descriptive create | `test_descriptive_recording_does_not_gain_route_support` |
| FA-19 | Authority-content change | `test_authority_currency_does_not_change_route_identity_or_health`; `test_authority_source_change_is_considered_not_forced_stale`; `test_authority_support_status_and_presence` |
| FA-20 | Applicability change | `test_material_applicability_changes_change_route_identity`; `test_functional_route_support_distinguishes_route_states`; `test_governance_only_change_crosses_repository_boundary` |
| FA-21 | Reverse authority navigation | `test_reverse_context_dependents_include_inheritance_closure` |
| FA-22 | Cross-repository reconsideration | `test_governance_only_change_crosses_repository_boundary` |
| FA-23 | Implementation change | `test_changed_path_maps_containment_direct_and_indirect`; `test_discovery_membership_change_is_direct` |
| FA-24 | Mixed answer | `test_descriptive_answer_survives_unresolved_governing_route`; `test_unresolved_governance_is_retained_but_qualified_unverifiable` |
| FA-25 | Canonical-source singularity | `test_functional_pyramid_carries_references_not_governing_prose` |
| FA-26 | Runtime lifecycle preservation | `test_three_tool_journey_and_restart`; `test_reconsider_record_succeeds_without_an_intervening_ask`; `test_challenge_raised_by_reconsider_is_settled_by_record` |
| FA-27 | Governance-source edit lifecycle | `test_authority_source_change_is_considered_not_forced_stale`; `test_governance_only_change_crosses_repository_boundary`; `test_normative_confirm_reestablishes_changed_server_route_support` |
| FA-28 | Participation-aware hooks | `test_functional_pyramid_unconfigured_notice_routes_to_skill`; `test_functional_pyramid_excluded_notice_is_silent`; `test_functional_pyramid_active_valid_notice_is_silent`; `test_functional_pyramid_active_degraded_notice_routes_to_lifecycle`; `test_hook_source_has_no_semantic_writer_or_builder` |
| FA-29 | Initialization handoff | `test_activation_handoff_status_matches_committed_result`; `test_installed_lifecycle_over_stdio` |
| FA-30 | One active instance per repository | `test_candidate_reports_duplicate_unregistered_and_other_active_members`; `test_concurrent_overlapping_activation_serializes_to_one_active_instance` |
| FA-31 | Three-tool host surface | `test_only_the_three_core_tools_are_registered`; `test_installed_lifecycle_over_stdio` |
| FA-32 | Outside FunctionalScope | `test_wholly_outside_scope_is_resolved_empty_governance`; `test_outside_functional_scope_records_resolved_empty_route_only` |
| FA-33 | Broad scope crossing the functional boundary | `test_broad_scope_crossing_boundary_is_mixed_and_resolved_when_covered`; `test_mixed_scope_preserves_covered_uncovered_and_outside_provenance` |
| FA-34 | Health iff structural findings | `test_status_keeps_participation_and_health_distinct`; `test_partial_uncovered_path_is_route_unresolved_but_health_valid`; `test_degraded_health_recovers_without_participation_change`; `test_authority_currency_does_not_change_route_identity_or_health` |
| FA-35 | Activation of pre-existing normative understanding | `test_newly_active_repository_reassesses_pre_route_normative_revision`; `test_pyramid_effect_coordinator_uses_shared_dependency_engine` |
| FA-36 | Functional Pyramid write propagation | `test_pyramid_effect_coordinator_uses_shared_dependency_engine`; `test_record_replay_live_projects_only_retained_effect_refs`; `test_governance_only_change_crosses_repository_boundary` |
| FA-37 | Deactivation/removal route state | `test_deliberately_inactive_repository_reassesses_recorded_route`; `test_record_deactivate_moves_all_members_to_excluded` |
| FA-38 | Operational route failure while ACTIVE | `test_functional_route_support_distinguishes_route_states`; `test_repository_unavailability_is_graph_state_not_unknown_identity` |
| FA-39 | Pyramid-write replay projection | `test_record_replay_live_projects_only_retained_effect_refs` |
| FA-40 | Pyramid concurrency | `test_concurrent_overlapping_activation_serializes_to_one_active_instance`; `test_concurrent_revise_and_deactivate_obey_version_cas`; `test_record_revise_enforces_version_cas`; `test_record_deactivate_enforces_version_cas` |
| FA-41 | Initialization declaration edits use ordinary re-alignment | `test_functional_pyramid_skill_covers_result_driven_lifecycle`; `test_governance_only_change_crosses_repository_boundary` |
| FA-42 | Conformance uses the normative input contract | `test_conformance_uses_existing_normative_assertion_contract`; `test_normative_create_derives_route_and_all_applicable_authorities` |
| FA-43 | Acceptance is not runtime completion | `test_unresolved_governance_is_retained_but_qualified_unverifiable`; `test_owner_read_failure_reports_unavailable_without_rejecting_acceptance`; `test_functional_pyramid_skill_covers_result_driven_lifecycle` |
| FA-44 | Participation-write acceptance is not initialization completion | `test_pyramid_effect_coordinator_uses_shared_dependency_engine`; `test_record_replay_live_projects_only_retained_effect_refs`; `test_functional_pyramid_skill_covers_result_driven_lifecycle` |

The matrix names enforcement boundaries; the CI execution receipt remains the
evidence that those tests passed for a particular candidate.
