"""Span canonical service coordination for the 0.10 lifecycle.

Coordinates ports/core and owns no semantic rules. The ordinary lifecycle is
served by ``ask``/``record``/``reconsider`` operations composed from the
lifecycle, evidence, support and answer services. Explicit setup and
read-only structural navigation are separate administrative capabilities.
"""

from span.service.administration import initialize_repository
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
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

__all__ = [
    "DEFAULT_SERVICE_BOUNDS_POLICY",
    "SemanticStructuralLocateRequest",
    "SemanticStructuralNeighborsRequest",
    "LifecycleService",
    "EvidenceService",
    "UnderstandService",
    "SupportService",
    "locate",
    "neighbors",
    "initialize_repository",
]
