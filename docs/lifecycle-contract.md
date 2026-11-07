# Span lifecycle contract — layer 2

**Status: binding.** This is the second foundational layer, beneath the
[goals](goals.md) (layer 0) and layer 1 ([foundations](foundations.md)). Layer 1
states the axioms about the agent and the principles of the system. This layer
turns them into functional requirements: the operations that exist, what the
agent sends and receives, and what is deliberately not the agent's job. The
[functional design](functional-design.md) (layer 3) and the implementation
(layer 4) must be derivable from this document.

Authority and derivation between layers are defined in the
[requirements pyramid model](requirements-pyramid.md).

## 1. Position in the pyramid

This document is layer 2. Layer 0 is [goals](goals.md), layer 1 is
[foundations](foundations.md), layer 3 is the
[functional design](functional-design.md), and layer 4 is the
[technical design](technical-design.md). The ownership of each layer, the
placement test for a new statement, the rule against restatement, and the
direction of derivation are defined in the [requirements pyramid model](requirements-pyramid.md).

## 2. Terminology

| Term | Meaning |
| --- | --- |
| **Surface** | Defined in [foundations](foundations.md) §1. A **declared surface** (`SERVICE`, `DOMAIN`) has an explicit name and boundary. A **path surface** (`FILE`, `SYMBOL`) is identified by its path or canonical locator and is created on first reference, with no separate declaration step. |
| **Request identity** | The caller's stable identifier for one request that writes or issues a context. A retry reuses it; a new intentional act uses a new one. It carries no Span state and is not a token. A pure change-scope `reconsider` is a read and carries none. |
| **Boundary** | The paths or symbols that a surface covers. Used for discovery, change mapping, and the `unexamined` count. |
| **Granularity** | The kind of surface being asked about. The same question at file scope and at service scope is a different question with a different answer. |
| **Understanding** | The retained, versioned unit: one question over one surface, with supported conclusions. |
| **Answer** | What `ask` returns when usable understanding exists for the surface. |
| **Conclusion** | One supported statement inside an understanding. |
| **Evidence** | Exact source content — locator, range, content identity. |
| **Support** | The typed dependency of a conclusion on evidence, a discovery boundary, an authority, or another conclusion. |
| **Surface status** | The distribution over a surface's own conclusions and its boundary: current, stale, unassessed, and unexamined, with descendant status reported separately. |
| **Gap** | The absence of usable understanding, with its cause and the means to resolve it. |
| **Challenge** | An explicit dispute against a conclusion revision. |
| **Verification** | An independent run recorded against the observations or evidence actually tested. |

An understanding may be unsupported. An **answer never is** — that asymmetry is
the point of the whole system.

## 3. Why exactly five operation families

| Decision | Source |
| --- | --- |
| The surface is obtain, retain, re-align, bind, navigate — and no more | F6 |
| Correctness cannot depend on the agent remembering a step | A4 |
| The agent supplies only what it already holds | F7 |
| A refusal must carry the way forward | A8 |
| Only valid content is an answer | F2, A7 |
| Scope is a surface and status is reported at its granularity | F9 |
| Understanding is retained, versioned, and reachable without the transcript | F3 |
| Reuse must beat maintaining documentation or acting on stale understanding | F8 |
| Surface-bound semantic content is the documentation, not a separate artifact | G6 |
| There are no per-intent operations | F5 |

*What does this do*, *what governs it*, *what depends on it*, *what breaks if I
change it*, and *is this still true* are **questions**, not operations. Span does
not classify them; the question ranks discovery, the surface fixes the scope,
and the agent judges applicability. Five intents never become five tools.

Audit needs no sixth operation. Every answer carries the surface status, because
a reader who cannot tell current from stale has not been answered (F9).

These five are **operation families**. The number of registered tools is a
layer-3 delivery decision constrained by host capability (see L8). It may exceed
five only by splitting one family's variants, and it may never add a family.

