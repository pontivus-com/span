# Fixtures and acceptance (plan Phase 5, MI-11)

Every case is judged on correctness, sufficiency, evidence integrity,
uncertainty integrity, freshness integrity, boundedness, and reuse
integrity — against generic/synthetic fixtures shipped here, never
proprietary material.

- A identity/purpose · B ownership/custody (incl. retired-owner-owns-
  nothing, structural use ≠ ownership) · C boundary/representation
  (no duplicate representations, no fallback writes) · D authority
  conflict (observed vs declared, declared precedence only) ·
  E verification (candidate vs current pass/fail, never presented as
  passed) · F lifecycle (create→terminal/fail, TTL/reaper, persistence
  points) · G non-local impact (structural possibility vs established
  impact) · H ambiguity (candidates, no arbitrary pick) ·
  I missing authority (unresolved + resolver, no invention) ·
  J staleness/partial refresh (only affected claims; coverage
  invalidation by new evidence; withdrawal with history) ·
  K portability (held-out repo, real Graft, no repo-specific code) ·
  L isolation (build/test/serve with no private access) ·
  M publication boundary (no proprietary artifacts; license gate).
- S-01 terminology/register authority (concept + surfaces + binding +
  conflict, no invented resolution). S-02 publication/disposition
  custody (terminal lifecycle, copy-only downstream, candidate vs
  current verification, recomputation violation).
- v0.6 paths: multi-unit chaining, second-page retrieval,
  superseding evidence, claim withdrawal, documentation-only subjects.

Lifecycle path: orient → impact → trace/authority → modify → status
(stale) → refresh → status (current). Hook/bootstrap path:
UNINITIALIZED setup notice → dedicated init → READY → HOOK_FAST
session → explicit impact → edit → hook classifies only →
explicit refresh → closure. Negatives: irrelevant edits silent, no
implicit init/interpret/rebuild/refresh, no whole-repo indexing.

## MI-11 execution mapping (G-02)

Current suite: 771 passed, 335 subtests passed under `pytest`; installed
lane: 4 passed (isolated venv install verified separately). Case → evidence:

