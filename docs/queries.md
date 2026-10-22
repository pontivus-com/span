# Queries, answers, boundedness (plan §4.10, §5.1, §11.4–11.10)

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
