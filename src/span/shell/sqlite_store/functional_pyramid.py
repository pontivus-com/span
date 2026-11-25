"""Installation-scoped Functional Pyramid SQLite persistence.

This store owns only cross-repository Functional Pyramid participation/version/
receipt state. Ordinary semantic/audit state remains in repository LifecycleStore
files. Runtime open never creates or migrates this database.
"""

from __future__ import annotations

import contextlib as _contextlib
import datetime as _datetime
import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3
import typing as _typing

from span.core import model as m
from span.shell.sqlite_store.contexts import (
    add_context_discovery_row,
    add_context_evidence_row,
    insert_context_row,
)
from span.shell.sqlite_store.schema import SCHEMA_VERSION as REPOSITORY_SCHEMA_VERSION
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


def _canonical_json(value: object) -> str:
    return _json.dumps(m.to_canonical(value), sort_keys=True, separators=(",", ":"))


def _member_json(member: m.FunctionalPyramidMemberView) -> str:
    return _canonical_json(member)


def _members_json(members: tuple[m.FunctionalPyramidMemberView, ...]) -> str:
    return _json.dumps(
        [m.to_canonical(member) for member in members],
        sort_keys=True,
        separators=(",", ":"),
    )


def _decode_member_data(value: object) -> m.FunctionalPyramidMemberView:
    try:
        return m.from_canonical(m.FunctionalPyramidMemberView, value)
    except m.CanonicalDecodeError:
        pass
    if not isinstance(value, dict):
        raise FunctionalPyramidInstallationStoreError("stored pyramid member is invalid")
    if value.get("$type") != "FunctionalPyramidMemberView":
        raise FunctionalPyramidInstallationStoreError("stored pyramid member type is invalid")
    allowed = {
        "$type",
        "repository_id",
        "declaration_refs",
        "functional_scope",
        "coverage",
    }
    if set(value) - allowed or "repository_id" not in value or "declaration_refs" not in value:
        raise FunctionalPyramidInstallationStoreError(
            "stored pyramid member cannot be projected to Version-2 membership"
        )
    projected = {
        "$type": "FunctionalPyramidMemberView",
        "repository_id": value["repository_id"],
        "declaration_refs": value["declaration_refs"],
    }
    return m.from_canonical(m.FunctionalPyramidMemberView, projected)


def _decode_member(payload: str) -> m.FunctionalPyramidMemberView:
    return _decode_member_data(_json.loads(payload))


def _decode_members(payload: str) -> tuple[m.FunctionalPyramidMemberView, ...]:
    raw = _json.loads(payload)
    if not isinstance(raw, list):
        raise FunctionalPyramidInstallationStoreError(
            "stored pyramid members are invalid"
        )
    return tuple(_decode_member_data(item) for item in raw)


def _active_pyramid_id(
    connection: _sqlite3.Connection,
    repository_id: str,
) -> m.FunctionalPyramidId | None:
    row = connection.execute(
        "SELECT pyramid_id FROM functional_pyramid_active_members"
        " WHERE repository_id=?",
        (repository_id,),
    ).fetchone()
    return None if row is None else m.FunctionalPyramidId(str(row["pyramid_id"]))


def _pyramid_version(
    connection: _sqlite3.Connection,
    pyramid_id: m.FunctionalPyramidId,
) -> m.FunctionalPyramidVersion | None:
    row = connection.execute(
        "SELECT version FROM functional_pyramids WHERE pyramid_id=?",
        (pyramid_id.value,),
    ).fetchone()
    return None if row is None else m.FunctionalPyramidVersion(int(row["version"]))


def _pyramid_members(
    connection: _sqlite3.Connection,
    pyramid_id: m.FunctionalPyramidId,
    version: m.FunctionalPyramidVersion | None,
) -> tuple[m.FunctionalPyramidMemberView, ...]:
    selected = version or _pyramid_version(connection, pyramid_id)
    if selected is None:
        return ()
    row = connection.execute(
        "SELECT members_json FROM functional_pyramid_versions"
        " WHERE pyramid_id=? AND version=?",
        (pyramid_id.value, selected.value),
    ).fetchone()
    if row is None:
        return ()
    return _decode_members(str(row["members_json"]))


