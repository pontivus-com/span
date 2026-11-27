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
Functional Pyramid participation writes are installation-scoped lifecycle writes;
surface declaration writes are repository-scoped. Neither issues an
investigation context merely because it is a write.
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

For surface writes, bind exact canonical surface action/expected boundary and
request content. Resolve receipt before parent/boundary validation; accepted
boundary version and action are immutable receipt facts. New writes use atomic
CAS; same-content retry returns original boundary even after another update.
An identical create under a new request may accept the unchanged boundary and
records its own decision. No artificial evidence context.

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

**Registered-root address resolution (FD-1, FD-62; lifecycle §4.1).**
Resolve every new public path against its supplied registered origin. Use
canonical absolute roots internally, segment containment and unique deepest
registered root. Reject duplicate deepest roots, path escape and a symlink
alias that crosses a registered boundary; unrelated unresolvable roots do
not block unless they could own the addressed path. For deleted/changed
paths resolve the nearest existing ancestor and validate remaining normalized
segments without requiring the leaf to exist. For SYMBOL use the existing
canonical file-locator extraction, preserve the symbol suffix. Reference
matching resolves a declared exact name in the supplied repository or path
owner; if both distinct candidates match, return AmbiguousSurface, never
guess. Explicit SERVICE/DOMAIN and identity/context selectors do not rebase.
A declared boundary may contain a nested registered root physically, but
that subtree is excluded from the parent's semantic path ownership; do not
re-key historical surfaces or evidence. Validate new boundaries and scope
against the owning repository; a boundary at an ancestor describes its own
repository portion, not independently registered descendants.

For direct create derive owner from explicit FILE/SYMBOL or path scope/
locator, otherwise declared surface or repository-wide origin. Normalize
all local source, scope and discovery paths to that owner before containment
checks. Identity-based update/challenge and context-bound operations keep
their canonical owner; translate local paths only if they resolve there.
Declaration source paths stay bound to the declared member, not rerouted.
Path-based verification uses the same scope ownership. Mixed-owner
admission/writes reject atomically before context or evidence creation;
existing qualified cross-repo authority and premise support stays explicit.
For change roots partition resolved owner/path pairs, deduplicate canonical
roots and union direct/containment roots before the one premise closure
(FD-17–22); identity references are never translated. Map hook paths through
this same rule before determining which lifecycle request to issue.
Resolve persisted request binding before new-write routing (FD-3), so even
a moved root cannot create a second accepted effect; never replay from an
inferred owner. These rules preserve standalone behavior and do not infer
participation.

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

The Functional Pyramid is a declared governance graph, not a semantic surface hierarchy.
Its resolution is deterministic, uses only explicit declarations, and is total for a
participating repository. Semantic surface ownership continues to follow FD-1–FD-8.

**FD-61 — Participation is explicit and distinct from registration and health.**
A registered repository is `UNCONFIGURED` until Functional Pyramid lifecycle
state says otherwise. `EXCLUDED` is an explicit non-participation decision.
`ACTIVE` means the repository belongs to one explicit, versioned Functional
Pyramid instance, and participation covers the whole repository. Those are the
only durable participation states. Repository installation, co-location, imports,
directory nesting or host registration never imply participation.

An ACTIVE pyramid's present health is computed independently as
`VALID | DEGRADED`; evaluating health never performs a participation-state
write. Surface obtain projects UNCONFIGURED/EXCLUDED explicitly and projects
ACTIVE together with current health rather than using absence or `None` to
conflate states. *(G4, G7, G8, F11, F12, L12, L13)*

**FD-62 — Directory selection is declaration-driven.**
A declared document placement carries one canonical document reference, one
layer, one explicit repository-relative directory `scope` in its declaring
repository, and its declared governing placements. The repository root is the
explicit `.` scope and the widest scope.

For exact directory lookup apply the registered-root address procedure in §2,
require an existing directory, then use the resolved owner-relative directory
(`.` for its root). Inability to establish ownership is explicit operational
unavailability, not parent fallback.
Determine that repository's own participation and instance, including explicit
UNCONFIGURED/EXCLUDED or operational unavailability; never substitute the
addressing repository's governance. For an ACTIVE owner, select every placement
declared by that repository whose scope contains the resolved directory: the
directory itself, or an ancestor directory scope including `.`. A placement confined to a descendant directory does not apply to
its parent. The selection is a point selection; it never enumerates descendant
files, never uses the file inventory to decide relevance, and never requires a
semantic surface declaration.

After selection, the resolver continues through FD-68 without a coverage
classification branch. For public location projection, choose the outermost
registered canonical ancestor of the resolved owner as the root basis.
This basis is independent of the caller's addressing origin and participation.
Rebase each selected directory, document locator and placement scope from its
actual owning or declaring root into that basis by canonical path-segment
containment and relative-path composition. A nested member's internal `.`
becomes its parent-root prefix, not the parent's `.`. Apply the same procedure
to public finding coordinates and embedded governing placements. If an actual
document or scope owner lies outside that tree, use its own outermost registered
root as the explicitly qualified basis. Resolve no path by guessing, emit no
`..` or absolute root, and do not claim a location when its root binding cannot
be established. Unavailable coordinates retain typed public cause/recovery;
never suppress an unresolved finding. Standalone status/candidate findings use
the same per-coordinate root projection without an invented common ancestor.
The projection changes addresses only; do not change selection, placement
identity, document authority, declaration scopes, support or route identity. Root-totality is validated independently by FD-86;
structural and operational defects remain typed under FD-71 and FD-91. Layer
summaries are derived from the resolved selection under FD-86 rather than from
directory inventory or a coverage state.

For a semantic scope, each member path is mapped deterministically to a
directory: a FILE or SYMBOL member uses the directory containing its locator,
and a SERVICE or DOMAIN boundary member uses the declared path as a directory
boundary unless the existing canonical semantic-containment owner has already
classified that member as an exact file or symbol locator, in which case its
containing directory is used. A repository-wide semantic scope selects every
placement in the repository. The resulting route is the union of the
per-directory selections, and provenance retains the path or boundary that
selected each placement.

Scope is explicit declaration input. The declaring owner supplies it in the
approved classification ledger during initialization. Absolute paths, traversal
outside the repository and ambiguous repository identity are rejected. Semantic
classification, model judgment, file-name heuristics and structural proximity
never participate. *(G1, G4, G7, F11, F12, L12–L13)*

**FD-63 — Applicable-set construction is monotone.**
For one normalized directory, start with an empty placement set and walk the
directory's canonical scope prefixes from `.` through the directory itself.
At each visited scope, union the placements declared exactly at that scope by
placement identity. The procedure only adds identities; it has no
most-specific-wins subtraction step. For a semantic selection with several
directory seeds, run the same procedure per seed and union the results while
retaining seed provenance. *(G4, G7, F11)*

**FD-64 — Applicability selection and governing traversal are separate.**
Complete FD-63 placement selection before following any governing-placement
edge. FD-67 governing traversal may add governing placements to the returned
route closure, but that relationship never changes which declaration scopes
matched the selected directory or makes a placement applicable to an unrelated
directory. *(F11)*

**FD-65 — Placement and document identity have one declaration owner.**
A placement identity names one canonical declaration within the resolved
repository set. A repeated typed placement identity is duplicate ownership
whether its governing relationships are identical or conflicting; it is not a
merge candidate and produces `DUPLICATE_DOCUMENT_PLACEMENT`. A canonical document
identity is listed at most once across a declaring repository's complete source
set, occupies exactly one layer and one scope, and has exactly one placement at
its source scope. Repetition produces `DUPLICATE_DOCUMENT_SOURCE`,
`DUPLICATE_DOCUMENT_LAYER` or `DUPLICATE_DOCUMENT_SCOPE` respectively. Duplicate
validation inspects the complete decoded entry set before any deduplicated index
is built. An unknown governing placement is unresolved. A governing-document
cycle is unresolved, and every route that depends on the cycle carries that
limitation. *(G1, F11)*

**FD-66 — Functional Pyramid sources are Version-3 declaration documents.**
A Functional Pyramid declaration source has one stable `source_id`, one kind
(`repository` or `area`), one explicit directory scope, an explicit
whole-document membership set, and placements. Each participating repository has
exactly one `repository` source at scope `.`; further sources are `area` sources
at canonical non-root scopes, including shared-ancestor sources. A placement has
one declaring repository, one repository-qualified canonical document reference,
one declared layer, one explicit directory scope equal to its containing source's
scope, and zero or more direct governing placement references. One canonical
document has exactly one placement in its declaring repository. Span never
requires, stores or returns individual rule IDs, rule anchors or section-level
rule placements. Substantive content remains at the canonical document.
*(G6, F1, F11)*

