# Span functional design — layer 3

**Status: binding target for Span 1.0 Beta.** This is the third layer of the pyramid. It states the
behaviour that makes the lifecycle contract deterministic and testable, without
choosing a mechanism. Layer 4 — schemas, storage, transport, and host adapters —
must satisfy it.

Where this layer and a higher layer disagree, the higher layer governs. A
requirement here that cannot be traced to a higher-layer statement is a defect.

**1.0 Beta functional design.** This document states binding deterministic
behavior. Implementation and delivery conformance are evidenced separately in
[acceptance](acceptance.md); implementation state never changes the authority of
this design.

## 1. Scope

This layer answers **how the system must behave to keep the contract**, not
**how it is built**. It defines identity, semantic containment, Functional Pyramid resolution,
support evaluation, governance and source change propagation, response
composition, state transitions, failure taxonomy, retention, concurrency, host
expectations, and truncation.

It does not define storage layout, wire encoding, transport framing, host
adapters, or exact deployment numbers.

FD-1–FD-60 retain their established identities from the pre-Version-1 design.
Version-1 Functional Pyramid behavior begins at FD-61 even where those rules are
placed earlier in this document so the existing requirement identities are not
renumbered.

## 2. Identity and binding

**FD-1 — Surface identity is derived, not chosen.**
A declared surface's identity is `(repository, declared name)`; the name is
unique per repository, and declaring the same name with a different kind is a
conflict. A path surface's identity is `(repository, path)`; a symbol surface's
identity is `(repository, canonical locator)`. An identity is never reused for a
different kind. *(F9, L1)*

**FD-2 — Context issuance and request identity are distinct.**
Ordinary obtain issues no context. Explicit evidence admission and ordinary
repository-scoped semantic/verification/challenge writes issue or reuse contexts
under their caller-owned request identities as required by their evidence path.
Functional Pyramid participation writes are installation-scoped lifecycle writes
and issue no investigation context merely because they are writes.
Change-scope reconsider also issues the bounded re-establishment contexts required
by F4, but their issuance identities are Span-owned and not caller retry keys. Any identity-bearing context
is bound to `(repository, request identity, question when applicable, scope,
source selection)`. Repeating a caller-identified request with the same identity
and binding returns the same context; the same identity with a different binding
is `CONTEXT_BINDING_CONFLICT`, unless a retained recording receipt has already
resolved the request (FD-3). A repeated changed-scope reconsider is instead a new
read and receives a usable live context even when an earlier one expired; its
internal identity is never derived from the changed-scope payload. Recovery for
caller-identified requests is original content or a new request identity, never a
version change or TTL increase. *(F4, F7, L7, L10)*

**FD-3 — Submission identity is derived from request identity and content.**
Ordinary repository-scoped recording looks up the retained receipt for
`(repository, request identity)` before context issuance/recovery, evidence
admission, or any other new-write check. Functional Pyramid recording uses the
distinct installation-level request-identity namespace fixed by lifecycle §4.2
and FD-85; no member repository is selected as an artificial key owner.

Within either namespace:

- receipt found, content digest equal → replay the accepted durable effect;
- receipt found, content digest different → conflict, no new write;
- no receipt → new write, keyed by that namespace's identity.

A replay whose accepted Functional Pyramid write has actionable dependent
effects may issue fresh live re-establishment contexts without changing the
immutable receipt/effect set. A new intentional act therefore requires a new
request identity. *(A2, D-3, L4, L14)*

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

## 4. Functional Pyramid resolution

The Functional Pyramid is a governance graph, not a semantic surface hierarchy.
Its resolution is deterministic and uses only explicit declarations. Semantic
surface ownership continues to follow FD-1–FD-8.

**FD-61 — Participation is explicit and distinct from registration and health.**
A registered repository is `UNCONFIGURED` until Functional Pyramid lifecycle
state says otherwise. `EXCLUDED` is an explicit non-participation decision.
`ACTIVE` means the repository belongs to one explicit, versioned Functional
Pyramid instance. Those are the only durable participation states. Repository
installation, co-location, imports, directory nesting or host registration never
imply participation.

An ACTIVE pyramid's present health is computed independently as
`VALID | DEGRADED`; evaluating health never performs a participation-state
write. Surface obtain projects UNCONFIGURED/EXCLUDED explicitly and projects
ACTIVE together with current health rather than using absence or `None` to
conflate states. *(G4, G7, G8, F11, F12, L12, L13)*

**FD-62 — Scope matching is deterministic and repository-relative.**
The effective semantic scope is normalized before Functional Pyramid matching,
then related to the ACTIVE member's declared `FunctionalScope`.

For the selected semantic scope Span computes, without file-tree inference, the
functional intersection and the semantic remainder outside that boundary.

- no functional intersection → `OUTSIDE_FUNCTIONAL_SCOPE`;
- non-empty functional intersection fully covered by applicable contexts and no
  outside remainder → `COVERED`;
- non-empty functional intersection wholly uncovered and no outside remainder →
  `UNCOVERED`;
- a broad scope containing more than one outside/covered/uncovered portion →
  `MIXED`.

The existing canonical semantic owner determines granularity:
`SurfaceKey.kind=FILE|SYMBOL` makes that owner exact, while
`SERVICE|DOMAIN` uses the selected `EvidenceScope` as declared broad boundary
membership. The resolver therefore receives the existing `SurfaceKey` together
with the fixed `EvidenceScope`; it never infers file-versus-directory meaning
from an arbitrary locator string. For SERVICE/DOMAIN, the existing canonical
semantic-containment rule remains authoritative for each `EvidenceScope.paths`
member: a structural symbol locator already classified by
`containment.surface_file_locator` is an exact SYMBOL member, while an ordinary
path member remains a broad path-prefix member. A cold declared-surface obtain
uses both `SurfaceBoundary.paths` and `SurfaceBoundary.symbols` as those same
semantic members; an empty declared boundary is not silently widened to a
repository-wide selection. An exact file/symbol scope is matched directly. A
declared broad surface or repository-wide scope resolves every Functional
Context whose declared coverage intersects the functional intersection,
including contexts narrower than the semantic scope boundary. No context is made
applicable merely because it lies in the same repository.

The one Layer-4 `FunctionalScope` selector grammar used by both Functional
Contexts and member coverage must make membership, intersection, containment and
set-difference deterministically decidable. If a declared selector cannot be
evaluated against the semantic scope, resolution reports
`UNRESOLVED_SCOPE_INTERSECTION`; it does not assume non-applicability.
Absolute paths, traversal outside the repository and ambiguous repository
identity are rejected. Semantic classification, model judgment, file-name
heuristics and structural proximity never participate. *(G1, G4, F11, F12,
L12–L13)*

**FD-63 — Every applicable context composes.**
A semantic scope resolves to all directly applicable functional contexts under
FD-62. Applicability is additive: a narrower or more specific context adds
obligations and never suppresses a broader context. Several contexts applying to
one exact path or broad scope is normal and is not an `AmbiguousSurface`. One
functional context may cover several disconnected paths. *(G4, G7, F11)*

**FD-64 — Context inheritance is many-to-many and additive.**
A context may inherit zero or more declared contexts. Resolution expands every
reachable inherited context to a fixed point and unions its rule references.
Inheritance expresses applicability composition, not authority precedence.
A context may not silently override another context. *(F11)*

**FD-65 — Context identity has one declaration owner.**
A context ID names one canonical declaration within the resolved repository
set. Two non-identical owners for one context ID are unresolved duplicate
ownership, not merge candidates. An unknown inherited context is unresolved.
A context-inheritance cycle is unresolved and every route that depends on the
cycle carries that limitation. *(G1, F11)*

**FD-66 — Functional rules have stable identity and one canonical owner.**
A functional rule has a stable rule ID, one declared layer, one canonical
authority binding and zero or more direct governing rule IDs. The substantive
rule text remains at that authority source. Span retains references, identity
and support; it never copies the rule text into a competing rule owner.
*(G6, F1, F11)*

**FD-67 — The layer relation is fixed and validated.**
The Functional Pyramid layers are `P0`, `P1`, `P2S`, `P2W`, `P3` and
`P4`. For governing derivation, the contract layer has two ordered
sublayers: `P2S` precedes `P2W`.

- P0 rules have `ROOT`, not a governing rule.
- P1 rules are governed by applicable P0 rules. A missing or undecided parent is
  `UNRESOLVED_RULE_PARENT`; an unresolved relationship is not a valid accepted
  governing edge.
