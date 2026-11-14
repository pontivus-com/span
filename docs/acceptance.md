# Acceptance and evidence

The current lifecycle is evaluated at three distinct boundaries: deterministic
contracts, delivered host behavior, and useful real-task reuse. Passing a
local suite proves neither host conversion nor comparative product value.

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

### Remediation scenarios (in progress)

The addendum in
`.context/plans/2026-11-02-mcp-surface-refactor.md` §17 schedules these. Rows
marked pending are not current coverage.

| ID | Behavior | Status | Evidence |
| --- | --- | --- | --- |
| F-20 | Surface-first document view is the normal reuse path; `RecordedQuestionSelector` is exact and surface-scoped, and a non-matching or paraphrased selector returns `Gap/unassessed` without semantic ranking. | implemented | `test_exact_question_without_membership_is_unassessed`, `test_exact_question_selector_does_not_paraphrase_match`, `test_surface_document_view_is_reuse_path` |
| F-21 | A rejection carries the exact cause, required action, and structured current version or boundary version. | implemented | `test_version_conflict_names_the_current_version`, `test_surface_conflict_is_rejected_with_the_current_boundary_version`, `test_replay_conflict_carries_its_own_cause`, `test_verification_requires_admitted_observation`, `test_schema_version_failure_is_unavailable_not_rejected`, `test_malformed_ingress_is_a_transport_error` |
| F-22 | A create with a question context uses the bound target; supplying an explicit question or scope is rejected. | implemented | `test_context_bound_create_rejects_an_explicit_target`, `test_question_context_rejects_an_explicit_target` |
| F-23 | A stale surface boundary version or surface kind conflict is `Rejected`, not `Unavailable`. | implemented | `test_surface_update_stale_boundary_returns_rejected`, `test_surface_kind_conflict_returns_rejected` |
| F-24 | A declared surface parent must be declared, same-repository, and acyclic. | implemented | `test_surface_parent_must_be_declared`, `test_surface_update_rejects_a_parent_cycle` |
| F-25 | A verification run appears only on the surfaces in its declared scope. | implemented | `test_verification_run_appears_only_on_its_scope`, `test_multi_file_run_is_visible_on_each_file`, `test_one_file_run_is_not_visible_on_a_broader_service`, `test_service_wide_run_is_visible_on_service_and_files`, `test_directory_scoped_run_covers_files_under_it`, `test_symbol_run_matches_through_containing_file`, `test_symbol_without_a_file_prefix_is_excluded`, `test_multi_file_verification_run_is_visible_on_each_file` (installed MCP lane) |
| F-26 | With the delivered product surface (server plus installer-managed pre-read notice and readiness wait), the first Span call precedes the first source read; bare registration is not claimed. | implemented — OpenCode 5/5 | `natural-use/F10-2026-11-03.md`; Codex 5/5 pre-remediation in `natural-use/realistic/REALISTIC.md` |
| F-27 | Cost is claimed only for a named task class with positive measured value. | implemented | `five-task/MATRIX.md` (reuse, break-even 2), `g5/REUSE.md` (break-even 11); single-use cross-file is negative and not claimed |
| F-29 | A create without a surface derives it from one scope path or the question context; multiple paths are rejected with the candidates, and a supplied surface must agree with the carried scope. | implemented | `test_create_without_surface_derives_from_one_scope_path`, `test_create_without_surface_uses_the_question_context_scope`, `test_create_without_surface_rejects_multiple_paths`, `test_create_surface_must_agree_with_the_carried_scope`, `five-task/DERIVED-SURFACE.md` |
| F-30 | A create states one conclusion with exactly one evidence mode (`locator`, `observation_id`, or non-empty `support`); scope is supplied or derived independently; Span stores explicit support as supplied and derives the basis, new lineage id, and surface. | implemented | `test_record_create_through_the_one_request`, `test_create_without_surface_derives_from_one_scope_path`, `test_create_with_support_only_derives_scope_from_context`, `test_create_with_support_and_no_surface_derives_scope_from_context`, `test_service_context_binds_the_scope_of_a_support_create`, `test_record_accepts_every_support_kind`, `five-task/TASK1-FLAT.md` |

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

Capture installed build/command, advertised schemas, model-delivered
declarations, requests/results, representation duplication, and recovery and
concurrency behavior. Codex and OpenCode are supported live targets with
candidate-specific delivery captures. Claude Code is a supported managed host
for registration, health inspection, and installer behavior, but its
authenticated model-delivery grammar and caller identity remain
**UNVERIFIED**. Hook wiring is separate from observed arrival.

## Product value

Compare equivalent real tasks with and without Span. Separate mandatory
conformance from natural use, cold recording from fresh-session reuse, and
calibration from a precommitted scored evaluation. Preserve task quality,
prerequisites, calls, tokens (cached separately), wall time, failures, omissions,
recording overhead, and useful focused reassessment. A populated store is not
useful reuse. An ACCEPT requires the frozen decision rule to pass.

Current beta calibration demonstrates recorded reuse but does not establish
a final comparative ACCEPT or universal time/token saving.

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
