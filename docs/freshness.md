# Freshness and refresh (plan §9; Addendum B)

## Preflight (before anything is presented as CURRENT)

0. Coverage: recorded inventory-membership/seed fingerprints vs
   current; mismatch → covered items stale/unverifiable.
   Zero-result questions keep freshness through their discovery
   snapshot, never through empty claim counts.
1–4. Direct dependencies: load, fingerprint current evidence,
   compare, classify each item CURRENT/STALE/UNVERIFIABLE and persist
   non-current marks. Last-index timestamps are never trusted alone.
   Work-start synchronization establishes current repository state.
5. Semantic premises: bounded transitive walk of
   `SemanticBasis.input_refs` with cycle detection before a CURRENT
   answer. Changed/retired premises stale dependents; truncation
   yields UNVERIFIABLE with outstanding scope.

Stored disposition is history; effective disposition is computed on
every read from evidence, discovery, and premise state.

## Explicit refresh (`refresh`, always scoped)

Identify stale/unverifiable (direct + coverage) → reselect bounded
evidence (including newly added authorities and competing
declarations in scope) → reinterpret affected units → validate and
materialize atomically per unit → preserve failures as
stale/unverifiable → leave current items untouched.

## Reconciliation (I-37; Addendum B)

One successful unit applies atomically: writes, coverage records,
question coverages, conflict record, premise index, and exactly the
listed retirements — or nothing. Exact-question retirement removes
only unshared outputs of the bound question; shared outputs keep
their association. Explicit withdrawals retire even shared items but
reopen all referencing questions. Legacy-unassigned items are never
silently adopted or retired. Unknown retire ids fail the unit.
Retired history is preserved, never discarded. Latest coverage per
question scope wins so old rows never re-invalidate refreshed
conclusions.