## 4. The five operation families

### 4.0 Answer boundary

State this before the operations, because everything else depends on it.

- Span answers from **retained understanding scoped to a surface**. It does not
  synthesise an answer from first principles.
- A first-contact question on an unassessed surface returns a **gap**, not a
  generated answer.
- When code changes, Span **marks containment and enumerates support loss, direct
  and indirect**; it never rewrites meaning. The answer is restored by the agent
  through `record`.
- Every answer reports the surface status. Status is never optional and never a
  single stamp.

### 4.1 `ask` — obtain

```text
ask(surface={kind, locator}, question?)
ask(reference, question?)       # convenience form
ask(selector)                   # exact snapshot or receipt
ask(continuation)               # omitted gap evidence
```

Exactly one form is supplied. `question` is optional for `surface` and
`reference`; every other form rejects it.

- `surface` is an exact `{kind, locator}` identity and resolves by identity,
  never containment. `kind` is `FILE`, `SYMBOL`, `SERVICE`, or `DOMAIN`.
- `reference` is the convenience form. A path or declared name that resolves to
  exactly one surface is accepted. If more than one granularity matches, the
  result is `AmbiguousSurface`; its `candidates` are exact identities. The agent
  copies one candidate into `surface`; it does not re-resolve the original path.
- `selector` is an exact `UnderstandingSnapshotSelector` or
  `ReceiptRetrievalSelector`. The result is historical: `RetrievedUnderstanding`
  or `RetrievedReceipt`, never merged into `Answer` and never counted current.
- `continuation` returns an `EvidencePage` for evidence omitted from a gap.

`surface` and `reference` are mutually exclusive. A `question` without either
is rejected. A `surface` or `reference` without a question is the surface
document view.

Response size is bounded by the server for the surface. Layer 4 owns that budget,
and the agent does not manage it (F7). Every surface/reference request carries a
request identity (see §4.2); a retry reuses it and recovers the same context.
Continuation and exact-reference forms carry their own binding.

**Continuation lifecycle.** A continuation is stateless. It binds the
repository, the investigation context, the original request identity and
content digest, and the next evidence position (unit index plus line offset).
It introduces no new table, TTL, or reaper: it is valid exactly while its
context is `LIVE`. The same token against the same live context returns the
same page. Restart works because the context and admitted evidence are
persisted. A token from another repository, a mismatched request binding, an
unknown context, or a context that is `EXPIRED` or `ABANDONED` returns typed
`Unavailable` with a recovery. `reap_expired` removes the context and evidence
together.

Every page advances by at least one evidence unit or one exact line range. If
one evidence unit exceeds the budget, the page carries the largest exact line
range that fits, with its content range and a continuation for the next line.
If one line plus the response envelope cannot fit, the result is `Unavailable`
with a recovery. A page never returns no evidence with the same continuation.

**Surface document view.** When `question` is omitted, `ask` returns the
surface's documentation: every `CURRENT` conclusion for that surface, grouped by
the question it answers, with the surface status, gaps, verification, and
context. This is the surface's documentation. The view cannot drift from its
conclusions.

**Surface-first reuse.** The document view is the normal reuse path. A fresh
agent that does not know the exact recorded question asks for the surface
without a question and selects the current conclusion that answers its intent.
An exact `question` is a targeted query and matches the recorded question by
exact identity; a paraphrase is a different question. When a targeted question
finds understanding for other questions on the surface, the `Gap` is `no_match`
and carries a recovery that names the document view. *(F5, A6)*

**The agent sends** a surface with an optional exact question, an exact selector,
or a continuation. Omitting the question reads the surface document view. It
never sends a context, an observation id, or an evidence body.

A context is returned in an answer and may be supplied to `record` or
`reconsider`; it is never an input to `ask`. Context inspection is an
internal/admin retrieval, not an agent operation.

**The agent receives** exactly one of:

