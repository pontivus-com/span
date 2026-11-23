"""Schema-14 -> schema-15 durable copy for curation persistence.

Schema 15 adds only immutable conclusion curation dispositions. Every schema-14
repository row, including the Functional Pyramid route-dependency projection, is
copied without reinterpretation. No curation disposition is fabricated.
"""

from __future__ import annotations

import json as _json
import sqlite3 as _sqlite3

from span.shell.store_transition import (
    TARGET_SCHEMA,
    TransitionConfig,
    TransitionError,
    TransitionPaths,
    _columns,
    _connect_read_only,
    _verify_staged_references,
)

__all__ = ["stage_schema14", "verify_schema14_staging"]


_SCHEMA14_TABLES = (
    "repositories",
    "surfaces",
    "surface_boundary_versions",
    "source_observations",
    "discovery_observations",
    "investigation_contexts",
    "context_evidence",
    "context_discovery_evidence",
    "understandings",
    "understanding_versions",
    "conclusions",
    "support_dependencies",
    "understanding_membership",
    "challenges",
    "verification_runs",
    "verification_observations",
    "record_receipts",
    "functional_route_dependency_index",
)


def _copy_table(
    target: _sqlite3.Connection,
    source: _sqlite3.Connection,
    table: str,
) -> int:
    target_columns = _columns(target, table)
    source_columns = _columns(source, table)
    if not target_columns or not source_columns:
        raise TransitionError(
            f"schema-14 table {table!r} is missing from source or schema-15 target"
        )
    if tuple(target_columns) != tuple(source_columns):
        raise TransitionError(
            f"schema-14 table {table!r} does not match the schema-15 retained shape"
        )
    selection = ", ".join(target_columns)
    rows = source.execute(f"SELECT {selection} FROM {table}").fetchall()
    if rows:
        placeholders = ", ".join("?" for _ in target_columns)
        target.executemany(
            f"INSERT OR REPLACE INTO {table} ({selection}) VALUES({placeholders})",
            [tuple(row) for row in rows],
        )
    return len(rows)


def stage_schema14(
    paths: TransitionPaths,
    config: TransitionConfig,
    root: str,
) -> tuple[tuple[str, ...], dict[str, object]]:
    """Copy every retained schema-14 table and leave curation storage empty."""
    source = _connect_read_only(paths.archive)
    target = _sqlite3.connect(paths.staging)
    target.row_factory = _sqlite3.Row
    counts: dict[str, int] = {}
    try:
        target.execute("PRAGMA foreign_keys = ON")
        target.execute("BEGIN IMMEDIATE")
        for table in _SCHEMA14_TABLES:
            counts[table] = _copy_table(target, source, table)

        target.execute(
            "UPDATE repositories SET root=? WHERE repository_id=?",
            (root, config.repository_id),
        )
        if (
            target.execute(
                "SELECT 1 FROM repositories WHERE repository_id=?",
                (config.repository_id,),
            ).fetchone()
            is None
        ):
            raise TransitionError("schema-14 source has no selected repository binding")

        if int(
            target.execute("SELECT COUNT(*) FROM conclusion_curations").fetchone()[0]
        ):
            raise TransitionError(
                "schema-14 transition must not fabricate curation dispositions"
            )
        target.commit()
    except BaseException:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()

    payload: dict[str, object] = {
        "source_schema": 14,
        "target_schema": TARGET_SCHEMA,
        "repository_id": config.repository_id,
        "counts": counts,
        "curation_rows": 0,
    }
    paths.mapping.write_text(
        _json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return (
        (
            "schema-14 state copied without semantic or governance reinterpretation",
            "schema-15 curation storage initialized with zero dispositions",
        ),
        payload,
    )


def verify_schema14_staging(paths: TransitionPaths, config: TransitionConfig) -> None:
    """Prove retained counts and the zero-curation migration invariant."""
    if not paths.mapping.is_file():
        raise TransitionError("schema-14 mapping artifact is missing")
    payload = _json.loads(paths.mapping.read_text(encoding="utf-8"))
    if (
        payload.get("source_schema") != 14
        or payload.get("target_schema") != TARGET_SCHEMA
    ):
        raise TransitionError("schema-14 mapping reports the wrong transition")
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise TransitionError("schema-14 mapping counts are not an object")

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
        curation_rows = int(
            connection.execute("SELECT COUNT(*) FROM conclusion_curations").fetchone()[0]
        )
        if curation_rows != 0 or payload.get("curation_rows") != 0:
            raise TransitionError(
                "schema-15 transition fabricated a curation disposition"
            )
        _verify_staged_references(connection, config)
    finally:
        connection.close()
