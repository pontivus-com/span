"""Lossless schema-11 -> schema-13 staging for the offline transition.

The only structural change is the removal of ``source_observations.excerpt``.
Every semantic table is copied by its common columns; the source excerpt is
not carried. Counts and cross-table references are verified against the staged
store.
"""

from __future__ import annotations

import json as _json
import sqlite3 as _sqlite3

from span.shell.store_transition import (
    TARGET_SCHEMA,
    TransitionConfig,
    TransitionError,
    TransitionPaths,
    _connect_read_only,
    _table_names,
    _verify_staged_references,
)

__all__ = ["stage_schema11", "verify_schema11_staging"]


#: Tables owned by the staged store itself; the source copies must not replace
#: the new schema version or the newly registered repository binding.
_SKIP_TABLES = frozenset(
    {
        "meta",
        "repositories",
        "investigation_contexts",
        "context_evidence",
        "context_discovery_evidence",
    }
)


def _columns(connection: _sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")]


def _copy_table(
    target: _sqlite3.Connection,
    source: _sqlite3.Connection,
    table: str,
    repository_id: str,
) -> int:
    target_columns = _columns(target, table)
    if not target_columns:
        raise TransitionError(
            f"schema-11 source table {table!r} has no schema-13 target"
        )
    source_columns = set(_columns(source, table))
    columns = [name for name in target_columns if name in source_columns]
    if not columns:
        return 0
    selection = ", ".join(columns)
    where = ""
    parameters: tuple[object, ...] = ()
    if "repository_id" in columns:
        where = " WHERE repository_id=?"
        parameters = (repository_id,)
    rows = source.execute(
        f"SELECT {selection} FROM {table}{where}", parameters
    ).fetchall()
    if rows:
        placeholders = ", ".join("?" for _ in columns)
        target.executemany(
            f"INSERT OR REPLACE INTO {table} ({selection})" f" VALUES ({placeholders})",
            [tuple(row) for row in rows],
        )
    return len(rows)


def stage_schema11(
    paths: TransitionPaths,
    config: TransitionConfig,
    root: str,
) -> tuple[tuple[str, ...], dict[str, object]]:
    """Copy a schema-11 archive into the staged schema-13 store."""
    source = _connect_read_only(paths.archive)
    target = _sqlite3.connect(paths.staging)
    counts: dict[str, int] = {}
    try:
        target.execute("BEGIN IMMEDIATE")
        tables = [table for table in _table_names(source) if table not in _SKIP_TABLES]
        for table in tables:
            counts[table] = _copy_table(target, source, table, config.repository_id)
        target.commit()
    except BaseException:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()
    payload = {
        "source_schema": 11,
        "target_schema": TARGET_SCHEMA,
        "repository_id": config.repository_id,
        "dropped_columns": {"source_observations": ["excerpt"]},
        "drained_not_copied": [
            "investigation_contexts",
            "context_evidence",
            "context_discovery_evidence",
        ],
        "counts": counts,
    }
    paths.mapping.write_text(
        _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return (
        (
            "schema-11 copy preserved durable semantic/audit tables, dropped "
            "source_observations.excerpt, and did not reactivate legacy contexts",
        ),
        payload,
    )


def verify_schema11_staging(paths: TransitionPaths, config: TransitionConfig) -> None:
    """Verify the schema-11 copy counts and every preserved reference."""
    if not paths.mapping.is_file():
        raise TransitionError("schema-11 mapping artifact is missing")
    payload = _json.loads(paths.mapping.read_text(encoding="utf-8"))
    if payload.get("source_schema") != 11:
        raise TransitionError("schema-11 mapping reports another source schema")
    counts = payload.get("counts", {})
    if not isinstance(counts, dict):
        raise TransitionError("schema-11 mapping counts are not an object")
    connection = _connect_read_only(paths.staging)
    try:
        if "excerpt" in _columns(connection, "source_observations"):
            raise TransitionError(
                "staged store still carries source_observations.excerpt"
            )
        for table, expected in counts.items():
            actual = int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            if actual != expected:
                raise TransitionError(
                    f"staged {table} holds {actual} rows, mapping expects {expected}"
                )
        for table in (
            "investigation_contexts",
            "context_evidence",
            "context_discovery_evidence",
        ):
            if connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                raise TransitionError(f"staged {table} must be empty")
        _verify_staged_references(connection, config)
    finally:
        connection.close()