| Result | Contains | Guarantee |
| --- | --- | --- |
| `Answer` | `ConclusionView`s (ref, statement, nature, scope, support, evidence), **surface status**, recorded gaps, applicable `VerificationView`s (run plus qualification), context | every listed conclusion is `CURRENT`; stale content is referenced, never served as the answer |
| `Gap` | reason (`invalidated` / `unverifiable` / `unassessed` / `no_match`), changed evidence, historical conclusions with their statement, evidence references, and present non-current state, missing items, admitted evidence, a context when the gap is question-bound, recovery, optional continuation | never a dead end; the recovery names the next action; omitted evidence is recoverable |
| `AmbiguousSurface` | exact candidate identities and the missing decision | no arbitrary scope chosen |
| `RetrievedUnderstanding` | one exact snapshot, its conclusions, live support, challenges | historical, never current-answer content |
| `RetrievedReceipt` | one retained receipt and its context when present | historical, never current-answer content |
| `EvidencePage` | omitted evidence units and an optional further continuation | always advances |
| `Unavailable` | the failure and its recovery | never an empty success |

A `Gap`'s `historical` list is historical **content**, not a pointer: each entry
carries the exact conclusion revision, the understanding version that holds it,
the statement, the evidence references it cites, and the present non-current
state that made it historical. It stays structurally separate from
`conclusions`; historical content never becomes current answer content. The list
is bounded with the rest of the response, and a truncated list names what was
omitted and the snapshot retrieval path (FD-54–FD-57). *(L2, L3)*

**Surface status** is a distribution, not a verdict:

| Component | Meaning |
| --- | --- |
| `current` | conclusions in this surface that are supported by present code |
| `stale` | conclusions whose support no longer holds, directly or through a premise; counted and returned as `stale_refs`, never as answer content |
| `unassessed` | recorded gaps or declared questions with no supported conclusion |
| `unexamined` | boundary members with no understanding at all; computed from the boundary, reported, never required (A9) |
| `descendants` | status of contained surfaces, summarised separately |

A parent surface's own conclusions are its own; descendant status is reported
alongside and never merged into the parent answer. That is what makes a domain
honestly reportable while it still holds both current and stale understanding.

`stale_refs` names each stale conclusion by its exact revision identity, the
understanding version that holds it, and its present non-current support state
(`REASSESSMENT_REQUIRED` or `UNVERIFIABLE`). The count and the references
describe the same set: no stale conclusion is counted without a reference, and
no reference is returned for a current conclusion. Descendant statuses carry
their own references; they are never merged into the parent. A reference is not
answer content: to read the statement, `ask` with
`UnderstandingSnapshotSelector{understanding_id, version}`. The status never
auto-withdraws or auto-corrects a conclusion (FD-23, FD-35, FD-36). *(L2, L9)*

**How it helps.** One call replaces re-reading the code, tells the agent what of
it is current, and names what is not.

### 4.2 `record` — retain

```text
record(kind="understanding", conclusion, locator|observation_id|support, surface?, question?|context)
record(kind="understanding", understanding_id, expected_version, actions)
record(kind="verification", run)
record(kind="surface", action="create"|"update", surface)
```

`kind` selects the record kind. It is not a tool variant. For understanding,
a first version is the flat create above. An update carries `actions`, an object
whose keys are `add`, `confirm`, `correct`, `replace`, `withdraw`. Multiple keys
are applied atomically. The agent never selects a separate record tool, and
`create` is not an action: the flat create form is the only first-version path.

**Surface declaration.** A declared surface (`SERVICE`, `DOMAIN`) carries a
stable name, a boundary, and an optional parent; its identity is the declared
name, so the boundary may evolve without losing its understanding. A path
surface (`FILE`, `SYMBOL`) needs no declaration: it is identified by the path or
canonical locator and is created on first reference.

