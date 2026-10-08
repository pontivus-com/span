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

Current suite: 217 tests green under `pytest` and `unittest`
(isolated venv install verified separately). Case → evidence:

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
| M publication boundary | provenance ledger, no proprietary material, GPL-3.0-only `LICENSE` at root |
| S-01 / S-02 | terminology authority; publication custody + violation |
| v0.6 paths | multi-unit chains, second-page retrieval, supersession, withdrawal, doc-only subjects |

Live-agent validation (2026-10-08, §21 #9): one end-to-end run with
an external LLM-connected agent (Claude via relay, ~$0.002, no
Span-owned provider code or credentials) — real `span_explain`
suspension → live judgments (purpose sentence, verbatim quote,
audit note) → deterministic transcription to typed candidates →
strict ingress + validation → materialized `EXPLAIN` answer. The
quote-backed invariant materialized `UNRESOLVED` with a
`MISSING_AUTHORITY` resolver (the evidence states no acceptance
status — correctly not invented); freshness `CURRENT`. Not a
committed test (public tests must not require external services,
MI-11 L); recorded here as validation evidence.