Membership uses the layer-independent identity `repository_id` + `document_ref`
and is derived from each placement's document reference. A source validates that
every listed document has a placement at the source scope
(`MISSING_AREA_DOCUMENT`), every placement's document is listed
(`UNLISTED_AREA_DOCUMENT`), and every placement scope equals the source scope
(`DOCUMENT_SCOPE_MISMATCH`). The same canonical document may participate in
different declaring repositories; uniqueness is evaluated within each declaring
repository.

`document_ref` is one normalized repository-relative whole-file locator. A
valid placement resolves to exactly one `AuthorityBinding` whose repository and
locator equal the document reference and whose evidence has no `section_or_span`.
Invalid locators, no binding, multiple bindings, a mismatched or anchored
binding, and an unreadable canonical document are respectively
`INVALID_DOCUMENT_REFERENCE`, `MISSING_DOCUMENT_AUTHORITY`,
`AMBIGUOUS_DOCUMENT_AUTHORITY`, `NONCANONICAL_DOCUMENT_AUTHORITY`, and
`DOCUMENT_UNAVAILABLE`. Accepted/draft/superseded content status remains an
authority-support question under FD-12 rather than a second placement identity.
*(G6, F1, F11, F12)*

**FD-67 — The layer relation is fixed and validated.**
The Functional Pyramid layers are `P0`, `P1`, `P2S`, `P2W`, `P3` and `P4`. For
governing derivation, the contract layer has two ordered sublayers: `P2S`
precedes `P2W`.

- P0 document placements have `ROOT`, not a governing placement.
- P1 placements are governed by applicable P0 placements. A missing or undecided
  parent is `UNRESOLVED_DOCUMENT_PARENT`; an unresolved relationship is not a valid accepted
  governing edge.
- P2S and P2W placements identify applicable higher goals/invariants.
- A P2W placement may explicitly identify a P2S placement as a direct governing
  placement. A P2S placement cannot derive from a P2W placement.
- Applicability never creates that P2W-to-P2S relationship. It exists only when
  the P2W declaration names the P2S placement directly.
- A governing edge within P2S or within P2W is invalid.
- P3 placements identify the applicable contracts/invariants they realize.
- P4 placements identify the applicable behavior or contracts they realize.
- A direct governing edge may skip an absent intermediate layer.
- Other same-layer edges and edges from a higher layer to a lower governing
  parent are invalid derivation edges.

A same-repository governing edge is valid only when the governing placement's
scope contains the governed placement's scope: a narrower document cannot govern
a broader location. Cross-repository governing edges are derivation only; their
scopes are not comparable, and applicability remains local to each declaring
repository.

A valid edge establishes derivation only. It does not prove that the document's
substantive content is correct. *(G7, G8, F5, F11, F12)*

**FD-68 — Route resolution follows declarations to closure.**
For each selected directory or semantic-scope portion Span:

1. selects every placement whose scope contains it under FD-62;
2. orders and deduplicates by placement identity while preserving every
   provenance path;
3. resolves each placement's canonical document and authority binding;
4. walks every direct governing-placement edge to `ROOT` or a typed structural
   unresolved terminal; authority status/content currency is evaluated
   separately by FD-12 and never changes graph topology;
5. reports the declared and absent layer summary under FD-86.

No step selects a preferred route when several valid routes apply. A directory
with no narrower placement still returns its declared ancestor placements,
including the repository-root P0 placement. *(G1, G7, F11, L12)*

A structural finding that affects this selection makes the route `UNRESOLVED`. A
finding attached to a placement is relevant when that placement is in the
selected closure. A finding without a placement is relevant when its
declaring-repository source scope contains a selected directory or semantic
portion, or when the selected closure contains a placement in the same declaring
repository whose scope is contained by the affected source scope. A finding in an
unrelated repository or unrelated scope does not invalidate the route, although
global ACTIVE health may still be `DEGRADED`.

**FD-69 — Multi-path and broad-scope resolution preserve provenance.**
When a semantic scope contains several explicit paths, Span resolves each path
or path boundary under FD-62, unions identical placements for presentation, and
preserves scope-to-placement-to-document provenance internally for each input. A
repository-wide scope selects every placement rather than an invented list of
files. A placement shared by several scope members appears once but remains
traceable from every applicable member. *(G4, F11)*

**FD-70 — Cross-repository references are explicit.**
Every declaration edge to a placement carries the target registered
`repository_id` together with the stable identity; local edges use the same
qualified form rather than a second shorthand. Placement and governing
references may cross repositories only between members of the same Functional
Pyramid instance. Registration outside the instance is not sufficient.
Applicability scope is always in the declaring repository; a cross-repository
document participates in another repository's directory only through a placement
declared by that repository.

This qualified identity is what makes failure classification deterministic: if
the named target repository is a member but unavailable, the relationship is
`REPOSITORY_UNAVAILABLE`; if that member is available but the named document or
placement does not exist there, it is `UNKNOWN_DOCUMENT`. A reference to a
repository outside the instance is invalid declaration state. Those states are
not conflated and none is repaired by searching for similar content or by
binding to another registered repository. *(G1, G7, G8, F11, F12, L13)*

**FD-71 — Unresolved route states are typed and preserved.**
The unresolved-reason vocabulary is closed:

- `INVALID_DECLARATION`;
- `INVALID_PLACEMENT_SCOPE`;
- `DUPLICATE_DOCUMENT_PLACEMENT`;
- `DUPLICATE_DOCUMENT_SOURCE`;
- `DUPLICATE_DOCUMENT_LAYER`;
- `DUPLICATE_DOCUMENT_SCOPE`;
- `DOCUMENT_SCOPE_MISMATCH`;
- `MISSING_AREA_DOCUMENT`;
- `UNLISTED_AREA_DOCUMENT`;
- `INVALID_DOCUMENT_REFERENCE`;
- `MISSING_DOCUMENT_AUTHORITY`;
- `AMBIGUOUS_DOCUMENT_AUTHORITY`;
- `NONCANONICAL_DOCUMENT_AUTHORITY`;
- `DOCUMENT_UNAVAILABLE`;
- `UNKNOWN_DOCUMENT`;
- `DOCUMENT_CYCLE`;
- `INVALID_GOVERNING_EDGE`;
- `UNRESOLVED_DOCUMENT_PARENT`;
- `REPOSITORY_UNAVAILABLE`;
- `MISSING_ROOT_PLACEMENT`.

The document-source, document-layer, document-scope and area-document reasons
apply to both repository-kind and area-kind sources. `INVALID_DECLARATION` is the
source-set topology reason (duplicate source identity or scope, missing or
multiple repository-kind sources, a repository-kind source at a non-root scope, an
area-kind source at the root scope, or an ACTIVE source that cannot be decoded).
`INVALID_DECLARATION_SOURCE` remains a candidate validation reason, and
`NONCANONICAL_DECLARATION` remains an installer-level provenance failure; neither
is an FD-71 finding.

Resolvable branches remain visible when another branch is unresolved, but the
route reports its unresolved state completely. No unresolved branch is dropped
to manufacture a complete route. A new unresolved reason requires an amendment
to this functional design rather than an implementation-local string or fallback.
*(G1, A7, F11, L12)*

**FD-72 — Route ordering and provenance are deterministic.**
Paths retain request order after normalization. Placements are presented in the
fixed layer order `P0`, `P1`, `P2S`, `P2W`, `P3`, `P4` and then by declaring
repository, canonical document repository, document reference and scope. This presentation
order does not classify governing edges. FD-67 alone determines edge
admissibility. The same repository state and selection produce the same route
ordering. *(A2, F11)*

**FD-73 — Route identity tracks applicability, not document prose.**
A route-support identity changes when its normalized scope, applicable
placements, canonical references, declared layers, governing-placement edges,
placement scopes or member/repository bindings that materially determine that
resolved route change. An unrelated pyramid-member revision that leaves the
complete route closure identical does not invalidate the route merely because the
instance version changed. Canonical document content and status are evaluated
through authority support, not duplicated into route identity. This separation
allows Span to state whether *what applies* changed independently from whether
*an applicable authority itself* changed. *(F1, F11, F12)*

**FD-74 — The projection returns applicable document references, never a copied authority.**
The Functional Pyramid view returns repository-qualified canonical document
references, their placements and layers, route status, the declared/absent layer
summary and unresolved findings. It does not return governing edges, reverse
dependencies, per-path provenance or authority-binding payloads; those are
internal resolution state used by record-time authority support and
reconsideration. A reverse-dependency projection is a separate document-scope
selection under FD-88 and is never part of a directory or semantic-scope answer.
It contains no rule IDs and does not copy, summarize, chunk, embed or cache
document prose. Ordinary evidence admission reads the canonical document when
substantive content is needed. *(G6, F1, F11, L11, L12)*

