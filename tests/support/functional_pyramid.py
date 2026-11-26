"""Shared Functional Pyramid view fixture (test support only)."""

from __future__ import annotations

from span.core import model as m

__all__ = ["functional_pyramid_view"]


def functional_pyramid_view(
    scope: m.EvidenceScope,
    *,
    pyramid_id: str = "fp",
    status: m.FunctionalPyramidRouteStatus = m.FunctionalPyramidRouteStatus.RESOLVED,
) -> m.FunctionalPyramidView:
    """One compact view with an explicit route status."""
    unresolved: tuple[m.FunctionalPyramidFinding, ...] = ()
    if status is m.FunctionalPyramidRouteStatus.UNRESOLVED:
        unresolved = (
            m.FunctionalPyramidFinding(
                reason=m.FunctionalPyramidFindingReason.DOCUMENT_UNAVAILABLE,
                repository_id="repo-1",
                detail="canonical Functional Pyramid document is unavailable",
                recovery="restore the declared canonical document",
            ),
        )
    return m.FunctionalPyramidView(
        pyramid_id=m.FunctionalPyramidId(pyramid_id),
        version=m.FunctionalPyramidVersion(1),
        status=status,
        semantic_scope=scope,
        placements=(),
        unresolved=unresolved,
        declared_layers=(),
        absent_layers=tuple(m.FunctionalPyramidLayer),
    )
