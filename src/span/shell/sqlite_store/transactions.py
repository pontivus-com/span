"""Shared SQLite transaction primitives for Span-owned stores."""

from __future__ import annotations

import contextlib as _contextlib
import sqlite3 as _sqlite3
import typing as _typing


@_contextlib.contextmanager
def immediate_transaction(
    connection: _sqlite3.Connection,
) -> _typing.Iterator[_sqlite3.Connection]:
    """Serialize one write decision with BEGIN IMMEDIATE and atomic rollback."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