**FD-75 — Normative support is server-derived from the complete route.**
When a new or revised conclusion has `assertion_nature=NORMATIVE` and its
repository is ACTIVE, Span resolves the complete effective semantic scope under
FD-68–FD-70 before acceptance. Span adds:

- one route-support dependency for that resolved applicability graph; and
- authority-support dependencies for every applicable canonical document.

A participating repository's semantic scope always has at least the
repository-root P0 placement, so no empty-applicability branch is invented. The
caller cannot omit, replace, narrow or mark derived dependencies current. If any
applicable functional route branch is unresolved or an applicable authority is
not currently supportable, the normative conclusion is not currently supportable.
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
Span never computes semantic conformance from document content and source
topology. A human or agent authors the conformance judgment after investigation
and records it as a NORMATIVE conclusion; the public assertion-nature contract
has no third CONFORMANCE value. Span can then establish that the judgment's
empirical dependencies, governing route and applicable authorities are current.
*(G7, F1, F5, L12)*

**FD-78 — Functional Pyramid orientation is available on cold surfaces.**
An unassessed semantic surface may return `Gap/unassessed` while its Functional
Pyramid view is fully resolved. Conversely, descriptive understanding may remain
usable while the Functional Pyramid view contains unresolved governance. The two
states are composed but never collapsed. *(G1, G4, G7, L3, L12)*

**FD-79 — Governance changes are support changes.**
A change to an ACTIVE placement declaration, canonical document
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
No resolver path may invent a placement, document, scope, layer, goal, governing
edge, exception, owner, precedence or repository mapping to complete a graph. The
unresolved relationship is the result until an owning declaration changes.
Absent documentation layers are reported; they are never filled by proximity,
similarity or structural adjacency. *(G1, G7, F5, F11)*

**FD-82 — Functional Pyramid instance identity and membership are explicit and
versioned.**
First activation derives one stable pyramid identity and version 1 from an
accepted activation; the caller does not manufacture that identity. A revision
names the existing identity and expected version and atomically replaces the
complete member intent. Every member names one registered repository and its
exact repository-owned declaration source requests. Participation is
whole-repository. A repository may belong to at most one ACTIVE Functional
Pyramid instance at a time so ordinary repository-scoped `ask` has one
unambiguous governing instance. *(G8, A3, F12, L13, L14)*

**FD-83 — Participation transitions and active health have separate
deterministic owners.**
Durable participation follows lifecycle §7.1 and changes only through accepted
Functional Pyramid record actions. No source, filesystem, installer, model,
`ask`, `reconsider` or hook event performs a hidden participation write.

For an ACTIVE instance, live health is computed from current structural state.
A required ACTIVE declaration source that is missing or cannot be decoded into
the current Version-3 model contributes the FD-71 graph reason
`INVALID_DECLARATION`; in particular, an ACTIVE member that still names a
Version-1 or Version-2 declaration remains ACTIVE but is structurally degraded
until an accepted Version-3 revision. A Version-2 candidate source is rejected as
`INVALID_DECLARATION_SOURCE`. This ACTIVE-state classification is distinct from
candidate validation of a proposed source, which uses
`MISSING_DECLARATION_SOURCE` or `INVALID_DECLARATION_SOURCE`.

- `VALID` iff there is no current structural finding for required member
  availability, declaration validity, placement/document identity ownership,
  document cycles, governing-edge legality including scope containment,
  cross-member resolution, or the required repository-root P0 placement;
- `DEGRADED` iff at least one such structural finding exists.

`FunctionalPyramidStatus.findings` is exactly the current set that causes
DEGRADED health. Authority content/status currency, absent documentation layers
and semantic conclusion support do not degrade graph health. The same ACTIVE
version may therefore move VALID ↔ DEGRADED as current source/member state
changes without a participation write. *(G1, G8, F11, F12, L13–L14)*

**FD-84 — Candidate validation is pure, action-aware, deterministic and complete.**
For one candidate and present repository state, validation returns the same
ordered findings and changes nothing. ACTIVATE validates the complete proposed
member set. REVISE additionally resolves the target pyramid, expected version,
current membership and removals before validating the replacement member set.

Validation has two distinct finding sets.

1. Candidate/lifecycle findings use exactly:
   `UNREGISTERED_MEMBER`, `DUPLICATE_MEMBER`,
   `MEMBER_ALREADY_ACTIVE`, `UNKNOWN_PYRAMID`,
   `STALE_PYRAMID_VERSION`, `MISSING_DECLARATION_SOURCE`, and
   `INVALID_DECLARATION_SOURCE`.
2. Graph findings use FD-71's closed vocabulary for declaration, placement and
   document defects, including `MISSING_ROOT_PLACEMENT`.

Candidate validation classifies declaration-source failure separately from
placement-scope failure. Invalid JSON, an unsupported declaration version, or a
source whose required placement structure cannot be recovered is
`INVALID_DECLARATION_SOURCE`. Once a placement entry's non-scope coordinates are
structurally recoverable, a scope string that fails canonical directory-scope
normalization is instead `INVALID_PLACEMENT_SCOPE` in `graph_findings`; it is
never coerced into a canonical placement and never duplicated as a validation
finding.

Candidate validation decodes each source under the Version-3 contract. A
Version-2 source is `INVALID_DECLARATION_SOURCE`. It validates source-set topology
(exactly one repository-kind source at `.`, area-kind sources at canonical
non-root scopes, unique source identities and scopes), membership/placement
consistency, and typed placement-identity uniqueness before constructing any
deduplicated index. The complete declaring-repository validator owns cross-source
duplicates; source-local validation owns within-source membership and
placement consistency.

Validation requires, for every member, at least one placement with scope `.`
and layer `P0` governed by `ROOT` (FD-86). It validates placement identities,
scope normalization, governing-edge legality including same-repository scope
containment, cross-member references and whole-document declaration sources. It
does not enumerate the repository directory inventory and does not grade
documentation completeness. *(G1, G8, A2, A3, F11, F12, L14)*

**FD-85 — Activation and revision revalidate current source and commit
atomically.**
A Functional Pyramid write never trusts a previous candidate-validation result.
New activation is owned exclusively by governed installation (FD-88A);
MCP may replay an accepted activation, not initialize another instance.
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
transaction decision. In the historical Beta-5 Version-1 → Version-2 cutover, a
REVISE whose current ACTIVE declarations were undecodable solely because they
were Version-1 rule declarations validated the replacement Version-2 candidate
without translating or reconstructing the old graph. Its old-side route effect
root is every retained current normative revision whose existing
FunctionalRouteSupport is bound to the target pyramid identity; those revisions
require re-establishment because a Version-1 rule-route identity cannot be proven
equal to the Version-2 document-route identity. No other declaration defect receives
this cutover treatment, and no Version-1 placement/document graph is fabricated.
The Version-1 → Version-2 cutover treatment is specific to Version 1. A
Version-2 ACTIVE source that cannot be decoded under Version 3 becomes `DEGRADED`
through the ordinary health mechanism, and a replacement Version-3 candidate is
accepted without translating or reconstructing the Version-2 graph. Declaration
organisation or version change alone does not invalidate retained routes; the
existing effective route-change and support mechanisms remain authoritative.

The immutable receipt retains the durable participation
and dependent-effect coordinates; the public result projects them through the
same `ChangedSurface`/affected-conclusion carriers used by `reconsider`.
Exactly one repository-bound live re-establishment context is issued for each
repository with an actionable effect. The immutable receipt/effect set is the
accepted revision/surface/cause coordinate set, not a frozen live
`ChangedSurface` status snapshot. On replay, Span keeps those immutable effect
identities unchanged, re-evaluates only those retained revisions against current
support/membership state, returns live actionable effects and explicit
verified dispositions under P2 §4.3, and issues contexts only for remaining
actionable effects. Unavailable owner or membership remains outstanding.
It never discovers additional accepted effects from later governance state.

Activation/revision stores only the identities, relationships, source identities,
placement scopes and layer assignments needed to reproduce resolution; canonical
document content is never stored as pyramid content. Revision/deactivation remain
compare-and-set on the target pyramid version, and activation/revision atomically
enforce one ACTIVE pyramid per repository. *(G3, G6, G8, A2, A3, F1, F4, F12,
L4, L14–L15)*

**FD-86 — Root-totality validation and layer-summary derivation are
deterministic.**
Candidate validation and ACTIVE health evaluate one root-totality predicate per
member: the declaration graph contains at least one placement with scope `.`,
layer `P0` and governing relationship `ROOT`. Failure contributes exactly
`MISSING_ROOT_PLACEMENT`. The check inspects declarations only and never
enumerates repository directories.

