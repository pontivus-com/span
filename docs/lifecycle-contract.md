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

**0.10.3 target contract, amended 2026-11-14.** Runtime implementation and
host delivery are pending. These requirements describe the target behavior;
they do not certify that the installed server already conforms.

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

## 3. The three public lifecycle operations

| Decision | Source |
| --- | --- |
| The surface is obtain, retain, re-align — and no more | F6 |
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
not classify them; the surface or exact understanding identity selects membership,
and the agent judges applicability.

Audit needs no sixth operation. Every answer carries the surface status, because
a reader who cannot tell current from stale has not been answered (F9).

Exactly three public tools realize these moments: `ask`, `record`, `reconsider`.
The installer binds repositories; the host supplies structural navigation.

## 4. Public lifecycle operations

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

Exactly one form is supplied:

| Form | Inputs | Effect |
| --- | --- | --- |
| Surface obtain | `repository_id` and exactly one of `surface` / `reference` | Read current grouped understanding and status; no request ID or context |
| Explicit source admission | Surface obtain inputs, non-empty `evidence` selection and `request_id` | Admit selected sources/ranges into a recoverable evidence-only context |
| Exact current obtain | `selector=CurrentUnderstandingSelector{repository_id, understanding_id}` | Read that understanding's current membership with live support/status |
| Historical/audit obtain | `selector=UnderstandingSnapshotSelector{repository_id, understanding_id, version?}` or `ReceiptRetrievalSelector{repository_id, request_id}` | Retrieve the exact snapshot or receipt; never current-answer content |
| Evidence continuation | `continuation` | Read the next selected-evidence page using its bound repository/request/context |

A surface is an exact `{kind, locator}` identity, never containment. A reference
must resolve to exactly one surface; otherwise return `AmbiguousSurface` with
exact candidates. No ordinary form accepts `question`. Recorded questions are
metadata grouped in the document view. They are not natural-language query keys.
An exact selector and continuation carry their own repository binding; a separate
repository override is forbidden. Unknown exact identities have an explicit
lookup rejection and public recovery, not an invented surface or generated answer.

**Pure obtain.** Surface/reference obtain returns all CURRENT conclusions on
that surface, grouped by recorded question, with status, gaps, verification,
limitations and explicit omissions. A current selector restricts membership to
its returned understanding identity and uses the same support/status owners.
Neither form creates an investigation context or requires caller request identity.
A genuinely unassessed surface remains a Gap. Recovery identifies the missing
investigation and available source pointers without pretending they are admitted
observations or fingerprinted proof. No source bodies are delivered unsolicited.

**Explicit evidence.** `evidence` is a non-empty selection of exact source
locators and ranges. Admission is restricted to the resolved surface and issued
scope. Whole-file requests are explicit. A valid selection returns the same
Answer/Gap classification plus the selected excerpts, source identity, exact
original ranges, observation membership and a bound context reference. Each
source outcome is tied to its request; missing/unreadable/omitted sources remain
explicit. Source or store failure is not semantic absence. The request identity
binds the complete selection; identical retries recover the same context.
Admission does not imply the agent read all selected bytes or established meaning.
The host owns structural navigation; Span never guesses relevant symbols/ranges.

**Context reference.** A returned `context` is one canonical
`InvestigationContextRef{repository_id, context_id}`, emitted by its owning
persisted context. It is not an unqualified ID. Context-bound operations derive
routing from that reference and reject independent repository overrides. The
reference grants no authority; liveness, scope and membership are checked at the
owner. Pure obtains have no context. Context inspection remains internal/admin.

**Continuation.** A continuation binds repository, investigation context,
original request identity/digest and next evidence position. It introduces no
separate storage or retention lifecycle. Each page advances by at least one
unit or exact line range; an oversized unit splits at line boundaries. Omission
is explicit and recoverable. One line that cannot fit is refused explicitly.
Wrong binding, malformed or absent references return a typed rejection with
public recovery. Genuine operational access failure is Unavailable. A missing
row is not labeled expired or reaped without evidence. Identical continuation
replay against the same live context returns the same page across restart.

The closed result union is `Answer`, `Gap`, `AmbiguousSurface`,
`RetrievedUnderstanding`, `RetrievedReceipt`, `EvidencePage`, `Rejected`,
`Unavailable`. Answer carries only CURRENT statements, nature, scope,
per-conclusion support, evidence references, surface status and applicable
verification. Gap carries status, cause (invalidated/unverifiable/unassessed),
changed evidence, historical content, missing items and actionable recovery.
Context/admitted evidence/continuation occur only when explicit admission ran.
All bounded results preserve omission and recovery. Historical retrieval includes
live support qualification of the exact revisions but is never served as Answer.
Compact qualification and audit retrieval follow §4.2; no evidence is invented
merely to populate a cheap result. *(L1–L3, L7, L9, L11)*

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
| `unexamined` | boundary members with no understanding at all; computed from the boundary and reported with explicit enumeration limits (F9) |
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

