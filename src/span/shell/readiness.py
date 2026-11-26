"""Typed administrative readiness probes (observational only).

These probes open existing resources strictly read-only. They never
initialize, migrate, rebuild or repair a store, and they never invoke a
semantic operation. Hooks and installer verification share this one
readiness rule instead of owning a second interpretation.
"""

from __future__ import annotations

import dataclasses as _dataclasses
import hashlib as _hashlib
import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3
import typing as _typing

from span.shell.sqlite_store.lifecycle import SCHEMA_VERSION

if _typing.TYPE_CHECKING:
    from span.core import model as _m
    from span.shell.functional_pyramid import (
        FilesystemFunctionalPyramidDeclarations,
    )

__all__ = [
    "StoreReadiness",
    "probe_active_functional_pyramid",
    "probe_functional_pyramid_installation_store",
    "probe_functional_pyramid_repository",
    "probe_governed_provenance",
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


def _functional_pyramid_declaration_report(
    repository_id: str,
    canonical_root: str,
) -> dict[str, object]:
    from span.core import model as m
    from span.ports.functional_pyramid import (
        FunctionalPyramidDeclarationInvalid,
        FunctionalPyramidRepositoryUnavailable,
    )
    from span.shell.functional_pyramid import FilesystemFunctionalPyramidDeclarations

    declarations = FilesystemFunctionalPyramidDeclarations(
        lambda requested: (
            canonical_root
            if requested == repository_id
            else (_ for _ in ()).throw(
                ValueError(f"unexpected repository identity: {requested}")
            )
        )
    )
    try:
        bootstrap_result = declarations.read_bootstrap(repository_id)
    except FunctionalPyramidRepositoryUnavailable:
        return {
            "status": "unavailable",
            "configured": False,
            "valid": False,
            "sources": [],
            "action": "restore the registered repository root",
        }
    except FunctionalPyramidDeclarationInvalid:
        return {
            "status": "invalid",
            "configured": True,
            "valid": False,
            "sources": [],
            "action": "correct .span/functional-pyramid.json",
        }
    if bootstrap_result is None:
        return {
            "status": "absent",
            "configured": False,
            "valid": True,
            "sources": [],
            "action": None,
        }

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
                    "reason": "declaration violates the Version-3 contract",
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
                "findings": [finding.reason.value for finding in graph_findings],
            }
        )
        if graph_findings:
            valid = False

    return {
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


def _active_member_declaration_refs(
    data_dir: str | _pathlib.Path,
    repository_id: str,
) -> tuple[_m.EvidenceRef, ...] | None:
    """Read the retained ACTIVE member declaration references, read-only."""
    installation = probe_functional_pyramid_installation_store(data_dir)
    if not installation.get("ready"):
        return None
    from span.shell.sqlite_store.functional_pyramid import (
        functional_pyramid_installation_path,
    )

    path = functional_pyramid_installation_path(data_dir)
    connection = _sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT member_json FROM functional_pyramid_active_members"
            " WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
    except (_sqlite3.Error, TypeError, ValueError):
        return None
    finally:
        connection.close()
    if row is None:
        return None
    from span.core import model as m

    try:
        member = m.from_canonical(
            m.FunctionalPyramidMemberView, _json.loads(str(row[0]))
        )
    except (m.CanonicalDecodeError, TypeError, ValueError):
        return None
    return member.declaration_refs


def _declaration_store(
    repository_id: str, canonical_root: str
) -> "FilesystemFunctionalPyramidDeclarations":
    from span.shell.functional_pyramid import FilesystemFunctionalPyramidDeclarations

    def root_for(requested: str) -> str:
        if requested != repository_id:
            raise ValueError(f"unexpected repository identity: {requested}")
        return canonical_root

    return FilesystemFunctionalPyramidDeclarations(root_for)


def _active_declaration_report(
    repository_id: str,
    canonical_root: str,
    refs: tuple[_m.EvidenceRef, ...],
) -> dict[str, object]:
    from span.core import model as m
    from span.ports.functional_pyramid import (
        FunctionalPyramidDeclarationInvalid,
        FunctionalPyramidRepositoryUnavailable,
    )

    store = _declaration_store(repository_id, canonical_root)
    sources: list[dict[str, object]] = []
    valid = True
    for ref in refs:
        locator = ref.locator
        request = m.EvidenceRequest(locator)
        try:
            result = store.read_declaration(repository_id, request)
        except FunctionalPyramidRepositoryUnavailable:
            sources.append({"locator": locator, "status": "unavailable"})
            valid = False
            continue
        except FunctionalPyramidDeclarationInvalid:
            sources.append({"locator": locator, "status": "invalid"})
            valid = False
            continue
        if isinstance(result, m.EvidenceSourceFailure):
            sources.append(
                {
                    "locator": locator,
                    "status": result.kind.value.lower(),
                    "reason": result.reason,
                }
            )
            valid = False
            continue
        _, _, findings = result
        sources.append(
            {
                "locator": locator,
                "status": "valid" if not findings else "invalid",
                "findings": [finding.reason.value for finding in findings],
            }
        )
        if findings:
            valid = False
    return {
        "status": "ready" if valid else "invalid",
        "configured": True,
        "selection": "active-members",
        "valid": valid,
        "sources": sources,
        "action": (
            None if valid else "correct the retained ACTIVE declaration sources"
        ),
    }


def probe_active_functional_pyramid(
    data_dir: str | _pathlib.Path,
    roots_by_repository: dict[str, str | _pathlib.Path],
) -> dict[str, object]:
    """Evaluate the complete retained ACTIVE graph without mutation."""
    installation = probe_functional_pyramid_installation_store(data_dir)
    if not installation.get("ready"):
        return {
            "status": "unavailable",
            "members": [],
            "findings": [],
            "action": installation.get("action"),
        }
    from span.core import functional_pyramid as _fp
    from span.core import model as m
    from span.ports.functional_pyramid import (
        FunctionalPyramidDeclarationInvalid,
        FunctionalPyramidRepositoryUnavailable,
    )

    declarations: list[tuple[str, _m.FunctionalPyramidDeclaration]] = []
    findings: list[m.FunctionalPyramidFinding] = []
    member_reports: list[dict[str, object]] = []
    for repository_id in sorted(roots_by_repository):
        canonical_root = str(
            _pathlib.Path(roots_by_repository[repository_id]).resolve()
        )
        refs = _active_member_declaration_refs(data_dir, repository_id)
        if refs is None:
            continue
        member_reports.append(
            {
                "repository_id": repository_id,
                "declaration_refs": [ref.locator for ref in refs],
            }
        )
        store = _declaration_store(repository_id, canonical_root)
        for ref in refs:
            locator = ref.locator
            request = m.EvidenceRequest(locator)
            try:
                result = store.read_declaration(repository_id, request)
            except FunctionalPyramidRepositoryUnavailable:
                findings.append(
                    m.FunctionalPyramidFinding(
                        reason=m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                        repository_id=repository_id,
                        declaration_locator=locator,
                        detail="retained ACTIVE declaration source is unavailable",
                        recovery="restore the registered member repository",
                    )
                )
                continue
            except FunctionalPyramidDeclarationInvalid:
                findings.append(
                    m.FunctionalPyramidFinding(
                        reason=m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id=repository_id,
                        declaration_locator=locator,
                        detail="retained ACTIVE declaration cannot be decoded",
                        recovery="revise the ACTIVE instance with valid Version-3 sources",
                    )
                )
                continue
            if isinstance(result, m.EvidenceSourceFailure):
                findings.append(
                    m.FunctionalPyramidFinding(
                        reason=m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id=repository_id,
                        declaration_locator=locator,
                        detail="retained ACTIVE declaration source cannot be loaded",
                        recovery="restore the named declaration source",
                    )
                )
                continue
            _, declaration, decode_findings = result
            declarations.append((repository_id, declaration))
            findings.extend(decode_findings)
    if not member_reports:
        return {
            "status": "not_active",
            "members": [],
            "findings": [],
            "action": None,
        }
    structural = _fp.evaluate_functional_pyramid_source_structure(
        tuple(declarations),
        tuple(findings),
    )
    return {
        "status": "valid" if not structural else "invalid",
        "members": member_reports,
        "findings": [finding.reason.value for finding in structural],
        "action": (
            None
            if not structural
            else "correct the ACTIVE declaration graph before acceptance"
        ),
    }


def installed_authority_bindings(
    data_dir: str | _pathlib.Path,
    repository_id: str,
) -> list[object] | None:
    """Read the installed whole-document binding set, read-only."""
    path = _pathlib.Path(data_dir) / f"{repository_id}.db"
    if not path.is_file():
        return None
    connection = _sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT authority_bindings_json FROM repositories WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
    except (_sqlite3.Error, TypeError, ValueError):
        return None
    finally:
        connection.close()
    if row is None:
        return None
    try:
        payload = _json.loads(str(row[0]))
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, list) else None


