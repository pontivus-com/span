"""Span typed port interfaces (plan §14).

Interfaces only — no implementations, no effects. Shell layers
implement these protocols; the core never imports them.
"""

from span.ports.evidence import EvidenceSource
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
    PendingInterpretation,
)
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection, StructuralSource

__all__ = [
    "EvidenceSource",
    "InterpretationIngressFailure",
    "InterpretationUnavailable",
    "PendingInterpretation",
    "SemanticStore",
    "StructuralDirection",
    "StructuralSource",
]
