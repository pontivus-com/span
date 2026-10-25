# Port contracts

## Structural source (§5.2)

`repository_state` · `resolve_subject` · `locations` · `edges` ·
`reach` · `search_symbols` · `file_outline` · `verify_files` ·
`describe_current` · `ensure_current`, over
`REFERENCES/IMPORTS/DEPENDS_ON/CALLS/DEFINES` in
`UPSTREAM/DOWNSTREAM/BOTH`. Every paginated read returns one
`StructuralResult[T]` envelope carrying repository state, explicit
truncation, redeemable `pg:` cursors, and `coverage` plus
`coverage_detail` for the structure behind the items. Coverage is a
property of the return type, not a per-operation convention.
Unsupported capabilities return typed `unsupported:true` with empty
items — never a faked empty result. Production provider: Graft
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
nothing), `mark_freshness`, repository-state record, schema version,
and the verification-record upsert/read on its `(subject, scope)`
natural key. SQLite implementation normalizes physically only.

Every table declares its fact kind in `STORE_FACT_DECLARATIONS`: an
Observation (content-addressed, no natural key), a State (natural key,
upsert), or a Handle (issued pointer). The declaration is checked
against `sqlite_master` in both directions, and a State's declared key
must be the table's primary key, so a new carrier cannot be added
without stating what kind of fact it holds.
