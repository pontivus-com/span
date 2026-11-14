# Span functional design — layer 3

**Status: binding.** This is the third layer of the pyramid. It states the
behaviour that makes the lifecycle contract deterministic and testable, without
choosing a mechanism. Layer 4 — schemas, storage, transport, and host adapters —
must satisfy it.

Where this layer and a higher layer disagree, the higher layer governs. A
requirement here that cannot be traced to a higher-layer statement is a defect.

**0.10.3 target behavior, amended 2026-11-14.** Implementation and host
verification remain pending; current code is not certified by this amendment.

## 1. Scope

This layer answers **how the system must behave to keep the contract**, not
**how it is built**. It defines identity, containment, support evaluation, change
propagation, response composition, state transitions, failure taxonomy,
retention, concurrency, host expectations, and truncation.

It does not define storage layout, wire encoding, transport framing, host
adapters, or exact deployment numbers.

## 2. Identity and binding

**FD-1 — Surface identity is derived, not chosen.**
A declared surface's identity is `(repository, declared name)`; the name is
unique per repository, and declaring the same name with a different kind is a
conflict. A path surface's identity is `(repository, path)`; a symbol surface's
identity is `(repository, canonical locator)`. An identity is never reused for a
different kind. *(F9, L1)*

**FD-2 — Request identity binds a context.**
Only explicit admission or writes issue contexts. Pure obtain and change-scope
reconsider issue none. An issued context is bound to `(repository, request
identity, question when applicable, scope, source selection)`. Repeating
a request with the same identity and the same binding returns the same context;
the same identity with a different binding is `CONTEXT_BINDING_CONFLICT`,
unless a retained recording receipt has already resolved the request (FD-3).
Recovery is original content or a new request identity, never a version change.
*(F7, L7)*

**FD-3 — Submission identity is derived from request identity and content.**
For a write, Span looks up the retained receipt for `(repository, request
identity)` before context issuance/recovery, evidence admission, or any other
new-write check.

- receipt found, content digest equal → replay the receipt;
- receipt found, content digest different → conflict, no new write;
- no receipt → new write, keyed by that identity.

A new intentional act therefore requires a new request identity. *(A2, D-3)*

**FD-4 — Receipt identity survives context expiry.**
A receipt is retrievable by submission identity after its context has expired and
after a process restart, for the retention period defined in FD-42–FD-45. *(A1, A2)*

## 3. Surface containment

**FD-5 — Membership is deterministic.**
A path is a member of a declared surface when it is inside the declared boundary
or equal to a declared symbol. Path surfaces contain themselves. *(F9)*

**FD-6 — A conclusion belongs to exactly one surface.**
The owning surface is the one named when the conclusion was recorded. A
relationship to a conclusion in another surface is expressed as premise support,
never as shared membership. *(F4, F9)*

**FD-7 — Containment is by boundary, with parent as ordering only.**
Every declared surface whose boundary contains a path or symbol contains its path
surface. An explicit parent orders surfaces for traversal; it does not create
membership and cannot remove it. Overlapping declared boundaries are permitted.
*(F4, L10)*

**FD-8 — Unexamined is computed from the boundary.**
`unexamined` counts boundary members with no understanding at all — no conclusion
at any granularity covering that member. It is computed from the declared
boundary and reported. A boundary that cannot be enumerated
reports the limit rather than claiming completeness. *(F9)*

## 4. Support evaluation

**FD-9 — Four dependency kinds.**
Support is a source observation, a discovery boundary, an authority binding, or a
conclusion revision (premise). Nothing else counts as declared support. *(F1, F2)*

**FD-10 — Source dependency.**
Compare the recorded content identity with the present identity of the declared
locator. Missing or unreadable source → `UNVERIFIABLE`. Different identity →
`REASSESSMENT_REQUIRED`. Equal identity → `CURRENT`. *(F2)*

**FD-11 — Discovery dependency.**
Recompute the membership fingerprint of the declared boundary. Changed
membership → `REASSESSMENT_REQUIRED`. Membership that cannot be observed →
`UNVERIFIABLE`. *(F2, F4)*

**FD-12 — Authority dependency.**
Resolve the declared authority. A declaration that no longer exists →
`UNVERIFIABLE`; a changed authority identity → `REASSESSMENT_REQUIRED`; an
unchanged declaration → `CURRENT`. *(F2)*

**FD-13 — Premise dependency.**
Resolve the exact conclusion revision.

- revision exists, is in current membership, and is supported → inherit its
  state;
