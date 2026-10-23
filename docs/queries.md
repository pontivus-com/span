# Queries, answers, boundedness

Five intents, one envelope (`SemanticAnswer`, intent↔content strictly
paired): `explain` (identity/purpose/implementation/ownership),
`trace`/`context` (flow, boundaries, lifecycle paths; structural
routes stay possible routes), `impact` (pre-change brief joining
reach with ownership/authority/lifecycle/verification),
`authority`/`evidence` (governance with side-by-side conflicts),
`status` (freshness, verification currency, refresh scope; `HOOK_FAST`
returns a compact notice only).

## Self-containment (I-36)

Every reference resolves to an item carried in the same answer;
per-item freshness travels inline; status carries readiness. No
second lookup is ever required to interpret an answer.

## Bounds (operational, never semantic)

`ServiceBoundsPolicy`: default/maximum/hook-fast. Omitted bounds use
defaults; over-maximum bounds are rejected, never clamped. Truncation
follows retention priority (requested identities → qualifiers →
governing evidence → direct claims → structural context → expansion);
conflict pairs are atomic; `BoundInfo` states what was cut and whether
continuation exists.

## Pagination vs continuation (I-39)

`page_token` is an opaque token returned by the listing operation. Pass it
unchanged to the same operation with the same request arguments to obtain the
next page. A `PendingInterpretation` continuation is likewise opaque: pass it
unchanged to `submit_interpretation`. The two mechanisms are different; never
substitute one for another, and never decode or synthesize either value.

---

## Change impact

Before a material edit, an agent can use:

```text
impact
```

to evaluate a proposed change against already established understanding.

That can surface more than a structural blast radius.

A structural tool might answer:

```text
What calls this function?
```

Span can reuse established understanding to help answer questions such as:

```text
Which capability owns this behavior?

Which consumers rely on this contract?

Which governing source constrains this change?

Which lifecycle boundary does this cross?

Which established conclusions may need to be re-checked?
```

`impact` returns a change brief.

It is not approval to modify the repository.

---

## Trace

Use:

```text
trace
```

when the important question is not merely "what calls this?" but how an established semantic path works.

For example:

```text
request
  ↓
validation owner
  ↓
canonical carrier
  ↓
transformation
  ↓
consumer
  ↓
terminal state
```

A semantic trace can preserve responsibilities, boundaries, and lifecycle meaning around that path.

Structural adjacency remains evidence underneath it.

---

## Authority

Use:

```text
authority
```

when the question is:

> What actually governs this behavior, contract, responsibility, or decision?

Span can place relevant governing sources and competing evidence side by side while preserving:

- authority kind;
- declared status;
- applicability;
- precedence where explicitly established;
- conflicts;
- missing authority.

It does not reconstruct precedence that the repository never declared.

---
