# Using Span

Span is designed to fit into normal coding work: retrieve what is already
known, investigate only what is missing or stale, implement with your normal
tools, then re-check the semantic scope your change affected.

## First use

Once Span is connected:

1. Call the operation you need: `explain` for explanation, `trace` for execution path, `impact` for change risk, `authority` for governance, or `status` when coverage/freshness is the objective.
2. If current understanding already exists, Span can return it with its supporting state.
3. If the required understanding has not yet been established, Span returns a bounded interpretation task.
4. Your coding agent investigates that task with its normal tools and model.
5. The result is submitted with `submit_interpretation`.
6. Continue until the original question resolves or an explicit unresolved requirement remains.

The interaction can therefore be immediate:

```text
explain
   ↓
established current understanding
```

or require investigation:

```text
explain
   ↓
PendingInterpretation
   ↓
coding agent investigates
   ↓
submit_interpretation
   ↓
answer or next bounded task
```

Span does not invoke the model during this process.

The host coding agent performs the reasoning.

Submitting accepted interpretation persists reusable knowledge.

Reading alone does not manufacture new semantic state.


---


## What can be established

When an agent investigates a system area, Span can preserve conclusions about
things such as:

- what a subsystem or component is responsible for;
- which component owns a decision;
- how data moves from producer to consumer;
- where important boundaries exist;
- which contracts or decisions govern behavior;
- what lifecycle or failure paths exist;
- which downstream areas depend on something;
- what a proposed change may affect.

Those conclusions remain connected to the evidence and semantic premises that
supported them. If that support changes, Span marks the affected understanding
stale instead of continuing to serve it as current. The agent can then re-check
only that affected scope.

> **A change underneath established understanding cannot silently leave that
> understanding looking current.**


---


## Establish a subsystem once

For an explicit directory or other bounded target that you want agents to understand and reuse, call:

```text
initialize_target
```

with:

- the exact target scope; and
- the objective for understanding it.

Span then coordinates a bounded establishment campaign through the host agent.

The target is partitioned into material areas.

Each material area must end with an explicit disposition rather than disappearing because it was ambiguous, difficult, or unsupported.

Established understanding becomes available to later agents.

Unresolved work remains visible.

See [the onboarding runbook](onboarding-runbook.md) for the complete procedure.


---


## An example

Suppose an agent establishes:

```text
AuthenticationService owns session issuance.
```

Span records that conclusion together with the evidence used to establish it.

Later, a refactor changes one of those supporting sources.

Span does **not** claim:

```text
AuthenticationService no longer owns session issuance.
```

It does not know that merely because evidence changed.

Instead, the affected understanding may read back as:

```text
AuthenticationService owns session issuance

STALE

Supporting evidence changed:
  auth/session.py

Re-check this scope before relying on it.
```

That distinction is intentional.

**Stale means "needs another look."**

It does not mean "proven wrong."

Span tracks whether established understanding is still supported by the repository state it depends on. It does not pretend that evidence drift automatically determines semantic truth.


---


## Current and stale are explicit

Span separates **whether an interpretation has been established** from **whether its support is still current**.

Those are different questions.

An interpretation can have been well established previously and still become stale because its evidence changed.

### Freshness

| State | Meaning |
| --- | --- |
| `CURRENT` | The recorded understanding is still supported by the evidence and premises it depends on. |
| `STALE` | Relevant support changed after the understanding was established. Re-check it before treating it as current. |
| `UNVERIFIABLE` | Span cannot currently establish whether the required support remains valid. The gap stays visible. |

### Unresolved work

Span also preserves unresolved investigation instead of forcing an answer.

For example:

| State | Meaning |
| --- | --- |
| `OPEN` | A material unresolved requirement is known and recorded. |
| `PENDING` | Required investigation has not yet been completed. |

The deeper establishment model also preserves ambiguity, conflict, partial support, and unresolved conclusions where appropriate.

The important user-facing behavior is simple:

> **Span does not flatten uncertainty into a confident answer.**

See [the freshness model](freshness.md) and [authority and trust](authority-trust.md) for the complete contract.


---


## How freshness works

Before recorded understanding is presented as current, Span checks the evidence and semantic premises it depends on.

At a high level:

```text
recorded understanding
        ↓
load supporting evidence
        ↓
compare against current repository state
        ↓
check dependent semantic premises
        ↓
CURRENT / STALE / UNVERIFIABLE
```

Span checks fingerprints and coverage dependencies rather than trusting an old timestamp or a previously stored status.

Changed or retired premises can make dependent understanding stale.

If required support cannot be verified, Span reports that limitation rather than presenting the old interpretation as current.

Stored history is not the same thing as effective current state.


---


## Scoped re-checking

When understanding becomes stale, Span does not automatically rewrite it.

Instead:

```text
identify affected stale scope
        ↓
select current evidence for that scope
        ↓
coding agent re-investigates
        ↓
submit interpretation
        ↓
Span validates and reconciles the result
        ↓
fresh state becomes reusable
```

Current unaffected understanding stays untouched.

A failed or incomplete reassessment remains visibly stale, unverifiable, open, or pending as appropriate.

A `refresh` call alone does not prove that understanding has been corrected.

Reassessment does.


---


## Why this matters

Without Span, the safest coding agent often has to reconstruct the relevant system area from first principles.

That can mean repeatedly:

- searching for definitions;
- following imports and callers;
- opening tests;
- reconstructing producer-to-consumer paths;
- comparing implementation with contracts or ADRs;
- determining responsibility and ownership;
- resolving conflicting documentation;
- checking whether old explanations still apply.

With Span, previously established understanding can be reused while its supporting evidence remains current.

When something changes, the agent does not have to distrust everything.

It can focus its effort on the affected scope.

The intended result is:

- less repeated code archaeology;
- less time and context spent reconstructing known architecture;
- less accidental reliance on stale documentation;
- narrower investigations after changes;
- more continuity between coding agents and sessions.


---


## Typical development workflow

Span is designed to fit into normal coding work.

```text
ORIENT
retrieve what is already known
        ↓
PREPARE
check likely semantic impact
        ↓
INVESTIGATE
resolve only what is missing, unclear, or stale
        ↓
IMPLEMENT
edit with your normal coding tools
        ↓
VERIFY
run normal tests and review
check semantic currency
        ↓
CLOSE OUT
re-check affected understanding
        ↓
REUSE
the next agent starts from current established context
```

Tests and Span answer different questions.

**Tests check executable behavior.**

**Span checks whether the evidence supporting recorded understanding is still current.**

Passing tests do not automatically prove a semantic interpretation.

Likewise, semantic currency does not replace executable testing.

They participate in the same development cycle while preserving their distinct responsibilities.

See [the lifecycle documentation](lifecycle.md).


---
