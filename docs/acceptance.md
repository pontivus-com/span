# Acceptance and evidence

The 0.9.0 lifecycle is evaluated at three distinct boundaries: deterministic
contracts, delivered host behavior, and useful real-task reuse. Passing a
local suite proves neither host conversion nor comparative product value.

## Behavioral scenarios

The functional scenario set covers:

| ID | Behavior | Representative current tests |
| --- | --- | --- |
| F-01 | Cold scoped question returns useful evidence and honest gaps. | `test_cold_question_admits_inspectable_evidence` |
| F-02 | Record a real supported investigation and inspect its receipt. | `test_create_records_and_replays`, installed MCP lane |
| F-03 | Fresh-session discovery without a supplied saved ID. | installed MCP fresh-process lane, host capture |
| F-04 | Relevant support change requires reassessment. | `test_source_support_current_changed_missing` |
| F-05 | Unrelated change preserves independent support. | `test_unrelated_source_change_keeps_current` |
| F-06 | Confirm/correct preserves revisions and version history. | `test_full_update_chain_preserves_history` |
| F-07 | Explicit challenges retain unresolved state and settlement history. | challenge transition and lifecycle-store tests |
| F-08 | Exact CSS/config evidence works without symbols. | `test_cross_file_batch_admits_each_source` |
| F-09 | Retry, restart, lost-response, and concurrent identities recover safely. | lifecycle service/store replay and concurrency tests |
| F-10 | Independent verification remains tied to tested observations. | `test_verification_runs_are_independent_and_source_aware` |
| F-11 | Correctness holds without hooks. | lifecycle tests, hooks-disabled Codex capture |
| F-12 | Batch outcomes, reference reuse, and membership changes remain explicit. | evidence/discovery/support service tests |
| F-13 | Missing, ambiguous, failed, expired, and truncated outcomes differ. | evidence, understand, and lifecycle tests |
| F-14 | Operational retention preserves accepted semantic history. | lifecycle-store reaping and replay-retention tests |

This maps representative coverage; a named test does not certify every clause
of a scenario or claim a host executed it. Read test assertions and execution
receipts for the exact demonstrated boundary.

## Contract and artifact verification

The suite exercises strict codecs and schemas, pure rules, atomic persistence,
compare-and-set transitions, recovery, support checks, bounds, readiness,
hooks, isolation, skills, and managed assets. The installed-MCP lane builds a
non-editable install and drives `span-mcp` over stdio outside the source tree.
The transition lane uses disposable stores, including archive/export/verify,
interruption recovery, active-writer refusal, and rollback preservation.

Use [contributing](contributing.md) for commands. The zero-error typing baseline
is the beta gate; a passing ratchet with pre-existing errors is insufficient.
Clean builds, packaged assets, docs, version, and changelog extraction are
separate release checks.

## Host evidence

Capture installed build/command, advertised schemas, model-delivered
declarations, requests/results, representation duplication, and recovery and
concurrency behavior. Codex is the live beta validation target. OpenCode's
earlier captures do not prove final-package delivery; Claude live grammar
and caller identity remain UNVERIFIED under the owner waiver. Hook wiring
is separate from observed arrival.

## Product value

Compare equivalent real tasks with and without Span. Separate mandatory
conformance from natural use, cold recording from fresh-session reuse, and
calibration from a precommitted scored evaluation. Preserve task quality,
prerequisites, calls, tokens (cached separately), wall time, failures, omissions,
recording overhead, and useful focused reassessment. A populated store is not
useful reuse. An ACCEPT requires the frozen decision rule to pass.

Current beta calibration demonstrates recorded reuse but does not establish
a final comparative ACCEPT or universal time/token saving.

## Historical evidence

[acceptance-evidence/](acceptance-evidence/) contains older transcripts and
fixtures. They retain their original protocol/results and do not prove the
new API, delivered grammar, or product-fitness acceptance. Current execution
receipts identify their candidate revision and tested boundary explicitly.