- P2S rules identify applicable higher goals/invariants. A P2S rule cannot
  derive from a P2W rule.
- P2W rules identify the applicable contract-layer obligations they realize. A
  P2W rule may explicitly identify a P2S rule as a direct governing rule.
- Applicability never creates that P2W-to-P2S relationship. It exists only when
  the P2W declaration names the P2S rule in its direct governing-rule IDs.
- A governing edge within P2S or within P2W is invalid.
- P3 rules identify the applicable contracts/invariants they realize.
- P4 rules identify the applicable behavior or contracts they realize.
- A direct governing edge may skip an absent intermediate layer.
- Other same-layer edges and edges from a higher layer to a lower governing
  parent are invalid derivation edges.

A valid edge establishes derivation only. It does not prove that the semantic
rule text is correct. *(G7, G8, F5, F11, F12)*

**FD-68 — Route resolution follows declarations to closure.**
For each selected semantic-scope portion Span:

1. computes its FD-62 relation to the member FunctionalScope; an
   `OUTSIDE_FUNCTIONAL_SCOPE` portion is a resolved empty governing branch and
   never becomes `UNCOVERED_PATH`;
2. for each non-empty functional portion, finds every directly applicable
   context by deterministic intersection; a functional portion with no applicable
   context is `UNCOVERED_PATH`;
3. expands context inheritance;
4. collects every rule referenced by those contexts;
5. resolves each rule's canonical owner;
6. walks every direct governing-rule edge to `ROOT` or a typed structural
   unresolved terminal; authority status/content currency is evaluated
   separately by FD-12 and never changes graph topology;
7. deduplicates by stable identity while preserving every provenance path and
   the outside/covered/uncovered classification of the originating semantic
   portion.

No step selects a preferred route when several valid routes apply. *(G1, G7,
F11, L12)*

**FD-69 — Multi-path and broad-scope resolution preserve provenance.**
When a semantic scope contains several explicit paths, Span resolves each path
or path boundary under FD-62, unions identical contexts and rules for
presentation, and preserves the scope-path-to-context-to-rule provenance for
each input. A repository-wide scope is represented as that semantic scope, not
as an invented list of files. Broad scopes preserve the deterministic
FunctionalScope set relation: outside portions remain visible as outside,
covered functional portions retain their context/rule provenance, and uncovered
functional portions retain `UNCOVERED_PATH`. A rule shared by several scope
members appears once in the rule set but remains traceable from every applicable
member.
*(G4, F11)*

**FD-70 — Cross-repository references are explicit.**
Every declaration edge to a context or rule carries the target registered
`repository_id` together with the stable context/rule identity; local edges use
the same qualified form rather than a second shorthand. Context and rule
references may cross repositories only between members of the same Functional
Pyramid instance. Registration outside the instance is not sufficient. This
qualified identity is what makes failure classification deterministic: if the
named target repository is a member but unavailable, the relationship is
`REPOSITORY_UNAVAILABLE`; if that member is available but the named context/rule
does not exist there, it is `UNKNOWN_CONTEXT` or `UNKNOWN_RULE`. A reference
to a repository outside the instance is invalid declaration state. Those states
are not conflated and none is repaired by searching for similar content or by
binding to another registered repository. *(G1, G7, G8, F11, F12, L13)*

**FD-71 — Unresolved route states are typed and preserved.**
The Version-1 Beta unresolved-reason vocabulary is closed:

- `UNCOVERED_PATH`;
- `INVALID_DECLARATION`;
- `UNRESOLVED_SCOPE_INTERSECTION`;
- `DUPLICATE_CONTEXT_OWNER`;
- `UNKNOWN_CONTEXT`;
- `CONTEXT_CYCLE`;
- `REPOSITORY_UNAVAILABLE`;
- `DUPLICATE_RULE_OWNER`;
- `UNKNOWN_RULE`;
- `RULE_CYCLE`;
- `INVALID_GOVERNING_EDGE`;
- `UNRESOLVED_RULE_PARENT`.

Resolvable branches remain visible when another branch is unresolved, but the
route reports its unresolved state completely. No unresolved branch is dropped
to manufacture a complete route. A new unresolved reason requires an amendment
to this functional design rather than an implementation-local string or fallback.
*(G1, A7, F11, L12)*

**FD-72 — Route ordering and provenance are deterministic.**
Paths retain request order after normalization. Direct contexts precede inherited
contexts and use declared stable ordering within each class. Rules are presented
in the fixed layer order `P0`, `P1`, `P2S`, `P2W`, `P3`, `P4` and
then stable rule identity. This presentation order does not classify governing
edges; FD-67 alone determines edge admissibility. Provenance edges use stable
identities. The same repository state and semantic scope produce the same route
ordering. *(A2, F11)*

**FD-73 — Route identity tracks applicability, not rule prose.**
A route-support identity changes when its normalized scope, directly matched
contexts, inherited-context closure, applicable rule membership, rule ownership,
declared layer, governing-rule edges or the member/repository bindings that
materially determine that resolved route change. An unrelated pyramid-member
revision that leaves the complete route closure identical does not invalidate the
route merely because the instance version changed. Canonical rule content and
status are evaluated through the rule's authority support, not duplicated into
route identity. This separation allows Span to state whether *what applies*
changed independently from whether *an applicable authority itself* changed.
*(F1, F11, F12)*

**FD-74 — Canonical rule content is never projected as a second authority.**
The Functional Pyramid view may return stable rule IDs, layer, exact canonical
owner reference/anchor, status, governing IDs, downstream declared dependencies
when relevant to the selected owner scope, and provenance. It does not copy,
summarize, chunk, embed or cache canonical rule prose as a competing semantic
document. When the investigator needs substantive source content, ordinary
evidence admission reads the canonical owner. *(G6, F1, F11, L11, L12)*

**FD-75 — Normative support is server-derived from the complete route.**
When a new or revised conclusion has `assertion_nature=NORMATIVE` and its
repository is ACTIVE, Span resolves the complete effective semantic scope
under FD-68–FD-70 before acceptance. Span adds:

- one route-support dependency for that resolved applicability graph; and
- authority-support dependencies for every applicable functional rule.

For a semantic scope wholly `OUTSIDE_FUNCTIONAL_SCOPE`, the derived route is
the resolved empty applicability route and no Functional Pyramid authority
dependency is invented. Otherwise the caller cannot omit, replace, narrow or
mark derived dependencies current. If any applicable functional route branch is
unresolved or an applicable authority is not currently supportable, the normative
conclusion is not currently supportable.
Additional explicit support may be supplied but cannot substitute for the
server-derived governance dependencies. *(G1, G3, F2, F7, F11, L12)*

**FD-76 — Descriptive understanding and governing orientation remain distinct.**
A descriptive conclusion does not automatically depend on the Functional
Pyramid merely because its path has a governing route. The route is still
returned for orientation. Explicit authority support remains permitted when a
descriptive conclusion genuinely depends on authority. Source currency cannot
make authority current, and accepted authority cannot establish observed
implementation behavior. *(F1, F5, F11)*

**FD-77 — Conformance is a supported normative judgment, not a generated verdict.**
Span never computes semantic conformance from rule text and source topology. A
human or agent authors the conformance judgment after investigation and records
it as a NORMATIVE conclusion; the public assertion-nature contract has no third
CONFORMANCE value. Span can then establish that the judgment's empirical
dependencies, governing route and applicable authorities are current. *(G7, F1,
F5, L12)*

**FD-78 — Functional Pyramid orientation is available on cold surfaces.**
An unassessed semantic surface may return `Gap/unassessed` while its Functional
Pyramid view is fully resolved. Conversely, descriptive understanding may remain
usable while the Functional Pyramid view contains unresolved governance. The two
states are composed but never collapsed. *(G1, G4, G7, L3, L12)*

**FD-79 — Governance changes are support changes.**
A change to an ACTIVE context declaration, rule declaration, canonical authority
identity/content/status, governing edge, member availability or active pyramid
membership causes affected route and authority dependencies to be re-evaluated.
The change root may be a repository changed-scope evaluated through
`reconsider` or an accepted Functional Pyramid ACTIVATE/REVISE/DEACTIVATE
write; both feed the same dependency-effect computation.

