# Span technical design — layer 4

**Status: binding Layer-4 mechanism authority for Span 1.0 Beta 3.**

This document chooses the implementation mechanisms that realize Layers 0–3. It
adds no product requirement. Where it conflicts with a higher layer, the higher
layer governs.

Current reading path:

- **Part B** — generic semantic-lifecycle mechanisms retained by Version 1;
- **Part C (§17–§22)** — Functional Pyramid mechanisms; and
- **Part D (§23–§27)** — Beta-3 capture/curation and schema-15 mechanisms.

Historical baseline comparison, old work packages, resolved open items, and
pre-Version-1 implementation archaeology are retained separately in
[History: technical design before Version 1](history/technical-design-pre-version1.md).

Implementation/release conformance is recorded in
[Acceptance and evidence](acceptance.md), not in this authority document.
The [requirements pyramid](requirements-pyramid.md) governs placement and
precedence.

## Part B — Core semantic-lifecycle mechanisms

Part B records the Layer-4 mechanisms for the pre-existing semantic lifecycle
that Version 1 retains. Parts C and D amend or supersede these mechanisms where
the Functional Pyramid or Beta-3 capture/curation contract changes the boundary.

Historical baseline selection, refactoring work packages, resolved O-* items,
and source-comparison evidence have moved to
[Historical technical-design record](history/technical-design-pre-version1.md).
References in older Part-B prose to O-* identifiers refer to that historical
record and do not create current technical requirements.

## 9. Canonical carriers and generated wire

**Authority:** FD-1–FD-4, FD-9–FD-16, FD-23–FD-29, FD-38–FD-41; L8.

Continue using the canonical dataclass model and schema generator. Put surface
carriers in `core/model/`, operation commands/results beside existing lifecycle
carriers, and persistence interfaces in `ports/lifecycle.py`. Extend the existing
support carrier with dependency-addressed findings instead of an additional
transport-only support model. Naming decision: reserve `Gap` for the public
operation result. Rename the existing recorded question/basis carrier to
`RecordedQuestionGap` in the canonical model, preserving its meaning and fields.
Update its references and generated schema through the same owner; the persisted
type-name treatment belongs to O-4's migration mapping. Do not retain a runtime
alias, shape adapter, or second writer. These are implementation targets, not
names already changed in code.

`core/schema/` owns strict ingress and generated schemas. Adapt the current
reference-only wire where the new contract needs locator/range or retained-context
inputs; do not wrap the old context/submission protocol in a new public tool.
Freeze each variant's required fields, result union, examples, malformed-input
cases, and serialization through that same owner. O-7 blocks the independent-run
variant. O-5 blocks its named support-state case, not unrelated carrier work.

`shell/mcp/schemas.py` registers the host-delivered projections of those carriers;
`shell/mcp/adapter.py` routes them. Family-variant splitting shares the canonical
command/result grammar. Host-specific duplicate semantic DTOs are excluded.
The deliverable is an executable schema/example set, not this prose table.

### 9.1 Delivered public surface (2026-11-02; historical)

This dated subsection records that delivered candidate. The current target
operation contract is lifecycle §4.1–§4.3 and its implementation choices are §9.2.
Do not use the old shapes below to generate new schemas or guidance.


The three-tool surface is implemented in the working tree. `ask`, `record`, and
`reconsider` are the only registered operations. Any other operation name is
unknown. There are no aliases, removed-name compatibility mappings, or dual
grammars.

`ask` accepts exactly one of an exact `surface={kind, locator}`, a `reference`,
a snapshot/receipt selector, or a continuation. With no question, it returns the
surface document view; that is the normal reuse path. An exact question is a
targeted query and matches by exact identity; a paraphrase returns `no_match`
with a recovery that points back to the view. A reference that resolves to
more than one granularity returns `AmbiguousSurface` with exact candidate
identities; the agent copies one candidate back rather than re-resolving the
path. A gap whose evidence was omitted carries a stateless continuation over
the investigation context. The token binds repository, context, request
identity/digest, and the next evidence position; it is valid only while the
context is `LIVE`. Replay and restart work because the context and admitted
evidence are persisted, and every page advances by at least one evidence unit
or exact line range. Historical retrieval is a separate path (FD-38).

`record` is one request selected by `kind` (`understanding`, `verification`, or
`surface`). For understanding, a create carries one `conclusion` with exactly
one evidence mode — `locator`, admitted `observation_id`, or non-empty `support`;
scope is supplied or derived independently. Updates use `actions` with `add`,
`confirm`, `correct`, `replace`, or `withdraw`, and multiple keys apply
atomically. The service derives context, observation identity, submission
identity, current revision, and new lineage identity. A create may cite the
context returned by `ask`; its bound question and scope are used, and the caller
does not re-author them. It preserves the full support union, gaps, provenance, and named
challenge dispositions. `record(kind="surface")` creates or updates a declared
service/domain boundary with an optional parent and compare-and-set
`expected_boundary_version`; cycles, unknown parents, and stale versions are
rejected.

`reconsider` is an after-edit operation. `Changed` carries per-conclusion
support state, so a considered conclusion may still be `CURRENT`; only
`REASSESSMENT_REQUIRED` and `UNVERIFIABLE` mean actual loss. The change walk
includes containment, direct source dependents, direct discovery dependents
whose scope membership changed, and indirect premise dependents to a fixed
point. Challenges are raised by `reconsider` and settled through `record` with
named `challenge_dispositions`.

The conformance gate is `tests/unit/test_surface_conformance.py`. It fails if a
registered name is outside `ask`/`record`/`reconsider` or a host-justified
optional tool, if a per-action or internal-preflight tool is registered, if a
removed name remains, if declared and packaged schemas disagree, if a common
path requires an internal identity the agent must fetch, or if a tool cannot
name the lifecycle verb and agent moment it serves. The G-S2b scenarios live in
`tests/unit/test_lifecycle_service.py`, `tests/unit/test_reconsider.py`,
`tests/unit/test_answer_service.py`, and
`tests/integration/test_lifecycle_mcp.py`.

The friction-remediation mechanisms that refine this surface are in §9.2.

### 9.2 Contract implementation decisions (amended 2026-11-14)

This section selects the mechanisms for the layer-2/3 statements in
`lifecycle-contract` §4.1–§4.2 and `functional-design` FD-25/28/30/39/41/46.
It adds no requirement; each paragraph names the binding statement it realises,
and that statement remains in its owning layer.

**FCIS / SoC / DRY.**

| Concern | Owner | Decision |
| --- | --- | --- |
| Obtain membership | `core` + `service` | Surface/current understanding identity/exact surface-scoped recorded question; retained questions are metadata; no similarity matching |
| Rejection cause kind | `core` | Typed enum; no text classification |
| Current version / boundary version | `shell/sqlite_store` + `service` | Structured values carried through the result; no regex extraction |
| `Gap.recovery` composition | `service` | One builder keyed by gap reason; reuse the `Unavailable.recovery` shape |
| Surface document view | `service` | Reuse the existing composer; no second render or stored document |
| Adapter | `shell/mcp` | Transport only; copies typed results; no semantic or keyword logic |
| Surface conflicts | `shell/sqlite_store` + `service` | Typed conflict with current boundary version; mapped to `Rejected` |
| Parent validation | `service` | One validator for create and update; declared-parent, same-repo, no cycle |
| Descriptions and snippet | `shell/docs` | Layer-4 delivery; no semantic decisions |
| Tests | `tests` | One rejection case per cause; one surface case per conflict; shared fixtures only |

Do not add a parallel `ToolError` cause path, a second free-text question
matcher/projection, or a second surface-declaration path. The exact
`RecordedQuestionSelector` is part of the one obtain grammar, not another
semantic writer. The document-view composer and the rejection builder are single
owners.

**Typed rejection.** Replace adapter text classification with one typed carrier
and one typed cause enum:

```python
class RejectionCauseKind(enum.Enum):
    VALIDATION = "validation"
    SOURCE_DRIFT = "source_drift"
    VERSION_CONFLICT = "version_conflict"
    SURFACE_CONFLICT = "surface_conflict"
    SURFACE_REQUIRED = "surface_required"
    SURFACE_AMBIGUOUS = "surface_ambiguous"
    SURFACE_MISMATCH = "surface_mismatch"
    CONTEXT_TARGET_CONFLICT = "context_target_conflict"
    CONTEXT_BINDING_CONFLICT = "context_binding_conflict"
    CONTEXT_SCOPE_CONFLICT = "context_scope_conflict"
    CONTEXT_REQUIRED = "context_required"
    CONTINUATION_INVALID = "continuation_invalid"
    OBSERVATION_NOT_ADMITTED = "observation_not_admitted"
    REPLAY_CONFLICT = "replay_conflict"
    ALREADY_EXISTS = "already_exists"


class Rejection(ValueError):
    cause_kind: RejectionCauseKind
    public_cause: str                # contract vocabulary, never raw exception text
    required_action: str             # one function of cause_kind only
    current_version: int | None = None
    current_boundary_version: int | None = None
```

Every raise site selects its kind; one cause-to-action function is the only place
that maps a kind to a remedy. `SOURCE_DRIFT`, `CONTEXT_REQUIRED`,
`CONTINUATION_INVALID`, `OBSERVATION_NOT_ADMITTED`, and `ALREADY_EXISTS`
exist because the prior text
classifier distinguished them and folding any into `VALIDATION` would misname the
conflict. `CONTINUATION_INVALID` owns malformed, missing, wrong-binding,
non-live, expired, exhausted, or out-of-position continuation references; its
recovery starts a new explicit evidence admission rather than asking the caller
to inspect internal context state. `OBSERVATION_NOT_ADMITTED` is the remedy gap a flat-create host hit:
the field was right and the value was an id `ask` never returned, so “correct the
named field” sent it back to the same call.

Stateful service/store validation raises `Rejection`. Structural decoding uses
one internal `StructuralFault{coordinate, rule, message}` and aggregated
`StructuralValidationError`; canonical branch rules and the strict decoder
preserve that carrier instead of flattening it into exception text. For a
recognized lifecycle tool the adapter projects those typed public coordinates
into the existing `Rejected.identity/cause/required_action` fields with
`VALIDATION`; it does not add another public result shape. Malformed transport
envelopes and unknown tools stay on the protocol error path. The adapter copies
stateful `public_cause`, typed kind, structured versions and required action
without parsing exception text. Internal diagnostics stay with the owning
exception/log path.

**Store failure taxonomy (0.11.0).** SQLite uses distinct
`LifecycleStoreConfigurationError`, `LifecycleRecordNotFound`,
`LifecycleStoreDataError`/`LifecycleStoreOperationalError`, and
`LifecycleStoreInvariantError` classes. Caller-supplied exact identities are
checked through the corresponding `find_*` owner and become `Rejected` with
safe public identity/cause coordinates when absent. An exact retained record
missing behind already-accepted history remains an operational unavailability;
persisted-data/schema failures are operational; configuration follows the setup
or repository-access boundary; invariant failures are logged and contained as
generic internal tool failure. The generic `LifecycleStoreError` is no longer
the operational catch-all.

**Public failure boundary.** Expected operational exceptions are classified by
their typed owner and mapped by one shell-level table to stable public
`Unavailable.failure` and recovery text. No expected public result is built
from `str(exc)`. Unexpected exceptions are logged with their internal
diagnostics and cross the MCP transport only as a stable generic tool failure;
the transport never serializes their message, traceback, module/class name,
filesystem/store path or database detail. This containment is an egress safety
boundary, not a semantic fallback: it does not turn a programming defect into
Gap, Rejected or ordinary operational state.

**Gap recovery.** Keep one service-owned gap_recovery builder implementing
FD-25/FD-41 and lifecycle §4.1. Typed lookup/operational failures reach the
existing result mapper; exception text is not used as a classifier.

**Closed result unions.** `TOOL_OUTPUT_SCHEMAS` projects FD-38;
`test_result_union_declarations_agree` asserts the reference and the runtime
union. There is no second declaration.

**Obtain implementation.** Extend the existing core/model selector union and
schema projection for lifecycle §4.1. Membership selection stays in AnswerService;
reuse its document/view composition and shared support/status evaluators. No
additional resolver/index or stored document is introduced.

**Delivered surface (F10).** The product surface tested for F10 is the MCP
server plus the installer-managed pre-read notice in `docs/agents-snippet.md`.
The bare server is a component, not the product: the evidence records zero of
five first-move use with bare registration and five of five with the installed
notice. F10 states the condition; this section owns the configuration that
demonstrates it.

**Canonical branch constraints.** Put one typed set of conditional branch rules
in core/schema beside the wire owner. Decode/construction validation and schema
projection consume it; services do not restate structural field combinations.
Keep null/default/empty/unknown-field behavior equivalent. Context origin,
membership, owner containment and CAS still consult their canonical state owners.
Do not use a root tagged union merely to evade hosts that cannot deliver the
approved grammar; test the real packaged schema through each claimed host.

**Public discriminator vocabulary.** Where structural ambiguity genuinely
requires a discriminator, declare its wire value explicitly beside the canonical
branch rule and make both schema projection and decoding consume that declaration.
Never derive a public tag, schema branch name or accepted-value list from
`type.__name__`, module paths or another runtime implementation identifier.
Internal carrier renames therefore cannot change the protocol. Where branch
structure is already unambiguous, omit the tag rather than exposing implementation
shape for convenience.

