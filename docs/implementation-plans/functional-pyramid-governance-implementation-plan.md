# Functional Pyramid governance — Beta 5 implementation plan

**Status:** Initial governed installation/public projection implemented and CI-verified at `261d055b4c2bbdba781358d500ba288a48cb750d`; S-FIELD-01 verified at `49f43b8798fd`; S-FIELD-02 and S-FIELD-03 implemented in candidate; final verification and S-FIELD-04 remain open.
**Historical baseline:** `pontivus-com/span`, `release/1.0.0-beta5`, `8ea0ba291867dd3433373e00069af97df655088d`. **Field-remediation baseline:** `261d055b4c2bbdba781358d500ba288a48cb750d`.  
**Authority:** G7–G8, F1/F4/F5/F7/F11/F12/F14, L4/L7/L8/L12–L16, amended FD-88A–C/FD-93/FD-94 and TD §§17, 17.1, 17.2, 20, 21. The plan implements these documents; it does not own another product design. The release programme remains the historical/release-gate record.  
**Governance and historical evidence:** This tracked plan is the single current Functional Pyramid implementation plan, superseding the previously local `.context/functional-pyramid-governance-implementation-plan.md`. The local plan was not available in Git for inspection; preserve its historical evidence and reconcile any independent outstanding obligations with the tracked release record before execution. It is not a second active plan. Do not infer completion from this document.

## 1. Objective and completion

Implement the single governed installation journey specified in lifecycle §7.1 and TD §17.2. The repository operator supplies a valid Functional Pyramid classification document for each explicitly selected member and requests governed initialization. Span executes the rest. Normal registration without an explicit governed initialization request remains separate and does not activate participation.

Success for a fresh installation is a verified ACTIVE/VALID instance, correct member set, exact derived governance, registered authority, installation provenance, and working ordinary MCP lifecycle, without a second setup command, manual configuration, manual Git commit of generated artifacts, or manually constructed MCP payload. Revision uses the same entry point. When an accepted change produces semantic obligations that Span cannot resolve deterministically, report those exact obligations and the receipt handoff; never claim semantic completion or invent dispositions. Keep external adopter rehearsal, managed-host preview, live cutover and release authorization as separate release gates, not additional setup responsibilities for an ordinary user.

## 2. Baseline and work classification

The table and §3 retain the original delivery baseline, task definitions and
intermediate evidence as history. They are not assertions about the current
tree or instructions to rebuild already delivered capabilities. The current
field-remediation delta and execution gates are in §3A.

| Existing owner | Verified source at baseline | Treatment |
|---|---|---|
| Classification row and aggregate | `src/span/core/model/classification.py` | Extend canonical row with missing authority kind/status and strict validation. No parallel model. |
| Declaration derivation | `src/span/core/functional_pyramid.py:385–497` | Reuse grouping, placements, membership, references and ordering. Extend derivation to complete inputs. |
| V3 graph/source validation | same module, `evaluate_functional_pyramid_source_structure` | Reuse; enforce complete selected member coverage, including all-excluded member failure. |
| Authority and bootstrap preflight | `src/span/shell/install/preflight.py:113–288,321–378` | Reuse canonical authority and source decoders; replace manual governed-input assembly at installer boundary. |
| Provisioning | `src/span/shell/install/cli.py:319–368,421–479`, `provision_repository_runtime` | Reuse exact provisioning owner and canonical request. |
| Candidate and participation writes | `src/span/service/functional_pyramid.py:442–493,588–686,775–881` | Reuse existing candidate/record service, atomic transaction, receipts and CAS. No second writer. |
| Effects and V2 revision | same service, `_change_effects`, `_proposed_changed_route_identities`; TD §21 | Preserve and verify effective-route changes and ordinary dependent-effect processing. |
| Directory resolution and compact read | `src/span/service/functional_pyramid.py:270–312`, `src/span/core/model/functional_pyramid.py:505–553` | Reuse. |
| Public findings and continuation | model lines 303–353,403–415,505–553; `src/span/service/answer.py:1029–1078` | FD-88B/C not closed: implement public projection and continuation using current owners. |
| Installer/host verification | `src/span/shell/install/cli.py:892–907`, `src/span/shell/install_verify.py` | Extend existing sequence and exact observed result; no parallel verification architecture. |
| Installed acceptance | `tests/integration/test_installed_mcp.py`, `functional_pyramid_governed_probe.py` | Reuse production installed lane; add document-only setup as sole governed input. |

This is static inspection, not test execution. Historical green CI on V2 or partial V3 is not evidence of the required end-to-end outcome. Retain unrelated passing test obligations.