The affected walk crosses repository boundaries inside the relevant Functional
Pyramid instance. In addition to conclusions that already carry route support,
activation must include every current NORMATIVE conclusion in a repository that
becomes ACTIVE when that revision predates required server-derived route support:
the new governance obligation is a definite applicability change and the
revision becomes `REASSESSMENT_REQUIRED` until re-established with current
derived support. A normative conclusion may therefore become
`REASSESSMENT_REQUIRED` or `UNVERIFIABLE` without any implementation source
change and without living in the repository where the governance change occurred.
*(G3, F2, F4, F11, F12, L10, L12, L14–L16)*

**FD-80 — Functional Pyramid resolution never originates missing governance.**
No resolver path may invent a context, rule, goal, governing edge, exception,
owner, precedence or repository mapping to complete a graph. The unresolved
relationship is the result until an owning declaration changes. *(G1, G7, F5,
F11)*

**FD-82 — Functional Pyramid instance identity and membership are explicit and
versioned.**
First activation derives one stable pyramid identity and version 1 from an
accepted activation; the caller does not manufacture that identity. A revision
names the existing identity and expected version and atomically replaces the
complete member intent. Every member names one registered repository, its exact repository-owned
declaration source requests, one explicit `FunctionalScope`, and its declared
`PARTIAL | COMPLETE` coverage. A repository may belong to at most one ACTIVE
Functional Pyramid instance at a time so ordinary repository-scoped `ask` has
one unambiguous governing instance. *(G8, A3, F12, L13, L14)*

**FD-83 — Participation transitions and active health have separate
deterministic owners.**
Durable participation follows lifecycle §7.1 and changes only through accepted
Functional Pyramid record actions. No source, filesystem, installer, model,
`ask`, `reconsider` or hook event performs a hidden participation write.

For an ACTIVE instance, live health is computed from current structural state:

- `VALID` iff there is no current structural finding for required member
  availability, declaration-source validity, context/rule identity ownership,
  context/rule cycles, governing-edge legality, cross-member resolution, or a
  COMPLETE member's FunctionalScope coverage;
- `DEGRADED` iff at least one such structural finding exists.

`FunctionalPyramidStatus.findings` is exactly the current set that causes
DEGRADED health. Authority content/status currency, expected PARTIAL uncovered
scope and semantic conclusion support do not degrade graph health. The same
ACTIVE version may therefore move VALID ↔ DEGRADED as current source/member
state changes without a participation write. *(G1, G8, F11, F12, L13–L14)*

**FD-84 — Candidate validation is pure, action-aware,
deterministic and complete.**
For one candidate and present repository state, validation returns the same
ordered findings and changes nothing. ACTIVATE validates the complete proposed
member set. REVISE additionally resolves the target pyramid, expected version,
current membership and removals before validating the replacement member set.

Validation has two distinct finding sets.

1. Candidate/lifecycle findings use exactly:
   `UNREGISTERED_MEMBER`, `DUPLICATE_MEMBER`,
   `MEMBER_ALREADY_ACTIVE`, `UNKNOWN_PYRAMID`,
   `STALE_PYRAMID_VERSION`, `MISSING_DECLARATION_SOURCE`,
   `INVALID_DECLARATION_SOURCE`, `INVALID_FUNCTIONAL_SCOPE`, and
   `INCOMPLETE_COMPLETE_COVERAGE`.
2. Graph findings use FD-71's closed vocabulary for declaration/context/rule
   defects.

`activation_ready` is true only when both finding sets contain no blocker.
Authority content/status currency is not structural candidate validity and never
blocks activation by itself. Validation reads only explicit declaration sources
and stable references reached from them; it does not scan for semantically
similar authority or repair a missing declaration. Each declaration source is
one complete declaration document. A ranged/partial source selection cannot
establish that document's complete declaration set and therefore produces
`INVALID_DECLARATION_SOURCE`; candidate validation never treats a fragment as
the whole declaration. *(G1, G8, A2, A3, F11, F12, L14)*

**FD-85 — Activation and revision revalidate current source and commit
atomically.**
A Functional Pyramid write never trusts a previous candidate-validation result.
It re-runs the corresponding FD-84 ACTIVATE/REVISE validation against current
source, derives the candidate graph identity/findings, and commits only when
`activation_ready=true`. Rejection commits no participation/version change.

Functional Pyramid writes use their own installation-level recording namespace:
the caller's `request_id` is the replay/conflict key in that namespace and the
accepted result returns `FunctionalPyramidReceiptSelector{request_id}`.
Historical retrieval returns `RetrievedFunctionalPyramidReceipt` with the exact
accepted action, resulting member set and
`FunctionalPyramidParticipationEffect` set. No member repository is selected
as an artificial recording/receipt owner. Same
request identity + same canonical write content is replay; same identity +
different content is conflict. Ordinary repository-scoped receipts remain
unchanged.

Before ACTIVATE/REVISE/DEACTIVATE commits, Span computes the deterministic
participation changes and FD-79 semantic dependent effects against the same
transaction decision. The immutable receipt retains the durable participation
and dependent-effect coordinates; the public result projects them through the
same `ChangedSurface`/affected-conclusion carriers used by `reconsider`.
Exactly one repository-bound live re-establishment context is issued for each
repository with an actionable effect. The immutable receipt/effect set is the
accepted `ConclusionRevisionRef` identity set, not a frozen live
`ChangedSurface` status snapshot. On replay, Span keeps those immutable effect
identities unchanged, re-evaluates only those retained revisions against current
support/membership state, returns the current actionable `ChangedSurface`
projection, and issues fresh contexts only for effects that are actionable now.
It never discovers additional accepted effects from later governance state.

Activation/revision stores only the identities, relationships, source identities,
functional scopes and coverage needed to reproduce resolution; canonical
governing prose is never stored as pyramid content. Revision/deactivation remain
compare-and-set on the target pyramid version, and activation/revision atomically
enforce one ACTIVE pyramid per repository. *(G3, G6, G8, A2, A3, F1, F4, F12,
L4, L14–L15)*

**FD-86 — Coverage is evaluated against the declared functional
scope, never repository inventory.**
Every member supplies one `FunctionalScope` under the same FD-62 selector
grammar as Functional Context coverage.

- `PARTIAL` declares incomplete context coverage inside that scope. A selected
  member scope inside the functional boundary with no applicable context returns
  `UNCOVERED_PATH`, but that expected incompleteness does not by itself make
  live pyramid health DEGRADED.
- `COMPLETE` asserts that the union of declared applicable Functional Context
  selectors covers the entire member `FunctionalScope`. Candidate validation
  proves this using deterministic containment/set-difference; any remainder is
  `INCOMPLETE_COMPLETE_COVERAGE` and is not activatable.
- After activation, if current declarations change so any part of a COMPLETE
  member's declared functional scope becomes uncovered, affected route
  resolution reports `UNCOVERED_PATH` and live health is DEGRADED until the
  declarations or coverage claim are corrected.

Repository paths outside the declared `FunctionalScope` are not made
functional merely because they exist, do not participate in COMPLETE coverage
proof, and do not return `UNCOVERED_PATH`. A semantic scope wholly outside the
boundary is `OUTSIDE_FUNCTIONAL_SCOPE` with a resolved empty governing
projection. A broad scope crossing the boundary is classified `MIXED` and
preserves outside/covered/uncovered provenance under FD-62/FD-69. *(G1, G4, G8, F11, F12, L13)*

**FD-87 — Membership is resolution reachability, never applicability.**
Adding a repository to an instance makes its stable declared identities
resolvable from other members. It adds no context/rule to another repository's
route unless explicit context inheritance, rule membership or governing
relationships make it applicable. Removing or losing a member preserves the
external identity in affected routes as unresolved; it never silently drops the
relationship. *(G1, G7, G8, F11, F12, L13)*

**FD-88 — Governing traversal is bidirectional over one declared graph.**
Upward orientation follows scope → context → rule → governing rule to ROOT under
FD-68. For a selected canonical rule-owner scope, Span derives the reverse view
from those same declaration edges: direct/transitive dependent rules and the
declared contexts that reference them. Reverse traversal is navigation/impact
orientation only; it does not predict what a proposed edit will do and never
creates a second dependency registry. *(G3, G7, F4, F11, L15, L16)*

**FD-89 — Cross-repository change propagation uses one dependency engine.**
Repository changed-scope and accepted Functional Pyramid participation changes
are two roots into the same FD-88/route-support dependency traversal. A
repository changed-scope starts from the changed repository. A Functional
Pyramid write starts from its old/new member/binding/route delta. Both traverse
every reachable dependent inside the relevant instance and then premise closure.