A create may supply the admitting `context` reference. A persisted question-origin
context binds the target; supplying `question` or non-empty `scope_paths` as well
is a Rejected conflict, not an override. New explicit ask admission is evidence-only:
its context does not supply the semantic question or independently determine an
owner. Such creates supply question and semantic scope through the declared
direct inputs. Without a supplied context, Span derives its operational context
from those inputs and complete support requirements. *(F7, L7)*

A create may also omit `surface`. Span derives it from the scope the request
already carries: the question context's bound scope when a context is supplied,
otherwise the effective scope derived from `scope_paths`, a direct locator, or
an explicit FILE surface. If the carried scope names more than one
path, the create is `Rejected` with the candidate surfaces. When the agent does
supply a surface, every semantic member must agree with that owner; a mismatch
is `Rejected`. FILE/SYMBOL agreement follows path-surface membership (FD-5),
not the presence of just one matching member.
*(F7, L7)*

Semantic scope describes what the conclusion is about; support identifies what
established it. Multiple support files do not create additional owning surfaces.
The effective semantic scope is a complete `EvidenceScope`: paths, exact evidence
references, or an empty scope denoting the whole repository. A supplied
SERVICE/DOMAIN must already exist and contain the complete semantic scope.

**Recording contexts.** A supplied context retains its complete issued scope.
New source evidence may be admitted inside it; a newly cited discovery boundary
must be wholly contained by it. Evidence membership may grow, but scope never
widens. A supplied `context` is the bound reference defined in §4.1; the
context-bound branch forbids a separate repository override. Direct-evidence
branches carry their repository explicitly. The same alternatives apply to
verification, update and challenge inputs that use admitted observations.
When investigation expands, omit `context` and provide direct
scope/evidence. Span derives an evidence-only operational context sufficient for
all required evidence, including repository-wide discovery when cited. This
operational scope never replaces the semantic scope of an understanding.
Admitted evidence references and observation IDs remain context-bound; supply
the admitting context or express dependencies through direct evidence.

**Request identity.** Every request carries the caller's request identity.
Retained receipt resolution precedes context issuance, evidence admission, and
command construction. Recording derives the submission identity from that
identity and the content:
the same identity with the same content is a replay; the same identity with
different content is a conflict; a new identity with identical content is a new
intentional act.
Across a grammar upgrade, retained accepted receipts remain retrievable by their
original repository/request identity for their promised retention period. A new
grammar does not authorize translating a historical write into another write or
blindly repeating it. Recover the accepted outcome first; old input acceptance
and immutable history retrieval are different promises.

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

**Structural grammar.** Kind/action selection, field presence, evidence-mode
exclusion and syntactic target/scope inputs have one canonical typed declaration
used by decoding and advertised schema projection. Null, omitted, empty and
unknown fields have the same meaning at both boundaries. Stateful context origin,
liveness/membership, surface containment and version checks remain with their
canonical runtime owners. Conflicting structural inputs are rejected before
admission, with all independently determinable conflicts and corrective fields;
validation never continues source work merely to collect more errors.

Omission is not deletion. Withdrawal is explicit, and history is preserved.

Evidence arrives in whichever form the agent already has it:

- locators and ranges it just read — Span re-reads and fingerprints them, or
- the bound `context` from explicit ask admission or a challenge — Span reuses
  its admitted evidence. Pure obtain/change analysis never implies admission.

Discovery support follows the same rule: the agent declares the boundary it
inspected and Span derives the observation, or it supplies a discovery
observation from a preceding answer. There is no separate discovery admission
call.

**Verification scope.** A recorded run applies to the surfaces **within** its
declared scope: a run scope path covers a surface path when it is equal or an
ancestor. It is returned in an answer for those surfaces and is not widened by
a broader question; a single-file run does not apply to a broader service.
Record the run against the surface it actually verifies. A run requires
at least one observation or evidence item; both may coexist. Observations require
their admitting context. Direct evidence may be newly admitted inside a supplied
context, or recorded without one against explicit run scope/evidence. *(A8, F4)*

There is no separate evidence-admission call. This is F7's test: recording
requires nothing the agent does not already hold.

**The agent receives** exactly one of `UnderstandingRecorded`,
`VerificationRecorded`, or `SurfaceDeclared` for the requested `kind`, or
`Rejected`, or `Unavailable`. An acceptance carries an immutable version, a
receipt with replay identity, the live support qualification, and the updated
surface status — or a rejection naming the exact offending identity, the exact
cause, the structured current version or current boundary version when one
exists, and the required action. For `UnderstandingRecorded`, live qualification
and owning `SurfaceStatus` are
composed after acceptance. Expected operational failure is represented by
`SupportUnavailable` or `SurfaceStatusUnavailable` while preserving the accepted
receipt. Status is never persisted in that receipt. The cause is the server's
exact validation
message; the adapter does not replace it with a generic action.

**Compact public acceptance and exact detail.** Return each identity and fact
once: repository/request, commit time, exact receipt selector, accepted
understanding/version, affected revision coordinates, dependent effects, live
qualification and owning status. Qualification includes exact revision, state,
evaluation time, material limitations, non-current dependency findings/causes
and detail coordinates. An all-current dependency list may be retrieved rather
than repeated; failed findings are never suppressed as a size optimization.
Applicable verification carries identity, command/outcome and qualification once.
Unavailable post-commit qualification/status preserves the accepted effect.

