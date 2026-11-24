---
name: span-after-change
description: Re-align Span after editing files. Use when a covered surface changed, a conclusion may have lost support, or a recorded conclusion is disputed and must be re-examined or challenged.
---

# After you edit: reconsider

Complete the applicable lifecycle before task completion; report named operational
blockers explicitly. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#required-agent-completion).


Call `reconsider` with the paths you just changed:

```json
{"repository_id": "repo-1", "changed_paths": ["src/retention.py"]}
```

The result is `Changed`, `Challenged`, `Rejected`, or `Unavailable`.

`Changed` names every affected surface and why it was considered:

- `CONTAINMENT` — a declared boundary contains a changed path;
- `DIRECT` — a conclusion cites source or discovery evidence that changed;
- `INDIRECT` — a premise dependent, walked to a fixed point.

Each conclusion carries its own support state. Reconsider traverses retained
CAPTURED and CURATED revisions; it does not change curation. `CURRENT` means
the conclusion was considered and its required support remains current; it is
not a semantic-truth certification.
`REASSESSMENT_REQUIRED` or `UNVERIFIABLE` means actual support loss:
investigate and re-establish it. A CURATED revision with non-current support is
not shared Answer content but keeps its curation history. A surface with no
`conclusions` is containment-only. Keep the returned order; re-establish
returned conclusions whose state is `REASSESSMENT_REQUIRED` or `UNVERIFIABLE`.

## Then

Functional Pyramid governance changes use the same affected-surface/conclusion
projection and may return effects in other member repositories. When those
effects came directly from an accepted Functional Pyramid participation write,
do not call `reconsider` again for that write; follow its returned contexts via
the `span-functional-pyramid` skill.

Use the returned re-establishment context with `record`. To dispute a
recorded conclusion, call `reconsider` with the challenge branch; do not copy
the changed-scope context into that request because Span derives the challenge
context from the challenged target and admitted evidence. A semantic-preserving
confirm can re-establish support while preserving inherited curation; a semantic
correction/replacement becomes CAPTURED and requires separate curation for
shared reuse. Settle a challenge through `record` with named
`challenge_dispositions`. A resolved
disposition supplies semantic intent (challenge/revision, reasoning, optional
target lineage IDs and context-bound evidence refs); Span derives the resulting
version/revision coordinates. Record new supported conclusions established
during the investigation too.
Containment alone does not require changing a conclusion.

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md), [lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md).
