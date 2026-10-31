# First investigation and fresh-session reuse

This runbook establishes useful understanding for a chosen engineering task.
Choose the repository, exact scope, and question before investigating. The
scope may span implementation, tests, configuration, and governing documents.
A source inventory is evidence to examine; it is not a campaign to document
one semantic unit per file.

## Prepare

Install and connect Span using the [installation guide](install.md). Keep its
data directory outside the target repository. Check the installed version,
root binding, store, and provider with `span-install --verify-only`.

If no store exists, use `initialize_repository` once in a dedicated setup
session. Supply only declared authority seeds and bindings; finding a document
does not make it governing. Preserve the returned canonical repository ID.
An older store requires the explicit offline transition, not ordinary setup.
Operational readiness creates no understanding.

## Investigate the chosen scope

Ask `understand_question` with a new caller request identity, the engineering
question, and its exact scope. Examine any saved candidates before starting
new work. An investigation gap is permission to investigate within the task,
not proof that the whole repository lacks understanding.

Follow returned cursors unchanged with the same request identity and
arguments. Truncation leaves unexamined work explicit; a first page does not
establish complete membership or absence. Retrieve referenced context detail
when the byte budget omitted source bodies.

Read material implementation, consumers, tests, and governing sources using
the agent's normal tools. Admit exact sources or ranges through a bounded
`evidence_start` batch or `evidence_extend`. CSS and configuration remain
addressable as exact source even when a parser supplies no symbols.

## Save a useful result

Record coherent conclusions with admitted support and a short account of how
the evidence led to them. Keep unresolved questions and their basis as gaps.
Choose the existing understanding when updating an explanation; do not create
an unrelated replacement merely to avoid its history or challenges.

Use the live tool schemas and the [recording guide](interpretation.md). Preserve
`repository_id`, `context_id`, `submission_id`, and the exact content before
dispatch. Inspect the receipt and post-commit qualification, then retrieve
the saved version. Acceptance proves storage and validation, not semantic truth.

## Check a fresh session

Start another agent session and ask a differently worded question over the
same material scope, without supplying the saved ID. Inspect discovery,
retrieve the applicable snapshot, and distinguish supported reuse from new
source investigation. If no candidate is found, report that bounded outcome
and continue explicit discovery; do not invent semantic equivalence.

## Maintain it

After a relevant edit, `reassess` the recorded understanding, investigate the
reported dependency changes, and record a confirm/correct/replace/withdraw
update against the expected version. Preserve unresolved disputes through
explicit challenge dispositions. Record verification independently after
external execution, using the observations actually tested.

Close the task with what was recorded and retrieved, what remains uncertain,
what was tested externally, and any omitted scope. There is no repository
coverage score or campaign-completion claim in this procedure. See
[lifecycle](lifecycle.md) and [scope](scope.md).
