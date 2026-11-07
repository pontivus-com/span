# Agent lifecycle

The agent investigates, records useful explanations, reuses applicable saved
understanding, and re-aligns affected support. Span does not require a
documentation campaign before ordinary work. See [usage](usage.md) for the
procedure and [MCP reference](mcp.md) for the three-tool grammar.

```
SETUP (installer)
  bind repository, declared authority seeds/bindings, schema 11
  → no understanding is created

ORDINARY SESSION
  ask
    → current answers with content and evidence,
      a gap with inspectable evidence, or the surface document view
  record
    → atomic create/update/verify, or a declared service/domain surface
  reconsider
    → every surface a change affects, with per-conclusion support state
```

## Contexts

`ask` issues or recovers one server-owned context bound to its request identity.
The context is returned in the answer; it may be supplied to `record` or
`reconsider`, but it is never an input to `ask`. A cold gap already carries the
context needed to investigate and record in the same binding. Changing the
question, surface, or other bound request fields under the same `request_id` is
a conflict.

Contexts expire. Expiry removes operational membership only. Accepted
understanding, challenges, verification runs, and retained receipts survive.
A gap's continuation lives exactly as long as its context; after expiry,
abandonment, or reaping it returns a typed `Unavailable`.

## Recording

`record` is atomic. It cites admitted observation or authority references; it
does not resend source bodies. The result is the committed receipt plus a
post-commit support qualification — or `SurfaceDeclared` for a boundary
declaration.

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
preserves the receipt and reports qualification failure separately from
acceptance.

A matching replay returns the retained receipt before new-write dependency
checks. The same identity with different content is a conflict.

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

Hooks are optional event-local notices. They never record, re-check, interpret,
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
