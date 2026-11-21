"""Installation-scoped Functional Pyramid SQLite persistence.

This store owns only cross-repository Functional Pyramid participation/version/
receipt state. Ordinary semantic/audit state remains in repository LifecycleStore
files. Runtime open never creates or migrates this database.
"""

from __future__ import annotations

import datetime as _datetime
import pathlib as _pathlib
import sqlite3 as _sqlite3
import typing as _typing

from span.core import model as m
from span.shell.sqlite_store.transactions import immediate_transaction

INSTALLATION_SCHEMA_VERSION = 1
INSTALLATION_STORE_RELATIVE = _pathlib.Path("installation") / "functional-pyramid.db"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS meta(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS functional_pyramid_versions(
        pyramid_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        content_digest TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        members_json TEXT NOT NULL,
        PRIMARY KEY(pyramid_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS functional_pyramids(
        pyramid_id TEXT PRIMARY KEY,
        version INTEGER NOT NULL,
        FOREIGN KEY(pyramid_id, version)
            REFERENCES functional_pyramid_versions(pyramid_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS functional_pyramid_active_members(
        repository_id TEXT PRIMARY KEY,
        pyramid_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        member_json TEXT NOT NULL,
        FOREIGN KEY(pyramid_id, version)
            REFERENCES functional_pyramid_versions(pyramid_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS functional_pyramid_exclusions(
        repository_id TEXT PRIMARY KEY
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS functional_pyramid_receipts(
        request_id TEXT PRIMARY KEY,
        content_digest TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        replay_expires_at TEXT,
        action TEXT NOT NULL,
        pyramid_id TEXT,
        version INTEGER,
        members_json TEXT NOT NULL,
        participation_effects_json TEXT NOT NULL,
        dependent_effect_refs_json TEXT NOT NULL
    )
    """,
)


class FunctionalPyramidInstallationStoreError(ValueError):
    """The installation-scoped Functional Pyramid store cannot satisfy a request."""


class FunctionalPyramidInstallationSchemaError(FunctionalPyramidInstallationStoreError):
    """The installation store is absent or has an unsupported schema."""


class FunctionalPyramidInstallationStore:
    """One installation-wide durable owner for Functional Pyramid state."""

    def __init__(
        self,
        path: str | _pathlib.Path,
        *,
        retention: m.LifecycleRetention,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
    ) -> None:
        self.path = _pathlib.Path(path)
        self.retention = retention
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        if not self.path.is_file():
            raise FunctionalPyramidInstallationSchemaError(
                f"Functional Pyramid installation store is not initialized: {self.path}"
            )
        self._connection = _sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = _sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._validate_schema()
        self._validate_transaction_mode()

    @classmethod
    def create(
        cls,
        path: str | _pathlib.Path,
        *,
        retention: m.LifecycleRetention,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
    ) -> "FunctionalPyramidInstallationStore":
        """Explicitly create the installation store; never used by pure runtime ask."""
        target = _pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        connection = _sqlite3.connect(str(target))
        try:
            connection.row_factory = _sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            mode = str(connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0])
            if mode.lower() != "delete":
                raise FunctionalPyramidInstallationStoreError(
                    f"installation store requires DELETE journal mode, observed {mode}"
                )
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE")
            for statement in _DDL:
                connection.execute(statement)
            row = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                    (str(INSTALLATION_SCHEMA_VERSION),),
                )
            elif int(row["value"]) != INSTALLATION_SCHEMA_VERSION:
                raise FunctionalPyramidInstallationSchemaError(
                    "unsupported Functional Pyramid installation schema "
                    f"{row['value']}; expected {INSTALLATION_SCHEMA_VERSION}"
                )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return cls(target, retention=retention, clock=clock)

    def close(self) -> None:
        self._connection.close()

    def schema_version(self) -> int:
        return INSTALLATION_SCHEMA_VERSION

    def _validate_schema(self) -> None:
        tables = {
            str(row["name"])
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master"
                " WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if "meta" not in tables:
            raise FunctionalPyramidInstallationSchemaError(
                "Functional Pyramid installation store has no schema marker"
            )
        row = self._connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        if row is None or int(row["value"]) != INSTALLATION_SCHEMA_VERSION:
            observed = None if row is None else row["value"]
            raise FunctionalPyramidInstallationSchemaError(
                "unsupported Functional Pyramid installation schema "
                f"{observed}; expected {INSTALLATION_SCHEMA_VERSION}"
            )
        required = {
            "functional_pyramid_versions",
            "functional_pyramids",
            "functional_pyramid_active_members",
            "functional_pyramid_exclusions",
            "functional_pyramid_receipts",
        }
        missing = required - tables
        if missing:
            raise FunctionalPyramidInstallationSchemaError(
                "Functional Pyramid installation store is missing tables: "
                + ", ".join(sorted(missing))
            )

    def _validate_transaction_mode(self) -> None:
        mode = str(self._connection.execute("PRAGMA journal_mode").fetchone()[0])
        synchronous = int(self._connection.execute("PRAGMA synchronous").fetchone()[0])
        if mode.lower() in {"wal", "off", "memory"} or synchronous == 0:
            raise FunctionalPyramidInstallationStoreError(
                "Functional Pyramid installation store does not support atomic "
                f"multi-database writes: journal_mode={mode}, synchronous={synchronous}"
            )

    def transaction(
        self,
    ) -> _typing.ContextManager[_sqlite3.Connection]:
        """Serialize one installation write; T08 extends this with attachments."""
        return immediate_transaction(self._connection)

    def reap_expired(self, moment: _datetime.datetime | None = None) -> int:
        """Reap installation-scoped replay receipts under the shared retention policy."""
        now = moment or self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("reap time must be timezone-aware")
        with self.transaction() as connection:
            result = connection.execute(
                "DELETE FROM functional_pyramid_receipts"
                " WHERE replay_expires_at IS NOT NULL AND replay_expires_at < ?",
                (now.astimezone(_datetime.timezone.utc).isoformat(),),
            )
            return result.rowcount


def functional_pyramid_installation_path(
    data_dir: str | _pathlib.Path,
) -> _pathlib.Path:
    return _pathlib.Path(data_dir) / INSTALLATION_STORE_RELATIVE


def ensure_functional_pyramid_installation_store(
    data_dir: str | _pathlib.Path,
    *,
    retention: m.LifecycleRetention,
) -> FunctionalPyramidInstallationStore:
    """Explicit setup owner for the installation store."""
    path = functional_pyramid_installation_path(data_dir)
    if path.is_file():
        return FunctionalPyramidInstallationStore(path, retention=retention)
    return FunctionalPyramidInstallationStore.create(path, retention=retention)
