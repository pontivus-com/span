# Span functional design — layer 3

**Status: binding target for Span 1.0 Beta.** This is the third layer of the pyramid. It states the
behaviour that makes the lifecycle contract deterministic and testable, without
choosing a mechanism. Layer 4 — schemas, storage, transport, and host adapters —
must satisfy it.

Where this layer and a higher layer disagree, the higher layer governs. A
requirement here that cannot be traced to a higher-layer statement is a defect.

**1.0 Beta target behavior, 21 November 2026.** This design completes the
product model across empirical understanding, declared governing authority and
the supported relationship between them. Implementation, migration and host
verification remain pending; current code is not certified by this design.

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
Ordinary obtain issues no context. Explicit evidence admission and writes issue
contexts under their caller-owned request identities. Change-scope reconsider
also issues the bounded re-establishment context required by F4, but its issuance
identity is Span-owned and not a caller retry key. Any identity-bearing context
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

## 4. Functional Pyramid resolution

The Functional Pyramid is a governance graph, not a semantic surface hierarchy.
Its resolution is deterministic and uses only explicit declarations. Semantic
surface ownership continues to follow FD-1–FD-8.

**FD-61 — Participation is explicit and distinct from registration.**
A registered repository is `UNCONFIGURED` until Functional Pyramid lifecycle
state says otherwise. `EXCLUDED` is an explicit non-participation decision.
`ACTIVE` and `DEGRADED` mean the repository belongs to one explicit,
versioned Functional Pyramid instance. Repository installation, co-location,
imports, directory nesting or host registration never imply participation.
Surface obtain projects the durable participation state rather than using absence
or `None` to conflate unconfigured and excluded repositories. *(G4, G7, G8,
F11, F12, L12, L13)*

**FD-62 — Scope matching is deterministic and repository-relative.**
The effective semantic scope is normalized before Functional Pyramid matching.
An exact file/symbol path is matched directly. A directory, declared-surface or
repository-wide scope resolves every functional context whose declared coverage
intersects that semantic scope, including contexts narrower than the scope
boundary. Repository-wide scope therefore intersects every declared context in
that participating repository.

The layer-4 selector grammar must make both membership and scope intersection
deterministically decidable. If a declared selector cannot be evaluated against
the semantic scope, resolution reports `UNRESOLVED_SCOPE_INTERSECTION`; it
does not assume non-applicability. Absolute paths, traversal outside the
repository and ambiguous repository identity are rejected. Semantic
classification, model judgment, file-name heuristics and structural proximity
never participate. *(G1, G4, F11, L12)*

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
`P4`.

- P0 rules have `ROOT`, not a governing rule.
- P1 rules are governed by applicable P0 rules. A missing or undecided parent is
  `UNRESOLVED_RULE_PARENT`; an unresolved relationship is not a valid accepted
  governing edge.
- P2S and P2W rules are contract-layer siblings. They identify applicable
  higher goals/invariants; neither becomes the other's derivation parent merely
  because both apply.
- P3 rules identify the applicable contracts/invariants they realize.
- P4 rules identify the applicable behavior or contracts they realize.
- A direct governing edge may skip an absent intermediate layer.
- Same-layer edges and edges from a higher layer to a lower governing parent are
  invalid derivation edges.

A valid edge establishes derivation only. It does not prove that the semantic
rule text is correct. *(G7, F11)*

**FD-68 — Route resolution follows declarations to closure.**
For each selected path Span:

1. finds every directly applicable context by deterministic semantic-scope
   intersection under FD-62;
2. expands context inheritance;
3. collects every rule referenced by those contexts;
4. resolves each rule's canonical owner;
5. walks every direct governing-rule edge to `ROOT` or a typed structural
   unresolved terminal; authority status/content currency is evaluated
   separately by FD-12 and never changes graph topology;
6. deduplicates by stable identity while preserving every provenance path.

No step selects a preferred route when several valid routes apply. *(G1, G7,
F11, L12)*