**Non-regression boundary.** The closed Beta-5 read-API over-fetch remediation R-1–R-6, strict Version-3 source contract and existing route/authority/support separation are established design decisions, not legacy mechanisms to recreate or reverse. When a stale example, acceptance statement or derived guide contradicts those decisions, correct that document at its owning layer; do not change working code to reproduce stale wording. Preserve the compact public projection, no-public-impact-selector scope, internal bidirectional graph and cross-repository effects, root totality, exact directory/semantic scope, canonical binding support qualification, ACTIVE/VALID versus semantic currency, single writer and existing atomic replay/CAS. Keep the V2 navigation bootstrap distinct from the retired V2 declaration grammar. Test these invariants without weakening existing assertions. The original production work is the initialization integration, public finding projection, continuation and their evidence. At the field-remediation baseline the only new authorized production changes are S-FIELD-01–03; S-FIELD-04 verifies them. No implementation of a deferred capability or replacement of an established owner is authorized. Trace any genuinely necessary change to current governing intent, not a historical example.

## 3. Ordered implementation tasks

### S-DOC-01 — Close governing design and public workflow

Original delivery task (historical): the governing documents were amended with this plan. Before changing code, verify their alignment. Review the selected administrative contract, metadata publication/failure semantics, authority ownership, explicit initialization intent, and semantic-effects completion boundary. Check all normative references and derived guides for the retired materialise-only/manual activation workflow. Keep the current Functional Pyramid classification grammar; do not introduce a second external declaration grammar. Verify FD acceptance cases 13, 23, 31, 33, 43 and 67–72 and corresponding FA rows; FA records must show new tests as pending until execution. Retain the established R-1–R-6 over-fetch decision; stale Version-2 declaration examples and public reverse-impact wording are document defects, not code tasks. Keep `docs/implementation-plans/1.0.0-beta5.md` a release record. This tracked plan is the sole current task authority. Do not retain a second active plan or commit `.context/`.

**Gate:** owner confirms the one-command administrative boundary and derived metadata/revision failure behavior. No unresolved design choice is delegated to implementation. This amendment is documentation only; planned CLI syntax is not represented as already available.

### S-INIT-01 — Complete one strict classification ingress and pure derivation

**Single ingress correction:** the earlier flat own-repository-only classification
could not express the existing FD-66 shared-document placement capability.
The sole classification grammar now includes exact declaring/owning repository
coordinates and resolves parent placements by both. Do not introduce a raw
bootstrap or manual initial activation alternative. Preserve the existing V3
resolver and canonical authority identity. The new cross-repository ingress
tests require executable verification.

**Execution state:** strict classification row/JSON ingress, canonical governing
order and all-excluded-member rejection implemented in the existing core owner.
Focused Actions verification for `5c3ef93062a2`: 43 tests and 30 subtests passed;
Ruff and zero-error typing passed; Black unchanged. Code-budget measurement:
33,884 test lines (previous 33,748), attributable to the new evidence.
The pure source/bootstrap/member-intent projection and authority reconciliation
passed focused Actions verification at `d6a7d45228c7`: 46 tests and 30 subtests;
Ruff and zero-error typing passed. The runner supplied Black formatting and
measured 33,978 test lines. The exclusive administrative lock and atomic receipt
publication passed focused Actions verification at `d200cbab4bbe`: 169 tests
and 30 subtests, Ruff and zero-error typing. Black formatting was applied
from that runner, and the test-line measurement is 34,020. Governed pending
intent and installer participation composition remain open. The temporary
verification workflow is removed; use the normal CI workflow for subsequent
candidate verification. The acceptance matrix continues to require executable FA-67–72 evidence;
a partial change does not close this gate.

1. Extend `FunctionalPyramidClassificationRow` using the existing canonical authority-kind/status enums. Place rows require both, explicit `ROOT` for P0, nonempty distinct qualified governing identities otherwise; exclude rows carry no placement or authority fields and a nonblank reason. Use existing strict canonical path and scope validators; reject unknown/missing/mixed fields, unsupported version, duplicate rows, duplicate mappings, noncanonical paths, repository mismatch and malformed identities. No permissive parser or compatibility grammar.
2. Decode one Version-1 classification file for each selected governed member; map each file to its explicit repository ID and root. Each row belongs to the mapped repository. Resolve parent identities over the entire combined member set. Every selected governed member must produce a valid root source/P0, including members with no place rows. Reject unselected parent references, absent/unreadable files, invalid edges, duplicate placements and invalid authority coverage before effects. Use actual repository source access, not guessed existence or semantic interpretation.
3. Extend the existing derivation owner, not a new parallel resolver: derive V3 sources, canonical binding inputs and V2 navigation bootstrap/member-intent references. Preserve deterministic source IDs based on repository and scope; locate source bytes by the content identity prescribed in TD §17.2. Bindings use the existing `AuthorityBinding` and `EvidenceRef` shapes; use the canonical evidence identity/digest conventions, exact whole-document location, source kind and row authority status/kind. Evidence content identity is observed from source, never supplied or guessed by the row. No DTOs or new semantic carriers.
4. Reuse existing structural validation; require one whole-document binding for each placement. Reconcile ordinary bindings per amended FD-88A. Previously FP-derived bindings removed from the placed set must be removed from the FP-derived portion only. Reuse a unique equivalent existing whole-document binding per FD-88A/TD §17.2 without changing its evidence identity or taking ownership. Preserve independently owned bindings; conflict if replacement/removal ownership or identity cannot be established, or a classified placement has a competing whole-document binding. Preserve independently owned section/span bindings; they cannot satisfy a whole-document placement but their presence must not invalidate an otherwise valid unique whole-document binding. Do not silently discard ordinary authority or infer ownership by prefix alone. Capture exact pre-provisioning old/new binding changes, including removed identities, for S-INIT-03.