For any returned Functional Pyramid selection, first resolve the complete
placement closure under FD-68. Let `declared_layers` be the ordered unique set
of layers present in that complete closure, using FD-72's fixed presentation
order. Let `absent_layers` be the complement against
`P0, P1, P2S, P2W, P3, P4`. For a multi-path semantic scope, both summaries are
computed over the unioned closure after placement deduplication; they are
aggregate selection summaries, not a claim that every provenance path contains
every declared layer. Per-path applicability remains represented by route
provenance.

An absent layer contributes no unresolved reason, support failure or health
finding by itself. A malformed placement scope is classified by FD-84 before
root-totality evaluation and is not coerced into a missing-root result.
*(G1, G4, G7, G8, F11, F12, L13)*

**FD-87 — Membership is resolution reachability, never applicability.**
Adding a repository to an instance makes its stable declared identities
resolvable from other members. It adds no placement or document to another
repository's route unless a placement declared by that repository or an explicit
governing relationship makes it applicable. Removing or losing a member
preserves the external identity in affected routes as unresolved; it never
silently drops the relationship. *(G1, G7, G8, F11, F12, L13)*

**FD-88 — Governing traversal is bidirectional over one declared graph.**
Upward orientation follows directory or scope → placement → governing placement
to ROOT under FD-68. Reverse traversal identifies direct and transitive
dependent placements through the same internal graph for reconsideration and
accepted governance changes. The compact directory and semantic-scope answers
do not expose the reverse index, internal routes or provenance. A separate
public document-impact selection is deferred until an explicit consumer requires
it (TD §17.1); it is not a current acceptance requirement. Any future impact
view is non-predictive navigation over this same graph, not a second registry. *(G3, G7, F4, F11, L15,
L16)*

**FD-88A — Governed initialization establishes the Functional Pyramid from the
repository-supplied input.**
Decode the complete member set under lifecycle §7.1 through the sole governed
initialization ingress. Rows are unique per declaring repository and canonical
document identity (FD-66). The declaring repository is the file's selected member;
the canonical document owner may be another selected member. Shared documents
may have one placement per declaring repository, with one consistent authority
kind/status for their canonical document identity. A document whose statements
span several layers or scopes within one declaring repository is split or
extracted by its owner before classification. Reject unknown, ambiguous,
incomplete, conflicting or unreadable inputs; never infer missing semantic or
authority decisions. Resolve each governing reference against exactly one
declaring-repository/document pair across the complete selected member set.
Every selected member must satisfy FD-66/FD-86, including a member with no place
rows. The single JSON ingress must express existing shared placements; a raw
declaration or manual activation path is not an alternative initializer.

Derive repository-kind and area-kind sources, document membership, one
placement per document, governing coordinates, ordering, one whole-document
authority binding per distinct placed canonical document and exact navigation/member-intent references.
For a newly derived binding use the document's repository and locator, no
section/span, the supplied kind/status, empty applicability and no declared
precedence. A unique existing whole-document binding that already satisfies
the declared semantics is reused with its existing evidence identity and
ownership; initialization must not replace it merely to obtain a generated
identity. Validate the complete graph and binding coverage before mutation.
An exclude row creates no placement or derived authority binding. Preserve
ordinary authority outside the derived placed set. Remove a formerly derived
binding whose placement is removed only when its derivation ownership is
established; do not revoke independently owned authority because the document
is excluded or omitted. A competing whole-document binding, or uncertain ownership where a
replacement/removal is required, is a conflict rather than silent replacement.
A section/span binding cannot satisfy a whole-document placement; independently
owned section/span bindings may coexist with its unique whole-document binding
and remain untouched, as the existing canonical resolver permits. The existing
lower-level authority and declaration contracts are not narrowed by initialization.

Administrative validation of explicitly supplied authority is exhaustive,
repository-qualified and independent of evidence-delivery bounds (FD-54).
This applies equally to ordinary authority seeds/bindings and derived or
reconciled governed bindings. Validate every requested locator and identity
before setup mutation, preserving seed resolution, binding identity, section/
span and ordinary preserve/clear/replace semantics. A valid configuration
cannot be rejected or shortened because it exceeds an agent-facing evidence
page. Name actual missing, unreadable, foreign or conflicting authority; a
provider failure remains an operational failure, not an unknown locator.
There is no fixed administrative capacity ceiling on the number of valid
authority locators, bindings or governed document placements per repository
or selected member set imposed by an evidence-delivery budget. The complete
owner-supplied configuration is the validation and registration unit, even
when it contains thousands of entries. No raised or configurable query cap,
operator batching, omitted placement or reduced governance coverage is a
supported solution. Genuine resource/provider failure remains an explicit
operational failure, never evidence that a locator is missing. Reject invalid
authority during preflight before publishing pending intent, generated
declarations or changing registered state; a subsequent operational failure
follows the recoverable setup contract below. Keep agent-facing retrieval
bounds unchanged (FD-54).

Administrative invocation compatibility is decided before consulting mutable
installation state or performing setup effects. Reject incompatible supplied
options by naming the user-visible options, why their combination is invalid
and the supported way to proceed. Operational preflight and semantic
validation retain their respective owners. Installation verification establishes
the identity of the actually installed runtime independently of the requested
source or package version. An unknown or inconsistent identity cannot establish
that the requested build is installed; identify the uncertainty and supported
correction without substituting requested identity for observed identity.

Administrative results and guidance expose the outcome, affected user-selected
repository or input, actionable cause and permitted next operation. Apply
FD-27's diagnostic boundary to these user-facing surfaces: internal exception
text, graph reason codes, private generated paths and recovery bookkeeping are
not remedies. An operator may receive the exact public option, supplied document
reference, observed build identity or supported recovery artifact reference
needed for the next action; those coordinates are not a new agent API or
semantic authority. Private recovery receipt contents remain owned by the
installer and are never a caller-authored input.

Select ACTIVATE for a fresh eligible explicitly selected member set. For the
same complete member set of one existing ACTIVE instance, select REVISE when
the requested and actual applied canonical governance configurations differ,
including registered binding changes; verify an identical applied configuration
without a new participation version. Input byte order/format changes alone are
not a governance delta. Repair an operationally degraded identical state before
claiming success; an actual binding change requires the same affected-support
projection as any other governed revision. A partial active-member selection or members belonging to
different ACTIVE instances fails; a member-set change requires its own explicit
lifecycle intent. A Version-2 ACTIVE instance is revised, never re-activated.

Run the existing candidate/write path and verify the exact accepted state.
Capture the old/new registered authority delta before provisioning changes the
bindings and include its affected conclusions in the accepted write's FD-89
projection. Authority-only changes can affect support without changing route
identity or structural health (FD-12/FD-73); unchanged support is not forced
stale. A failure is not successful initialization; retain the exact pending
intent, affected-binding evidence and accepted receipt identity needed for
recovery, and report actual operational state and outstanding obligations.
Re-running the same input does not duplicate an accepted write. Never create
semantic conclusions to clear effects.

If an unaccepted pending operation cannot complete with the same input,
explicit authorized recovery to its verified pre-setup state is the alternative
to resumption, not another initialization route. Recovery owns the entire
administrative effect of that pending setup: previous receipt, stores, registered
authority, and repository-local generated artifacts. Restore previous owned
metadata and absence where applicable; retire only exact artifacts proved
created by the abandoned operation. Preserve independently owned or modified
content, previous accepted sources, and retained semantic/receipt obligations.
If ownership, prior bytes, absence or absence of competing semantic writes
cannot be proved, report a recovery conflict before destructive mutation.
An authorized restore must not strand generated artifacts without ownership
evidence, require an operator to reconstruct that evidence, or report success
while receipt, stores and generated metadata disagree. A fresh installation
has a recoverable pre-setup state even when no store previously existed.
Recovery is limited to the pending setup's attributable effects, not every
store captured by a full backup. Preserve unrelated stores and independent
accepted state within shared stores; inability to establish the permitted
state is a conflict. Exclude competing runtime and administrative writes
continuously from recovery eligibility through final publication, including
removal of a previously absent store. Interruption at each durable boundary
remains recoverable without a new participation write.
For an already accepted pending participation, resume/replay the accepted
intent and preserve its immutable dependent-effect references; abandoning an
unaccepted operation is not permission to roll back an accepted semantic write.
*(G7, G8, F1, F4, F7, F11, F12, L4, L11–L16)*

**FD-88B — Runtime results expose only the public governance reasons.**
The public Functional Pyramid result carriers (`FunctionalPyramidView.unresolved`,
`FunctionalPyramidStatus.findings`, `FunctionalPyramidCandidate.graph_findings`)
use one public finding: `reason`, `detail`, `recovery`, optional
`repository_id`, optional `directory` and optional `placement`. The public
governance reason vocabulary is exactly `DECLARATION_INVALID`,
`DOCUMENT_SET_INCOMPLETE`, `DOCUMENT_UNAVAILABLE`, `DOCUMENT_AMBIGUOUS` and
`GOVERNANCE_UNAVAILABLE`. Candidate lifecycle findings add the five public
lifecycle reasons below; the public reason enum is their union, with
`DECLARATION_INVALID` shared.
The internal FD-71 reasons map as follows and are never serialized:

