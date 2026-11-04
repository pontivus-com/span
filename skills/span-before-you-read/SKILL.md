---
name: span-before-you-read
description: Ask Span before reading or grepping source when the question is about understanding rather than syntax. Use when orienting in unfamiliar code, checking a saved explanation, or deciding whether source inspection is still needed.
---

# Before you read: ask

Call `ask` with a question and one surface:

```json
{
  "repository_id": "repo-1",
  "request_id": "ask-1",
  "surface": {"kind": "FILE", "locator": "src/service.py"},
  "question": "How is the retention value determined?"
}
```

Use `reference` instead of `surface` only when a path or declared name resolves
to exactly one surface. If the result is `AmbiguousSurface`, copy one candidate
into `surface`; do not re-resolve the same path.

For reuse, call `ask` with the surface and no question. Read the surface document
view and select the current conclusion that answers the task. Use an exact
question only when you know the recorded question; a paraphrase is a different
question and returns `no_match`, whose recovery points back to the document view.

## Read the result

- `Answer` — current conclusions with statement, nature, scope, support, and
  evidence, plus surface status. `status.stale_refs` names each stale
  conclusion by exact revision, understanding version, and present state. Use
  it instead of re-deriving the same understanding.
- `Gap` — no current conclusion. It carries the reason, the prior non-current
  conclusions as historical content (statement, exact revision, understanding
  version, evidence references, present state), admitted evidence,
  observations, a context when the gap is question-bound, and a recovery. If
  the reason is `no_match`, ask the same surface without a question to read its
  current document view. Otherwise read the evidence, then `record` what you
  establish. A truncated gap's recovery names the snapshot selector.
- `AmbiguousSurface` — choose the file, symbol, service, or domain surface.
- `Unavailable` — an operational failure or a response too small for the
  minimum result. Follow its recovery.
- `EvidencePage` — omitted gap evidence. Continue until the gap is complete.

When a gap carries a `continuation`, call `ask` with only the repository and
that continuation. Never fetch or construct a context id.

## Then

Finish the investigation with `record`. Do not record source text as a
conclusion; record the supported statement the agent established.

Detail: [MCP reference](../../docs/mcp.md), [queries](../../docs/queries.md).
