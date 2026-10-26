"""Listing version shared by structural listing operations ([design note F](docs/design-references.md#f) §4.3).

A listing cursor is bound to the repository state it was issued against. The
version is the repository state fingerprint, read from the structural source —
one owner for every listing operation that mints or redeems such a cursor.
"""

from __future__ import annotations

from span.ports.structural import StructuralSource

__all__ = ["listing_version"]


def listing_version(structural: StructuralSource, repository_id: str) -> str:
    """The repository state fingerprint binding a listing page token."""
    return structural.repository_state(repository_id).state_fingerprint