`record(kind="surface", action="create")` declares a service or domain with a
boundary and optional parent. `action="update"` requires
`expected_boundary_version` and advances exactly one boundary version. A
declared surface must exist before an understanding is recorded against it;
the service never auto-declares a surface from an understanding. The result is
`SurfaceDeclared` with the stored surface and its boundary version.

A parent must be an existing declared surface in the same repository;
self-parent and cycles are rejected. A `create` with a changed boundary under an
existing version is a `Rejected` conflict; an `update` with a stale
`expected_boundary_version` is a `Rejected` naming the current boundary version,
not `Unavailable`. *(A2, A8, L4)*

**Understanding request** carries one conclusion, the evidence that supports it,
the question or the context that binds the target, the surface or the scope
that derives it, and any gaps. A create names exactly one evidence mode —
`locator`, `observation_id`, or non-empty `support` — where `support` is the
complete declared dependency set the agent already holds. A locator may
accompany explicit support as the carried code scope, but an observation id may
not: it would be ignored by the dependency set. A create's scope is supplied or
derived independently of its evidence mode, from explicit `scope_paths`, the
bound context, or a single carried path; a multi-file conclusion names its
owning surface and supplies its scope, or uses a context that binds that scope.
An update carries the expected
version and the action set instead. A create is one conclusion; a second
conclusion is a second request. *(F5, F7, L7)*

A create may supply the `context` from a preceding `ask` instead of re-sending
the question and scope. When that context is a question context, the context
binds the target; supplying `question` or a non-empty `scope_paths` as well is a
`Rejected` conflict, not a silent override. Without a context, a create requires
the question and scope and issues its own evidence-only context. *(F7, L7)*

A create may also omit `surface`. Span derives it from the scope the request
already carries: the question context's bound scope when a context is supplied,
otherwise a single `scope_paths` entry. If the carried scope names more than one
path, the create is `Rejected` with the candidate surfaces. When the agent does
supply a surface, it must agree with the carried scope; a mismatch is `Rejected`.
*(F7, L7)*

**Request identity.** Every request carries the caller's request identity.
Recording derives the submission identity from that identity and the content:
the same identity with the same content is a replay; the same identity with
different content is a conflict; a new identity with identical content is a new
intentional act.

| Action | Meaning |
| --- | --- |
| `add` | add a conclusion lineage while retaining the rest of the membership |
| `confirm` | the same conclusions still hold after substantive reassessment |
| `correct` | a conclusion's content changes; a new revision is created |
| `replace` | one conclusion is superseded by another |
| `withdraw` | a conclusion is retracted, with its basis |

Update actions are compact semantic deltas, not full conclusion snapshots.
The caller supplies semantic intent and evidence it already holds; Span derives
new conclusion lineage identities and all mechanical bookkeeping. `add` carries
`conclusion`; `confirm`, `correct`, `replace`, and `withdraw` carry the existing
`conclusion_id` returned by Span. `correct` also carries `conclusion`;
`replace` carries `conclusion` and `reason`; `withdraw` carries `reason`. No
action accepts a caller-created new lineage identity, and `replace` has no
`new_conclusion_id`. Every action that supplies evidence names exactly one
evidence mode: `locator`, `observation_id`, or non-empty `support`; `withdraw`
may supply one or none. Span derives the old revision identity, any unchanged
assertion nature or scope, the mechanical basis, and the submission digest.
`expected_version` stays mandatory and compare-and-set. *(F5, F7, L4, L7)*

A first version is not an action. It is the flat create
(`conclusion`, one of `locator`, `observation_id`, or `support`, and the target)
stated above. The caller does not supply a conclusion identity; Span derives the
first lineage identity. *(F7, L7)*

Omission is not deletion. Withdrawal is explicit, and history is preserved.

Evidence arrives in whichever form the agent already has it:

- locators and ranges it just read — Span re-reads and fingerprints them, or
- the `context` from a preceding `ask`/`reconsider` — Span reuses what it admitted.

