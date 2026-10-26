"""Canonical item-reference helpers (core).

One owner for reading an identity off a claim or relationship reference, so
service and shell projections agree without either importing the other.
"""

from __future__ import annotations

from span.core import model as m

__all__ = ["ref_value"]


def ref_value(ref: m.ClaimRef | m.RelationshipRef) -> str:
    """The canonical identity string carried by one item reference."""
    return ref.id.value