**FD-69 — Multi-path and broad-scope resolution preserve provenance.**
When a semantic scope contains several explicit paths, Span resolves each path
or path boundary under FD-62, unions identical contexts and rules for
presentation, and preserves the scope-path-to-context-to-rule provenance for
each input. A repository-wide scope is represented as that semantic scope, not
as an invented list of files. A rule shared by several scope members appears
once in the rule set but remains traceable from every applicable member.
*(G4, F11)*

**FD-70 — Cross-repository references are explicit.**
Context and rule references may cross repositories only through declared stable
identities between members of the same Functional Pyramid instance. Registration
outside the instance is not sufficient. If a referenced member repository is
not available, the relationship is `REPOSITORY_UNAVAILABLE`. If that member is
available but the named context/rule does not exist, it is `UNKNOWN_CONTEXT` or
`UNKNOWN_RULE`. Those states are not conflated and neither is repaired by
searching for similar content or by binding to another registered repository.
*(G1, G7, G8, F11, F12, L13)*

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
by layer from P0 through P4 and then stable rule identity. Provenance edges use
stable identities. The same repository state and semantic scope produce the
same route ordering. *(A2, F11)*

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
repository participates, Span resolves the complete effective semantic scope
under FD-68–FD-70 before acceptance. Span adds:

- one route-support dependency for that resolved applicability graph; and
- authority-support dependencies for every applicable functional rule.

The caller cannot omit, replace, narrow or mark those dependencies current. If
any applicable route branch is unresolved or an applicable authority is not
currently supportable, the normative conclusion is not currently supportable.
Additional explicit support may be supplied but cannot substitute for the
server-derived governance dependencies. *(G1, G3, F2, F7, F11, L12)*

**FD-76 — Descriptive understanding and governing orientation remain distinct.**
A descriptive conclusion does not automatically depend on the Functional
Pyramid merely because its path has a governing route. The route is still
returned for orientation. Explicit authority support remains permitted when a
descriptive conclusion genuinely depends on authority. Source currency cannot
make authority current, and accepted authority cannot establish observed
implementation behavior. *(F1, F5, F11)*

**FD-77 — Conformance is a supported judgment, not a generated verdict.**
Span never computes semantic conformance from rule text and source topology. A
human or agent authors a normative/conformance conclusion after investigation.
Span can then establish that the judgment's empirical dependencies, governing
route and applicable authorities are current. *(G7, F1, F5)*

**FD-78 — Functional Pyramid orientation is available on cold surfaces.**
An unassessed semantic surface may return `Gap/unassessed` while its Functional
Pyramid view is fully resolved. Conversely, descriptive understanding may remain
usable while the Functional Pyramid view contains unresolved governance. The two
states are composed but never collapsed. *(G1, G4, G7, L3, L12)*

**FD-79 — Governance changes are support changes.**
A change to a participating context declaration, rule declaration, canonical
authority identity/content/status, governing edge, member availability or active
pyramid membership causes affected route and authority dependencies to be
re-evaluated. The affected walk crosses repository boundaries inside the same
Functional Pyramid instance. A normative conclusion may therefore become
`REASSESSMENT_REQUIRED` or `UNVERIFIABLE` without any implementation source
change and without living in the repository where the governance change occurred.
*(G3, F4, F11, F12, L10, L12, L15)*

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
complete member intent. Every member names one registered repository, its exact
repository-owned declaration source requests and its declared
`PARTIAL | COMPLETE` coverage. A repository may belong to at most one
ACTIVE/DEGRADED Functional Pyramid instance at a time so ordinary repository-
scoped `ask` has one unambiguous governing instance. *(G8, A3, F12, L13, L14)*

**FD-83 — Participation-state transitions are closed.**
The durable states are exactly `UNCONFIGURED`, `EXCLUDED`, `ACTIVE` and
`DEGRADED`, with the transitions in lifecycle §7.1.

- candidate validation never changes durable state;
- failed activation/revision leaves the prior durable state/version unchanged;
- successful activation moves UNCONFIGURED/EXCLUDED members to ACTIVE;
- successful revision keeps retained members ACTIVE and makes removed members
  EXCLUDED;