**Gate:** strict ingress and pure derivation tests prove exact results, multi-repository resolution, all-excluded member rejection, non-default authority kind/status, malformed inputs, explicit ROOT, deterministic output, equivalent existing whole-document identity reuse and ordinary binding preservation (including ancillary section/span bindings). Existing V3 validation remains green. No production shell mutation in pure tests.

### S-INIT-02 — Compose governed initialization within the existing installer

1. Implement `--functional-pyramid-classification-file REPOSITORY_ID PATH` (repeatable) on the normal `span-install` path. Its explicit presence requests governed initialization for the mapped members. Do not introduce a separate `--materialize-functional-pyramid` command or require an additional activation command. Retire the user-facing raw bootstrap setup option for governed installation; keep the V2 bootstrap and V3 declaration carriers internal to Span. Ordinary authority input remains available for repositories outside the governed set; reject simultaneous conflicting authority-binding input for a governed member before mutation.
2. Extend preflight to decode all inputs, derive the complete candidate source and authority set in memory, validate repository identities/locators, membership intent and ownership of generated metadata. Use existing `evaluate_functional_pyramid_source_structure`, existing authority validation and existing backup owner. Invalid input must not mutate repositories, authority stores or participation. Dry-run and verify-only remain non-mutating.
3. Implement the metadata publication mechanism in TD §17.2 using the existing shell filesystem/evidence owner. Stage immutable content-addressed declaration files; generate the canonical bootstrap/binding payloads internally. Keep accepted source locators intact until the new participation write succeeds. Do not use a stable filename overwrite as an atomic set commit. Keep ordinary install backup and exact failure reporting; no assertion of atomicity across filesystem, multiple repository provisions and participation. Only owned artifacts may be written; reject path escapes, symlinks, unmanaged collisions or unverifiable ownership. No canonical document edits or user commits of generated files. Implement TD §17.2 pending-intent recovery in the existing installer receipt owner: atomically persist the exact preflight input, planned artifact digests/paths, old/new binding evidence and original canonical action/member payload and request ID before first metadata/binding mutation, retaining prior accepted provenance and the existing backup. Recognize only evidenced owned artifacts; no separate journal, authority registry or database schema. Update the existing receipt writer to atomic replacement and make incomplete governed setup explicit to observational verification. At the installer entry/composition boundary implement TD §17.2's exclusive administrative ownership of the canonical data directory, held before mutable preflight reads through finalization or failure. Use one stable OS advisory lock distinct from receipt and databases; keep existing SQLite ownership/CAS. All competing mutating administrative paths share it; pending intent blocks ordinary installation and unrelated maintenance, allowing only same-input governed recovery or explicitly authorized existing recovery. Observation modes remain non-mutating.
4. Use `provision_repository_runtime(InitializeRepositoryRequest)` once per selected repository through the existing installer owner. Supply the derived/reconciled canonical bindings directly; derive member intents from exact generated source references. Preserve omitted/empty/replace semantics for non-governed authority configuration and existing schema handling. Do not reimplement repository registration or structural index provisioning. The governed installation flow automatically proceeds to S-INIT-03; reporting ordinary installation complete before that is incorrect.
5. Test failure injection before mutation, after pending intent but before/after staged sources, after provisioning and after participation acceptance before final receipt. A failed later setup may leave explicitly reported operational state; retain backup, pending evidence and prior accepted receipt identity and do not claim successful initialization. Same-input retry resumes the recorded intent and original receipt selector; mismatched input/observed state is an explicit recovery conflict. No fallback to the manual workflow or blind rollback of an accepted participation write. Test competing governed/ordinary installs and mutating maintenance against a held owner, canonical path aliases, rejection without receipt/binding mutation, and process exit followed by same-input recovery. No lock bypass through receipt replacement or pending intent.

**Gate:** installed CLI receives repository paths plus the approved input only. It creates exact artifacts and provisions exact bindings without fixture injection; generated content is deterministic and operator never needs to supply it. Test unsafe paths, owned revision versus collision, partial failure, no-write modes and ordinary descriptive install regression.

### S-INIT-03 — Establish, verify and report participation automatically