| Internal FD-71 reason | Public reason |
| --- | --- |
| `INVALID_DECLARATION`, `INVALID_PLACEMENT_SCOPE`, `DOCUMENT_SCOPE_MISMATCH`, `INVALID_DOCUMENT_REFERENCE`, `NONCANONICAL_DOCUMENT_AUTHORITY`, `DOCUMENT_CYCLE`, `INVALID_GOVERNING_EDGE` | `DECLARATION_INVALID` |
| `MISSING_AREA_DOCUMENT`, `UNLISTED_AREA_DOCUMENT`, `UNKNOWN_DOCUMENT`, `UNRESOLVED_DOCUMENT_PARENT`, `MISSING_ROOT_PLACEMENT` | `DOCUMENT_SET_INCOMPLETE` |
| `DOCUMENT_UNAVAILABLE` | `DOCUMENT_UNAVAILABLE` |
| `DUPLICATE_DOCUMENT_PLACEMENT`, `DUPLICATE_DOCUMENT_SOURCE`, `DUPLICATE_DOCUMENT_LAYER`, `DUPLICATE_DOCUMENT_SCOPE`, `AMBIGUOUS_DOCUMENT_AUTHORITY` | `DOCUMENT_AMBIGUOUS` |
| `REPOSITORY_UNAVAILABLE`, `MISSING_DOCUMENT_AUTHORITY` | `GOVERNANCE_UNAVAILABLE` |

Candidate lifecycle findings use the public lifecycle reasons
`UNREGISTERED_MEMBER`, `DUPLICATE_MEMBER`, `MEMBER_ALREADY_ACTIVE`,
`UNKNOWN_PYRAMID` and `STALE_PYRAMID_VERSION`; missing or invalid declaration
sources project to `DECLARATION_INVALID`. The internal
`MISSING_DECLARATION_SOURCE` and `INVALID_DECLARATION_SOURCE` are never
serialized. `declaration_locator`, internal reason enums, route and provenance
state, health internals and authority payloads are never serialized. Retain
exact declaration refs only in justified accepted receipt audit; status
projects member IDs, candidate projects validation outcomes. Map nested
public locations using FD-62. The internal per-finding declaration locator
is not serialized.
`detail` and `recovery` are public and must not contain an internal reason code
or internal locator. The unavailable carrier's `failure` and `recovery` use the
same public vocabulary.

The projection happens at the service boundary; the serializer emits only public
carriers. A conformance test asserts that the wire schema contains no internal
finding carrier, internal reason enum or declaration locator, and the
installed-MCP journey asserts that only public reasons are returned. *(G1, G7,
F11, L12)*

**FD-88C — A truncated directory list is resumable through the public selector.**
When the ordered placement list exceeds the response budget, the view returns the
fitting prefix, `truncated=true`, one constant omission statement and a public
continuation token. `FunctionalPyramidDirectorySelector` accepts that token and
returns the next deterministic page for the same directory and selection.
Unresolved status is never dropped; if findings cannot fit, page the complete
finding set explicitly under FD-55–57. The token is opaque, versioned and bound to the
original addressing repository/directory, resolved repository/directory,
root basis and projected path bindings, selection and declaration version;
changes to that binding invalidate the token.
It carries no internal route, provenance or authority state. *(A7, A8, G1, L12)*

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
the exact effective semantic scope already selected for the Answer/Gap. A FILE or
SYMBOL member maps to the directory containing its locator; a SERVICE or DOMAIN
boundary member maps each declared path to that directory boundary unless the
existing canonical semantic-containment owner classifies it as an exact file or
symbol locator, in which case its containing directory is used; a
repository-wide selection uses every placement. For a directory selector it is
resolved from that exact directory as a point in the repository tree.
Descendant-only placements do not apply to their parent directory. Question
text, embeddings, similarity, document genre and source prominence never expand
either selection. The view returns every declared document placement applicable
through the selected scopes. *(G4, G6, G7, F9, F11, L12, L16)*

**FD-91 — Participation, health, route and support state remain independent.**
An ACTIVE pyramid can return only the declared ancestor layers for a directory
while its live health remains VALID. An ACTIVE pyramid with DEGRADED health can
still return RESOLVED routes for unaffected scopes. A structurally RESOLVED route
can still yield non-current normative support because an applicable authority is
draft, superseded, unavailable or changed under FD-12. Durable participation,
live pyramid health, per-scope route resolution and conclusion support are never
used as shortcuts for one another. *(G1, F1, F2, F12, L13, L16)*

**FD-92 — Functional Pyramid lifecycle projections never become semantic
understanding.**
Status, candidate validation and receipt retrieval are lifecycle projections over
declared/persisted pyramid state. They never create an Answer, conclusion,
investigation context, document meaning or authority. Ordinary semantic obtain
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
Ordinary repository initialization registers the canonical root and leaves
participation unchanged. Explicit governed initialization is FD-88A; it owns
mechanical establishment of the requested instance, not merely registration.
The source of governance remains the owner-supplied classification and
canonical documents. Hooks observe the result; they never perform setup or
participation writes.

At session start/resume/compact, canonical participation and live health select
only the Functional Pyramid obligation: UNCONFIGURED directs governed use to the
initialization/status path; EXCLUDED has no initialization obligation and
ordinary descriptive semantic work remains available; ACTIVE/VALID adds no
separate Pyramid action beyond ordinary governed orientation; ACTIVE/DEGRADED
reports governance attention and the next existing lifecycle action.
ACTIVE/DEGRADED means ACTIVE participation with DEGRADED live health, not a
fourth participation state.

Observational installation verification follows the same obligation rule,
composed with actual store readiness, declaration/graph validity, installation
provenance and pending administrative recovery. A verified ACTIVE/VALID
installation with matching required provenance and no pending intent has no
initialization obligation. Pending setup reports the existing recovery
obligation; degraded or mismatched ACTIVE state reports the actual repair;
EXCLUDED does not request activation; unavailable state names the operational
blocker; only eligible UNCONFIGURED governed use requires initialization.
Verification must not equate registration, successful structural setup or
semantic currency with each other, invent a participation state, or perform
a write. Guidance is a projection of observed facts, never an unconditional
request to install. Observe each relevant ACTIVE instance with its complete
retained membership; never combine independent instances as one graph.
Incomplete observation is not healthy. Pending acceptance is not completed
installation: a finalized receipt and subsequent observation must agree for
the same committed state, without prematurely clearing recovery.

For an external edit/write, the same canonical changed-scope projection decides
semantic, authority, route, premise, containment and cross-repository effects;
the hook does not first classify the edit as semantic versus governance work.
The resulting obligation may therefore be semantic-only, Functional-Pyramid-
related only, both, or neither while still routing through the existing public
lifecycle. An accepted Functional Pyramid activate/revise/deactivate write is
different: its `FunctionalPyramidRecorded` result already owns the canonical
dependent effects and re-establishment contexts, so a hook does not recompute
those effects or require a second `reconsider` for that write.

Hooks never activate/revise a pyramid, author document meaning, copy document content,
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
Authority currency never establishes the semantic truth of the governing document.
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
Project each finding from its typed dependency, not its diagnostic string:
source → admitted evidence identity/ranges and captured time; discovery →
recorded repository/scope/time; authority → all recorded semantic binding
facts; premise → exact revision; route → recorded repository/pyramid/scope. Audit projects all retained dependencies by the same rule.
If required historical coordinates cannot be recovered, retain the typed
unavailable basis and reason; do not infer authority or invent evidence.
Qualification and audit preserve dependency multiplicity and order where
meaningful, without private identity or fingerprint leakage. *(F2, A8)*

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
a surface owned by another member repository reached through FD-89. Entries are deduplicated by repository + surface identity. Track direct and
indirect causes by exact revision before grouping; containment-only surfaces
may have no affected revisions. Aggregate causes plus containment separately
at surface level. Traverse every reachable current and historical dependency
to a fixed point with cycle detection before limiting delivery. Retain the full
affected current-revision set and per-owner context requirements; processing
interruption returns Unavailable with exact original changed-scope retry;
no partial Changed, no cursor for an undiscovered set, no contexts from a
failed traversal. Participation precommit failure aborts atomically. Retry
is a new complete analysis; previously delivered completed selections remain
recoverable independently. Inclusion is not a verdict:
each affected conclusion carries its own support state, so a considered
conclusion may remain `CURRENT`. *(F4, L10)*

