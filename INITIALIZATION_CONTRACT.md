# Span — Offline Initialization / Readiness Contract (plan Phase 0.7)

Governing invariants: I-27 (initialization is explicit, never implicit),
I-31 (readiness is operational state, not semantic trust), I-29/I-30
(hooks never interpret or refresh).

## Contract

1. Repository initialization is an explicit administrative lifecycle
   operation: `initialize_repository`. It runs in a dedicated
   initialization session, never inside a normal coding session.
2. A fresh Span checkout is **uninitialized by definition**: no semantic
   store artifact exists, and readiness is `UNINITIALIZED` (§4.8).
   Initialization performs structural-source verification/build where
   required, evidence inventory/fingerprinting, authority-seed
   registration, and semantic-store/schema initialization — and performs
   **no agent semantic interpretation** (plan Phase 0 exit, Phase 2.8:
   interpretation is executed by the invoking agent, never by Span).
3. Normal queries (`explain`, `impact`, `trace`,
   `authority`) and all automatic hooks (`SESSION_START`,
   `SOURCE_CHANGED`, `SESSION_STOP` → `status(..., mode=HOOK_FAST)`
   only) **must never start initialization implicitly**. An uninitialized
   repository returns `UNINITIALIZED` plus a setup notice, not bootstrap.
4. The full `RepositoryReadiness` enum and `HookStatusNotice` carrier are
   defined canonically in Phase 1.1 (§4.8). This contract fixes the
   behavior those types must exhibit; Phase 1 must adopt it verbatim.

## Phase 0 tests

- `tests/unit/test_initialization_contract.py` pins: fresh tree carries no
  initialized-store artifact; no existing code path invokes initialization
  from query/hook paths (structural scan — vacuously true in Phase 0,
  guards Phases 1–4); the contract document exists and states
  explicit-only bootstrap.
- Full readiness-state behavior (`READY`/`DEGRADED`/`UNAVAILABLE`,
  `HOOK_FAST` bounds) is implemented and tested in its owning phases
  (Phase 1 freshness preflight, Phase 2.8 bootstrap, Phase 4.9–4.10 hooks).