Affected semantic surfaces remain owned by their own repositories. The canonical
affected projection retains repository-qualified surface identities and exactly
one repository-bound `InvestigationContextRef` for each repository that owns
actionable affected conclusions. `reconsider` returns it as `Changed`;
`FunctionalPyramidRecorded` reuses the same affected carriers. No context spans
repositories and callers never enumerate dependent repository IDs. *(G3, F4,
F12, L10, L14–L15)*

**FD-90 — The governing projection uses the same effective semantic scope.**
For ordinary semantic obtain, Functional Pyramid applicability is resolved from
the exact effective semantic scope already selected for the Answer/Gap. Question
text, embeddings, similarity, document genre and source prominence never expand
that scope or select governing documents. The view returns references to every
declared rule applicable through that scope, regardless of which document genre
owns each rule. *(G4, G6, G7, F9, F11, L12, L16)*

**FD-91 — Participation, health, route and support state remain independent.**
An ACTIVE/PARTIAL instance can return an `UNCOVERED_PATH` route while its live
health remains VALID. An ACTIVE pyramid with DEGRADED health can still return
RESOLVED routes for unaffected scopes. A structurally RESOLVED route can still
yield non-current normative support because an applicable authority is draft,
superseded, unavailable or changed under FD-12. Durable participation, live
pyramid health, per-scope route resolution and conclusion support are never used
as shortcuts for one another. *(G1, F1, F2, F12, L13, L16)*

**FD-92 — Functional Pyramid lifecycle projections never become semantic
understanding.**
Status, candidate validation and receipt retrieval are lifecycle projections over
declared/persisted pyramid state. They never create an Answer, conclusion,
investigation context, rule meaning or authority. Ordinary semantic obtain
composes its existing Answer/Gap membership with the governing projection for
the same semantic scope without allowing either plane to manufacture the other.
*(F1, F5, F6, F11, F12, L8, L12–L14)*

**FD-93 — Functional Pyramid writes derive all mechanical state and effects.**
For the Layer-2 Functional Pyramid record branch, the caller supplies only the
declared lifecycle intent. Span derives pyramid identity/version, validation,
source identities, participation effects, semantic dependent effects and
re-establishment contexts through FD-84/FD-85/FD-89. The write never creates a
second semantic writer, route carrier or dependency-effect representation.
*(G3, G8, F6, F7, F12, L4, L8, L14–L15)*

**FD-94 — Lifecycle notices compose Functional Pyramid obligations without
becoming governance.**
At session start/resume/compact, canonical participation and live health select
only the Functional Pyramid obligation: UNCONFIGURED directs governed use to the
initialization/status path; EXCLUDED has no initialization obligation and
ordinary descriptive semantic work remains available; ACTIVE/VALID adds no
separate Pyramid action beyond ordinary governed orientation; ACTIVE/DEGRADED
reports governance attention and the next existing lifecycle action.
ACTIVE/DEGRADED means ACTIVE participation with DEGRADED live health, not a
fourth participation state.

For an external edit/write, the same canonical changed-scope projection decides
semantic, authority, route, premise, containment and cross-repository effects;
the hook does not first classify the edit as semantic versus governance work.
The resulting obligation may therefore be semantic-only, Functional-Pyramid-
related only, both, or neither while still routing through the existing public
lifecycle. An accepted Functional Pyramid activate/revise/deactivate write is
different: its `FunctionalPyramidRecorded` result already owns the canonical
dependent effects and re-establishment contexts, so a hook does not recompute
those effects or require a second `reconsider` for that write.

Hooks never activate/revise a pyramid, author rule meaning, copy rule content,
create authority, or make support current. *(G8, A4, A9, F5–F6, F10, F12,
L13–L16)*

## 5. Support evaluation

**FD-9 — Five dependency kinds.**
Support is a source observation, a discovery boundary, an authority binding, a
Functional Pyramid route, or a conclusion revision (premise). Caller-declared
support may use the first, second, third and fifth forms; route support is
server-derived under FD-75. Nothing else counts as support. *(F1, F2, F7, F11)*

**FD-10 — Source dependency.**
Compare the recorded content identity with the present identity of the declared
locator. Missing or unreadable source → `UNVERIFIABLE`. Different identity →
`REASSESSMENT_REQUIRED`. Equal identity → `CURRENT`. *(F2)*

**FD-11 — Discovery dependency.**
Recompute the membership fingerprint of the declared boundary. Changed
membership → `REASSESSMENT_REQUIRED`. Membership that cannot be observed →
`UNVERIFIABLE`. *(F2, F4)*

**FD-12 — Authority dependency.**
Resolve the exact declared authority binding. Missing authority is
`UNVERIFIABLE`; `SUPERSEDED` is `REASSESSMENT_REQUIRED`; draft, declared
but unaccepted, or unknown authority is `UNVERIFIABLE`. Changed identity,
kind, applicability or content identity is `REASSESSMENT_REQUIRED`. Only the
same accepted binding with current canonical source content is `CURRENT`.
Authority currency never establishes the semantic truth of the governing rule.
*(F1, F2)*

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
not established (F1, A6). See §14. *(F2, A7)*

**FD-16 — Reasons are complete.**
The combined evaluation lists every non-current dependency with its state and
reason, so a definite finding is not lost inside an `UNVERIFIABLE` summary.
*(F2, A8)*

**FD-81 — Route dependency.**
Re-resolve the exact semantic scope through FD-61–FD-73 and the current
Functional Pyramid instance bindings under FD-82–FD-91. If the revision recorded route support while its repository was ACTIVE and the
repository is now UNCONFIGURED/EXCLUDED or has been removed from that instance,
the governing applicability definitely changed and support is
`REASSESSMENT_REQUIRED`; this is not operational unavailability. If the
repository remains ACTIVE but evaluation of the required route/member/declaration
state is operationally impossible, support is `UNVERIFIABLE`. If its complete
route-support identity differs from the recorded identity, support is
`REASSESSMENT_REQUIRED`. If that route contains an unresolved functional
branch, support is `UNVERIFIABLE`. Only the same complete resolved route is
`CURRENT`.
DEGRADED live health does not by itself invalidate an unrelated scope whose
route still resolves identically. Applicable authority content/status is checked
separately by FD-12. *(F2, F11, F12, L13, L15)*

## 6. Change propagation

**FD-17 — Paths map to surfaces in both directions.**
A changed path maps to its path surface and to every declared surface whose
boundary contains it. *(F4, L10)*

**FD-18 — Direct support loss.**
A conclusion loses support directly when a changed path affects any declared or
server-derived dependency: a source dependency on that path, a discovery
dependency whose membership contains it, an authority binding whose canonical
source changed, or a Functional Pyramid route whose declaration/authority/member
graph may be affected. Route and authority dependencies are re-evaluated by
their own owners; a path match alone is never a stale verdict. Functional
Pyramid dependency lookup uses FD-89 and therefore may find a direct normative
dependent in another repository of the same instance. Where a reliable declared
source range exists, evaluate that range; otherwise evaluate the whole file. A
range that cannot be reliably bound falls back to the whole file rather than to
a narrower claim. Support evaluation re-reads the current source; the
observation stores the content hash and ranges, not the source bytes. *(F2, F4,
F12, L15)*

**FD-19 — Indirect support loss.**
After direct loss, walk premise chains to a fixed point. A conclusion whose
premise is `REASSESSMENT_REQUIRED` becomes `REASSESSMENT_REQUIRED`; if the
premise is withdrawn, absent, or cannot be checked, the conclusion is
`UNVERIFIABLE`, and FD-15 governs the combined state. *(F4)*

**FD-20 — Inclusion is complete.**
The result includes every surface that must be re-examined or repaired: by
containment, by direct source/discovery/authority/route support loss, or by
indirect loss — including a surface whose boundary excludes the changed path and
a surface owned by another member repository reached through FD-89. Entries are
deduplicated by repository + surface identity and carry the set of reasons that
apply. Inclusion is not a verdict:
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

## 7. Response composition

