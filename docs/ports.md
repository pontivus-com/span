# Port contracts (plan §5)

## Structural source (§5.2)

`repository_state` · `resolve_subject` · `locations` · `edges` ·
`reach`, over `REFERENCES/IMPORTS/DEPENDS_ON/CALLS/DEFINES` in
`UPSTREAM/DOWNSTREAM/BOTH`. Every page carries repository state,
explicit truncation, and redeemable `pg:` cursors; unsupported
capabilities return typed `unsupported:true` with empty items — never
a faked empty result. Production provider: Graft
(`shell/structural/graft.py`, MIT, closed node-kind/relation mapping
with explicit errors for unknown vocabulary). Deterministic
in-memory source for tests.

## Evidence (§5.3)

`inventory_evidence` (fingerprints, paged) · `list_inventory_entries`
(membership-only `(locator, evidence_id)` listing plus targeted
fingerprints — one metadata walk, no per-page re-hash) ·
`select_evidence`
(relevance only: links, structural context, authority seeds,
identity/term anchors, bounded) · `read_evidence` (bounded units).
Selection never confers authority. Production: filesystem source
(skips `.git/`, `graft/`, binaries; path-escape rejected); fixture
source for tests.

## Store (§5.5)

Canonical domain types directly, no DTO layer. Loads (subjects,
by-refs, claims, relationships — all paged), evidence/coverage/
conflict dependency loads, atomic `write_index_batch` (write +
coverage + conflict record + exactly the listed retirements, or
nothing), `mark_freshness`, repository-state record, schema version.
SQLite implementation normalizes physically only.
