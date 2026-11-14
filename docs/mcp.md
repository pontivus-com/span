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

The host supplies structural navigation and the installer owns setup. Neither is
part of the default surface.

`record` carries `kind` (`understanding`, `verification`, or `surface`). An
understanding create is flat — one `conclusion` plus exactly one evidence mode
(`locator`, `observation_id`, or non-empty `support`); scope is supplied or
derived independently. `actions` is for updates and `action` for a surface
declaration. Those are semantic fields, not separate tools. Only the current
three names are registered. Any other operation name follows the ordinary typed
`unknown_tool` error path and performs no work.

Every repository-scoped request carries its canonical `repository_id`. Paths are
never accepted as IDs.

## `ask`

Forms (exactly one):

```json
{"repository_id": "repo-1", "surface": {"kind": "FILE", "locator": "src/a.py"}}
{"repository_id": "repo-1", "reference": "src/a.py"}
{"selector": {"$type": "RecordedQuestionSelector", "repository_id": "repo-1", "surface": {"kind": "FILE", "locator": "src/a.py"}, "question": "What does it do?"}}
{"repository_id": "repo-1", "request_id": "evidence-1", "surface": {"kind": "FILE", "locator": "src/a.py"}, "evidence": [{"locator": "src/a.py", "ranges": []}]}
{"selector": {"$type": "CurrentUnderstandingSelector", "repository_id": "repo-1", "understanding_id": "u:..."}}
{"selector": {"$type": "UnderstandingSnapshotSelector", "repository_id": "repo-1", "understanding_id": "u:...", "version": 1}}
{"selector": {"$type": "ReceiptRetrievalSelector", "repository_id": "repo-1", "request_id": "write-1"}}
{"continuation": "span1_..."}
```

- Pure `surface`/`reference` obtain is the normal reuse path. It takes no
  `question`, `request_id`, evidence, or context and returns the current surface
  document view grouped by recorded question.
- `surface` is an exact `{kind, locator}` identity. It resolves by identity,
  never containment. `kind` is `FILE`, `SYMBOL`, `SERVICE`, or `DOMAIN`.
- `reference` must resolve to exactly one surface; otherwise the result is
  `AmbiguousSurface` with exact candidate identities.
- `RecordedQuestionSelector` is targeted reuse only when the exact recorded
  question is already known. Matching is exact within the supplied surface;
  Span performs no paraphrase, similarity, or semantic question matching. A
  non-match is `Gap/unassessed`.
- Explicit evidence admission reuses the surface/reference form with non-empty
  `evidence` and a caller-owned `request_id`. It returns the same Answer/Gap
  classification plus one `EvidenceAdmissionView` with a bound
  `InvestigationContextRef`, admission outcomes, exact deliveries, omissions,
  and a continuation when selected bytes do not fit.
- `CurrentUnderstandingSelector` reads one understanding's current membership.
  Snapshot and receipt selectors are historical/audit retrieval and are never
  merged into current Answer content.
- Selectors and `continuation` carry their own repository namespace. Do not add
  a top-level `repository_id` override to those forms.
- `continuation` returns the next `EvidencePage` for bytes selected by explicit
  evidence admission.

Pure obtain creates no context. A context reference is returned only by explicit
evidence admission or by `reconsider`; treat it as an opaque
`InvestigationContextRef` and copy it only into a declared `context` field.

Results: `Answer`, `Gap`, `AmbiguousSurface`, `RetrievedUnderstanding`,
`RetrievedReceipt`, `EvidencePage`, `Rejected`, or `Unavailable`.

- `Answer` carries current `ConclusionView` content, surface status, recorded
  gaps, applicable `VerificationView` values and explicit truncation state.
  Surface document view content is grouped by recorded question. `admission`
  is absent unless explicit evidence admission ran.
- `Gap` carries one reason (`invalidated`, `unverifiable`, or `unassessed`),
  historical non-current content where applicable, missing items, recovery, and
  concrete `source_pointers`. It does not imply source bytes were admitted.
  When explicit evidence admission ran, the same optional `admission` field is
  present. A non-matching exact recorded-question selector is `unassessed`.
- `AmbiguousSurface` carries exact candidates. Copy one into `surface`; do not
  re-resolve the path.
- `EvidencePage` carries exact `EvidenceDelivery` fragments and an optional
  further continuation. It is evidence, not current conclusion content.
- `Rejected` is caller-correctable invalid selection/binding/reference state.
  `Unavailable` is genuine operational inability or a response budget that
  cannot carry the minimum result.

### Continuation

A continuation is opaque and stateless. It binds repository, investigation
context, original request identity/digest, and the next evidence position. The
same token against the same live context returns the same page across restart.
A page advances by at least one exact delivery or line fragment; oversized
content splits only at line boundaries and preserves original source positions.

Malformed, wrong-binding, missing, non-live, expired, exhausted, or
out-of-position continuation references return typed `Rejected` with recovery
that starts a new explicit evidence admission. Genuine store/provider failure is
`Unavailable`. A line or minimum response envelope that cannot fit the response
budget is also `Unavailable`; that is not a continuation-reference rejection.

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

A create carries one conclusion and exactly one evidence mode. `locator` cites
source evidence and may also supply semantic scope; `observation_id` returned by explicit evidence admission may replace it;
non-empty `support` is the complete typed dependency set the agent already
holds. A locator may accompany explicit support as the carried code scope, but
an observation id may not. Scope is supplied or derived independently through
`scope_paths`, the bound context, or a single carried path. `surface` is
optional and derived from the carried scope. `assertion_nature` defaults to
`DESCRIPTIVE`. A create takes no caller-created conclusion identity, no
`action`, and no `actions`: `action` belongs to `kind="surface"` and `actions`
to updates. Sending any of them is an ingress error.

