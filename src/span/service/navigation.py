"""Retained structural navigation contracts (administrative, no semantics)."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.ports.structural import StructuralDirection

__all__ = [
    "SemanticStructuralLocateRequest",
    "SemanticStructuralNeighborsRequest",
]


@_dataclasses.dataclass(frozen=True)
class SemanticStructuralLocateRequest:
    """Structural locate contract."""

    repository_id: str
    mode: m.StructuralLocateMode
    bounds: m.QueryBounds | None = None
    query: str | None = None
    match: m.StructuralLocateMatch = m.StructuralLocateMatch.EXACT
    target: m.EvidenceScope | None = None
    page_token: str | None = None


@_dataclasses.dataclass(frozen=True)
class SemanticStructuralNeighborsRequest:
    """Structural neighbors contract."""

    repository_id: str
    target: m.SubjectSelector
    direction: StructuralDirection
    bounds: m.QueryBounds | None = None
    edge_kinds: tuple[m.StructuralEdgeKind, ...] = ()
    max_depth: int = 1
    page_token: str | None = None
