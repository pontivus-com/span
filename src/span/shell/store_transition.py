"""Offline schema-9 → schema-10 store transition (N-06, §8.3/§8.5).

This is the one canonical transition tool. It is deliberately raw: legacy
stores are inspected and exported by reading their observed SQLite catalog and
cell values directly. It never imports a legacy store constructor, reaper,
semantic decoder, or mutating upgrade helper, so the historical bytes keep
their original meaning instead of being reinterpreted by the runtime that is
being replaced.

The new runtime never migrates at open. This command performs the explicit,
separately authorized offline protocol:

    inspect → archive → stage → verify → activate → verify

Every step is recorded in a restart-safe manifest. ``inspect`` and ``verify``
are observational; ``apply`` owns archive/staging/activation; ``rollback``
restores a verified old store and preserves any new-format writes instead of
discarding them.
"""

from __future__ import annotations

import base64 as _base64
import contextlib as _contextlib
import dataclasses as _dataclasses
import datetime as _datetime
import enum as _enum
import hashlib as _hashlib
import json as _json
import math as _math
import os as _os
import pathlib as _pathlib
import shutil as _shutil
import sqlite3 as _sqlite3
import tempfile as _tempfile
import typing as _typing

from span.core import model as m
from span.ports.evidence import EvidenceSource

__all__ = [
    "LEGACY_TABLES",
    "SUPPORTED_SOURCE_SCHEMAS",
    "TARGET_SCHEMA",
    "TransitionConfig",
    "TransitionError",
    "TransitionManifest",
    "TransitionPaths",
    "TransitionPhase",
    "TransitionReport",
    "TransitionState",
    "TransitionStep",
    "apply",
    "dispatch",
    "inspect_store",
    "parse_phase",
    "report_payload",
    "rollback",
    "verify",
]


TARGET_SCHEMA = 10
SUPPORTED_SOURCE_SCHEMAS = frozenset({7, 8, 9})

#: Every table the schema-7/8/9 runtime could own. A table outside this set is
#: preserved and reported, never silently omitted.
LEGACY_TABLES = frozenset(
    {
        "repositories",
        "subjects",
        "claims",
        "relationships",
        "evidence_dependencies",
        "coverage_dependencies",
        "question_coverages",
        "premise_dependents",
        "question_result_refs",
        "conflict_records",
        "verification_records",
        "meta",
        "target_associations",
    }
)

_TRANSITIONS_DIR = "transitions"
_MANIFEST = "manifest.json"
_ARCHIVE = "archive.db"
_EXPORT = "export.jsonl"
_EXPORT_REPORT = "export-report.json"
_REPORT = "report.md"
_STAGING = "staging.db"
_PREVIOUS = "previous.db"
_SMOKE = "smoke.db"

_BLOB = "$span.blob"
_REAL = "$span.real"


class TransitionError(ValueError):
    """The transition cannot proceed without risking preserved data."""


class TransitionPhase(_enum.Enum):
    """Installer-visible transition phases."""

    INSPECT = "inspect"
    APPLY = "apply"
    VERIFY = "verify"
    ROLLBACK = "rollback"


class TransitionState(_enum.Enum):
    """Restart-safe position in the offline protocol."""

    MISSING = "MISSING"
    INSPECTED = "INSPECTED"
    ARCHIVED = "ARCHIVED"
    STAGED = "STAGED"
    ACTIVATED = "ACTIVATED"
    VERIFIED = "VERIFIED"
    ALREADY_CURRENT = "ALREADY_CURRENT"
    ROLLED_BACK = "ROLLED_BACK"


@_dataclasses.dataclass(frozen=True)
class TransitionConfig:
    """One explicit transition request (no inferred store or root)."""

    data_dir: _pathlib.Path
    repository_id: str
    root: str | None = None
    #: Free-space probe, injectable so a test can prove the refusal path
    #: without filling a real filesystem.
    free_bytes: _typing.Callable[[_pathlib.Path], int] = _dataclasses.field(
        default=lambda path: _shutil.disk_usage(path).free
    )
    clock: _typing.Callable[[], _datetime.datetime] = _dataclasses.field(
        default=lambda: _datetime.datetime.now(_datetime.timezone.utc)
    )

    def __post_init__(self) -> None:
        if not self.repository_id:
            raise TransitionError("transition requires an explicit repository id")
        if (
            "/" in self.repository_id
            or "\\" in self.repository_id
            or self.repository_id in {".", ".."}
        ):
            raise TransitionError(
                "repository id must be a plain identifier, not a path"
            )


@_dataclasses.dataclass(frozen=True)
class TransitionPaths:
    """Every path the protocol may read or own."""

    data_dir: _pathlib.Path
    repository_id: str

    @property
    def active(self) -> _pathlib.Path:
        return self.data_dir / f"{self.repository_id}.db"

    @property
    def transition_dir(self) -> _pathlib.Path:
        return self.data_dir / _TRANSITIONS_DIR / self.repository_id

    @property
    def manifest(self) -> _pathlib.Path:
        return self.transition_dir / _MANIFEST

    @property
    def archive(self) -> _pathlib.Path:
        return self.transition_dir / _ARCHIVE

    @property
    def export(self) -> _pathlib.Path:
        return self.transition_dir / _EXPORT

    @property
    def export_report(self) -> _pathlib.Path:
        return self.transition_dir / _EXPORT_REPORT

    @property
    def report(self) -> _pathlib.Path:
        return self.transition_dir / _REPORT

    @property
    def staging(self) -> _pathlib.Path:
        return self.transition_dir / _STAGING

    @property
    def previous(self) -> _pathlib.Path:
        return self.transition_dir / _PREVIOUS

    @property
    def smoke(self) -> _pathlib.Path:
        return self.transition_dir / _SMOKE


@_dataclasses.dataclass(frozen=True)
class TableInventory:
    """Observed columns, rows and value hash for one table."""

    name: str
    columns: tuple[str, ...]
    row_count: int
    sha256: str
    unknown: bool = False