The receipt selector retrieves the full immutable acceptance, digest and replay
details. The snapshot selector with the exact accepted understanding/version
retrieves revisions/dependencies and their live qualification, with evaluation
time. Neither historical retrieval becomes Answer content. Omission remains
explicit and recoverable; compact output is not permission to drop audit state.

**How it helps.** It converts an investigation the agent already performed into
retained understanding, in one call, through its retained conclusions.

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
- and exact update coordinates/source references for re-establishment.

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
Change-scope reconsider is a pure read: it issues no context, requires no request
identity and must not bind repeated changed paths to a content-derived expiring
request. Re-establishment uses direct evidence with the returned update version;
explicit admitted observations use their original bound context reference.

**`challenge`** raises an explicit dispute and returns the prior answer, the
evidence, and a context. Challenges are raised here and settled through `record`
with named dispositions. They never settle implicitly, and a matching
fingerprint never settles one.
The context is the canonical bound reference from §4.1. Challenge is a write
with stable request identity; a supplied context determines routing, without an
independent repository override. Direct challenge evidence derives its context
internally. This write branch is distinct from pure change-scope reconsider.

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

**Safety and participation.** F2 makes every `ask` check declared support.
The agent calls `reconsider` after changes and completes the applicable
re-establishment work under §7.

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
| Exact understanding membership and surface document view | inside `ask` (F6) |
| Challenge persistence | `reconsider` raises; `record` settles (F5, F6) |
| Status, digest, notices | host-surface notices use the same computation; answer safety remains server-owned (A4, F6) |
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
| **L3** | Every `Gap` carries cause, status, changed evidence, missing items and public recovery; explicit evidence admission also carries its bound context and source outcomes. | F4, A8 |
| **L4** | Every write is atomic, receipted, retry-safe, and compare-and-set on update. | A2, A3 |
| **L5** | An operation accepts its declared inputs without an unrelated API preflight; this does not waive the agent lifecycle in §7. | F7, A8 |
| **L6** | Evidence identity is computed by Span from source, never accepted from a description. | A5 |
| **L7** | The agent supplies intent; Span derives identity, context, and qualification. | F7 |
| **L8** | The public operations are exactly `ask`, `record`, and `reconsider`. | F6 |
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
| Start, resume, compact | `ask` when semantic work begins or resumes | current retained understanding or an actionable gap |
| Complete | applicable records and re-establishment are accepted | retained conclusions and explicit disposition, or a named operational blocker |

### Required agent completion

Before deriving semantic understanding, consult Span for the relevant surface.
For reuse, read its no-question document view; use an exact recorded question
for targeted retrieval. Investigate the returned gaps and evidence, then record
supported conclusions when established. After editing, call `reconsider` with
the changed paths, follow explicit omissions/recovery, and investigate returned
`REASSESSMENT_REQUIRED` or `UNVERIFIABLE` conclusions. Record the supported
confirmation, correction, replacement or withdrawal against the returned version.
New supported conclusions established during that investigation are also retained.

Complete the applicable lifecycle before claiming the work complete. Reusing a
current applicable conclusion requires no duplicate record. Preserve genuine
uncertainty and disputes; report a named operational blocker when the lifecycle
cannot complete. A rejected call is not retained understanding. Acceptance with
unavailable qualification preserves its receipt and requires explicit recovery.
Direct `record` ingress remains supported; its API capability does not waive
consultation before deriving understanding.

## 8. One round trip

```text
1. ask(repository_id="repo", surface={kind:"FILE", locator:"opencode.json"})
   ← Gap(unassessed; status; source pointers; recovery)

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
             per-conclusion state, source references, update coordinates)

5. record(kind="understanding", understanding_id="u:…",
          expected_version=1, actions={correct:[…]})
   ← UnderstandingRecorded(version 2, receipt, support=CURRENT, history preserved)
```

Steps 1–3 are the agent's existing work plus the record calls. Steps 4–5 are its
existing edit plus two calls. Each step serves the current investigation, and none
requires a memory from a previous session.

## 9. Decisions recorded

| ID | Decision | Rationale | Revisit |
| --- | --- | --- | --- |
| D-1 | Obtain forms are owned by §4.1 | preserves the three lifecycle operations (L8) | amend this layer |
| D-3 | The caller supplies a request identity for every write and explicit source admission, not pure obtain or a retry token | same identity + same content is a replay; same identity + different content is a conflict; a new identity with identical content is a new act. This distinguishes a retry from an intentional repetition without exposing Span internals (A2, A4, F7). A pure change-scope `reconsider` is a read and carries none | amend this layer |
| D-4 | `ask` has no `change` parameter | before-change understanding uses surface obtain; Span does not author proposed-change analysis (F5) | amend this layer |
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
- exactly `ask`, `record`, and `reconsider`, with no per-intent tools;
- host delivery verified against the three declared schemas;
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