Discovery support follows the same rule: the agent declares the boundary it
inspected and Span derives the observation, or it supplies a discovery
observation from a preceding answer. There is no separate discovery admission
call.

**Verification scope.** A recorded run applies to the surfaces **within** its
declared scope: a run scope path covers a surface path when it is equal or an
ancestor. It is returned in an answer for those surfaces and is not widened by
a broader question; a single-file run does not apply to a broader service.
Record the run against the surface it actually verifies. A run requires
observations or evidence; either is accepted. *(A8, F4)*

There is no separate evidence-admission call. This is F7's test: recording
requires nothing the agent does not already hold.

**The agent receives** exactly one of `UnderstandingRecorded`,
`VerificationRecorded`, or `SurfaceDeclared` for the requested `kind`, or
`Rejected`, or `Unavailable`. An acceptance carries an immutable version, a
receipt with replay identity, the live support qualification, and the updated
surface status — or a rejection naming the exact offending identity, the exact
cause, the structured current version or current boundary version when one
exists, and the required action. The cause is the server's exact validation
message; the adapter does not replace it with a generic action.

**How it helps.** It converts an investigation the agent already performed into
retained understanding, in one call, with no documentation task.

### 4.3 `reconsider` — re-align

```text
reconsider(changed_scope, since?)
reconsider(challenge, understanding_ref, conclusions, reason, evidence)
```

**`changed_scope`** takes the paths the agent just edited, or exact surfaces.
It is an after-edit operation, not a before-edit planning call. Before editing,
use `ask` for current understanding. The result includes every surface that must
be re-examined or repaired, and says why it appears:

- every surface whose boundary contains the change — **containment**;
- every surface that owns a conclusion with direct source or discovery support
  loss — **direct**;
- every surface that owns a conclusion with indirect support loss, including a
  surface whose boundary does not contain the change — **indirect**.

Discovery dependents are part of the direct set: a changed path maps to every
discovery observation whose scope contains it, and the conclusions supported by
those observations are included before the premise walk.

For each included surface:

- the affected conclusions, each with its own support state,
- the checked differences,
- the dependency effects, including descendant effects,
- the current evidence,
- the reason or reasons it appears,
- and a context for re-establishment.

A surface can appear for more than one reason, and the reasons are never
collapsed into one "stale" set. Reasons mean **considered**, not stale: a
conclusion may be included because its surface was considered and still be
`CURRENT`. Only `REASSESSMENT_REQUIRED` and `UNVERIFIABLE` mean actual loss and
require re-establishment. Inclusion is not limited to containment: as F4
requires, a conclusion in one surface can depend on a conclusion in another, and
its owning surface must appear even when the changed file is outside its
boundary.

When `since` is absent, the comparison is present source against each recorded
observation's identity. That is the default and needs no caller input.

**`challenge`** raises an explicit dispute and returns the prior answer, the
evidence, and a context. Challenges are raised here and settled through `record`
with named dispositions. They never settle implicitly, and a matching
fingerprint never settles one.

Results are a closed union: `Changed`, `Challenged`, `Rejected`, `Unavailable`.
`Changed` is keyed by surface; each entry carries its reasons (`containment`,
`direct`, `indirect`) and its affected conclusions with per-conclusion support
state. Each affected conclusion also carries the understanding's current
`expected_version`, so a continuation into `record` needs no intervening `ask`;
only a conclusion in current membership is returned as actionable, while
historical revisions remain traversable as dependencies. `Challenged` carries
the challenge and its derived context; challenges are settled through `record`
with named dispositions.

**How it helps.** It answers the question no per-question API can: *what did my
change invalidate, and at which granularity?* Without it, re-establishment is
discovered by accident.

**It is not what makes the guarantee hold.** F2 makes every `ask` safe on its
own. `reconsider` makes re-establishment efficient. This is how the contract
satisfies A4: the guarantee is server-owned; only efficiency is
agent-initiated.

