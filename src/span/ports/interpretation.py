"""Agent interpretation exchange contract (plan §5.4, §11.12).

Span constructs the bounded interpretation request; the invoking
LLM-connected agent performs the interpretation and returns the typed
result. There is no Span-side provider runtime behind this boundary.

This module holds what crosses the boundary (the pending envelope) and
the exchange failure contract (§7.3). The request/result/candidate types
themselves live in the core model; submit-request ingress lives with the
service operations.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass

from span.core import model as m

__all__ = [
    "PendingInterpretation",
    "InterpretationUnavailable",
]


@_dataclass(frozen=True)
class PendingInterpretation:
    """Suspended operation awaiting agent interpretation (§11.12).

    An exchange envelope, never semantic state: it carries the bounded
    task for the agent plus the single-use continuation the agent
    submits alongside its typed result.
    """

    continuation: str
    request: m.SemanticInterpretationRequest

    def __post_init__(self) -> None:
        if not self.continuation:
            raise ValueError("continuation must be non-empty")


class InterpretationUnavailable(Exception):
    """No result was submitted for the exchange (§7.3).

    Raised for unknown or expired continuations. The agent re-issues
    the original operation, which is idempotent.
    """
