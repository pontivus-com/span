"""One containment resolver shared by resolution, status, and change mapping.

Implements FD-5, FD-7, and FD-17 membership. A parent link orders traversal
only; it never creates membership and can never remove it (FD-7). Boundaries
may overlap; a member may belong to any number of declared surfaces.
"""

from __future__ import annotations

import typing as _typing

from span.core.model.surfaces import (
    Surface,
    SurfaceBoundary,
    SurfaceKey,
    SurfaceKind,
)


def _kind_width(kind: SurfaceKind) -> int:
    """Granularity rank: smallest region first."""
    if kind is SurfaceKind.SYMBOL:
        return 0
    if kind is SurfaceKind.FILE:
        return 1
    if kind is SurfaceKind.SERVICE:
        return 2
    return 3


def path_surface(repository_id: str, locator: str) -> SurfaceKey:
    """The path surface identity of one file (FD-1)."""
    return SurfaceKey(
        repository_id=repository_id,
        kind=SurfaceKind.FILE,
        locator=locator,
    )


def symbol_surface(repository_id: str, locator: str) -> SurfaceKey:
    """The symbol surface identity of one canonical locator (FD-1)."""
    return SurfaceKey(
        repository_id=repository_id,
        kind=SurfaceKind.SYMBOL,
        locator=locator,
    )


def boundary_contains_path(boundary: SurfaceBoundary, locator: str) -> bool:
    """True when a file locator is inside the declared path boundary."""
    for prefix in boundary.paths:
        stem = prefix.rstrip("/")
        if locator == stem or locator.startswith(stem + "/"):
            return True
    return False


def surface_contains(surface: Surface, member: SurfaceKey) -> bool:
    """True when ``member`` is contained by ``surface`` (FD-5, FD-7).

    Membership is by boundary only. Declared surfaces contain path and symbol
    surfaces; a surface always contains itself.
    """
    if surface.key.repository_id != member.repository_id:
        return False
    if member == surface.key:
        return True
    if member.kind is SurfaceKind.SYMBOL:
        return member.locator in surface.boundary.symbols
    if member.kind is SurfaceKind.FILE:
        return boundary_contains_path(surface.boundary, member.locator)
    return False


def surface_sort_key(key: SurfaceKey) -> tuple[int, str, str]:
    """Narrowest to widest, then by kind and identity (FD-21)."""
    return (_kind_width(key.kind), key.kind.value, key.locator)


def order_surfaces(
    keys: _typing.Iterable[SurfaceKey],
) -> tuple[SurfaceKey, ...]:
    """Deterministic, deduplicated surface order."""
    return tuple(sorted(set(keys), key=surface_sort_key))


def containing_surfaces(
    surfaces: _typing.Iterable[Surface], member: SurfaceKey
) -> tuple[SurfaceKey, ...]:
    """Every surface a path or symbol belongs to, narrowest first.

    The member's own path or symbol surface is included, along with every
    declared surface whose boundary contains it. Parent links are not read:
    an explicit parent orders surfaces but never adds or removes membership.
    """
    keys = [member]
    keys.extend(
        surface.key
        for surface in surfaces
        if surface.key != member and surface_contains(surface, member)
    )
    return order_surfaces(keys)
