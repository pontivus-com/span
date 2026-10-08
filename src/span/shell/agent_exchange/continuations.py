"""Suspended-operation continuations (plan §11.12).

Ephemeral, single-use, TTL-bounded exchange state. Continuations are
never persisted semantic state, never authoritative, and abandoned on
expiry or use. Lost continuations are recovered by re-issuing the
original operation, which is idempotent (deterministic content-derived
identifier values make re-indexing safe, plan §4.7).
"""

from __future__ import annotations

import datetime as _datetime
from collections.abc import Callable as _Callable
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core import model as m

__all__ = [
    "DEFAULT_CONTINUATION_TTL_SECONDS",
    "SuspendedOperation",
    "ContinuationStore",
]

#: Default continuation lifetime (plan §11.12, product configuration).
DEFAULT_CONTINUATION_TTL_SECONDS = 30 * 60


@_dataclass(frozen=True)
class SuspendedOperation:
    """Record of one suspended indexing step (exchange state, not semantics)."""

    op: str
    repository_id: str
    subject: m.Subject
    request: m.SemanticInterpretationRequest
    bounds: m.QueryBounds
    state: m.RepositoryState
    scope: tuple[m.Subject, ...] = ()
    remaining: tuple[m.Subject, ...] = ()
    changed: tuple[m.EvidenceDependency, ...] = ()
    resolution: m.SubjectResolution | None = None
    fingerprints: tuple[tuple[str, str], ...] = ()
    known_subject_ids: tuple[m.SubjectId, ...] = ()
    seeds: tuple[m.EvidenceRef, ...] = ()
    reissues: int = 0
    suspended: tuple[str, ...] = ()
    change_kind: str | None = None
    change_description: str | None = None
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = ()
    operation_intent: str = "EXPLAIN"
    question_slice: str = ""
    declared_complete: bool = False
    trace_direction: str | None = None
    trace_filter: tuple[m.RelationshipKind, ...] = ()
    trace_filter_set: bool = False
    trace_boundary: bool = False
    establish_baseline: bool = False

    def __post_init__(self) -> None:
        if self.op not in (
            "explain", "authority", "refresh", "trace", "status", "impact"
        ):
            raise ValueError(f"unknown suspended op: {self.op}")
        if self.reissues < 0:
            raise ValueError("reissues must be non-negative")


@_dataclass
class _Entry:
    record: SuspendedOperation
    created_at: _datetime.datetime


class ContinuationStore:
    """Ephemeral single-use continuation bookkeeping (shell lifecycle).

    Tokens are deterministic per store instance (``cont-1``, …) so
    exchange flows are exactly reproducible in tests. Time is
    injectable for the same reason; production uses UTC wall-clock.
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CONTINUATION_TTL_SECONDS,
        now: _Callable[[], _datetime.datetime] | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl = ttl_seconds
        self._now = now or (
            lambda: _datetime.datetime.now(_datetime.timezone.utc)
        )
        self._counter = 0
        self._entries: dict[str, _Entry] = {}

    def pend(self, record: SuspendedOperation) -> str:
        """Suspend an operation; returns its single-use continuation."""
        self._counter += 1
        token = f"cont-{self._counter}"
        self._entries[token] = _Entry(record, self._now())
        return token

    def claim(self, continuation: str) -> SuspendedOperation | None:
        """Take a continuation exactly once; expired or unknown yields None
        (abandoned, per §11.12)."""
        entry = self._entries.pop(continuation, None)
        if entry is None:
            return None
        created = entry.created_at
        now = self._now()
        if created.tzinfo is None or now.tzinfo is None:
            return None
        if (now - created).total_seconds() > self._ttl:
            return None
        return entry.record

    def __len__(self) -> int:
        return len(self._entries)
