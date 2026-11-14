# Questions, retrieval, and bounds

Obtain retained understanding by exact surface. A pure `ask` names either an
exact `surface={kind, locator}` or an unambiguous `reference`, with no
question, request identity, context, or evidence. It returns the current surface
document view grouped by recorded question. A genuinely unassessed surface
returns a Gap with source pointers; the agent investigates and records what it
establishes.

When the exact recorded question is already known, use
`RecordedQuestionSelector`. It is exact surface-scoped equality, not semantic
search. When source bytes are needed, use explicit evidence admission:
surface/reference plus non-empty `evidence` and a caller-owned `request_id`.

## Result paths

- `Answer`: current supported content, grouped by recorded question for the
  document view, with statement, nature, scope, support/evidence references,
  surface status (including `stale_refs`), recorded gaps, applicable
  verification, and explicit truncation state. `admission` is present only
  when explicit evidence admission ran.
- `Gap`: exactly one reason — `invalidated`, `unverifiable`, or
  `unassessed` — with historical non-current content where applicable,
  missing items, concrete `source_pointers`, status and recovery. It does not
  imply evidence possession. Explicit evidence admission may add the same
  `admission` projection and continuation. A non-matching
  `RecordedQuestionSelector` is `unassessed`; a truncated historical gap's
  recovery names the snapshot selector.
- `AmbiguousSurface`: more than one granularity matches a reference; candidates
  are exact identities. Copy one into `surface`; Span never guesses.
- `RetrievedUnderstanding` / `RetrievedReceipt`: exact-reference history.
  They are never merged into `Answer` and never satisfy current-answer reuse.
- `EvidencePage`: the next exact selected-evidence deliveries, with an optional
  further continuation.
- `Rejected`: caller-correctable invalid selector/reference/binding state,
  including an unusable continuation.
- `Unavailable`: genuine operational failure or a response budget too small to
  carry the minimum result.

Surface-first document view is the normal reuse path. Read it and select the
current conclusion that answers the task. Use exact recorded-question selection
only when that metadata is already known; Span does not rank, embed, paraphrase,
or similarity-match questions.

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
context, original request identity/digest, and the next evidence position.
Pass only the continuation to `ask`; it carries its own namespace. The same
token against the same live context returns the same page. Malformed,
wrong-binding, missing/non-live/expired, exhausted, or out-of-position
continuations are typed `Rejected`; genuine operational failure is
`Unavailable`.

Every page advances by at least one evidence unit or exact line range. An
oversized unit is split at line boundaries; a unit that cannot fit even one line
is refused rather than returned as an empty page. Continuations are not
structural listing cursors and cannot be interchanged with them.

See [freshness](freshness.md) for what current support means.