**FD-23 — The Answer/Gap threshold is defined.**
`ask` returns `Answer` when at least one matched conclusion is both
`CURRENT` and `CURATED`. Functional Pyramid orientation does not itself turn
a semantic Gap into an Answer and an unresolved pyramid does not by itself
discard an otherwise eligible descriptive conclusion. It returns `Gap` when
no matched conclusion is eligible for shared reuse. `Answer` contains only
CURRENT + CURATED conclusions; current CAPTURED and non-current conclusions
appear as references/status, never as answer content. One eligible conclusion is
not withheld because a sibling is pending curation or stale. See §14.
*(F2, F13, L2, L17)*

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
An `Answer` may therefore contain CURRENT + CURATED conclusions while the
surface status reports pending, stale and unassessed items, and while recorded
gaps are returned. The agent can act on the reusable part and see exactly what
is missing. *(A9, F13, L3)*

**FD-25 — Gap reasons are exhaustive.**
For surface/current-identity/exact-recorded-question membership selected under
lifecycle §4.1, no Answer-eligible conclusion yields one reason from current
membership. If at least one matched revision is CURRENT but CAPTURED, the reason
is `pending_curation`. Otherwise REASSESSMENT_REQUIRED becomes
`invalidated`, UNVERIFIABLE becomes `unverifiable`, and no retained usable
understanding becomes `unassessed`. The ordinary free `question` lookup
branch and its `no_match` production path are retired.
`RecordedQuestionSelector` performs exact equality only within its supplied
surface. An empty matched set for the exact question maps to `unassessed`;
matched membership with lost support still follows the ordinary
`invalidated`/`unverifiable` mapping. The selector does not reintroduce
natural-language or similarity matching. Stored question metadata/history is not
rewritten. An unknown exact identity is a lookup rejection, not a newly invented
Gap. Context binding/admission failures never become semantic absence.
*(F2–F4, F13, A8, L3, L17)*

**FD-26 — Ambiguity is a separate result.**
When a surface reference resolves to more than one granularity, the result is
`AmbiguousSurface` with the candidates and the missing decision. It is never a
`Gap` reason and never an arbitrary choice. *(F9, L2)*

**FD-27 — Operational failure is not an empty answer.**
A failure that prevents the lifecycle operation itself from evaluating —
unavailable store, required provider error, schema version — returns
`Unavailable` with the recovery. If semantic answer composition succeeds but
Functional Pyramid orientation for an ACTIVE member, including one whose live health is DEGRADED, fails operationally,
the Answer/Gap carries `FunctionalPyramidUnavailable`; it does not erase otherwise valid descriptive
understanding. Normative conclusions whose route support cannot be evaluated
remain non-current through FD-81. An unreadable source is not
`Unavailable`; it is `UNVERIFIABLE` support. *(A8, L3)*

Expected operational failures are classified at their typed owner and projected
into the public vocabulary fixed by lifecycle §4. Raw exception messages,
tracebacks, filesystem/store details, runtime carrier/module names, internal
keys/digests/origins and administrative state never cross the agent boundary.
Unexpected defects remain defects: transport containment may return a stable
generic tool failure while retaining diagnostics internally, but it never turns
the defect into a semantic Gap or an actionable Rejected result. *(A8, L3, L7)*

Context-issuance conflicts propagate as typed rejection; expected store/provider
access failures propagate as Unavailable. A catch-all conversion to Gap is
forbidden. Missing/invalid references identify the bound repository/context and
public corrective action; absence alone does not establish expiry or reaping.
Stateful validation stays with its canonical owner. *(FD-39, FD-41, L3, L5)*

**FD-28 — The surface document view is assembled, never stored.**
The semantic surface view is composed on read from CURRENT + CURATED
conclusions; no stored copy exists. This assembled explanatory view is distinct from canonical governing
documents. Functional Pyramid rules remain at their canonical owners and are
referenced by the accompanying pyramid view rather than copied into the surface
document view. Its contents are fixed in `lifecycle-contract` §4.1.
*(G6, F11, L11, L12)*

Pure surface obtain groups all Answer-eligible membership by recorded question
metadata and reports current CAPTURED membership separately as pending
curation.
`RecordedQuestionSelector` restricts membership to one exact recorded question
on one exact surface; current identity selectors restrict membership to one
returned understanding identity. All three reuse forms use the same composition,
issue no context and require no request identity. Their role as the reuse paths
is stated in `lifecycle-contract` §4.1. *(G2, F3, A4, L11)*

**FD-29 — Result ordering is stable.**
The selected surface and Functional Pyramid participation/orientation precede semantic content
in the canonical projection; current conclusions are grouped by question, then
status, gaps, verification and references. Functional Pyramid internal ordering
follows FD-72. The same request against the same state produces the same order.
*(A2, L12)*

## 8. State transitions

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
`DESCRIPTIVE`; the basis records explicit evidence from the cited source. For
`NORMATIVE` content in an ACTIVE Functional Pyramid repository, route and authority support
are derived under FD-75 after semantic scope is fixed and before acceptance.
*(F5, F7, F11, L2, L12)*

**FD-31 — confirm.** A re-establishment action: accepted only after present
support has been checked, and only for a version whose recorded support was not
current. If the version is already current and unchanged, the operation returns
the current version rather than creating a new one. Unchanged wording alone is
never a confirmation. A confirm names the conclusion and the reassessed
evidence; Span preserves the current statement, assertion nature, and scope,
re-derives required Functional Pyramid support when normative, and derives a
non-empty mechanical basis. When the predecessor revision is CURATED, the
confirmed revision inherits that curation because confirm is semantically
identity-preserving; a CAPTURED predecessor remains CAPTURED.
*(F2, F13, A6, F8, F11, L4, L17)*

**FD-32 — correct.** A conclusion's content changes and a new revision is
created. Dependents on the previous revision become `REASSESSMENT_REQUIRED`.
The corrected statement and its caller-supplied support are explicit; an
omitted assertion nature or scope is preserved from the current revision, Span
derives any required normative route/authority support, and Span derives the
content basis. *(F4, F7, F11)*

**FD-33 — replace.** A conclusion is superseded by another. Dependents on the
superseded revision become `REASSESSMENT_REQUIRED`. Replacement never retargets
another conclusion's premises silently. The action identifies the current
lineage being replaced. The replacement lineage identity follows L7. Span
derives the exact current old revision, preserves an omitted assertion nature
or scope for the new conclusion, derives any required normative
route/authority support, uses the supplied reason as the replacement basis, and
derives the new content basis. *(F4, F7, F11)*

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

**FD-37 — Premise and challenge effects are derived and reported, not applied silently.**
Any transition that invalidates a premise must name the affected dependents in
the same result. *(F4, L10)*

For a resolved challenge disposition, Span resolves each semantic target against
the resulting version after the update actions have been applied. An omitted
target set uses the challenge's target conclusion lineages. A supplied target
must either identify a lineage in the resulting membership or identify the old
lineage of exactly one `replace` action in the same command, in which case the
replacement action's server-derived lineage is the target. Duplicate or
ambiguous mappings reject the write. The selected resulting revision is derived
from the resulting membership: a withdrawal revision is recorded in the
resolution's `withdrawn` set and any supported revision in its `conclusions`
set. The resolution's resulting understanding/version are the same atomic
transition's coordinates. Disposition evidence references are resolved only
through the recording context. No caller-provided resulting version or revision
participates in this procedure. *(F5, F7, L4, L7)*

## 9. Failure taxonomy

**FD-38 — Closed unions.**
`ask`, `record`, and `reconsider` each return exactly the results declared in
`lifecycle-contract` §4.1–§4.3. There are no optional public operations in the
current build. No result is invented at runtime and no result crosses
operations. *(L3)*

**FD-39 — Rejection is not replay and not unavailability.**
A replay returns the original acceptance. A rejection returns the offending
identity and the required action. Unavailability returns the operational failure
and recovery. They are never merged. *(A2, A8)*

A rejection carries what `lifecycle-contract` §4.2 fixes. Its public cause and
action are a deterministic function of the typed rejection kind plus structured
public coordinates; neither is derived by parsing or copying exception text.
This design owns only the separation above: a failure that prevents evaluation
is `Unavailable` (FD-27), never a rejection. *(A2, A8)*

**FD-40 — No partial application.** A rejected write commits nothing: no version,
no revision, no challenge disposition, and no consumed context. *(A2, L4)*

