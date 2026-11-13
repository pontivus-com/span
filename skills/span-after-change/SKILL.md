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

Each conclusion carries its own support state. `CURRENT` means the surface was
considered but the conclusion still holds. `REASSESSMENT_REQUIRED` or
`UNVERIFIABLE` means actual loss: investigate and re-establish it. A surface
with no `conclusions` is containment-only. Keep the returned order; re-establish returned
conclusions whose state is `REASSESSMENT_REQUIRED` or `UNVERIFIABLE`.

## Then

Use the returned context with `record` or a challenge. Settle a
challenge through `record` with named `challenge_dispositions`. Record new supported conclusions established during the investigation too.
Containment alone does not require changing a conclusion.

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md), [lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md).
