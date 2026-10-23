# Demand-driven indexing

No unrequested whole-repository structural or semantic-interpretation crawl.
When the user supplies an exact directory or repository target, the host may
partition and process that complete boundary; the campaign remains
demand-driven per material area. Indexing is subject/evidence bounded,
incremental, and reusable
through persisted claims plus evidence fingerprints and question-scoped
coverage. Normal repository-level `status(target=None)` may report a
bounded inventory derived from that persisted coverage; it is a read-only
projection of the semantic frontier, not a new crawl or completeness claim.

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

The Point 4 report must distinguish covered/current, incomplete
(`PENDING`/`OPEN`), stale/unverifiable, and unassessed persisted semantic
items, and must disclose page/truncation/outstanding scope. Missing items
outside the returned frontier remain unknown, not silently current or
silently absent.

## Scoped coverage dependency

`CoverageDependency` carries `discovery_scope` (the exact bounded search
universe) alongside `scope_subjects`, `inventory_fingerprint`, and
`seed_fingerprints`. Rows sharing a scope share one membership walk. An
empty scope enumerates the repository inventory for initialization and
inventory operations; persisted task coverage always carries a non-empty
scope.
