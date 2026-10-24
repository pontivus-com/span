"""Span service structural neighbors operation (Addendum F §4.2).

Read-only bounded adjacency over the StructuralSource port. No semantic
interpretation, no persistence. Traversal consumes every adjacency page
per visited node (single-page reads silently drop branches); a visited
cap bounds total work and yields an explicit truncated continuation
that resumes the traversal — replay-free, because visited and frontier
state travels in the token.
"""

from __future__ import annotations

import base64 as _base64
import json as _json
from collections import deque as _deque

from span.core import model as m
from span.ports.store import SemanticStore
from span.ports.structural import StaleContinuationError
from span.ports.structural import StructuralDirection
from span.ports.structural import StructuralSource
from span.service.bounds import resolve_bounds as _resolve_bounds
from span.service.repository import _is_initialized
from span.service.requests import SemanticStructuralNeighborsRequest
from span.service.resolution import _resolve_query_subject

__all__ = ["neighbors", "encode_traversal_token", "decode_traversal_token"]

_TOKEN_PREFIX = "pgn:"


def encode_traversal_token(
    version: str, visited: tuple[str, ...], frontier: tuple[tuple[str, int], ...]
) -> str:
    """Encode resumable BFS state (Addendum F §4.3).

    Visited count is bounded by the visited cap, so tokens stay small.
    Distinct format from offset tokens; never interchanged.
    """
    payload = _json.dumps(
        {
            "v": version,
            "seen": list(visited),
            "frontier": [list(pair) for pair in frontier],
        },
        separators=(",", ":"),
    )
    return _TOKEN_PREFIX + _base64.urlsafe_b64encode(payload.encode("utf-8")).decode(
        "ascii"
    )


def decode_traversal_token(
    page_token: str | None,
    *,
    version: str,
) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...]]:
    """Decode BFS resume state; version drift restarts the traversal."""
    if page_token is None:
        return (), ()
    if not page_token.startswith(_TOKEN_PREFIX):
        raise ValueError(f"unknown page token: {page_token}")
    try:
        payload = _json.loads(
            _base64.urlsafe_b64decode(
                page_token[len(_TOKEN_PREFIX) :].encode("ascii")
            ).decode("utf-8")
        )
        token_version = payload["v"]
        visited = tuple(payload["seen"])
        frontier = tuple((loc, depth) for loc, depth in payload["frontier"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"unknown page token: {page_token}") from exc
    if not all(isinstance(loc, str) for loc in visited) or not all(
        isinstance(loc, str) and isinstance(depth, int) and not isinstance(depth, bool)
        for loc, depth in frontier
    ):
        raise ValueError(f"unknown page token: {page_token}")
    if any(d < 0 for _, d in frontier):
        raise ValueError(f"unknown page token: {page_token}")
    if token_version != version:
        raise StaleContinuationError(
            f"stale listing continuation: token version "
            f"{token_version!r} != current {version!r}"
        )
    return visited, frontier


def _listing_version(structural: StructuralSource, repository_id: str) -> str:
    return structural.repository_state(repository_id).state_fingerprint


def _all_edges(
    structural: StructuralSource,
    repository_id: str,
    subject: m.SubjectId,
    edge_kinds: tuple[m.StructuralEdgeKind, ...],
    direction: StructuralDirection,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.StructuralEdge, ...], bool]:
    """Every adjacency page for one node; True when unsupported."""
    out: list[m.StructuralEdge] = []
    seen_tokens: set[str | None] = {None}
    token: str | None = None
    while True:
        page = structural.edges(
            repository_id,
            subject,
            edge_kinds,
            direction,
            bounds,
            token,
        )
        if page.unsupported:
            return (), True
        out.extend(page.items)
        if not page.bound_info.truncated:
            return tuple(out), False
        token = page.bound_info.continuation_token
        if token in seen_tokens:
            return tuple(out), False
        seen_tokens.add(token)


