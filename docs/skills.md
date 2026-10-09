# Agent Skills integration guide

Skills (`skills/span/SKILL.md`, `skills/span-change-context/SKILL.md`,
`skills/span-document/SKILL.md`)
are optional lifecycle/orchestration guidance over the ten canonical
operations. They sit outside the semantic core and the service
contract: semantic correctness never depends on them.

Allowed: when/how to invoke operations, multi-call workflow
composition, preserving `PARTIAL`/`AMBIGUOUS`/`CONFLICTED`/
`UNRESOLVED`/`STALE`/`UNVERIFIABLE` states verbatim, directing
normal repository-level `status` orientation and exact-target
`status`/`refresh` around verification. The repository status inventory is
bounded persisted coverage, not structural enumeration; if the current
runtime returns readiness only, the skill reports the Point 4 activation
gap rather than inferring empty semantic state.

All three skills use the same compact pending-task card: objective; exact
scope and exclusions; evidence and authority; material input-to-terminal
path; typed result; adversarial check; explicit disposition with requirements;
and fresh readback. This is orchestration guidance over the canonical
`TaskBrief`, not a second semantic policy or quality model.

When the user supplies an exact directory or repository target, the skills
direct the host to treat that path as the complete semantic boundary. The
host partitions all material areas within it and applies the same analysis
card to each area, retaining `NOT_APPLICABLE`, `OPEN`, or `PENDING` work with
requirements until it is resolved or explicitly reported. A representative
root, structural `READY`, or a populated store cannot stand in for target
coverage. Without an exact target, the skills require the user to choose a
bounded scope before semantic establishment begins. Exact onboarding path:
`docs/onboarding-runbook.md`.

Forbidden: defining claim/relationship kinds, authority, ownership,
precedence, trust, freshness, or change semantics; reinterpreting
uncertainty into certainty; referencing non-canonical operations.
`tests/unit/test_skills.py` enforces this mechanically (canonical-ops
allowlist, rule-vocabulary scan, uncertainty-preservation presence,
implementation-independence).

Distribution is by filesystem. Serving skills through the MCP Skills
extension is permitted but deferred until a proven consumer exists;
correctness must never depend on it.