**FD-41 — Every rejection is actionable.** The rejection names the exact identity
that failed validation and what must change. Functional Pyramid unresolved
states are not input rejections merely because governance is incomplete: they
are returned in the pyramid view and make required normative route/authority
support non-current. A semantically valid normative create/update with such
derived non-current governance support is retained and returned with
`UNVERIFIABLE` or `REASSESSMENT_REQUIRED` qualification; F2 keeps it out of
CURRENT Answer content. A malformed declaration that violates the accepted declaration
contract is an explicit unresolved/validation condition at its owning boundary,
never silently ignored. Recovery must correct the actual
invariant: original content/new identity for binding conflicts, in-scope evidence
or context-free direct recording for scope conflicts, and the admitting context
or direct evidence for context-bound references. What it carries is fixed in
`lifecycle-contract` §4.2. *(A8)*

## 10. Retention and recovery

**FD-42 — Context expiry removes membership only.** Expiry of a context does not
remove accepted understanding, challenge history, verification runs, or receipts.
*(A1, A2)*

**FD-43 — The replay window is derived, not invented.**
A receipt is retained at least as long as the longest supported session
suspension, so a caller that can resume can recover its identity. That lower
bound follows from A1 and A2 and applies equally to repository-scoped ordinary
receipts and installation-scoped Functional Pyramid receipts. The concrete
window is a deployment measurement recorded in layer 4, not a product choice.
*(A2)*

**FD-44 — History reaping must not silently break premises.**
If retained history is reaped, any premise that referenced a removed revision
becomes `UNVERIFIABLE` and is reported. Reaping never turns a broken premise into
a current one. *(F2, F3)*

Historical normative revisions retain their route-support identity and authority
references. They do not retain copied governing prose. If a referenced repository
or declaration can no longer be evaluated, live qualification becomes
`UNVERIFIABLE` while historical membership remains retrievable. *(G6, F2,
F11)*

**FD-45 — Restart recovery is by identity.**
After a restart, a caller request identity recovers its context if retained and
its receipt if retained. No conversation replay is required. The canonical
context reference binds repository and context identity at issuance.
Context-bound routing derives from that reference with no separate override;
lookup still validates actual liveness and membership. No cross-store search or
context replacement is implicit. Change-scope issuance follows FD-2 and its contexts use the same retention
owner. *(A1, A2, F4, L7, L10)*

## 11. Concurrency

**FD-46 — Updates are compare-and-set.**
An update names the expected version. A mismatch rejects the write and reports
the current version. *(A3, L4)*

This applies to understanding versions, declared-surface boundary versions and
Functional Pyramid revisions/deactivation. A Functional Pyramid revision or
deactivation names the exact current pyramid version; a stale version rejects
without participation change. Activation has no prior pyramid version, but the
same transaction must enforce that no proposed member is already ACTIVE in
another instance. The surface-conflict and Functional Pyramid write cases are
fixed in `lifecycle-contract` §4.2. *(A3, F12, L4, L13, L14)*

**FD-47 — Same identity, concurrent writers.**
Two writers with the same request identity and content produce one acceptance and
one replay. Same identity with different content produces one acceptance and one
conflict. *(A2, A3)*

**FD-48 — Different identities, same version.**
Exactly one write succeeds; the other is rejected as a version conflict. There is
no last-write-wins and no silent merge. *(A3)*

## 12. Host contract

**FD-49 — The host delivers the advertised schema.**
Span requires the host to expose the declared tool schemas without coercion or
re-encoding that changes their meaning. Any required union discriminator has an
explicit public protocol value independent of runtime class/type names; renaming
an internal carrier cannot silently change the wire contract. Structurally
unambiguous branches need no discriminator merely to expose their implementation
type. *(L8, A9, F10)*

**FD-50 — The host preserves request identity.**
A retry must carry the same request identity if it is the same act. If a host
cannot preserve it, replay safety is not claimed for that host. *(A2, D-3)*

**FD-51 — The host delivers a complete result or states truncation.**
A host that truncates must say so. A truncated result is not a smaller correct
result. *(A8)*

**FD-52 — Answer safety is independent of host notices.**
Support and curation-eligibility checks occur within the operations returning
understanding, regardless of notice delivery. The agent lifecycle remains
required by layer 2 §7. *(A4, F2, F13)*

**FD-53 — Live delivery is unverified until captured.**
A host contract is established only by a recorded capture observed or failed.
*(A8)*

The Version-1 host contract still exposes exactly `ask`, `record` and
`reconsider`. Functional Pyramid orientation is verified as part of those
result schemas; no host is accepted on evidence from a separate authority tool
because no such public operation exists. *(F6, L8, L12)*

**FD-58 — Lifecycle notices interrupt omission at host-observable moments.**
A lifecycle notice exists only where host-observable activity can create a
required Span action outside the result of an MCP operation: session
start/resume/compact, a reliable pre-investigation source-access event when the
host exposes one, an external edit/write, or idle/stop/completion with a known
outstanding lifecycle obligation. At each such moment notice selection evaluates
the semantic-understanding obligation and the Functional Pyramid obligation
independently from canonical Span state; either, both, or neither may require
action. That distinction is a deterministic selection rule, not a new public
state, carrier, operation, or hook-owned lifecycle.

The delivered notice names the smallest existing public lifecycle action or
actions that satisfy those obligations. A transition already exposed by an
`ask`, `record`, or `reconsider` result remains owned by that result and is
not rediscovered by a hook. Pre-investigation reminders are permitted only when
the host identifies the source-access moment without semantic guessing; arbitrary
command/string heuristics never manufacture a semantic surface or lifecycle
state.

For external changes, the complete normalized changed scope available from the
host is evaluated through the canonical changed-scope effect projection before
notice presentation is bounded. Multiple observed edits that have not yet been
handed off preserve their union. A host that cannot supply a complete changed
scope must make that incompleteness explicit; a subset is never treated as a
smaller complete change. The resulting notice may report cross-repository
effects but never computes another affected set.

Notices never activate/revise governance, author or curate semantic conclusions,
issue re-establishment contexts, make support current, or certify meaning.
Answer safety remains independent of notice delivery under FD-52. Measure
delivered notice cost under F8 and delivery under FD-53. *(A4, A8–A9, F5–F6,
F10, F12, L8, L12–L16)*

## 13. Bounds and truncation

**FD-54 — Response size is server-owned.**
The agent does not manage response size; the default is set per host and recorded
with the delivered result. The bound applies to delivery, not to binding a
source reference. *(F7)*

**FD-55 — Truncation is explicit and recoverable.**
A truncated result names what was omitted and provides a public way to retrieve
it. The continuation contract is `lifecycle-contract` §4.1. A response is
complete or explicitly truncated. *(A8)*

**FD-56 — Truncation never substitutes stale content.**
A budget limit never promotes historical content into answer content and never
omits the fact that truncation occurred. *(F2, A7)*

**FD-57 — A result too small to be safe is refused.**
If the budget cannot carry the result kind, surface identity, Functional Pyramid
participation/resolution state when applicable, and the fact of truncation, the
operation returns an explicit budget refusal rather than a misleading fragment.
Rule lists or provenance may be continued/omitted only when the result still
states that they are incomplete; unresolved governance is never truncated into
an apparently complete route. *(A7, A8, G1, L12)*

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

### Beta 3 capture and curation

**FD-95 — Answer eligibility composes support and curation.**
For every current semantic revision,
`eligible_for_answer(ref, t)` is true exactly when support is CURRENT and
curation state is CURATED. Support and curation remain independent projections.
*(G2, F2, F13, L17)*

**FD-96 — Semantic creation and change begin captured.**
Create, add, correct and replace produce CAPTURED revisions. No semantic write
may create a curation disposition as a side effect. Withdrawal produces no
reusable semantic content. *(A10, F7, F13, L17)*

**FD-97 — Curation is an immutable exact-revision disposition.**
A curation action resolves each target lineage against the expected current
understanding version, derives the exact revision, requires non-empty reviewer
reasoning, and evaluates the target's required support at acceptance time. Only
a `CURRENT` target may be curated; non-current support is a typed validation
rejection requiring re-establishment first. Acceptance records one immutable
curation disposition per exact revision and advances the understanding version
without creating or changing a semantic conclusion revision. Compare-and-set and
receipt/replay rules remain the existing ones.
*(A2, A3, F2, F5, F13, L4, L17)*

**FD-98 — Semantic change resets curation; semantic-preserving confirmation
preserves it.**
Correct and replace create new CAPTURED revisions; add creates a new CAPTURED
lineage. Confirm inherits curation only from a CURATED predecessor because the
existing confirm transition preserves statement, assertion nature and semantic
scope. Confirm of a CAPTURED predecessor remains CAPTURED.
*(F2, F4, F13, L17)*

