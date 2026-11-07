---
name: span-router
description: Orient before reading source, retain a conclusion after investigating, and re-align understanding after a code change. Use when work touches unfamiliar code, a cross-boundary effect, saved meaning, authority, or verification and you need the right lifecycle moment.
---

# Span — route by moment

Span answers from recorded understanding and exact source evidence. It owns
validation, identity, freshness, and persistence. You own interpretation and
every edit. Span never edits the target, runs application tests, selects a
model, or decides a semantic claim.

## Start here

| About to… | Do instead |
| --- | --- |
| `Read` a file to understand it | `ask` |
| `Grep` for a concept | `ask` |
| Hit an ambiguous path or want a specific granularity | `ask` with the exact `surface` |
| Edit a covered surface | `ask` first; `reconsider` after the edit |
| Finish an investigation | `record` |
| Declare or change a service/domain boundary | `record(kind="surface")` |
| Dispute a recorded conclusion | `reconsider` with a challenge |

Before editing, use `ask` for current understanding. A gap is not a failure.
Read its evidence, then record the conclusion you established. If the gap omitted
evidence to fit the response, follow its continuation. On `no_match`, omit the
question and ask for the surface document view. Never fetch a context id.

## The three moments

- **Before reading:** `ask` one exact question about an exact surface for a
  targeted query. For reuse, omit the question and read the surface document
  view; select the current conclusion you need. Use `surface={kind, locator}`
  when a path matches more than one granularity. A paraphrased question returns
  `no_match`; its recovery points to the document view. `Answer` carries
  current conclusions, support, evidence, and applicable verification runs.
  `Gap` carries the prior statement as historical content and the evidence you
  need to record.
- **After establishing:** `record` one `kind`. Use `kind="understanding"` to
  create or update, `kind="verification"` to record a test/run, and
  `kind="surface"` to declare a service/domain boundary. A create is flat —
  one `conclusion` plus exactly one evidence mode: `locator`, `observation_id`,
  or non-empty `support`; scope is supplied or derived independently. `actions`
  is for updates and `action` only for a surface declaration.
- **After editing:** `reconsider` the paths you just changed. It returns every
  surface to re-examine, why it was considered, per-conclusion support state,
  and the context for re-establishing what actually changed. A surface with no
  `conclusions` is containment-only; act only on conclusions whose state is
  `REASSESSMENT_REQUIRED` or `UNVERIFIABLE`, and keep the returned order.

## Boundaries

- Use outside tools to edit and test.
- Hooks are optional notices. They never record, re-check, or make stale
  understanding current.
- Keep `CURRENT`, `REASSESSMENT_REQUIRED`, `UNVERIFIABLE`, the `Gap` reasons,
  and the challenge states `OPEN`/`UNRESOLVED`/`RESOLVED` verbatim.
- A `CURRENT` conclusion in a reconsideration result was considered; it is not
  automatically stale.

Detail: [MCP reference](../../docs/mcp.md), [lifecycle](../../docs/lifecycle.md).