**Bound context implementation.** Put the lifecycle §4.1 reference carrier in
core/model. Parse its canonical wire branch once, then route through the typed
request's bound namespace in shell/mcp/wire and adapter. Migrate existing public
context constructor/reader sites together; internal stored InvestigationContext,
RecordingIdentity and receipt keys are retained. Existing store/port lookup
errors supply typed failures for the mapper; no secondary context lookup exists.

**Reconsider issuance implementation.** `ReconsiderService._reconsider_context`
allocates a new internal request key through the existing UUID identity utility
for each evaluation and delegates creation/recovery to
`service/contexts.issue_context` with explicit `CHANGED_SUPPORT` origin. The
changed-scope digest remains binding content, not the issuance key. Challenge
issuance uses the same owner with explicit `CHALLENGE` origin when no context is
supplied; an already supplied context is preserved. Other caller-identified
operations continue using their existing keys through the same issuance owner.
This implements FD-2/FD-45 without a second context constructor or origin
heuristic; lifecycle §4.3 owns the public guarantee.

**Admission implementation.** Implement lifecycle §4.1's single public admission
projection in core/model and construct it through EvidenceService. Keep stored
SourceObservation immutable; associate its ID with existing EvidenceUnit page
fragments produced by the answer fitter/_slice_unit. Schema generation handles
that canonical delivery carrier on both initial and continuation results. Do
not introduce a second source-copy/range parser or reconstruct source identity in
transport code.

**Compact implementation.** Implement only lifecycle §4.2's public field sets
and qualification projections in core/model. Service composition projects the
existing support evaluator's results once; detailed support and durable receipt
models are unchanged. Exact audit retrieval reads verification runs through the
existing accepted-run IDs in the receipt and their store owner. The wire generator
serializes those canonical results; the adapter does not rewrite JSON.

**Context-bound create.** The service chooses `ContextBoundTarget` or
`ExplicitTarget` once from the context origin (FD-30). The adapter does not
infer it.

**Derived create surface.** `_resolve_create_surface` is the one resolver; the
service passes its key to `record_command` as `derived_surface`. The three
surface rejection causes are the FD-30 cases.

**Flat create.** The service derives one complete semantic `EvidenceScope` from
the question context or explicit paths/locator/FILE surface and passes it to
`flat_conclusion`, owner resolution, and `record_command(derived_scope=...)`.
The canonical `ExplicitTarget` uses that carrier, never raw wire scope again.
Owner agreement projects the complete semantic scope through
`containment.scope_surfaces` and validates every member with
`containment.surface_contains`, including path-surface self-membership (FD-5).
Support dependencies never participate in owner agreement.

**Reconsider scope preservation (FD-17, FD-59).** Discovery impact checks use
`evidence_scope_contains` over the complete observation scope. Challenge contexts
union the complete version scope with actual owner/evidence requirements through
`evidence_scope_union`; exact references are never flattened into paths.

**Scope algebra and context derivation (FD-59).** Canonical pure
`evidence_scope_contains` and `evidence_scope_union` live alongside
`evidence_scope_allows` in `core/model/primitives.py`. Empty scope is
repository-wide; it absorbs union and cannot fit inside a restricted outer
scope. Union deterministically preserves paths and exact references. Only
actual requirements participate; absent optional data is not an empty operand.
`_resolve_record_request` remains the sole context builder. It unions complete
semantic/version scopes, direct evidence, action scopes, and complete discovery
boundaries. Context-free discovery with context-admitted reference strings
rejects before context issuance; references are never globally resolved.
Source admission checks locator membership for restricted contexts. Discovery
checks full containment before inventory. EvidenceService keeps its admission
backstop. Neither path widens a supplied context.

**Canonical context binding (FD-2–FD-4, FD-59; 0.11.0).** One internal
`ContextBinding` carrier owns the digest projection used by every
`issue_context` caller. Repository and caller request identity remain the
store key and are not duplicated inside the digest. The binding contains the
explicit `ContextOrigin`, the effective complete `EvidenceScope`, the exact
source requests as locator plus inclusive ranges, the exact discovery scopes
selected for admission, and `question` when it is part of caller-owned binding
identity. Source requests and discovery scopes are canonicalized by their
canonical value, deduplicated and sorted before hashing; caller order therefore
cannot create another binding for the same selection. Origin is never inferred
from question presence. The binding excludes conclusion wording, update
actions, challenge disposition text, verification outcome, submission digest,
and every other semantic write field. `payload_digest(ContextBinding)` is the
sole `binding_digest`.

`issue_context` receives that typed binding rather than an arbitrary payload.
The persisted context stores `binding_digest`; repository/request uniqueness
plus that digest is the recovery/conflict boundary. The complete write wire is
still hashed independently at the receipt owner before context/evidence work.
Explicit ask/source admission is `EVIDENCE_ONLY`. A context-free record is also
`EVIDENCE_ONLY`; for a create its question participates in the binding digest so
a changed semantic request under the same caller identity conflicts, but the
operational context does not become a question-bound semantic target and does
not persist that question. A genuine question-bound start is `QUESTION`.
Changed-scope reconsider is `CHANGED_SUPPORT`, and a challenge context issued by
reconsider is `CHALLENGE`; when the caller already supplies a valid context,
reconsider preserves that context rather than manufacturing a second one.
Context-free record derives source requests and discovery scopes from the same
direct-evidence fields that admission consumes. Challenge issuance binds its
effective scope and direct challenge evidence selection. Changed-scope
reconsider continues to use a fresh Span-owned request identity on every read,
so it does not reuse caller request identity.

**Surface conflicts.** `SurfaceConflict` carries the current boundary version.
`put_surface` and `update_surface` raise it for a kind conflict, a changed
boundary under the existing version, and a stale compare-and-set. The service
maps it to `Rejected` with `current_boundary_version`. `LifecycleStoreError`
stays for operational store failures and maps to `Unavailable`.

**Parent validation.** `_require_valid_parent` is the single validator for
create and update; it enforces the parent rule in `lifecycle-contract` §4.2
(declared parent, same repository, no self-parent or cycle).

**Verification scope.** The run's `scope_paths` remains the applicability key.
`AnswerService` selects runs whose scope matches the asked surface. No new
carrier and no widening by a broader question.

**Test ownership.** Typed rejection cases live in
`tests/unit/test_lifecycle_surface.py` and
`tests/unit/test_lifecycle_service.py`; `Gap.recovery` and document-view cases
live in `tests/unit/test_answer_service.py`; context-bound and surface-conflict
cases live in `tests/unit/test_lifecycle_service.py` and
`tests/integration/test_lifecycle_mcp.py`; description and snippet cases live in
`tests/unit/test_surface_conformance.py`, `tests/unit/test_agents_snippet.py`,
and `tests/unit/test_skills.py`.

### 9.3 Release and consumer compatibility disposition — 0.10.3

The release identifier remains the user's selected **0.10.3**. This is a bugfix
release with intentionally breaking request grammar; it is not described as a
backward-compatible protocol patch. Repository release mechanics are owned by
contributing.md §Releases. No unrecorded version-number compatibility guarantee
is inferred, and no version metadata is changed by this documentation amendment.

| Consumer | Required delivery before release |
| --- | --- |
| MCP tool clients (Codex/OpenCode/Claude where support is claimed) | Refresh tools/list against the same candidate; replace retired input grammar; capture actual branch delivery and results |
| Managed skills, snippet and lifecycle notices | Ship the same surface-only obtain, direct-capture and bound-context grammar through existing packaging/install owners |
| Existing configured/running MCP processes | Resolve pending accepted outcomes before upgrade; restart/reconnect and refresh cached schemas; do not silently run old and new grammar as peers |
| Direct/custom clients | Explicit protocol upgrade required; reject retired fields through the canonical decoder with actionable new-schema guidance, not aliases |
| Retained receipts, revisions and contexts | Preserve store identity/history and promised retention; use existing exact audit selectors for old acceptance, bound references for still-live contexts; no re-execution or store migration inferred |

The supported delivery boundary is one identified package candidate plus its
managed projections and a refreshed host session. Source declarations or prior
host captures alone do not certify it. Existing packaging/install owners deliver
the managed assets; candidate-specific captures verify each claimed host. Unverified host versions are reported
as unverified; no new compatibility parser, pinned old semantic writer or shape
adapter may compensate. Failure to deliver this boundary blocks publication,
not the structural contract correction.

Preserve replay meaning through original repository/request keys and full
immutable receipts. Before a grammar switch, resolve accepted old operations
through their retained receipt selectors. Do not re-encode a historical write
as a new one or assume a new wire digest equals the old request. New direct
writes still use stable caller-owned identities. Registration refresh and
publication require separate authorization; this disposition performs neither.

## 10. Schema-13 layout and indexes

**Authority:** FD-1–FD-8, FD-30, FD-35–FD-36, FD-42–FD-48.

Keep SQLite and `shell/sqlite_store/lifecycle.py` as the transaction owner.
Canonical JSON remains the payload; relational columns/indexes project its keys.
The proposed physical changes are:

| Storage owner | Key/index change | Canonical payload / treatment |
| --- | --- | --- |
| `surfaces` (new) | repository plus canonical surface key; declared-name uniqueness and kind-conflict validation | `Surface`, including boundary and parent reference; no persistent currency flag |
| `understandings` | add owning surface reference and unique repository/surface/question index | adapt `Understanding`; preserve stable IDs and version pointers |
| `understanding_versions`, `conclusions`, `understanding_membership` | retain immutable revision and membership keys; bind ownership through the understanding | adapt canonical payload references; no duplicated conclusion bodies |
| `investigation_contexts` | retain repository/request uniqueness; rename the persisted digest column to `binding_digest` | `InvestigationContext.binding_digest` commits the canonical context binding; scope/question remain canonical context fields |
| `record_receipts` | replace repository/context/submission key with repository/request key | adapted acceptance identity, digest, effects, and expiry; no cascading dependence on live context |
| `support_dependencies` | retain reverse index and exact revision keys | project dependencies from canonical revisions in the acceptance transaction |
| source/discovery observations, challenges, verification runs | retain canonical records and their reference integrity | only required ownership/identity adaptations; run-ingress mapping is the resolved O-7 path recorded in §12 |
| `meta` | advance expected schema to 13 | existing runtime format check; no migration on ordinary open |

Resolve path containment from canonical boundaries and existing inventory/locator
capabilities. Compute surface status on read; do not add a second maintained
containment graph, status ledger, or document store. Indexes can accelerate exact
lookups but cannot define semantic ownership.

**Boundary updates (O-8).** The update input is the declared surface carrying the
new boundary and `expected_boundary_version`; a mismatch rejects the write with
the current version (FD-46). One transaction appends an immutable
`surface_boundary_versions` row `(surface, boundary_version, boundary_json,
digest)` and advances the surface's current pointer. Each understanding version
records the `surface_boundary_version` it was assessed against, so a historical
reference identifies the boundary it describes. FD-35–FD-36 govern history, and
no second containment graph or status ledger is introduced.

Schema fixtures must exercise foreign/cross-repository references, overlapping
boundaries, conflicting kinds, duplicate creates, and referenced history. O-4
blocks the old-row backfill; adding nullable runtime surface ownership is not a
transition solution. Exact DDL is verified with those fixtures before activation.

## 11. Read composition and change traversal

**Authority:** FD-5–FD-29, FD-54–FD-57.

Implement lifecycle §4.1 membership selection in the existing AnswerService
using canonical store surface/understanding membership and the exact-question
predicate. Reuse _document/_view and the shared evaluator under FD-25/28.
EvidenceService constructs the admission projection; the existing page fitter
produces EvidenceUnit deliveries. Neither transport nor an added resolver
constructs evidence identity or semantic relevance.

The read composer returns historical `Gap` content through
`HistoricalConclusion` and stale surface references through
`StaleConclusionRef`; both are read-time projections over stored revisions, not
a second stored shape. Verification applicability uses the shared containment
rule: a run applies when the asked surface is within its declared scope, and a
single-file run is not widened to a broader service.

Implement one containment resolver shared by query resolution, status, and
change mapping. Add `service/reconsider.py` for the operation composition. Use
`source_observation_ids_for_locator` and `support_dependents` as lookup building
blocks; expand premise references through a visited-set worklist to a fixed
point. Resolve owning surfaces after dependency traversal, not only through the
changed path's boundaries. Group the result by canonical surface key, collecting
reason sets and stable recorded sequence information. No swallowed lookup failure
becomes an empty affected set. The unresolved state selection is O-5.

Represent individual failing dependency evaluations in the canonical support
carrier. Reuse the core precedence calculation after collecting those results;
do not recover dependency identities by parsing `_revision_eval`'s reason text.
Use the same evaluator for reads, writes, verification qualification, and notices.
Range binding follows FD-18; delivered ranges alone do not prove a reliable
range identity and do not justify widening the implementation into a new parser.

## 12. Acceptance, replay, and transition composition

**Authority:** FD-2–FD-4, FD-30–FD-41, FD-46–FD-48; L4, L7.

