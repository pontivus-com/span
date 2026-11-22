"""Shared SQLite row writers for canonical investigation contexts."""

from __future__ import annotations

import datetime as _datetime
import json as _json
import re as _re
import sqlite3 as _sqlite3

from span.core import model as m

_SCHEMA_NAME = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _table(schema: str | None, name: str) -> str:
    if schema is None:
        return name
    if _SCHEMA_NAME.fullmatch(schema) is None:
        raise ValueError("SQLite schema alias must be an internal identifier")
    return f"{schema}.{name}"


def insert_context_row(
    connection: _sqlite3.Connection,
    context: m.InvestigationContext,
    *,
    schema: str | None = None,
) -> None:
    """Persist one canonical context row using the existing lifecycle shape."""
    expires_at = (
        None
        if context.expires_at is None
        else context.expires_at.astimezone(_datetime.timezone.utc).isoformat()
    )
    connection.execute(
        f"INSERT INTO {_table(schema, 'investigation_contexts')}"
        "(context_id, repository_id, request_id, binding_digest,"
        " canonical_json, expires_at) VALUES(?,?,?,?,?,?)",
        (
            context.context_id.value,
            context.repository_id,
            context.request_id.value,
            context.binding_digest.value,
            _json.dumps(m.to_canonical(context), sort_keys=True),
            expires_at,
        ),
    )


def add_context_evidence_row(
    connection: _sqlite3.Connection,
    *,
    repository_id: str,
    context_id: str,
    observation_id: str,
    schema: str | None = None,
) -> None:
    connection.execute(
        f"INSERT OR IGNORE INTO {_table(schema, 'context_evidence')}"
        "(repository_id, context_id, observation_id) VALUES(?,?,?)",
        (repository_id, context_id, observation_id),
    )


def add_context_discovery_row(
    connection: _sqlite3.Connection,
    *,
    repository_id: str,
    context_id: str,
    observation_id: str,
    schema: str | None = None,
) -> None:
    connection.execute(
        f"INSERT OR IGNORE INTO {_table(schema, 'context_discovery_evidence')}"
        "(repository_id, context_id, observation_id) VALUES(?,?,?)",
        (repository_id, context_id, observation_id),
    )
