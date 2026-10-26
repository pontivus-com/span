"""The SQLite SemanticStore: connection lifecycle and schema handshake."""

from __future__ import annotations

import datetime as _datetime
import pathlib as _pathlib
import sqlite3 as _sqlite3

from collections.abc import Callable as _Callable

from span.core import model as m

from span.shell.sqlite_store.questions import QuestionReadMixin
from span.shell.sqlite_store.reads import ReadMixin
from span.shell.sqlite_store.repository import RepositoryMixin
from span.shell.sqlite_store.schema import (
    SCHEMA_VERSION,
    SQLITE_BUSY_TIMEOUT_MS,
    TARGET_RETENTION_DAYS,
    _SCHEMA,
)
from span.shell.sqlite_store.writes import WriteMixin


class SqliteSemanticStore(RepositoryMixin, QuestionReadMixin, ReadMixin, WriteMixin):
    def __init__(
        self,
        path: str | _pathlib.Path,
        target_retention_days: int = TARGET_RETENTION_DAYS,
        utc_now: _Callable[[], _datetime.datetime] | None = None,
    ) -> None:
        self._db = _sqlite3.connect(str(path))
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        self._target_retention_days = target_retention_days
        self._utc_now = utc_now or (
            lambda: _datetime.datetime.now(_datetime.timezone.utc)
        )
        tables = {
            row[0]
            for row in self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        row = None
        if "meta" in tables:
            try:
                row = self._db.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()
            except _sqlite3.OperationalError:
                row = None
        on_disk = int(row[0]) if row is not None else 0
        if not tables:
            # Fresh database: create schema 8 directly.
            self._db.executescript(_SCHEMA)
            self._db.execute(
                "INSERT OR REPLACE INTO meta(key, value) "
                "VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._db.commit()
            self._reap_expired_target_associations()
            return
        if on_disk != SCHEMA_VERSION:
            raise ValueError(
                "unsupported Span store schema version "
                f"{on_disk}; migrate this store to schema "
                f"{SCHEMA_VERSION} before using this Span build"
            )
        self._reap_expired_target_associations()

    def _now(self) -> _datetime.datetime:
        result = self._utc_now()
        assert isinstance(result, _datetime.datetime)
        return result

    def _reap_expired_target_associations(self) -> int:
        now_iso = self._now().isoformat()
        try:
            cur = self._db.execute(
                "DELETE FROM target_associations WHERE expires_at <= ?",
                (now_iso,),
            )
            self._db.commit()
            return cur.rowcount or 0
        except _sqlite3.OperationalError:
            return 0

    def close(self) -> None:
        """Release the database connection (shell lifecycle only)."""
        self._db.close()

    def schema_version(self) -> m.SchemaVersion:
        row = self._db.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        return m.SchemaVersion(value=int(row[0]) if row else 0)