@_dataclasses.dataclass(frozen=True)
class LegacyInspection:
    """Read-only facts about one observed legacy store."""

    path: _pathlib.Path
    exists: bool
    integrity: str
    schema_version: int | None
    tables: tuple[TableInventory, ...]
    repository_ids: tuple[str, ...]
    file_bytes: int
    logical_bytes: int
    empty_target_bytes: int
    required_free_bytes: int
    unknown_tables: tuple[str, ...]
    limitations: tuple[str, ...] = ()


@_dataclasses.dataclass(frozen=True)
class TransitionStep:
    """One completed manifest step (audit trail, not a semantic claim)."""

    name: str
    at: str
    detail: str = ""


@_dataclasses.dataclass(frozen=True)
class TransitionManifest:
    """Restart-safe record of one store transition."""

    repository_id: str
    source_path: str
    source_schema_version: int
    root: str
    state: TransitionState
    expected_active_schema: int
    archive_sha256: str
    export_sha256: str
    tables: tuple[TableInventory, ...]
    created_at: str
    updated_at: str
    build: str
    steps: tuple[TransitionStep, ...] = ()
    limitations: tuple[str, ...] = ()


@_dataclasses.dataclass(frozen=True)
class TransitionReport:
    """Machine-readable effect report for one phase."""

    phase: TransitionPhase
    state: TransitionState
    repository_id: str
    changed: bool
    effects: tuple[str, ...]
    inspection: LegacyInspection
    manifest: TransitionManifest | None
    limitations: tuple[str, ...] = ()


# -- value encoding -------------------------------------------------------


def _cell_to_json(value: object) -> object:
    """Encode one SQLite cell losslessly into JSON-compatible values.

    TEXT/INTEGER/NULL keep their native JSON form. BLOB keeps its exact bytes
    as base64 under a tagged object; NaN and infinities keep their exact float
    identity under a tagged object. No value is coerced to a different type.
    """
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if _math.isnan(value):
            return {_REAL: "nan"}
        if _math.isinf(value):
            return {_REAL: "inf" if value > 0 else "-inf"}
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {_BLOB: _base64.b64encode(bytes(value)).decode("ascii")}
    raise TransitionError(f"unsupported SQLite cell type: {type(value).__name__}")


