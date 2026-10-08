# Freshness and refresh (plan §9)

## Preflight (before anything is presented as CURRENT)

0. Coverage: recorded inventory-membership/seed fingerprints vs
   current; mismatch → covered items stale/unverifiable.
1–4. Direct dependencies: load, fingerprint current evidence,
   compare, classify each item CURRENT/STALE/UNVERIFIABLE and persist
   non-current marks. Last-index timestamps are never trusted alone.
   Work-start synchronization establishes current repository state.

## Explicit refresh (`span_refresh`, always scoped)

Identify stale/unverifiable (direct + coverage) → reselect bounded
evidence (including newly added authorities and competing
declarations in scope) → reinterpret affected units → validate and
materialize atomically per unit → preserve failures as
stale/unverifiable → leave current items untouched.

## Reconciliation (I-37)

One successful unit applies atomically: writes, coverage record,
conflict record, and exactly the listed retirements — or nothing.
An absent prior assertion inside declared-complete coverage is
withdrawal; outside it, bounded-evidence truncation (prior state
preserved). Unknown retire ids fail the unit. Retired history is
preserved, never discarded. Latest coverage per scope wins so old
rows never re-invalidate refreshed conclusions.
