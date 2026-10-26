"""Continuation port: the service's view of suspended-operation storage.

The shell owns the store (ephemeral, TTL-bounded, single-use). The service only
needs these operations, so it depends on this protocol rather than on the shell
implementation.
"""

from __future__ import annotations

from typing import Protocol

from span.core.continuations import SuspendedOperation

__all__ = ["ContinuationPort"]


class ContinuationPort(Protocol):
    """Read/write contract for suspended-operation continuations."""

    def pend(self, record: SuspendedOperation) -> str:
        """Store one suspended operation and return its single-use token."""
        ...

    def peek(self, continuation: str) -> SuspendedOperation | None:
        """Read a live continuation without consuming or marking it."""
        ...

    def acquire(self, continuation: str) -> SuspendedOperation | None:
        """Mark a live continuation in-flight for single-commit ownership."""
        ...

    def release(self, continuation: str) -> None:
        """Clear the in-flight mark, retaining the live token."""
        ...

    def claim(self, continuation: str) -> SuspendedOperation | None:
        """Consume a continuation exactly once."""
        ...

    def live_question_keys(self) -> frozenset[tuple[str, ...]]:
        """Question identities with a live suspended unit."""
        ...

    def live_records(self) -> tuple[SuspendedOperation, ...]:
        """Every live suspended operation, in creation order."""
        ...

    def __len__(self) -> int:
        """Number of live continuations."""
        ...