- structural loss in an active graph moves affected instance state to DEGRADED;
- restoration of the same graph or a valid repair revision moves DEGRADED to
  ACTIVE;
- deactivation moves every member to EXCLUDED.

No filesystem/installer/model event creates another transition. Authority
content/status change alone does not make graph topology DEGRADED when all
declared identities/edges remain resolvable. *(G1, G8, F12, L13, L14)*

**FD-84 — Candidate validation is pure, deterministic and complete.**
For one member intent and present repository state, validation returns the same
ordered findings and changes nothing. It validates registered-member identity,
declaration-source existence, duplicate ownership, selector decidability,
context inheritance, rule identity/ownership/layer, governing-edge legality,
cross-member references, cycles and the declared coverage mode. It reads only
explicit declaration sources and references reached from them; it does not scan
for semantically similar authority or repair a missing declaration. *(G1, G8,
A2, F11, F12, L14)*

**FD-85 — Activation and revision revalidate current source and commit
atomically.**
A Functional Pyramid write never trusts a previous candidate-validation result.
It resolves the submitted member intent against current source, derives the
candidate graph identity and findings, and commits only if the candidate is
structurally admissible. Rejection commits no participation/version change.
Activation/revision stores the identities, relationships, source identities and
coverage needed to reproduce resolution; canonical governing prose is never
stored as pyramid content. All accepted writes obey receipt replay and
compare-and-set rules. *(G6, G8, A2, A3, F1, F12, L4, L14)*

**FD-86 — Coverage state never invents absence of authority.**
`PARTIAL` explicitly declares incomplete migration. A selected scope with no
applicable declared context returns `UNCOVERED_PATH` while the instance may
remain ACTIVE. `COMPLETE` is an owner-supplied claim that functional migration
is complete; Span does not infer that claim from repository inventory. If a
selected functional scope in a COMPLETE member has no applicable context, the
route returns `UNCOVERED_PATH` and the instance becomes DEGRADED until the
coverage claim or declarations are corrected. Process/evidence/support files are
not automatically functional scope merely because they exist. *(G1, G4, G8,
F11, F12, L13)*

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

**FD-89 — Cross-repository change propagation uses the whole instance.**
When changed paths can affect a context declaration, rule declaration, canonical
authority source or member binding, direct dependency lookup starts from the
changed repository but traverses FD-88/route-support dependents across every
member of the same instance. Affected semantic surfaces remain owned by their
own repositories and are grouped that way in the reconsider result. The caller
need not submit dependent repository IDs. *(G3, F4, F12, L10, L15)*

**FD-90 — The governing projection uses the same effective semantic scope.**
For ordinary semantic obtain, Functional Pyramid applicability is resolved from
the exact effective semantic scope already selected for the Answer/Gap. Question
text, embeddings, similarity, document genre and source prominence never expand
that scope or select governing documents. The view returns references to every
declared rule applicable through that scope, regardless of which document genre
owns each rule. *(G4, G6, G7, F9, F11, L12, L16)*

**FD-91 — Participation state and route/support state remain independent.**
An ACTIVE/PARTIAL instance can return an `UNCOVERED_PATH` route without
becoming DEGRADED. A DEGRADED instance can still return RESOLVED routes for
unaffected scopes. A structurally RESOLVED route can still yield non-current
normative support because an applicable authority is draft, superseded,
unavailable or changed under FD-12. No one state is used as a shortcut for the
other two planes. *(G1, F1, F2, F12, L13, L16)*

**FD-92 — Functional Pyramid status/candidate projection is lifecycle data, not
semantic understanding.**
`FunctionalPyramidSelector` returns exact participation/instance state;
`FunctionalPyramidCandidateSelector` returns pure validation findings. Neither
result creates an Answer, conclusion, investigation context or authority.
Surface/current-understanding obtain continues to compose semantic content with
the governing projection for that surface. *(F5, F6, F11, F12, L8, L13, L14)*

