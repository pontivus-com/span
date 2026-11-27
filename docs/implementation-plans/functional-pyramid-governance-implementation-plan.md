# Functional Pyramid governance — Beta 5 implementation plan

**Status:** Public lifecycle boundary remediation API-01–23 design amended; PUB-01 owner-confirmed complete; PUB-02–10 implementation/verification OPEN (§3B). Initial governed installation/public projection implemented and CI-verified at `261d055b4c2bbdba781358d500ba288a48cb750d`; S-FIELD-01 verified at `49f43b8798fd`; S-FIELD-01–03 candidate CI green at `8d6548d71f49`; exhaustive recovery/acceptance closeout remains open. Follow-up S-FIELD-05–07 implemented in candidate; full CI, native host delivery and operator-output boundary acceptance remain open.
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

**Non-regression boundary.** The closed Beta-5 read-API over-fetch remediation R-1–R-6, strict Version-3 source contract and existing route/authority/support separation are established design decisions, not legacy mechanisms to recreate or reverse. When a stale example, acceptance statement or derived guide contradicts those decisions, correct that document at its owning layer; do not change working code to reproduce stale wording. Preserve the compact public projection, no-public-impact-selector scope, internal bidirectional graph and cross-repository effects, root totality, exact directory/semantic scope, canonical binding support qualification, ACTIVE/VALID versus semantic currency, single writer and existing atomic replay/CAS. Keep the V2 navigation bootstrap distinct from the retired V2 declaration grammar. Test these invariants without weakening existing assertions. The original production work is the initialization integration, public finding projection, continuation and their evidence. At the historical field-remediation baseline S-FIELD-01–03 owned the authorized production changes; the current programme adds §3B PUB-01–10, with its own design and acceptance gates. No implementation of a deferred capability or replacement of an established owner is authorized. Trace any genuinely necessary change to current governing intent, not a historical example.

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

