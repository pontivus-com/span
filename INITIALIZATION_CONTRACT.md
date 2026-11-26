# Span — Offline Initialization and Readiness Contract

> **Document role: derived administrative contract.** This artifact gives the
> installer/readiness tests and operators one concise statement of the
> initialization boundary. It is **not** a sixth Functional Pyramid layer and
> cannot create product authority.
>
> Binding lifecycle behavior comes from
> [Lifecycle contract](docs/lifecycle-contract.md), deterministic behavior from
> [Functional design](docs/functional-design.md), and installation/transition
> mechanisms from [Technical design](docs/technical-design.md). If this derived
> artifact conflicts with those owners, this file is the defect.

The derived invariants are: initialization is explicit, never implicit;
readiness is operational state, not semantic trust; hook execution remains
outside initialization and durable semantic/governance mutation (FD-58;
Technical Design §22).

## Contract

1. Repository initialization is the explicit administrative operation
   performed by the installer (`span-install`).
   It runs in a dedicated setup session, never inside ordinary question,
   record, or hook work.
2. A repository with no schema-15 lifecycle store is uninitialized.
   Initialization binds the canonical root, registers declared authority seeds
   and bindings, and creates the schema-15 repository store. Installer/setup
   also creates or verifies the separate installation Functional Pyramid store
   at installation schema 1.
   It performs no semantic interpretation and creates no understanding.
3. Ordinary lifecycle calls (`ask`, `record`, `reconsider`) never initialize a
   store. They must never start initialization implicitly. An `UNINITIALIZED`
   repository fails with the explicit setup action.
4. An older schema fails closed with the offline transition action. The
   runtime never migrates or rebuilds a store at open. Supported repository
   schemas 7–14 transition explicitly to schema 15; schema 14 is copied without
   semantic/governance reinterpretation and starts with zero curation
   dispositions.
5. `span-install --verify-only` is observational. It reports build, store
   schema, root binding, provider availability, and registration state; it
   never initializes, migrates, or invokes a semantic operation.
6. Automatic hooks deliver event-local lifecycle reminders. They never establish
   freshness, and a missed hook cannot make stale understanding current.
7. `READY` means the repository store, required installation capabilities and
   provider are operationally available. It is not semantic coverage,
   correctness, Functional Pyramid participation, or completeness.
8. Registration alone and Functional Pyramid participation remain distinct.
   Ordinary installation preserves existing participation. Explicit governed
   initialization composes installation and the existing participation writer
   according to lifecycle §7.1 and TD §17.2. Runtime open never initializes or
   changes participation. The governed user supplies only the classification
   and explicit initialization intent; generated inputs are Span-owned.
9. Installer authority ingress is repository-qualified:
   `--authority-seeds-file REPOSITORY_ID PATH` and
   `--authority-bindings-file REPOSITORY_ID PATH`. Files contain strict JSON
   lists of the canonical `EvidenceRef` and `AuthorityBinding` carriers.
   Omission preserves existing configuration, an explicit empty list clears it,
   and a non-empty list replaces it. Deterministic decoding, repository
   identity, and locator validation precede repository-state mutation.

## Tests

- `tests/unit/test_initialization_contract.py` pins explicit-only setup and
  the absence of initialization from ordinary reads.
- `tests/unit/test_administrative_readiness.py` pins observational installer
  verification and uninitialized/old-schema outcomes.
- `tests/unit/test_lifecycle_hooks.py` pins bounded, non-writing hooks.