def _initialization_provenance(
    data_dir: str | _pathlib.Path, repository_id: str, root: str | _pathlib.Path,
    entry: dict[str, object], *, pyramid_id: object, version: object,
) -> dict[str, object]:
    """Verify the actual installed generated configuration against its receipt."""
    mismatches: list[dict[str, object]] = []
    artifacts = entry.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("invalid generated artifact provenance")
    classification = entry.get("classification")
    classification_digest = entry.get("classification_digest")
    if not isinstance(classification, str) or not isinstance(classification_digest, str):
        raise ValueError("invalid classification provenance")
    inputs = {**artifacts, classification: classification_digest}
    for locator, expected in inputs.items():
        path = _pathlib.Path(root) / locator
        try:
            actual = _hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            mismatches.append({"locator": locator, "reason": "unreadable"})
            continue
        if actual != expected:
            mismatches.append({"locator": locator, "reason": "digest_mismatch"})
    refs = _active_member_declaration_refs(data_dir, repository_id)
    expected_refs = {key: value for key, value in artifacts.items() if key != ".span/functional-pyramid.json"}
    actual_refs = {} if refs is None else {
        ref.locator: ref.revision_or_fingerprint for ref in refs
    }
    if actual_refs != expected_refs:
        mismatches.append({"locator": repository_id, "reason": "accepted_declaration_set_differs"})
    if installed_authority_bindings(data_dir, repository_id) != entry.get("bindings"):
        mismatches.append({"locator": repository_id, "reason": "installed_binding_set_differs"})
    participation = _functional_pyramid_participation(data_dir, repository_id)
    if participation.get("state") != "ACTIVE" or participation.get("pyramid_id") != pyramid_id or participation.get("version") != version:
        mismatches.append({"locator": repository_id, "reason": "accepted_participation_differs"})
    if str(_pathlib.Path(root).resolve()) != entry.get("root"):
        mismatches.append({"locator": repository_id, "reason": "repository_root_differs"})
    return {
        "state": "PROVENANCE_MISMATCH" if mismatches else "PROVENANCE_MATCH",
        "inputs": len(inputs), "mismatches": mismatches,
    }