| Case | Tests |
|---|---|
| A identity/purpose | vertical slice explain assertions |
| B ownership/custody | owner-vs-consumer, retired-owner-owns-nothing |
| C boundary/representation | S-01 surfaces, prohibitions |
| D authority conflict | S-01/S-02 conflicts, precedence, no silent resolution |
| E verification | currency distinction, candidate-never-passed |
| F lifecycle | terminal/TTL/persistence assertions |
| G non-local impact | possibility vs established, kind gating, proposal typing |
| H ambiguity | multi-candidate, no arbitrary pick |
| I missing authority | unresolved + deterministic resolvers |
| J staleness/refresh | partial staleness, coverage invalidation, withdrawal + history |
| K portability | hermetic held-out graft run, no repo-specific code |
| L isolation | import/path/artifact gate, venv install + suite |
| M publication boundary | provenance ledger, no proprietary material, Apache-2.0 `LICENSE` at root |
| S-01 / S-02 | terminology authority; publication custody + violation |
| v0.6 paths | multi-unit chains, second-page retrieval, supersession, withdrawal, doc-only subjects |
| Addendum B A–L | `tests/acceptance/test_addendum_b_acceptance.py` (binding B.11: First-contact held-out baseline + restart, question-local vs baseline, negative/empty reopen, shared replace/withdraw + fanout + overflow-defer, premise cascade, cycle/truncation, reconcile/failure, authority conflict, paging/restart, benign change, schema cutover rejection, isolation, cited-but-wrong + omitted-participant oracle must-fails, sibling-question isolation) plus `tests/unit/test_addendum_b.py` (seeding, stable IDs, shared storage, premise walk, paging grammar, effective disposition, schema-7 opening, coverage invariant) |
| Addendum C (cutover + campaign mechanics) | `tests/acceptance/test_addendum_c_acceptance.py` (C-N explicit-disposition cutover: claims-only persists PENDING and never completes; explicit ANSWERED derives refs and reads back current; explicit ANSWERED with zero material rejects atomically with nothing written; the store refuses empty ANSWERED rows; incomplete resubmission retires nothing. C-O single-writer serialization with parallel analysis and stable IDs. C-M seeded scope restart-retrievable. C-P/C-06 mechanical limits: byte-valid-but-wrong passes validation, pinning oracle ownership. C-Q withdraw-plus-replace recovery without rollback machinery. C-S document subject registration. C-T explicit bound truncation) |
| Addendum D establishment + expansion (adopted by owner waiver 2026-10-09; independent reviewer items waived — see adoption ledger) | `tests/acceptance/test_addendum_d_acceptance.py` on held-out `ledger-svc`: baseline audit with readback + reuse (D-ACCEPT-01); closeout expansion to an unknown consumer with no silent broadening (D-ACCEPT-04). Full D-ACCEPT-01–07 bindings in ACCEPT-D-01. |
| Addendum E corrective boundary (historical; structural currency superseded by Addendum M) | E-01/E-02: Span consumes an existing machine-readable Graft index, never runs `graft build`, never generates Graft Markdown, and writes only the installer-managed lifecycle block in target `AGENTS.md`; no other target artifacts are written. Missing wiring fails closed. |
| Addendum E target lifecycle | E-03/E-04/E-13: an exact user boundary is carried in every target task separately from its structural anchor; the host records canonical area subjects, typed target-inventory assignment/exclusion/unresolved mapping, semantic question coverage, and cross-area obligations. Question-level `NOT_APPLICABLE` is not target exclusion. File enumeration is not semantic completion. |
| Addendum E uniform semantic quality | E-06/E-07: initialization, ordinary questions, refresh, closeout, and expansion use the same compact quality card and fresh readback; status distinguishes persisted semantic coverage from readiness and pending work. |
| Addendum E runtime closure (historical; current surface per Addendum M) | E-05/E-09/E-10: all twelve MCP operations, source, installed runtime, receipt, hosts, skills, hooks, and acceptance evidence are synchronized. Full E §6 checklist governs: fail-closed missing index with no `graft/` or Markdown created; no `graft build` from provisioning, startup, MCP, or hooks; valid wiring consumed without cards; exact boundary carried separately from anchor; skills state scope/granularity/quality per E; twelve ops dispatchable (`locate`/`neighbors` per Addendum F); submissions persist and advance to truthful final status; fresh `status`/`explain` separates persisted coverage from new pending work; §4A matrix exercised preflight through fresh-session closeout with a disposition per material area; runbook followable — see `docs/onboarding-runbook.md`; no graft server registered anywhere, with the structural target-artifact snapshot proving only the data store changed apart from the managed `AGENTS.md` guidance block; receipt and installed files match source revision. |
| Addendum M runtime implementation and host cold-start closure | M-01–M-22: eleven public operations; `reissue_interpretation` removed; one repository locator; minimal ordinary and batch-complete mapping templates; opaque page tokens/continuations with request-bound service-answer tokens; exactly one `mcp.servers.span` OpenCode V2 registration; provider-owned structural currency only on setup/explicit refresh; synchronized managed guidance; raw external client with zero `span.*` imports covering the public matrix, including untouched PENDING, semantic-rejection recovery, unresolved mapping, one-locator setup, multi-member mapping with the service-owned CQ-01 seed, opaque pagination/cross-request rejection, OpenCode V2 output, and installed managed guidance. Host-start registration is non-provisioning: `span-mcp --repo` registers repository identity and serves the full roster with no provider build, semantic initialization, or target artifact, and explicit `initialize_repository` owns the build. Supported-host fresh-session smoke passes on OpenCode and Codex with the default MCP startup timeout and no host-specific override. OpenCode support is bounded: the `mcp.servers.span` connection and eleven-tool roster are supported and verified, while exposing Span tools to a given OpenCode model is host-dependent and is not guaranteed by Span. Current suite: 771 passed, 335 subtests passed; installed lane: 4 passed; external matrix EC-01–EC-31 all pass. EC-31 is the permanent black-box fresh-process authority gate: initialize once with a seed, terminate, start a fresh `span-mcp` with no `initialize_repository`, ask a previously unestablished question, and require the returned `PendingInterpretation` brief to carry the restored seed. |
| Addendum F single MCP | F-1–F-7: Span serves read-only structural navigation (`locate`, `neighbors`) with two-tier freshness and version-bound pagination; no separate structural MCP registration is supported or created; E-14 scan deleted; preflight is index-presence plus census. Acceptance: `tests/unit/test_structural_navigation.py` (carriers, tokens, memory provider, service ops, envelope mapping) and `tests/acceptance/test_addendum_f_acceptance.py` (stale exclusion, new-caller UNVERIFIED, empty-stale-search, reload without restart, rebuild-between-pages rejection, high-degree recovery, non-indexed members, git-backed VERIFIED coverage). |