def _canonical_row(values: _typing.Iterable[object]) -> str:
    return _json.dumps(
        [_cell_to_json(item) for item in values],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


# -- read-only inspection -------------------------------------------------


def _connect_read_only(path: _pathlib.Path) -> _sqlite3.Connection:
    uri = f"file:{_pathlib.Path(path).as_posix()}?mode=ro"
    return _sqlite3.connect(uri, uri=True)


def _table_names(connection: _sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master"
        " WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        " ORDER BY name"
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _columns(connection: _sqlite3.Connection, table: str) -> tuple[str, ...]:
    rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return tuple(str(row[1]) for row in rows)


def _row_order(connection: _sqlite3.Connection, table: str) -> str:
    columns = _columns(connection, table)
    if "rowid" in columns:
        return f'"{table}"'
    if not columns:
        return f'"{table}"'
    return f'"{table}" ORDER BY ' + ", ".join(f'"{name}"' for name in columns)


def _scan_table(
    connection: _sqlite3.Connection, table: str
) -> tuple[TableInventory, tuple[str, ...]]:
    columns = _columns(connection, table)
    digest = _hashlib.sha256()
    rows: list[str] = []
    count = 0
    for row in connection.execute(f"SELECT * FROM {_row_order(connection, table)}"):
        encoded = _canonical_row(row)
        digest.update(encoded.encode("utf-8"))
        digest.update(b"\n")
        rows.append(encoded)
        count += 1
    return (
        TableInventory(
            name=table,
            columns=columns,
            row_count=count,
            sha256=digest.hexdigest(),
            unknown=table not in LEGACY_TABLES,
        ),
        tuple(rows),
    )


def _read_schema_version(connection: _sqlite3.Connection) -> int | None:
    tables = _table_names(connection)
    if "meta" not in tables:
        return None
    try:
        row = connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
    except _sqlite3.DatabaseError:
        return None
    if row is None:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        raise TransitionError(
            "store meta.schema_version is not an integer; refusing to guess"
        ) from None


def _repository_ids(connection: _sqlite3.Connection) -> tuple[str, ...]:
    if "repositories" not in _table_names(connection):
        return ()
    try:
        rows = connection.execute(
            "SELECT repository_id FROM repositories ORDER BY repository_id"
        ).fetchall()
    except _sqlite3.DatabaseError:
        return ()
    return tuple(str(row[0]) for row in rows)


def _integrity(connection: _sqlite3.Connection) -> str:
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    except _sqlite3.DatabaseError as exc:
        raise TransitionError(f"store cannot be read: {exc}") from None
    return "ok" if row and str(row[0]) == "ok" else str(row[0] if row else "unknown")


def _logical_bytes(connection: _sqlite3.Connection) -> int:
    page_count = connection.execute("PRAGMA page_count").fetchone()
    page_size = connection.execute("PRAGMA page_size").fetchone()
    if not page_count or not page_size:
        return 0
    return int(page_count[0]) * int(page_size[0])


def _file_bytes(path: _pathlib.Path) -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        candidate = _pathlib.Path(str(path) + suffix)
        if candidate.is_file():
            total += candidate.stat().st_size
    return total


def _empty_target_bytes() -> int:
    """Measured size of an empty schema-10 store (not an invented floor)."""
    connection = _sqlite3.connect(":memory:")
    try:
        from span.shell.sqlite_store.lifecycle import _DDL

        for statement in _DDL:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', '10')"
        )
        connection.commit()
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        return int(page_count) * int(page_size)
    finally:
        connection.close()


def inspect_store(config: TransitionConfig) -> LegacyInspection:
    """Read every observable fact without creating, migrating or reaping."""
    paths = TransitionPaths(config.data_dir, config.repository_id)
    source = paths.active
    if not source.is_file():
        return LegacyInspection(
            path=source,
            exists=False,
            integrity="missing",
            schema_version=None,
            tables=(),
            repository_ids=(),
            file_bytes=0,
            logical_bytes=0,
            empty_target_bytes=_empty_target_bytes(),
            required_free_bytes=0,
            unknown_tables=(),
            limitations=(
                f"no store at {source}; explicit initialize_repository creates "
                "a new schema-10 store instead of a transition",
            ),
        )
    connection = _connect_read_only(source)
    try:
        integrity = _integrity(connection)
        version = _read_schema_version(connection)
        tables = tuple(
            _scan_table(connection, table)[0] for table in _table_names(connection)
        )
        logical = _logical_bytes(connection)
    finally:
        connection.close()
    file_bytes = _file_bytes(source)
    empty_target = _empty_target_bytes()
    # Archive copy + lossless export (raw rows cannot exceed the logical
    # database bytes) + one empty schema-10 store.
    required = file_bytes + logical + empty_target
    limitations: list[str] = []
    if version is None:
        limitations.append(
            "store has no readable meta.schema_version; apply is refused"
        )
    elif version not in SUPPORTED_SOURCE_SCHEMAS:
        limitations.append(
            f"schema {version} is not a supported transition source "
            f"({sorted(SUPPORTED_SOURCE_SCHEMAS)})"
        )
    if config.root is not None:
        root_name = _pathlib.Path(config.root).name
        if root_name != config.repository_id:
            limitations.append(
                f"supplied root {config.root!r} does not derive repository id "
                f"{config.repository_id!r}"
            )
    unknown = tuple(item.name for item in tables if item.unknown)
    if unknown:
        limitations.append(
            "unknown tables preserved and exported: " + ", ".join(unknown)
        )
    return LegacyInspection(
        path=source,
        exists=True,
        integrity=integrity,
        schema_version=version,
        tables=tables,
        repository_ids=_repository_ids_ro(source),
        file_bytes=file_bytes,
        logical_bytes=logical,
        empty_target_bytes=empty_target,
        required_free_bytes=required,
        unknown_tables=unknown,
        limitations=tuple(limitations),
    )


def _repository_ids_ro(path: _pathlib.Path) -> tuple[str, ...]:
    connection = _connect_read_only(path)
    try:
        return _repository_ids(connection)
    finally:
        connection.close()


# -- manifest -------------------------------------------------------------


def _utc(moment: _datetime.datetime) -> str:
    return moment.astimezone(_datetime.timezone.utc).isoformat()


def _table_payload(item: TableInventory) -> dict[str, object]:
    return {
        "name": item.name,
        "columns": list(item.columns),
        "row_count": item.row_count,
        "sha256": item.sha256,
        "unknown": item.unknown,
    }


def _manifest_payload(manifest: TransitionManifest) -> dict[str, object]:
    return {
        "repository_id": manifest.repository_id,
        "source_path": manifest.source_path,
        "source_schema_version": manifest.source_schema_version,
        "root": manifest.root,
        "state": manifest.state.value,
        "expected_active_schema": manifest.expected_active_schema,
        "archive_sha256": manifest.archive_sha256,
        "export_sha256": manifest.export_sha256,
        "tables": [_table_payload(item) for item in manifest.tables],
        "created_at": manifest.created_at,
        "updated_at": manifest.updated_at,
        "build": manifest.build,
        "steps": [
            {"name": step.name, "at": step.at, "detail": step.detail}
            for step in manifest.steps
        ],
        "limitations": list(manifest.limitations),
    }


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        raise TransitionError("transition manifest integer field is a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TransitionError(
        f"transition manifest integer field has type {type(value).__name__}"
    )


def _manifest_from_payload(payload: dict[str, object]) -> TransitionManifest:
    try:
        return TransitionManifest(
            repository_id=str(payload["repository_id"]),
            source_path=str(payload["source_path"]),
            source_schema_version=_as_int(payload["source_schema_version"]),
            root=str(payload["root"]),
            state=TransitionState(str(payload["state"])),
            expected_active_schema=_as_int(payload["expected_active_schema"]),
            archive_sha256=str(payload["archive_sha256"]),
            export_sha256=str(payload["export_sha256"]),
            tables=tuple(
                TableInventory(
                    name=str(item["name"]),
                    columns=tuple(str(name) for name in item["columns"]),
                    row_count=_as_int(item["row_count"]),
                    sha256=str(item["sha256"]),
                    unknown=bool(item["unknown"]),
                )
                for item in _typing.cast(list, payload["tables"])
            ),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            build=str(payload["build"]),
            steps=tuple(
                TransitionStep(
                    name=str(item["name"]),
                    at=str(item["at"]),
                    detail=str(item.get("detail", "")),
                )
                for item in _typing.cast(list, payload["steps"])
            ),
            limitations=tuple(
                str(item)
                for item in _typing.cast(
                    tuple[object, ...], payload.get("limitations", ())
                )
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TransitionError(f"transition manifest is not readable: {exc}") from None


def _read_manifest(paths: TransitionPaths) -> TransitionManifest | None:
    if not paths.manifest.is_file():
        return None
    try:
        payload = _json.loads(paths.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TransitionError(
            f"transition manifest is unreadable: {exc}; preserved in place"
        ) from None
    if not isinstance(payload, dict):
        raise TransitionError("transition manifest is not an object")
    return _manifest_from_payload(payload)


def _fsync_file(path: _pathlib.Path) -> None:
    with open(path, "rb") as handle:
        _os.fsync(handle.fileno())


def _fsync_dir(path: _pathlib.Path) -> None:
    descriptor = _os.open(str(path), _os.O_RDONLY)
    try:
        _os.fsync(descriptor)
    finally:
        _os.close(descriptor)


def _write_manifest(paths: TransitionPaths, manifest: TransitionManifest) -> None:
    paths.transition_dir.mkdir(parents=True, exist_ok=True)
    temporary = paths.manifest.with_suffix(".json.partial")
    temporary.write_text(
        _json.dumps(_manifest_payload(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _fsync_file(temporary)
    _os.replace(temporary, paths.manifest)
    _fsync_dir(paths.transition_dir)


def _advance(
    manifest: TransitionManifest,
    state: TransitionState,
    step: str,
    *,
    clock: _typing.Callable[[], _datetime.datetime],
    detail: str = "",
    archive_sha256: str | None = None,
    export_sha256: str | None = None,
    tables: tuple[TableInventory, ...] | None = None,
    limitations: tuple[str, ...] | None = None,
) -> TransitionManifest:
    return _dataclasses.replace(
        manifest,
        state=state,
        updated_at=_utc(clock()),
        steps=manifest.steps
        + (TransitionStep(name=step, at=_utc(clock()), detail=detail),),
        archive_sha256=(
            manifest.archive_sha256 if archive_sha256 is None else archive_sha256
        ),
        export_sha256=(
            manifest.export_sha256 if export_sha256 is None else export_sha256
        ),
        tables=manifest.tables if tables is None else tables,
        limitations=manifest.limitations if limitations is None else limitations,
    )


def _build_identity() -> str:
    from span import __version__

    return f"span-mcp {__version__}"


# -- archive and export ---------------------------------------------------


@_contextlib.contextmanager
def _exclusive_source(path: _pathlib.Path) -> _typing.Iterator[_sqlite3.Connection]:
    """Hold SQLite exclusive ownership for the whole archive-to-activate span.

    ``locking_mode=EXCLUSIVE`` keeps the file lock after the first write
    transaction until this connection closes. The backup runs from this same
    connection (the backup API cannot run inside an open transaction), so a
    live SQLite writer is refused for the full protocol, not just for a probe.
    """
    connection = _sqlite3.connect(str(path), timeout=1.0, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 1000")
    connection.execute("PRAGMA locking_mode = EXCLUSIVE")
    try:
        try:
            connection.execute("BEGIN EXCLUSIVE")
        except _sqlite3.OperationalError as exc:
            raise TransitionError(
                "store is held by a live process; stop the old server and "
                f"hooks before transitioning it ({exc})"
            ) from None
        connection.execute("COMMIT")
    except BaseException:
        connection.close()
        raise
    try:
        yield connection
    finally:
        connection.close()


def _archive(
    paths: TransitionPaths,
    config: TransitionConfig,
    source: _sqlite3.Connection,
) -> str:
    paths.transition_dir.mkdir(parents=True, exist_ok=True)
    partial = paths.archive.with_suffix(".db.partial")
    destination = _sqlite3.connect(str(partial))
    try:
        source.backup(destination)
    finally:
        destination.close()
    _fsync_file(partial)
    _os.replace(partial, paths.archive)
    _fsync_dir(paths.transition_dir)
    return _sha256_file(paths.archive)


def _sha256_file(path: _pathlib.Path) -> str:
    digest = _hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _export(paths: TransitionPaths) -> tuple[tuple[TableInventory, ...], str]:
    """Write raw rows for every table and one readable historical report."""
    connection = _connect_read_only(paths.archive)
    partial = paths.export.with_suffix(".jsonl.partial")
    report_partial = paths.export_report.with_suffix(".json.partial")
    inventory: list[TableInventory] = []
    try:
        integrity = _integrity(connection)
        if integrity != "ok":
            raise TransitionError(
                f"archive failed integrity check: {integrity}; preserved in place"
            )
        with open(partial, "w", encoding="utf-8") as stream:
            for table in _table_names(connection):
                item, rows = _scan_table(connection, table)
                stream.write(
                    _json.dumps(
                        {
                            "table": item.name,
                            "columns": list(item.columns),
                            "unknown": item.unknown,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                for row in rows:
                    stream.write(row + "\n")
                stream.write(
                    _json.dumps(
                        {
                            "table": item.name,
                            "rows": item.row_count,
                            "sha256": item.sha256,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                inventory.append(item)
        _fsync_file(partial)
        _os.replace(partial, paths.export)
        report_partial.write_text(
            _json.dumps(
                {
                    "source": str(paths.archive),
                    "archive_sha256": _sha256_file(paths.archive),
                    "tables": [_table_payload(item) for item in inventory],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _fsync_file(report_partial)
        _os.replace(report_partial, paths.export_report)
        paths.report.write_text(
            _readable_report(connection, tuple(inventory)),
            encoding="utf-8",
        )
        _fsync_file(paths.report)
    finally:
        connection.close()
    _fsync_dir(paths.transition_dir)
    return tuple(inventory), _sha256_file(paths.export)


def _readable_report(
    connection: _sqlite3.Connection, inventory: tuple[TableInventory, ...]
) -> str:
    """Human-readable historical projection; every grouping is labelled."""
    lines = [
        "# Span legacy store export",
        "",
        "This is a raw historical export. It is not current Span understanding",
        "and no row here is presented as a supported conclusion.",
        "",
        "## Tables",
        "",
        "| Table | Rows | SHA-256 |",
        "| --- | --- | --- |",
    ]
    for item in inventory:
        label = item.name + (" (unknown)" if item.unknown else "")
        lines.append(f"| {label} | {item.row_count} | `{item.sha256}` |")
    tables = {item.name for item in inventory}
    if "claims" in tables and "subjects" in tables:
        lines += [
            "",
            "## Historical claims by subject",
            "",
            "Grouping reuses the legacy association only. It does not create an",
            "understanding, a conclusion revision, or current support.",
            "",
        ]
        try:
            rows = connection.execute(
                "SELECT subject_locator, claim_id, kind FROM claims"
                " ORDER BY subject_locator, claim_id"
            ).fetchall()
        except _sqlite3.DatabaseError as exc:
            lines.append(f"claims could not be grouped: {exc}")
        else:
            current = None
            for locator, claim_id, kind in rows:
                if locator != current:
                    lines += ["", f"### `{locator}`", ""]
                    current = locator
                lines.append(f"- claim `{claim_id}` ({kind})")
    for name, columns in (
        ("question_coverages", "question_class, question_slice, disposition"),
        ("target_associations", "target_id, last_touched_at, expires_at"),
        ("conflict_records", "left_id, right_id"),
    ):
        if name not in tables:
            continue
        lines += ["", f"## {name}", ""]
        try:
            rows = connection.execute(
                f"SELECT {columns} FROM {name} ORDER BY 1, 2"
            ).fetchall()
        except _sqlite3.DatabaseError as exc:
            lines.append(f"{name} could not be listed: {exc}")
            continue
        for row in rows:
            lines.append("- " + " | ".join(str(value) for value in row))
    lines.append("")
    return "\n".join(lines)


def _reconcile_export(paths: TransitionPaths) -> tuple[TableInventory, ...]:
    """Recompute counts/hashes from the archive and compare the export."""
    if not paths.export_report.is_file() or not paths.export.is_file():
        raise TransitionError("archive export is missing; run apply again")
    try:
        report = _json.loads(paths.export_report.read_text(encoding="utf-8"))
        recorded = {
            str(item["name"]): TableInventory(
                name=str(item["name"]),
                columns=tuple(str(name) for name in item["columns"]),
                row_count=int(item["row_count"]),
                sha256=str(item["sha256"]),
                unknown=bool(item["unknown"]),
            )
            for item in _typing.cast(list, report["tables"])
        }
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise TransitionError(
            f"export report is not readable: {exc}; preserved in place"
        ) from None
    connection = _connect_read_only(paths.archive)
    try:
        if _integrity(connection) != "ok":
            raise TransitionError("archive integrity check failed during verify")
        observed = {
            item.name: item
            for item in (
                _scan_table(connection, table)[0] for table in _table_names(connection)
            )
        }
    finally:
        connection.close()
    if set(observed) != set(recorded):
        raise TransitionError(
            "archive/export table sets differ: "
            f"{sorted(set(observed) ^ set(recorded))}"
        )
    for name, item in observed.items():
        other = recorded[name]
        if item.row_count != other.row_count or item.sha256 != other.sha256:
            raise TransitionError(
                f"archive/export mismatch for table {name}: "
                f"{item.row_count}/{item.sha256[:12]} vs "
                f"{other.row_count}/{other.sha256[:12]}"
            )
    return tuple(observed[name] for name in sorted(observed))


# -- staging and activation ----------------------------------------------


def _legacy_binding(
    paths: TransitionPaths, repository_id: str
) -> tuple[tuple[m.EvidenceRef, ...], tuple[str, ...]]:
    """Read repository binding seeds verbatim; validate, never reinterpret."""
    connection = _connect_read_only(paths.archive)
    try:
        if "repositories" not in _table_names(connection):
            return (), ("archive has no repositories table; no seeds imported",)
        columns = _columns(connection, "repositories")
        if "authority_seeds_json" not in columns:
            return (), (
                "archive repositories table has no authority_seeds_json; "
                "no seeds imported",
            )
        row = connection.execute(
            "SELECT authority_seeds_json FROM repositories" " WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
    except _sqlite3.DatabaseError as exc:
        raise TransitionError(f"repository binding is unreadable: {exc}") from None
    finally:
        connection.close()
    if row is None:
        return (), (
            f"archive has no repositories row for {repository_id}; "
            "no binding imported",
        )
    try:
        payload = _json.loads(row[0])
        if not isinstance(payload, list):
            raise ValueError("authority seeds are not a list")
        seeds = tuple(m.from_canonical(m.EvidenceRef, item) for item in payload)
    except (TypeError, ValueError) as exc:
        raise TransitionError(
            f"archive authority seeds are not canonical: {exc}; "
            "preserved in place, nothing imported"
        ) from None
    for seed in seeds:
        if seed.repository_id != repository_id:
            raise TransitionError(
                "archive authority seed belongs to another repository: "
                f"{seed.repository_id}"
            )
    return seeds, ()


def _stage(
    paths: TransitionPaths,
    config: TransitionConfig,
    root: str,
) -> tuple[
    tuple[TableInventory, ...],
    tuple[str, ...],
]:
    from span.shell.sqlite_store.lifecycle import SCHEMA_VERSION, LifecycleStore
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION

    for stale in (paths.staging, paths.smoke):
        if stale.exists():
            stale.unlink()
    seeds, limitations = _legacy_binding(paths, config.repository_id)
    store = LifecycleStore(paths.staging, retention=DEFAULT_LIFECYCLE_RETENTION)
    try:
        if SCHEMA_VERSION != TARGET_SCHEMA:
            raise TransitionError(
                f"staged store schema {SCHEMA_VERSION} is not the expected "
                f"transition target {TARGET_SCHEMA}"
            )
        store.register_repository(config.repository_id, root, authority_seeds=seeds)
    finally:
        store.close()
    _fsync_file(paths.staging)
    _fsync_dir(paths.transition_dir)
    return (), limitations


def _semantic_counts(path: _pathlib.Path) -> dict[str, int]:
    connection = _connect_read_only(path)
    try:
        tables = set(_table_names(connection))
        counts: dict[str, int] = {}
        for table in (
            "understandings",
            "understanding_versions",
            "conclusions",
            "challenges",
            "verification_runs",
            "record_receipts",
        ):
            if table in tables:
                counts[table] = int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
            else:
                counts[table] = 0
        return counts
    finally:
        connection.close()


def _verify_staged(
    paths: TransitionPaths,
    config: TransitionConfig,
    root: str,
    expected: tuple[TableInventory, ...],
) -> tuple[str, ...]:
    """Verify one candidate active/staging store without mutating it."""
    if not paths.staging.is_file():
        raise TransitionError("staging store is missing; run apply again")
    reconciled = _reconcile_export(paths)
    if tuple((item.name, item.row_count, item.sha256) for item in reconciled) != (
        tuple((item.name, item.row_count, item.sha256) for item in expected)
    ):
        raise TransitionError("archive/export reconciliation changed during apply")
    connection = _connect_read_only(paths.staging)
    try:
        if _integrity(connection) != "ok":
            raise TransitionError("staged store failed integrity check")
        version = _read_schema_version(connection)
        if version != TARGET_SCHEMA:
            raise TransitionError(
                f"staged store reports schema {version}, expected {TARGET_SCHEMA}"
            )
        row = connection.execute(
            "SELECT repository_id, root FROM repositories" " WHERE repository_id=?",
            (config.repository_id,),
        ).fetchone()
        if row is None:
            raise TransitionError("staged store has no repository binding")
        if str(row[1]) != root:
            raise TransitionError(
                f"staged store root {row[1]!r} does not match {root!r}"
            )
    finally:
        connection.close()
    counts = _semantic_counts(paths.staging)
    if any(counts.values()):
        raise TransitionError(
            "staged store contains migrated semantic content: "
            + ", ".join(f"{name}={count}" for name, count in counts.items())
        )
    _smoke(paths, config)
    return (
        "staged store is schema 10 with the bound root and no semantic rows",
        "fresh lifecycle smoke test passed on an isolated copy",
    )


def _smoke(paths: TransitionPaths, config: TransitionConfig) -> None:
    """Exercise a fresh lifecycle on an isolated copy, never the store."""
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore
    from span.service.lifecycle import LifecycleService
    from span.service.support import SupportService

    with _tempfile.TemporaryDirectory(prefix="span-transition-smoke-") as tmp:
        copy = _pathlib.Path(tmp) / "smoke.db"
        _shutil.copy2(paths.staging, copy)
        store = LifecycleStore(copy, retention=DEFAULT_LIFECYCLE_RETENTION)
        try:

            class _NoEvidence:
                def read_exact(self, *_args: object, **_kwargs: object) -> object:
                    raise TransitionError("smoke test must not read sources")

                def list_inventory_entries(
                    self, *_args: object, **_kwargs: object
                ) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
                    return (), {}

            support = SupportService(
                store=store,
                evidence=_typing.cast(EvidenceSource, _NoEvidence()),
                authority=store,
                clock=config.clock,
            )
            service = LifecycleService(
                store=store,
                authority=store,
                support=support,
                clock=config.clock,
            )
            context = service.start_context(
                m.StartContextRequest(
                    repository_id=config.repository_id,
                    request_id=m.RequestId("transition-smoke"),
                    scope=m.EvidenceScope(),
                    question="transition smoke test",
                )
            )
            recovered = service.start_context(
                m.StartContextRequest(
                    repository_id=config.repository_id,
                    request_id=m.RequestId("transition-smoke"),
                    scope=m.EvidenceScope(),
                    question="transition smoke test",
                )
            )
            if recovered.context_id != context.context_id:
                raise TransitionError("smoke test context is not recoverable")
        finally:
            store.close()


def _activate(
    paths: TransitionPaths,
    *,
    clock: _typing.Callable[[], _datetime.datetime],
) -> tuple[str, ...]:
    effects: list[str] = []
    if paths.active.exists():
        if paths.previous.exists():
            preserved = paths.transition_dir / (
                "previous-" + _utc(clock()).replace(":", "").replace("+", "_") + ".db"
            )
            _os.replace(paths.previous, preserved)
            effects.append(f"preserved older previous store at {preserved}")
        _os.replace(paths.active, paths.previous)
        _fsync_dir(paths.data_dir)
        effects.append(f"preserved old active store at {paths.previous}")
    _os.replace(paths.staging, paths.active)
    _fsync_file(paths.active)
    _fsync_dir(paths.data_dir)
    effects.append(f"activated schema-{TARGET_SCHEMA} store at {paths.active}")
    return tuple(effects)


# -- public phases --------------------------------------------------------


def inspect_store_report(
    config: TransitionConfig,
) -> tuple[LegacyInspection, TransitionManifest | None, TransitionState]:
    paths = TransitionPaths(config.data_dir, config.repository_id)
    inspection = inspect_store(config)
    manifest = _read_manifest(paths)
    if not inspection.exists:
        state = TransitionState.MISSING
    elif inspection.schema_version == TARGET_SCHEMA:
        state = TransitionState.ALREADY_CURRENT
    elif manifest is not None:
        state = manifest.state
    else:
        state = TransitionState.INSPECTED
    return inspection, manifest, state


def _require_transitionable(
    config: TransitionConfig,
    inspection: LegacyInspection,
    root: str,
) -> None:
    if not inspection.exists:
        raise TransitionError(f"no store at {inspection.path}; nothing to transition")
    if inspection.schema_version == TARGET_SCHEMA:
        raise TransitionError("store is already schema 10; use inspect or verify")
    if inspection.schema_version not in SUPPORTED_SOURCE_SCHEMAS:
        raise TransitionError(
            f"unsupported source schema {inspection.schema_version}; "
            "preserve the file and supply a supported schema 7/8/9 store "
            "or re-record with explicit interpretation"
        )
    if inspection.integrity != "ok":
        raise TransitionError(
            f"source integrity check failed: {inspection.integrity}; "
            "nothing was changed"
        )
    actual_root = _pathlib.Path(root).resolve()
    if not actual_root.is_dir():
        raise TransitionError(f"transition root is not a directory: {root}")
    if actual_root.name != config.repository_id:
        raise TransitionError(
            f"root {root!r} derives repository id {actual_root.name!r}, "
            f"not {config.repository_id!r}"
        )


def _check_space(config: TransitionConfig, inspection: LegacyInspection) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    free = int(config.free_bytes(config.data_dir))
    if free < inspection.required_free_bytes:
        raise TransitionError(
            "insufficient free space for a lossless transition: "
            f"{free} bytes free, {inspection.required_free_bytes} required "
            "(archive copy + raw export + staged schema-10 store)"
        )


def apply(config: TransitionConfig) -> TransitionReport:
    """Archive, stage, verify and activate one store (the only mutating phase)."""
    if config.root is None:
        raise TransitionError(
            "apply requires an explicit --transition-root repository path"
        )
    root = str(_pathlib.Path(config.root).resolve())
    paths = TransitionPaths(config.data_dir, config.repository_id)
    inspection = inspect_store(config)
    _require_transitionable(config, inspection, root)
    _check_space(config, inspection)
    effects: list[str] = []
    limitations: list[str] = list(inspection.limitations)
    with _exclusive_source(paths.active) as source:
        manifest = _open_manifest(config, paths, inspection, root)
        manifest, step_effects, step_limits = _archive_step(
            config, paths, manifest, root, source
        )
        effects.extend(step_effects)
        limitations.extend(step_limits)
        for step in (_export_step, _stage_step, _activate_step):
            manifest, step_effects, step_limits = step(config, paths, manifest, root)
            effects.extend(step_effects)
            limitations.extend(step_limits)
    return TransitionReport(
        phase=TransitionPhase.APPLY,
        state=manifest.state,
        repository_id=config.repository_id,
        changed=True,
        effects=tuple(effects),
        inspection=inspection,
        manifest=manifest,
        limitations=tuple(limitations),
    )


def _open_manifest(
    config: TransitionConfig,
    paths: TransitionPaths,
    inspection: LegacyInspection,
    root: str,
) -> TransitionManifest:
    existing = _read_manifest(paths)
    now = _utc(config.clock())
    if existing is None:
        manifest = TransitionManifest(
            repository_id=config.repository_id,
            source_path=str(paths.active),
            source_schema_version=_typing.cast(int, inspection.schema_version),
            root=root,
            state=TransitionState.INSPECTED,
            expected_active_schema=TARGET_SCHEMA,
            archive_sha256="",
            export_sha256="",
            tables=(),
            created_at=now,
            updated_at=now,
            build=_build_identity(),
            limitations=inspection.limitations,
        )
        _write_manifest(paths, manifest)
        return manifest
    if (
        existing.repository_id != config.repository_id
        or existing.root != root
        or existing.source_schema_version != inspection.schema_version
    ):
        raise TransitionError(
            "an unfinished transition for this repository has different "
            "binding facts; inspect it before reusing or removing it"
        )
    if existing.state in {
        TransitionState.ACTIVATED,
        TransitionState.VERIFIED,
    }:
        raise TransitionError(
            "store transition is already activated; use verify or rollback"
        )
    return existing


def _archive_step(
    config: TransitionConfig,
    paths: TransitionPaths,
    manifest: TransitionManifest,
    _root: str,
    source: _sqlite3.Connection,
) -> tuple[TransitionManifest, tuple[str, ...], tuple[str, ...]]:
    if manifest.state is not TransitionState.INSPECTED:
        if not paths.archive.is_file():
            raise TransitionError("manifest claims archive but the file is missing")
        return manifest, (), ()
    archive_hash = _archive(paths, config, source)
    manifest = _advance(
        manifest,
        TransitionState.ARCHIVED,
        "archive",
        clock=config.clock,
        detail=f"sha256 {archive_hash}",
        archive_sha256=archive_hash,
    )
    _write_manifest(paths, manifest)
    return (
        manifest,
        (f"archived WAL-consistent store at {paths.archive}",),
        (),
    )


def _export_step(
    config: TransitionConfig,
    paths: TransitionPaths,
    manifest: TransitionManifest,
    _root: str,
) -> tuple[TransitionManifest, tuple[str, ...], tuple[str, ...]]:
    if manifest.state is not TransitionState.ARCHIVED:
        return manifest, (), ()
    tables, export_hash = _export(paths)
    manifest = _advance(
        manifest,
        TransitionState.STAGED,
        "export",
        clock=config.clock,
        detail=f"{len(tables)} tables",
        tables=tables,
        export_sha256=export_hash,
    )
    _write_manifest(paths, manifest)
    return (
        manifest,
        (f"wrote lossless raw export at {paths.export}",),
        (),
    )


def _stage_step(
    config: TransitionConfig,
    paths: TransitionPaths,
    manifest: TransitionManifest,
    root: str,
) -> tuple[TransitionManifest, tuple[str, ...], tuple[str, ...]]:
    if manifest.state is not TransitionState.STAGED:
        return manifest, (), ()
    _, binding_limitations = _stage(paths, config, root)
    effects = [f"staged schema-{TARGET_SCHEMA} store at {paths.staging}"]
    effects.extend(_verify_staged(paths, config, root, manifest.tables))
    manifest = _advance(
        manifest,
        TransitionState.ACTIVATED,
        "stage-and-verify",
        clock=config.clock,
        detail="staging verified before activation",
        limitations=tuple(dict.fromkeys((*manifest.limitations, *binding_limitations))),
    )
    _write_manifest(paths, manifest)
    return manifest, tuple(effects), binding_limitations


def _activate_step(
    config: TransitionConfig,
    paths: TransitionPaths,
    manifest: TransitionManifest,
    _root: str,
) -> tuple[TransitionManifest, tuple[str, ...], tuple[str, ...]]:
    if manifest.state is not TransitionState.ACTIVATED:
        return manifest, (), ()
    effects = _activate(paths, clock=config.clock)
    manifest = _advance(
        manifest,
        TransitionState.VERIFIED,
        "activate",
        clock=config.clock,
        detail="schema-10 store is active",
    )
    _write_manifest(paths, manifest)
    return manifest, effects, ()


def verify(config: TransitionConfig) -> TransitionReport:
    """Re-check a transition without mutating any store."""
    paths = TransitionPaths(config.data_dir, config.repository_id)
    inspection = inspect_store(config)
    manifest = _read_manifest(paths)
    if manifest is None:
        if inspection.schema_version == TARGET_SCHEMA:
            _verify_active_binding(paths, config)
            return TransitionReport(
                phase=TransitionPhase.VERIFY,
                state=TransitionState.ALREADY_CURRENT,
                repository_id=config.repository_id,
                changed=False,
                effects=("active store is schema 10 with no transition manifest",),
                inspection=inspection,
                manifest=None,
                limitations=inspection.limitations,
            )
        raise TransitionError(
            "no transition manifest for this repository; run inspect/apply first"
        )
    if manifest.repository_id != config.repository_id:
        raise TransitionError("transition manifest belongs to another repository")
    if inspection.schema_version != TARGET_SCHEMA:
        raise TransitionError(
            "active store is not schema 10; the transition is not activated"
        )
    effects = [
        "active store opens as schema 10",
        f"archive integrity: {inspection.integrity}",
    ]
    reconciled = _reconcile_export(paths)
    effects.append(f"archive/export reconcile for {len(reconciled)} tables")
    recorded = {(item.name, item.row_count, item.sha256) for item in manifest.tables}
    observed = {(item.name, item.row_count, item.sha256) for item in reconciled}
    if recorded != observed:
        raise TransitionError(
            "archive/export no longer matches the recorded transition manifest"
        )
    _verify_active_binding(paths, config)
    effects.append("active root binding matches the transition manifest")
    counts = _semantic_counts(paths.active)
    effects.append(
        "no legacy rows were promoted as current semantic content "
        f"({', '.join(f'{name}={count}' for name, count in counts.items())})"
    )
    return TransitionReport(
        phase=TransitionPhase.VERIFY,
        state=manifest.state,
        repository_id=config.repository_id,
        changed=False,
        effects=tuple(effects),
        inspection=inspection,
        manifest=manifest,
        limitations=manifest.limitations,
    )


def _verify_active_binding(paths: TransitionPaths, config: TransitionConfig) -> None:
    connection = _connect_read_only(paths.active)
    try:
        if _integrity(connection) != "ok":
            raise TransitionError("active store failed integrity check")
        row = connection.execute(
            "SELECT root FROM repositories WHERE repository_id=?",
            (config.repository_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise TransitionError("active store has no binding for this repository")
    if config.root is not None:
        expected = str(_pathlib.Path(config.root).resolve())
        if str(row[0]) != expected:
            raise TransitionError(
                f"active root binding {row[0]!r} does not match {expected!r}"
            )


def rollback(config: TransitionConfig) -> TransitionReport:
    """Discard owned staging, or restore the old store after activation."""
    paths = TransitionPaths(config.data_dir, config.repository_id)
    inspection = inspect_store(config)
    manifest = _read_manifest(paths)
    if manifest is None:
        raise TransitionError("no transition manifest to roll back")
    if manifest.state not in {
        TransitionState.INSPECTED,
        TransitionState.ARCHIVED,
        TransitionState.STAGED,
        TransitionState.ACTIVATED,
        TransitionState.VERIFIED,
    }:
        raise TransitionError(
            f"transition state {manifest.state.value} cannot be rolled back"
        )
    effects: list[str] = []
    if manifest.state in {
        TransitionState.INSPECTED,
        TransitionState.ARCHIVED,
        TransitionState.STAGED,
    }:
        for owned in (paths.staging, paths.smoke):
            if owned.exists():
                owned.unlink()
                effects.append(f"discarded owned staging file {owned}")
        manifest = _advance(
            manifest,
            TransitionState.ROLLED_BACK,
            "rollback-pre-activation",
            clock=config.clock,
        )
        _write_manifest(paths, manifest)
        return TransitionReport(
            phase=TransitionPhase.ROLLBACK,
            state=manifest.state,
            repository_id=config.repository_id,
            changed=bool(effects),
            effects=tuple(effects),
            inspection=inspection,
            manifest=manifest,
            limitations=manifest.limitations,
        )
    if paths.active.exists():
        with _exclusive_source(paths.active) as source:
            if _read_schema_version(source) != TARGET_SCHEMA:
                raise TransitionError(
                    "active store is not the schema-10 store this manifest "
                    "owns; refusing to move it"
                )
            preserved = paths.transition_dir / (
                "new-format-"
                + _utc(config.clock()).replace(":", "").replace("+", "_")
                + ".db"
            )
            _os.replace(paths.active, preserved)
            effects.append(f"preserved new-format writes at {preserved}")
    if paths.previous.is_file():
        if _read_schema_version_ro(paths.previous) not in (SUPPORTED_SOURCE_SCHEMAS):
            raise TransitionError(
                "preserved previous store is not a supported legacy schema; "
                "leaving both stores in place"
            )
        _os.replace(paths.previous, paths.active)
        _fsync_dir(paths.data_dir)
        effects.append(f"restored verified legacy store at {paths.active}")
    else:
        effects.append("no previous store existed; active store left absent")
    manifest = _advance(
        manifest,
        TransitionState.ROLLED_BACK,
        "rollback-post-activation",
        clock=config.clock,
    )
    _write_manifest(paths, manifest)
    return TransitionReport(
        phase=TransitionPhase.ROLLBACK,
        state=manifest.state,
        repository_id=config.repository_id,
        changed=bool(effects),
        effects=tuple(effects),
        inspection=inspection,
        manifest=manifest,
        limitations=manifest.limitations,
    )


def _read_schema_version_ro(path: _pathlib.Path) -> int | None:
    connection = _connect_read_only(path)
    try:
        return _read_schema_version(connection)
    finally:
        connection.close()


def parse_phase(value: str) -> TransitionPhase:
    """Parse the installer-visible phase name; reject anything else."""
    try:
        return TransitionPhase(value)
    except ValueError:
        raise TransitionError(
            f"unknown transition phase {value!r}; use inspect, apply, verify "
            "or rollback"
        ) from None


def report_payload(report: TransitionReport) -> dict[str, object]:
    """Canonical machine-readable report for the installer command."""
    inspection = report.inspection
    return {
        "phase": report.phase.value,
        "state": report.state.value,
        "repository_id": report.repository_id,
        "changed": report.changed,
        "effects": list(report.effects),
        "inspection": {
            "path": str(inspection.path),
            "exists": inspection.exists,
            "integrity": inspection.integrity,
            "schema_version": inspection.schema_version,
            "repository_ids": list(inspection.repository_ids),
            "tables": [_table_payload(item) for item in inspection.tables],
            "file_bytes": inspection.file_bytes,
            "logical_bytes": inspection.logical_bytes,
            "required_free_bytes": inspection.required_free_bytes,
            "unknown_tables": list(inspection.unknown_tables),
        },
        "manifest": (
            _manifest_payload(report.manifest) if report.manifest is not None else None
        ),
        "limitations": list(report.limitations),
    }


def dispatch(config: TransitionConfig, phase: TransitionPhase) -> TransitionReport:
    """One implementation behind every installer transition invocation."""
    if phase is TransitionPhase.INSPECT:
        inspection, manifest, state = inspect_store_report(config)
        return TransitionReport(
            phase=phase,
            state=state,
            repository_id=config.repository_id,
            changed=False,
            effects=(),
            inspection=inspection,
            manifest=manifest,
            limitations=inspection.limitations,
        )
    if phase is TransitionPhase.APPLY:
        return apply(config)
    if phase is TransitionPhase.VERIFY:
        return verify(config)
    if phase is TransitionPhase.ROLLBACK:
        return rollback(config)
    raise TransitionError(f"unknown transition phase: {phase}")
