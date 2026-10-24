"""Span service repository lifecycle (plan §11.1, v0.6 §14 Amendment A-01).

Explicit initialization plus the deterministic uninitialized-repository
answer (I-27). Imports answer constructors from ``answers.py`` and
request contracts from ``requests.py``; the edge is acyclic.
Verbatim from ``span.service_operations``; only the module path
changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.service.answers import _answer_id, _bound_info
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.requests import (
    SemanticInitializeRepositoryRequest,
    SemanticInitializeRepositoryResult,
)

__all__ = [
    "_setup_requirement",
    "_is_initialized",
    "_uninitialized_answer",
    "initialize_repository",
]


def _setup_requirement(repository_id: str) -> m.ResolutionRequirement:
    """Deterministic resolver for uninitialized repositories (I-27)."""
    return m.ResolutionRequirement(
        kind=m.ResolutionKind.MISSING_EVIDENCE,
        subject_or_claim=None,
        description=(
            f"repository {repository_id} is not initialized; run "
            f"initialize_repository in a dedicated setup session"
        ),
        supporting_context=(),
    )


def _is_initialized(repository_id: str, *, store: SemanticStore) -> bool:
    """Whether explicit initialization recorded this repository.

    Read-only: checking never initializes (I-27).
    """
    return store.load_repository_state(repository_id) is not None


def _uninitialized_answer(
    intent: m.SemanticIntent,
    repository_id: str,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.SemanticAnswer:
    """Setup notice for uninitialized repositories (plan §11.1, I-27).

    Never initializes implicitly; directs to a dedicated
    initialization session through a deterministic requirement.
    """
    content: m.SemanticContent
    if intent is m.SemanticIntent.STATUS:
        content = m.StatusContent(readiness=m.RepositoryReadiness.UNINITIALIZED)
    elif intent is m.SemanticIntent.EXPLAIN:
        content = m.ExplainContent()
    elif intent is m.SemanticIntent.TRACE:
        content = m.TraceContent()
    elif intent is m.SemanticIntent.IMPACT:
        content = m.ImpactContent()
    else:
        content = m.AuthorityContent()
    return m.SemanticAnswer(
        answer_id=_answer_id("uninit", repository_id, intent.value),
        intent=intent,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=(),
        resolution_requirements=(_setup_requirement(repository_id),),
        bound_info=_bound_info(bounds, 0, False, None),
        state_explanation=("returned assertions: none",),
    )


def initialize_repository(
    request: SemanticInitializeRepositoryRequest,
    *,
    repository_id: str,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds | None = None,
) -> SemanticInitializeRepositoryResult:
    """Explicit offline bootstrap lifecycle (plan §11.1).

    Assigns identity (caller-held, derived at source construction),
    establishes current repository state, verifies the structural
    source, builds the evidence inventory/fingerprint index, resolves
    the repository's configured authority seeds, and persists state and
    seeds in one atomic row. Seed semantics: omitted (``None``)
    preserves already configured seeds, an explicit empty tuple clears
    them, and a non-empty tuple replaces them. Performs NO agent
    semantic interpretation: there is no interpretation input by
    construction.
    """
    if not request.repository_locator:
        raise ValueError("repository_locator must be non-empty")
    policy_bounds = bounds or DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds
    effective_seeds = (
        store.load_repository_authority_seeds(repository_id)
        if request.authority_seeds is None
        else request.authority_seeds
    )
    state = structural.repository_state(repository_id)
    store.record_repository_initialization(state, effective_seeds)
    inventory = evidence.inventory_evidence(
        repository_id,
        m.EvidenceScope(paths=(), evidence_refs=()),
        policy_bounds,
    )
    warnings: list[str] = []
    if inventory.bound_info.truncated:
        warnings.append(
            "evidence inventory truncated by maximum bounds; "
            "remaining sources discovered on demand"
        )
    if state.dirty:
        warnings.append("working tree dirty; fingerprints track actual content read")
    version = store.schema_version()
    # §4.8/I-31: readiness is operational — whether the repository can
    # service semantic operations — never inventory completeness.
    # Partial inventory is boundedness (§8.4), carried in
    # evidence_inventory_status and warnings, and the HOOK_FAST path
    # likewise reports READY once initialized (plan Q34: readiness
    # must not be confused with freshness/boundedness).
    readiness = m.RepositoryReadiness.READY
    return SemanticInitializeRepositoryResult(
        repository_id=repository_id,
        readiness=readiness,
        structural_source_status="ready",
        evidence_inventory_status=(
            f"ready:{inventory.bound_info.returned_results}items"
            if not inventory.bound_info.truncated
            else f"degraded:truncated-at-{inventory.bound_info.returned_results}"
        ),
        semantic_store_status=f"ready:schema-{version.value}",
        warnings=tuple(warnings),
        bound_info=inventory.bound_info,
    )