def _is_excluded(connection: _sqlite3.Connection, repository_id: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM functional_pyramid_exclusions WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        is not None
    )


def _decode_receipt(row: _sqlite3.Row) -> m.RetrievedFunctionalPyramidReceipt:
    members_raw = _json.loads(str(row["members_json"]))
    effects_raw = _json.loads(str(row["participation_effects_json"]))
    refs_raw = _json.loads(str(row["dependent_effect_refs_json"]))
    if not isinstance(members_raw, list):
        raise FunctionalPyramidInstallationStoreError(
            "stored receipt members are invalid"
        )
    if not isinstance(effects_raw, list):
        raise FunctionalPyramidInstallationStoreError(
            "stored receipt participation effects are invalid"
        )
    if not isinstance(refs_raw, list):
        raise FunctionalPyramidInstallationStoreError(
            "stored receipt dependent effects are invalid"
        )
    pyramid_value = row["pyramid_id"]
    version_value = row["version"]
    return m.RetrievedFunctionalPyramidReceipt(
        request_id=m.RequestId(str(row["request_id"])),
        content_digest=m.ContentDigest(str(row["content_digest"])),
        committed_at=_datetime.datetime.fromisoformat(str(row["committed_at"])),
        action=m.FunctionalPyramidAction(str(row["action"])),
        pyramid_id=(
            None if pyramid_value is None else m.FunctionalPyramidId(str(pyramid_value))
        ),
        version=(
            None
            if version_value is None
            else m.FunctionalPyramidVersion(int(version_value))
        ),
        members=tuple(_decode_member_data(item) for item in members_raw),
        participation_effects=tuple(
            m.from_canonical(m.FunctionalPyramidParticipationEffect, item)
            for item in effects_raw
        ),
        dependent_effect_refs=tuple(
            m.from_canonical(m.ConclusionRevisionRef, item) for item in refs_raw
        ),
    )


def _receipt(
    connection: _sqlite3.Connection,
    request_id: m.RequestId,
) -> m.RetrievedFunctionalPyramidReceipt | None:
    row = connection.execute(
        "SELECT request_id, content_digest, committed_at, action, pyramid_id,"
        " version, members_json, participation_effects_json,"
        " dependent_effect_refs_json FROM functional_pyramid_receipts"
        " WHERE request_id=?",
        (request_id.value,),
    ).fetchone()
    return None if row is None else _decode_receipt(row)


class _FunctionalPyramidInstallationReader:
    """Shared read projection over installation-scoped Functional Pyramid state."""

    _connection: _sqlite3.Connection

    def active_pyramid_id(self, repository_id: str) -> m.FunctionalPyramidId | None:
        return _active_pyramid_id(self._connection, repository_id)

    def pyramid_version(
        self, pyramid_id: m.FunctionalPyramidId
    ) -> m.FunctionalPyramidVersion | None:
        return _pyramid_version(self._connection, pyramid_id)

    def pyramid_members(
        self,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion | None = None,
    ) -> tuple[m.FunctionalPyramidMemberView, ...]:
        return _pyramid_members(self._connection, pyramid_id, version)

    def is_excluded(self, repository_id: str) -> bool:
        return _is_excluded(self._connection, repository_id)

    def receipt(
        self, request_id: m.RequestId
    ) -> m.RetrievedFunctionalPyramidReceipt | None:
        return _receipt(self._connection, request_id)