Updates use `actions` with `add`, `confirm`, `correct`, `replace`, or `withdraw`,
plus `understanding_id` and `expected_version`. Multiple keys apply atomically.
Actions are compact semantic deltas, not full conclusion snapshots. `add` takes
no identity; `confirm`, `correct`, `replace`, and `withdraw` name the
`conclusion_id` returned by Span for an existing lineage. Each action names
exactly one evidence mode — `locator`, `observation_id`, or non-empty
`support`:

```json
{"add":     [{"conclusion": "B performs Y.", "locator": "src/b.py"}]}
{"confirm": [{"conclusion_id": "<id returned by Span>", "locator": "src/a.py"}]}
{"correct": [{"conclusion_id": "<id returned by Span>", "conclusion": "A now performs Z.", "locator": "src/a.py"}]}
{"replace": [{"conclusion_id": "<id returned by Span>", "conclusion": "The replacement behaviour is Z.", "reason": "The prior implementation was superseded.", "locator": "src/a.py"}]}
{"withdraw":[{"conclusion_id": "<id returned by Span>", "reason": "The implementation no longer has this behaviour."}]}
```

`add` and `correct` take `conclusion`; `replace` takes `conclusion` and
`reason`; `confirm` preserves the current statement, assertion nature, and
scope; `withdraw` may supply one evidence mode or none. Span derives the new
lineage identity on `create`, `add`, and `replace`, the old revision identity,
unchanged content metadata, and the mechanical basis. Supply
`assertion_nature` or `scope_paths` only when overriding the current value on
`add`, `correct`, or `replace`. Do not send `statement`, `basis_*`, `old_*`,
`new_conclusion_id`, or a nested `new_conclusion`; those fields are not part of
the public grammar. `challenge_dispositions` settles a challenge raised by
`reconsider`.

A create may supply the canonical `context` reference returned by explicit evidence admission or `reconsider`.
The context's bound target/scope are used where applicable; do not also send a conflicting explicit target — that conflict is rejected. Without a context, a create requires
`question` and issues its own evidence-only context.

Semantic scope describes what the conclusion is about; support identifies what
established it. Multiple support files do not create multiple owning surfaces.
Declare SERVICE/DOMAIN only when the conclusion describes that declared boundary.
Its semantic scope must fit that boundary. Support locators do not create
independent retained conclusions; author per-file conclusions when needed.

A supplied context has fixed scope. New source or discovery evidence can be
admitted during record inside that scope; it need not already be admitted.
Empty evidence scope means repository-wide. Discovery must fit completely:
a broader ancestor or repository-wide discovery cannot fit a restricted context.

When investigation expands, omit `context` and supply explicit semantic/run
scope and direct evidence. Span derives a new operational context. Repository-wide
discovery makes that context repository-wide while the semantic scope stays
narrow. Admitted evidence references and observation IDs remain context-bound; supply that context or use direct evidence.

```json
{
  "repository_id": "repo-1",
  "request_id": "plan-status-1",
  "kind": "understanding",
  "question": "Is this plan implemented?",
  "scope_paths": ["docs/implementation-plan.md"],
  "conclusion": "The implementation described by the plan is complete.",
  "support": [
    {"$type": "SourceSupportWire", "locator": "src/a.py", "ranges": []},
    {"$type": "SourceSupportWire", "locator": "tests/a.py", "ranges": []}
  ]
}
```

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
broader question. A run requires at least one observation or evidence item; both may coexist.
Use context + run.observations only for observations admitted to that context.
Use context + run.evidence for new direct evidence inside its fixed scope.
For evidence beyond it, omit context and supply run.scope_paths/run.evidence.
Do not substitute scenario text for structural evidence.

```json
{
  "repository_id": "repo-1",
  "request_id": "verify-ui-1",
  "kind": "verification",
  "run": {
    "repository_id": "repo-1",
    "scope_description": "UI form suite",
    "scope_paths": ["ui/"],
    "evidence": [{"locator": "ui/tests/form.test.ts", "ranges": []}],
    "command": "pnpm exec vitest run tests/form.test.ts --pool=forks --maxWorkers=1 --no-file-parallelism",
    "scenario": "UI form suite",
    "outcome": "PASS",
    "observed_at": "2026-11-07T00:00:00Z",
    "observer": "agent"
  }
}
```

Support wires preserve source, admitted-source, authority, premise,
discovery-boundary, and admitted-discovery support. A discovery boundary is the
common path: the agent declares the scope it inspected and Span observes
membership internally.

Results: `UnderstandingRecorded`, `VerificationRecorded`, `SurfaceDeclared`,
`Rejected`, or `Unavailable`. A rejection names the offending identity, the
stable server-owned public cause text, the required action, and the structured current version or
current boundary version when one exists; it is a result, not a transport error.
An accepted write is never reported as a rejection because present support
could not be evaluated; that outcome is `SupportUnavailable`. Ordinary acceptance
carries a receipt selector rather than nesting the full receipt. Accepted
understanding also carries live status or `SurfaceStatusUnavailable`; exact receipt
detail remains retrievable with `ReceiptRetrievalSelector`.

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
      {"understanding_id": "u:...", "conclusion_id": "<id returned by Span>", "revision": 1}
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
(`containment`, `direct`, `indirect`), per-conclusion support state, the
understanding's current `expected_version`, and a context for re-establishment.
That is everything the subsequent compact `record` needs; no intervening `ask`
is required. `surfaces` is the complete containment set: a
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
per-response availability, typed errors, and bounded lifecycle notices.
`READY` means the store and provider are operationally available. It never means
the repository is semantically understood or complete.
