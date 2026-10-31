# MCP reference

Span runs over stdio:

```bash
span-mcp --data-dir DIR [--repo /path ...]
```

`--repo` registers repository identity for discovery. It opens no store and
performs no structural build; context opens lazily on the first
repository-scoped call. Setup remains explicit.

## Tools

Exactly nineteen tools ship in 0.9.0.

| Family | Tools |
| --- | --- |
| Setup | `initialize_repository` |
| Understand | `start_context`, `understand_question`, `understand_retrieve`, `evidence_start`, `evidence_extend` |
| Qualify | `reassess`, `verification_support` |
| Record | `record_create`, `record_add`, `record_confirm`, `record_correct`, `record_replace`, `record_withdraw`, `record_challenge`, `record_update`, `record_verification` |
| Navigate | `locate`, `neighbors` |

The retired names `explain`, `trace`, `impact`, `authority`, `status`,
`refresh`, `initialize_target`, and `submit_interpretation` are not
registered. Calling one returns a typed `removed` error with its replacement;
it performs no work.

Every repository-scoped request carries its canonical `repository_id`.
`initialize_repository` instead carries a plain `repository_locator` and
returns the canonical ID. Paths are never accepted as IDs.

## Ingress

Each tool takes its canonical request as compact wire JSON. Generated schemas
carry `additionalProperties: false`, required fields, enum values, and tagged
union branches. Unknown tools, unknown fields or enums, missing required
fields, and unknown `$type` values fail closed with an `ingress` error that
reports every shape fault found in one response.

`bounds` may be omitted for service defaults. A supplied bound is validated,
never widened.

`understand_retrieve` is a closed selector and requires a top-level `$type`:

- `UnderstandingSnapshotSelector` — `repository_id`, `understanding_id`,
  optional `version`; omitted version means current.
- `ContextRetrievalSelector` — `repository_id`, `context_id`.
- `ReceiptRetrievalSelector` — `repository_id`, `context_id`,
  `submission_id`.

Record tools use the reference-only wire in
`span.core.schema.record_wire`. They cite admitted observation or authority
references; they do not resend source bodies or invent fingerprints.

## Egress

Every result is canonical JSON in both MCP text and structured content.
Failures are typed `ToolError` envelopes: `unknown_tool`, `removed`,
`ingress`, `unavailable`, `conflict`, `validation`, `source_drift`,
`stale_continuation`, `rejected`, and `transport`.

`understand_question` returns one of:

- `UnderstandingCandidateAnswer` — bounded candidate identities and exact
  snapshots, each with live support; omitted detail is represented by a
  `UnderstandingCandidateReference` or `UnderstandingSnapshotReference`.
- `InvestigationNeeded` — a recovered context, admitted evidence, per-item
  outcomes, and the material gap. Truncated inventory remains explicit.
- `DiscoveryLimit` — no usable candidate or scope; no repository-wide absence
  is claimed.
- `ResponseBudgetExceeded` — the requested `max_evidence_bytes` cannot hold
  the minimum response; retry with a larger budget or narrower scope.

`understand_retrieve` returns `RetrievedUnderstanding` (snapshot, conclusion
bodies, live support, challenges), `RetrievedContext` (context with admitted
source and discovery observations), or `RetrievedReceipt` (retained receipt
plus the context when it still exists).

Record tools return `UnderstandingRecorded`, `VerificationRecorded`, or
`ChallengeRecorded`: the atomic receipt plus a post-commit qualification.
An accepted write is never reported as a rejection because present support
could not be evaluated; that outcome is `SupportUnavailable`.

## Replay, identity, and retention

A recording submission is identified by
`(repository_id, context_id, submission_id)`. The caller owns and preserves
that identity before dispatch. Retrying the same identity and content returns
the committed receipt. Retrying the same identity with different content is a
`conflict`. Matching replay is resolved before new-write dependency checks, so
a retained receipt recovers even after its context was reaped.

Contexts expire on the configured lifetime. Receipts remain replayable for
their configured retention. Operational reaping removes expired contexts and
expired receipts only; accepted understanding, challenges, verification runs,
and retained receipts survive.

## Cursors

Pagination cursors are opaque. Pass the returned value to the same operation
with the same arguments and `request_id`.

- `dsp:<n>` — discovery cursor. Follow it with `understand_question`.
- `pg:<n>` — inventory cursor. Follow it with `understand_question`; it
  resumes the evidence inventory for the same investigation.
- Structural `locate`/`neighbors` cursors are versioned and belong to those
  tools.

Pagination position is not part of the investigation binding. Changing the
question or scope under an existing `request_id` is a binding conflict;
advancing a cursor is not.

## Repository discovery

`tools/list` appends the sorted registered canonical repository IDs to
repository-scoped descriptions. `initialize_repository` also returns the ID.
Unknown IDs fail closed with the registered list.

## Administrative readiness

There is no `status` tool. Readiness is reported by:

- `initialize_repository` for explicit setup;
- `span-install --verify-only` for observational installation checks;
- transition `inspect`/`verify` for stores;
- per-response availability and typed errors;
- optional bounded hook notices.

`READY` means the store and provider are operationally available. It never
means the repository is semantically understood or complete.