def probe_governed_provenance(
    data_dir: str | _pathlib.Path,
    repository_id: str,
    root: str | _pathlib.Path,
    *,
    pending_setup: bool = False,
) -> dict[str, object]:
    """Compare current governed inputs with the retained installation evidence."""
    from span.shell.install.receipt import read_receipt

    receipt = read_receipt(data_dir)
    if receipt is None:
        return {"state": "PROVENANCE_NOT_RECORDED", "inputs": [], "mismatches": []}
    from span.shell.install.governed import ACCEPTED, PENDING

    pending = receipt.get(PENDING)
    if isinstance(pending, dict):
        if not pending_setup:
            return {"state": "PENDING_GOVERNED_INITIALIZATION", "inputs": [], "mismatches": []}
        entries = pending.get("repositories")
        if isinstance(entries, dict) and repository_id in entries:
            entry = entries[repository_id]
            if not isinstance(entry, dict):
                raise ValueError("invalid pending initialization provenance")
            return _initialization_provenance(
                data_dir, repository_id, root, entry,
                pyramid_id=pending.get("accepted_pyramid_id"),
                version=pending.get("accepted_version"),
            )
    accepted = receipt.get(ACCEPTED)
    if isinstance(accepted, dict) and repository_id in accepted:
        recorded = accepted[repository_id]
        if not isinstance(recorded, dict):
            raise ValueError("invalid accepted initialization provenance")
        return _initialization_provenance(
            data_dir, repository_id, root, recorded,
            pyramid_id=recorded.get("pyramid_id"), version=recorded.get("version"),
        )
    facts = receipt.get("preflight_facts")
    entry: dict[str, object] | None = None
    if isinstance(facts, dict):
        for value in facts.values():
            if isinstance(value, dict) and value.get("repository_id") == repository_id:
                entry = value
                break
    if entry is None:
        return {"state": "PROVENANCE_NOT_RECORDED", "inputs": [], "mismatches": []}
    inputs = entry.get("governed_inputs")
    if not isinstance(inputs, list) or not inputs:
        return {"state": "PROVENANCE_NOT_RECORDED", "inputs": [], "mismatches": []}
    canonical_root = _pathlib.Path(root)
    mismatches: list[dict[str, object]] = []
    recorded_declarations: set[str] = set()
    binding_inputs: list[_pathlib.Path] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        locator = item.get("locator")
        role = item.get("role")
        expected = item.get("digest")
        if not isinstance(locator, str) or not isinstance(expected, str):
            mismatches.append({"locator": locator, "reason": "unrecorded"})
            continue
        path = _pathlib.Path(locator)
        if not path.is_absolute():
            path = canonical_root / locator
        if role == "declaration_source":
            recorded_declarations.add(locator)
        if role == "authority_binding":
            binding_inputs.append(path)
        try:
            actual = _hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            mismatches.append({"locator": locator, "reason": "unreadable"})
            continue
        if actual != expected:
            mismatches.append({"locator": locator, "reason": "digest_mismatch"})

    active_refs = _active_member_declaration_refs(data_dir, repository_id)
    if active_refs is not None and recorded_declarations:
        active_locators = {ref.locator for ref in active_refs}
        if active_locators != recorded_declarations:
            mismatches.append(
                {
                    "locator": repository_id,
                    "reason": "accepted_declaration_set_differs",
                    "accepted": sorted(active_locators),
                    "reviewed": sorted(recorded_declarations),
                }
            )

    if binding_inputs:
        installed = installed_authority_bindings(data_dir, repository_id)
        if installed is None:
            mismatches.append(
                {"locator": repository_id, "reason": "installed_bindings_unreadable"}
            )
        else:
            installed_json = _json.dumps(
                installed, sort_keys=True, separators=(",", ":")
            )
            for path in binding_inputs:
                try:
                    reviewed = _json.loads(path.read_text())
                except (OSError, TypeError, ValueError):
                    mismatches.append(
                        {
                            "locator": str(path),
                            "reason": "reviewed_bindings_unreadable",
                        }
                    )
                    continue
                reviewed_json = _json.dumps(
                    reviewed, sort_keys=True, separators=(",", ":")
                )
                if installed_json != reviewed_json:
                    mismatches.append(
                        {
                            "locator": str(path),
                            "reason": "installed_binding_set_differs",
                        }
                    )
    return {
        "state": ("PROVENANCE_MATCH" if not mismatches else "PROVENANCE_MISMATCH"),
        "inputs": len(inputs),
        "mismatches": mismatches,
    }


def probe_functional_pyramid_repository(
    data_dir: str | _pathlib.Path,
    repository_id: str,
    root: str | _pathlib.Path,
    *,
    pending_setup: bool = False,
) -> dict[str, object]:
    """Validate local Functional Pyramid configuration without activating it."""
    canonical_root = str(_pathlib.Path(root).resolve())
    active_refs = _active_member_declaration_refs(data_dir, repository_id)
    declarations = (
        _active_declaration_report(repository_id, canonical_root, active_refs)
        if active_refs is not None
        else _functional_pyramid_declaration_report(repository_id, canonical_root)
    )
    return {
        "repository_id": repository_id,
        "declarations": declarations,
        "participation": _functional_pyramid_participation(data_dir, repository_id),
        "provenance": probe_governed_provenance(
            data_dir, repository_id, canonical_root, pending_setup=pending_setup
        ),
        "activation_readiness": {
            "status": "requires_governed_install",
            "action": "run span-install with the repository classification input",
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
