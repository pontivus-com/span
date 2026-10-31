# Span — Offline Initialization and Readiness Contract

Governing invariants: initialization is explicit, never implicit; readiness
is operational state, not semantic trust; hooks never interpret, record,
reassess, or rebuild.

## Contract

1. Repository initialization is the explicit administrative operation
   `initialize_repository`. It runs in a dedicated setup session, never inside
   ordinary question, record, or hook work.
2. A repository with no schema-10 store is uninitialized. Initialization binds
   the canonical root, registers declared authority seeds and bindings, and
   creates the schema-10 store. It performs no semantic interpretation and
   creates no understanding.
3. Ordinary lifecycle calls (`understand_question`, `understand_retrieve`,
   `evidence_start`, `evidence_extend`, `record_*`, `reassess`,
   `verification_support`, `locate`, `neighbors`) never initialize a store.
   They must never start initialization implicitly. An `UNINITIALIZED`
   repository fails with the explicit setup action.
4. An older schema fails closed with the offline transition action. The
   runtime never migrates or rebuilds a store at open.
5. `span-install --verify-only` is observational. It reports build, store
   schema, root binding, provider availability, and registration state; it
   never initializes, migrates, or invokes a semantic operation.
6. Automatic hooks are optional, event-local notices. They never establish
   freshness, and a missed hook cannot make stale understanding current.
7. `READY` means the store and provider are operationally available. It is
   not semantic coverage, correctness, or completeness.

## Tests

- `tests/unit/test_initialization_contract.py` pins explicit-only setup and
  the absence of initialization from ordinary reads.
- `tests/unit/test_administrative_readiness.py` pins observational installer
  verification and uninitialized/old-schema outcomes.
- `tests/unit/test_lifecycle_hooks.py` pins bounded, non-writing hooks.
