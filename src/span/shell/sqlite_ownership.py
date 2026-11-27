"""Shared SQLite exclusive-ownership protocol (shell effect).

One implementation of the store-quiescence rule. The offline store transition
and the data-directory restore both need to refuse a store that a live process
still holds; each caller translates :class:`StoreHeldError` into its own public
failure instead of re-implementing the lock protocol.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import sqlite3
import stat
from pathlib import Path
from typing import Iterator

#: How long a caller waits for a live holder to release the store. This is the
#: existing offline-transition wait, not a rule about when work may proceed.
DEFAULT_LOCK_TIMEOUT_SECONDS = 1.0


class StoreHeldError(RuntimeError):
    """The store is held by a live process for the whole probe window."""


@contextlib.contextmanager
def stable_ownership(
    data_dir: str | Path, name: str, *, exclusive: bool
) -> Iterator[None]:
    """Advisory ownership on a stable canonical installation-local path."""
    root = Path(data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    try:
        handle = os.open(
            path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600
        )
    except OSError as exc:
        raise StoreHeldError(f"cannot open ownership lock {path}: {exc}") from exc
    try:
        identity = os.fstat(handle)
        if not stat.S_ISREG(identity.st_mode):
            raise StoreHeldError(f"invalid ownership lock: {path}")
        try:
            mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(handle, mode | fcntl.LOCK_NB)
        except OSError as exc:
            raise StoreHeldError(f"ownership lock held or unavailable: {path}") from exc
        current = path.stat(follow_symlinks=False)
        if (identity.st_dev, identity.st_ino) != (current.st_dev, current.st_ino):
            raise StoreHeldError(f"ownership lock identity changed: {path}")
        yield
    finally:
        os.close(handle)


@contextlib.contextmanager
def store_use_ownership(
    data_dir: str | Path, *, exclusive: bool = False
) -> Iterator[None]:
    """Shared runtime admission or exclusive installation recovery."""
    with stable_ownership(data_dir, ".store-use.lock", exclusive=exclusive):
        if not exclusive:
            from span.shell.store_transition import (
                require_completed_installation_cutover,
            )

            require_completed_installation_cutover(Path(data_dir).resolve())
        yield


@contextlib.contextmanager
def exclusive_ownership(
    path: str | Path, timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS
) -> Iterator[sqlite3.Connection]:
    """Hold SQLite exclusive ownership until the context exits.

    ``locking_mode=EXCLUSIVE`` keeps the file lock after the first transaction
    until this connection closes, so a live writer or reader refuses the
    operation rather than being overwritten silently. The connection is yielded
    for callers that archive through the same handle; callers that only probe
    may use the context without touching it.
    """
    connection = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=rw",
        timeout=timeout_seconds,
        isolation_level=None,
        uri=True,
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