**FD-99 — Pending curation is deterministic, not semantic search.**
Pending-curation obtain returns current-membership semantic revisions that both
lack a curation disposition and presently evaluate `CURRENT` under their
required support. CAPTURED non-current revisions remain in the ordinary
stale/re-establishment path until support is restored. Queue order is the
ascending exact key `(understanding_id, conclusion_id, revision)`; an optional
exact `ConclusionRevisionRef` keyset cursor resumes strictly after that key.
Membership and ordering never depend on similarity, inferred importance,
confidence or a model-generated score. Bounds/truncation remain server-owned and
explicit.
*(A6, A8, F2, F13, L17)*

**FD-100 — Curation never alters Functional Pyramid authority.**
Curation never changes participation, health, applicability, route identity or
authority support. CURATED normative content with non-current governing support
is not Answer content, and a resolved governing route cannot make CAPTURED
content reusable. *(F1, F11–F13, L12, L17)*

**FD-101 — Surface composition exposes pending knowledge safely.**
CURRENT + CURATED conclusions form Answer content. CURRENT + CAPTURED revisions
form pending references/status. Any non-current revision, whether CAPTURED or
CURATED, follows the existing historical/stale path and is not simultaneously
counted as pending. If no eligible conclusion exists but pending current capture
exists, the result is `Gap/pending_curation`. Each current semantic revision
therefore belongs to exactly one Answer or pending population.
*(A7, F2, F9, F13, L2, L3, L17)*

**FD-102 — Failed curation review uses the existing semantic lifecycle.**
A reviewer who finds captured meaning wrong, incomplete, duplicated or wrongly
scoped uses challenge, correct, replace or withdraw as appropriate. No
`rejected_curation` semantic state or second writer exists. Only a stable exact
semantic revision can be curated. *(F5, F13, L17)*

## 14. Derivation

Each FD rule cites the higher-layer goal, foundation, or lifecycle law that
justifies it. Those citations are the derivation record.

This layer does not maintain a second prose rationale for the same decisions:
where a rule's justification is unclear, correct its owning requirement or its
citations rather than adding a parallel explanation here.