- revision exists and is in current membership but its own support cannot be
  checked → `UNVERIFIABLE`; inheritance never converts an uncheckable premise
  into a definite finding (FD-10, FD-15);
- revision is withdrawn → `UNVERIFIABLE`;
- revision exists but is superseded or not in current membership →
  `REASSESSMENT_REQUIRED`;
- revision is absent → `UNVERIFIABLE`;
- cycle encountered → `UNVERIFIABLE`.

*(F2, F4)*

**FD-14 — Cycles are explicit.**
A premise walk that revisits a revision marks every revision on the cycle, and
every dependent of the cycle, as `UNVERIFIABLE` with a cycle reason. A cycle is
never reported as current and never silently truncated. *(F2)*

**FD-15 — Combined state precedence.**
Across declared dependencies: any `UNVERIFIABLE` → `UNVERIFIABLE`; else any
`REASSESSMENT_REQUIRED` → `REASSESSMENT_REQUIRED`; else `CURRENT`. Declaring a
change when a dependency cannot be checked would assert a definite finding that is
not established (F1, A6). See §13. *(F2, A7)*

**FD-16 — Reasons are complete.**
The combined evaluation lists every non-current dependency with its state and
reason, so a definite finding is not lost inside an `UNVERIFIABLE` summary.
*(F2, A8)*

## 5. Change propagation

**FD-17 — Paths map to surfaces in both directions.**
A changed path maps to its path surface and to every declared surface whose
boundary contains it. *(F4, L10)*

**FD-18 — Direct support loss.**
A conclusion loses support directly when it declares a source dependency on the
changed path, or a discovery dependency whose scope membership contains the
changed path. Where a reliable declared range exists, evaluate that range;
otherwise evaluate the whole file. A range that cannot be reliably bound falls
back to the whole file rather than to a narrower claim. *(F2, F4)*

**FD-19 — Indirect support loss.**
After direct loss, walk premise chains to a fixed point. A conclusion whose
premise is `REASSESSMENT_REQUIRED` becomes `REASSESSMENT_REQUIRED`; if the
premise is withdrawn, absent, or cannot be checked, the conclusion is
`UNVERIFIABLE`, and FD-15 governs the combined state. *(F4)*

**FD-20 — Inclusion is complete.**
The result includes every surface that must be re-examined or repaired: by
containment, by direct source or discovery loss, or by indirect loss — including
a surface whose boundary excludes the changed path. Entries are deduplicated by
surface and carry the set of reasons that apply. Inclusion is not a verdict:
each affected conclusion carries its own support state, so a considered
conclusion may remain `CURRENT`. *(F4, L10)*

**FD-21 — Ordering is deterministic.**
Surfaces are ordered narrowest to widest, then by identity; conclusions within a
surface are ordered by their recorded sequence. The same change produces the same
order. *(A2, L10)*

**FD-22 — Unaffected is bounded and explicit.**
A surface may be reported unaffected only within the examined boundary. A bounded
walk that cannot complete reports the limit; it does not report "unaffected".
*(F4, A8)*

## 6. Response composition

**FD-23 — The Answer/Gap threshold is defined.**
`ask` returns `Answer` when at least one matched conclusion is `CURRENT`. It
returns `Gap` when no matched conclusion is current. `Answer` contains only
current conclusions; stale conclusions appear as references in the surface
status, never as answer content. A supported conclusion is never withheld because
another matched conclusion is stale: that would discard usable understanding
(A9) and force re-derivation (F8). See §13. *(F2, L2)*

The historical view is assembled at read time from the stored revisions. Each
`Gap.historical` entry carries the exact revision, the understanding version
that holds it, the statement, the evidence **references**, and the present
non-current support state. It is never a stored second copy, never a
compatibility shape, and never mixed into `conclusions`. The surface status
names the same set through `stale_refs`: exact revision, understanding version,
and present state, alongside the count. Descendant statuses keep their own
references. Neither view auto-withdraws or rewrites history; recovery is an
explicit `record` action. *(FD-20, FD-21, FD-23, FD-35, FD-36)*

**FD-24 — Partial answers are usable.**
An `Answer` may therefore contain current conclusions while the surface status
reports stale and unassessed items, and while recorded gaps are returned. The
agent can act on the current part and see exactly what is missing. *(A9, L3)*

