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
    "probe_functional_pyramid_installation_store",
    "probe_functional_pyramid_repository",
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
            action=("run the installer to bind this repository"),
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
            action=("run the installer to bind this repository"),
        )
    return StoreReadiness(
        repository_id=repository_id,
        path=path,
        exists=True,
        schema_version=version,
        bound_root=bound_root,
        ready=True,
    )


def probe_functional_pyramid_installation_store(
    data_dir: str | _pathlib.Path,
) -> dict[str, object]:
    """Observe the installation Functional Pyramid store without creating it."""
    from span.shell.sqlite_store.functional_pyramid import (
        INSTALLATION_SCHEMA_VERSION,
        functional_pyramid_installation_path,
    )

    path = functional_pyramid_installation_path(data_dir)
    if not path.is_file():
        return {
            "status": "absent",
            "path": str(path),
            "schema_version": None,
            "ready": False,
            "action": "run the installer to initialize Functional Pyramid state",
        }
    connection = _sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        version = None if row is None else int(row[0])
        mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
    except (_sqlite3.Error, TypeError, ValueError):
        return {
            "status": "invalid",
            "path": str(path),
            "schema_version": None,
            "ready": False,
            "action": "restore or recreate the Functional Pyramid installation store",
        }
    finally:
        connection.close()
    ready = (
        version == INSTALLATION_SCHEMA_VERSION
        and mode.lower() not in {"wal", "off", "memory"}
        and synchronous != 0
    )
    return {
        "status": "ready" if ready else "incompatible",
        "path": str(path),
        "schema_version": version,
        "journal_mode": mode,
        "ready": ready,
        "action": (
            None
            if ready
            else "run the installer to repair Functional Pyramid installation state"
        ),
    }


def _functional_pyramid_participation(
    data_dir: str | _pathlib.Path,
    repository_id: str,
) -> dict[str, object]:
    """Read durable participation from the installation store without mutation."""
    installation = probe_functional_pyramid_installation_store(data_dir)
    if not installation.get("ready"):
        return {
            "state": "UNAVAILABLE",
            "pyramid_id": None,
            "version": None,
            "action": installation.get("action"),
        }

    from span.shell.sqlite_store.functional_pyramid import (
        functional_pyramid_installation_path,
    )

    path = functional_pyramid_installation_path(data_dir)
    connection = _sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        active = connection.execute(
            "SELECT pyramid_id, version FROM functional_pyramid_active_members"
            " WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if active is not None:
            return {
                "state": "ACTIVE",
                "pyramid_id": str(active[0]),
                "version": int(active[1]),
                "action": None,
            }
        excluded = connection.execute(
            "SELECT 1 FROM functional_pyramid_exclusions WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
    except (_sqlite3.Error, TypeError, ValueError):
        return {
            "state": "UNAVAILABLE",
            "pyramid_id": None,
            "version": None,
            "action": "restore or recreate the Functional Pyramid installation store",
        }
    finally:
        connection.close()

    return {
        "state": "EXCLUDED" if excluded is not None else "UNCONFIGURED",
        "pyramid_id": None,
        "version": None,
        "action": None,
    }


def probe_functional_pyramid_repository(
    data_dir: str | _pathlib.Path,
    repository_id: str,
    root: str | _pathlib.Path,
) -> dict[str, object]:
    """Validate local Functional Pyramid configuration without activating it.

    The optional bootstrap is navigation/configuration only. This probe validates
    it and every exact declaration source it names, then reports durable
    participation independently. Full activation readiness remains the pure
    FunctionalPyramidCandidateSelector contract because only the caller owns the
    complete multi-repository member intent.
    """
    from span.core import model as m
    from span.ports.functional_pyramid import (
        FunctionalPyramidDeclarationInvalid,
        FunctionalPyramidRepositoryUnavailable,
    )
    from span.shell.functional_pyramid import FilesystemFunctionalPyramidDeclarations

    canonical_root = str(_pathlib.Path(root).resolve())
    declarations = FilesystemFunctionalPyramidDeclarations(
        lambda requested: (
            canonical_root
            if requested == repository_id
            else (_ for _ in ()).throw(
                ValueError(f"unexpected repository identity: {requested}")
            )
        )
    )
    participation = _functional_pyramid_participation(data_dir, repository_id)

    try:
        bootstrap_result = declarations.read_bootstrap(repository_id)
    except FunctionalPyramidRepositoryUnavailable:
        declaration_report: dict[str, object] = {
            "status": "unavailable",
            "configured": False,
            "valid": False,
            "sources": [],
            "action": "restore the registered repository root",
        }
    except FunctionalPyramidDeclarationInvalid:
        declaration_report = {
            "status": "invalid",
            "configured": True,
            "valid": False,
            "sources": [],
            "action": "correct .span/functional-pyramid.json",
        }
    else:
        if bootstrap_result is None:
            declaration_report = {
                "status": "absent",
                "configured": False,
                "valid": True,
                "sources": [],
                "action": None,
            }
        else:
            bootstrap_ref, bootstrap = bootstrap_result
            source_reports: list[dict[str, object]] = []
            valid = True
            for request in bootstrap.declaration_sources:
                if request.ranges:
                    source_reports.append(
                        {
                            "locator": request.locator,
                            "status": "invalid",
                            "reason": "declaration source must be a whole document",
                        }
                    )
                    valid = False
                    continue
                try:
                    result = declarations.read_declaration(repository_id, request)
                except FunctionalPyramidRepositoryUnavailable:
                    source_reports.append(
                        {
                            "locator": request.locator,
                            "status": "unavailable",
                            "reason": "repository cannot be read",
                        }
                    )
                    valid = False
                    continue
                except FunctionalPyramidDeclarationInvalid:
                    source_reports.append(
                        {
                            "locator": request.locator,
                            "status": "invalid",
                            "reason": "declaration violates the Version-2 contract",
                        }
                    )
                    valid = False
                    continue
                if isinstance(result, m.EvidenceSourceFailure):
                    source_reports.append(
                        {
                            "locator": request.locator,
                            "status": result.kind.value.lower(),
                            "reason": result.reason,
                        }
                    )
                    valid = False
                    continue
                declaration_ref, _, graph_findings = result
                source_reports.append(
                    {
                        "locator": request.locator,
                        "status": "valid" if not graph_findings else "invalid",
                        "evidence_id": declaration_ref.evidence_id.value,
                        "findings": [
                            finding.reason.value for finding in graph_findings
                        ],
                    }
                )
                if graph_findings:
                    valid = False

            declaration_report = {
                "status": "ready" if valid else "invalid",
                "configured": True,
                "valid": valid,
                "bootstrap_locator": bootstrap_ref.locator,
                "sources": source_reports,
                "action": (
                    None
                    if valid
                    else "correct the named Functional Pyramid declaration sources"
                ),
            }

    return {
        "repository_id": repository_id,
        "declarations": declaration_report,
        "participation": participation,
        "activation_readiness": {
            "status": "requires_candidate",
            "action": (
                "validate the complete intended member set with "
                "FunctionalPyramidCandidateSelector"
            ),
        },
    }


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