**Follow-up adopter feedback (2026-11-27).** The owner reports a successful
168-placement Legal installation at `8d6548d71f49`, previously failing at
101 placements; healthy ACTIVE reports `not_required`, and directory retrieval
worked with up to 99 placements per page. These are reported field observations,
not independently captured evidence or distinct authority-locator counts.
Exact candidate [CI 45924871018](https://github.com/pontivus-com/span/actions/runs/45924871018)
passed 1,035 tests, 1 skipped, 218 subtests, zero typing errors and distribution
verification. The prior recovery boundary evidence obligations remain open.
The reported whole-document classification correction is adopter-owned;
the Legal document was not retrievable from its default branch. Do not infer
authority or alter the classification contract to compensate.

Follow-up source findings at the exact green candidate: FIELD-04, checkout
`venv.py` omits the existing build generator and synchronization hashes only
Python sources; version-only distribution checks are insufficient for exact
identity. FIELD-05, OpenCode `span-hooks.js` prompt readiness latches on an
`_ask` suffix without complete current intended-tool observation. FIELD-06,
`cli.py` checks classification/one-shot compatibility after receipt-dependent
checks and discards conflicting option names. FIELD-07, administrative
`readiness.py` emits raw graph reason values (lines 381/493/677) and interpolates
exceptions in actions (716/729). These are source-supported output boundary
risks, not evidence that MCP currently leaks them. FD-27/88B and lifecycle §5
remain binding; administrative guidance is corrected under FD-88A. G5/G8,
A2/A8/A9, F6/F8/F10/F12, L8 and lifecycle §7.1 justify the follow-up;
Layers 0–2 require no new requirement.

Static inspection of the exact field baseline confirms three distinct defects:

| Finding | Root cause at field baseline | Governing correction | Task |
|---|---|---|---|
| FIELD-01 | `service/administration.py:20–85` consumes the first page of `inventory_evidence`; `service/bounds.py:50–57` and `shell/evidence_source.py:137–169` establish the 96-unit evidence page, not an installation limit. Both seed and binding consumers can reject valid later locators. | FD-54, FD-88A; TD §20 | S-FIELD-01 |
| FIELD-02 | `shell/install/governed.py:461–501` records pending ownership and publishes generated files outside the data directory; `shell/install/recovery.py:335–405` restores only listed data artifacts. Restoring the prior receipt loses pending ownership without reconciling generated paths or absence. | FD-88A; TD §17.2 | S-FIELD-02 |
| FIELD-03 | `shell/readiness.py:817–844` always reports `requires_governed_install`, irrespective of actual state. | FD-94; TD §17.2 | S-FIELD-03 |

**Session finding traceability (acceptance closeout OPEN).** The following
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
| FIELD-04: installed build identity incomplete | FD-88A; acceptance 73 | TD §20 installed identity | S-FIELD-05; FA-73 |
| FIELD-05: stale or partial host reachability | FD-49/52/53/58; acceptance 74 | TD §§15, 22.3 | S-FIELD-06; FA-74 |
| FIELD-06: late/ambiguous invocation conflict | FD-88A; acceptance 75 | TD §20 argument owner | S-FIELD-07; FA-75 |
| FIELD-07: private diagnostic values in administrative readiness | FD-27/88A/88B; acceptance 75 | TD §20 output projection | S-FIELD-03/07; FA-71/75 |

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
passed 165 focused tests and 30 subtests on the formatted tree. Its six
Black corrections and both collection typing fixes were applied in
`5884e4a1f251`; the temporary workflow was removed. An additional source
review consolidates live registration and recovery's isolated expected-state
registration in the existing service owner, and both readiness projections
in one composition helper. These extractions preserve the canonical carriers,
store writer, core graph evaluator and public bounds (FD-88A/94; TD §17.2).
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

### S-FIELD-05 — Verifiable installed runtime identity

**Status:** IMPLEMENTED IN CANDIDATE; VERIFICATION OPEN. Authority FD-88A, acceptance 73; mechanism TD §20.

- Reuse the existing build generation and package-data owner in checkout and
  distribution paths; prove actual installed identity, not requested checkout
  revision or package-version equality. Detect missing, stale, changed and
  unverifiable identity before claiming exact install acceptance. Keep clean/
  dirty source provenance honest. No generated identity edits, new identity
  carrier or copied receipt value as proof.
- Exercise fresh and reused environments, same-version different builds,
  generated identity missing/stale, dirty and unknown source, distribution
  installation, and read-only verification. Assert observed identity agrees
  with the installed artifact and requested build where verifiable. Expose
  only meaningful operator-facing provenance and actionable failure; do not
  expose build internals in MCP or require an agent to correlate receipt internals.

### S-FIELD-06 — Correct host reachability observation and reconnection guidance

**Status:** IMPLEMENTED IN CANDIDATE; NATIVE DELIVERY EVIDENCE OPEN. Authority FD-49/52/53/58, acceptance 74; TD §§15, 22.3.

- Correct the existing adapter observation of the intended installation's
  complete native L8 tool set. A partial or foreign catalogue, lost connection,
  re-registration or stale prior observation is not readiness. Use documented
  native host capabilities; unsupported refresh requires explicit restart or
  fresh-session guidance. Do not own transport lifecycle, add discovery tools,
  increase polling limits as a fix or introduce persistent readiness state.
- Test cold start, partial/foreign catalogue, disconnect after readiness,
  re-registration, reconnect, unavailable native refresh and fresh-session
  delivery. The notice identifies unavailable capability and supported user
  action, never raw transport exception, private event state or internal names.
  Record native authenticated delivery evidence separately under FD-53; adapter
  simulation is not that evidence.

### S-FIELD-07 — Deterministic invocation validation and public administrative guidance

**Status:** CANDIDATE IMPLEMENTED; OUTPUT AUDIT AND VERIFICATION OPEN. Authority FD-27/88A/88B, acceptance 75; TD §20.

- Move compatibility validation into the existing argument-validation owner
  before state-dependent checks or effects. Cover every incompatible operation
  with classification input and applicable related options; name the actual
  public flags, conflict and supported next invocation. Preserve valid modes,
  dry-run and read-only behavior. No duplicate checks or new command grammar.
- Close FIELD-07 at the readiness/projection owner: inspect all affected
  verifier/doctor, install, recovery and host notice outputs for internal
  finding codes, raw exceptions, private generated paths and bookkeeping.
  Reuse canonical public findings and expected failure projection; retain
  detailed diagnostic evidence internally. Do not remove a public user-input
  coordinate or supported backup/receipt reference necessary for recovery.
  The retained on-disk receipt is internal recovery evidence, not a new API.
- Exercise structured and human-readable output, including nested detail,
  recovery/action fields and errors before final publication; assert stable
  actionable causes and absence of private diagnostics with deliberately
  distinctive internal test values. Preserve existing FD-27/88B MCP schema
  and installed negative leak tests. No new carrier/DTO, aliases, semantic
  state, writer or public API. Run the complete existing CI unchanged.

Follow-up diagnostic [45935760895](https://github.com/pontivus-com/span/actions/runs/45935760895)
passed 157 focused tests, 14 subtests, 15 plugin tests and zero-error typing
on the formatted candidate. Measured test lines increase from 35,091 to
35,140 (+49 lines), recording the added and consolidated identity, invocation,
verification and recovery regressions; no architectural limit is raised.
The longest function is 131 lines, below the existing 141-line ceiling.
The temporary diagnostic workflow is removed before final full CI. Simulated
host catalogue observations do not establish live authenticated delivery.

Closeout review of `6d66e89ad222`: [CI 45935891140](https://github.com/pontivus-com/span/actions/runs/45935891140)
passed 1,035 tests with 2 failed acceptance-matrix checks (FA-73–75 were
unmapped and the ordinal assertion stopped at FA-72). It did not establish
acceptance. Review findings F01–F12 also identified inconsistent exact-build
proof, unproven host reachability, private administrative diagnostics and lost
public coordinates. The follow-up retains the initial requested identity until
receipt publication, requires identical installed sources without obsolete
files, reports catalogue uncertainty rather than live readiness, uses existing
typed rejection/public finding owners, and retains public document coordinates.
The matrix now requires all 75 cases with live executable references. The
prior discriminator test now requires rejection plus file/item coordinates and
exclusion of internal type names; its rejection contract is not relaxed.

[Diagnostic 45943190670](https://github.com/pontivus-com/span/actions/runs/45943190670)
passed 196 focused tests, 41 subtests, 15 host tests, Ruff and zero-error
typing on `aab049f3426b`. Test lines measured 35,221; the added authority
provider diagnostic regression contributes 19 lines, for a candidate
ratchet of 35,240 (+100 over 35,140).
All other architectural ceilings remain unchanged; longest function measured
131 lines. Final CI must establish the exact candidate and confirm the
measured ratchet. The temporary workflow is removed. The adapter cannot
attest a live authenticated connection from catalogue names; native delivery
evidence remains OPEN. Exhaustive operator-output and recovery-boundary
acceptance, independent review and DCO sign-off remain OPEN.

### S-FIELD-04 — Exact-candidate regression and acceptance closeout

**Status:** OPEN. Depends on S-FIELD-01–03 and S-FIELD-05–07.

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
- Independent review checks FIELD-01–07 and F-01–F-06 against the amended
  design. Map FA-73–75 to executable tests and native delivery evidence where
  required; audit public outputs including free text against FD-27/88B/88A.
  Preserve existing FA-71 schema and installed-wire evidence.
  A controlled local retest of the real adopter corpus is the next adopter
  gate; no publication, release tag, merge or live adopter mutation is
  authorized by this amendment.

**Gate:** all field fixes demonstrated by executable evidence; complete
candidate CI green, then owner-authorized local Beta-5 retest. Prior green
CI and the adopter's reported version 8 are not closure of FIELD-01–03.

## 3B. Public lifecycle boundary remediation — 2026-11-27

**Status:** OPEN — source review at `fd571b4a9fc2d28dc4e9177537a590e5ab7490b1`.
This is the single task owner for this cross-cutting Beta-5 correction, including
ordinary lifecycle prerequisites; no implementation or installed acceptance is
asserted. Authority: lifecycle §5, F2/F4/F6–F9/F11–F13, L1–L17, FD-27/54–57,
FD-62/88B/88C, TD §§9/17.1/21. The canonical P2/P3/P4 changes now own the public outcome, deterministic
behavior and mechanism; this register owns execution and evidence, not a
second product authority. PUB-01 verifies their exact generated-schema and
runtime conformance before dependent code is accepted. Preserve S-FIELD-01–07 obligations and release gates.

### Anti-patterns

AP-01 over-fetch; AP-02 under-fetch; AP-03 private representation leakage;
AP-04 scope expansion; AP-05 duplication; AP-06 consumer reconstruction;
AP-07 unrecoverable truncation; AP-08 primary outcome displaced; AP-09
unbounded auxiliary growth; AP-10 ambiguous/misleading lifecycle outcome;
AP-11 private diagnostic leakage; AP-12 inconsistent lifecycle guarantees.
Apply these criteria transitively to all public request/result branches,
including errors, audit retrieval and installed delivery.

### Finding register and target correction

Paths below are under `src/span/` at the pinned baseline. The first 22 rows
consolidate the public-boundary investigation; API-23 is the new field report.

| ID / AP | Source evidence and producer | Required outcome / solution direction | Acceptance discriminator |
| --- | --- | --- | --- |
| API-01 / 01,03,09 | core/model/functional_pyramid.py:276–291,469–494; service/functional_pyramid.py:351–370 | Status returns participation, identity/version, health, member IDs and actionable findings, not declaration inventory. Retain source refs in internal state and justified audit. | Vary declaration count without unrelated status growth. |
| API-02 / 01,05 | service/functional_pyramid.py:644–693 | Candidate returns action, observed target/version, readiness and findings; no echoed resolved declaration collection or commit token. | Valid/invalid and stale multi-member candidates. |
| API-03 / 01,05,10 | service/functional_pyramid.py:1448–1463 | Accepted action, receipt, participation effects and recoverable dependent obligations; no complete member inventory. Preserve replay. | All actions, exact replay and effects. |
| API-04 / 07,09,12 | shell/mcp/adapter.py:397–450 | Bound installation-scoped results using existing delivery semantics; never lose committed identity or unresolved findings. | Large status/candidate/receipt/effects. |
| API-05 / 01,04,09 | service/surface_status.py:25–108; service/answer.py:99–170 | Status scoped to selected subject; exact selectors do not carry unrelated recursive status. Preserve truthful distribution and actionable pending/stale refs. | Unrelated descendant/sibling growth. |
| API-06 / 01,09 | service/answer.py:589–609 | Relevant verification evidence rather than all history; preserve conflicting failures, scope, time, outcome, limitations and qualification; history recoverable. | Repeated runs, distinct scenarios, later failure. |
| API-07 / 08 | service/answer.py:1008–1105 | Primary result before auxiliary data; page necessary remainder without losing mandatory qualification. | Large auxiliary payload cannot evict primary answer. |
| API-08 / 07,12 | service/answer.py:1022–1072 | Embedded multi-path governance continuation recovers exact original selection, not guessed directories. | Multi-path selection, deterministic complete paging. |
| API-09 / 04,07,09 | service/answer.py:611–701 | Exact historical retrieval bounded and pinned; distinguish later challenge events/live qualification. | Large history and later mutations. |
| API-10 / 03,05 | core/model/understanding.py:62–104,299–308; core/model/support.py:82–139 | Audit returns exact semantic content/withdrawal, evidence, premise/governing references and provenance, not stored content/support dependency unions. | Historical semantic equivalence and no transitive private type. |
| API-11 / 01,04 | service/lifecycle.py:823–898 | Qualify affected knowledge, separately identify dependent obligations; do not return entire owner state. | Narrow update in broad surface. |
| API-12 / 02,06,10 | core/model/outcomes.py:27–38; L17 | Explicit revision-bound CAPTURED/CURATED independent of support, with withdrawal distinct. | Create/correct/confirm/curate/withdraw/replay. |
| API-13 / 02,06,10 | core/model/outcomes.py:27–38; core/model/understanding.py:270–295 | Exact accepted challenge revision/disposition and remaining question; no inference from acceptance. | Resolved/unresolved/batched dispositions. |
| API-14 / 12 | service/lifecycle.py:201–246; ports/lifecycle.py:284–320; shell/sqlite_store/lifecycle.py:361–436; core/model/recording.py:76–111 | Surface write atomic request receipt and CAS/replay under L4; existing content idempotence is insufficient. No artificial investigation context. | Retry after intervening update, conflict, atomic crash/concurrency. |
| API-15 / 01,03,09 | core/model/answers.py:298–315; service/effects.py:412–448 | Change qualification uses public causes/evidence, exact revision/version and reasons, not full SupportEvaluation. | Direct/indirect/forced/non-current/unavailable. |
| API-16 / 02,07 | service/effects.py:300–410 | Complete discoverability of affected obligations independently of delivery bounds, including per-repo context and accepted effects on replay. | Deep/branching/cyclic cross-repo graph, all refs recoverable. |
| API-17 / 02,06 | service/reconsider.py:110–136; lifecycle §4.3 | Challenge returns exact disputed prior statements and evidence, challenge coordinates and context. | Older and multiple target revisions. |
| API-18 / 03,12 | core/model/support.py:36–80,178–272; core/model/functional_pyramid.py:751–760 | Correct existing qualification projection: DependencyFinding currently embeds internal SupportDependency even in compact results. Semantic causes and evidence/premise/governing coordinates only; all non-current causes retained. | Generated schema and installed wire across every nested consumer. |
| API-19 / 04,06,10 | service/lifecycle.py:858–898 | Return exact accepted effects rather than snapshot membership; semantic_effects computed then not used for normal updates. | One of two revisions, gap-only/no-op, confirm, withdraw, curate. |
| API-20 / 04,10 | service/effects.py:300–432 | Track change reasons per exact revision, separately aggregate surface reasons; no reason bleed. | Direct-only and indirect-only in one surface; true multi-reason case. |
| API-21 / 04,07,12 | service/answer.py:451–536,771–806; service/evidence.py:76–84; service/continuation.py:24–32 | Pin ordered admitted selection/ranges at issuance; same sequence in initial and continuation, not all mutable context observations in sorted ID order. | Reverse order, later context extension, drift and restart replay. |
| API-22 / 01,07,08,09 | service/answer.py:451–536,1008–1141; service/evidence.py:244–270 | Page admission outcomes and source content; distinguish omitted admission and deferred content, no duplicate omission inventory or lost accepted context. | Large batch, failure/range metadata, oversized line. |
| API-23 / 02,04,06,10 | service/functional_pyramid.py:404–449; shell/functional_pyramid.py:66–73; core/model/functional_pyramid.py:517–529,620–675; shell/mcp/adapter.py:60–99,397–450 | Correct directory address ownership before participation; FD-62/88C and TD §17.1. Same exact applicable governance and parent-root public locations via either address; directly usable in ordinary lifecycle; no namespace discovery preflight. | Nested registered roots, direct/parent-relative equivalence, explicit non-ACTIVE and ambiguous/unavailable cases, stable pages and no leak. |

### API-23 field evidence and decision

Owner-reported installed runtime (not independently reproduced): parent-relative
queries into two nested member directories returned 7 root placements, versus
47 and 74 from equivalent member-relative queries. This is a plausible but
mis-scoped RESOLVED answer, not proof of a missing declaration or a graph defect.
The directory service currently calls _active_participation on the supplied ID,
then passes the same ID and relative path to the pure resolver. The filesystem
existence check permits nested paths but does not establish owner. Registry
roots already exist; no new metadata or adopter shim is required.

Adopt existing directory selector with server-side ownership resolution, not
a new root-relative selector, root map in status, or adopter path rewrite.
Strict nested roots are intentionally supported; only non-unique deepest
ownership is ambiguous. Registered ownership precedes participation (including
a nested registered repository in another instance or UNCONFIGURED/EXCLUDED);
never combine ancestor and child governance merely by filesystem nesting.
Owner decision (2026-11-27): return the resolved owner and all governance
locations in the outermost registered parent root's coordinates, regardless
of whether the parent or member addressed the directory. This includes the
selected directory, every document path, placement scope and finding directory;
the member-root scope is its prefix from the parent, not `.`. The public
placement/path carriers in lifecycle §4.1 are the sole projection; keep
canonical owner-relative identities internal, never publish duplicate local
and translated paths. Explicitly qualify references outside that root tree
by their own registered root; never use absolute paths or traversal. The
directory contract is distinct from automatic rewrites of semantic identity:
audit ordinary surface/reference obtain, evidence admission, record scope,
changed-scope reconsideration and hooks for the same namespace assumption;
document exact ownership semantics for each before any broader change. Do not
silently reroute a retained revision or split a write across owners. Existing
classification scope and document authority remain independent.

### Canonical traceability and execution gates

The following cross-reference is exhaustive for the session register. P2 is
lifecycle-contract.md; P3 is functional-design.md; P4 is technical-design.md.
Acceptance references are existing FA cases as amended in P3 §15, not
claims of already passing tests.

| Finding | P2 owner | P3 owner | P4 owner | Task / acceptance |
| --- | --- | --- | --- | --- |
| API-01 | §4.1 status | FD-83,88B | §§17.1,20.1 | PUB-06 / FA-01,36,71 |
| API-02 | §4.1 candidate | FD-84,88B | §§17.1,20.1 | PUB-06 / FA-02,71 |
| API-03 | §4.2 FP acceptance | FD-85,93 | §§19,20.4 | PUB-06 / FA-03,04,38,41 |
| API-04 | §4.1 continuation | FD-54–57 | §§13,17.1,20 | PUB-04,06 / FA-71,72 |
| API-05 | §4.1 status | FD-23,28,101 | §§11,24.1 | PUB-05 / FA-28,48,51 |
| API-06 | §4.2 verification scope, §4.1 | FD-28,29,55 | §§11,13 | PUB-05 / FA-28,66 |
| API-07 | §4.1 continuation | FD-29,54–57 | §§11,13 | PUB-04 / FA-28,72 |
| API-08 | §4.1 embedded orientation | FD-55,62,69,88C,90 | §§13,17.1,20.1 | PUB-04 / FA-10,14,72 |
| API-09 | §4.2 snapshot/receipt audit | FD-28,55 | §§11–13 | PUB-02,04 / FA-28,66,72 |
| API-10 | §4.2 audit basis/snapshot | FD-16,28 | §§9.2,11 | PUB-02 / FA-28,71 |
| API-11 | §4.2 acceptance | FD-37,60 | §§12,20.2 | PUB-07 / FA-45,47,66 |
| API-12 | §4.2 accepted maturity | FD-60,95–98 | §§12,23–24 | PUB-07 / FA-47,50,53–59 |
| API-13 | §4.2 accepted disposition | FD-37 | §12 | PUB-07 / FA-62,66 |
| API-14 | §4.2 surface/receipt | FD-2–4,46–48 | §§12,14,25 | PUB-07 / FA-28,66 |
| API-15 | §§4.2–4.3 qualification | FD-16,20 | §§9.2,20.3 | PUB-02 / FA-24,38,71 |
| API-16 | §§4.1,4.3 complete effects | FD-19–22,55,85,89 | §§13,20.3–4 | PUB-03,04 / FA-24,25,38,41 |
| API-17 | §4.3 challenge | FD-37 | §§11,12 | PUB-08 / FA-62,66 |
| API-18 | §4.2 public support | FD-16,27 | §§9,9.2,11 | PUB-02 / FA-65,66,71 |
| API-19 | §4.2 exact effects | FD-37,60 | §§12,24.2 | PUB-07 / FA-47,53–59,66 |
| API-20 | §4.3 per-ref reasons | FD-20–21 | §§11,20.3 | PUB-03 / FA-24,25,38 |
| API-21 | §4.1 evidence continuation | FD-2,55,59 | §§9.2,13 | PUB-04 / FA-28,66,72 |
| API-22 | §4.1 admission pages | FD-29,54–57 | §§9.2,13 | PUB-04 / FA-28,72 |
| API-23 | §4.1 directory/location | FD-62,74,88B–C | §§17,17.1,20.1 | PUB-06 / FA-09,10,14,16,72 |

### Ordered implementation tasks (all OPEN)

**PUB-01 — Executable baseline and conformance preflight (OWNER-CONFIRMED COMPLETE).** Before production
changes, generate the actual three tool request/result schemas at the pinned
source baseline and recursively enumerate every reachable public carrier,
including nested unions, optional fields, errors and actual free-text
producers. Inventory all 21 consumer intents and document field ownership
against P2 §§4–5. Capture sanitized failure-before evidence for API-01–23;
use generic fixtures only. INV-01/08: digests, replay keys and expiry are
private, accepted semantic effect and exact member declaration evidence are
audit; INV-02: preserve opaque repository-bound context; INV-03/04: audit
public override/provider errors including sentinel internal values; INV-05:
evidence IDs/fingerprints and admitted ranges retain citation identity;
INV-06: version-targeted challenges/current dispositions explicitly separated;
INV-07: latest applicable verification grouping and history as P3 FD-28.
Check actual generated schemas against amended exact P2 fields and record
every remaining discrepancy in the corresponding P2/P3/P4 owner before code.
Verify path-bound ordinary ask/evidence/record/reconsider/hooks against
closed P2 §4.1 / P3 §2 / P4 §17.1 addressing design; baseline all affected
paths. Verify the concrete schema-16/2 and ResultPage contracts; no design
delegation to implementers. Gate: actual baseline and recursive generated
schema evidence; discrepancies stop at governing owner before code. All
nine review corrections are assigned below; no silent extra scope.

**PUB-01 baseline execution record.** Documentation candidate `36a3e77b6d8f`
CI run 45951210720, test job 140347349335: lint, formatting, typing and build
passed; 1,037 tests passed, one failed and one skipped. Existing
`SurfaceConformanceTest.test_result_union_declarations_agree` failed on its
obsolete Markdown delimiter before comparing result families. Correct that
parser at the existing conformance owner (no weakened equality checks), make
the conditional restart families explicit in P2's ask table, and add
failure-before assertions over the actual generated output schema definitions
and selected public result fields for API-01/02/03/10/11/14/15/18/19. These
assertions are target regressions, not preservation of the defective shapes;
they are expected to expose baseline failures until their owning tasks fix
them. The full recursive field/provider audit, real wire failure-before
coverage, path consumer tests and independent conformance review remain
OPEN. No production change is authorized until PUB-01's gate is satisfied.

**PUB-01 execution update (2026-11-27).** CI 45952859693 at
`a84ffc5475803` completed: lint/format, typing and build passed;
1,039 passed, 12 failed, one skipped (226 passing subtests).
Eleven target conformance subtests established failure-before for the
result unions, private carrier reachability and five compact result shapes.
One unintended measured test-lines regression was 35,240 → 35,340.
Reconcile that measured metric and the exact additional test-line delta
(+122, target 35462) in tests/code_budget_baseline.json, without changing
the gate or any production metric. The new tests target exact-question
population (API-05), repeated verification selection (API-06), complete
effect discovery independent of query bounds (API-16), per-revision
attribution (API-20), challenge opening fields (API-17), and installed
parent-addressed admission (API-23). The two older tests that required
semantic truncation are corrected against FD-20/54–57: their old expected
behavior is the defect, not a compatibility requirement. Their replacements
inspect the shared engine before delivery and require all affected surfaces,
without issuing contexts. Preserve all real delivery-bound checks in their
existing owner tests. New probes await execution; do not claim PUB-01 closure.
Remaining full provider/consumer/schema audit and all dependent gates stay
OPEN. Existing intentional red assertions are not waived or xfailed.

**PUB-01 owner direction (2026-11-27).** The release owner confirmed that
PUB-01 is complete and directed implementation to continue across the remaining
PUB tasks without repeating baseline work. Earlier OPEN statements above are
historical execution records; this owner direction does not invent additional
baseline evidence or waive task-specific conformance/architecture acceptance.

**Architecture acceptance applies at each PUB task gate.** TD §9.2's
remediation construction ownership is binding. PUB-01 records actual
source owner/call-site inventory, planned replacement/deletion of superseded
mechanisms, typed port boundaries and I-01/I-04/I-13/I-15/I-18/I-21/I-28/I-39
and existing architecture-guard evidence baseline. For every task, verify
implementation against that owning mechanism and P0–P3 before downstream
integration. A functional pass with a second owner, DTO, unchecked boundary,
compatibility path or misplaced effect is a failed task. No architecture
cleanup deferred to PUB-09/10; those integrate/verify, not repair debt.
Record actual tests and review evidence in the existing invariant/functional
acceptance matrices, never mark passing from plan text.

**PUB-02 candidate development increment (OPEN, not accepted).** CI
45954673769 at `a8cf8c1f763a` established 18 target failures, with 1,038
passing and one skipped; the measured test-budget gate passed. The first
source increment implements the live public support basis and finding union
at the existing core support owner, resolves recorded facts through the
existing support service, and replaces live qualification consumers
including edit notices. It does not change retained support records or
store versions. The existing wire registry is extended for the seven
canonical semantic carriers (measured carrier count 226 → 233); the
recorded-source equivalence test adds 25 test lines. The raw historical
audit and receipt projection, full PUB-01 audit, schema transition, and
all acceptance evidence remain open. This candidate is not permission
to close PUB-01, PUB-02 or proceed to deployment.

**PUB-02 exact retrieval owner reconciliation (OPEN).** CI 45956749986
passed formatting and stopped at the typing ratchet: the older internal
UnderstandService retained the obsolete snapshot constructor. Move all
snapshot and receipt selection/composition into that existing owner and
inject the same service instance into AnswerService from shell composition.
Update the existing internal retrieval test and all direct test compositions;
no second snapshot producer or compatibility view. Test lines +16.

**PUB-02 snapshot increment (OPEN).** Replace raw conclusion revisions and
version-wide internal support in exact snapshot delivery with the canonical
AuditConclusion supported/withdrawn union. Resolve recorded basis through
the existing support owner, retain exact semantic derivation and selected
version facts, qualify supported content only, preserve withdrawal and
version-scoped maturity. Challenges are selected by exact target version;
their shared fact carrier cutover and receipt audit are still required in
PUB-07A. This increment changes no persisted model. Measured canonical
carrier count 233 → 236, maximum carrier fields 13 → 14 (exact required
snapshot facts), test lines +13. No compatibility shape or separate
evaluator is introduced; CI verification remains open.

**PUB-02 — Public support and immutable audit (API-09/10/15/18).** After
PUB-01, edit core/model/support.py, understanding.py, answers.py, repository
exports and service/support.py / service/answer.py / service/effects.py
at their existing projection/evaluation owners. Implement typed SupportBasis,
SupportFinding and AuditConclusion from P2 §4.2, preserving immutable stored
support, canonical identity and single evaluator. Resolve source observation
ranges and exact evidence, premise refs, all recorded authority semantics and governing
scope; unavailable recorded basis explicit. Preserve SemanticBasis derivation,
summary and exact input refs for both supported and withdrawn content. Test
complete semantic equivalence including authority applicability/precedence,
observation time and exact evidence boundaries. Replace SupportEvaluation in
ChangedConclusion and eliminate transitive DependencyFinding/SupportDependency,
AuthorityBinding, FunctionalRouteIdentity and stored revision content from
all result schemas. Snapshot selection pinned to version, version-as-of
curations and exact targeted challenge history with present state labeled.
Test all five dependency kinds, mixed loss precedence, unavailable basis,
historical withdrawn content, later curation/challenge, and negative recursive
schema plus installed wire assertions. No transport stripping or regenerated
authority. Gate: exact semantic audit equivalence, no private type leakage.
Architecture gate: establish TD §13's shared immutable verification and
challenge fact components at their existing canonical model owners; retain
complete stored records and build the single public audit projection reused
by PUB-05/08. Any persisted-carrier change is integrated atomically with
PUB-07A's offline migration and target store version. Develop and test the
pure components first; do not commit a runtime that reads old persisted
shapes as the new model or keep a temporary runtime bridge. Replace compact_support/compact_understanding/
compact_verification at their canonical ownership boundary as applicable;
all consumers use one typed support projection with service-supplied facts.
Inspect import direction and actual call sites; pure projection test without
filesystem/SQL/service fixture, every nested generated variant negative
schema test, no raw dependency object or parallel stored support model.
I-01/04/06/15/18/43.

**PUB-03 candidate increment (OPEN).** CI 45955614825 confirmed the
PUB-02 live schema checks for record and reconsider passed; ask still
exposes retained audit carriers. Three mock fixtures failed because
they did not implement the new qualification contract. Restore the
test-double contract through the real core projection, without weakening
assertions. Remove traversal limits from the shared effects engine and
its constructor, retaining result budgets at the service delivery owner.
Read the complete reverse index, propagate forced governance roots first,
track every indirect edge before visited-set deduplication, and assign
per-revision causes through pure core rules. Add direct+indirect and
frontier tests; exact test-line delta 26. Accepted receipt cause persistence,
effect disposition and bounded delivery are not implemented by this
increment and remain required. No acceptance gate is closed by this change.

**PUB-03 — Exact complete effects (API-16/20).** After PUB-02, modify
service/effects.py at _project/_indirect/_changed_conclusion and shared
reconsider/Pyramid record callers. Keep full direct roots and premise closure
independent of delivery bounds; accumulate reasons per ref then aggregate
surface, preserve containment-only entries. Produce complete immutable effect
refs before accepted participation commit; context once per actionable owner.
Operational interruption follows FD-20: explicit Unavailable with original
changed-scope recovery, no partial Changed or context issuance; abort
participation transaction before commitment. Test injected interruption before
and during traversal and precommit failure. Tests: direct-only and indirect-only on same
surface, genuine multi-reason ref, deep chain beyond former max_depth/nodes,
wide graph, cycles, cross-repo, omitted context/replay, current/superseded refs.
Gate: full affected identity set and true attribution, including accepted
replay and ordinary dependent effects. Persist original per-ref reasons and
surface with immutable accepted coordinates; replay must not rewrite all
causes to DIRECT. Test direct seed reached as indirect dependent, replay
of indirect effect, current/superseded/withdrawn/unavailable dispositions,
and legacy unknown cause. Keep a stable affected_conclusions slot through
live disposition changes; verify successor support before declaring an effect
discharged. PUB-03 closes pure traversal/projection first; receipt/manifest
persistence integration follows PUB-07A and PUB-04. Shared engine, no second traversal.
Architecture gate: pure frontier/visited/reason decision tests over supplied
facts, one service-owned repository-qualified traversal and one live-effect
projector; no shell graph walk, local fallback or new semantic callback.
Prove same engine used by ordinary/participation/record effects and preview;
preview writes no contexts or delivery state. I-01/13/15/28/30/48.

**PUB-02/03 candidate development update (OPEN).** Commits
`eb37ba4`, `32bf2a7`, `fa4ff73`, and `da429da` reconcile stale
test compositions, preserve unavailable recorded basis coordinates and
distinguish operational errors from invalid model state. Reconsider returns
Unavailable for interrupted discovery and requires the original changed scope
on retry. Participation route-provider failures propagate before commitment.
The shared context owner gathers every actionable repository's complete
binding before issuing any context. Failure-before/after probes cover all five
support basis kinds, discovery interruption, precommit activation failure and
cross-repository context gathering. No storage version is changed; shared
immutable verification/challenge components, receipt audit, accepted causes,
migration, bounded delivery and acceptance remain OPEN. Actions is the only
test execution owner; do not claim acceptance before the exact candidate's
checks complete.

**PUB-04 — Bound exact result delivery (API-04/07–09/16/21/22).** After
PUB-02/03 and PUB-07A, modify service/continuation.py, bounds.py, answer.py, evidence.py,
lifecycle.py, reconsider.py, functional_pyramid.py and shell/mcp/{adapter,wire,
schemas}.py; use existing store/retention owners for immutable ordered
delivery selection. Extend existing token grammar to typed selection owner,
namespace, exact request/receipt/version, collection position and binding;
source outcomes/ranges pinned when admitted. Implement canonical ResultPage/ResultPart and exact allowed item/parent pairs
(P2 §4.1), not continued Answer or separate VerificationHistory. Use §13
selection/cursor tables in installation schema 2 and existing retention;
directory after routes to the same ResultPage, pending keyset retains its
canonical form. Test stale state vs timestamp-only changes, exact restart,
missing/forged cursor, mixed nested collection, no-progress rejection,
expiry with undisposed effects, receipt recovery after manifest loss.
Test state changes between nested effect pages (including context expiry):
restart with a fresh initial envelope of the same pinned selection via the
typed rejection recovery token, no offset reuse, no new traversal or write. Verify one enclosing delivery metadata owner and exact count/ref
equality on complete delivery; reject misleading partial status.
Test repeated admission retry against the same durable manifest, successor
becoming non-current, and primary-complete Answer with history cursor. No
second evidence selection or semantic writer. Fit mandatory subject/state/
receipt envelope first, primary content then aux, page all P2 variable
collections (including nested findings, evidence metadata, exact receipts
and contexts), constant omission description, no lost commit. Preflight
minimum acceptance envelope before write; postcommit delivery failure returns
receipt recovery. Invalidate stale reads, exact restart and replay; re-evaluate
pinned accepted effects without dropping undelivered obligations. Verify
encoded size in both MCP channels using existing budget, max-size single
unit/line, empty page/progress, unbounded metadata, large candidate/status/
receipt/changed writes, cross-repo scope, exact multi-path orientation,
order drift and later context extension, restart and postcommit failure.
Gate: all independently pageable selections recoverable without new ceiling
or gate edits; FD-57 handles a genuinely indivisible oversized fact explicitly.
Use PUB-02's shared recorded-fact components and P2's nested slices; never
avoid delivery by making a whole retained run, challenge or member atomic.
Test single run with large observations/limitations, single challenge with
large target/disposition/resolution evidence collections, and one member with
large declaration inventory. Reassemble exact ordered semantic facts across
pages without partial stored records or mirrored DTOs.
Architecture gate: TD §13 single canonical encoder and pure fitting decision,
one service continuation owner, closed typed selection/part variants, no
runtime reflection or DTOs, no trimmed retained semantic records. Delete
superseded evidence-only cursor codec, per-family fitters and shell cursor
routing; retain only domain entry points delegating to shared delivery. Test
byte parity, strict variant/parent rejection, unchanged immutable record
round trip, initial valid envelope, no state write in preview, accepted
manifest stores receipt pointer only and no copied accepted effects.
Test reaping against a concurrent semantic update: final disposition check
uses locked typed capabilities and deletion retains changed/unknown candidates.
I-01/02/04/13/15/16/18/21/28/35/36/39.

**PUB-05 — Select status and relevant verification (API-05/06).** After
PUB-04, edit service/surface_status.py and service/answer.py (_document,
_question_result, _verification), core/model/surfaces.py and answers.py.
Construct StatusSubject for surface/question/exact understanding version
before status; only ordinary surface obtain calculates boundary and immediate
child summaries; remove
recursive descendant inventory; count/ref consistency across pages.
Match runs to complete selected scope and select FD-28 latest recorded plus
latest CURRENT per outcome; preserve ties and history cursor. Test earlier
CURRENT FAIL vs later stale/unavailable PASS, and current conflicting runs. Preserve outcome/time/provenance,
environment limitations and live qualification. Test sibling/descendant growth,
empty exact selection, narrower/wider run coverage, repeated run, conflicting
ties, later fail and older history. Gate: unrelated corpus growth cannot
displace selected answer; scoped counts truthful and history recoverable.
Architecture gate: deterministic population, counts, group/tie selection
and ordering in core over typed supplied facts; existing service reads once
and calls one evaluator per distinct candidate. Remove recursive status
composition and duplicate verification selectors; no SQL or transport-level
filtering. Unit test pure selection and count invariants, then actual service
and installed retrieval. I-01/04/12/15/18/42/43.

**PUB-06 compact projection increment (OPEN).** The existing status,
candidate and accepted-write carriers no longer expose declaration member
inventories. Status reports member repository IDs; candidate validation
returns the canonical public verdict and existing retained member facts
separately to its transactional caller, with no second validation engine.
Installer verification reads immutable accepted version membership from its
existing read-only state capability; the installed probe obtains declaration
references via the exact receipt, not the write response. This is an
independent compact-projection increment, not completion of PUB-06's
root-addressing/delivery obligations. Test lines +9. Integration and
acceptance still require PUB-04 and PUB-07A; no gate is closed.

**PUB-06 — Compact governance and end-to-end root addressing (API-01–04/23).** After
PUB-04 and API-23 root-registry verification in PUB-01, change core/model/
functional_pyramid.py, core/functional_pyramid.py, service/functional_pyramid.py,
ports/functional_pyramid.py, shell/functional_pyramid.py,
shell/installation_runtime.py and shell/mcp_server.py as specified in TD §17.1.
Separate stored member/receipt facts from status member IDs, candidate findings
and write acceptance; exact receipt retains justified declaration evidence,
not private digest. Reuse registered_locator callback, not attached-store
paths; pure unique-deepest-root containment before participation, normalize
public coordinates from outermost registered ancestor, standalone/other roots
explicitly qualified, no duplicated owner-relative path, path map, or absolute
root. One canonical public projection for directory, orientation and findings.
Bind pages to actual selected owner and path basis; no change to canonical
placement/support/authority identity. Implement §17.1 shared address owner
in existing routing, ordinary ask/evidence/record/verification/reconsider and
hooks; validate context/identity vs path distinction, single-owner writes,
partition changed paths into one effect engine, deleted file, symbol suffix,
parent/child alias conflict and request replay after registry change.
Installed end-to-end: obtain nested docs from parent, read/admit exact returned
address, record against owning child, edit from parent and reconsider, then
retrieve accepted child receipt; no consumer namespace inference. Cross-owner
batch write/admission rejection before any mutation. Reuse PUB-07 transaction
and PUB-04 selection mechanisms. Installed nested --repo fixtures:
parent-relative/member-relative equality after all pages, member-root '.'
becomes parent prefix, direct document/scope read locations, shared parent/
sibling references, unrelated trees, findings, ordinary embedded view, three
levels, prefix-lookalike, equal-root ambiguity, unknown/unavailable root,
escape/symlink, other-instance/EXCLUDED/UNCONFIGURED child, no inferred
participation, stale token after root/selection changes; preserve graph and
cross-repo effects. Vary member declaration inventory and verify compact
status/candidate/record independent of unrelated detail. Gate: exact functional
equivalence and no consumer path translation or internal leakage.
Architecture gate: §17.1 shared installation capability constructed once,
core deterministic root resolution/rebasing, filesystem shell supplies facts,
service normalizes once before owner dispatch. No FP-dependent generic
routing, shell semantic selection, copied root map, downstream normalization
or optional reduced runtime. Remove replaced wire routing/FP directory-only
resolver code. Test pure root selection, port fault handling, installed
ordinary/FP/hooks parity and original request arbitration across concurrent
origin/owner operations. I-01/07/13/15/17/18/28/39/48.

**PUB-07 — Accurate write outcomes and surface receipts (API-11–14/19).**
PUB-07A follows PUB-02/03; PUB-07B follows PUB-04. For PUB-07B, change core/model/{outcomes,recording,commands,
understanding,answers}.py, core transition owner, ports/lifecycle.py,
service/lifecycle.py, shell/sqlite_store/lifecycle.py and existing migration
owner per TD §§12,14,25. Retain immutable AcceptedRevisionEffect/action/
ref/maturity, replacement predecessor, accepted challenge disposition and
dependent refs inside existing atomic receipt; qualify only accepted supported
refs after commit. No full snapshot or recursive status. Gap-only and
disposition-only no revision effects; no-op confirm explicitly unchanged.
Surface action, canonical accepted boundary/version and receipt committed
atomically under existing repository request key; no artificial context.
Replay before live parent/version/support checks, original accepted effect
after later update; conflicting same request rejected; different request
CAS preserved. Implement §14 repository schema 16 and installation schema 2 migration as
PUB-07A before PUB-04 (shared schema/transaction infrastructure). PUB-07B
is accepted-outcome composition after PUB-04. No circular gate. Map old receipts offline to
exact accepted effect or HistoricalAcceptanceDetailUnavailable; preserve every
receipt key/digest, history and curation; original origin canonical owner.
Apply TD §14's shared semantic component factoring in the offline mapping;
compare reconstructed exact recorded facts to the input, no runtime dual
shape. Preserve challenge disposition coordinates and retained history.
Use existing boundary history rows and atomic addressed-request index owner.
Verify all source schemas, installation 1→2, full staged/verified activation,
interruption recovery and rollback, no mixed-version runtime.
Verification: all semantic actions, no-op, gap-only, challenge resolve/
unresolved, curation independent of currency, surface create/update/replay/
conflict/concurrency/interrupted transaction, postcommit unavailable support,
legacy receipt and history migration. Gate: exact accepted facts and stable
replay, no fabricated historical acceptance, one transaction owner.
Architecture gate PUB-07A: schema conversion is offline-only; typed ports and
one existing transaction scope reuse existing context/surface/receipt writers
for attached and ordinary stores. No SQL in service, no shell semantic
callback, no second receipt table, no new implicit migration. Verify
rollback on every failure and lock-order/concurrent origin-key arbitration;
assert no nested independent writer connection. PUB-07B: one core semantic
transition returns immutable exact action effects, service projects them,
store persists them unchanged; no full snapshot inference, duplicate receipt
facts in delivery, or legacy runtime shape fallback. Compare canonical row
facts to receipt/public accepted projection; I-01/04/07/08/11/13/15/18/21/39/41/44.

**PUB-08 — Exact challenge opening (API-17).** After PUB-02/04/07, change
service/reconsider.py and existing challenge receipt/qualification owner;
return receipt selector/time, exact accepted challenge/target revision and
context, prior content/evidence through AuditConclusion, not current membership.
Paginate large target sets. Preserve challenge write atomicity/idempotence and
named disposition semantics. Test multiple targets, older version, replay
after subsequent correction/settlement, unavailable historical basis and
context recovery. Gate: reviewer can investigate dispute without reconstructing
prior statements or performing unrelated lookup.
Architecture gate: same core challenge transition, existing receipt writer and
PUB-02 audit projection; no second challenge store, evaluator, DTO or
historical reconstruction in adapter. Verify one transaction and immutable
exact target lookup under replay. I-04/08/11/15/18/39.

**PUB-09 — Public contract integration.** After PUB-02–08, regenerate the
single schema from canonical model; update docs/mcp.md, glossary, installer/
operator guidance where affected, AGENTS lifecycle fragment, skills/hooks and
native host tests. Replace retired references to whole UnderstandingRecorded
qualification/status/affected_revisions, raw snapshot/receipt, status member
inventory and member-relative public paths. Agent completion consumes all
pages and exact revision/obligation states; no false success from partial
results. Map actual tests to amended existing FA cases in
docs/functional-acceptance.md (no invented passing evidence or duplicate
matrix). Reconcile migration/versioned schema and public examples; no
compatibility aliases or fourth tool. Gate: strict schema/round-trip and
installed guidance agreement. Confirm no generated artefacts edited by hand,
no extra grammar, and all obsolete helpers/exports/call sites removed by
owning tasks; verify existing invariant matrix names actual tests, no new
parallel compliance checklist. I-02/03/04/18/23–25/28/34/39.

**PUB-10 — Full exact-candidate verification.** Run focused failure-before/
fix-after, complete unit/integration/acceptance, non-editable installed-MCP
journeys incl nested root and all public branches, native host delivery where
required, Ruff, Black, zero-error typing, plugin tests, distribution and
full CI per existing release procedure. Assert schema recursively and actual
wire/free text with distinctive private sentinels; preserve no-leak,
containment, curation, atomicity/CAS/replay, graph/support and existing field
remediation checks. Record sanitized exact-revision results, measured
ratchets only; no gate weakening. Run existing `scripts/typecheck.py` and
invariant/architecture guards, review changed annotations and dependency
edges; zero-error typing, no new suppressions or baseline increases. Verify
source ownership, canonical model/schema round-trip, no duplicate codec,
writer, registry, evaluator or dependency engine, and no shell-side semantic
logic. Existing architecture guard and invariant suites are extended at
their real owners, not replaced with string-matching-only assertions.
Independent review and release owner
authorization remain separate. No live adopter mutation/publication.

Sequence: PUB-01 → PUB-02 → PUB-03 → PUB-07 persistence/migration subtask
(schema 16/2, canonical receipt/index/selection tables and transaction ports)
→ PUB-04 → PUB-07 accepted outcome composition → PUB-05/PUB-06 → PUB-08
→ PUB-09 → PUB-10. PUB-06 uses PUB-07 receipt transaction and PUB-04 delivery;
PUB-08 uses PUB-02/04/07. Test each subtask before dependent integration. PUB-02 and PUB-03's pure
model/rule work and PUB-07A's affected persisted model/store changes form one
integrated code cutover before PUB-04: intermediate incompatible schemas are
not valid committed runtime states. No task may introduce temporary parallel
carriers or postpone removal of a superseded active path. The §3B order
supersedes earlier independent-task wording for this track.
PUB-02–10 remain OPEN pending executable acceptance evidence. PUB-01 is
owner-confirmed complete. The documented
contracts are design targets; the source baseline still contains the defects.

**Review closure trace (F01–F09).** F01: G7/F9/F11 and L1/L9 reconciled
(PUB-01/09); F02: P2 §4.1, P3 §2/FD-62, TD §17.1 (PUB-06/07);
F03: P2 ResultPage, FD-43/45/55–57, TD §§13–14 (PUB-04/07);
F04: P2 verification scope, FD-28, TD §11 (PUB-05);
F05: P2 StatusSubject, FD-28, TD §11 (PUB-05);
F06: P2 audit/support basis, FD-16/28, TD §§9.2/11 (PUB-02/08);
F07: P2 receipts, FD-3/37/43, TD §§12–14/19/21 (PUB-07);
F08: P2 §4.3, FD-20/22, TD §20.3 (PUB-03/04);
F09: P0–P4 canonical ownership and plan traceability, not a second authority
(PUB-01/09). Acceptance is the amended P3 §15 cases and PUB-10 evidence.
PUB-10 and S-FIELD-04 close the same release programme.

## 4. Execution sequence

Original delivery sequence (historical): S-DOC-01 → S-INIT-01 → S-INIT-02 → S-INIT-03 → S-PUBLIC-01 → S-PUBLIC-02 → S-VERIFY-01 → S-VERIFY-02 → S-VERIFY-03. Field amendment execution sequence: S-FIELD-01 → S-FIELD-02 → S-FIELD-03; S-FIELD-05–07 follow the existing owners and design, then S-FIELD-04 closes all gates. The PUB-01–10 sequence in §3B is the additional active public-boundary track;
S-FIELD-04 and release readiness depend on its closure as well. The tests at each task gate must pass before dependent work is accepted. Public boundary tasks follow §3B's ordered dependencies and integrated persisted-contract cutover; final installed acceptance is a single end-to-end gate. Reuse all existing owners; if a governing contradiction is discovered, stop at its owner and amend the design, not a downstream workaround.

## 5. Explicit non-scope

No replacement of the V3 resolver, route-support engine, repository store or installation store; the only active storage-format target for PUB is TD §14 (16/2), not a second storage owner or schema for setup convenience; no changes to the repository's canonical governance content; no LLM discovery or automatic semantic re-establishment; no new public MCP tool; no compatibility bridge for V1/V2 declaration grammar; no manual metadata-authoring alternative to the governed setup contract; no release publication or live adopter cutover. Any genuine additional architectural requirement must be raised against the governing layer before implementation.
