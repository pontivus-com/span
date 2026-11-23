# Span — Offline Initialization and Readiness Contract

Governing invariants: initialization is explicit, never implicit; readiness
is operational state, not semantic trust; hooks never interpret, record,
re-check, or rebuild.

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
8. Repository registration and Functional Pyramid participation are separate.
   A registered ready repository is UNCONFIGURED until explicitly EXCLUDED or
   ACTIVATED through the ordinary three-tool lifecycle. Runtime open never
   creates or changes participation.
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
