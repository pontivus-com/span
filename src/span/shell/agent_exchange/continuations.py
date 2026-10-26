"""Suspended-operation continuations (plan §11.12).

Ephemeral, single-use, TTL-bounded exchange state. Continuations are
never persisted semantic state, never authoritative, and abandoned on
expiry or use. Lost continuations are recovered by re-issuing the
original operation, which is idempotent (deterministic content-derived
identifier values make re-indexing safe, plan §4.7).
"""

from __future__ import annotations

import datetime as _datetime
import threading as _threading
from collections.abc import Callable as _Callable
from dataclasses import dataclass as _dataclass

from span.core.continuations import SuspendedOperation

__all__ = [
    "DEFAULT_CONTINUATION_TTL_SECONDS",
    "SuspendedOperation",
    "ContinuationStore",
]

#: Default continuation lifetime (plan §11.12, product configuration).
DEFAULT_CONTINUATION_TTL_SECONDS = 30 * 60


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
        self._now = now or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._counter = 0
        self._entries: dict[str, _Entry] = {}
        self._lock = _threading.Lock()
        self._in_flight: set[str] = set()

    def _is_expired_at(self, entry: _Entry, now: _datetime.datetime) -> bool:
        """Abandonment predicate shared by reads and sweeps.

        Mirrors exactly what ``claim()`` abandons: naive timestamps or
        age beyond TTL. Takes the observation time as an argument so
        each operation reads the clock exactly once.
        """
        created = entry.created_at
        if created.tzinfo is None or now.tzinfo is None:
            return True
        return (now - created).total_seconds() > self._ttl

    def _sweep_locked(self, now: _datetime.datetime) -> None:
        """Evict expired entries. Caller must hold ``self._lock``.

        Event-driven only (called from ``pend``/``acquire``/``claim``):
        no background reaper, no new ledger. Abandoned expired tokens
        are actually removed, so TTL bounds memory retention.
        """
        dead = [
            token
            for token, entry in self._entries.items()
            if self._is_expired_at(entry, now)
        ]
        for token in dead:
            self._entries.pop(token, None)
            self._in_flight.discard(token)

    def pend(self, record: SuspendedOperation) -> str:
        """Suspend an operation; returns its single-use continuation."""
        with self._lock:
            now = self._now()
            self._sweep_locked(now)
            self._counter += 1
            token = f"cont-{self._counter}"
            self._entries[token] = _Entry(record, now)
            return token

    def peek(self, continuation: str) -> SuspendedOperation | None:
        """Read a live continuation without consuming it ([design note H](docs/design-references.md#h) §4).

        Unknown or expired yields None. Never marks in-flight; never
        pops. Submit preparation uses this; ownership for the
        commit-critical section comes only from ``acquire()``.
        """
        entry = self._entries.get(continuation)
        if entry is None:
            return None
        if self._is_expired_at(entry, self._now()):
            return None
        return entry.record

    def acquire(self, continuation: str) -> SuspendedOperation | None:
        """Mark a live continuation in-flight for single-commit ownership.

        Returns the record once; a second concurrent acquirer for the
        same token observes in-flight/consumed/expired and receives
        None. Pair with ``release()`` on failure or ``claim()`` on
        successful commit. Bare ``peek()`` followed by ``claim()``
        without this guard is prohibited.
        """
        with self._lock:
            now = self._now()
            self._sweep_locked(now)
            if continuation in self._in_flight:
                return None
            entry = self._entries.get(continuation)
            if entry is None or self._is_expired_at(entry, now):
                return None
            self._in_flight.add(continuation)
            return entry.record

    def release(self, continuation: str) -> None:
        """Clear the in-flight mark, retaining the live token."""
        with self._lock:
            self._in_flight.discard(continuation)

    def claim(self, continuation: str) -> SuspendedOperation | None:
        """Take a continuation exactly once; expired or unknown yields None
        (abandoned, per §11.12).

        Sole consuming transition. ``submit_interpretation`` calls it
        only after a successful ``write_index_batch``.
        """
        with self._lock:
            now = self._now()
            self._sweep_locked(now)
            self._in_flight.discard(continuation)
            entry = self._entries.pop(continuation, None)
        if entry is None:
            return None
        if self._is_expired_at(entry, now):
            return None
        return entry.record

    def live_question_keys(self) -> frozenset[tuple[str, ...]]:
        """Identity keys of unexpired suspended units.

        One key per live entry uses the complete semantic question identity:
        scope root, subject, question class, and question slice. Used by
        refresh admission (G-15) so a recorded pending is never suspended
        twice while its first unit is still outstanding. Expired entries are
        skipped here (they are abandoned on next claim); nothing is evicted
        by this read.
        """
        now = self._now()
        keys: set[tuple[str, ...]] = set()
        for entry in self._entries.values():
            record = entry.record
            created = entry.created_at
            if created.tzinfo is None or now.tzinfo is None:
                continue
            if (now - created).total_seconds() > self._ttl:
                continue
            question = record.request.question
            if question is not None:
                keys.add(
                    (
                        "q",
                        question.scope_root.repository_id,
                        question.scope_root.subject_kind.value,
                        question.scope_root.canonical_locator,
                        question.subject.repository_id,
                        question.subject.subject_kind.value,
                        question.subject.canonical_locator,
                        question.question_class.value,
                        question.question_slice,
                    )
                )
            elif record.request.question_slice:
                for subject in record.request.subjects:
                    keys.add(
                        (
                            "q",
                            record.repository_id,
                            "",
                            "",
                            subject.subject_id.repository_id,
                            subject.subject_id.subject_kind.value,
                            subject.subject_id.canonical_locator,
                            "",
                            record.request.question_slice,
                        )
                    )
        return frozenset(keys)

    def live_records(self) -> tuple[SuspendedOperation, ...]:
        """Return unexpired suspended records for read-only status views.

        The accessor exposes the existing exchange records, never private
        entries or continuation tokens. Ordering is stable across calls and
        expired records remain excluded without changing the store.
        """
        now = self._now()
        with self._lock:
            records = [
                entry.record
                for entry in self._entries.values()
                if not self._is_expired_at(entry, now)
            ]
        return tuple(
            sorted(
                records,
                key=lambda record: (
                    record.repository_id,
                    record.target_id.value if record.target_id is not None else "",
                    (
                        record.request.question.scope_root.canonical_locator
                        if record.request.question is not None
                        else ""
                    ),
                    (
                        record.request.question.subject.canonical_locator
                        if record.request.question is not None
                        else record.subject.subject_id.canonical_locator
                    ),
                    (
                        record.request.question.question_class.value
                        if record.request.question is not None
                        else ""
                    ),
                    (
                        record.request.question.question_slice
                        if record.request.question is not None
                        else record.request.question_slice
                    ),
                    record.op,
                ),
            )
        )

    def __len__(self) -> int:
        return len(self._entries)
