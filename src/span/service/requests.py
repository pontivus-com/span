"""Span service request contracts (plan §11.10, v0.6 §14 Amendment A-01).

Frozen dataclasses for strict typed ingress (I-02). Canonical
carriers only — all shapes compose ``core.model`` types.
Verbatim from ``span.service_operations``; only the module path
changed.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.ports.structural import StructuralDirection

__all__ = [
    "ChangeKind",
    "ProposedChange",
    "SemanticExplainRequest",
    "SemanticImpactRequest",
    "SemanticTraceRequest",
    "SemanticAuthorityRequest",
    "SemanticStatusRequest",
    "SemanticRefreshRequest",
    "SemanticInitializeTargetRequest",
    "SemanticSubmitInterpretationRequest",
    "SemanticReissueInterpretationRequest",
    "SemanticInitializeRepositoryRequest",
    "SemanticInitializeRepositoryResult",
    "AuthorityTargetError",
    "RefreshScopeError",
    "StatusTargetError",
    "SemanticStructuralLocateRequest",
    "SemanticStructuralNeighborsRequest",
]


@_dataclass(frozen=True)
class SemanticStructuralLocateRequest:
    """Structural locate contract (Addendum F §4.1)."""

    repository_id: str
    mode: m.StructuralLocateMode
    bounds: m.QueryBounds
    query: str | None = None
    match: m.StructuralLocateMatch = m.StructuralLocateMatch.EXACT
    target: m.EvidenceScope | None = None
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticStructuralNeighborsRequest:
    """Structural neighbors contract (Addendum F §4.2)."""

    repository_id: str
    target: m.SubjectSelector
    direction: StructuralDirection
    bounds: m.QueryBounds
    edge_kinds: tuple[m.StructuralEdgeKind, ...] = ()
    max_depth: int = 1
    page_token: str | None = None

#: Canonical change vocabulary lives in the core model (single carrier);
#: re-exported here for service consumers (plan §11.10, I-04).
ChangeKind = m.ChangeKind
ProposedChange = m.ProposedChange


@_dataclass(frozen=True)
class SemanticExplainRequest:
    repository_id: str
    target: m.SubjectSelector
    bounds: m.QueryBounds
    page_token: str | None = None
    establish_baseline: bool = False


@_dataclass(frozen=True)
class SemanticImpactRequest:
    repository_id: str
    target: m.SubjectSelector
    change_kind: ChangeKind
    change_description: str | None
    bounds: m.QueryBounds
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = ()
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticTraceRequest:
    repository_id: str
    target: m.SubjectSelector
    direction: StructuralDirection
    relationship_filter: tuple[m.RelationshipKind, ...] | None
    boundary_only: bool
    bounds: m.QueryBounds
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticAuthorityRequest:
    repository_id: str
    target: m.SubjectSelector | m.ClaimRef
    bounds: m.QueryBounds
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticStatusRequest:
    repository_id: str
    target: (
        m.SubjectSelector
        | m.ClaimRef
        | m.RelationshipRef
        | m.EvidenceScope
        | m.TargetId
        | None
    )
    bounds: m.QueryBounds
    mode: m.StatusMode = m.StatusMode.NORMAL
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticRefreshRequest:
    repository_id: str
    target: m.SubjectSelector | m.EvidenceScope | None
    bounds: m.QueryBounds
    stale_only: bool = True
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticInitializeTargetRequest:
    """Start host-owned semantic establishment for an exact target."""

    repository_id: str
    target: m.EvidenceScope
    objective: str
    bounds: m.QueryBounds


@_dataclass(frozen=True)
class SemanticSubmitInterpretationRequest:
    continuation: str
    result: m.SemanticInterpretationResult


@_dataclass(frozen=True)
class SemanticReissueInterpretationRequest:
    continuation: str


@_dataclass(frozen=True)
class SemanticInitializeRepositoryRequest:
    repository_locator: str
    structural_provider_config: str
    authority_seeds: tuple[m.EvidenceRef, ...] = ()


@_dataclass(frozen=True)
class SemanticInitializeRepositoryResult:
    repository_id: str
    readiness: m.RepositoryReadiness
    structural_source_status: str
    evidence_inventory_status: str
    semantic_store_status: str
    warnings: tuple[str, ...]
    bound_info: m.BoundInfo


class AuthorityTargetError(ValueError):
    """ClaimRef-target authority requires the Phase 3 subject-scoped
    claim lookup; Phase 1 serves selector targets."""


class RefreshScopeError(ValueError):
    """Repo-wide refresh (target None) requires indexed-subject
    enumeration, which arrives with the Phase 3 query surface."""


class StatusTargetError(ValueError):
    """Claim/relationship/answer-ref targets require indexed-identity
    lookup, which v0.5 does not provide: answers are never persisted as
    second authority (§11.10), and the store port has no by-id load.
    Status serves selector, evidence-scope, and None targets."""
