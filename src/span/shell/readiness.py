"""Typed administrative readiness probes (observational only).

These probes open existing resources strictly read-only. They never
initialize, migrate, rebuild or repair a store, and they never invoke a
semantic operation. Hooks and installer verification share this one
readiness rule instead of owning a second interpretation.
"""

from __future__ import annotations

import dataclasses as _dataclasses
import pathlib as _pathlib
import sqlite3 as _sqlite3

from span.shell.sqlite_store.lifecycle import SCHEMA_VERSION

__all__ = [
    "StoreReadiness",
    "probe_store",
    "probe_structural",
]


@_dataclasses.dataclass(frozen=True)
class StoreReadiness:
    """One repository's observed operational readiness."""

    repository_id: str
    path: _pathlib.Path
    exists: bool
    schema_version: int | None
    bound_root: str | None
    ready: bool
    action: str | None = None
    expected_version: int = SCHEMA_VERSION

    def payload(self) -> dict[str, object]:
        return {
            "repository_id": self.repository_id,
            "path": str(self.path),
            "exists": self.exists,
            "schema_version": self.schema_version,
            "expected_version": self.expected_version,
            "bound_root": self.bound_root,
            "ready": self.ready,
            "action": self.action,
        }


def probe_store(
    data_dir: str | _pathlib.Path,
    repository_id: str,
) -> StoreReadiness:
    """Observe one store's version and binding without mutating it."""
    path = _pathlib.Path(data_dir) / f"{repository_id}.db"
    if not path.is_file():
        return StoreReadiness(
            repository_id=repository_id,
            path=path,
            exists=False,
            schema_version=None,
            bound_root=None,
            ready=False,
            action=("call initialize_repository in a dedicated setup session"),
        )
    connection = _sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master"
                " WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        version: int | None = None
        if "meta" in tables:
            row = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is not None:
                try:
                    version = int(row[0])
                except (TypeError, ValueError):
                    version = None
        bound_root = None
        if version == SCHEMA_VERSION and "repositories" in tables:
            row = connection.execute(
                "SELECT root FROM repositories WHERE repository_id=?",
                (repository_id,),
            ).fetchone()
            if row is not None:
                bound_root = str(row[0])
    finally:
        connection.close()
    if version != SCHEMA_VERSION:
        return StoreReadiness(
            repository_id=repository_id,
            path=path,
            exists=True,
            schema_version=version,
            bound_root=bound_root,
            ready=False,
            action=(
                "run `span-install --transition-store "
                f"{repository_id} --transition-phase inspect` for the "
                "offline transition"
            ),
        )
    if bound_root is None:
        return StoreReadiness(
            repository_id=repository_id,
            path=path,
            exists=True,
            schema_version=version,
            bound_root=None,
            ready=False,
            action=("call initialize_repository in a dedicated setup session"),
        )
    return StoreReadiness(
        repository_id=repository_id,
        path=path,
        exists=True,
        schema_version=version,
        bound_root=bound_root,
        ready=True,
    )


def probe_structural(
    data_dir: str | _pathlib.Path,
    repository_id: str,
) -> dict[str, object]:
    """Report whether the provider cache directory exists (not its freshness)."""
    artifact = _pathlib.Path(data_dir) / "structural" / repository_id
    if artifact.is_dir():
        return {"status": "present", "path": str(artifact)}
    return {
        "status": "absent",
        "path": str(artifact),
        "action": "rerun installation to provision the structural indexer",
    }
