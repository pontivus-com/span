"""Span typed port interfaces.

Interfaces only — no implementations, no effects. Shell layers implement
these protocols; the core never imports them.
"""

from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import (
    LifecycleAuthorityResolver,
    LifecycleStorePort,
)
from span.ports.structural import StructuralDirection, StructuralSource

__all__ = [
    "EvidenceSource",
    "LifecycleAuthorityResolver",
    "LifecycleStorePort",
    "StructuralDirection",
    "StructuralSource",
]
