"""Shared SQLite exclusive-ownership protocol (shell effect).

One implementation of the store-quiescence rule. The offline store transition
and the data-directory restore both need to refuse a store that a live process
still holds; each caller translates :class:`StoreHeldError` into its own public
failure instead of re-implementing the lock protocol.
"""

from __future__ import annotations

import contextlib
import sqlite3
from typing import Iterator

#: How long a caller waits for a live holder to release the store. This is the
#: existing offline-transition wait, not a rule about when work may proceed.
DEFAULT_LOCK_TIMEOUT_SECONDS = 1.0


class StoreHeldError(RuntimeError):
    """The store is held by a live process for the whole probe window."""


@contextlib.contextmanager
def exclusive_ownership(
    path, timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS
) -> Iterator[sqlite3.Connection]:
    """Hold SQLite exclusive ownership until the context exits.

    ``locking_mode=EXCLUSIVE`` keeps the file lock after the first transaction
    until this connection closes, so a live writer or reader refuses the
    operation rather than being overwritten silently. The connection is yielded
    for callers that archive through the same handle; callers that only probe
    may use the context without touching it.
    """
    connection = sqlite3.connect(
        str(path), timeout=timeout_seconds, isolation_level=None
    )
    try:
        connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
        connection.execute("PRAGMA locking_mode = EXCLUSIVE")
        try:
            connection.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            raise StoreHeldError(str(exc)) from None
        connection.execute("COMMIT")
    except BaseException:
        connection.close()
        raise
    try:
        yield connection
    finally:
        connection.close()