### 4.4 `structure` — navigate (optional)

```text
structure(reference)                    # exact location and definition
structure(reference, direction, depth)  # bounded structural adjacency
```

Returns structural evidence only — never authority, never a conclusion. It is
exposed only when the host lacks navigation; otherwise the host's own navigation
serves this moment. **How it helps.** It lets an agent find the surface before
it has a question.

### 4.5 `setup` — bind (optional)

```text
setup(repository_locator, authority_seeds?)
```

Binds one repository and returns readiness. It creates no understanding, and it
is never a required preflight for `ask`. The installer binds repositories;
`setup` is exposed only when the host has no installer path. **How it helps.**
One-time setup.

## 5. The internal boundary

Everything in this table exists. None of it is the agent's job. The right-hand
column is the law that forces it inward.

| Internal | Why it is not public |
| --- | --- |
| Context issuance | the agent never needs an id to ask or record (F7) |
| Evidence admission | a step inside `ask`/`record`/`reconsider`, not a task (F7) |
| Observation identity | derived by Span from source (A5, F7) |
| Submission identity | derived from the caller's request identity and content; receipts make retry safe (A2, F7) |
| Support evaluation | an attribute of every returned answer (F2, F6) |
| Surface status computation | an attribute of every returned answer (F9) |
| Retrieval by reference | no separate operation; exact snapshots and receipts fold into `ask`, and context inspection remains internal/admin (F6) |
| Discovery scan and ranking | inside `ask` (F6) |
| Challenge persistence | `reconsider` raises; `record` settles (F5, F6) |
| Status, digest, notices | host-surface notices built from the same computation; never load-bearing (A4, F6) |
| Structural provider build | setup/maintenance, never per-request (F7) |
| Store migration | explicit offline administration (A2) |

Internal does not mean unimportant. It means **not the agent's work**. An API
that promotes any of these to an operation has charged the agent for Span's
bookkeeping, which is the specific failure this layer exists to prevent.

## 6. Contract laws

| Law | Statement | From |
| --- | --- | --- |
| **L1** | Every `Answer` carries per-conclusion support, evidence, and the surface status. | F1, F2, F9 |
| **L2** | Unsupported content is never in `conclusions`; it appears as historical content in a `Gap`, or as references and counts in the surface status. | F2, A7 |
| **L3** | Every `Gap` carries cause, changed evidence, missing items, and — when the gap is bound to a question — a context. | F4, A8 |
| **L4** | Every write is atomic, receipted, retry-safe, and compare-and-set on update. | A2, A3 |
| **L5** | No operation requires a preflight or orientation step. | F7, A8 |
| **L6** | Evidence identity is computed by Span from source, never accepted from a description. | A5 |
| **L7** | The agent supplies intent; Span derives identity, context, and qualification. | F7 |
| **L8** | The operation families are closed at five. Registered tool count is a layer-3 decision constrained by host capability; it may split a family's variants but never add a family. | F6 |
| **L9** | A surface's status is always reported as a distribution, never a single stamp. | F9 |
| **L10** | `reconsider` returns every containing surface for a changed path and reports direct and premise-dependent support loss separately, as F4 requires. | F4, F9 |
| **L11** | A surface's current conclusions are readable as that surface's documentation; there is no separate document artifact to maintain. | G6, F3 |

## 7. Lifecycle mapping

| Agent moment | Operation | Server guarantee |
| --- | --- | --- |
| Orient | `ask` | valid answer, surface status, or actionable gap |
| Investigate | `ask` returns evidence; the agent reads | evidence bound and addressable |
| Conclude | `record` | atomic version, receipt, live support, updated status |
| Reuse | `ask(question)` or `ask(reference)` | valid, with status, or explicitly not |
| Edit | `reconsider(changed_scope)` | every surface to re-examine or repair, with its reason, differences, current evidence |
| Re-establish | `record` against the returned version | supersession, history preserved |
| Dispute | `reconsider(challenge)` then `record` | explicit, never auto-settled |
| Start, resume, compact | nothing | currency is checked on read; nothing here is load-bearing |