Extend `RecordingIdentity`, its wire ingress, receipt selectors, and store port
together. Retain `receipt_decision` and the existing `BEGIN IMMEDIATE`
transaction. Both service lookup and in-transaction lookup address the adapted
request key; neither derives a new retry identity from a fresh context. Derive
understanding IDs through the core identity owner, while the surface/question
unique index enforces creation arbitration.

**Compact update grammar.** `RecordActionsWire` carries action-specific compact
deltas (`AddConclusionWire`, `ConfirmConclusionWire`, `CorrectConclusionWire`,
`ReplaceActionWire`, `WithdrawActionWire`) rather than a full conclusion
snapshot. The public caller supplies no new conclusion lineage identity on
create, `add`, or `replace`; `span.core.identity.conclusion_identity` derives it
from `(repository_id, request_id, role, ordinal)` for roles `create`, `add`,
and `replace`, projected as `c:<digest>`. The function is pure and replay-stable;
no database allocator, counter, context, version, or source content participates.
`LifecycleService.record()` reads the exact understanding version the caller
names, derives the old revision identity, the unchanged assertion nature or
scope, the mechanical basis, and the complete supplied support, and builds the
existing canonical action carriers and `UpdateUnderstandingCommand`. The
existing atomic store transition and compare-and-set remain the only acceptance
owner; no second command representation, grammar, or writer is introduced.

Compute the original wire digest and call `_replay` before any context or
evidence work, for both understanding and verification. Reuse `receipt_decision`.
`CONTEXT_BINDING_CONFLICT` and `CONTEXT_SCOPE_CONFLICT` have canonical actions;
context binding is not a version conflict.

Compose internal context issuance and `EvidenceService` admission inside the
operation service, after receipt lookup. There is no required public admission
or context-fetch step. Candidate-specific host identity preservation remains
O-6. On conflicting updates, carry the observed current version as structured
rejection data rather than requiring the caller to parse an exception sentence.

**Verification ingestion (O-7).** A run cites the `SourceObservationId`s the
independent run actually exercised. Those are the observations admitted for the
operation's context: the bound reference returned by explicit ask admission or
a challenge, or
the locators/ranges the operation admits internally before recording. The service
stores those exact IDs with the run, so the run names what it actually exercised.
The wire accepts `run.observations` and/or `run.evidence`; evidence locators are
admitted before the same command path. No separate public admission step and no
inferred run provenance is introduced.

Split the core confirm/correct branches in `_apply_action`. The service supplies
the prior and newly observed support needed by FD-31; the core transition selects
the appropriate effect. The store can persist a receipt for a no-op result without
writing an unnecessary revision/version. Test that path with both identical retry
identity and a new intentional identity. Preserve challenge dispositions through
the existing atomic transition owner.

**Live owner status (FD-60).** One functional `service/surface_status.py`
composer owns the existing AnswerService algorithm. Both ask and understanding
record qualification use it. `UnderstandingRecorded.status` is `SurfaceStatus`
or transient `SurfaceStatusUnavailable(reason, surface?)`; neither is persisted.
Expected operational read failures preserve accepted receipts; programming and
contract defects are not normal unavailability. `LifecycleStorePort.operational_errors`
is the store-owned classification of operational exception types; SQLite declares
`LifecycleStoreError` and `sqlite3.OperationalError`. Post-commit qualification
catches those types and provider `OSError` independently for support and status,
without importing the SQLite shell into the service or catching every `ValueError`.
Status coverage retains complete conclusion scopes and checks members through
canonical scope containment: exact refs do not imply repository-wide coverage.
A repository-wide semantic scope cannot agree with a FILE owner. Surface declaration receipt
semantics are outside this remediation.

Use the reverse dependency index to compose FD-37 effects against the accepted
transition. Store immutable acceptance facts in the receipt, and expose the
affected references through the canonical recorded result. Live support and
surface status remain freshly qualified, not cached truth inside that receipt.
The result representation must preserve known committed acceptance even if
post-commit qualification is unavailable. This is a schema/probe obligation in
§9 and §15; a generic rejection cannot represent it.

## 13. Operational lifetime and bounded results

**Authority:** FD-42–FD-45, FD-54–FD-57.

Keep `LifecycleRetention`, injected clocks, and the operational reaper. O-2 owns
the evidence for deployment durations; the one-day/seven-day defaults are not
silently adopted. Define request/context/receipt recovery at both sides of expiry
in the schema fixtures. Do not copy the old plan's expired-context safety claim
onto a different request-key protocol without checking its actual lifecycle.

Retain accepted semantic history and its referenced observations. No new history
reaper is selected by this design. If one is separately justified, extend the
existing persistence owner with the FD-44 cases and a reference-safe lifecycle;
do not infer that requirement from an operational TTL.

Move response budgeting from public request carriers into the existing composition
boundary. Continue using core paging and `_fit_result` mechanisms where applicable,
but fit every new result variant through its canonical projection. O-3 supplies
per-host values. Include omitted identities and recovery references in the fitted
result; those references resolve through `ask(reference)`, with no public budget
or new retrieval family. No response-size limit is allowed to change support
classification or hide a traversal limit.

**Implementation state (2026-11-01).** All public request carriers are free of
response budgets and traversal bounds; services apply the server-owned policy.
`AnswerService` fits every result variant, names each omission, and refuses a
budget below the minimum result. Expiry and restart fixtures cover context,
receipt, and accepted-history survival. The O-2 duration and O-3 per-host value
remain unmeasured, so FG-4 stays `OPEN`.

## 14. Offline schema transition

**Authority:** F3, F7, L4; FD-1, FD-6, FD-35–FD-36, FD-42–FD-45.

Extend `shell/store_transition.py` and the existing installer transition command.
For 0.11.0 the target is schema 13 and `SUPPORTED_SOURCE_SCHEMAS` contains
7–12. The runtime never migrates at open. Historical schemas 7–9 retain their
export-only treatment; schema 10 and 11 keep their documented semantic mappings
into the current target; schema 12 has the dedicated mapping below. Retain
historical old-format exports without a second active decoder or semantic writer
in the MCP runtime.

**Schema-12 to schema-13 mapping (0.11.0).** Schema 13 changes the meaning and
name of the context digest from whole-request `request_digest` to the canonical
`binding_digest` defined in §9.2. A schema-12 context cannot be mechanically
rebound because the persisted row does not retain every original source
selection. Therefore the transition is an offline drain, not a context rewrite.

Before staging, inspect every schema-12 `investigation_contexts` row. Refuse
while any context is `LIVE` and either has no expiry or has an expiry at or
after the transition clock. Expired or non-live contexts do not block the
transition and are not copied. The staged schema-13 store copies every repository
and durable semantic/audit table for the selected repository, including source
and discovery observations, surfaces and boundary history, understandings,
versions, conclusions, support dependencies and membership, challenges,
verification runs and verification-observation membership, and retained
`record_receipts`. It deliberately copies no `investigation_contexts`,
`context_evidence`, or `context_discovery_evidence` rows. Receipt
`RecordingIdentity.context_id` values remain immutable historical coordinates;
they do not require the operational context row to survive (FD-42).

The mapping artifact classifies those three context tables as
`drained_not_copied` and every other target table as `preserved`, recording
source/target counts. Verification requires zero staged operational contexts,
exact preserved counts, SQLite integrity, support/dependency reconciliation,
verification-observation references, and every receipt's accepted understanding,
challenge and verification references. A refused drain leaves schema 12
untouched. Rollback before schema-13 writes restores schema 12 through the
existing owner; after schema-13 writes the existing rollback preservation rule
keeps the new-format store rather than discarding accepted writes.

**Schema-10 mapping rule (O-4).** Each schema-10 understanding maps to the path
surface named by its recorded `EvidenceScope` when that scope names exactly one
path that is a file. A scope naming several paths, none, or a directory is
classified `unresolved` with reason `scope does not identify one file surface`,
and preserved in the archive; no service or domain surface is inferred from an
evidence scope, and no conclusion is split across surfaces (FD-6). A receipt
identity maps through its context's recorded request identity; a receipt whose
context is gone is preserved as unresolved with its recorded digest and effects.
The persisted `$type: Gap` tag maps to `RecordedQuestionGap` during staging; no
runtime alias or second decoder is retained.

The transition specification must enumerate each schema-10 table and classify its
rows as preserved canonically, mechanically transformed with verified references,
or unresolved with a named reason. Record source IDs, target IDs, counts, hashes,
and the provenance of each mapping. Surface assignments and old receipt keys are
O-4: this document does not choose a fabricated service, domain, or request ID.
An incomplete mapping cannot activate the new runtime or silently downgrade
accepted understanding to an empty active store. Any proposed different
preservation policy requires the owning authority decision first.

**Implementation state (2026-11-01).** Schema 10 is accepted by the existing
transition path. `shell/store_transition_schema10.py` performs the raw per-table
mapping, records `mapping.json` with source/target identities, counts, hashes,
and provenance, and verifies counts and every source/discovery/premise
reference before activation. Schemas 7–9 keep their export-only treatment. A
disposable-store fixture covers understandings, versions, conclusions, gaps,
challenges, verification runs, and mapped receipts. No live user store was
transitioned and the per-table mapping still needs its owner review.

Reuse inspect/archive/export/stage/verify/activate/rollback and the manifest
owner. Add schema-10 fixtures for nonempty understanding history, cross-surface
premises after assigned mapping, outstanding challenges, verification runs,
retained/expired receipts, and restart after interrupted staging/activation.
Verify archive integrity, reference reconciliation, new-format writes on rollback,
and active-writer refusal. Prior journal/platform observations remain limited to
the platforms tested. Ordinary store open still only checks format; transition
execution against any user store is outside this documentation change.

## 15. Host delivery, assets, and measured fitness

**Authority:** FD-38–FD-41, FD-49–FD-58; F7, F8, L8.

Keep stdio transport and the existing host adapters. Select registered variant
splits only from captures of the generated §9 candidate, including required error
and post-commit-result branches. Capture exact source/build/schema digests,
host/model/version, delivered declarations, calls/replies, request-identity
preservation, retry/restart, and truncation. A callable tool with opaque required
fields is not complete declaration evidence. O-6 remains open until the actual
identity owner and delivery boundary are observed.

Record the supported host set before evaluation. Historical Codex/OpenCode runs
retain their original scope; no broader support claim follows from this
document. Measure result-size limits
and supported suspension bounds for O-2/O-3. An unbounded or unobservable host
resume horizon needs an explicit supported-recovery decision, not an invented
finite measurement.

Update `skills/`, `docs/agents-snippet.md`, affected public guides, registration
descriptions, and installer-owned assets with the new binary/schema cutover.
Generate packaged copies from their canonical sources; preserve foreign host
configuration. Test installation/reconnect using isolated profiles and disposable
stores. Updating source does not claim deployed host-local copies changed.

**Adoption notice (FD-58, 2026-11-03).** Two mechanisms are required, and the
first is the actual cause of the first-move failure: OpenCode dispatches the
first model request before a local MCP server has connected (the first request
carried 66 tools with no Span; the second carried 69 with all three). The plugin
therefore registers `session.hook("prompt")`, which waits a bounded three seconds
until a Span `_ask` tool appears in the tool list, then proceeds whether or not
it did. Without that wait the agent cannot ask before reading even when it
intends to. The notice itself is delivered through `session.hook("context")`:
the plugin calls `span-hooks adoption-primer --repo-root <root>`, which prints
the lifecycle notice for every registered operational repository, including
a cold repository.
The plugin pushes the text into `event.system` once per session and stays silent
on any failure. The text names the required lifecycle actions and direct tools, and makes no
claim that retained understanding exists or is current. The installer deploys the plugin under Span's
own data root and registers it once in the host's global `opencode.json`; it
never writes the plugin into a target. Codex continues to use the managed
`AGENTS.md` block. The notice's bytes are counted in the F8 class measurement.
FD-53 applies: the notice is not claimed delivered until captured. An edit-time
notice is computed on a tool edit, held once per session, and delivered by the
next `context` hook; it names the changed paths and the exact
`reconsider(changed_paths=[...])` call. It asserts support state only and is
silent on failure.

**0.10.2 pending notice lifecycle.** Extend the existing pending notice with the
paths of its producing edit event; do not create a session edit ledger. Native
lifecycle events use `data.sessionID`. Idle refresh forwards unconsumed paths as
`[{"file_path": path}]` to the stop runner's JSON stdin. Successful context
injection consumes the notice; failed injection/reporting retains it. Deletion
and plugin disposal clear notice state. The existing bounded notice cache reaps
abandoned entries with an explicit diagnostic at capacity. A missing session ID
is diagnosed; no shared cross-session fallback is used. Previously delivered
notices are not replayed at idle. Answer support remains checked by operations.

