# Agent lifecycle

The agent follows [the required lifecycle](lifecycle-contract.md#required-agent-completion):
consult retained understanding, investigate, record supported conclusions and
re-align affected understanding after edits. See [usage](usage.md) for the
procedure and [MCP reference](mcp.md) for the three-tool grammar.

```
SETUP (installer)
  bind repository, declared authority seeds/bindings, schema 11
  → no understanding is created

ORDINARY SESSION
  ask
    → current surface document view or an honest gap with source pointers;
      explicit evidence admission is separate
  record
    → atomic create/update/verify, or a declared service/domain surface
  reconsider
    → every surface a change affects, with per-conclusion support state
```

## Contexts

Pure surface/reference obtain creates no context and requires no caller request
identity. Explicit evidence admission issues or recovers one persisted
evidence-only context bound to its caller-owned request identity and complete
selection. Changed-scope `reconsider` issues a fresh Span-owned bounded context
for re-establishment. Both expose the same opaque `InvestigationContextRef`;
copy it only into operations that declare a `context` field.

Contexts expire without deleting accepted understanding, challenges,
verification runs, or retained receipts. A continuation is valid only for its
bound live context. Malformed, wrong-binding, missing/non-live/expired,
exhausted, or out-of-position continuation references are typed `Rejected`;
genuine store/provider inability is `Unavailable`. A missing row alone is not
described as expired or reaped.

## Recording

`record` is atomic. It cites direct or admitted evidence without resending
source bodies. Ordinary understanding/verification acceptance carries a receipt
selector, accepted coordinates and post-commit qualification; the immutable
receipt remains in storage for exact retrieval. Surface declaration returns
`SurfaceDeclared`.

- `kind="understanding"` with `conclusion` and exactly one evidence mode —
  `locator`, `observation_id`, or non-empty `support` — creates version 1; scope
  is supplied or derived independently.
- `actions.add`, `confirm`, `correct`, `replace`, and `withdraw` update an exact
  expected version; multiple actions apply atomically. Actions are compact
  deltas: name the conclusion and one evidence mode; Span derives the old
  revision, unchanged content metadata, and the mechanical basis.
- `challenge_dispositions` settles a challenge raised by `reconsider`.
- `kind="verification"` records an independent run against the observations or
  evidence actually tested.
- `kind="surface"` creates a service/domain boundary or updates it with
  compare-and-set.

A verification run applies to the surfaces within its declared scope. A
single-file run is not widened to a broader service, and a service-wide run
applies to the files it covers. A run requires observations or evidence; either
is accepted.

A validation, identity, conflict, or source-drift rejection commits no semantic
transition and names the offending identity. A post-commit `SupportUnavailable`
preserves the accepted effect and receipt selector while reporting qualification
failure separately from acceptance.

A matching replay resolves from the retained receipt before new-write dependency
checks and returns the same compact acceptance. The same identity with different
content is a conflict.

## Currentness

Support is evaluated on retrieval and recording. States are `CURRENT`,
`REASSESSMENT_REQUIRED`, and `UNVERIFIABLE`. A missing authority or observation
stays explicit; it is never promoted to current.

`reconsider` returns every affected surface and every conclusion it considered,
with that conclusion's own support state. Inclusion is not a verdict: a
considered conclusion can remain `CURRENT`. Only non-current states require
re-establishment. A surface with no `conclusions` is containment-only, and the
returned order is deterministic.

A non-current conclusion is still recoverable as historical **content**: an
invalidated `ask` returns the prior statement with its exact revision,
understanding version, evidence references, and present non-current state in
`Gap.historical`. A surface status names the same set through `stale_refs`,
alongside the count. Neither is current answer content; to read the statement,
use `ask(selector=UnderstandingSnapshotSelector{understanding_id, version})`.

Challenges settle only through an explicit disposition in `record`. A new
version, a passing test, or a matching fingerprint does not settle a dispute.
Current support does not certify meaning or complete investigation. Saved gaps
and open disputes remain relevant to the agent's judgment.

## Hooks

Hooks deliver event-local lifecycle reminders. They never record, re-check, interpret,
or rebuild. A missed or disabled hook cannot make stale understanding current;
correctness is evaluated by the lifecycle operations.

## Store transition

The runtime never migrates at open. Older stores use the offline
inspect/apply/verify/rollback commands in [install](install.md). Schema 10
carries the same semantic tables as the target, so each understanding maps to
the path surface named by its recorded single-file scope, with unresolved rows
preserved and reported. Older schemas carry a different meaning: only the
repository binding and declared seeds are carried forward, and their legacy
semantic content remains historical export.