**FD-21 — Ordering is deterministic.**
Surfaces are ordered narrowest to widest, then by identity; conclusions within a
surface are ordered by their recorded sequence. The same change produces the same
order. *(A2, L10)*

**FD-22 — Unaffected is bounded and explicit.**
A surface may be reported unaffected only within the examined boundary. An interrupted walk follows FD-20; it reports neither unaffected nor
discharged obligations.
Delivery paging never sets dependency traversal depth/node limits.
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
and present state, alongside the count. Immediate child summaries are separate from selected membership; retrieve
their refs by exact surface ask. Neither view auto-withdraws or rewrites history; recovery is an
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
documents. Functional Pyramid documents remain at their canonical owners and are
referenced by the accompanying pyramid view rather than copied into the surface
document view. Its contents are fixed in `lifecycle-contract` §4.1.
*(G6, F11, L11, L12)*

Pure surface obtain groups all Answer-eligible membership by recorded question
metadata and reports current CAPTURED membership separately as pending
curation.
`RecordedQuestionSelector` restricts membership to one exact recorded question
on one exact surface; current identity selectors restrict membership to one
returned understanding identity. All three reuse forms use the same composition,
issue no context and require no request identity. Construct StatusSubject from
resolved selector and exact version, then calculate its membership only.
Ordinary surface obtain computes own boundary coverage and immediate contained
surface distributions; choose immediate by strict containment with no
intervening declared surface, not parent pointer; stable order by SurfaceKey.
Select verification runs whose declared scope covers every path/reference of
selected semantic scope; repository-wide scope requires repository-wide run.
Group by normalized declared scope, exact description, command, scenario and
ordered normalized environment limitations. Evaluate candidates once using
existing evaluator. Union max observed_at among all runs in each group and
max observed_at among CURRENT runs for each outcome in that group; keep all
ties, dedup by run ID. Sort group keys then descending observed_at and run ID.
All other applicable runs ordered identically form history. Never infer a
later PASS resolves an earlier still-CURRENT FAIL; retain both. Distinguish
non-current/unavailable latest runs from supported outcomes. For exact audit resolve the pinned
version's exact revisions and curation as of that version; select only challenges
targeting that version and label present challenge disposition and live support.
Retrieve receipt effects by accepted identity, never current snapshot membership.
Their role as the reuse paths
is stated in `lifecycle-contract` §4.1. *(G2, F3, A4, L11)*

**FD-29 — Result ordering is stable.**
The selected subject, classification and mandatory qualification or
participation/unresolved summary precede collections. Deliver the primary
consumer result first (semantic conclusions, requested evidence, exact audit,
validation findings or affected obligations), then necessary recovery refs and
auxiliary status/verification/history. Group current conclusions by question;
do not evict them to retain unrelated descendant/verification inventory.
Mandatory governance is complete or explicitly unresolved/incomplete with
continuation; never imply applicability completion. Functional Pyramid internal ordering
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
Any transition that invalidates a premise must name affected dependents in
the same result, recoverably paged under FD-55. Derive exact accepted revision
effects from applied actions at transition time: create/add/correct/replace/
withdraw/confirm name resulting refs, replace retains predecessor, curation
names accepted target, no-op confirmation names unchanged ref with no mutation.
Gap-only/disposition-only transitions produce no revision effect. Retain those
facts and accepted challenge disposition revisions in the same receipt
transaction; replay never substitutes later membership or disposition.
Challenge opening projects exact disputed retained content and basis from
the target version, with accepted challenge and context. *(F4, L4, L10)*

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
suspension, so a caller that can resume can recover its identity. Completed
change selections and receipts with outstanding actionable effects also
retain their exact immutable obligation coordinates until disposed. Reaping
requires both elapsed replay retention and no outstanding obligation; if
qualification cannot be established, do not reap. No new arbitrary duration. That lower
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
owner. Pure-read and evidence delivery use the context lifetime as specified
by lifecycle §4.1; completed change/accepted effect selections follow FD-43.
Delivery recovery is by issued selection/position, not caller reconstruction.
*(A1, A2, F4, L7, L10)*

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

Host reachability is established only for the intended installation's complete
L8 lifecycle surface, not a registration entry, a partial catalogue or a
previously successful connection. Changed or unavailable host delivery must
not be presented as ready. Where delivery cannot be established, the
user-facing notice identifies the unavailable lifecycle capability and the
supported reconnect/restart action; it does not expose host transport internals
or require the agent to manage them. The host owns connection and catalogue
management; FD-52 and FD-53 remain binding.

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
with the delivered result. Apply encoded-size fitting to every result family,
including installation operations and writes, independently of semantic
evaluation and commitment. *(F7)*

**FD-55 — Truncation is explicit and recoverable.**
For lifecycle §4.1 ResultPage, evaluate full selection once, order via FD-29
and domain ordering, bind exact immutable semantic keys plus live-state
signature (excluding clock-only variation). Select maximum fitting prefix of the first remaining pageable collection,
advance by exact offset or evidence range; visit independently pageable
public nested collections immediately after their parent before later
siblings. Use lifecycle §4.1's recorded-fact and nested-collection boundaries;
never manufacture a partial retained record, or classify a variable collection
as one indivisible fact to avoid recoverable delivery.
Always include required parent/owner and context coordinates. Initial Answer
must contain usable conclusion content, not merely an auxiliary collection;
continuation never returns Answer. If primary unit cannot fit, apply FD-57.
Every delivered item belongs exactly once to the selected ordered sequence
except required scalar parent/context references. Keep selection and issued
positions immutable; repeat cursor yields same slice under unchanged binding.
For pure read changes reject stale binding; for accepted/completed effects
retain immutable keys and re-evaluate only those refs, report disposed/
superseded ones without erasing their position. Recreate expired contexts
only for still-actionable owners. Evidence page uses original outcome order,
and deduplicates delivery only by exact observation/range, not by locator;
later context additions do not change order or membership. Retention follows
FD-43/45; no new semantic evaluation or write on continuation. *(A8)*

**FD-56 — Truncation never substitutes stale content.**
A budget limit never promotes historical content into answer content and never
omits the fact of truncation. Preserve support/maturity/route state and
full-population counts; incomplete unresolved findings or obligations remain
explicitly incomplete, not empty success. *(F2, A7)*

**FD-57 — A result too small to be safe is refused.**
Reserve result classification, exact subject, required qualification,
participation/route state, accepted identity/receipt (if committed), and
recovery indication before fitting collections. If a pure query cannot carry
one required unit and safe envelope, refuse with supported narrower selection
or other real recovery; never suggest raising a hard gate. Refuse a new write
whose acceptance envelope cannot fit before mutation. After commit retain
acceptance and receipt even when live detail is unavailable. No arbitrary new
budget or change to semantic traversal. *(A7, A8, G1, L4, L12)*

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

**FD-60 — Accepted understanding reports exact accepted effects.**
After commitment qualify only accepted resulting supported revision refs
(including accepted no-op confirmation), using the single evaluator. Read
curation at accepted version; withdrawal has neither maturity nor reusable
verdict. Operational failure preserves accepted effect with SupportUnavailable.
Report canonical surface identity, no owner-wide or recursive status; ask owns
surface status. Store immutable acceptance facts, not live qualification.
*(F9, L4, L17)*

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
   pyramid/version replacement return deterministic validation and placement-graph
   findings, change no durable participation state, and set `activation_ready`
   exactly from the closed blocker conditions. Governing-edge validation uses the
   same FD-67 relation later used by ACTIVE health and ordinary route resolution.
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
5. **Root totality.** Activation is impossible without at least one placement
   whose scope is `.`, whose layer is `P0` and whose governing relationship is
   `ROOT`. With that placement present, the repository root, every nested
   directory and a newly created directory each return at least the foundational
   placement. No directory returns an empty governing projection.
6. **Inheritance without per-directory declaration.** A directory with no own
   placement returns the placements declared at its ancestor scopes, including
   root. Creating that directory does not require a declaration, does not change
   health and does not produce an uncovered or incomplete state.
7. **Degraded-health recovery.** Member/declaration/structural unavailability
   makes ACTIVE health DEGRADED; unaffected routes can still resolve; restoring
   current declaration and document availability returns health to VALID without a
   participation write.
8. **Cold governed path.** `ask(FILE)` on an ACTIVE member returns
   `Gap/unassessed` plus the Functional Pyramid view without generating
   semantic understanding.
9. **Directory obtain.** `FunctionalPyramidDirectorySelector` accepts the
   repository root and every existing repository-relative directory without a
   semantic surface declaration. It returns every placement whose declared scope
   contains that directory.
10. **Same semantic scope.** The governing view is resolved from the exact
    semantic scope selected for Answer/Gap; natural-language question text,
    embeddings, filename similarity and document genre never expand governing
    applicability.