**OpenCode plugin scope (0.9.4).** The lifecycle plugin is managed under an
explicit `--opencode-plugin-scope global|local|none`; the installer never infers
the scope from disk. `global` deploys the canonical plugin and reports a
conflict when an explicitly inspected target contains another Span plugin; it
does not move or delete that target-owned artifact. `local` and `none` remove
Span's global registration and leave target plugins to the user, reporting each
copy. Receipt targets not selected with `--repo` are inspected read-only and
yield `conflict`, never `wired`. A fresh install defaults to `global`; an
upgrade uses the current receipt's scope and a receipt with no unambiguous scope
stops and names the flag. The authoritative full scope matrix is in
[install](install.md#opencode).
Foundations §1 binds the MCP **server**, which still makes no target edits; host
integration and the upgrade migration are installer behaviour. Under the global
scope, the installer uses that same fixed global configuration for the MCP
registration unless an explicit, prior-receipt, or local MCP path takes
precedence. Selected paths are absolute receipt identities; an explicit
relocation removes the prior Span registration after the new registration
succeeds. The receipt retains the MCP and plugin configuration paths independently; doctor reuses the
recorded MCP path and uninstall removes each owned artifact from its recorded
configuration. See
[install](install.md#upgrading-from-09091).

**Measured 2026-11-03 (OpenCode):** with the readiness wait and the notice,
**5/5** clean runs put the first `ask` before the first source read; without the
wait the first tool list had no Span and the rate was 2/5. Evidence:
`.context/evidence/fitness/2026-11-02-three-tool/natural-use/F10-2026-11-03.md`.

Retain comparative measurements as optional product research, not as a
Version-1 release gate. G5/F8 are demonstrated for Beta through real integration use
on ordinary engineering work. The pre-release candidate must still pass the
deterministic contract, packaging, migration, recovery, public-boundary, and
functional-acceptance gates; Beta publication does not wait for an artificial
equivalent-task score.

Post-release evaluation should capture the product behavior that matters in
practice: cold investigation, fresh-session reuse, implementation and governance
changes, re-establishment, recovery, and failure. Findings from that use are
inputs to follow-up Beta patches. No telemetry service or numeric acceptance
threshold is introduced.

Historical comparative captures from 2026-11-02/03 remain calibration material
only. They do not certify Version 1 and they are not required to publish it.
Any future public time/token/cost claim must be supported by evidence scoped to
that claim.

## 16. Verification ownership and completion

The forward plan owns execution dependencies and receipts. This matrix maps
FD coverage to mechanisms and the existing test owners to extend; it is not a
second declaration of those requirements.

| Authority | Mechanism section | Test owner / required scenario family | Present status |
| --- | --- | --- | --- |
| FD-1, FD-5–FD-8 | §10–§11 | `test_lifecycle_store.py`, `test_answer_service.py`; identity, boundaries, ownership, overlap, partial inventory, computed `unexamined`, descendant status | computed status tested; boundary enumeration is store-known members with the limit reported |
| FD-2–FD-4 | §9–§12 | `test_lifecycle_service.py`, `test_lifecycle_store.py`, `test_record_wire.py`, `test_store_transition.py`; canonical request binding, restart/expiry and schema transition | 0.11 canonical `ContextBinding`, caller request identity, replay/restart, schema-12 live/no-expiry refusal and exact post-cutover receipt/run retrieval verified |
| FD-9–FD-16 | §9, §11 | `test_support_service.py`; dependency findings, mixed states, withdrawal, cycles | adapt; O-5 AMBIGUOUS |
| FD-17–FD-22 | §11 | `test_reconsider.py` plus the installed MCP lane; cross-boundary closure, bounded traversal, challenge raise and re-establishment | bounded walk, fresh changed-support context, exact evidence membership, ordinary re-establishment and packaged challenge resolution verified; T08 comparative measurement remains separate |
| FD-23–FD-29 | §11 | `test_answer_service.py`; mixed-support answers, gap variants, ambiguity, document view | candidate tests added |
| FD-30–FD-37 | §10, §12 | `test_lifecycle_service.py`, `test_lifecycle_store.py`; duplicate create, confirm no-op, dependent effects, disputes | dependent effects named on the receipt; tested |
| FD-38–FD-41 | §9, §12 | `test_record_wire.py`, `test_lifecycle_surface.py`, `tests/integration/test_lifecycle_mcp.py`; closed unions, rejection identity/action/version, post-commit failure | packaged MCP exercises all declared result families including `Unavailable`; structural faults are typed `Rejected`, unknown tools remain transport errors, and malformed ingress is separately contained |
| FD-42–FD-45 | §13–§14 | `test_lifecycle_store.py`, `test_store_transition.py`; expiry boundaries, restart recovery, context drain and preserved references | expiry/replay verified; schema-12 live and no-expiry contexts refuse cutover without mutation; drained activation preserves exact retained receipt and verification history; interruption/rollback paths are verified |
| FD-46–FD-48 | §10, §12 | `test_lifecycle_store.py`, `test_lifecycle_service.py`; concurrent first write, duplicate create, CAS and replay | same-identity replay/conflict, receipt-first concurrent acceptance, and distinct request identities racing one expected version are verified |
| FD-49–FD-53 | §15 | `test_host_contract.py`, installed stdio lifecycle coverage, raw live-host capture | 0.11 packaged stdio exact selectors, public grammar, structural rejection and result families are verified. Candidate-specific managed-host schema/argument/server-receipt capture and session handoff remain T09 external acceptance; older host captures do not substitute for it |
| FD-54–FD-57 | §13, §15 | `test_answer_service.py`; result fitting, explicit omission, minimum-result refusal | O-3 measured per host and applied as the delivered-wire budget |
| FD-58 | §15 | `test_lifecycle_hooks.py`, `test_install.py`, `test_skills.py`; cold/warm lifecycle notice, plugin deploy/remove, skill vocabulary | canonical native/shell guidance, hooks, skills and plugin notice-delivery lane are verified; 0.11 candidate-specific managed-host native/search/shell captures remain T10 external acceptance |
| F1, F7; verification variant in layer 2 §4.2 | §9, §12 | independent run before source mutation, then ingestion/reuse with original observation identity | O-7 resolved for source-observation ingestion; external execution authenticity remains a separate, not-yet-designed workstream |
| F8, G5 | §15 | real integration use across the ordinary lifecycle; optional scoped comparative research | prior measurements remain historical evidence only for their named candidates. Version 1 validates practical value through post-release Beta use; no synthetic comparative score is required for publication |
| FD-61–FD-74, FD-86–FD-91 | Part C §17–§18, §20.1 | Functional Pyramid core/service tests plus installed MCP; FunctionalScope algebra, outside/covered/uncovered/mixed projection, overlapping/inherited/cross-repository graph resolution, deterministic provenance, health iff structural findings | implemented; T10 generic acceptance verified on exact-head CI, T13 re-verifies the assembled candidate |
| FD-75–FD-81 | Part C §18, §20.2–§20.3 | support/record/reconsider tests; FunctionalRouteSupport derivation/evaluation, authority separation, pre-existing normative activation effects, deliberate participation removal vs operational unavailability | implemented; covered by T10 generic acceptance, T13 re-verifies the assembled candidate |
| FD-82–FD-85, FD-93 | Part C §19–§20.4 | lifecycle store/service/schema tests; installation-level receipts, activation/revision/deactivation atomicity, participation effects, dependent effects, replay with fresh contexts, pyramid CAS and one-ACTIVE-instance uniqueness | implemented; covered by T10 generic acceptance, T13 re-verifies the assembled candidate |
| FD-92, FD-94; L8, L13–L16 | Part C §20–§22 | generated schema, MCP integration, hooks/skills and host capture; exact three tools, candidate/status/receipt selectors, FunctionalPyramidRecorded affected projection, result-driven initialization through DECLARE→reconsider/disposition→VALIDATE→ACTIVATE/REVISE→VERIFY→effect disposition and matching runtime qualification gates | implementation and generic installed-MCP evidence complete; candidate-specific managed-host delivery remains T13 |
| Functional design §15 cases 32–44 | Part C §18–§22 | generic acceptance plus installed MCP; outside scope, MIXED scope, structural health equivalence, activation of pre-existing normative understanding, participation-write propagation, deactivation/removal route state, replay/context recovery, concurrency, initialization re-alignment, conformance-as-NORMATIVE, accepted-non-current runtime gating and participation-write effect completion | T10 generic acceptance complete; T11 private acceptance passed; T13 reruns the assembled candidate |

The matrix covers both the established Part-B baseline and the Part-C
Version-1 target. Part-B historical/current mechanism claims remain governed by
their existing evidence and open measurements. Part C is design-complete because
its derivation map has no unmapped FD owner or unowned mechanism, and its
implementation is complete through the T10 generic acceptance evidence recorded
above. Candidate-specific managed-host delivery remains unverified unless separately
claimed, and final Part-C derivation re-verification remains release-verification
work. G5/F8 product-value validation is post-release Beta work and does not
reopen the implemented mechanism or block publication.

## Part C — Version 1 Functional Pyramid mechanisms

Part C implements the binding Version-1 behavior in lifecycle §4/§7 and
FD-61–FD-94. It does not redefine those requirements. Parts A/B remain evidence
and mechanism authority for the pre-existing semantic lifecycle unless a Part-C
decision explicitly adapts that mechanism.

### Part-C derivation map

This is the canonical Layer-3 → Layer-4 association for Version 1. Layer 3
remains mechanism-independent; this table points downward from each functional
owner to its primary technical mechanism and verification owner. Supporting
sections may contribute plumbing, but they do not create another functional
owner.

| Functional authority | Primary technical mechanism | Verification owner |
| --- | --- | --- |
| FD-61 | §19 participation persistence + §20.1 projection | lifecycle store/service + ask integration |
| FD-62–FD-69 | §17 FunctionalScope/declaration representation + §18 graph resolver | pure scope/graph tests + ask integration |
| FD-70–FD-74 | §17 declaration/identity carriers + §18 resolution; FD-74 projection in §20.1 | graph/source-binding + ask integration |
| FD-75–FD-77 | §18 support evaluation + §20.2 understanding record composition | support + lifecycle record tests |
| FD-78 | §20.1 ask composition | answer-service/MCP tests |
| FD-79 | §20.3 shared effect engine + §20.4 participation write composition | reconsider + pyramid-write tests |
| FD-80 | §17 strict declarations + §18 resolver | graph validation tests |
| FD-81 | §18 FunctionalRouteSupport evaluation | support-service tests |
| FD-82 | §19 versioned membership persistence + §20.4 write composition | store/service CAS tests |
| FD-83 | §18 health evaluator + §20.1 status projection | health/status tests |
| FD-84 | §17 complete declaration input + §20.1 pure candidate validation | candidate-validation tests |
| FD-85 | §19 receipt/transaction mechanics + §20.4 accepted/replay projection | store/service replay and atomicity tests |
| FD-86–FD-87 | §17 scope algebra/member binding + §18 resolver | coverage/reachability tests |
| FD-88 | §18 reverse graph traversal + §20.3 impact traversal | graph/reconsider tests |
| FD-89 | §20.3 shared effect engine + §20.4 Functional Pyramid projection | reconsider/pyramid-write tests |
| FD-90 | §20.1 same-scope ask composition + §20.2 normative derivation | ask/record tests |
| FD-91 | §18 independent support/health evaluation + §20.1/§20.2 composition | support/ask/record tests |
| FD-92 | §20.1 lifecycle projection separation + §22 generated wire | MCP schema/integration tests |
| FD-93 | §20.4 Functional Pyramid record composition | lifecycle service/MCP tests |
| FD-94 | §22 skill/hook/host delivery | hook/skill/host-contract tests |

Version 1 also adapts established mechanisms whose functional ownership remains
in FD-1–FD-60:

| Existing functional owner | Version-1 adaptation |
| --- | --- |
| FD-2–FD-4 | §19 separates repository-scoped receipt/context identity from installation-scoped Functional Pyramid writes |
| FD-9–FD-16 | §18 adds FunctionalRouteSupport to the one existing support evaluator |
| FD-17–FD-22 | §20.3 extends the one reconsider/effect traversal across governance dependencies |
| FD-23–FD-29 | §20.1 composes Functional Pyramid orientation into existing Answer/Gap behavior |
| FD-30–FD-37 | §20.2 derives governance support inside the existing understanding writer |
| FD-38–FD-41 | §20/§22 extend existing closed public result/failure unions without another operation |
| FD-43–FD-48 | §19/§21 extend retention, replay, CAS and offline transition mechanics |
| FD-49–FD-58 | §22 extends generated wire, hooks, skills and managed-host delivery |


### 17. Canonical carriers, scope algebra and declaration boundary

**Authority:** F1, F6, F7, F11, F12; L7–L8, L12–L14; FD-62–FD-74,
FD-80, FD-82, FD-84, FD-86–FD-88.

Add one canonical core model module for Functional Pyramid domain carriers and
export those carriers through the existing `span.core.model` package. Do not
create setup/runtime DTO variants. The canonical family contains the Layer-2
identities, member intent/view, participation/effect, status/view/candidate,
findings, receipt selector/retrieval, rule/context declarations, route identity
and `FunctionalRouteSupport`. Existing `EvidenceRequest`, `EvidenceRef`,
`EvidenceScope`, `AuthorityBinding`, `SurfaceKey`,
`ChangedSurface`/`ChangedConclusion` and `InvestigationContextRef` remain
their current owners and are reused.

The public route projection uses the exact Layer-2 carriers
`FunctionalContextRoute`, `FunctionalRuleRoute`,
`FunctionalRouteProvenance`, `FunctionalPyramidFinding`,
`FunctionalPyramidValidationFinding`, `FunctionalPyramidView` and
`FunctionalPyramidUnavailable`; their field sets are not re-decided in the
wire/shell layer. Declaration carriers remain distinct from resolved route
carriers: declarations hold repository-owned references, while resolved rule
routes reuse the existing `AuthorityBinding`.

The new support union gains exactly one branch:
`FunctionalRouteSupport`. Its canonical payload contains the repository whose
semantic conclusion owns the dependency, the Functional Pyramid identity that
governed the revision, the exact persisted semantic `EvidenceScope`, and the
server-derived route identity. The route identity is a canonical digest/value of
FD-73 applicability state; canonical rule prose is never part of that digest or
carrier. Existing authority dependencies continue to carry each applicable
`AuthorityBinding` separately.

**FunctionalScope representation.** Implement one strict
`FunctionalScopeSelector` carrier and `FunctionalScope` as a canonical
non-empty tuple/set of those selectors. The same carrier is used by member
functional coverage and Functional Context applicability. Version 1 admits
exactly four selector kinds:

| kind | fields | meaning |
| --- | --- | --- |
| `REPOSITORY` | no path/locator | the complete repository functional region |
| `PATH` | normalized repository-relative `path` | exactly that path and semantic symbols owned by that path |
| `PREFIX` | normalized repository-relative directory `path` | that directory boundary and all descendant paths/symbols |
| `SYMBOL` | normalized owning `path` + canonical symbol `locator` | exactly that symbol |

No glob, regex, negation, suffix match or free-form selector exists in Version 1.
Paths use canonical POSIX-style repository-relative normalization; empty paths,
absolute paths, `.`/`..` traversal and trailing-separator aliases reject.
`REPOSITORY` is the only whole-repository representation.

Normalization deduplicates selectors and removes selectors wholly contained by
another selector in the same scope. The pure algebra is symbolic and never uses
current file inventory:

- REPOSITORY contains/intersects every selector;
- PREFIX contains an equal/narrower PREFIX, PATH, or SYMBOL whose owning path is
  inside the prefix boundary;
- PATH contains the same PATH and SYMBOLs owned by that path;
- SYMBOL contains only the same canonical symbol;
- two selectors intersect iff either contains the other under those rules.

For COMPLETE coverage, a member FunctionalScope is covered iff every normalized
member selector is contained by at least one normalized selector in the union of
applicable Functional Context coverage. A collection of narrower child prefixes
does not prove an open parent prefix or repository region complete; that avoids
inferring absence from current inventory. Set difference need only return
empty/non-empty plus the uncovered member selectors/provenance needed by FD-86;
it does not invent complement globs.

The resolver never converts an `EvidenceScope` into a second public selector
grammar. One pure adapter consumes the already-fixed semantic `SurfaceKey` and
`EvidenceScope`: FILE/SYMBOL owner kind supplies exact granularity; for
SERVICE/DOMAIN, each scope path member is interpreted through the existing
canonical semantic-containment owner—`containment.surface_file_locator` marks a
canonical structural symbol locator as an exact SYMBOL member and every other
path member remains a broad PREFIX boundary. A cold SERVICE/DOMAIN surface
projection constructs that EvidenceScope from both declared
`SurfaceBoundary.paths` and `SurfaceBoundary.symbols`. Only an explicitly
repository-wide semantic selection uses empty EvidenceScope as the whole
repository; an empty declared surface boundary is invalid/unresolvable rather
than repository-wide. This adapter evaluates that semantic selection against
FunctionalScope algebra and produces the FD-62 relation/provenance. It never uses
extensions, filesystem existence or inventory to decide granularity.

**Declarations and bootstrap.** Add the canonical domain carriers in
`src/span/core/model/functional_pyramid.py`, the pure resolver/algebra in
`src/span/core/functional_pyramid.py`, the orchestration service in
`src/span/service/functional_pyramid.py`, and the external source capability
in `src/span/ports/functional_pyramid.py`. The existing package exports remain
the public import boundary.

`FunctionalGraphRef` is the single canonical declaration-edge reference:
`{ "repository_id": str, "identity": str }`. It is used for both context and
rule edges; the containing field determines which identity namespace is
required. The target repository is always explicit, including for a local edge,
so there is no local shorthand/second grammar. Stable context/rule IDs remain
unique across the resolved instance; the repository coordinate additionally
makes FD-70 availability/ownership classification possible without a hidden
identity index. `ROOT` remains the sole non-reference terminal and is allowed
only where FD-67 permits it.

For discoverability, a repository may expose exactly one conventional navigation
bootstrap at `.span/functional-pyramid.json`. This bootstrap is configuration,
not authority. Its strict JSON shape is:

```text
{
  "version": 1,
  "functional_scope": [FunctionalScopeSelector, ...],
  "coverage": "PARTIAL" | "COMPLETE",
  "declaration_sources": [EvidenceRequest, ...]
}
```

The initialization skill may use this bootstrap to construct member intent, but
the public candidate/write still carries the explicit intent and therefore does
not depend on conversational discovery. Absence of the bootstrap is not inferred
as exclusion; the agent/user may supply the same explicit member intent directly.

Each named declaration source is strict JSON with one canonical document shape:

```text
{
  "version": 1,
  "contexts": [
    {
      "context_id": str,
      "coverage": [FunctionalScopeSelector, ...],
      "inherits": [FunctionalGraphRef, ...],
      "rules": [FunctionalGraphRef, ...]
    }
  ],
  "rules": [
    {
      "rule_id": str,
      "layer": "P0" | "P1" | "P2S" | "P2W" | "P3" | "P4",
      "owner": {"repository_id": str, "authority_ref": str},
      "governing_rule_ids": [FunctionalGraphRef | "ROOT", ...]
    }
  ]
}
```

P0 has exactly `ROOT`; other layers use the FD-67 governing-edge rules.
Documents may contain contexts, rules or both. A declaration's own context/rule
identity is owned by the repository containing that declaration source; every
edge names its target repository through `FunctionalGraphRef`. IDs are stable
and unique across the entire resolved pyramid instance; duplicate non-identical
owners are FD-65/FD-71 findings. A graph ref whose repository is not an instance
member is `INVALID_DECLARATION`; a ref into an unavailable member is
`REPOSITORY_UNAVAILABLE`; a missing identity in an available named member is
the corresponding `UNKNOWN_CONTEXT`/`UNKNOWN_RULE`. The document never
contains canonical rule prose.

The `FunctionalPyramidDeclarationPort` reads only the exact bootstrap/declaration
sources named by member intent across registered repositories. Version-1
declaration sources are whole documents: each member
`EvidenceRequest.ranges` must be empty. A non-empty ranges tuple is rejected as
`INVALID_DECLARATION_SOURCE` before declaration parsing; the port never treats
a selected fragment as a complete declaration document.

Its shell implementation resolves repository roots through the existing
`LifecycleStorePort.require_repository` owner and existing exact source
capability. Strict whole-document decoding creates the canonical carriers;
semantic graph validation remains pure core/service behavior. No directory
scan, similarity search, file-name inference or model call participates.

No persisted graph index is authoritative in the beta. Any in-memory or
persisted acceleration is a rebuildable projection of current member intent and
repository-owned declarations and must be discardable without changing a route
answer.

**Runtime composition boundary.** Version 1 has two construction levels and
they must not be collapsed.

A repository runtime is the raw registered-repository capability set: canonical
repository identity/root, its repository-scoped `LifecycleStore`, exact
filesystem evidence source and structural source. It contains no composed
`AnswerService`, `LifecycleService`, `SupportService`,
`ReconsiderService` or `ServiceContext`.

The installation runtime owns the registry/resolver of those raw repository
runtimes, the installation-scoped Functional Pyramid store, declaration and
repository-qualified authority/evidence access, one
`FunctionalPyramidService`, and the factory that composes ordinary repository
`ServiceContext` instances with those installation capabilities. The
Functional Pyramid service may depend on raw repository-runtime capabilities;
it must not obtain repository access through an already-composed
`ServiceContext`. MCP transport is downstream of this graph and never becomes
a semantic owner.

This split is required to avoid a composition cycle in which the Functional
Pyramid service depends on repository services that themselves require
Functional Pyramid orientation/support. No second repository-runtime DTO family
is introduced: the shell may use one internal typed capability object/port for
the raw runtime and the existing `ServiceContext` remains the composed
operation context.

**Version-1 service-construction contract.** Mandatory installation capabilities
are constructor invariants for the semantic services used by production
operations, not optional feature switches. The canonical production
`ServiceContext` composition supplies all of the following together:

- `AnswerService` receives the installation Functional Pyramid orientation
  projection;
- `LifecycleService` receives the installation Functional Pyramid route
  projection;
- `SupportService` receives both the Functional Pyramid route evaluator and
  the repository-runtime resolver used for repository-qualified authority and
  evidence access;
- `DependencyEffectService` receives the Functional Pyramid route-impact
  resolver, repository-runtime resolver, registered-repository resolver and
  repository-qualified support resolver; and
- `ReconsiderService` receives that already-composed
  `DependencyEffectService`.

No production semantic constructor may interpret an omitted capability as a
valid operating mode. In particular, `ReconsiderService` must not manufacture
a repository-local effect engine when the installation engine is absent,
`DependencyEffectService.repository_change` must not skip Functional Pyramid
route-impact traversal because a callback is absent, and `SupportService` must
not evaluate a cross-repository authority dependency through its local store
because the repository-runtime resolver is absent. If a constructor retains an
optional seam solely for isolated unit testing, invoking semantics that require
that seam must raise an invariant/programming error before a domain result is
created. Production composition and installed acceptance must never exercise
such a partial construction.

Unit tests that do not need a real installation may inject explicit typed
deterministic capabilities representing the intended participation state. They
must not obtain legacy behavior by omitting Functional Pyramid dependencies.

### 18. Pure graph resolver, health and support evaluation

**Authority:** G1, G3, G4, G7; F1, F2, F11, F12; L12–L16; FD-9–FD-16,
FD-62–FD-73, FD-75, FD-79–FD-81, FD-83, FD-86–FD-88, FD-91.

Add one pure Functional Pyramid resolver in `src/span/core/` with service
orchestration in `src/span/service/`. It accepts:

1. one ACTIVE instance/member view;
2. the existing semantic owner `SurfaceKey` plus its fixed `EvidenceScope`;
3. strict-decoded declarations/member availability.

`SurfaceKey` is not copied into FunctionalRouteSupport: a retained conclusion
already has one owning surface under FD-6, so support re-evaluation recovers that
canonical owner from the retained understanding and combines it with the
dependency's persisted semantic EvidenceScope.

It returns the canonical governing projection and route identity. Resolution
order is exactly FD-62/FD-68: compute the semantic-scope relation to
`FunctionalScope`, resolve only the functional intersection, compose every
applicable context, expand inheritance, resolve rule owners/governing edges to
closure, preserve unresolved branches and provenance, then derive the public
scope relation:

- `OUTSIDE_FUNCTIONAL_SCOPE` → resolved empty route;
- `COVERED` → no outside/uncovered portion;
- `UNCOVERED` → functional portion exists and has no applicable context;
- `MIXED` → broad scope contains more than one outside/covered/uncovered
  portion.

A MIXED route is RESOLVED only when every functional portion is covered and no
other structural unresolved branch exists. Outside portions never create
`UNCOVERED_PATH`.

The same declaration graph owns reverse navigation. Reverse traversal derives
dependent rules/contexts from the forward declaration edges; no second impact
registry is stored.

For FD-88 canonical-owner navigation, exact semantic selection of a
Functional Rule's canonical `FunctionalRuleOwner.authority_ref` is itself a
rule-resolution seed even when that selected owner scope is not covered by a
Functional Context. The resolver maps the exact selected owner reference through
the already-resolved `AuthorityBinding` set to the owning declared rule, then
uses the same forward/reverse declaration graph to derive downstream rules and
contexts. It does not perform semantic similarity, source scanning or maintain a
second authority-to-rule registry.

**Health.** One health evaluator consumes current ACTIVE member/declaration graph
state and returns `VALID` when the FD-83 structural finding set is empty,
otherwise `DEGRADED` with exactly those findings. Do not persist health. Do
not include authority currency, expected PARTIAL uncovered scope or semantic
support in health.

**Support.** Extend the existing support evaluator rather than creating a
Functional-Pyramid evaluator. Its dependency dispatch gains
`FunctionalRouteSupport`; evaluation re-runs the same resolver for the recorded
semantic scope/current participation state:

- repository deliberately no longer ACTIVE in the recorded governing instance →
  `REASSESSMENT_REQUIRED`;
- ACTIVE but route/member/declaration evaluation operationally unavailable →
  `UNVERIFIABLE`;
- resolved route identity changed → `REASSESSMENT_REQUIRED`;
- current functional route contains unresolved functional branch →
  `UNVERIFIABLE`;
- identical complete resolved route → `CURRENT`.

Authority dependencies remain evaluated through the existing authority-support
branch. FD-15/FD-16 remain the sole combined-state owner.

**Repository-qualified support access.** The existing support evaluator is the
single evaluator, but its external capabilities are repository-qualified.
Evaluating an `AuthoritySupportDependency` or evidence reference uses the
repository id carried by that canonical dependency/reference to obtain the
registered repository runtime that owns the authority/evidence. A semantic
revision owned by repository A may therefore be governed by canonical authority
owned and re-read from repository B without copying B's authority/evidence into
A. Repository-local stores remain the owners of their own authority bindings and
observations.

Functional Pyramid route evaluation is likewise a required installation
capability of the Version-1 runtime. Absence of the production composition is
not a domain state: a missing route/orientation/effect capability must fail as a
program/invariant error and must never be converted to UNCONFIGURED, empty
governance, skipped route propagation or an operational UNVERIFIABLE result.
Operational unavailability after correct composition remains the explicit
UNVERIFIABLE/Unavailable behavior defined above. Unit tests may supply typed
deterministic fakes at these ports; production assembly may not omit them.

### 19. Installation-level persistence, receipts and concurrency

**Authority:** A1–A3; F3, F12; L4, L13–L15; FD-3–FD-4, FD-43–FD-48,
FD-61, FD-82, FD-85.

The existing `LifecycleStore` is repository-scoped: the shell opens
`<data_dir>/<repository_id>.db` and ordinary semantic/audit state remains owned
there. Version 1 must not pretend that one of those files is installation-wide
or select one member repository as the Functional Pyramid coordinator.

Add one installation-scoped SQLite owner,
`FunctionalPyramidInstallationStore`, at
`<data_dir>/installation/functional-pyramid.db`. It is the sole durable owner
of Functional Pyramid participation, instance versions, exclusions and
installation-scoped receipts. It stores no ordinary understanding, source
observation, verification or repository-owned governing prose.

Repository lifecycle schema 14 retains every schema-13 table and adds only the
repository-local derived route lookup projection:

| repository-store table | key / purpose |
| --- | --- |
| `functional_route_dependency_index` | conclusion revision key + `pyramid_id` + owning `repository_id` + route identity; derived lookup projection over canonical FunctionalRouteSupport |

The installation store has its own schema identity, version 1, and owns exactly:

| installation-store table | key / purpose |
| --- | --- |
| `functional_pyramids` | `pyramid_id PRIMARY KEY`, current live version; row exists only for a live ACTIVE instance |
| `functional_pyramid_versions` | `(pyramid_id, version) PRIMARY KEY`; immutable canonical complete member intent + digest/commit time |
| `functional_pyramid_active_members` | `repository_id PRIMARY KEY`; current `pyramid_id`, version and canonical member intent projection; this key enforces one ACTIVE instance per repository |
| `functional_pyramid_exclusions` | `repository_id PRIMARY KEY`; explicit EXCLUDED state; absence from both active-members and exclusions means registered repository state UNCONFIGURED |
| `functional_pyramid_receipts` | `request_id PRIMARY KEY`; digest, action, commit/replay times, pyramid/version, resulting members, participation effects and immutable dependent-effect refs |

Repository registration/root/authority configuration remains owned by each
repository LifecycleStore and the installed repository routing configuration;
the installation store does not duplicate that configuration. Candidate/write
service composition revalidates member registration before committing an
installation record.

Canonical `FunctionalRouteSupport` remains inside each conclusion's existing
canonical support dependency set. Repository schema 14 extends the existing
`support_dependencies` projection with dependency kind `FUNCTIONAL_ROUTE`;
its `dependency_ref` is the canonical route identity.
`functional_route_dependency_index` is only a rebuildable repository-local
lookup projection and never a second support model.

The immutable Functional Pyramid receipt stores the canonical write digest,
action, committed time, affected pyramid/version, resulting ACTIVE member set,
actual durable participation changes, and immutable semantic dependent-effect
coordinates. It does not store live support qualification, health or
investigation-context liveness. Public
`RetrievedFunctionalPyramidReceipt` projects this exact acceptance.

Functional Pyramid receipt decision uses the same core replay/conflict algorithm
as ordinary recording but the installation store owns its distinct request-id
namespace. Do not coerce the write into `RecordingIdentity`.

**Atomic cross-repository participation writes.** The installation store opens
its real file as SQLite `main` and ATTACHes the affected repository lifecycle
databases under generated internal schema aliases. The transaction is permitted
only when the installation database and every attached repository database use a
rollback-journal mode that preserves SQLite multi-database atomicity; WAL/OFF/
MEMORY journal modes or `synchronous=OFF` are explicit operational blockers,
never silently downgraded at runtime. Installation/provisioning establishes the
supported rollback-journal configuration.

Use one `BEGIN IMMEDIATE` transaction across `main` plus all affected
attached repository databases. This acquires the write reservation before
effect computation, so ordinary repository writers cannot change semantic state
between the accepted effect decision and commit. The service-owned shared effect
engine runs while those locks are held; shell SQL does not classify effects.

The transaction boundary and semantic-decision boundary remain distinct. Shell
persistence acquires/holds the installation plus repository locks and exposes
repository-qualified transaction capabilities. Service composition evaluates
the old/new Functional Pyramid delta through the one shared effect engine while
those locks are held. The transaction writer persists only the resulting
participation/version state, immutable dependent-effect refs, canonical context
rows and receipt. Shell code must not compute changed route identities, group
semantic effect refs by repository, instantiate a semantic support evaluator for
projection, merge `ChangedSurface` semantics or classify activation/deactivation
effects. Replay projects only the retained immutable refs through the same
service-owned support/effect capabilities.

ACTIVATE/REVISE/DEACTIVATE then commit atomically:

1. installation receipt replay/conflict decision;
2. target pyramid CAS and unique-ACTIVE-member checks;
3. current dependent-effect calculation against the locked repository stores;
4. immutable pyramid version/current membership and participation effects;
5. immutable dependent-effect refs in the installation receipt;
6. initial repository-bound re-establishment contexts in the affected attached
   repository stores; and
7. the installation receipt.

The context row writer is factored from the existing LifecycleStore persistence
mechanism and reused for both ordinary and attached-database context creation;
there is no second context format or writer rule. A context-issuance failure
rolls back the entire multi-database transaction.

EXCLUDE uses the same installation receipt/participation transaction but has no
active-route semantic effects and therefore need not attach repository stores
for effect/context writes after registration/state validation.

Replay keeps the immutable accepted effect refs. Service composition re-evaluates
only those retained refs against current repository support/membership and
issues fresh repository-bound contexts when they remain actionable; it never
adds later effects to the accepted receipt.

Concurrent REVISE/DEACTIVATE use pyramid-version CAS. Concurrent
ACTIVATE/REVISE serialize on the installation store and the unique ACTIVE-member
key; affected repository databases are locked in deterministic repository-id
order before effect computation. SQLite ATTACH capacity is an operational
environment limit: inability to attach the required member set returns
Unavailable and never changes product semantics or partially commits.

### 20. Operation composition and governance-change propagation

Authority is split by operation below; §20 does not create a second functional
owner.

**Installation composition.** The shell constructs one installation runtime
before it composes ordinary repository services. Its repository-runtime resolver
opens raw registered repository capabilities independently of
`ServiceContext`. The installation Functional Pyramid service uses those raw
capabilities for declaration, authority/evidence and state access. The repository
context factory then supplies that same installation capability set to the
ordinary support, lifecycle, answer and reconsider/effect services.

Production Functional Pyramid dependencies are mandatory, not optional
behavioral callbacks. A Version-1 process therefore has one coherent state
projection: the same repository cannot be ACTIVE through
`FunctionalPyramidSelector` while an ordinary ask treats it as UNCONFIGURED,
and an ACTIVE NORMATIVE record cannot silently omit route/authority support
because a callback was absent.

Every shell consumer that needs semantic services enters through the same
installation composition root. The MCP server may register repository locators
without opening repository stores, but the first repository-scoped operation
must obtain its `ServiceContext` from `InstallationRuntime`. Read-only host
hooks that evaluate support or changed dependents must likewise open a bounded
installation runtime for the hook invocation and compose the target repository
through it. Hooks must not call a repository-context helper that requires
Functional Pyramid capabilities they do not own, and must not recreate a local
support/effect graph.

Explicit installer/provisioning code is the only exception because it is not a
semantic runtime operation: it may create/verify the installation store and
open the raw repository runtime needed to initialize a repository, but it must
not fabricate a partially composed `ServiceContext`. Provisioning ownership
remains in the installer/context setup path; MCP startup registration does not
restore a public or implicit provisioning path.

**Beta-3 administrative initialization correction (B3-D01/B3-D02).** Beta-1
external integration use exposed a composition defect, not a missing Functional Pyramid
product rule. The released `span-install` never invokes the already-owned
`provision_repository_runtime(InitializeRepositoryRequest)` path, and its
installed production-topology fixture manufactures repository/binding state
directly. Beta 3 therefore repairs the shell/setup seam and the acceptance seam
without introducing another authority model, setup DTO, semantic writer, MCP
operation or Functional Pyramid lifecycle.

The initialization correction is schema-neutral in itself. In Beta 1 the
omission affected schema 14. In the complete Beta-3 release the same canonical
provisioning path creates/opens the **current Beta-3 repository schema 15**
defined by Part D; installation Functional Pyramid schema 1 remains unchanged.

The exact mechanism is:

1. `span-install` remains the sole mutating administrative entry point.
   Runtime `ask`/`record`/`reconsider`, host startup registration,
   `--dry-run` and `--verify-only` remain non-initializing.
2. Repository authority configuration is explicit and repository-qualified:
   repeatable
   `--authority-seeds-file REPOSITORY_ID PATH` and
   `--authority-bindings-file REPOSITORY_ID PATH`. Each file is a strict JSON
   list of the existing canonical `EvidenceRef` or `AuthorityBinding`
   carrier respectively; there is no setup-specific wrapper/domain carrier.
3. The repository-id argument is shell routing metadata only. Every decoded
   item must carry the same repository identity. Duplicate mappings, a mapping
   for an unselected repository, malformed canonical content, or repository-id
   disagreement reject before the first repository-store mutation.
4. The shell preserves `InitializeRepositoryRequest` tri-state semantics for
   both families: missing mapping = `None`/preserve; mapped `[]` =
   `()`/clear; mapped non-empty list = replace with that exact tuple.
5. All deterministic configuration decoding/validation completes before
   repository-state mutation. The existing data-directory backup is taken
   before initialization mutates an existing installation.
6. After runtime/indexer preparation, the installer invokes
   `provision_repository_runtime` exactly once for each selected repository
   with one canonical `InitializeRepositoryRequest`, retains the returned
   `InitializeRepositoryResult`, closes the raw runtime, and only then
   performs host registration and observational verification.
7. `provision_repository_runtime` remains the sole owner of structural
   `ensure_current`, installation-store creation/verification,
   repository-store creation/open, evidence-locator validation and
   `initialize_repository` dispatch. The installer does not reproduce those
   mechanics or fabricate a partial `ServiceContext`.
8. Initialization remains repository-local administration, not Functional
   Pyramid participation. It may establish the authority state required by
   candidate validation but never ACTIVATEs/REVISEs/DEACTIVATEs/EXCLUDEs a
   pyramid and creates no cross-repository setup transaction.
9. The install receipt reports observed `InitializeRepositoryResult`
   projections for each successfully initialized repository (repository id,
   canonical root, current repository schema, structural/store readiness and
   resulting seed/binding counts). Input presence is not success evidence.
10. A later operational failure names the repository that failed and preserves
    the pre-mutation backup. It does not silently continue or claim all-or-nothing
    cross-repository setup.

**Acceptance escape-hatch correction.** At least one non-editable installed
production-topology lane must begin with target repositories plus an empty data
directory and establish both repository lifecycle stores and declared authority
state through the installed `span-install`. That lane may not call
`LifecycleStore.register_repository` or inject `AuthorityBinding` directly
for setup. Lower-level store/service tests may still construct state directly
when that lower layer is the subject under test.

#### 20.1 `ask`

**Authority:** F6, F10, F11, F12; L1–L3, L8, L12–L14, L16;
FD-23–FD-29, FD-61, FD-74, FD-78, FD-83–FD-84, FD-90–FD-92.

Extend the existing `AskRequest` selector union and generated wire from its
canonical model declaration with:

- `FunctionalPyramidSelector`;
- `FunctionalPyramidCandidateSelector`;
- `FunctionalPyramidReceiptSelector`.

Extend the Ask result union with `FunctionalPyramidStatus`,
`FunctionalPyramidCandidate` and
`RetrievedFunctionalPyramidReceipt`. Extend ordinary `Answer`/`Gap` with
the Layer-2 `functional_pyramid` projection. Do not add another tool or a
second answer composer.

`AnswerService` keeps semantic membership/Answer/Gap composition unchanged.
The Functional Pyramid projection first resolves exact repository participation.
UNCONFIGURED/EXCLUDED project participation directly and do not require
ACTIVE-only semantic-scope conversion. For ACTIVE members, AnswerService supplies
the exact semantic scope and the Functional Pyramid service invokes the resolver
from §18 on that scope. If a current semantic surface cannot be converted to the
required exact Functional Pyramid scope, the ACTIVE overlay projects
`FunctionalPyramidUnavailable`; it does not widen the surface, invent
repository-wide scope, or discard otherwise-current descriptive semantic
content. ACTIVE operational graph failure likewise projects
`FunctionalPyramidUnavailable`.

Candidate validation is a pure service call over the proposed member intent plus
current registered/declaration state. It uses the FD-84 reason taxonomy and the
same graph/coverage validators as activation. It persists nothing.

Status selectors are exact identities. A registered repository absent from both
active membership and exclusion is UNCONFIGURED; an explicitly excluded
registered repository is EXCLUDED; an active registered repository is ACTIVE.
An unknown repository identity is an exact-lookup rejection, never
UNCONFIGURED. A pyramid-id selector resolves only a known live/current pyramid
identity; an unknown or non-live pyramid identity follows the existing exact
public lookup-failure taxonomy and is never coerced into repository
participation state.

Candidate evaluation accumulates every deterministic finding that can be
established from the submitted candidate. A lifecycle-invalid member may be
uninspectable itself, but its finding must not short-circuit declaration,
coverage, authority or graph validation for the other validly inspectable
members. The ordered validation/graph finding sets are therefore the complete
deterministic result available for that candidate.

#### 20.2 understanding `record`

**Authority:** F2, F5, F7, F11; L7, L12, L16; FD-30–FD-37,
FD-75–FD-77, FD-90–FD-91.

Keep the existing create/update command owners and transaction path. After
semantic scope and assertion nature are fixed and before a NORMATIVE revision is
accepted in an ACTIVE repository, service composition resolves the governing
route and adds one `FunctionalRouteSupport` plus every applicable
`AuthoritySupportDependency` to the canonical dependency set. A scope wholly
OUTSIDE_FUNCTIONAL_SCOPE records the resolved empty route dependency and no
invented Functional Pyramid authority dependency. DESCRIPTIVE recording remains
unchanged unless the caller explicitly cites authority.

If derived governance is non-current, acceptance still follows the existing
semantic write path; live qualification is non-current and F2 keeps the revision
out of CURRENT Answer content. The service does not manufacture a second
"completed" result: agent lifecycle guidance consumes the returned
`UnderstandingRecorded.qualification`, and only CURRENT required qualification
permits successful CONCLUDE/REESTABLISH completion.

#### 20.3 `reconsider` and shared effect engine

**Authority:** G3; F4, F11, F12; L10, L15–L16; FD-17–FD-22,
FD-79, FD-88–FD-89.

Keep the existing repository-scoped changed-path/surface request grammar.
Refactor the current reconsider dependency traversal into one service-owned
effect engine with two internal root types:

- repository changed scope;
- Functional Pyramid old/new participation/route delta.

Both roots produce the same canonical affected conclusion/surface projection,
then premise closure, deterministic grouping and one context specification per
repository with actionable effects. The public `reconsider` operation projects
that as `Changed`; Functional Pyramid write composition projects the same
`ChangedSurface` family inside `FunctionalPyramidRecorded`.

The effect engine is genuinely installation-aware while remaining service-owned.
It receives repository-qualified store/support/context capabilities, not one
repository `LifecycleStore` treated as if it represented the installation. Its
constructor has no single-store/single-support operating mode: repository access
is always through the repository-runtime resolver, support qualification is
always through the repository-qualified support resolver, and the registered
repository resolver defines the search boundary. A one-repository unit test uses
a one-entry resolver/registry; it does not switch the service into another
architecture.

The engine uses the repository that owns each canonical dependency index to
discover direct dependents, resolves the semantic owner of each affected
conclusion, re-evaluates support through the repository-qualified support
capability, performs premise closure once, groups canonical `ChangedSurface`
results by owning repository, and produces exactly one context specification for
each repository with actionable effects. Ordinary reconsider and Functional
Pyramid writes invoke this same engine. A shell-side loop over per-repository
semantic effect engines or a second Functional-Pyramid-specific effect
coordinator is forbidden.

For an ordinary changed-scope root, Functional Pyramid route-impact traversal is
unconditional. The engine always asks the installation route-impact capability
for changed route identities, including when the repository is currently
UNCONFIGURED or EXCLUDED; those states yield the canonical empty impact set.
Absence of the capability is not equivalent to an empty set and must fail as a
composition invariant. `ReconsiderService` therefore never has authority to
construct a reduced repository-local `DependencyEffectService`.

For a repository newly becoming ACTIVE, the Functional Pyramid root additionally
selects every current NORMATIVE revision in that repository that lacks
`FunctionalRouteSupport`; those revisions are direct
`REASSESSMENT_REQUIRED` effects. This is the mechanism for FD-79 and avoids
fabricating historical support.

Existing authority-source edits continue to use changed-scope reconsider. The
effect engine re-evaluates canonical route/authority support rather than marking
conclusions stale merely because a declaration file path matched.

#### 20.4 Functional Pyramid `record`

**Authority:** G3, G8; F4, F6, F7, F12; L4, L8, L14–L15;
FD-82, FD-84–FD-85, FD-89, FD-93.

Add the Layer-2 `functional_pyramid` branch to the existing record decoder and
service dispatcher; do not create a fourth MCP operation. It does not use
`RecordingIdentity` or an evidence investigation context. It uses the
installation-level request namespace from §19, strict action-aware candidate
revalidation, the shared effect engine above, and one atomic store transaction.

On first acceptance, the result contains the resulting ACTIVE members, only
actual durable `FunctionalPyramidParticipationEffect` transitions, the
canonical dependent `ChangedSurface` projection and one live repository-bound
context per repository with actionable effects. The receipt stores only the
immutable dependent `ConclusionRevisionRef` identities. On replay, §19
re-evaluates only those retained refs to produce the current actionable
`ChangedSurface` projection and fresh contexts; replay never expands the
accepted effect identity set. Receipt selectors from accepted participation
writes remain the durable public handoff across subsequent DEGRADED repair or
revision loops so earlier accepted effect refs cannot disappear from lifecycle
completion merely because a later pyramid write occurs.

### 21. Offline transition and compatibility boundary

**Authority:** F2–F4, F12; L4, L12–L15; FD-35–FD-48, FD-73, FD-79,
FD-81, FD-85.

The first Version-1 Beta release identity is **1.0.0 Beta 1** and its
lifecycle store identity is schema 14. That one release identity has deterministic
ecosystem serializations rather than independent version owners:

- Python/PyPI package version and changelog section: `1.0.0b1` (PEP 440);
- Git tag: `v1.0.0b1`;
- GitHub Release: title `Span 1.0.0 Beta 1`, explicitly marked prerelease;
- MCP Registry top-level server version: `1.0.0-beta.1` (SemVer);
- MCP Registry PyPI package entry version: `1.0.0b1`.

`src/span/__init__.py::__version__` remains the canonical package serialization.
Release tooling derives the tag, changelog lookup and PyPI package version from
that value and derives the MCP server SemVer deterministically; `server.json`
metadata is a generated/validated release projection, not a second version
authority. Prerelease detection must understand PEP-440 beta/rc/dev forms and
must not rely on the presence of a hyphen in the package version.

Later beta increments may advance the release/package version without changing
schema identity when no persisted contract changes; any persisted-contract
change requires a new explicit schema transition.

Extend the existing explicit offline repository-store transition from schema
13 to repository schema 14. Runtime open remains exact-version only and never
migrates in place. The explicit installer/setup path creates or verifies the
installation Functional Pyramid store at
`<data_dir>/installation/functional-pyramid.db` with installation schema 1;
the repository transition command remains repository-scoped, and pure runtime
`ask` never creates or migrates either store.

The repository schema-13 → schema-14 transition preserves every existing
semantic/audit row and receipt exactly and adds the empty derived
`functional_route_dependency_index`. The installation store begins with empty
pyramid/version/member/exclusion/receipt state. Existing registered repositories
therefore begin UNCONFIGURED because registration is not participation.
Historical and current NORMATIVE revisions are **not** backfilled with invented
FunctionalRouteSupport.

Consequently, transition alone changes no semantic conclusion's support state.
When a repository is later ACTIVATED, §20.3 selects current pre-activation
NORMATIVE revisions without route support and returns them as
REASSESSMENT_REQUIRED dependent effects. This is the only migration path from
pre-Version-1 normative understanding into governed current understanding.

The transition verifies:

- every pre-existing semantic/audit count and reference under the current
  schema-13 preservation rules;
- repository schema-14 route index exists and is empty after transition;
- installation schema-1 pyramid/member/exclusion/receipt state is empty;
- no FunctionalRouteSupport is fabricated for existing revisions;
- installation-store unique ACTIVE-member constraint is present;
- ordinary repository receipts remain in their original per-repository namespace;
- installation Functional Pyramid receipts are independently keyed;
- full data-directory backup/restore includes the installation database, while
  repository-portable backups continue to contain only that repository's
  lifecycle store and never claim to carry cross-repository participation state.

Existing archive/stage/verify/activate/rollback ownership remains unchanged.

### 22. Host delivery, skills and Version-1 verification

**Authority:** A4, A8, A9; F6, F8, F10, F12; L8, L12–L16; FD-38–FD-58,
FD-92–FD-94 and functional acceptance §15.

Generate all new selector/result branches from the canonical model/schema owner.
The shell MCP adapter remains transport-only and may not classify Functional
Pyramid semantics from strings, paths or runtime class names. Exactly three
advertised tools remain `ask`, `record`, `reconsider`.

Update the Functional Pyramid skill and managed notices only after the canonical
wire is generated. Initialization guidance must consume the Layer-2 result gates,
not merely call names:

`STATUS → DISCOVER/VALIDATE → DECLARE when needed → reconsider/disposition →
VALIDATE → ACTIVATE/REVISE → VERIFY → REESTABLISH when accepted write effects
remain actionable → ACTIVE`.

DEACTIVATE likewise consumes its returned dependent effects before the
deactivation task is called complete. An accepted participation write is never
treated as completion solely because it returned a receipt. The skill retains
the returned Functional Pyramid receipt selector/effect obligation across any
DEGRADED repair/revision loop and uses replay/live projection when fresh
re-establishment contexts are required.

Ordinary runtime guidance likewise checks
`UnderstandingRecorded.qualification`: accepted but non-current NORMATIVE
content returns to investigation/re-establishment instead of successful
COMPLETE. Conformance guidance always records that judgment as NORMATIVE.
Participation/health notices use the canonical status/health evaluator and
affected projections, never an independent hook computation.

Extend the §16 verification matrix and installed MCP/host lanes to cover every
functional-design §15 case, specifically:

- OUTSIDE_FUNCTIONAL_SCOPE and broad MIXED scope;
- VALID/DEGRADED iff structural findings;
- pre-existing normative revision invalidation on activation;
- ACTIVATE/REVISE/DEACTIVATE dependent effects and per-repository contexts;
- removal/deactivation REASSESSMENT_REQUIRED versus ACTIVE operational
  UNVERIFIABLE;
- Functional Pyramid receipt replay with fresh expired-context recovery;
- pyramid CAS and overlapping activation concurrency;
- initialization declaration-edit reconsideration and post-write effect
  disposition before successful adoption/revision/deactivation completion;
- accepted non-current NORMATIVE record results returning to
  investigation/re-establishment rather than successful COMPLETE;
- conformance judgments using the NORMATIVE assertion contract;
- preservation of every pre-Version-1 semantic lifecycle branch and exactly
  three public MCP tools.

Managed-host captures are candidate-specific delivery evidence only. Historical
0.10/0.11 captures remain evidence for their named candidates and do not certify
the Version-1 grammar.

**Production-topology acceptance.** At least one non-editable installed MCP lane
must exercise physically separate repository-A and repository-B lifecycle
databases plus the installation Functional Pyramid database. The fixture must
contain a rule consumed by semantic scope in A whose canonical
`AuthorityBinding` and authority evidence are owned by B. The lane must prove,
through the production composition root:

```
activate A+B
→ ordinary ask(A scope) returns the governing projection
→ NORMATIVE record in A derives FunctionalRouteSupport plus B authority support
→ reuse/ask qualifies CURRENT
→ B canonical governance source or applicability changes
→ ordinary reconsider(B changed scope) reaches the dependent A conclusion
→ A re-establishes through the returned repository-bound context
→ required qualification is CURRENT again
```

The same verification set must prove exact canonical-owner reverse navigation,
unknown repository/pyramid status rejection, complete mixed candidate findings,
and architecture guards preventing shell semantic effect coordination or
optional production Functional Pyramid dependencies. Component tests that
manually inject Functional Pyramid callbacks do not satisfy this production
composition requirement.

The architecture guard must inspect both composition sites and service behavior:
the production `ServiceContext` factory supplies every mandatory capability;
`ReconsiderService` has no local effect-engine fallback;
`DependencyEffectService` has no single-store/single-support constructor mode;
ordinary `DependencyEffectService.repository_change` cannot conditionally omit
route impact traversal; repository-qualified authority evaluation cannot silently
fall back to the semantic owner's local store for an external authority; and
semantic hook paths compose through `InstallationRuntime`. A green installed
journey does not waive any of these static ownership checks.

**2026-11-22 design-detail audit.** The adversarial implementation audit found
no contradiction requiring a Layer-0–3 product/functional amendment. It found
that the prior Part-C text was not construction-complete at the installation
composition, repository-qualified support and multi-repository effect-engine
seams. The paragraphs above close those Layer-4 mechanism gaps without changing
the governing Layer-0–3 behavior.

Part C is complete only when the mechanisms above are implemented and the
functional acceptance matrix passes without adding a product rule below Layer 3.

## Part D — Beta 3 capture/curation mechanisms

Part D realizes the Beta-3 capture/curation contract in F13, L17 and
FD-95–FD-102. It does not change Functional Pyramid authority, the three-tool
surface, or semantic authorship. Part C remains the mechanism authority for the
Functional Pyramid except where Part D composes curation into ordinary semantic
reuse.

### Part-D derivation map

| Functional authority | Primary technical mechanism | Verification owner |
| --- | --- | --- |
| FD-95, FD-101 | §24 ask/status composition | answer/status service + MCP integration |
| FD-96, FD-98 | §24.2 understanding-writer transition rules | lifecycle service/store tests |
| FD-97 | §23 immutable curation persistence + §24.2 record composition | lifecycle store/service CAS/replay tests |
| FD-99 | §24.1 deterministic pending-curation query | store/query + MCP selector tests |
| FD-100 | §24.3 composition boundary reusing Part-C governance support | support/Functional Pyramid isolation tests |
| FD-102 | existing challenge/update owners + §24.2 curation exclusivity | lifecycle/challenge integration tests |
| functional acceptance 45–64 | §24–§27 | unit/integration/transition/installed-MCP lanes |

### 23. Canonical curation carriers and persistence

**Authority:** G2; A10; F2, F3, F5, F7, F13; L4, L7, L17;
FD-95–FD-102.

Use the existing canonical model modules rather than creating a curation DTO
family:

- `src/span/core/model/commands.py` owns
  `CurateConclusion{conclusion_id: ConclusionId, reasoning: str}` and adds
  `curate: tuple[CurateConclusion, ...]` to `UpdateUnderstandingCommand`;
- `src/span/core/model/understanding.py` owns
  `CurationState = CAPTURED | CURATED`,
  `CurationOrigin = EXPLICIT | INHERITED_CONFIRMATION`,
  `CurationDisposition`,
  `PendingCurationSelector`,
  `PendingCurationItem`, and `PendingCuration`;
- `src/span/core/model/surfaces.py` owns
  `PendingConclusionRef{ref, understanding_version}` beside
  `StaleConclusionRef` and extends `SurfaceStatus` with
  `pending`/`pending_refs`;
- `src/span/core/model/answers.py` adds `PENDING_CURATION` to `GapReason`
  and `PendingCuration` to `AskResult`;
- `RetrievedUnderstanding` gains
  `curations: tuple[CurationDisposition, ...]` for exact historical/current
  audit projection.

The exact public carriers are those fixed by lifecycle §4.1. In particular,
`PendingCurationSelector.after` is an optional exact
`ConclusionRevisionRef` keyset cursor and `PendingCuration.next_after` is
the exact last returned ref when truncation requires another page. No opaque
second continuation grammar is introduced.

`CurationDisposition` has exactly:

```text
ref: ConclusionRevisionRef
accepted_in_version: UnderstandingVersionNumber
reasoning: str
provenance: str
recorded_at: datetime
origin: EXPLICIT | INHERITED_CONFIRMATION
inherited_from: ConclusionRevisionRef | None
```

`origin=EXPLICIT` requires `inherited_from=None`.
`origin=INHERITED_CONFIRMATION` requires `inherited_from` to name the
immediate confirmed predecessor in the same understanding/conclusion lineage.
The inherited record preserves the predecessor's reviewer reasoning/provenance
as historical facts but records the confirmation transaction time/version and
the inherited origin explicitly; it never pretends another reviewer acted.

Do not add a mutable `curated` boolean to `SupportedConclusion` and do not
copy semantic content into a second approval record. Current `CurationState`
is derived from exact-revision disposition existence.

Schema 15 adds exactly one repository table:

```sql
CREATE TABLE conclusion_curations(
    understanding_id TEXT NOT NULL,
    conclusion_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    accepted_in_version INTEGER NOT NULL,
    origin TEXT NOT NULL
        CHECK(origin IN ('EXPLICIT', 'INHERITED_CONFIRMATION')),
    inherited_from_revision INTEGER,
    canonical_json TEXT NOT NULL,
    PRIMARY KEY(understanding_id, conclusion_id, revision),
    FOREIGN KEY(understanding_id, conclusion_id, revision)
        REFERENCES conclusions(understanding_id, conclusion_id, revision),
    FOREIGN KEY(understanding_id, accepted_in_version)
        REFERENCES understanding_versions(understanding_id, version),
    FOREIGN KEY(understanding_id, conclusion_id, inherited_from_revision)
        REFERENCES conclusions(understanding_id, conclusion_id, revision),
    CHECK(
        (origin='EXPLICIT' AND inherited_from_revision IS NULL)
        OR
        (origin='INHERITED_CONFIRMATION'
         AND inherited_from_revision IS NOT NULL)
    )
)
```

`canonical_json` is the canonical serialization of
`CurationDisposition`; the indexed structural columns must agree with that
carrier on write/read. No second curation table or approval column is allowed.
The primary key is sufficient for exact-revision lookup and the pending query's
left join; add no speculative index without measured query evidence.

Historical projection is version-aware: a snapshot at understanding version V
considers a revision curated only when its disposition has
`accepted_in_version <= V`. This preserves capture → later curation without
rewriting prior snapshots.

### 24. Ask, record and re-alignment composition

**Authority:** F2, F5–F7, F13; L2–L8, L11, L17; FD-23–FD-37,
FD-95–FD-102.

#### 24.1 `ask`

Extend the existing canonical selector/result union with
`PendingCurationSelector` and `PendingCuration`. The repository-local queue
is the current understanding membership whose exact revision has no curation
disposition **and** whose existing support evaluator returns CURRENT.
Non-current CAPTURED revisions remain stale/re-establishment work and are not
also pending.

The query order is exactly ascending
`(understanding_id, conclusion_id, revision)`. When
`selector.after` is present, resume strictly after that exact tuple. Apply the
existing response budget to whole `PendingCurationItem` values. If truncated,
return `next_after` equal to the last emitted item's exact ref; if not
truncated, `next_after=None`. The item's statement is not copied: the reviewer
uses its exact snapshot coordinates to retrieve content.

The one AnswerService composes semantic support and curation state. A conclusion
is Answer-eligible only when its existing support evaluator returns CURRENT and
the exact revision has a curation disposition effective in the current
understanding version. CURRENT + CAPTURED revisions project only through pending
status/references; any non-current revision projects only through the existing
stale/historical path. If no eligible conclusion exists but CURRENT captured
membership does, the existing Gap composer returns
`reason=pending_curation`.

Do not create a curation-specific answer composer or support evaluator.

#### 24.2 understanding `record`

Extend the existing `UpdateUnderstandingCommand`/understanding-writer owner
with `curate`. The action resolves every supplied lineage against
`expected_version`, derives each exact current revision, then runs the existing
support evaluator before mutation. Every target must be CURRENT at that moment;
otherwise reject the whole update with the existing typed
`Rejected/validation` path and a public recovery instructing the reviewer to
re-establish support first.

On acceptance the one existing understanding CAS transaction:
1. creates version `expected_version + 1` with unchanged conclusion membership;
2. inserts one EXPLICIT `conclusion_curations` row per target, with
   `accepted_in_version` equal to that new version;
3. writes the ordinary recording receipt; and
4. composes the ordinary `UnderstandingRecorded` result/status from committed
   state.

The curation action:
- changes no semantic conclusion content or support;
- creates no conclusion revision;
- cannot contain add/confirm/correct/replace/withdraw actions;
- uses the existing repository-scoped request identity, content digest, replay
  and conflict semantics;
- reports the curated exact refs through the existing
  `UnderstandingRecorded.affected_revisions`.

Semantic create/add/correct/replace commit without a curation disposition for
their new revisions. Withdrawal remains non-reusable.

Confirm keeps its existing semantic identity rule. If the predecessor revision
is CURATED, the same confirmation transaction creates the new revision and one
INHERITED_CONFIRMATION curation row that points to the exact predecessor; both
belong to the new understanding version. If the predecessor is CAPTURED, no
curation row is created. This is a mechanical carry-forward of an existing
publication decision, not a new reviewer judgment.

#### 24.3 reconsider and Functional Pyramid composition

The existing effect engine continues to traverse retained revisions regardless
of curation state. `reconsider` changes support state only and never mutates
curation.

Part-C Functional Pyramid route/authority derivation and evaluation are reused
unchanged. Curation storage has no participation, graph, route, authority or
health writer. A query may therefore observe any combination allowed by Layer 3,
including CURATED + non-current governance and CAPTURED + current governance;
only CURRENT + CURATED is ordinary Answer content.

### 25. Repository schema 15 and explicit transition

**Authority:** A1–A3; F2–F4, F13; L4, L17; FD-42–FD-48,
FD-95–FD-102.

Beta 3 is a persisted-contract change and therefore advances the repository
lifecycle store:

- Beta-1 repository schema: 14;
- Beta-3 repository schema: **15**;
- installation Functional Pyramid schema remains **1**.

The canonical transition owner remains `src/span/shell/store_transition.py`.
Set its target to schema 15, add schema 14 to the supported source set, and add
one mapping module `src/span/shell/store_transition_schema14.py`. Do not create
another transition command or runtime migration path.

The schema-14 mapping copies every existing repository table and relationship
into a fresh schema-15 staging store under the same preservation/reconciliation
rules used by the current transition architecture. In particular it preserves
repositories (including authority seeds/bindings), surfaces/boundary versions,
source/discovery observations, contexts and memberships, understandings and
versions, conclusions, support dependencies, challenges, verification state,
ordinary receipts, and `functional_route_dependency_index`. The new
`conclusion_curations` table remains empty.

Consequently every migrated Beta-1 semantic revision begins CAPTURED under the
Beta-3 reuse contract. A migrated revision enters the pending queue only when it
is current membership and its existing support evaluates CURRENT; non-current
captures remain stale until re-established. No migration step may invent an
independent review that never occurred.

Runtime open remains exact-version only; no in-place implicit migration exists.
Archive/stage/verify/activate/rollback ownership remains the existing transition
path. Transition verification proves:
- source semantic/audit counts and canonical identities are preserved;
- source schema-14 `functional_route_dependency_index` rows are preserved;
- `conclusion_curations` exists and has zero rows;
- ordinary exact/historical retrieval still resolves;
- installation schema-1 Functional Pyramid state is unchanged;
- rollback restores the exact archived schema-14 store.

The transition smoke lane then curates one migrated CURRENT capture in the
staged schema-15 store and proves it becomes reusable without rewriting the
migrated conclusion revision.

Beta-3 release identity is:

- Python/PyPI/changelog: `1.0.0b3`;
- Git tag: `v1.0.0b3`;
- GitHub Release: `Span 1.0.0 Beta 3`;
- MCP Registry server: `1.0.0-beta.3`;
- MCP Registry PyPI package: `1.0.0b3`.

### 26. Host guidance and generated public schema

**Authority:** A4, A8–A10; F6–F8, F10, F13; L7–L8, L17;
FD-49–FD-58, FD-95–FD-102.

Generate the pending-curation selector/result and curation action from the
canonical model/schema owner. The MCP adapter remains transport-only. Exactly
three tools are advertised: `ask`, `record`, `reconsider`.

Update working-agent guidance only after the wire is implemented:
- investigate and record supported meaning while evidence is fresh;
- semantic create/change is capture, not self-publication;
- task completion may leave a pending curation item.

Add reviewer/curator guidance using the same three operations:
`ask(PendingCurationSelector)` → exact retrieval/investigation →
challenge/correct/replace/withdraw when needed → `record(actions.curate)` for
the stable revision.

Span schedules no background model and imposes no model provider. A team may run
the reviewer at task completion, PR review, before first cross-session reuse or
asynchronously.

### 27. Beta-3 verification

Extend functional acceptance and installed-MCP coverage through cases 45–64.
Verification must prove at least:

- capture is retained but not Answer content;
- `Gap/pending_curation` and pending selector behavior;
- curation advances understanding history without a semantic revision;
- CURRENT + CURATED reuse;
- support still gates curated content;
- correct/replace/add reset to CAPTURED;
- confirm inheritance rules;
- curation/semantic-mutation exclusivity;
- Functional Pyramid state is unchanged by curation;
- schema-14 → 15 preserves all prior data and fabricates zero curation;
- migrated current Beta-1 knowledge is pending, not auto-published;
- exactly three MCP tools remain;
- a non-editable installed journey covers capture → curate → fresh-session reuse
  → change → reconsider → confirm/reuse and semantic-change → re-curation.

The Beta-3 installed-candidate acceptance composes this Part-D lifecycle proof
with Part-C §20's corrected production-topology setup proof in the **same
candidate**: repositories plus an empty data directory are initialized through
the installed `span-install`; the resulting governed runtime then exercises
Functional Pyramid orientation and the capture/curation lifecycle. Direct store
registration or direct authority-binding injection may remain lower-layer test
fixtures but cannot satisfy that installed-candidate gate.

The existing architecture guards remain binding: one canonical carrier per
boundary, no shell semantic writer, no duplicate support evaluator, no
curation-specific Functional Pyramid path and no fallback that treats absence of
curation data as approval.

Part D is implementation-complete only when these mechanisms and the extended
functional acceptance surface pass on the exact Beta-3 candidate.
