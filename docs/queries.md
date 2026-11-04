# Questions, retrieval, and bounds

Ask a scoped engineering question with `ask`, naming either an exact
`surface={kind, locator}` or a reference the agent is looking at. The answer
comes from retained understanding, never from first principles. A first-contact
question on an unassessed surface returns a gap with inspectable evidence; the
agent investigates and then records the result.

## Result paths

- `Answer`: every matched conclusion is current. It carries `ConclusionView`s
  with statement, nature, scope, support, and evidence; the surface status
  distribution (including `stale_refs`); recorded gaps; applicable
  `VerificationView`s; and an explicit truncation state when the server budget
  omitted content.
- `Gap`: exactly one reason — `invalidated`, `unverifiable`, `unassessed`, or
  `no_match` — with the prior non-current conclusions as historical content
  (statement, exact revision, understanding version, evidence references, and
  present state), admitted evidence, the context, the missing items, and a
  recovery. It carries a continuation when evidence was omitted. A `no_match`
  gap points back to the surface document view. A truncated gap's recovery
  names the snapshot selector.
- `AmbiguousSurface`: more than one granularity matches the reference; the
  candidates are exact identities. Copy one into `surface`; Span never guesses.
- `RetrievedUnderstanding` / `RetrievedReceipt`: exact-reference history. They
  are never merged into `Answer` and never satisfy the current-answer guarantee.
- `EvidencePage`: omitted gap evidence with an optional further continuation.
- `Unavailable`: an operational failure, an invalid continuation, or a response
  budget too small to carry the minimum result, always with a recovery action.

With no question, `ask` returns the surface document view: current conclusions
grouped by the question they answer, plus status, gaps, and verification. The
view is assembled on read and cannot drift.

That view is the normal reuse path. Read it and select the current conclusion
that answers the task; an exact question is a targeted query. A paraphrase is a
different question and returns `no_match`; its recovery tells the agent to read
the document view. Span does not rank, embed, or semantically match questions.

## Retrieve exact detail

Use `ask` with an `UnderstandingSnapshotSelector` for a current or exact
snapshot, or a `ReceiptRetrievalSelector` for a retained receipt. A receipt can
survive its context; missing context detail does not revoke committed
acceptance. Snapshot retrieval evaluates support and returns challenges
alongside the recorded content.

`ask` also returns applicable verification runs and their live qualification.
A run applies to the surfaces within its declared scope; a single-file run is
not widened to a broader service. There is no separate qualification call.
Neither retrieval nor qualification performs semantic reinterpretation or
external test execution.

## Bounds and truncation

The agent does not manage response size. Layer 4 owns the per-host budget and
applies it at the composition boundary. A truncated result names what was
omitted; truncation never promotes historical content into the answer. If the
budget cannot carry the result kind, the surface identity, and the fact of
truncation, the operation returns `Unavailable` rather than a misleading
fragment.

## Continuations

A continuation is an opaque, stateless token bound to a repository, live
context, original request identity and digest, and the next evidence position.
Pass it to `ask` with the same repository. The same token against the same live
context returns the same page. Expired, abandoned, reaped, unknown, or
mismatched tokens return `Unavailable`.

Every page advances by at least one evidence unit or exact line range. An
oversized unit is split at line boundaries; a unit that cannot fit even one line
is refused rather than returned as an empty page. Continuations are not
structural listing cursors and cannot be interchanged with them.

See [freshness](freshness.md) for what current support means.