**FD-93 — Functional Pyramid writes are one record kind, not a fourth tool.**
The `functional_pyramid` record kind implements activate/revise/deactivate/
exclude exactly as lifecycle §4.2 defines, returns
`FunctionalPyramidRecorded`, and uses the canonical receipt/replay contract.
The caller supplies intended member/declaration/coverage input; Span derives
pyramid identity, validation, source identities and qualification. *(G8, F6, F7,
F12, L4, L8, L14)*

**FD-94 — Lifecycle notices reflect participation without becoming governance.**
For a registered UNCONFIGURED repository, the session notice directs the agent to
the Functional Pyramid initialization skill/status path; EXCLUDED is quiet about
initialization unless explicitly requested. ACTIVE uses ordinary governed-work
guidance. DEGRADED reports governance attention and the next public lifecycle
action. Change notices use canonical cross-repository reconsideration results.
Hooks never activate/revise a pyramid, author rule meaning, copy rule content,
or make support current. *(G8, A4, F5, F10, F12, L13–L16)*

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
Functional Pyramid instance bindings under FD-82–FD-91. If evaluation of that
scope is operationally impossible, support is `UNVERIFIABLE`. If its complete
route-support identity differs from the recorded identity, support is
`REASSESSMENT_REQUIRED`. If that route contains an unresolved branch, support
is `UNVERIFIABLE`. Only the same complete resolved route is `CURRENT`.
A DEGRADED instance does not by itself invalidate an unrelated scope whose route
still resolves identically. Applicable authority content/status is checked
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
`ask` returns `Answer` when at least one matched conclusion is `CURRENT`.
Functional Pyramid orientation does not itself turn a semantic Gap into an
Answer and an unresolved pyramid does not by itself discard a current
descriptive conclusion. It
returns `Gap` when no matched conclusion is current. `Answer` contains only
current conclusions; stale conclusions appear as references in the surface
status, never as answer content. A supported conclusion is never withheld because
another matched conclusion is stale: that would discard usable understanding
(A9) and force re-derivation (F8). See §14. *(F2, L2)*

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
For surface/current-identity/exact-recorded-question membership selected under
lifecycle §4.1, no current conclusion yields one reason from combined support:
REASSESSMENT_REQUIRED becomes `invalidated`, UNVERIFIABLE becomes
`unverifiable`, and no retained usable understanding becomes `unassessed`.
The ordinary free `question` lookup branch and its `no_match` production path
are retired. `RecordedQuestionSelector` performs exact equality only within its
supplied surface. An empty matched set for the exact question maps to
`unassessed`; matched membership with lost support still follows the ordinary
`invalidated`/`unverifiable` mapping. The selector does not reintroduce
natural-language or similarity matching. Stored question metadata/history is not
rewritten. An unknown exact identity is a lookup rejection, not a newly invented
Gap. Context binding/admission failures never become semantic absence.
*(F3, F4, A8, L3)*

**FD-26 — Ambiguity is a separate result.**
When a surface reference resolves to more than one granularity, the result is
`AmbiguousSurface` with the candidates and the missing decision. It is never a
`Gap` reason and never an arbitrary choice. *(F9, L2)*

**FD-27 — Operational failure is not an empty answer.**
A failure that prevents the lifecycle operation itself from evaluating —
unavailable store, required provider error, schema version — returns
`Unavailable` with the recovery. If semantic answer composition succeeds but
Functional Pyramid orientation for an ACTIVE/DEGRADED member fails operationally,
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
The semantic surface view is composed on read from current conclusions; no stored
copy exists. This assembled explanatory view is distinct from canonical governing
documents. Functional Pyramid rules remain at their canonical owners and are
referenced by the accompanying pyramid view rather than copied into the surface
document view. Its contents are fixed in `lifecycle-contract` §4.1.
*(G6, F11, L11, L12)*

Pure surface obtain groups all current membership by recorded question metadata.
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
`NORMATIVE` content in a participating repository, route and authority support
are derived under FD-75 after semantic scope is fixed and before acceptance.
*(F5, F7, F11, L2, L12)*

