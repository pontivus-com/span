# First investigation and fresh-session reuse

This runbook establishes useful understanding for a chosen engineering task.
Choose the repository, exact scope, and question before investigating. The
scope may span implementation, tests, configuration, and governing documents.
A source inventory is evidence to examine; it is not a campaign to document one
semantic unit per file.

## Prepare

Install and connect Span using the [installation guide](install.md). Keep its
data directory outside the target repository. Check the installed version, root
binding, store, and provider with `span-install --verify-only`.

Provisioning is owned by the installer. Supply only declared authority seeds
and bindings; finding a document does not make it governing. Preserve the
returned canonical repository ID. An older store requires the explicit offline
transition, not ordinary setup. Operational readiness creates no understanding.

## Investigate the chosen scope

Ask with a new caller request identity, the engineering question, and either an
exact `surface={kind, locator}` or a reference. An `Answer` is usable current
content; a `Gap` is permission to investigate within the task, not proof that
the whole repository lacks understanding.

Truncation leaves unexamined work explicit; a partial answer does not establish
complete membership or absence. If a gap carries a continuation, follow it
until its evidence is complete.

Read material implementation, consumers, tests, and governing sources using the
agent's normal tools. CSS and configuration remain addressable as exact source
even when a parser supplies no symbols.

## Save a useful result

Record coherent conclusions with the evidence you hold and a short account of
how it led to them. Use `record(kind="understanding")` with `conclusion` plus
`locator` or `observation_id` for a first version and an explicit update action
for an existing one. Keep unresolved questions and their basis as gaps.

Use the live tool schemas and the [recording guide](interpretation.md). Preserve
`repository_id`, `request_id`, and the exact content before dispatch. Inspect the
receipt and post-commit qualification, then ask for the saved version.
Acceptance proves storage and validation, not semantic truth.

## Check a fresh session

Start another agent session and ask the same recorded question about the same
surface, without supplying the saved ID. Inspect the answer and retrieve an
exact snapshot if needed; distinguish supported reuse from new source
investigation. If no current conclusion is returned, report the gap and continue
explicit investigation; do not invent semantic equivalence.

## Maintain it

After a relevant edit, call `reconsider` with the changed paths. Investigate the
reported dependency changes, then record a confirm/correct/replace/withdraw
update against the expected version. Preserve unresolved disputes through
explicit challenge dispositions in `record`. Record verification independently
after external execution, using the evidence actually tested.

Close the task with what was recorded and retrieved, what remains uncertain,
what was tested externally, and any omitted scope. There is no repository
coverage score or campaign-completion claim in this procedure. See
[lifecycle](lifecycle.md) and [scope](scope.md).