**FD-25 — Gap reasons are exhaustive.**
For surface/current-identity membership selected under lifecycle §4.1, no current
conclusion yields one reason from combined support: REASSESSMENT_REQUIRED becomes
`invalidated`, UNVERIFIABLE becomes `unverifiable`, and no retained usable
understanding becomes `unassessed`. String-question matching and its `no_match`
production path are retired. Stored question metadata/history is not rewritten.
An unknown exact identity is a lookup rejection, not a newly invented Gap.
Context binding/admission failures never become semantic absence. *(F4, A8, L3)*

**FD-26 — Ambiguity is a separate result.**
When a surface reference resolves to more than one granularity, the result is
`AmbiguousSurface` with the candidates and the missing decision. It is never a
`Gap` reason and never an arbitrary choice. *(F9, L2)*

**FD-27 — Operational failure is not an empty answer.**
A failure that prevents evaluation — unavailable store, provider error, schema
version — returns `Unavailable` with the recovery. An unreadable source is not
`Unavailable`; it is `UNVERIFIABLE` support. *(A8, L3)*

Context-issuance conflicts propagate as typed rejection; expected store/provider
access failures propagate as Unavailable. A catch-all conversion to Gap is
forbidden. Missing/invalid references identify the bound repository/context and
public corrective action; absence alone does not establish expiry or reaping.
Stateful validation stays with its canonical owner. *(FD-39, FD-41, L3, L5)*

**FD-28 — The document view is assembled, never stored.**
The view is composed on read from current conclusions; no stored copy exists. Its
contents are fixed in `lifecycle-contract` §4.1. *(G6, L11)*

Pure surface obtain groups all current membership by recorded question metadata;
current identity selectors restrict membership before the same composition.
No pure read issues a context or requires request identity. Its role as
the reuse path is stated in `lifecycle-contract` §4.1. *(G2, F3, A4, L11)*

**FD-29 — Result ordering is stable.**
Current conclusions first, grouped by question; then status; then gaps and
verification; then references. The same request produces the same order. *(A2)*

## 7. State transitions

**FD-30 — create.** The first version for `(surface, question)`. *(L4)*

A create may reuse a persisted question-origin context through its bound
reference; new explicit ask admission is evidence-only. Evidence-only contexts
never supply a semantic question. Target resolution follows lifecycle §4.2.
An explicit question/non-empty scope conflicts only with a question-origin
context that already binds that target; evidence-only contexts require the
independent semantic inputs. Neither origin is guessed from reference presence.
*(F7, L7)*

A create derives one complete effective semantic `EvidenceScope`: the question
context's complete scope, otherwise explicit `scope_paths`, a direct locator,
or an explicit FILE surface path. The same carrier drives owner resolution,
owner agreement, canonical target and conclusion construction, and persisted
understanding/version scopes. Support dependencies establish the conclusion but
do not redefine that scope. A supplied owner must contain every canonical
semantic member under FD-5; this applies to FILE/SYMBOL and declared owners. Omitted
ownership resolves only one unambiguous path surface; it never infers a declared
surface. *(F9, FD-1, L4)*

A create carries its complete explicit support when supplied, otherwise the
admitted observation or a re-read of the cited locator. *(F5, F7, L2)*
The new conclusion lineage identity follows L7; assertion nature defaults to
`DESCRIPTIVE`; the basis records explicit evidence from the cited source.
*(F5, F7, L2)*

**FD-31 — confirm.** A re-establishment action: accepted only after present
support has been checked, and only for a version whose recorded support was not
current. If the version is already current and unchanged, the operation returns
the current version rather than creating a new one. Unchanged wording alone is
never a confirmation. A confirm names the conclusion and the reassessed
evidence; Span preserves the current statement, assertion nature, and scope and
derives a non-empty mechanical basis. *(F2, A6, F8, L4)*

**FD-32 — correct.** A conclusion's content changes and a new revision is
created. Dependents on the previous revision become `REASSESSMENT_REQUIRED`.
The corrected statement and its complete supplied support are explicit; an
omitted assertion nature or scope is preserved from the current revision, and
Span derives the content basis. *(F4)*

**FD-33 — replace.** A conclusion is superseded by another. Dependents on the
superseded revision become `REASSESSMENT_REQUIRED`. Replacement never retargets
another conclusion's premises silently. The action identifies the current
lineage being replaced. The replacement lineage identity follows L7. Span
derives the exact current old revision, preserves an omitted assertion nature
or scope for the new conclusion, uses the supplied reason as the replacement
basis, and derives the new content basis. *(F4)*

