"""Offline coordinated schema-16 / installation-schema-2 transition."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from pathlib import Path

from span.shell.sqlite_ownership import store_use_ownership
from span.shell.sqlite_store.functional_pyramid import (
    functional_pyramid_installation_path,
)
from span.shell.store_transition import (
    SUPPORTED_SOURCE_SCHEMAS,
    TARGET_SCHEMA,
    TransitionConfig,
    TransitionError,
    TransitionPaths,
    _archive,
    _connect_read_only,
    _exclusive_source,
    _export,
    _fsync_dir,
    _fsync_file,
    _integrity,
    _read_schema_version_ro,
    _require_schema12_context_drain,
    _sha256_file,
    _stage,
    _verify_staged,
)
from span.shell.store_transition_schema15 import stage_installation_schema1


def _workspace(data_dir: Path) -> Path:
    return data_dir / "transitions" / "installation-cutover"


def _manifest(data_dir: Path) -> Path:
    return _workspace(data_dir) / "manifest.json"


def _write_manifest(data_dir: Path, payload: dict[str, object]) -> None:
    target = _manifest(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial")
    partial.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    _fsync_file(partial)
    os.replace(partial, target)
    _fsync_dir(target.parent)


def _paths(data_dir: Path, relative: str) -> TransitionPaths:
    active = data_dir / relative
    identity = active.stem
    if active == functional_pyramid_installation_path(data_dir):
        workspace = _workspace(data_dir) / "installation"
    elif active.parent == data_dir and active.suffix == ".db":
        workspace = _workspace(data_dir) / "repositories" / identity
    else:
        raise TransitionError("invalid store in installation transition")
    return TransitionPaths(data_dir, identity, active, workspace)


def _inventory(data_dir: Path) -> tuple[str, ...]:
    installation = functional_pyramid_installation_path(data_dir)
    if not installation.is_file():
        raise TransitionError("installation schema-1 store is absent")
    repositories = sorted(p.name for p in data_dir.glob("*.db") if p.is_file())
    return (*repositories, str(installation.relative_to(data_dir)))


def _inspect(data_dir: Path) -> dict[str, object]:
    return {
        "stores": {
            relative: _read_schema_version_ro(data_dir / relative)
            for relative in _inventory(data_dir)
        },
        "manifest": (
            json.loads(_manifest(data_dir).read_text(encoding="utf-8"))
            if _manifest(data_dir).is_file()
            else None
        ),
    }


def _repository_root(paths: TransitionPaths) -> str:
    with contextlib.closing(_connect_read_only(paths.archive)) as connection:
        rows = connection.execute(
            "SELECT repository_id, root FROM repositories"
        ).fetchall()
    if len(rows) != 1 or rows[0][0] != paths.repository_id:
        raise TransitionError("repository archive has no unique retained root binding")
    return str(rows[0][1])


def _prepare(data_dir: Path, inventory: tuple[str, ...]) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    with contextlib.ExitStack() as stack:
        sources = {
            relative: stack.enter_context(_exclusive_source(data_dir / relative))
            for relative in inventory
        }
        for relative, source in sources.items():
            paths = _paths(data_dir, relative)
            config = TransitionConfig(data_dir, paths.repository_id)
            archive_hash = _archive(paths, config, source)
            tables, _ = _export(paths)
            schema = _read_schema_version_ro(paths.archive)
            installation = paths.active == functional_pyramid_installation_path(data_dir)
            if installation:
                if schema != 1:
                    raise TransitionError("expected installation schema 1")
                stage_installation_schema1(paths)
                target = 2
            else:
                if schema not in SUPPORTED_SOURCE_SCHEMAS:
                    raise TransitionError(f"unsupported repository schema: {schema}")
                assert schema is not None
                root = _repository_root(paths)
                config = TransitionConfig(data_dir, paths.repository_id, root)
                _require_schema12_context_drain(paths.archive, config)
                _stage(paths, config, root, schema)
                _verify_staged(paths, config, root, tables, schema)
                target = TARGET_SCHEMA
            _fsync_file(paths.staging)
            _fsync_dir(paths.transition_dir)
            entries.append({
                "relative": relative,
                "source_schema": schema,
                "target_schema": target,
                "archive_sha256": archive_hash,
                "staged_sha256": _sha256_file(paths.staging),
            })
        payload: dict[str, object] = {"state": "prepared", "stores": entries}
        _write_manifest(data_dir, payload)
        _publish(data_dir, entries)
        payload["state"] = "activated"
        _write_manifest(data_dir, payload)
        return payload


def _publish(data_dir: Path, entries: list[dict[str, object]]) -> None:
    for entry in entries:
        paths = _paths(data_dir, str(entry["relative"]))
        if _sha256_file(paths.staging) != entry["staged_sha256"]:
            raise TransitionError("verified staging digest changed")
        if _sha256_file(paths.archive) != entry["archive_sha256"]:
            raise TransitionError("verified archive digest changed")
    for entry in entries:
        paths = _paths(data_dir, str(entry["relative"]))
        os.replace(paths.active, paths.previous)
        _fsync_dir(paths.active.parent)
        _fsync_dir(paths.transition_dir)
        os.replace(paths.staging, paths.active)
        _fsync_file(paths.active)
        _fsync_dir(paths.active.parent)


def _rollback(data_dir: Path, payload: dict[str, object]) -> dict[str, object]:
    entries = payload["stores"]
    if not isinstance(entries, list):
        raise TransitionError("invalid transition manifest")
    for entry in entries:
        paths = _paths(data_dir, str(entry["relative"]))
        if _sha256_file(paths.archive) != entry["archive_sha256"]:
            raise TransitionError("rollback archive digest changed")
    payload["state"] = "rolling-back"
    _write_manifest(data_dir, payload)
    for entry in entries:
        paths = _paths(data_dir, str(entry["relative"]))
        if paths.active.is_file():
            with _exclusive_source(paths.active):
                preserved = paths.transition_dir / "post-transition.db"
                if _read_schema_version_ro(paths.active) == entry["target_schema"]:
                    if preserved.exists():
                        raise TransitionError("post-transition preservation path already exists")
                    os.replace(paths.active, preserved)
                    _fsync_dir(paths.transition_dir)
        partial = paths.active.with_suffix(".restore-partial")
        shutil.copy2(paths.archive, partial)
        _fsync_file(partial)
        os.replace(partial, paths.active)
        _fsync_dir(paths.active.parent)
    payload["state"] = "rolled-back"
    _write_manifest(data_dir, payload)
    return payload


def dispatch_installation(data_dir: Path, phase: str) -> dict[str, object]:
    """Stage and verify all stores before any activation; preserve rollback bytes."""
    data_dir = data_dir.resolve()
    if phase == "inspect":
        return _inspect(data_dir)
    if phase == "verify":
        result = _inspect(data_dir)
        manifest = result["manifest"]
        if not isinstance(manifest, dict) or manifest.get("state") != "activated":
            raise TransitionError("installation transition has not been activated")
        for entry in manifest["stores"]:
            paths = _paths(data_dir, str(entry["relative"]))
            if _read_schema_version_ro(paths.active) != entry["target_schema"]:
                raise TransitionError("mixed installation schema set")
            with contextlib.closing(_connect_read_only(paths.active)) as connection:
                if _integrity(connection) != "ok":
                    raise TransitionError("active store failed integrity check")
            if _sha256_file(paths.archive) != entry["archive_sha256"]:
                raise TransitionError("retained archive digest changed")
        return result
    with store_use_ownership(data_dir, exclusive=True):
        if phase == "apply":
            if _manifest(data_dir).exists():
                raise TransitionError("existing installation transition: inspect or rollback")
            return _prepare(data_dir, _inventory(data_dir))
        if phase == "rollback":
            if not _manifest(data_dir).is_file():
                raise TransitionError("no installation transition manifest")
            payload = json.loads(_manifest(data_dir).read_text(encoding="utf-8"))
            if payload.get("state") == "rolled-back":
                return payload
            return _rollback(data_dir, payload)
    raise TransitionError("unknown installation transition phase")