1. In the governed installer orchestration, use the existing installation runtime/service composition. Resolve status for the complete explicitly selected governed member set. Fresh eligible members use ACTIVATE; exactly one existing ACTIVE instance with identical selected membership uses REVISE when the actual applied canonical governance configuration differs from the requested one, including binding-only changes. An identical valid installed configuration is a no-op for participation (preserve pyramid version and receipt); raw classification formatting alone cannot force a revision. An identical but operationally degraded configuration must be repaired/verified, not falsely accepted. Any actual binding mutation must be included in the accepted effect projection. Conflicting active instances, partial member selections or implicit removal reject; explicit member-set change remains the existing separately authorized lifecycle action. Never infer membership from document references or merge active instances silently. Explicit governed initialization authorizes adoption of explicitly selected UNCONFIGURED/EXCLUDED members only when they form a fresh eligible member set.
2. Derive canonical member intent, action and exact existing pyramid/version from the initialization request and observed state; allocate the canonical request ID once in the pending installer receipt. Use the canonical candidate service and the same `FunctionalPyramidService.record` owner as MCP, including transactional revalidation, CAS, replay and dependent effects. Resume pending intent before selecting any new action/version; query/replay the original receipt/payload, preserve existing canonical record digest semantics and never issue another revision for an already accepted pending operation. No second writer, direct SQL, new MCP operation or subprocess-specific semantic path. Extend the existing participation effect composition internally as required by FD-89/TD §20.3: union changed old/new repository-qualified AUTHORITY dependency identities (including removed bindings) with existing route/participation effects in the same `DependencyEffectService` projection, evaluate through existing support rules, close premises once and retain the affected refs in the canonical participation receipt. No change to public write grammar, route identity, structural health, forced-route logic or authority qualification semantics.
3. After acceptance publish navigation metadata, then strictly verify exact accepted identity, version and membership, ACTIVE/VALID and actual governed provenance against the pending expected configuration using the existing verifier. Atomically finalize the existing installer receipt only after verification; persist/return the canonical participation receipt and dependent-effect handoff, keeping outstanding accepted effect references. No new semantic result carrier. Report invalid input, candidate rejection, operational failure and post-commit verification failure explicitly. A successful structural setup with outstanding semantic effects is not full lifecycle completion; return exact effects/contexts/receipt selector for ordinary agent re-establishment without a second participation reconsideration. The installer does not interpret source meaning or write semantic conclusions.
4. Verify Version-2→Version-3 cutover against retained route/support changes using the existing engine; preserve historical receipts and descriptive understanding, no old graph translation. Verify fresh-process use, idempotent rerun, changed input revision, stale expected-version conflict, partial/multiple active-member conflicts, post-commit recovery, and actual affected semantic support. Exercise binding-only kind/status changes, removed bindings, unchanged bindings, equivalent pre-existing binding reuse, explicit authority support in descriptive conclusions and cross-repository premise closure. Assert existing route identity and structural health do not change solely because authority currency changes; do not force unaffected support stale. Do not conflate runtime health with authority-support currency or semantic completeness.

**Gate:** one installed command executes fresh governed setup and a second invocation with changed input performs the correct revision; unchanged input does not increment version. Exact public status, provenance, receipt replay, route selection and dependent effects are verified. Ordinary installation, hooks and runtime open remain non-activating.

### S-PUBLIC-01 — Close FD-88B public projection

Reuse existing internal FD-71 and candidate findings. Implement the fixed public vocabulary and service-boundary projection in FD-88B/TD §17.1; public results must not serialize internal reason enums, declaration locators, routes, authority payload or per-path provenance. Cover status, candidate graph/validation, directory/semantic view and unavailable results, including detail/recovery text. Regenerate the public schema from canonical types. Keep internal reasons available for resolver/effects and do not change the graph semantics. Do not add a public operation. Test mapping completeness, structural status invariants and generated-schema absence of internal details.

### S-PUBLIC-02 — Close FD-88C directory continuation

Use existing paging conventions and exact directory resolution. Extend the canonical selector/view with `after`/`next_after`; bind the opaque token to the repository, directory, selection and declaration version/identity, return the next ordered fitting page, reject stale or mismatched continuation, retain complete unresolved state and constant-size omission. No second resolver or impact API. Ensure response budget remains measured, no arbitrary ceiling increases, no zero-progress continuation, and semantic orientation remains bounded. Test all placements recovered once in order, stale token and budget cases. The corrected TD §17.1 response example must satisfy the existing model invariants; no model-validation loosening. Preserve closed over-fetch remediation and deferred public impact scope.

### S-VERIFY-01 — Reconcile acceptance and deliverable guidance

Preserve corrected FA-13's Version-3 invariant and sibling exclusion evidence, and FA-23's internal reverse-dependency traversal and compact public surface; do not reinstate the deferred impact API or retired V2 declaration grammar. Implement or extend executable FA-67–72 as specified by amended FD §15, preserve live tests for other rows, reconcile installer and host skill instructions, regenerate only through canonical generation tooling. The skill invokes governed initialization once and handles actual input defects or semantic handoffs; it does not ask an agent to build Span's metadata or manually ACTIVATE. Public examples clearly identify planned syntax until implemented. Record exact test names and status only after evidence. Run focused suites on modified owners.

