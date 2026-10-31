"""Span canonical service coordination for the 0.9.0 lifecycle.

Coordinates ports/core and owns no semantic rules. The ordinary lifecycle is
served by ``understand``/``record``/``reconsider`` operations composed from the
lifecycle, evidence, support and discovery services. Explicit setup and
read-only structural navigation are separate administrative capabilities.
"""

from span.service.administration import initialize_repository
from span.service.bounds import (
    DEFAULT_SERVICE_BOUNDS_POLICY,
    BoundsRejectedError,
    resolve_bounds,
)
from span.service.evidence import EvidenceService
from span.service.lifecycle import LifecycleService
from span.service.navigation import (
    SemanticStructuralLocateRequest,
    SemanticStructuralNeighborsRequest,
)
from span.service.operations.locate import locate
from span.service.operations.neighbors import neighbors
from span.service.support import SupportService
from span.service.understand import UnderstandService
from span.service.understanding_discovery import DiscoveryService

__all__ = [
    "DEFAULT_SERVICE_BOUNDS_POLICY",
    "BoundsRejectedError",
    "resolve_bounds",
    "SemanticStructuralLocateRequest",
    "SemanticStructuralNeighborsRequest",
    "LifecycleService",
    "EvidenceService",
    "DiscoveryService",
    "UnderstandService",
    "SupportService",
    "locate",
    "neighbors",
    "initialize_repository",
]
