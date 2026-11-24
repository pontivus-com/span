---
name: span-router
description: Orient before reading source, retain a conclusion after investigating, and re-align understanding after a code change. Use when work touches unfamiliar code, a cross-boundary effect, saved meaning, authority, or verification and you need the right lifecycle moment.
---

# Span — route by moment

Complete the applicable lifecycle before task completion; report named operational
blockers explicitly. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#required-agent-completion).


Span serves ordinary Answer content only from current curated shared knowledge.
It separately retains captured understanding and exact source evidence for
review and investigation. It owns validation, identity,
freshness, persistence, and deterministic lifecycle projection. You own
interpretation and every edit; a reviewer/curator owns the decision to accept an
exact stable revision for shared reuse. Span never edits the target, runs
application tests, selects a model, or decides a semantic claim.

## Start here

Before ordinary governed work, resolve Functional Pyramid participation.
ACTIVE + VALID proceeds normally. ACTIVE + DEGRADED routes to governance
repair. UNCONFIGURED routes to the `span-functional-pyramid` skill when
governed use is intended; an intentionally non-governed repository is
explicitly EXCLUDED.

| About to… | Do instead |
| --- | --- |
| Native `Read`/`Grep` to understand source | `ask` |
| Shell read/search (`cat`, `rg`, `grep`, etc.) to understand source | `ask` |
| Hit an ambiguous path or want a specific granularity | `ask` with the exact `surface` |
| Edit a surface | `ask` first; `reconsider` after the edit |
| Finish an investigation | `record` the supported meaning as capture |
| Review captured knowledge for shared reuse | `ask` with PendingCurationSelector, then `record` curation for a stable exact revision |
| Declare or change a service/domain boundary | `record(kind="surface")` |
| Initialize/revise/deactivate/exclude Functional Pyramid participation | Use the `span-functional-pyramid` skill; it stays inside `ask` / `record` / `reconsider` |
| Dispute a recorded conclusion | `reconsider` with a challenge |

For ACTIVE Functional Pyramid repositories, ordinary `ask` also returns the
governing projection for the same semantic scope. Use the
`span-functional-pyramid` skill for participation lifecycle work; do not
reconstruct that lifecycle here.

Before editing, use `ask` for shared reusable understanding. Ordinary Answer
content is both CURRENT and CURATED; CURRENT captured-only meaning remains
explicit pending knowledge rather than shared reuse. A gap is not a failure. It
names status, what is missing, recovery, and source pointers without
automatically dumping source bytes. Select the evidence you actually need, then
record the conclusion you establish. Treat returned context references as opaque
handles and never inspect internal context state.

## The three moments

- **Before reading:** `ask` the exact surface with no question or request
  identity and read its current document view. Use `surface={kind, locator}`
  when a path matches more than one granularity. Use the exact recorded-question
  selector only when you already know that recorded question; it is exact,
  surface-scoped lookup rather than semantic matching. `Answer` carries current
  conclusions, support, evidence references, status, and applicable verification
  runs. `Gap` carries explicit absence/staleness information and source pointers.
- **After establishing:** `record` one `kind`. Use `kind="understanding"` to
  capture supported semantic meaning, `kind="verification"` to record a
  test/run, and `kind="surface"` to declare a service/domain boundary. A
  semantic create/change is CAPTURED, not self-publication. A create is flat —
  one `conclusion` with dependency evidence from `locator`,
  `observation_id`, or non-empty `support`; a locator may accompany support
  solely as carried semantic scope while observation remains exclusive. Scope
  is supplied or derived independently. A reviewer discovers CURRENT captures
  with PendingCurationSelector, follows `next_after` while the bounded result
  is truncated, repairs semantic defects through the ordinary lifecycle when
  needed, and uses the same `record` tool to curate only a stable exact
  revision. `actions` is for updates and `action` only for a
  surface declaration or Functional Pyramid lifecycle write.
- **After editing:** `reconsider` the paths you just changed. It returns every
  surface to re-examine, why it was considered, per-conclusion support state,
  and the context for re-establishing what actually changed. A surface with no
  `conclusions` is containment-only; re-establish returned conclusions whose state is
  `REASSESSMENT_REQUIRED` or `UNVERIFIABLE`, and keep the returned order.

## Boundaries

- Use outside tools to edit and test.
- Hooks deliver reminders; the agent performs the required lifecycle even
  when a reminder is absent. Hooks never record conclusions, curate knowledge,
  or make stale understanding current.
- Engineering-task completion may leave a captured revision pending separate
  review; pending curation is visible work, not a failed semantic record.
- Keep `CURRENT`, `REASSESSMENT_REQUIRED`, `UNVERIFIABLE`, the `Gap` reasons,
  and the challenge states `OPEN`/`UNRESOLVED`/`RESOLVED` verbatim.
- A `CURRENT` conclusion in a reconsideration result was considered; it is not
  automatically stale.

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md), [lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md).
