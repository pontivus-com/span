"""Mechanics shared by the structural provider adapters (plan §2.6, S8/D5).

Two adapters implement the same port over different stores. The parts that are
identical — repository binding, version-bound paging, and the adjacency
selection skeleton — live here once. What differs stays in each adapter: the
in-memory source iterates pre-built edges, while Graft maps raw wiring rows
through its closed vocabulary.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from span.core import model as m
from span.core import paging as _paging
from span.ports.structural import StaleContinuationError, StructuralDirection

_Token = TypeVar("_Token")
_Item = TypeVar("_Item")

__all__ = [
    "check_repository",
    "versioned_offset",
    "versioned_page",
    "selected_edges",
]


def check_repository(repository_id: str, configured: str) -> None:
    """Reject a request addressed to a different repository (fail closed)."""
    if repository_id != configured:
        raise ValueError(f"unknown repository: {repository_id}")


def versioned_offset(
    page_token: str | None,
    *,
    index_version: str,
    version: str | None = None,
) -> int:
    """Decode a version-bound cursor; drift becomes a stale continuation."""
    try:
        return _paging.parse_versioned_token(
            page_token,
            version=index_version if version is None else version,
        )
    except ValueError as exc:
        if str(exc).startswith(_paging.STALE_CONTINUATION_PREFIX):
            raise StaleContinuationError(str(exc)) from None
        raise


def versioned_page(
    items: tuple[_Item, ...],
    offset: int,
    max_results: int,
    category: str,
    *,
    index_version: str,
    version: str | None = None,
) -> tuple[tuple[_Item, ...], m.BoundInfo]:
    """Slice one version-bound listing page and describe it deterministically."""
    kept = items[offset : offset + max_results]
    remaining = len(items) - (offset + len(kept))
    truncated = remaining > 0
    token_version = index_version if version is None else version
    return tuple(kept), m.BoundInfo(
        requested_max_results=max_results,
        requested_max_depth=0,
        returned_results=len(kept),
        truncated=truncated,
        truncated_category=category if truncated else None,
        continuation_token=(
            _paging.format_versioned_token(token_version, offset + len(kept))
            if truncated
            else None
        ),
    )


def selected_edges(
    locator: str,
    edge_kinds: tuple[m.StructuralEdgeKind, ...],
    direction: StructuralDirection,
    entries: Iterable[tuple[m.StructuralEdgeKind, str, str, _Token]],
    materialize: Callable[[m.StructuralEdgeKind, str, str, _Token], m.StructuralEdge],
) -> list[m.StructuralEdge]:
    """Select and order one node's adjacent edges.

    ``entries`` carries the cheap identity of every candidate edge; only the
    selected ones are materialized, so a caller that maps raw rows pays for the
    rows it returns. Ordering is part of the port contract and stays here.
    """
    kinds = set(edge_kinds) if edge_kinds else set(m.StructuralEdgeKind)
    found: list[m.StructuralEdge] = []
    for kind, source, target, token in entries:
        if kind not in kinds:
            continue
        if (
            direction
            in (
                StructuralDirection.DOWNSTREAM,
                StructuralDirection.BOTH,
            )
            and source == locator
        ):
            found.append(materialize(kind, source, target, token))
        elif (
            direction
            in (
                StructuralDirection.UPSTREAM,
                StructuralDirection.BOTH,
            )
            and target == locator
        ):
            found.append(materialize(kind, source, target, token))
    found.sort(
        key=lambda edge: (
            edge.kind.value,
            edge.source.canonical_locator,
            edge.target.canonical_locator,
        )
    )
    return found