11. **Additive composition.** One directory matching a repository-wide placement,
    a project placement and a local placement returns all of them and the union
    of their governing documents; no most-specific-wins behavior occurs.
12. **Sibling and descendant exclusion.** Directory lookup excludes
    sibling-only and descendant-only placements while retaining every containing
    ancestor scope and the repository root.
13. **Disconnected scope and unique placement.** Distinct documents placed at
    unrelated scopes apply only to their declared scope and its descendants.
    Repeating a canonical document in multiple scopes/layers of one declaring
    repository is invalid under FD-66.
14. **Multi-path and broad semantic scope.** Resolution unions placements across
    path-derived directories while preserving per-path provenance internally. The view's
    `declared_layers` is the ordered union of layers in that complete route
    closure and `absent_layers` is its fixed-layer complement; neither summary
    is interpreted as per-path completeness. A repository-wide semantic
    selection returns every placement rather than an invented file list. This
    case is distinct from the exact directory selector in cases 9, 11 and 12.
15. **Membership is not applicability.** Adding another repository to the
    pyramid changes no route unless a placement declared by the queried
    repository or an explicit governing relationship makes that member relevant.
16. **Cross-repository authority.** With the referenced member available, a local
    directory resolves external governing documents by canonical reference. With that member
    unavailable, the same relationship is `REPOSITORY_UNAVAILABLE`, not
    `UNKNOWN_DOCUMENT` and not silently discarded. Applicability scope remains
    local to the declaring repository.
17. **Document and placement defects.** Unknown documents, duplicate placements,
    document cycles, invalid governing edges, invalid placement scopes and
    missing required parents are explicit unresolved states. A placement entry
    whose non-scope coordinates are structurally recoverable but whose scope
    fails canonical normalization appears exactly once in candidate
    `graph_findings` as `INVALID_PLACEMENT_SCOPE`, never as a validation
    finding. A same-repository governing edge whose scope is narrower than the
    governed placement's scope is `INVALID_GOVERNING_EDGE`. An unresolved parent
    is never accepted as a valid derivation edge. The acceptance surface proves
    FD-67's permitted contract-sublayer derivation and rejects its reverse and
    same-sublayer prohibited cases as `INVALID_GOVERNING_EDGE`.
18. **Route versus authority currency.** A structurally complete route can remain
    RESOLVED while an applicable authority is DRAFT/SUPERSEDED/changed and
    normative support becomes non-current through authority support.
19. **Normative create.** The caller supplies semantic intent and empirical
    evidence; Span derives route and every applicable authority dependency.
    Omitting governance is impossible through the public grammar. If those
    derived governance dependencies are unresolved/non-current but the semantic
    request is otherwise valid, the revision is retained with non-current
    qualification and is not served as CURRENT Answer content.
20. **Descriptive create.** A descriptive conclusion remains source-supported
    without automatically becoming normative merely because a pyramid route
    exists.
21. **Authority-content change.** Changing an applicable canonical document without
    changing route topology requires reassessment through authority support while
    route identity can remain unchanged.
22. **Applicability change.** Changing a placement's scope, layer, document
    identity, governing edges or material member bindings requires reassessment
    through route support even when implementation/document content is unchanged.
23. **Internal reverse dependency traversal.** Reconsideration and participation
    changes use the same reverse graph to reach dependent placements and
    conclusions; ordinary directory and surface results do not expose that
    internal state. No separate public impact selector is required for current
    acceptance (FD-88).
24. **Cross-repository reconsideration.** A governing change in repository A
    returns affected normative understanding in repository B when the same
    pyramid document relationships connect them; the caller does not enumerate B. The Changed
    result returns exactly one repository-bound re-establishment context for A
    and/or B wherever that repository has actionable affected conclusions; no
    cross-repository context is created.
25. **Implementation change.** Existing source/discovery/premise propagation
    remains intact and does not depend on the Functional Pyramid being the cause.
26. **Mixed answer.** A current descriptive conclusion can be returned while its
    pyramid route is unresolved; a normative conclusion depending on that route
    cannot be returned CURRENT.
27. **Canonical-source singularity.** Pyramid state/view/storage returns whole
    document references, placements, layers and relationships but no rule IDs,
    rule anchors, copied summaries, chunks or canonical document content.
28. **Runtime lifecycle preservation.** Every existing Span runtime path in
    lifecycle §7.2 remains exercisable with its pre-Version-1 semantic behavior:
    current reuse without duplicate record, gap → investigate → conclude/record,
    external edit → reconsider → investigate when needed → re-establish,
    dispute → disposition, start/resume and completion. Functional Pyramid behavior is additive at those
    same moments and introduces no second ordinary-development lifecycle.
29. **Governance-source edit lifecycle.** Before editing a canonical document,
    the separate document-impact selection makes the current downstream document
    relationships obtainable; after the edit, reconsider
    reports cross-repository authority/route effects and record closes the
    affected dispositions.
30. **Lifecycle-compliance hooks.** Session start/resume/compact exercises
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
31. **Initialization handoff.** Governed initialization verifies exact committed
    pyramid identity/version/member view, live health VALID, readiness and
    provenance; no caller-managed activation or undefined route sample is
    required (FD-88A).
32. **One active instance per repository.** Attempting to activate/revise a
    member already ACTIVE in another pyramid produces
    `MEMBER_ALREADY_ACTIVE` and cannot create ambiguous repository-scoped
    governing orientation.
33. **Three-tool host surface.** Governed initialization uses the existing
    administrative entry and canonical participation writer; governed runtime
    and re-alignment use `ask`, `record`, `reconsider`. No new MCP tool exists.
34. **No uncovered answer.** Every directory in an ACTIVE repository returns a
    Functional Pyramid result. A directory whose only applicable placement is the
    repository root returns that placement. `UNCOVERED_PATH`,
    `OUTSIDE_FUNCTIONAL_SCOPE` and an empty governing projection are not
    producible outcomes.
35. **Explicit scope, no placement inference.** A canonical document that sits
    under `docs/` does not govern `src/` unless a placement declares that scope.
    Moving a document without changing its declaration changes no route; changing
    a declared scope changes every affected route and its normative dependents.
36. **Health iff structural findings.** ACTIVE health is VALID exactly when the
    FD-83 structural finding set is empty and DEGRADED exactly when it is
    non-empty; authority currency, absent documentation layers and ancestor-only
    resolution do not change health.
37. **Activation of pre-existing normative understanding.** A repository with a
    retained NORMATIVE revision recorded before ACTIVE participation is activated;
    that revision is returned as a direct dependent effect and becomes
    REASSESSMENT_REQUIRED until re-established with server-derived governance
    support.
38. **Functional Pyramid write propagation.** ACTIVATE/REVISE/DEACTIVATE return
    the same canonical affected-surface/conclusion projection used by reconsider,
    plus exactly one repository-bound re-establishment context per repository
    with actionable effects.
39. **Deactivation/removal route state.** A revision with recorded route support
    whose repository becomes UNCONFIGURED or EXCLUDED is
    REASSESSMENT_REQUIRED, not UNVERIFIABLE merely because participation ended.
40. **Operational route failure while ACTIVE.** An ACTIVE repository whose
    required route/member/declaration state cannot presently be evaluated is
    UNVERIFIABLE; deliberate participation change and operational unavailability
    remain distinct.
41. **Pyramid-write replay projection.** Replaying an accepted Functional
    Pyramid write preserves the immutable participation state and accepted
    dependent `ConclusionRevisionRef` set, re-evaluates only those refs into a
    live actionable projection and verified effect dispositions, with fresh
    contexts only where the retained effect is actionable now;
    it never adds effects from later governance state.
42. **Pyramid concurrency.** Concurrent revise/deactivate operations obey pyramid
    version compare-and-set, and concurrent overlapping activations/revisions
    cannot make one repository ACTIVE in more than one instance.
43. **External governance edits use ordinary re-alignment.** External edits
    remain subject to changed-scope reconsideration; generated initialization
    effects are disposed through their canonical owners without requiring a
    manual declaration-authoring phase or duplicating participation effects.
44. **Conformance uses the normative input contract.** A conformance judgment
    is recorded with `assertion_nature=NORMATIVE`; in an ACTIVE repository it
    receives the same server-derived route/authority support as every other
    normative conclusion, and no third assertion-nature branch exists.
45. **Acceptance is not runtime completion.** An otherwise-valid NORMATIVE
    create/update whose derived governance is non-current returns
    `UnderstandingRecorded` with REASSESSMENT_REQUIRED/UNVERIFIABLE
    qualification, but the agent runtime cannot transition to successful
    COMPLETE until the required disposition becomes CURRENT; post-commit
    qualification unavailability likewise remains an explicit recovery/blocker.
