---
name: span-before-you-read
description: Ask Span before reading or grepping source when the question is about understanding rather than syntax. Use when orienting in unfamiliar code, checking a saved explanation, or deciding whether source inspection is still needed.
---

# Before you read: ask

Complete the applicable lifecycle before task completion; report named operational
blockers explicitly. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#required-agent-completion).


Call `ask` with the surface and no question or request identity. This is both
the reuse path and the cold-start probe:

```json
{
  "repository_id": "repo-1",
  "surface": {"kind": "FILE", "locator": "src/service.py"}
}
```

When you already know an exact recorded question and want only that membership,
use `RecordedQuestionSelector`; it performs exact equality within the supplied
surface and is not semantic search.

Use `reference` instead of `surface` only when a path or declared name resolves
to exactly one surface. If the result is `AmbiguousSurface`, copy one candidate
into `surface`; do not re-resolve the same path.

Read the surface document view and select the current curated conclusion that
answers the task. Ordinary Answer content is shared reusable knowledge only when
the exact semantic revision is both CURRENT and CURATED. A genuinely unassessed
surface returns `Gap/unassessed`; exact recorded question lookup is optional
and never relies on paraphrase or similarity matching.

## Read the result

- `Answer` — CURRENT + CURATED conclusions with statement, nature, scope,
  support, and evidence, plus surface status. For ACTIVE Functional Pyramid participation,
  the same result also carries governing orientation for the selected semantic
  scope; use `span-functional-pyramid` for status/candidate/participation work. `status.stale_refs` names each stale
  conclusion by exact revision, understanding version, and present state. Reuse current conclusions; investigate stale references
  through their historical content and current evidence.
- `Gap` — no shared reusable conclusion. It carries status, the reason,
  historical non-current conclusions where applicable, source pointers, and
  recovery. CURRENT captured-only meaning is reported as Gap/pending_curation
  rather than ordinary Answer content. Source
  bytes are not dumped automatically. Select only the evidence you need through
  an explicit evidence-admission `ask`, then `record` what you establish.
- `AmbiguousSurface` — choose the file, symbol, service, or domain surface.
- `Unavailable` — an operational failure or a response too small for the
  minimum result. Follow its recovery.
- `EvidencePage` — omitted gap evidence. Continue until the gap is complete.

When an explicit evidence delivery carries a `continuation`, call `ask` with
only that continuation. Treat returned context references as opaque handles:
copy them only into operations that declare a context field.

## Reviewer / curator obtain

A reviewer who is selecting captured knowledge for shared reuse uses
PendingCurationSelector with the repository identity. It returns only CURRENT
captured exact revisions in deterministic order. Retrieve and inspect the exact
capture and relevant retained knowledge/governance before curation; if the
meaning is wrong or incomplete, repair it through the ordinary semantic
lifecycle first.

## Then

Finish the engineering investigation with `record`. Do not record source text
as a conclusion; record the supported statement the agent established. A new or
semantically changed conclusion is capture, not self-publication, and may remain
pending separate review after the engineering task is complete.

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md), [queries](https://github.com/pontivus-com/span/blob/master/docs/queries.md).