**FD-31 — confirm.** A re-establishment action: accepted only after present
support has been checked, and only for a version whose recorded support was not
current. If the version is already current and unchanged, the operation returns
the current version rather than creating a new one. Unchanged wording alone is
never a confirmation. A confirm names the conclusion and the reassessed
evidence; Span preserves the current statement, assertion nature, and scope,
re-derives required Functional Pyramid support when normative, and derives a
non-empty mechanical basis. *(F2, A6, F8, F11, L4)*

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
are returned in the pyramid view and make required normative route support
`UNVERIFIABLE`. A malformed declaration that violates the accepted declaration
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
bound follows from A1 and A2. The concrete window is a deployment measurement
recorded in layer 4, not a product choice. *(A2)*

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
Support checks occur within the operations returning understanding, regardless
of notice delivery. The agent lifecycle remains required by layer 2 §7. *(A4)*

**FD-53 — Live delivery is unverified until captured.**
A host contract is established only by a recorded capture observed or failed.
*(A8)*

The Version-1 host contract still exposes exactly `ask`, `record` and
`reconsider`. Functional Pyramid orientation is verified as part of those
result schemas; no host is accepted on evidence from a separate authority tool
because no such public operation exists. *(F6, L8, L12)*

**FD-58 — Lifecycle notices reach the agent at the moment of use.**
For a registered operational repository, the notice reflects the durable
Functional Pyramid participation state under FD-94 and names only the next
public lifecycle action: initialization/status orientation for UNCONFIGURED,
ordinary governed-work orientation for ACTIVE, governance attention for
DEGRADED, and no unsolicited initialization pressure for EXCLUDED. A
source/governance-change notice names the next required `reconsider` action and
may report that affected understanding crosses member repositories. Notices use
canonical computations; they do not activate/revise governance, author semantic
conclusions or certify meaning. Measure delivered notice cost under F8 and
delivery under FD-53. *(F5, F10, F12, G2, G8, L13–L16)*

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

## 14. Why these choices follow

The choices below that resemble judgement calls are derivations, not preferences.

### The Answer/Gap threshold (FD-23, FD-25)

F2 forbids presenting unsupported content as an answer. L2 and L3 require
unsupported content to appear as history or references instead. F2 preserves the current part, and F8 penalises discarding usable understanding.

Therefore: if at least one matched conclusion is current, the result is an
`Answer` containing only current conclusions, with the rest reported as status
references. If none is current, the result is a `Gap`. The Gap reason follows the
combined state under FD-25; membership is selected by surface, current identity,
or the explicit exact recorded-question selector, never by an ordinary supplied
question string or semantic similarity.

Withholding a supported conclusion because a sibling is stale would satisfy no
principle and violate two.

### The state precedence (FD-15)

F1 keeps evidence and authority proof distinct, A6 says confidence is not
evidence, and A7 requires a safe default. If any dependency cannot be checked, the conclusion is not
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

### Two proof planes (FD-12, FD-81, FD-73, FD-76)

G1 and F1 require Span to say only what its evidence establishes. Source identity
can establish empirical currency but cannot establish that a governing rule is
legitimate or applicable. Conversely, accepted canonical authority can establish
governing status but cannot establish what implementation currently does.

Therefore source/verification support and authority/route support remain distinct
dependencies. A conformance judgment becomes reusable by depending on both,
rather than by weakening either proof type.

### Additive context resolution (FD-63, FD-64)

G7 requires the complete applicable governing route, and F11 forbids inference.
A path can legitimately participate in several responsibilities at once.
Selecting one "best" context would drop obligations without authority to do so.
Therefore every explicit match composes and inheritance adds rather than
replaces.

### Server-derived normative governance support (FD-75)

A4 says the agent will omit bookkeeping; F7 says Span derives what can be
derived; G7 requires governing applicability to be complete. If the caller were
allowed to enumerate the applicable governing route, omission would create a
false CURRENT normative conclusion. Therefore Span derives route and authority
support from the already-declared semantic scope and Functional Pyramid.

### confirm (FD-31)