Addendum B adopted 2026-10-08: v0.6 contracts synchronized (question identity,
exchange, validation, store v3, query/change, transport, guides);
`READY` is operational only; `ANSWERED` is recorded analysis, never
reviewer truth; no `ACCEPTED` without source declaration. Full suite
green including executable B.11 challenges (each B.12 challenge is a
test, not documentation).

Live-agent validation (2026-10-08, §21 #9): one end-to-end run with
an external LLM-connected agent (Claude via relay, ~$0.002, no
Span-owned provider code or credentials) — real `explain`
suspension → live judgments (purpose sentence, verbatim quote,
audit note) → deterministic transcription to typed candidates →
strict ingress + validation → materialized `EXPLAIN` answer. The
quote-backed invariant materialized `UNRESOLVED` with a
`MISSING_AUTHORITY` resolver (the evidence states no acceptance
status — correctly not invented); freshness `CURRENT`. Not a
committed test (public tests must not require external services,
MI-11 L); recorded here as validation evidence.

Live production-path session, Addendum D (2026-10-08): a full
onboard → reuse → maintenance cycle executed against the real
`span-mcp` stdio server (one process per host session), a real
on-disk repository (`field-svc`: README/OWNERSHIP/CONTRACT plus a
four-file Python system under a real graft index), and a real SQLite
store file persisting across two server sessions — with the session
agent forming its own judgments from evidence read over the wire:

- orientation via `propose_territories()` (one territory, four file
  entries) selecting the `src/collect.py` root; baseline `explain`
  suspended CQ-01 with the `TaskBrief` (C-04 aspects, scope
  boundaries) attached in transit;
- 9 wire submissions accepted (purpose + responsibility claims from
  unit evidence, no invented authority — both materialized
  `UNRESOLVED` with `MISSING_AUTHORITY`; CQ_03 left `OPEN` with a
  requirement where the unit named no owner; CQ_08/CQ_09 completed
  `NOT_APPLICABLE` on examined evidence);
- new server process, same DB: `explain` answered from coverage with
  both claims `CURRENT` and zero re-investigation;
- controlled edit of the cited evidence → `status` showed the exact
  stale scope → scoped `refresh` suspended the stale question under
  its persisted identity → corrected resubmission verified `CURRENT`
  on readback, superseded predecessor retained visibly `STALE` per
  retirement rules (not silently deleted).

Observed mechanics worth recording: continuations are per-server-
process (a second process correctly rejects the old token as
unavailable — resume by re-issuing the idempotent operation);
per-process servers are a harness artifact, deployment holds one
server per host session. The host-side `drive()` expansion round
exercised the Python-helper path only, not OpenCode/Codex host
integration. Effort: ~16 MCP tool calls across two
sessions. Independence caveat: implementer and agent coincide in
this run — the transcript and store above are presented for
independent reviewer judgment against the field-svc files, which
was waived by owner decision 2026-10-09 (adoption ledger; explicitly
unverified, not claimed as passed — material retained for future
reviewer use).

## Independent reviewer runs (Addendum D §13 R-01, D-ACCEPT-01–07)

Committed tests prove mechanics deterministically; substantive
semantic quality with a real invoking agent is reviewer-executed —
public tests must not require external services (MI-11 L). Procedure:

1. The reviewer authors undisclosed truth with `_ledger_variant()`
   (`tests/acceptance/test_addendum_d_acceptance.py`: new repo id,
   purpose, owner and participant names the implementer has not
   seen; same structural shape). Truth stays with the reviewer.
2. The invoking agent (not the implementer) investigates the fresh
   store through the canonical exchange (explain → submit until
   answers), then the reviewer asks predeclared representative
   questions in a new interaction.
3. The reviewer judges every answer against the undisclosed truth:
   correct content, qualified uncertainty, evidence that actually
   supports the assertion, no silent broadening. Any substantive
   miss blocks adoption regardless of suite state.
4. Effort (rounds, submissions, wall-clock) is recorded
   descriptively; no thresholds.

`UndisclosedInstanceTest` proves the machinery accepts
reviewer-controlled truth (mill-svc establishes and reads back
independently of ledger-svc); it is not itself the independent
evaluation.