**FD-34 — withdraw.** A conclusion is retracted with its basis. Dependents on the
withdrawn revision become `UNVERIFIABLE`. The action supplies the reason;
Span derives the withdrawal basis from that reason and accepts an optional
support set. A withdrawal revision remains an explicit non-current reference
in surface status and is retrievable in its immutable snapshot with its reason.
It is not projected as supported statement content in `Gap.historical`; prior
supported revisions remain retrievable by their own exact version. *(F2, F3, F4)*

No transition above bypasses the expected-version compare-and-set (FD-46), and
none interprets meaning automatically. *(A3, F5, L4)*

**FD-35 — Omission is not deletion.** Each version carries the complete
membership of conclusion references. A conclusion absent from a new version is
not thereby withdrawn; withdrawal is explicit. *(L4)*

**FD-36 — Supersession preserves history.** Every version is immutable, the
newest accepted version is current, and prior versions remain retrievable.
*(F3)*

**FD-37 — Premise effects are reported, not applied silently.** Any transition
that invalidates a premise must name the affected dependents in the same result.
*(F4, L10)*

## 8. Failure taxonomy

**FD-38 — Closed unions.**
`ask`, `record`, and `reconsider` each return exactly the results declared in
`lifecycle-contract` §4.1–§4.3. There are no optional public operations in the
current build. No result is invented at runtime and no result crosses
operations. *(L3)*

**FD-39 — Rejection is not replay and not unavailability.**
A replay returns the original acceptance. A rejection returns the offending
identity and the required action. Unavailability returns the operational failure
and recovery. They are never merged. *(A2, A8)*

A rejection carries what `lifecycle-contract` §4.2 fixes. This design owns only
the separation above: a failure that prevents evaluation is `Unavailable`
(FD-27), never a rejection. *(A2, A8)*

**FD-40 — No partial application.** A rejected write commits nothing: no version,
no revision, no challenge disposition, and no consumed context. *(A2, L4)*

**FD-41 — Every rejection is actionable.** The rejection names the exact identity
that failed validation and what must change. Recovery must correct the actual
invariant: original content/new identity for binding conflicts, in-scope evidence
or context-free direct recording for scope conflicts, and the admitting context
or direct evidence for context-bound references. What it carries is fixed in
`lifecycle-contract` §4.2. *(A8)*

## 9. Retention and recovery

**FD-42 — Context expiry removes membership only.** Expiry of a context does not
remove accepted understanding, challenge history, verification runs, or receipts.
*(A1, A2)*

**FD-43 — The replay window is derived, not invented.**
A receipt is retained at least as long as the longest supported session
suspension, so a caller that can resume can recover its identity. That lower
bound follows from A1 and A2. The concrete window is a deployment measurement
recorded in layer 4, not a product choice. *(A2)*

**FD-44 — History reaping must not silently break premises.**
If retained history is reaped, any premise that referenced a removed revision
becomes `UNVERIFIABLE` and is reported. Reaping never turns a broken premise into
a current one. *(F2, F3)*

**FD-45 — Restart recovery is by identity.**
After a restart, a request identity recovers its context if retained and its
receipt if retained. No conversation replay is required. The canonical context reference binds
repository and context identity at issuance. Context-bound routing derives from
that reference with no separate override; lookup still validates actual liveness
and membership. No cross-store search or context replacement is implicit. Pure
change-scope reconsider is not assigned a content-derived expiring identity.
*(A1, A2, L7)*

## 10. Concurrency

**FD-46 — Updates are compare-and-set.**
An update names the expected version. A mismatch rejects the write and reports
the current version. *(A3, L4)*

This applies to understanding versions and to declared-surface boundary
versions. The surface-conflict case is fixed in `lifecycle-contract` §4.2.
*(A3, L4)*

**FD-47 — Same identity, concurrent writers.**
Two writers with the same request identity and content produce one acceptance and
one replay. Same identity with different content produces one acceptance and one
conflict. *(A2, A3)*

**FD-48 — Different identities, same version.**
Exactly one write succeeds; the other is rejected as a version conflict. There is
no last-write-wins and no silent merge. *(A3)*

## 11. Host contract

**FD-49 — The host delivers the advertised schema.**
Span requires the host to expose the declared tool schemas without coercion or
re-encoding that changes their meaning. *(L8)*

**FD-50 — The host preserves request identity.**
A retry must carry the same request identity if it is the same act. If a host
cannot preserve it, replay safety is not claimed for that host. *(A2, D-3)*