def neighbors(
    request: SemanticStructuralNeighborsRequest,
    *,
    structural: StructuralSource,
    store: SemanticStore,
) -> m.StructuralNeighborsResult:
    """Execute one structural neighbors traversal (read-only)."""
    if not _is_initialized(request.repository_id, store=store):
        raise ValueError(f"repository not initialized: {request.repository_id}")
    if (
        isinstance(request.max_depth, bool)
        or not isinstance(request.max_depth, int)
        or request.max_depth < 1
    ):
        raise ValueError("neighbors max_depth must be a positive integer")
    bounds = _resolve_bounds(request.bounds, hook=False)
    version = _listing_version(structural, request.repository_id)
    try:
        visited_token, frontier_token = decode_traversal_token(
            request.page_token, version=version
        )
    except StaleContinuationError:
        raise
    except ValueError as exc:
        raise ValueError(f"neighbors failed: {exc}") from None
    resolution = _resolve_query_subject(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        state = structural.repository_state(request.repository_id)
        return m.StructuralNeighborsResult(
            resolution=resolution,
            repository_state=state,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_results,
                requested_max_depth=bounds.max_depth,
                returned_results=0,
                truncated=False,
                truncated_category=None,
                continuation_token=None,
            ),
        )
    limit = min(request.max_depth, bounds.max_depth)
    kinds = request.edge_kinds
    direction = request.direction
    seen: set[str] = set(visited_token)
    queue: _deque[tuple[str, int]] = _deque(frontier_token)
    if not queue:
        root = resolution.candidates[0].subject.subject_id.canonical_locator
        seen.add(root)
        queue.append((root, 0))
    visit_cap = bounds.max_subjects
    collected: dict[tuple[str, str, str], m.StructuralEdge] = {}
    unsupported = False
    truncated = False
    # Caps are per response segment, checked between node expansions so
    # every expanded node contributes its complete adjacency (overshoot
    # bounded by one node's degree). Visited/frontier state travels in
    # the token, so resume continues the identical sequence: no
    # duplicates, no replay, no deadlock (a total-seen cap would
    # truncate every resume the moment it starts).
    expansions = 0
    while queue:
        if expansions >= visit_cap or len(collected) >= bounds.max_results:
            truncated = True
            break
        current, depth = queue.popleft()
        if depth >= limit:
            continue
        expansions += 1
        current_id = m.SubjectId(
            repository_id=request.repository_id,
            subject_kind=m.SubjectKind.OTHER,
            canonical_locator=current,
        )
        # Subject kind is irrelevant to edge filtering (locator-only);
        # resolution already established identity above.
        page_edges, page_unsupported = _all_edges(
            structural,
            request.repository_id,
            current_id,
            kinds,
            direction,
            bounds,
        )
        if page_unsupported:
            unsupported = True
            break
        for edge in page_edges:
            key = (
                edge.source.canonical_locator,
                edge.kind.value,
                edge.target.canonical_locator,
            )
            collected.setdefault(key, edge)
            other = (
                edge.target.canonical_locator
                if edge.source.canonical_locator == current
                else edge.source.canonical_locator
            )
            if other not in seen:
                seen.add(other)
                queue.append((other, depth + 1))
    state = structural.repository_state(request.repository_id)
    if unsupported:
        return m.StructuralNeighborsResult(
            resolution=resolution,
            repository_state=state,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_results,
                requested_max_depth=bounds.max_depth,
                returned_results=0,
                truncated=False,
                truncated_category=None,
                continuation_token=None,
            ),
            unsupported=True,
        )
    edges = tuple(collected.values())
    # Edge currency follows each edge's evidence file; stale evidence
    # excludes the edge (counted), never silently kept.
    report = structural.verify_files(
        request.repository_id,
        tuple(sorted({e.evidence.locator for e in edges})),
    )
    stale_set = set(report.stale_files)
    live_edges = tuple(e for e in edges if e.evidence.locator not in stale_set)
    stale_omitted = len(edges) - len(live_edges)
    if queue:
        truncated = True
    # Frontier keeps queue order (insertion/BFS order), not sorted:
    # resume must continue the identical traversal sequence.
    resume_frontier = tuple(queue)
    return m.StructuralNeighborsResult(
        resolution=resolution,
        repository_state=state,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_results,
            requested_max_depth=bounds.max_depth,
            returned_results=len(live_edges),
            truncated=truncated,
            truncated_category="neighbors" if truncated else None,
            continuation_token=(
                encode_traversal_token(version, tuple(sorted(seen)), resume_frontier)
                if truncated
                else None
            ),
        ),
        edges=live_edges,
        unsupported=False,
        stale_omitted=stale_omitted,
        coverage=report.coverage,
        coverage_detail=report.coverage_detail,
    )
