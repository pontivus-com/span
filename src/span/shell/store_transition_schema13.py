"""Schema-13 -> schema-14 durable copy for Functional Pyramid persistence.

Schema 14 adds installation-level Functional Pyramid state and a derived route
lookup projection. Existing schema-13 rows are copied without reinterpretation.
No Functional Pyramid participation, receipt, or route support is fabricated.
"""

from __future__ import annotations

import json as _json
import sqlite3 as _sqlite3

from span.core import model as m
from span.shell.store_transition import (
    TARGET_SCHEMA,
    TransitionConfig,
    TransitionError,
    TransitionPaths,
    _columns,
    _connect_read_only,
    _verify_staged_references,
)

__all__ = ["stage_schema13", "verify_schema13_staging"]


_SCHEMA13_TABLES = (
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
            f"schema-13 table {table!r} is missing from source or schema-14 target"
        )
    if tuple(target_columns) != tuple(source_columns):
        raise TransitionError(
            f"schema-13 table {table!r} does not match the schema-14 retained shape"
        )
    selection = ", ".join(target_columns)
    rows = source.execute(f"SELECT {selection} FROM {table}").fetchall()
    if rows:
        placeholders = ", ".join("?" for _ in target_columns)
        target.executemany(
            f"INSERT OR REPLACE INTO {table} ({selection}) VALUES ({placeholders})",
            [tuple(row) for row in rows],
        )
    return len(rows)


def _derive_route_index(target: _sqlite3.Connection) -> int:
    count = 0
    rows = target.execute(
        "SELECT canonical_json FROM conclusions"
        " ORDER BY understanding_id, conclusion_id, revision"
    ).fetchall()
    for row in rows:
        revision = m.from_canonical(
            m.ConclusionRevision,
            _json.loads(row[0]),
        )
        for dependency in revision.content.support:
            if not isinstance(dependency, m.FunctionalRouteSupport):
                continue
            target.execute(
                "INSERT INTO functional_route_dependency_index"
                "(understanding_id, conclusion_id, revision, pyramid_id,"
                " repository_id, route_identity) VALUES(?,?,?,?,?,?)",
                (
                    revision.understanding_id.value,
                    revision.conclusion_id.value,
                    revision.revision.value,
                    dependency.pyramid_id.value,
                    dependency.repository_id,
                    dependency.route_identity.value,
                ),
            )
            count += 1
    return count


def stage_schema13(
    paths: TransitionPaths,
    config: TransitionConfig,
    root: str,
) -> tuple[tuple[str, ...], dict[str, object]]:
    source = _connect_read_only(paths.archive)
    target = _sqlite3.connect(paths.staging)
    target.row_factory = _sqlite3.Row
    counts: dict[str, int] = {}
    try:
        target.execute("PRAGMA foreign_keys = ON")
        target.execute("BEGIN IMMEDIATE")
        for table in _SCHEMA13_TABLES:
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
            raise TransitionError("schema-13 source has no selected repository binding")

        route_rows = _derive_route_index(target)
        target.commit()
    except BaseException:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()

    payload: dict[str, object] = {
        "source_schema": 13,
        "target_schema": TARGET_SCHEMA,
        "repository_id": config.repository_id,
        "counts": counts,
        "derived_functional_route_rows": route_rows,
        "functional_pyramid_installation_state": "separate",
    }
    paths.mapping.write_text(
        _json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return (
        (
            "schema-13 state copied without semantic reinterpretation; "
            "Functional Pyramid participation remains installation-owned",
            "existing FunctionalRouteSupport rows indexed without adding support",
        ),
        payload,
    )


def verify_schema13_staging(paths: TransitionPaths, config: TransitionConfig) -> None:
    if not paths.mapping.is_file():
        raise TransitionError("schema-13 mapping artifact is missing")
    payload = _json.loads(paths.mapping.read_text(encoding="utf-8"))
    if (
        payload.get("source_schema") != 13
        or payload.get("target_schema") != TARGET_SCHEMA
    ):
        raise TransitionError("schema-13 mapping reports the wrong transition")
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise TransitionError("schema-13 mapping counts are not an object")

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
        route_rows = int(
            connection.execute(
                "SELECT COUNT(*) FROM functional_route_dependency_index"
            ).fetchone()[0]
        )
        if route_rows != payload.get("derived_functional_route_rows"):
            raise TransitionError(
                "schema-14 route index count differs from the schema-13 mapping"
            )
        _verify_staged_references(connection, config)
    finally:
        connection.close()
