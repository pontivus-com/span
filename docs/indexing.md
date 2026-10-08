# Demand-driven indexing (plan §8; Addendum B)

No whole-repository semantic crawl, ever. Indexing is demand-driven,
subject/evidence bounded, incremental, and reusable through persisted
claims plus evidence fingerprints and question-scoped coverage.

1. Register: identity, repository state, structural source,
   evidence-inventory index, explicit authority seeds. No
   interpretation — readiness, not knowledge.
2. Query: resolve target → load current state → find missing/stale
   kinds for the intent → select bounded evidence → interpretation
   task (with immutable `SemanticQuestionScope` and SA obligations) →
   validate/materialize → persist claim→evidence dependencies,
   discovery-coverage dependencies (inventory-membership + seed
   fingerprints), persisted question coverages, and premise reverse
   index → compose answer with read-only coverage projection.
3. One interpretation unit: one primary subject + explicitly related
   subjects (≤ `max_subjects`), one precise question
   (`scope_root, subject, question_class, question_slice`), bounded
   evidence units/bytes, bounded candidate counts.
4. Broad queries expand one bounded frontier at a time and suspend
   per missing unit; chains return fresh continuations, never dumps.
   Baseline worklists resume PENDING questions deterministically.
5. Unchanged evidence with unchanged contract version is not
   reinterpreted. Changed direct dependencies stale only affected
   items. Gained/lost inventory members or moved seeds stale covered
   scopes (new authorities can't hide behind unchanged bytes);
   known-source content changes stay per-item (unrelated changes never
   invalidate unrelated assertions). Changed semantic premises stale
   their dependents until reassessed; truncation yields UNVERIFIABLE.

No watcher/daemon/queue. No benchmark harness (bounds + acceptance
sufficiency only).
