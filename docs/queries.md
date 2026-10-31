# Questions, retrieval, and bounds

Ask an engineering question with `understand_question`; the agent interprets
the result. Saved understanding is discovered through scope association and
term overlap. Candidates retain their match reasons and ambiguity. Neither a
match nor a `CURRENT` qualification proves applicability or correctness.

## Result paths

- `UnderstandingCandidateAnswer`: saved candidate identities and qualified
  snapshots, or public references when details exceed the budget.
- `InvestigationNeeded`: a recoverable context, inspected source evidence,
  per-item admission outcomes, and an explicit gap.
- `DiscoveryLimit`: the bounded scan found no usable candidate/scope; inspect
  the reason and any continuation. Repository-wide absence is not asserted.
- `ResponseBudgetExceeded`: the requested byte allowance cannot hold the
  minimum reduced response; retry with a larger allowance or narrower scope.

Request/result schemas are owned by [MCP reference](mcp.md) and the installed
`tools/list`. The substantive result includes its qualifications, limits, and
next action; large supporting detail may require public retrieval. The old
requirement that every detail body travel in the same answer is retired.

## Retrieve exact detail

`understand_retrieve` has three selectors: an understanding snapshot (current
or exact version), a context with admitted excerpts/discovery observations, or
a retained receipt. A receipt can survive its context; missing context detail
does not revoke committed acceptance. Snapshot retrieval evaluates support
and returns challenges alongside the recorded content.

Use `reassess` to qualify a selected understanding/version and
`verification_support` to qualify an independent recorded run. Neither
operation performs semantic reinterpretation or external test execution.

## Bounded discovery and delivery

A discovery request scans at most one stored page, bounded by `max_results`.
No match on that page does not establish absence on later pages. Question
answers apply `max_evidence_bytes` to the complete canonical response,
including candidates, snapshots, context, and cold evidence. They can replace
bodies with references, omit details explicitly, and provide a continuation.
There is no oversized-first-item exception for an ordinary answer.

The explicit `ResponseBudgetExceeded` refusal is control output; it can
itself exceed an impossibly small allowance. This budget is not a guarantee
on host context size: MCP delivers both text and structured content, and host
declarations and rendering add their own overhead. Other tools have their
own declared bounds; exact retrieval is not the question's byte-budget page.

## Cursors and identities

Pass each returned cursor unchanged to the same operation with the same
request identity, question, scope, and bounds. A cursor changes position,
not the context binding. Discovery and inventory cursors resume different
listings; they cannot be interchanged with structural navigation cursors.
There is no interpretation continuation in the 0.9.0 lifecycle.

Truncated inventory cannot stand in for a complete discovery observation.
Absence/completeness conclusions require the recorded membership boundary
they actually depend on. See [freshness](freshness.md).