### S-VERIFY-02 — Installed end-to-end acceptance

Use the existing non-editable installed-MCP lane and neutral temporary repositories. Fixture setup may author canonical documents and valid classification files only; it must not create declarations, authority bindings, bootstrap, candidate payloads, store registration or participation. Start from an empty data directory; invoke installed `span-install` with the declared input once, then use the installed public API only to inspect the result and perform ordinary runtime verification. Include a root P0, shared ancestor, sibling scope, cross-repository governing reference, exclusion and non-default authority. Prove exact derived governance and bindings/provenance; root/nested/sibling retrieval and paging; public finding vocabulary; a fresh process; unchanged rerun; changed-input revision; previously ACTIVE V2 revision; affected and unaffected normative support; binding-only kind/status/removal effects including explicit descriptive authority dependencies and premise closure; equivalent independently owned binding reuse, ancillary section/span preservation and exclusion preservation; raw input formatting changes with identical derived configuration do not increment the version; receipt handoff; invalid input before mutation; interruption at each pending-intent/provisioning/acceptance/final-receipt boundary and same-input recovery without duplicate participation; stale/mismatched recovery conflict; concurrent governed and ordinary installer/maintenance ownership with non-mutating rejection and recovery after owner exit; unchanged route identity and structural health for authority-only currency changes. Verify ordinary install without input and no-write modes do not activate. No manual activation hidden in a fixture or a probe. Lower-layer tests may use constructed carriers only when that layer is the subject.

### S-VERIFY-03 — Full exact-candidate closeout

Run repository-prescribed full Python suite, Ruff, Black, typing ratchet, plugin suite, generated schema conformance, distribution build and installed-MCP acceptance. Record exact command, commit/tree, results, measured budget change and sanitized evidence in the existing acceptance/release record; no raw captures in Git. Do not lower a valid gate or mark planned rows complete. Check all old manual setup instructions and obsolete options have been removed from governed installation; check no new parallel carrier, writer, resolver, compatibility route, semantic interpretation or fourth MCP tool. Independent review and tasks 14–17 of the release programme remain open until their own evidence/authorization. No publication or live adopter mutation authorized here.

## 3A. Field-remediation amendment — 2026-11-27

