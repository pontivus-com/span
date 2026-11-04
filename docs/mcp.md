# MCP reference

Span runs over stdio:

```bash
span-mcp --data-dir DIR [--repo /path ...]
```

`--repo` registers repository identity for discovery. It opens no store and
performs no structural build; context opens lazily on the first
repository-scoped call. Setup belongs to the installer.

## Tools

Exactly three core tools ship, one per lifecycle moment:

| Tool | Lifecycle verb | Job |
| --- | --- | --- |
| `ask` | obtain | Current understanding or gap |
| `record` | retain | Create, update, verify, or declare a surface |
| `reconsider` | re-align | Changed scope or challenge |

`structure` and `setup` are not registered in this build. The host's own file
navigation covers structural lookup, and the installer covers setup. An optional
`structure` tool may be delivered later for hosts without navigation; it is not
part of the default surface.

`record` carries `kind` (`understanding`, `verification`, or `surface`). An
understanding create is flat — one `conclusion` plus `locator` or
`observation_id`; `actions` is for updates and `action` for a surface
declaration. Those are semantic fields, not separate tools. Only the current
three names are registered. Any other operation name follows the ordinary typed
`unknown_tool` error path and performs no work.

Every repository-scoped request carries its canonical `repository_id`. Paths are
never accepted as IDs.

## `ask`

Forms (exactly one):

```json
{"repository_id": "repo-1", "request_id": "ask-1", "surface": {"kind": "FILE", "locator": "src/a.py"}, "question": "What does it do?"}
{"repository_id": "repo-1", "request_id": "ask-2", "reference": "src/a.py", "question": "What does it do?"}
{"repository_id": "repo-1", "request_id": "ask-3", "reference": "src/a.py"}
{"repository_id": "repo-1", "selector": {"$type": "UnderstandingSnapshotSelector", "repository_id": "repo-1", "understanding_id": "u:...", "version": 1}}
{"repository_id": "repo-1", "selector": {"$type": "ReceiptRetrievalSelector", "repository_id": "repo-1", "request_id": "write-1"}}
{"repository_id": "repo-1", "continuation": "span1_..."}
```

- `surface` is an exact `{kind, locator}` identity. It resolves by identity,
  never containment. `kind` is `FILE`, `SYMBOL`, `SERVICE`, or `DOMAIN`.
- `reference` is the convenience form. It must resolve to exactly one surface;
  otherwise the result is `AmbiguousSurface` with exact candidate identities.
- `surface`/`reference` without a question returns the surface document view.
  This is the normal reuse path: a fresh agent that does not know the exact
  recorded question reads the view and selects the conclusion it needs. An exact
  `question` is a targeted query and matches by exact identity; a paraphrase is a
  different question.
- `selector` returns a historical `RetrievedUnderstanding` or
  `RetrievedReceipt`. These are never merged into `Answer` and never counted
  current.
- `continuation` returns an `EvidencePage` for evidence omitted from a gap.

`context_id` is never an `ask` input. A context is returned in the answer and
may be supplied to `record` or `reconsider`.

Results: `Answer`, `Gap`, `AmbiguousSurface`, `RetrievedUnderstanding`,
`RetrievedReceipt`, `EvidencePage`, or `Unavailable`.

- `Answer` carries `ConclusionView`s (ref, statement, nature, scope, support,
  evidence), surface status, gaps, applicable `VerificationView`s (run plus
  qualification), context, and explicit truncation state. The surface status
  carries `stale_refs`: each names the exact conclusion revision, the
  understanding version that holds it, and its present non-current support
  state. Descendant statuses keep their own refs.
- `Gap` carries one reason (`invalidated`, `unverifiable`, `unassessed`,
  `no_match`), historical conclusions with their statement, evidence
  references, and present non-current state, admitted evidence, observations,
  context, a recovery, and a `continuation` when evidence was omitted. A
  `no_match` gap tells the agent to ask the same surface without a question.
  Historical content is never mixed into `conclusions`. To read a referenced
  stale statement directly, use
  `ask(selector=UnderstandingSnapshotSelector{understanding_id, version})`.
- `AmbiguousSurface` carries exact `SurfaceKey` candidates. Copy one into
  `surface`; do not re-resolve the path.
- `EvidencePage` carries evidence units and an optional further continuation.
  It is evidence, not current conclusion content.

### Continuation

A continuation is opaque and stateless. It binds the repository, investigation
context, original request identity and digest, and the next evidence position.
It is valid while the context is `LIVE`; expired, abandoned, reaped, unknown, or
wrong-repository tokens return `Unavailable` with a recovery. The same token
against the same live context returns the same page. A page always advances by
at least one evidence unit or exact line range; an oversized unit is split at
line boundaries, and a unit that cannot fit even one line is refused rather than
returned as an empty page.

## `record`

```json
{
  "repository_id": "repo-1",
  "request_id": "write-1",
  "kind": "understanding",
  "question": "What does it do?",
  "scope_paths": ["src/a.py"],
  "conclusion": "It does a thing.",
  "locator": "src/a.py"
}
```

A create carries one conclusion. `locator` is the file the conclusion is
about; `observation_id` from an `ask` gap may replace it. `surface` is optional
and derived from the carried scope. `assertion_nature` defaults to
`DESCRIPTIVE`; `conclusion_id` defaults to `c-1`. An understanding create
takes no `action` and no `actions`: `action` belongs to `kind="surface"` and
`actions` to updates. Sending either is an ingress error.

