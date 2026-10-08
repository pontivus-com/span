# Demand-driven indexing (plan §8)

No whole-repository semantic crawl, ever. Indexing is demand-driven,
subject/evidence bounded, incremental, and reusable through persisted
claims plus evidence fingerprints.

1. Register: identity, repository state, structural source,
   evidence-inventory index, explicit authority seeds. No
   interpretation — readiness, not knowledge.
2. Query: resolve target → load current state → find missing/stale
   kinds for the intent → select bounded evidence → interpretation
   task → validate/materialize → persist claim→evidence dependencies
   **and** discovery-coverage dependencies (inventory-membership +
   seed fingerprints) → compose answer.
3. One interpretation unit: one primary subject + explicitly related
   subjects (≤ `max_subjects`), one question slice, bounded evidence
   units/bytes, bounded candidate counts.
4. Broad queries expand one bounded frontier at a time and suspend
   per missing unit; chains return fresh continuations, never dumps.
5. Unchanged evidence with unchanged contract version is not
   reinterpreted. Changed direct dependencies stale only affected
   items. Gained/lost inventory members or moved seeds stale covered
   scopes (new authorities can't hide behind unchanged bytes);
   known-source content changes stay per-item (unrelated changes never
   invalidate unrelated assertions).

No watcher/daemon/queue. No benchmark harness (bounds + acceptance
sufficiency only).