46. **Participation-write acceptance is not initialization completion.** An
    accepted ACTIVATE/REVISE/DEACTIVATE that returns actionable dependent effects
    supplies their canonical update coordinates and per-repository contexts; the
    initialization/revision/deactivation procedure must dispose those effects
    before successful completion, without calling reconsider again for the
    participation write itself.

47. **New capture is not shared reuse.** A newly recorded supported conclusion is
    CAPTURED and absent from ordinary Answer content even when support is CURRENT.
48. **Pending-capture gap.** A surface with CURRENT captured knowledge but no
    CURRENT + CURATED conclusion returns `Gap/pending_curation` and exact
    pending revision references.
49. **Pending-curation discovery.** Repository pending-curation obtain returns
    exactly the deterministic CURRENT-support, current-membership revision set
    lacking curation and resumes by the exact revision keyset cursor.
50. **Curation does not rewrite or bypass support.** Curation accepts only a
    CURRENT exact revision, advances understanding history, and records an
    immutable disposition without creating a conclusion revision or changing
    semantic content/support; a non-current target is rejected for
    re-establishment first.
51. **Curated reuse.** The exact CURRENT revision becomes ordinary Answer content
    after accepted curation.
52. **Curation cannot override later support loss.** A previously CURATED
    revision that becomes REASSESSMENT_REQUIRED/UNVERIFIABLE is not Answer
    content and does not lose its curation history.
53. **Correction resets curation.** Correcting curated meaning creates a new
    CAPTURED revision.
54. **Replacement resets curation.** Replacing curated meaning creates a new
    CAPTURED lineage/revision.
55. **Addition begins captured.** Adding a new lineage to an understanding does
    not inherit sibling curation.
56. **Confirm preserves curated meaning.** A semantically unchanged support-only
    confirm of a CURATED predecessor inherits curation with explicit inherited
    provenance.
57. **Confirm does not invent curation.** Confirm of a CAPTURED predecessor remains
    CAPTURED.
58. **Withdrawal is never reusable.** Withdrawal remains explicit history and
    cannot acquire curation.
59. **Curation is a separate act.** A curation action cannot be combined atomically
    with create/add/confirm/correct/replace/withdraw semantic mutation.
60. **Curation is not governance.** Curation changes no Functional Pyramid
    participation, health, applicability, route or authority support.
61. **Normative reuse requires both planes.** A normative revision is Answer
    content only when CURRENT under its empirical/governing support and CURATED.
62. **Failed review repairs meaning first.** Challenge/correct/replace/withdraw
    can resolve a curation review finding without creating a rejected-curation
    state; only the resulting stable revision is curated.
63. **Schema-14 migration fabricates no curation.** Transition preserves every
    retained semantic/audit row while historical/current Beta-1 revisions begin
    CAPTURED under the new reuse contract.
64. **Migrated current knowledge is pending.** A migrated CURRENT revision is
    discoverable for curation but absent from ordinary Answer until curated.
65. **Three-tool host surface remains exact.** Capture, curation, reuse and
    re-alignment are all reachable through `ask`, `record` and
    `reconsider`; no curate tool exists.
66. **Installed lifecycle closes the loop.** A non-editable installed MCP journey
    demonstrates capture → pending discovery → curation → fresh-session reuse →
    change → reconsider → semantic-preserving confirm/reuse, and a semantic
    correction path that requires re-curation.
67. **Document-only governed initialization.** From a fresh installation, the
    supplied classification documents plus explicit member selection suffice;
    exact derived governance, authority, ACTIVE/VALID, provenance and ordinary
    runtime are observable without caller-generated intermediate configuration.
68. **Strict preflight.** Invalid classification, identity, membership, authority
    or graph input fails before setup mutation; no semantic repair is inferred.
    Ordinary and governed explicit authority configurations are completely
    validated and applied regardless of evidence-delivery bounds, including
    a field-scale configuration of more than a thousand distinct valid
    locators. The exact complete binding identities, attributes and placed
    document coverage are retained; repeat identical input does not duplicate
    participation. Actual missing/foreign/conflicting/unreadable input
    (including a locator late in the large input) and provider failure are
    distinguished and rejected before pending intent, generated declarations
    or registered-state mutation. Retrieval limits remain unchanged. This
    acceptance scale is evidence of the behavior, not an installation limit.
69. **Repeat and revise.** Identical valid input is a no-op for participation;
    changed input for the same member set revises the exact instance, including
    V2 cutover. Conflicts and failed verification remain explicit; accepted
    receipts and actionable effects survive recovery. An authority-only revision
    returns the exact affected direct/premise-dependent conclusions, including
    removed bindings; route identity and structural health remain independent.
    Unaffected support is not forced stale (FD-12/FD-73/FD-89).
70. **Ownership and interruption.** Owned metadata can legitimately change;
    unowned conflicts fail. Equivalent independently owned whole-document
    authority is reused without replacing its identity; ordinary authority
    survives exclusion. Interrupted setup preserves recoverable pending intent
    and accepted receipt identity, never reports successful governed setup
    prematurely, and resumes without a duplicate write. Competing administrative
    mutations cannot replace pending intent or partially provision another setup.
    Explicit authorized abandonment of an unaccepted pending setup restores
    the verified prior administrative state, including generated-file content
    and absence, without orphaning ownership or requiring manual cleanup.
    Fresh-state, previously accepted-state and interrupted restore cases are
    covered; modified/unowned artifacts and competing writes fail closed.
    Protect both existing and newly created affected stores against independent
    retained changes; preserve unrelated stores and accepted obligations.
    Exclude live runtime admission throughout restoration and prove continuation
    at every durable mutation boundary, including absence restoration.
    An accepted pending write remains recoverable with its receipt/effects.
    Ordinary install and observation modes do not activate. Observational
    guidance distinguishes healthy ACTIVE, degraded/mismatched ACTIVE,
    UNCONFIGURED, EXCLUDED, pending and unavailable state without a
    contradictory initialization request (FD-94). Partial target selection and
    multiple independent ACTIVE instances cannot manufacture health. A completed
    receipt agrees with subsequent observation for the same committed state.
71. **Public findings.** FD-88B applies across all public governance results;
    internal reasons/locators never leak.
72. **Complete bounded retrieval.** FD-88C directory continuation returns all
    applicable placements and findings in deterministic pages, never a false
    resolved state or unrecoverable omission.
73. **Installed runtime identity.** FD-88A verifies the actual requested build
    across checkout and distribution installation, including same-version
    differing builds and absent/stale identity; verification is observational.
74. **Host reachability.** FD-49/52/53/58 distinguish complete, partial, lost
    and restored lifecycle delivery for the intended installation. User-facing
    recovery remains host-supported; live delivery needs recorded evidence.
75. **Administrative invocation and output.** FD-88A rejects incompatible
    options before operational effects; failure, readiness and recovery
    messages contain public actionable coordinates and no private diagnostics.
    FD-27/88B continue to govern every MCP result, including prose fields.
### Public lifecycle boundary acceptance amendment (API-01–23)

These extend the named existing FA cases; verification remains OPEN until
executable evidence is mapped in the existing functional-acceptance matrix.

- FA-01–04/36/41/71: status only member IDs, candidate no echo, accepted writes
  only exact effects, receipt exact immutable audit, no private digest or
  declaration inventory outside receipt; large result continuation.
- FA-09/10/14/16/72: nested root and direct member requests yield identical
  complete parent-root public locations and applicable placements; unrelated
  roots qualified, no prefix guessing or implicit participation; embedded
  multi-path and directory continuation preserve selection and unresolved state.
- FA-24/25/38/41: deep/branching/cyclic cross-repo affected sets recoverable,
  exact per-revision causes, one context per actionable owner, replay only
  immutable accepted refs, no false completion when interrupted.
- FA-28/48/49/51/66: exact question/current selector status scoped to selected
  membership, no recursive descendant inventory, latest applicable verification
  including failures, older history recoverable, evidence admission exact order
  across restart and later context extension, outcome metadata paged, primary
  content preserved under large auxiliaries.
- FA-45/47/50/53–59/62/66: exact accepted revision actions including no-op and
  withdrawal, explicit maturity independent of live support, exact challenge
  prior content and accepted dispositions, surface CAS receipt replay after
  later change, immutable audit vs live qualification; no fabricated migration.
- FA-65/66/71/72: all advertised result branches and nested unions, real wire
  plus free text checked for private carrier/route/digest/diagnostic leakage;
  no increased response ceiling or weakened gate; every bounded collection
  complete or explicitly recoverable, postcommit acceptance never lost.

## 16. What this layer does not define

Layer 3 does not choose storage layout, wire encoding, transport framing,
installer mechanics, host adapters, persistence schemas, or deployment values.
Those are Layer-4 choices and must remain derivable from this functional design
and the higher layers.