## 8. One round trip

```text
1. ask(surface={kind:"FILE", locator:"opencode.json"},
       question="what governs it?")
   ← Gap(unassessed; admitted evidence; context)

2. record(kind="surface", action="create",
          surface={kind:"SERVICE", locator:"mcp-registration",
                   boundary:{paths:["opencode.json"]}})
   ← SurfaceDeclared(boundary version 1)

3. record(kind="understanding",
          surface={kind:"SERVICE", locator:"mcp-registration"},
          question="what governs it?",
          conclusion="opencode.json registers the local span server.",
          locator="opencode.json")
   ← UnderstandingRecorded(version 1, receipt, support=CURRENT, status)

4. reconsider(changed_paths=["opencode.json"])
   ← Changed(affected=[path surface opencode.json,
                        mcp-registration service surface],
             per-conclusion state, current evidence, context)

5. record(kind="understanding", understanding_id="u:…",
          expected_version=1, actions={correct:[…]})
   ← UnderstandingRecorded(version 2, receipt, support=CURRENT, history preserved)
```

Steps 1–3 are the agent's existing work plus the record calls. Steps 4–5 are its
existing edit plus two calls. No step is a documentation task, and no step
requires a memory from a previous session.

## 9. Decisions recorded

| ID | Decision | Rationale | Revisit |
| --- | --- | --- | --- |
| D-1 | `ask` accepts a question or a reference in one operation | keeps the families at five (L8) | amend this layer |
| D-2 | `structure` is one operation with two modes | navigation is one verb (F6) | amend this layer |
| D-3 | The caller supplies a request identity for every write and every `ask`, not a retry token | same identity + same content is a replay; same identity + different content is a conflict; a new identity with identical content is a new act. This distinguishes a retry from an intentional repetition without exposing Span internals (A2, A4, F7). A pure change-scope `reconsider` is a read and carries none | amend this layer |
| D-4 | `ask` has no `change` parameter | a proposed change is expressed in the question; Span does not analyse changes (F5) | amend this layer |
| D-5 | A parent's own conclusions are separate from descendant status | merging would blur granularity and double-count (F9) | amend this layer |

## 10. Constraints on the functional design and implementation

Layer 3 must specify the behaviour that satisfies these constraints; layer 4
must provide the mechanisms.

- declared surfaces with a stable identity and an evolvable boundary, and path
  surfaces identified by path or canonical locator;
- containment mapping, so a changed path resolves to every enclosing surface;
- dependency evaluation that follows premise chains transitively, so indirect
  support loss is reported alongside direct loss;
- immutable understanding versions, with supersession rather than overwrite;
- typed support dependencies, evaluated against present source on every read;
- content identity derived from source, not from caller input;
- surface status computed on read, including `unexamined` from the boundary;
- a surface document view assembled on read from current conclusions, with no
  separately stored document artifact;
- retained receipts keyed by the caller's request identity, replayable across
  restart within their window;
- compare-and-set on every update;
- exactly the five operation families, with no aliases and no per-intent tools;
- a registered tool count justified by observed host delivery, never by
  assuming a shape is deliverable;
- host notices that never carry currency or acceptance.

Layer 4 may choose tables, schemas, transports, and host adapters freely. It may
not revive an internal concern from §5 as a public operation, and it may not
move evaluation from read time to write time.

Layer 2 also imposes a release gate that neither the functional design nor the
implementation can satisfy by itself: each supported task class must be measured
against maintaining parallel documentation and against acting on stale
understanding (F8). A design that is correct but priced above the work it removes
has not met this contract.

## 11. What this layer does not define

Field serialization, wire schemas, storage layout, transport framing, installer
behaviour, and host-specific integration. Those are layer 4 and must satisfy
this layer and the functional design.