**FD-51 — The host delivers a complete result or states truncation.**
A host that truncates must say so. A truncated result is not a smaller correct
result. *(A8)*

**FD-52 — Answer safety is independent of host notices.**
Support checks occur within the operations returning understanding, regardless
of notice delivery. The agent lifecycle remains required by layer 2 §7. *(A4)*

**FD-53 — Live delivery is unverified until captured.**
A host contract is established only by a recorded capture observed or failed.
*(A8)*

**FD-58 — Lifecycle notices reach the agent at the moment of use.**
For a registered operational repository, the adoption notice names the direct
lifecycle tools and their required use, including when no understanding has yet
been recorded. A source-change notice names the next required `reconsider`
action. Notices report operational availability and observed support through
the canonical computations; they do not author semantic conclusions or certify
meaning. Measure delivered notice cost under F8 and delivery under FD-53.
*(F5, F10, G2)*

## 12. Bounds and truncation

**FD-54 — Response size is server-owned.**
The agent does not manage response size; the default is set per host and recorded
with the delivered result. *(F7)*

**FD-55 — Truncation is explicit and recoverable.**
A truncated result names what was omitted and provides a public way to retrieve
it. The continuation contract is `lifecycle-contract` §4.1. A response is
complete or explicitly truncated. *(A8)*

**FD-56 — Truncation never substitutes stale content.**
A budget limit never promotes historical content into answer content and never
omits the fact that truncation occurred. *(F2, A7)*

**FD-57 — A result too small to be safe is refused.**
If the budget cannot carry the result kind, the surface identity, and the fact of
truncation, the operation returns an explicit budget refusal rather than a
misleading fragment. *(A7, A8)*

**FD-59 — Recording context scope is fixed; derived operational scope is complete.**
Source evidence admission requires membership in the supplied context's scope;
discovery admission requires complete-scope containment. Repository-wide outer
scope contains any inner scope; restricted outer scope cannot contain a
repository-wide inner scope. Context-free recording composes the complete union
of actual semantic/verification and admissible evidence requirements after
receipt resolution. Repository-wide requirements absorb narrower ones. This
operational scope never changes understanding's semantic scope. Context-admitted
references remain context-bound and are never dropped or made portable.
*(A5, A8, F7, F9, L5, L7)*

**FD-60 — Accepted understanding reports ownership through live status.**
After commitment, compose current status for the understanding's canonical owner.
Operational status failure preserves acceptance and reports explicit status
unavailability. Status is never persisted in the receipt. *(F9, L4)*

## 13. Why these choices follow

The four choices that resemble judgement calls are derivations, not preferences.

### The Answer/Gap threshold (FD-23, FD-25)

F2 forbids presenting unsupported content as an answer. L2 and L3 require
unsupported content to appear as history or references instead. F2 preserves the current part, and F8 penalises discarding usable understanding.

Therefore: if at least one matched conclusion is current, the result is an
`Answer` containing only current conclusions, with the rest reported as status
references. If none is current, the result is a `Gap`. The Gap reason follows the
combined state under FD-25; membership is selected by surface/current identity,
not by a supplied question string.

Withholding a supported conclusion because a sibling is stale would satisfy no
principle and violate two.

### The state precedence (FD-15)

F1 makes code the authority, A6 says confidence is not evidence, and A7 requires
a safe default. If any dependency cannot be checked, the conclusion is not
established. Reporting `REASSESSMENT_REQUIRED` in that case would assert a
definite change that has not been observed — promoting uncertainty to a claim.
Therefore `UNVERIFIABLE` dominates. FD-16 keeps every definite finding visible,
so nothing is hidden; only the summary is conservative.

### The replay window (FD-43)

A2 requires that a lost response not duplicate work; A1 requires that a resumed
session recover; D-3 makes the retry the same request identity. The receipt must
therefore outlive the longest suspension a supported host allows. That lower
bound is derived. The exact window is a deployment measurement because the
suspension length is a property of the host, not of Span.

### confirm (FD-31)

F2 requires present support for any claim of currency; A6 forbids treating
unchanged wording as evidence; F8 penalises work that adds no value. A
confirmation is therefore a re-establishment, not a re-assertion: it requires a
present check and applies to a version that was not current. If the version is
already current and nothing changed, a new version would be churn, so the current
version is returned.

## 14. What this layer does not define

Storage layout, wire schemas, transport framing, installer behaviour, host
adapters, and exact deployment numbers. Those are layer 4 and must satisfy this
layer.