Updates use `actions` with `add`, `confirm`, `correct`, `replace`, or `withdraw`,
plus `understanding_id` and `expected_version`. Multiple keys apply atomically.
`challenge_dispositions` settles a challenge raised by `reconsider`.

A create may supply the `context_id` returned by `ask` (including a cold gap).
The context's bound question and scope are used; do not also send `question` or
`scope_paths` — that conflict is rejected. Without a context, a create requires
`question` and issues its own evidence-only context.

Surface declaration:

```json
{
  "repository_id": "repo-1",
  "request_id": "surface-1",
  "kind": "surface",
  "action": "create",
  "surface": {
    "kind": "SERVICE",
    "locator": "billing",
    "boundary": {"paths": ["src/billing/"], "symbols": []},
    "parent": null
  }
}
```

`SERVICE` and `DOMAIN` require a boundary; `FILE` and `SYMBOL` reject one.
`action="update"` requires `expected_boundary_version` and advances exactly one
version. A declared surface must exist before understanding is recorded against
it. A parent must be an existing declared surface in the same repository; self-
parent and cycles are rejected. A stale boundary version or a kind conflict is
`Rejected` with the current boundary version, not `Unavailable`.

Verification uses `kind="verification"` with a `run` carrying the command,
scope, outcome, observed time, observer, and the evidence it actually tested. A
run applies to the surfaces **within** its declared scope (a run scope path
covers a surface path when it is equal or an ancestor) and is not widened by a
broader question. A run requires `observations` or `evidence`: `run.observations`
takes the `obs:` ids that `ask` returned for the request context; to cite a
source instead, put it in `run.evidence` with the same `context_id` and Span
admits it. Sending neither is rejected; sending either is accepted. An id that
was never admitted is `Rejected` with `cause_kind=observation_not_admitted`, not
a transport error.

Support wires preserve source, admitted-source, authority, premise,
discovery-boundary, and admitted-discovery support. A discovery boundary is the
common path: the agent declares the scope it inspected and Span observes
membership internally.

Results: `UnderstandingRecorded`, `VerificationRecorded`, `SurfaceDeclared`,
`Rejected`, or `Unavailable`. A rejection names the offending identity, the
exact server cause, the required action, and the structured current version or
current boundary version when one exists; it is a result, not a transport error.
An accepted write is never reported as a rejection because present support
could not be evaluated; that outcome is `SupportUnavailable`.

## `reconsider`

```json
{"repository_id": "repo-1", "changed_paths": ["src/a.py"]}
```

```json
{
  "repository_id": "repo-1",
  "challenge": {
    "request_id": "ch-1",
    "understanding_id": "u:...",
    "target_version": 1,
    "target_conclusions": [
      {"understanding_id": "u:...", "conclusion_id": "c-1", "revision": 1}
    ],
    "reason": "The cited source does not support this statement.",
    "evidence": []
  }
}
```

This is an after-edit operation. The service derives the challenge context from
the target version and cited evidence; the caller does not supply a context id.
Results: `Changed`, `Challenged`, `Rejected`, or `Unavailable`.

`Changed` names every surface to re-examine, the reasons it was considered
(`containment`, `direct`, `indirect`), per-conclusion support state, and a
context for re-establishment. `surfaces` is the complete containment set: a
surface with no `conclusions` is containment-only, not a finding. Act only on
conclusions whose support state is `REASSESSMENT_REQUIRED` or `UNVERIFIABLE`; a
`CURRENT` conclusion in the set needs no work. Inclusion is not a verdict.
Discovery dependents are part of the direct set. The order is deterministic;
do not re-sort it. `Challenged` carries the challenge and its derived context;
settle it through `record`.

For example, a `Changed` result may list `src/a.py` with one `CURRENT`
conclusion and `billing` with no `conclusions`. Neither is a finding by itself:
act only on conclusions whose `support.state` is `REASSESSMENT_REQUIRED` or
`UNVERIFIABLE`, and keep the returned surface order.

## Egress and errors

Every result is canonical JSON in both MCP text and structured content.
Failures are typed `ToolError` envelopes: `unknown_tool`, `removed`, `ingress`,
`unavailable`, `conflict`, `validation`, `source_drift`, `rejected`, and
`transport`.

No operation accepts a response-size budget or a caller-supplied traversal
bound. Layer 4 owns the default per host and applies it inside the composition
boundary.

## Replay, identity, and retention

A recording decision is identified by `(repository_id, request_id)`. The caller
owns and preserves that identity before dispatch. A context is not part of the
replay key; it may be omitted when the recording cites locators and ranges, in
which case the operation issues one internally. Retrying the same identity and
content returns the committed receipt. Retrying the same identity with different
content is a `conflict`. Replay is resolved before new-write dependency checks,
so a retained receipt recovers even after its context was reaped.

Contexts expire on the configured lifetime. Receipts remain replayable for their
configured retention. Operational reaping removes expired contexts and receipts
only; accepted understanding, challenges, verification runs, and retained
receipts survive.

## Repository discovery

The repository ID is the registered name of a repository root — the basename
recorded by the installer — never a filesystem path. `span-install --verify-only`
prints it with store readiness. `tools/list` does not enumerate IDs; an unknown
ID fails closed with the registered names.

## Readiness

There is no status tool. Readiness is reported by the installer verification,
per-response availability, typed errors, and optional bounded hook notices.
`READY` means the store and provider are operationally available. It never means
the repository is semantically understood or complete.