class FunctionalPyramidInstallationTransaction(_FunctionalPyramidInstallationReader):
    """One locked installation write across attached repository stores."""

    def __init__(
        self,
        connection: _sqlite3.Connection,
        aliases: tuple[tuple[str, str], ...],
    ) -> None:
        self._connection = connection
        self._aliases = aliases

    def _schema(self, repository_id: str) -> str:
        for current, alias in self._aliases:
            if current == repository_id:
                return alias
        raise FunctionalPyramidInstallationStoreError(
            f"repository is not attached to this pyramid transaction: {repository_id}"
        )

    def write_pyramid_version(
        self,
        *,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion,
        content_digest: m.ContentDigest,
        committed_at: _datetime.datetime,
        members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> None:
        if committed_at.tzinfo is None or committed_at.utcoffset() is None:
            raise ValueError("pyramid commit time must be timezone-aware")
        self._connection.execute(
            "INSERT INTO functional_pyramid_versions"
            "(pyramid_id, version, content_digest, committed_at, members_json)"
            " VALUES(?,?,?,?,?)",
            (
                pyramid_id.value,
                version.value,
                content_digest.value,
                committed_at.astimezone(_datetime.timezone.utc).isoformat(),
                _members_json(members),
            ),
        )

    def set_current_pyramid(
        self,
        *,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion,
        members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> None:
        self._connection.execute(
            "INSERT INTO functional_pyramids(pyramid_id, version) VALUES(?,?)"
            " ON CONFLICT(pyramid_id) DO UPDATE SET version=excluded.version",
            (pyramid_id.value, version.value),
        )
        self._connection.execute(
            "DELETE FROM functional_pyramid_active_members WHERE pyramid_id=?",
            (pyramid_id.value,),
        )
        for member in sorted(members, key=lambda item: item.repository_id):
            conflict = self._connection.execute(
                "SELECT pyramid_id FROM functional_pyramid_active_members"
                " WHERE repository_id=?",
                (member.repository_id,),
            ).fetchone()
            if conflict is not None and str(conflict["pyramid_id"]) != pyramid_id.value:
                raise FunctionalPyramidInstallationStoreError(
                    f"repository already belongs to an ACTIVE Functional Pyramid: "
                    f"{member.repository_id}"
                )
            self._connection.execute(
                "DELETE FROM functional_pyramid_exclusions WHERE repository_id=?",
                (member.repository_id,),
            )
            self._connection.execute(
                "INSERT INTO functional_pyramid_active_members"
                "(repository_id, pyramid_id, version, member_json)"
                " VALUES(?,?,?,?)",
                (
                    member.repository_id,
                    pyramid_id.value,
                    version.value,
                    _member_json(member),
                ),
            )

    def clear_current_pyramid(self, pyramid_id: m.FunctionalPyramidId) -> None:
        self._connection.execute(
            "DELETE FROM functional_pyramid_active_members WHERE pyramid_id=?",
            (pyramid_id.value,),
        )
        self._connection.execute(
            "DELETE FROM functional_pyramids WHERE pyramid_id=?",
            (pyramid_id.value,),
        )

    def set_excluded(self, repository_id: str, excluded: bool) -> None:
        if excluded:
            if self.active_pyramid_id(repository_id) is not None:
                raise FunctionalPyramidInstallationStoreError(
                    f"ACTIVE repository cannot be excluded: {repository_id}"
                )
            self._connection.execute(
                "INSERT OR IGNORE INTO functional_pyramid_exclusions(repository_id)"
                " VALUES(?)",
                (repository_id,),
            )
            return
        self._connection.execute(
            "DELETE FROM functional_pyramid_exclusions WHERE repository_id=?",
            (repository_id,),
        )

    def write_receipt(
        self,
        receipt: m.RetrievedFunctionalPyramidReceipt,
        *,
        replay_expires_at: _datetime.datetime,
    ) -> None:
        if replay_expires_at.tzinfo is None or replay_expires_at.utcoffset() is None:
            raise ValueError("receipt replay expiry must be timezone-aware")
        self._connection.execute(
            "INSERT INTO functional_pyramid_receipts"
            "(request_id, content_digest, committed_at, replay_expires_at,"
            " action, pyramid_id, version, members_json,"
            " participation_effects_json, dependent_effect_refs_json)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                receipt.request_id.value,
                receipt.content_digest.value,
                receipt.committed_at.astimezone(_datetime.timezone.utc).isoformat(),
                replay_expires_at.astimezone(_datetime.timezone.utc).isoformat(),
                receipt.action.value,
                None if receipt.pyramid_id is None else receipt.pyramid_id.value,
                None if receipt.version is None else receipt.version.value,
                _members_json(receipt.members),
                _json.dumps(
                    [
                        m.to_canonical(effect)
                        for effect in receipt.participation_effects
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                _json.dumps(
                    [m.to_canonical(ref) for ref in receipt.dependent_effect_refs],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )

    def write_reestablishment_context(
        self,
        context: m.InvestigationContext,
        *,
        source_observation_ids: tuple[str, ...] = (),
        discovery_observation_ids: tuple[str, ...] = (),
    ) -> None:
        schema = self._schema(context.repository_id)
        insert_context_row(self._connection, context, schema=schema)
        for observation_id in source_observation_ids:
            add_context_evidence_row(
                self._connection,
                repository_id=context.repository_id,
                context_id=context.context_id.value,
                observation_id=observation_id,
                schema=schema,
            )
        for observation_id in discovery_observation_ids:
            add_context_discovery_row(
                self._connection,
                repository_id=context.repository_id,
                context_id=context.context_id.value,
                observation_id=observation_id,
                schema=schema,
            )


class FunctionalPyramidInstallationStore(_FunctionalPyramidInstallationReader):
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

    @_contextlib.contextmanager
    def transaction(
        self,
        repository_paths: tuple[tuple[str, str], ...] = (),
    ) -> _typing.Iterator[FunctionalPyramidInstallationTransaction]:
        """Serialize one installation write across deterministic repository attachments."""
        ordered = tuple(sorted(repository_paths))
        if len({repository_id for repository_id, _ in ordered}) != len(ordered):
            raise ValueError("repository attachments must have unique repository IDs")
        aliases: list[tuple[str, str]] = []
        try:
            for index, (repository_id, raw_path) in enumerate(ordered):
                path = _pathlib.Path(raw_path)
                if not path.is_file():
                    raise FunctionalPyramidInstallationStoreError(
                        f"repository lifecycle store is unavailable: {repository_id}"
                    )
                alias = f"repo_{index}"
                self._connection.execute(
                    f'ATTACH DATABASE ? AS "{alias}"',
                    (str(path),),
                )
                aliases.append((repository_id, alias))
                row = self._connection.execute(
                    f'SELECT value FROM "{alias}".meta WHERE key="schema_version"'
                ).fetchone()
                if row is None or int(row["value"]) != REPOSITORY_SCHEMA_VERSION:
                    raise FunctionalPyramidInstallationStoreError(
                        f"repository store has incompatible schema: {repository_id}"
                    )
                mode = str(
                    self._connection.execute(
                        f'PRAGMA "{alias}".journal_mode'
                    ).fetchone()[0]
                )
                synchronous = int(
                    self._connection.execute(
                        f'PRAGMA "{alias}".synchronous'
                    ).fetchone()[0]
                )
                if mode.lower() in {"wal", "off", "memory"} or synchronous == 0:
                    raise FunctionalPyramidInstallationStoreError(
                        "repository store does not support atomic Functional Pyramid "
                        f"writes: {repository_id}"
                    )
            with immediate_transaction(self._connection):
                yield FunctionalPyramidInstallationTransaction(
                    self._connection,
                    tuple(aliases),
                )
        except _sqlite3.Error as exc:
            raise FunctionalPyramidInstallationStoreError(
                f"Functional Pyramid transaction failed: {exc}"
            ) from exc
        finally:
            for _, alias in reversed(aliases):
                try:
                    self._connection.execute(f'DETACH DATABASE "{alias}"')
                except _sqlite3.Error:
                    pass

    def reap_expired(self, moment: _datetime.datetime | None = None) -> int:
        """Reap installation-scoped replay receipts under the shared retention policy."""
        now = moment or self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("reap time must be timezone-aware")
        with immediate_transaction(self._connection) as connection:
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
