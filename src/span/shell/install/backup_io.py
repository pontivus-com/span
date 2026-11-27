"""Shared filesystem and SQLite primitives for recovery artifacts.

Stdlib only. Both the full data-directory backup and the per-repository
deployable backup use these functions so the artifact writer, hashing and
database facts have one implementation.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
from pathlib import Path

from span.shell.install.manifest import DatabaseFacts


def utc_stamp() -> str:
    # Microsecond precision keeps two artifacts from the same process-second
    # distinct without inventing a counter; an exact collision still fails
    # closed rather than overwriting.
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_only_uri(path) -> str:
    return Path(path).resolve().as_uri() + "?mode=ro"


def database_facts(path) -> DatabaseFacts:
    """Read the facts a recovery artifact must carry for one database.

    Raises ``sqlite3.Error`` when the file is not a readable database so the
    caller can fail closed instead of recording a false integrity result.
    """
    connection = sqlite3.connect(read_only_uri(path), uri=True)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        integrity = str(row[0]) if row is not None else "unreported"
        tables = {
            str(item[0])
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        schema_version = None
        if "meta" in tables:
            row = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is not None:
                try:
                    schema_version = int(row[0])
                except (TypeError, ValueError):
                    schema_version = None
        max_conclusion_revision = None
        if "conclusions" in tables:
            row = connection.execute("SELECT MAX(revision) FROM conclusions").fetchone()
            if row is not None and row[0] is not None:
                max_conclusion_revision = int(row[0])
    finally:
        connection.close()
    return DatabaseFacts(
        schema_version=schema_version,
        integrity=integrity,
        max_conclusion_revision=max_conclusion_revision,
    )


def logical_database_digest(connection: sqlite3.Connection) -> str:
    """Fingerprint complete typed SQLite content, independently of page layout."""
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("database integrity is not established")
    schema = [
        tuple(row)
        for row in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )
    ]
    digest = hashlib.sha256(json.dumps(schema).encode("utf-8"))

    def typed(value: object) -> tuple[str, object]:
        return (
            type(value).__name__,
            value.hex() if isinstance(value, bytes) else value,
        )

    for pragma in ("user_version", "application_id", "encoding"):
        value = connection.execute(f"PRAGMA {pragma}").fetchone()[0]
        digest.update(json.dumps((pragma, typed(value))).encode("utf-8"))
    for kind, name, _, _ in schema:
        if kind != "table":
            continue
        quoted = '"' + name.replace('"', '""') + '"'
        rows = sorted(
            json.dumps(tuple(typed(value) for value in row))
            for row in connection.execute(f"SELECT * FROM {quoted}")
        )
        digest.update(json.dumps((name, rows)).encode("utf-8"))
    return digest.hexdigest()


def copy_database(
    source, destination, *, connection: sqlite3.Connection | None = None
) -> None:
    src = connection or sqlite3.connect(read_only_uri(source), uri=True)
    try:
        dst = sqlite3.connect(str(destination))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        if connection is None:
            src.close()
