# Agent Skills integration guide

Skills (`skills/span/SKILL.md`, `skills/span-change-context/SKILL.md`,
`skills/span-document/SKILL.md`)
are optional lifecycle/orchestration guidance over the eight canonical
operations. They sit outside the semantic core and the service
contract: semantic correctness never depends on them.

Allowed: when/how to invoke operations, multi-call workflow
composition, preserving `PARTIAL`/`AMBIGUOUS`/`CONFLICTED`/
`UNRESOLVED`/`STALE`/`UNVERIFIABLE` states verbatim, directing
`impact` before material changes and `status`/
`refresh` around verification.

Forbidden: defining claim/relationship kinds, authority, ownership,
precedence, trust, freshness, or change semantics; reinterpreting
uncertainty into certainty; referencing non-canonical operations.
`tests/unit/test_skills.py` enforces this mechanically (canonical-ops
allowlist, rule-vocabulary scan, uncertainty-preservation presence,
implementation-independence).

Distribution is by filesystem. Serving skills through the MCP Skills
extension is permitted but deferred until a proven consumer exists;
correctness must never depend on it.
