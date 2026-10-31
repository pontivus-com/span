# Agent lifecycle

```
SETUP (dedicated session)
  initialize_repository
    → binds root, declared authority seeds/bindings, creates schema 10

ORDINARY SESSION
  understand_question
    → saved candidates with live support, or an investigation gap
  evidence_start / evidence_extend
    → admit exact sources into a server-issued context
  record_*
    → atomic understanding update plus a receipt and support qualification
  reassess / verification_support
    → qualify exactly what was recorded against present evidence
  locate / neighbors
    → structural navigation only
```

## Contexts

`start_context` issues or recovers one server-owned context for a caller
`request_id`. `understand_question` also issues a context when it returns an
investigation gap or candidate answer. A context binds repository, question,
scope, origin, and expiry. Following a pagination cursor keeps the same
binding; changing the question or scope under the same `request_id` is a
conflict.

Contexts expire. Expiry removes operational membership only. Accepted
understanding, challenges, verification runs, and retained receipts survive.

## Recording

Every record tool is atomic. It cites admitted observation or authority
references; it does not resend source bodies. The result is the committed
receipt plus a post-commit support qualification. A validation, identity,
conflict, or source-drift failure changes nothing and names the offending
identity.

- `record_create` creates version 1.
- `record_add`, `record_confirm`, `record_correct`, `record_replace`, and
  `record_withdraw` update an exact expected version.
- `record_challenge` creates an explicit dispute.
- `record_update` applies conclusion actions and named challenge dispositions
  together.
- `record_verification` records an independent run against the observations
  actually tested.

A matching replay returns the retained receipt before new-write dependency
checks. The same identity with different content is a conflict.

## Currentness

Support is evaluated on retrieval, recording, reassessment, and verification.
States are `CURRENT`, `REASSESSMENT_REQUIRED`, and `UNVERIFIABLE`. A missing
authority or observation stays explicit; it is never promoted to current.

Challenges settle only through an explicit disposition. A new version, a
passing test, or a matching fingerprint does not settle a dispute.

## Hooks

Hooks are optional event-local notices. They never record, reassess,
interpret, or rebuild. A missed or disabled hook cannot make stale
understanding current; correctness is evaluated by the lifecycle operations.

## Store transition

The runtime never migrates at open. Schema 7/8/9 stores use the offline
inspect/apply/verify/rollback commands in [install](install.md). Only the
repository binding and declared seeds are carried forward; legacy semantic
content remains historical export and must be re-recorded.
