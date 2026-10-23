"""Span canonical service coordination.

Coordinates ports/core. Owns no semantic rules. Package surface for
the service boundary: bounds policy, frozen request contracts, and the
eleven public operations plus their query helpers.

Internal service modules import each other by defining-module path
(``span.service.<module>``), never through this surface. External
consumers (shell, integrations, tests) import public names from here.

Every operation lives in its canonical module; the former
``service_operations`` monolith is deleted.
"""

from span.core.validation import (
    InterpretationUnitRejected as InterpretationUnitRejected,
)
from span.service.bounds import (
    DEFAULT_SERVICE_BOUNDS_POLICY,
    BoundsRejectedError,
    resolve_bounds,
)
from span.service.discovery import discover_evidence
from span.service.exchange import (
    submit_interpretation,
)
from span.service.freshness import (
    coverage_check,
    preflight,
)
from span.service.interpretation import prepare_interpretation_task
from span.service.operations.authority import authority
from span.service.operations.explain import explain
from span.service.operations.impact import impact
from span.service.operations.initialize_target import initialize_target
from span.service.operations.locate import locate
from span.service.operations.neighbors import neighbors
from span.service.operations.refresh import refresh
from span.service.operations.status import status
from span.service.operations.trace import trace
from span.service.questions import (
    effective_question_view,
    question_coverage_check,
)
from span.service.repository import initialize_repository
from span.service.requests import (
    AuthorityTargetError,
    ChangeKind,
    ProposedChange,
    RefreshScopeError,
    SemanticAuthorityRequest,
    SemanticExplainRequest,
    SemanticImpactRequest,
    SemanticInitializeRepositoryRequest,
    SemanticInitializeRepositoryResult,
    SemanticInitializeTargetRequest,
    SemanticRefreshRequest,
    SemanticStatusRequest,
    SemanticStructuralLocateRequest,
    SemanticStructuralNeighborsRequest,
    SemanticSubmitInterpretationRequest,
    SemanticTraceRequest,
    StatusTargetError,
)

__all__ = [
    "DEFAULT_SERVICE_BOUNDS_POLICY",
    "BoundsRejectedError",
    "resolve_bounds",
    "ChangeKind",
    "ProposedChange",
    "SemanticExplainRequest",
    "SemanticImpactRequest",
    "SemanticTraceRequest",
    "SemanticAuthorityRequest",
    "SemanticStatusRequest",
    "SemanticRefreshRequest",
    "SemanticSubmitInterpretationRequest",
    "SemanticStructuralLocateRequest",
    "SemanticStructuralNeighborsRequest",
    "SemanticInitializeRepositoryRequest",
    "SemanticInitializeRepositoryResult",
    "SemanticInitializeTargetRequest",
    "AuthorityTargetError",
    "RefreshScopeError",
    "StatusTargetError",
    "InterpretationUnitRejected",
    "preflight",
    "coverage_check",
    "question_coverage_check",
    "effective_question_view",
    "discover_evidence",
    "prepare_interpretation_task",
    "submit_interpretation",
    "explain",
    "authority",
    "refresh",
    "trace",
    "status",
    "impact",
    "locate",
    "neighbors",
    "initialize_repository",
    "initialize_target",
]
