# First investigation and fresh-session reuse

Agent work follows [the required Span lifecycle](lifecycle-contract.md#required-agent-completion).

This runbook establishes useful understanding for a chosen engineering task.
Choose the repository, exact scope, and question before investigating. The
scope may span implementation, tests, configuration, and governing documents.
A source inventory identifies evidence for that investigation.

## Prepare

Install and connect Span using the [installation guide](install.md). Keep its
data directory outside the target repository. Check the installed version, root
binding, store, and provider with `span-install --verify-only`.

Provisioning is owned by the installer. Supply only declared authority seeds
and bindings; finding a document does not make it governing. Preserve the
returned canonical repository ID. An older store requires the explicit offline
transition, not ordinary setup. Operational readiness creates no understanding.

## Investigate the chosen scope

Start with a pure surface/reference `ask`: no question, request identity, or
context. An `Answer` is the current surface document view grouped by recorded
question; a `Gap` names what is missing plus concrete source pointers and does
not prove the whole repository lacks understanding.

When source bytes are needed, make a separate explicit evidence-admission
`ask` with a new caller request identity and the exact locators/ranges needed.
Only that admission returns a context and may return a continuation. Follow its
continuation until the selected evidence is complete. Use
`RecordedQuestionSelector` only when the exact recorded question is already
known.

Read material implementation, consumers, tests, and governing sources using the
agent's normal tools. CSS and configuration remain addressable as exact source
even when a parser supplies no symbols.

## Retain established understanding

Record coherent conclusions with the evidence you hold and a short account of
how it led to them. Use `record(kind="understanding")` with `conclusion` and
exactly one evidence mode — `locator`, `observation_id`, or non-empty `support`
— for a first version, and an explicit update action for an existing one. Scope
is supplied or derived independently. Keep unresolved questions and their basis
as gaps.

Use the live tool schemas and the [recording guide](interpretation.md). Preserve
`repository_id`, `request_id`, and exact content before dispatch. Inspect the
compact acceptance and its post-commit qualification; use its receipt selector
or snapshot selector only when exact audit detail is needed. Acceptance proves
storage and validation, not semantic truth.

## Check a fresh session

Start another agent session and ask the surface document view, without a saved
understanding ID or recorded question. Select the applicable current conclusion
from the grouped view and retrieve an exact snapshot only when needed. If no
current conclusion is returned, report the gap and continue explicit
investigation; do not invent semantic equivalence.

## Maintain it

After a relevant edit, call `reconsider` with the changed paths. Investigate the
reported dependency changes, then record a confirm/correct/replace/withdraw
update against the expected version. Preserve unresolved disputes through
explicit challenge dispositions in `record`. Record verification independently
after external execution, using the evidence actually tested.

Close the task with what was recorded and retrieved, what remains uncertain,
what was tested externally, and any omitted scope. Follow the completion boundary in the lifecycle contract. See
[lifecycle](lifecycle.md) and [scope](scope.md).