F2 requires present support for any claim of currency; A6 forbids treating
unchanged wording as evidence; F8 penalises work that adds no value. A
confirmation is therefore a re-establishment, not a re-assertion: it requires a
present check and applies to a version that was not current. If the version is
already current and nothing changed, a new version would be churn, so the current
version is returned.

## 15. Version 1 Beta functional acceptance

The implementation is not functionally conformant to this design until the
following behaviors are demonstrated against the public lifecycle and pure core
rules. These are behavioral cases, not layer-4 mechanism choices.

1. **Unconfigured versus excluded.** A registered repository starts
   UNCONFIGURED. Explicit exclusion returns EXCLUDED. Neither state invents an
   empty governing route, and descriptive semantic lifecycle remains usable.
2. **Pure candidate validation.** Validation of a proposed multi-repository
   member/declaration set returns deterministic complete findings and changes no
   durable participation state.
3. **Activation and replay.** A valid activation atomically creates one pyramid
   identity/version; replay is idempotent; invalid activation leaves every
   repository's prior state unchanged.
4. **Revision and removal.** A compare-and-set revision atomically changes the
   complete member intent; removed members become EXCLUDED and retained members
   preserve the pyramid identity with a new version.
5. **Partial coverage.** ACTIVE/PARTIAL scope outside declared contexts returns
   `UNCOVERED_PATH` without degrading unrelated covered routes or the instance.
6. **Complete-coverage contradiction.** An uncovered selected functional scope
   in a COMPLETE member returns `UNCOVERED_PATH` and moves the instance to
   DEGRADED until corrected.
7. **Degraded recovery.** Member/declaration/structural unavailability moves an
   ACTIVE instance to DEGRADED; unaffected routes can still resolve; restoring
   the graph or committing a valid repair returns ACTIVE.
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
    valid derivation edge.
16. **Route versus authority currency.** A structurally complete route can remain
    RESOLVED while an applicable authority is DRAFT/SUPERSEDED/changed and
    normative support becomes non-current through authority support.
17. **Normative create.** The caller supplies semantic intent and empirical
    evidence; Span derives route and every applicable authority dependency.
    Omitting governance is impossible through the public grammar.
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
    predicting a proposed edit or copying rule text.
22. **Cross-repository reconsideration.** A governing change in repository A
    returns affected normative understanding in repository B when the same
    pyramid graph connects them; the caller does not enumerate B.
23. **Implementation change.** Existing source/discovery/premise propagation
    remains intact and does not depend on the Functional Pyramid being the cause.
24. **Mixed answer.** A current descriptive conclusion can be returned while its
    pyramid route is unresolved; a normative conclusion depending on that route
    cannot be returned CURRENT.
25. **Canonical-source singularity.** Pyramid state/view/storage returns rule
    identities, owner anchors and relationships but no copied summaries, chunks
    or canonical rule prose.
26. **Governed development lifecycle.** The §7.2 state machine can be exercised
    from ORIENT through COMPLETE, including INVESTIGATE, BLOCKED,
    READY_TO_CHANGE, RECONSIDER and REESTABLISH transitions; no hidden transition
    is required.
27. **Governance-source edit lifecycle.** Before editing a canonical rule owner,
    the current downstream graph is obtainable; after the edit, reconsider
    reports cross-repository authority/route effects and record closes the
    affected dispositions.
28. **Participation-aware hooks.** UNCONFIGURED, ACTIVE, DEGRADED and EXCLUDED
    produce the FD-94 notice behavior without any hook mutating governance or
    support.
29. **Three-tool host surface.** Initialization, governed development and
    re-alignment are all reachable through `ask`, `record` and `reconsider`;
    no authority/pyramid MCP operation is advertised.


## 16. What this layer does not define

Storage layout, wire schemas, transport framing, installer behaviour, host
adapters, and exact deployment numbers. Those are layer 4 and must satisfy this layer. The concrete declaration file format, path-selector grammar, persistence schema,
graph-index/cache mechanism, repository-binding storage, host adapter mechanics,
administrative CLI representation and migration from 0.11 are therefore
intentionally left to the Version-1 technical design. The public lifecycle
semantics and transitions in layer 2 are not left for layer 4 to invent.
