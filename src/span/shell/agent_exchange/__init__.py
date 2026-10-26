"""Span agent-exchange shell (plan §11.12, §14).

Continuation bookkeeping for the Span↔agent interpretation exchange.
No provider SDKs, no credentials, no model invocation — the agent side
of the boundary belongs to the invoking agent, never to Span.
"""

from span.shell.agent_exchange.continuations import (
    ContinuationStore,
    SuspendedOperation,
)

__all__ = [
    "ContinuationStore",
    "SuspendedOperation",
]
