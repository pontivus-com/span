# field-svc live session ledger (Addendum D adoption evidence)

Production-path session of 2026-10-08 against the real `span-mcp`
stdio server (one process per host session), a real graft-indexed
repository, and a file SQLite store reused across two server
sessions. The session agent formed its own judgments from evidence
read over the wire; implementer and agent coincide — independent
reviewer judgment against `repo/` was waived by owner decision
2026-10-09 (adoption ledger; explicitly unverified).

## Corpus

- `repo/`: target repository **as finally edited** (v2 state).
- `transcripts/`: verbatim MCP request/response JSON per round.
- `field-svc.sql`: SQLite `.iterdump` of the final store
  (`claims 4, retired_claims 1, question_coverages 10,
  coverage_dependencies 10, evidence_dependencies 3`); reload with
  `sqlite3 out.db < field-svc.sql`. No absolute paths inside.

## v1 → v2 source diff (the controlled edit)

- `README.md`: `Collects field readings.` →
  `Collects field readings and limits.`
- `src/collect.py` docstring: `Collect field readings from sensors.`
  → `Collect field readings and limits from sensors.`
- Everything else byte-identical (v1 bytes preserved inside
  `transcripts/pending1.json` evidence units).

## Round log (session 1, one server process)

| # | Tool | Continuation | Outcome |
|---|---|---|---|
| 1 | `status` (target null) | — | `READY`, zero claims (Milestone A) |
| 2 | `explain` baseline `src/collect.py` | `cont-1` | `PendingInterpretation` CQ-01 + `TaskBrief` in transit |
| 3 | `submit` audit (purpose claim, ANSWERED CQ-01, PENDING CQ-02–09) | `cont-1` → `cont-2` | accepted; CQ-02 pends |
| 4 | `submit` CQ-02 responsibility (`hold`-then-`send` order) | `cont-2` → `cont-3` | accepted; CQ-03 pends |
| 5 | `submit` CQ-03 `OPEN` (unit names no owner) | `cont-3` → `cont-4` | accepted, preserved |
| 6–9 | `submit` CQ-04–07 `OPEN`, CQ-08/09 `NOT_APPLICABLE` on examined evidence | `cont-4`…`cont-9` | accepted |
| 10 | (terminal) | — | `SemanticAnswer`: PURPOSE + RESPONSIBILITY, both `MISSING_AUTHORITY` (no governing source — correctly not invented) |

A second server process correctly rejected the stale `cont-1`
(`unavailable`); resume is by re-issuing the idempotent operation.

## Round log (session 2, new server process, same DB file)

| # | Tool | Outcome |
|---|---|---|
| 11 | `explain` `src/collect.py` | `SemanticAnswer` from coverage, both claims `CURRENT`, no suspension |
| 12 | `status` after the `collect.py` edit | exact stale scope: both claims `STALE` (both cited the moved bytes) |
| 13 | `refresh` (scoped, `stale_only`) | `PendingInterpretation` CQ-01 under persisted identity, new fingerprint |
| 14 | `submit` corrected purpose + reasserted responsibility | `SemanticAnswer` |
| 15 | `explain` readback | purpose corrected + `CURRENT`; superseded predecessor retained visibly `STALE` per retirement rules |

## Round log (session 3: host-side `drive()` expansion, same DB file)

| # | Tool | Outcome |
|---|---|---|
| 16 | `explain` `src/failures.py` (via `drive()`) | `PendingInterpretation` CQ-01; failures.py selected as evidence through the structural reference (no `authority_seeds` on the MCP surface — unknown tool fields fail closed, as designed) |
| 17 | `submit` purpose "Dead-letter failed readings" via `drive()` | `SemanticAnswer`, 1 submission, 0 reissues, cost measured |
| 18 | `explain` `src/failures.py` readback | `SemanticAnswer`, PURPOSE `CURRENT`, no suspension — expanded knowledge persisted and reused |

## Reviewer steps (independent)

1. Reload the dump; confirm 10 coverages, 4 live claims + 1 retired
   (failures PURPOSE added in session 3), evidence deps pointing at
   v1/v2 fingerprints.
2. For each `claims` row, judge the value against `repo/` bytes at
   the cited fingerprint: does the evidence actually support it?
3. Confirm the v1 purpose text appears nowhere as current, the v2
   text appears as `CURRENT`, and the stale predecessor is labeled,
   not deleted.
4. Record verdict + effort (~16 tool calls, 2 sessions) in the
   verification record.

## Host-path verification (2026-10-08, same session)

- opencode plugin event mapping verified live against a fixture
  store: clean session/start/idle silent; stale+pending session
  prints exception lines; unchanged edit silent; moved edit names
  the dependent id. Required one product fix: `span-hooks.js`
  mixed `require()` with `export` and could not load under node
  module resolution — converted to `import` (behavior unchanged).
- Codex `hooks.json` wiring remains installer-tested (dry); no live
  codex CLI available in this environment.