Non-normative conceptual explanations belong in the public
[concept documentation](README.md#concepts).

## 15. Version 1 Beta functional acceptance

The implementation is not functionally conformant to this design until the
following behaviors are demonstrated against the public lifecycle and pure core
rules. These are behavioral cases, not layer-4 mechanism choices.

1. **Unconfigured versus excluded.** A registered repository starts
   UNCONFIGURED. Explicit exclusion returns EXCLUDED. Neither state invents an
   empty governing route, and descriptive semantic lifecycle remains usable.
2. **Pure action-aware candidate validation.** ACTIVATE validation of a proposed
   multi-repository member/declaration set and REVISE validation of an exact
   pyramid/version replacement return deterministic validation + graph findings,
   change no durable participation state, and set `activation_ready` exactly
   from the closed blocker rules. Governing-edge validation uses the same FD-67
   relation later used by ACTIVE health and ordinary route resolution.
3. **Activation and replay.** A valid activation atomically creates one pyramid
   identity/version and one installation-scoped Functional Pyramid receipt;
   replay is idempotent without choosing a member repository as receipt owner;
   `FunctionalPyramidReceiptSelector` retrieves an exact
   `RetrievedFunctionalPyramidReceipt`; invalid activation leaves every
   repository's prior state unchanged.
4. **Revision and removal.** A compare-and-set revision atomically changes the
   complete member intent; the resulting member set shows retained/added ACTIVE members while canonical
   participation effects contain only actual durable-state changes (for example,
   added members becoming ACTIVE and removed members becoming UNCONFIGURED);
   retained members preserve the pyramid identity with a new version, and a stale expected version is reported
   by candidate validation and rejected at write revalidation.
5. **Partial coverage.** A PARTIAL member is evaluated only within its explicit
   FunctionalScope; uncovered scope inside that boundary returns
   `UNCOVERED_PATH` without degrading live health, and repository paths outside
   the boundary create no coverage obligation.
6. **Complete coverage.** COMPLETE activation is impossible when deterministic
   set-difference leaves any part of the declared FunctionalScope outside the
   union of applicable Functional Context coverage. If a later declaration
   change creates such a remainder, affected routes become uncovered and ACTIVE
   health becomes DEGRADED without a participation/version write.
7. **Degraded-health recovery.** Member/declaration/structural unavailability
   makes ACTIVE health DEGRADED; unaffected routes can still resolve; restoring
   current graph availability/validity returns health to VALID without a
   participation write.
8. **Cold governed path.** `ask(FILE)` on an ACTIVE member returns
   `Gap/unassessed` plus the Functional Pyramid view without generating
   semantic understanding.
9. **Same semantic scope.** The governing view is resolved from the exact
   semantic scope selected for Answer/Gap; natural-language question text,
   embeddings, filename similarity and document genre never expand governing
   applicability.
10. **Overlapping contexts.** One path matching broad platform, workflow and
    boundary contexts returns all of them and the union of their governing
    rules; no most-specific-wins behavior occurs.
11. **Distributed context.** One context covering disconnected paths resolves as
    one context without requiring path ancestry.
12. **Multi-path and broad semantic scope.** Resolution unions context/rule
    membership while preserving per-scope provenance. A directory/service/domain
    scope includes narrower intersecting contexts.
13. **Membership is not applicability.** Adding another repository to the
    pyramid changes no route unless an explicit declared context/rule
    relationship makes that member relevant.
14. **Cross-repository authority.** With the referenced member available, a local
    path resolves external governing rules by stable identity. With that member
    unavailable, the same relationship is `REPOSITORY_UNAVAILABLE`, not
    `UNKNOWN_RULE` and not silently discarded.
15. **Authority graph defects.** Unknown rules, duplicate owners, context cycles,
    rule cycles, invalid governing edges and missing required parents are
    explicit unresolved states. An unresolved parent is never accepted as a
    valid derivation edge. The acceptance surface proves FD-67's permitted
    contract-sublayer derivation and rejects its reverse and same-sublayer
    prohibited cases as `INVALID_GOVERNING_EDGE`.
16. **Route versus authority currency.** A structurally complete route can remain
    RESOLVED while an applicable authority is DRAFT/SUPERSEDED/changed and
    normative support becomes non-current through authority support.
17. **Normative create.** The caller supplies semantic intent and empirical
    evidence; Span derives route and every applicable authority dependency.
    Omitting governance is impossible through the public grammar. If those
    derived governance dependencies are unresolved/non-current but the semantic
    request is otherwise valid, the revision is retained with non-current
    qualification and is not served as CURRENT Answer content.
18. **Descriptive create.** A descriptive conclusion remains source-supported
    without automatically becoming normative merely because a pyramid route
    exists.
19. **Authority-content change.** Changing an applicable canonical rule without
    changing route topology requires reassessment through authority support while
    route identity can remain unchanged.
20. **Applicability change.** Changing context coverage, inheritance, rule
    membership, governing edges or material member bindings requires
    reassessment through route support even when implementation/rule prose are
    unchanged.
21. **Reverse authority navigation.** Asking an exact canonical rule-owner scope
    exposes its declared downstream rule/context dependency graph without
    predicting a proposed edit or copying rule text. For FD-67's permitted
    contract-sublayer derivation, selecting the governing rule's canonical owner
    exposes the declared dependent through that same graph.
22. **Cross-repository reconsideration.** A governing change in repository A
    returns affected normative understanding in repository B when the same
    pyramid graph connects them; the caller does not enumerate B. The Changed
    result returns exactly one repository-bound re-establishment context for A
    and/or B wherever that repository has actionable affected conclusions; no
    cross-repository context is created.
23. **Implementation change.** Existing source/discovery/premise propagation
    remains intact and does not depend on the Functional Pyramid being the cause.
24. **Mixed answer.** A current descriptive conclusion can be returned while its
    pyramid route is unresolved; a normative conclusion depending on that route
    cannot be returned CURRENT.
25. **Canonical-source singularity.** Pyramid state/view/storage returns rule
    identities, owner anchors and relationships but no copied summaries, chunks
    or canonical rule prose.
26. **Runtime lifecycle preservation.** Every existing Span runtime path in
    lifecycle §7.2 remains exercisable with its pre-Version-1 semantic behavior:
    current reuse without duplicate record, gap → investigate → conclude/record,
    external edit → reconsider → investigate when needed → re-establish,
    dispute → disposition, start/resume and completion. Functional Pyramid behavior is additive at those
    same moments and introduces no second ordinary-development lifecycle.
27. **Governance-source edit lifecycle.** Before editing a canonical rule owner,
    the current downstream graph is obtainable; after the edit, reconsider
    reports cross-repository authority/route effects and record closes the
    affected dispositions.
28. **Lifecycle-compliance hooks.** Session start/resume/compact exercises
    the FD-94 participation cases; a reliable host pre-investigation event, where
    supported, directs the agent to ordinary `ask`; edit/write evaluates the
    complete changed scope through the same canonical effect projection as
    `reconsider`, including source, discovery, authority, route, containment,
    premise and cross-repository effects; multiple edits before handoff preserve
    their union; only notice presentation is bounded; and idle/stop/completion
    reports only known outstanding lifecycle obligations. Where logically
    possible, no-action, semantic-only, Functional-Pyramid-only and combined
    obligations are exercised. Explicit MCP-result transitions are not
    rediscovered, and no hook mutates semantics, curation, participation,
    governance or support or issues re-establishment contexts.
29. **Initialization handoff.** After accepted activation/revision, lifecycle
    verification succeeds only when `FunctionalPyramidSelector` returns the
    exact committed pyramid identity/version/member view with live health VALID;
    no undefined representative-route sample is required.
30. **One active instance per repository.** Attempting to activate/revise a
    member already ACTIVE in another pyramid produces
    `MEMBER_ALREADY_ACTIVE` and cannot create ambiguous repository-scoped
    governing orientation.
31. **Three-tool host surface.** Initialization, governed development and
    re-alignment are all reachable through `ask`, `record` and `reconsider`;
    no authority/pyramid MCP operation is advertised.
32. **Outside FunctionalScope.** An ACTIVE member queried wholly outside its
    declared FunctionalScope returns `OUTSIDE_FUNCTIONAL_SCOPE`, a resolved
    empty governing projection and no `UNCOVERED_PATH`.
33. **Broad scope crossing the functional boundary.** A directory/service/domain
    scope spanning outside and functional portions returns `MIXED` and preserves
    outside/covered/uncovered provenance without inventing file enumeration.
34. **Health iff structural findings.** ACTIVE health is VALID exactly when the
    FD-83 structural finding set is empty and DEGRADED exactly when it is
    non-empty; authority currency and expected PARTIAL gaps do not change health.
35. **Activation of pre-existing normative understanding.** A repository with a
    retained NORMATIVE revision recorded before ACTIVE participation is activated;
    that revision is returned as a direct dependent effect and becomes
    REASSESSMENT_REQUIRED until re-established with server-derived governance
    support.
36. **Functional Pyramid write propagation.** ACTIVATE/REVISE/DEACTIVATE return
    the same canonical affected-surface/conclusion projection used by reconsider,
    plus exactly one repository-bound re-establishment context per repository
    with actionable effects.
37. **Deactivation/removal route state.** A revision with recorded route support
    whose repository becomes UNCONFIGURED or EXCLUDED is
    REASSESSMENT_REQUIRED, not UNVERIFIABLE merely because participation ended.
38. **Operational route failure while ACTIVE.** An ACTIVE repository whose
    required route/member/declaration state cannot presently be evaluated is
    UNVERIFIABLE; deliberate participation change and operational unavailability
    remain distinct.
39. **Pyramid-write replay projection.** Replaying an accepted Functional
    Pyramid write preserves the immutable participation state and accepted
    dependent `ConclusionRevisionRef` set, re-evaluates only those refs into a
    current actionable `ChangedSurface` projection, and issues fresh live
    re-establishment contexts only where the retained effect is actionable now;
    it never adds effects from later governance state.
40. **Pyramid concurrency.** Concurrent revise/deactivate operations obey pyramid
    version compare-and-set, and concurrent overlapping activations/revisions
    cannot make one repository ACTIVE in more than one instance.
41. **Initialization declaration edits use ordinary re-alignment.** Every
    repository declaration edit in lifecycle §7.1 runs through changed-scope
    reconsideration and disposition before candidate validation proceeds.
42. **Conformance uses the normative input contract.** A conformance judgment
    is recorded with `assertion_nature=NORMATIVE`; in an ACTIVE repository it
    receives the same server-derived route/authority support as every other
    normative conclusion, and no third assertion-nature branch exists.
43. **Acceptance is not runtime completion.** An otherwise-valid NORMATIVE
    create/update whose derived governance is non-current returns
    `UnderstandingRecorded` with REASSESSMENT_REQUIRED/UNVERIFIABLE
    qualification, but the agent runtime cannot transition to successful
    COMPLETE until the required disposition becomes CURRENT; post-commit
    qualification unavailability likewise remains an explicit recovery/blocker.
44. **Participation-write acceptance is not initialization completion.** An
    accepted ACTIVATE/REVISE/DEACTIVATE that returns actionable dependent effects
    supplies their canonical update coordinates and per-repository contexts; the
    initialization/revision/deactivation procedure must dispose those effects
    before successful completion, without calling reconsider again for the
    participation write itself.
45. **New capture is not shared reuse.** A newly recorded supported conclusion is
    CAPTURED and absent from ordinary Answer content even when support is CURRENT.
46. **Pending-capture gap.** A surface with CURRENT captured knowledge but no
    CURRENT + CURATED conclusion returns `Gap/pending_curation` and exact
    pending revision references.
47. **Pending-curation discovery.** Repository pending-curation obtain returns
    exactly the deterministic CURRENT-support, current-membership revision set
    lacking curation and resumes by the exact revision keyset cursor.
48. **Curation does not rewrite or bypass support.** Curation accepts only a
    CURRENT exact revision, advances understanding history, and records an
    immutable disposition without creating a conclusion revision or changing
    semantic content/support; a non-current target is rejected for
    re-establishment first.
49. **Curated reuse.** The exact CURRENT revision becomes ordinary Answer content
    after accepted curation.
50. **Curation cannot override later support loss.** A previously CURATED
    revision that becomes REASSESSMENT_REQUIRED/UNVERIFIABLE is not Answer
    content and does not lose its curation history.
51. **Correction resets curation.** Correcting curated meaning creates a new
    CAPTURED revision.
52. **Replacement resets curation.** Replacing curated meaning creates a new
    CAPTURED lineage/revision.
53. **Addition begins captured.** Adding a new lineage to an understanding does
    not inherit sibling curation.
54. **Confirm preserves curated meaning.** A semantically unchanged support-only
    confirm of a CURATED predecessor inherits curation with explicit inherited
    provenance.
55. **Confirm does not invent curation.** Confirm of a CAPTURED predecessor remains
    CAPTURED.
56. **Withdrawal is never reusable.** Withdrawal remains explicit history and
    cannot acquire curation.
57. **Curation is a separate act.** A curation action cannot be combined atomically
    with create/add/confirm/correct/replace/withdraw semantic mutation.
58. **Curation is not governance.** Curation changes no Functional Pyramid
    participation, health, applicability, route or authority support.
59. **Normative reuse requires both planes.** A normative revision is Answer
    content only when CURRENT under its empirical/governing support and CURATED.
60. **Failed review repairs meaning first.** Challenge/correct/replace/withdraw
    can resolve a curation review finding without creating a rejected-curation
    state; only the resulting stable revision is curated.
61. **Schema-14 migration fabricates no curation.** Transition preserves every
    retained semantic/audit row while historical/current Beta-1 revisions begin
    CAPTURED under the new reuse contract.
62. **Migrated current knowledge is pending.** A migrated CURRENT revision is
    discoverable for curation but absent from ordinary Answer until curated.
63. **Three-tool host surface remains exact.** Capture, curation, reuse and
    re-alignment are all reachable through `ask`, `record` and
    `reconsider`; no curate tool exists.
64. **Installed lifecycle closes the loop.** A non-editable installed MCP journey
    demonstrates capture → pending discovery → curation → fresh-session reuse →
    change → reconsider → semantic-preserving confirm/reuse, and a semantic
    correction path that requires re-curation.


## 16. What this layer does not define

Layer 3 does not choose storage layout, wire encoding, transport framing,
installer mechanics, host adapters, persistence schemas, or deployment values.
Those are Layer-4 choices and must remain derivable from this functional design
and the higher layers.