**Evidence and disposition.** The original S-DOC/S-INIT/S-PUBLIC/S-VERIFY
programme delivered the one-input initialization and passed [full CI run
45907630622](https://github.com/pontivus-com/span/actions/runs/45907630622)
at `261d055b4c2b` (1,021 passed, 1 skipped, 186 subtests; typing, lint,
format, distribution and host plugin gates passed). This is prior candidate
evidence, not proof of the new amendment. The adopter agent reports final
version 8 ACTIVE/VALID, strict acceptance, 30/30 directory checks and
idempotency. These local observations are reported, not independently
verified. Its inferred scope/layer/parent decisions and self-referential
verification were repository-input errors; no change to the semantic boundary
or classification grammar is justified. A placement may have multiple
governing references. The reported obsolete Pontivus-local guide and independent
semantic reconciliation remain adopter work, not Span production tasks.

**Owner-reported field scale (2026-11-27).** The report attributed to
`card.2026-11-27-span-beta5-local-install.json` describes the approved
`261d055b4c2b` Legal installation failing with
`unknown authority binding locator` for a readable existing path, followed
by pending intent and generated declarations requiring recovery. Legal
requires well over 1,100 authority bindings according to the owner; the
card and exact distinct-locator count have not been independently inspected.
Source inspection confirms that `inventory_evidence` paginates distinct
locators using `max_evidence_units=96`, not `max_results=250`; the latter
is another query bound but does not control this inventory path. The defect
is the administrative first-page consumer, not the query policy. This
corroborates FIELD-01 and FIELD-02, not a new implementation task. Neither
a configurable installation cap nor a higher retrieval bound is authorized.

Static inspection of the exact field baseline confirms three distinct defects:

| Finding | Root cause at field baseline | Governing correction | Task |
|---|---|---|---|
| FIELD-01 | `service/administration.py:20–85` consumes the first page of `inventory_evidence`; `service/bounds.py:50–57` and `shell/evidence_source.py:137–169` establish the 96-unit evidence page, not an installation limit. Both seed and binding consumers can reject valid later locators. | FD-54, FD-88A; TD §20 | S-FIELD-01 |
| FIELD-02 | `shell/install/governed.py:461–501` records pending ownership and publishes generated files outside the data directory; `shell/install/recovery.py:335–405` restores only listed data artifacts. Restoring the prior receipt loses pending ownership without reconciling generated paths or absence. | FD-88A; TD §17.2 | S-FIELD-02 |
| FIELD-03 | `shell/readiness.py:817–844` always reports `requires_governed_install`, irrespective of actual state. | FD-94; TD §17.2 | S-FIELD-03 |

**Session finding traceability (all acceptance gates OPEN).** The following
maps the reported defects and their review refinements to their existing
design owners and executable work; it is not another task or acceptance
programme. The owner-reported Legal-scale failure is part of FIELD-01/02.
The adopter's classification decisions, obsolete local guidance and semantic
reconciliation remain repository-owner work as noted above.

| Finding | Functional authority | Technical mechanism | Task and acceptance |
|---|---|---|---|
| FIELD-01: valid authority rejected above evidence page, including Legal scale | FD-54, FD-88A | TD §20 exact validation, no administrative cap | S-FIELD-01.1–4; FA-68/69 |
| FIELD-02: orphaned generated declarations and incomplete restore | FD-88A | TD §17.2 preimages, absence, scoped restore and accepted-intent recovery | S-FIELD-02.1–7; FA-70 |
| FIELD-03: misleading activation guidance | FD-94 | TD §17.2 observational guidance | S-FIELD-03; FA-70 |
| F-01: ownership check releases before restore | FD-88A | TD §17.2 continuous recovery isolation | S-FIELD-02.5; FA-70 |
| F-02: independent-write proof insufficient | FD-88A | TD §17.2 complete logical affected-state proof | S-FIELD-02.6; FA-70 |
| F-03: unrelated stores at risk | FD-88A | TD §17.2 exact affected scope | S-FIELD-02.6; FA-70 |
| F-04: stale pending guidance in final receipt | FD-94 | TD §17.2 final receipt composition | S-FIELD-03 F-04; FA-70 |
| F-05: incomplete or combined instance observation | FD-82/83/94 | TD §17.2 complete per-instance observation | S-FIELD-03 F-05; FA-70 |
| F-06: insufficient interruption coverage | FD-88A, acceptance 70 | TD §17.2 durable recovery transitions | S-FIELD-02.7; FA-70 |

S-FIELD-04 closes the entire mapping with executable evidence, not historical
CI or a successful count-only installation.

### S-FIELD-01 — Exhaustive exact administrative authority validation

**Status:** VERIFIED at `49f43b8798fd` ([CI 45922217648](https://github.com/pontivus-com/span/actions/runs/45922217648): 1,024 passed, 1 skipped, 186 subtests; zero-error typing and distribution passed). **Owner:** existing
`service/administration.py` and installer preflight/provisioning composition,
existing EvidenceSource port. The exact-locator validator and installer
preflight are implemented; unit and installed field-scale regressions added.
Test-line ratchet records the measured added regression lines (189); no
delivery or semantic budget changed. S-FIELD-02–04 remain open.

1. Implement the exact unbounded-by-delivery validation mechanism in TD §20.
   Replace first-page inventory consumption for both ordinary seeds and bindings.
   Reuse the canonical observed reference for seeds, preserve supplied canonical
   binding identity and every binding attribute. Distinguish actual missing,
   unreadable, wrong-repository, duplicate and provider-failure outcomes.
2. Validate every explicit ordinary replacement and the entire final
   reconciled governed authority configuration in read-only installer preflight
   before pending publication or setup mutation, and reuse the same validator
   at provisioning. No shell duplicate, larger query bound, caller batching
   or partial registration. Omitted ordinary families preserve existing state;
   explicit empty families clear it.
3. Add service and installed tests with more than the existing maximum
   evidence-page count of distinct locators, including both ordinary seed/
   binding input and document-only governed setup. Exercise duplicate
   locators with distinct section/span binding identities, invalid locator
   beyond the old first page, foreign identity, unreadable/provider failure,
   identity retention, and complete rejection before repository-state or
   generated-artifact mutation. Preserve existing bounded retrieval tests.

4. Add a synthetic installed governed initialization fixture with more than
   1,100 distinct valid authority locators and their canonical bindings,
   exceeding both numerical query bounds without changing either. This is
   owner-reported field-scale regression evidence, not a capacity threshold
   or assertion about the adopter's distinct-locator count. Verify the exact
   complete persisted binding set by canonical identity and attributes and
   the complete placed document coverage, not by a single bounded evidence
   response or count alone. Repeat identical
   input without a duplicate participation write; test a missing/unreadable
   locator late in the large set and prove rejection before pending intent,
   generated declarations or repository-state mutation. Use the existing
   installed acceptance lane; the real adopter corpus retest remains the
   separate owner-authorized gate in S-FIELD-04.

**Gate:** exact valid set registered and retrieved, no truncation and no
delivery-budget change; exact invalid input diagnosed before setup mutation.

### Review closure — 2026-11-27

Independent static review at `8066997d18f2` confirmed FIELD-01–03 and
identified six implementation-contract gaps. F-01 continuous isolation
(`recovery.py::_assert_quiescent` releases its lease), F-02 complete store
proof (`backup_io.py::database_facts` is not a write-history oracle), F-03
affected scope (full backup includes unrelated stores), F-04 pending versus
final receipt (`cli.py::_build_receipt` embeds pre-finalization verification),
F-05 instance-qualified membership (`readiness.py::probe_active_functional_pyramid`
iterates CLI roots), and F-06 durable-boundary fault injection are closed at
design/task level below; no production correction or executable proof yet.

### S-FIELD-02 — Restore pending governed setup without orphaned ownership

**Status:** IMPLEMENTED IN CANDIDATE, VERIFICATION OPEN. **Owner:** existing installer receipt, governed artifact
publication and full installation backup/restore owners. Focused diagnostic run
[45923069189](https://github.com/pontivus-com/span/actions/runs/45923069189)
passed 154 tests and 21 subtests on the formatted working tree; two typing
diagnostics and formatting were corrected before the full CI candidate.
The measured test-line increase is 459 and the lifecycle module increases by
four lines (1913) to bind connection lifetime to ownership; the existing
AST gate records those measurements, not delivery limits. Depends on S-FIELD-01
for the corrected preflight boundary, not for ownership semantics.

1. Implement TD §17.2's verified pre-setup artifact/absence protection in the
   existing backup manifest, including fresh setup with no existing DBs.
   Capture all planned generated-path preimages, exact root identity and
   absence, and bind backup identity/digest to pending intent before mutations.
   Reuse existing manifest/carriers, atomic publication and administrative lock.
2. Extend the existing `--restore-backup` confirmed operation. For an
   unaccepted pending request, verify the exact baseline backup, all path/
   digest/ownership and store-state preconditions, including no independent
   writes to newly created stores. Take the verified pre-restore snapshot
   with generated bytes. Persist restore intent in the pending receipt, then
   reconcile only proven generated paths and affected data artifacts; restore
   present/absent state, verify, and publish the restored receipt last. Preserve
   previous accepted sources and independently owned material. A modified,
   unknown, missing required preimage, wrong backup, or unverifiable write
   history is a named conflict. Never blindly delete or adopt files.
3. Resume the same restore after interruption before final receipt replacement,
   without reconstructing intent or choosing another backup. Accepted pending
   participation is a separate branch: query its original receipt and preserve
   accepted effects, complete/replay rather than abandoning it. Retain ordinary
   recovery scope outside pending governed setup; do not introduce another
   recovery operation or receipt.
4. Exercise installed failures after pending intent, after generated sources
   and after one member provisions but before participation acceptance, both
   fresh and existing installations. Prove changed-input initialization can
   proceed after verified abandonment without manual generated-file cleanup,
   and that prior bootstrap bytes, prior authority, active membership,
   historical sources and independent bindings are preserved. Inject restore
   interruption before final receipt and prove idempotent continuation. Test
   modified/unowned artifacts, symlinks, wrong backup, unrelated/new store
   activity, missing preimage and accepted-but-incomplete recovery. Verify
   the competing-mutator and same-input replay tests remain green.

5. F-01: implement TD §17.2's shared runtime/exclusive restore store-use lease
   in the existing ownership shell; cover context and installation runtime,
   hooks and provisioning, with stable canonical lock identity, lock order
   and lifetime. Keep SQLite handles through inspection/snapshot/in-place
   restore; test idle runtime, racing admission after quiescence, absent
   store retirement and alias paths. Existing ordinary installation semantics
   remain unchanged; no runtime can enter an exclusively held recovery.
6. F-02/F-03: record exact prior/planned canonical seed/binding configuration
   and selected store scope in pending, including ordinary selected members.
   Move baseline/pending protection before pointer publication in `cli.py`;
   reuse baseline on retry. Implement complete logical state proof at
   the existing SQLite/backup owner as defined in TD §17.2. Test independent
   writes to existing and fresh stores (including same counts/max revision),
   unrelated repository C modified after A/B setup, independent shared-store
   changes, missing/reaped acceptance receipt, unchanged-request/no-op and
   unexplained store creation. Preserve unrelated state or conflict before
   effects; no whole-backup copy loop for abandonment.
7. F-06: inject interruption after baseline capture before pending, after
   pending before protected effects, after pointer and each generated-file
   publication, after each store creation/registration, after restore snapshot
   before restore intent, after restore intent, after each generated-file
   restore/removal, after each store restore/removal, before and after final
   receipt publication. Resume in a fresh process; assert allowed states,
   unchanged original backup/snapshot identity, absence, exact restored
   state, preserved ownership and no duplicate participation write. Wrong
   backup, unexpected bytes or competing state must fail closed. Include
   fresh and existing installations, and accepted-but-incomplete replay.
   Do not implement the next task if proof or isolation cannot be established.

**Gate:** exact restored state and ownership verified or explicit recoverable
conflict; no orphaned generated files, lost accepted obligations or duplicate
participation write. No operator reconstruction of internal provenance.

### S-FIELD-03 — Correct observational initialization guidance

**Status:** IMPLEMENTED IN CANDIDATE, VERIFICATION OPEN. **Owner:** existing readiness and installed verifier
projection; depends on S-FIELD-02 for restore-intent guidance.

Diagnostic run [45924116947](https://github.com/pontivus-com/span/actions/runs/45924116947)
passed 165 focused tests and 30 subtests on the formatted tree. Apply its six
Black corrections and fix both collection typing errors at their declarations.
The measured test-line ratchet grows from 34,759 to 35,091 (+332 lines),
covering readiness, finalized receipt agreement and restore interruption tests;
no architectural gate or delivery limit changes. Full installed CI is required.

Implement the TD §17.2 projection using existing observed state and complete
active membership, with the exact documented status/action behavior. Remove
the unconditional hint, preserve the ordinary descriptive installation
contract and strict acceptance checks. Reuse the projection for doctor,
installed verification and receipt; no additional semantic state or graph
algorithm. Test every defined state, including mismatched provenance,
incomplete membership observation, healthy ACTIVE, pending setup/restore,
EXCLUDED, eligible UNCONFIGURED and unavailable. Assert observational
verification does not mutate stores, receipts or generated files and that
healthy ACTIVE never requests another initialization.

F-05: in the existing readiness/installed verifier composition, expand the
retained membership by exact ACTIVE instance/version from the existing store
and registered roots, not CLI target selection; evaluate independent instances
separately through the existing graph owner. Cover partial selection,
missing/inaccessible members, changing version, cross-repository graph and two
independent ACTIVE instances. Assert no synthetic combined graph.

F-04: retain actual pending guidance in pre-finalization strict verification.
Build the candidate finalized receipt through `governed.finalize`, then use
the same diagnostic projection and observed facts with that candidate
receipt/provenance context before atomic publication, per TD §17.2. Do not
override status in CLI or publish success for an incomplete state. Test a
healthy completed receipt against fresh doctor and strict verification;
inject failure before publication and confirm pending guidance persists.
Test descriptive UNCONFIGURED with and without explicit governed intent.

**Gate:** coherent observed guidance and verification result across all
administrative outputs; no false initialization requirement or false readiness.

### S-FIELD-04 — Exact-candidate regression and acceptance closeout

**Status:** OPEN. Depends on S-FIELD-01–03.

- Extend the existing FA-68 and FA-70 evidence mappings (and FA-67/69
  installed evidence where exercised) in `docs/functional-acceptance.md`
  with the actual executable test names; do not create a parallel acceptance
  matrix or claim new evidence before execution.
- Reconcile affected installation, recovery and host guidance in their
  existing derived owners (`docs/install.md`, `docs/recovery.md`, relevant
  onboarding/skill references). Describe the single input, exact validation,
  actual recovery choices and observed readiness. Do not document 96 as an
  authority cap. Do not introduce a second grammar or activation command.
- Run focused tests and the existing non-editable installed-MCP lane, then
  full CI on the exact candidate per S-VERIFY-03. Retain original green
  acceptance, public pagination, route/authority separation, CAS/replay,
  and semantic effects; no weakened gate, increased delivery ceiling or
  invented ratchet value. Record exact revision and sanitized results.
- Map F-01–F-06 to exact executable tests in FA-70 (and FA-68/69 where
  applicable); record failure-before/fix-after evidence for continuous
  ownership, independent writes, scoped restoration, finalized receipt,
  per-instance membership and every durable interruption boundary. Retain
  original tests and prove no newly introduced administrative deadlock.
- Independent review checks all three root causes and F-01–F-06 against the amended design.
  A controlled local retest of the real adopter corpus is the next adopter
  gate; no publication, release tag, merge or live adopter mutation is
  authorized by this amendment.

**Gate:** all three fixes demonstrated by executable evidence; complete
candidate CI green, then owner-authorized local Beta-5 retest. Prior green
CI and the adopter's reported version 8 are not closure of FIELD-01–03.

## 4. Execution sequence

Original delivery sequence (historical): S-DOC-01 → S-INIT-01 → S-INIT-02 → S-INIT-03 → S-PUBLIC-01 → S-PUBLIC-02 → S-VERIFY-01 → S-VERIFY-02 → S-VERIFY-03. Field amendment execution sequence: S-FIELD-01 → S-FIELD-02 → S-FIELD-03 → S-FIELD-04. The tests at each task gate must pass before dependent work is accepted. Public boundary tasks may be implemented independently after their canonical design is closed, but final installed acceptance is a single end-to-end gate. Reuse all existing owners; if a governing contradiction is discovered, stop at its owner and amend the design, not a downstream workaround.

## 5. Explicit non-scope

No replacement of the V3 resolver, route-support engine, repository store or installation store; no new storage schema solely for setup convenience; no changes to the repository's canonical governance content; no LLM discovery or automatic semantic re-establishment; no new public MCP tool; no compatibility bridge for V1/V2 declaration grammar; no manual metadata-authoring alternative to the governed setup contract; no release publication or live adopter cutover. Any genuine additional architectural requirement must be raised against the governing layer before implementation.
