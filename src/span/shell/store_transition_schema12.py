"""Schema-12 -> schema-13 staging after operational context drain.

Schema 13 changes context binding semantics. Durable semantic/audit state is
copied exactly by common columns; investigation contexts and their membership
are deliberately not reactivated.
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

__all__ = ["stage_schema12", "verify_schema12_staging"]

_SKIP_TABLES = frozenset(
    {
        "meta",
        "repositories",
        "investigation_contexts",
        "context_evidence",
        "context_discovery_evidence",
    }
)
_DRAINED_TABLES = (
    "investigation_contexts",
    "context_evidence",
    "context_discovery_evidence",
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
            f"schema-12 source table {table!r} has no schema-13 target"
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
            f"INSERT OR REPLACE INTO {table} ({selection}) VALUES ({placeholders})",
            [tuple(row) for row in rows],
        )
    return len(rows)


def _drained_counts(
    source: _sqlite3.Connection, repository_id: str
) -> dict[str, int]:
    counts: dict[str, int] = {}
    counts["investigation_contexts"] = int(
        source.execute(
            "SELECT COUNT(*) FROM investigation_contexts WHERE repository_id=?",
            (repository_id,),
        ).fetchone()[0]
    )
    for table in ("context_evidence", "context_discovery_evidence"):
        counts[table] = int(
            source.execute(
                f"SELECT COUNT(*) FROM {table} AS links"
                " JOIN investigation_contexts AS contexts"
                " ON contexts.context_id=links.context_id"
                " WHERE contexts.repository_id=?",
                (repository_id,),
            ).fetchone()[0]
        )
    return counts


def stage_schema12(
    paths: TransitionPaths,
    config: TransitionConfig,
    root: str,
) -> tuple[tuple[str, ...], dict[str, object]]:
    del root
    source = _connect_read_only(paths.archive)
    target = _sqlite3.connect(paths.staging)
    counts: dict[str, int] = {}
    drained: dict[str, int] = {}
    try:
        target.execute("BEGIN IMMEDIATE")
        tables = [table for table in _table_names(source) if table not in _SKIP_TABLES]
        for table in tables:
            counts[table] = _copy_table(target, source, table, config.repository_id)
        row = source.execute(
            "SELECT authority_bindings_json FROM repositories WHERE repository_id=?",
            (config.repository_id,),
        ).fetchone()
        if row is not None:
            target.execute(
                "UPDATE repositories SET authority_bindings_json=?"
                " WHERE repository_id=?",
                (row[0], config.repository_id),
            )
        drained = _drained_counts(source, config.repository_id)
        target.commit()
    except BaseException:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()
    payload = {
        "source_schema": 12,
        "target_schema": TARGET_SCHEMA,
        "repository_id": config.repository_id,
        "counts": counts,
        "drained_not_copied": drained,
    }
    paths.mapping.write_text(
        _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return (
        (
            "schema-12 durable state copied after context drain; operational "
            "contexts and membership were not reactivated",
        ),
        payload,
    )


def verify_schema12_staging(paths: TransitionPaths, config: TransitionConfig) -> None:
    if not paths.mapping.is_file():
        raise TransitionError("schema-12 mapping artifact is missing")
    payload = _json.loads(paths.mapping.read_text(encoding="utf-8"))
    if (
        payload.get("source_schema") != 12
        or payload.get("target_schema") != TARGET_SCHEMA
    ):
        raise TransitionError("schema-12 mapping reports the wrong transition")
    counts = payload.get("counts", {})
    if not isinstance(counts, dict):
        raise TransitionError("schema-12 mapping counts are not an object")
    connection = _connect_read_only(paths.staging)
    try:
        for table, expected in counts.items():
            actual = int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            if actual != expected:
                raise TransitionError(
                    f"staged {table} holds {actual} rows, mapping expects {expected}"
                )
        for table in _DRAINED_TABLES:
            if connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                raise TransitionError(f"staged {table} must be empty")
        _verify_staged_references(connection, config)
    finally:
        connection.close()
