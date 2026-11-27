"""Pending governed setup recovery through the existing backup/receipt owners."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Callable, NoReturn

from span.shell.install import governed
from span.shell.install.backup_io import (
    copy_database,
    logical_database_digest,
    read_only_uri,
    sha256_file,
)
from span.shell.install.manifest import BackupArtifact, BackupManifest, RestoreResult
from span.shell.install.receipt import (
    durable_unlink,
    fsync_directory,
    publish_install_bytes,
    read_receipt,
    write_receipt,
)
from span.shell.install.recovery import (
    BACKUP_MANIFEST,
    _load_manifest,
    create_backup,
    verify_backup,
)

if TYPE_CHECKING:
    from span.core import model as m

_INSTALLATION_DB = "installation/functional-pyramid.db"
_POINTER = "structural-indexer.json"
_RECEIPT = "install.json"


def _conflict(message: str) -> NoReturn:
    raise SystemExit(f"governed recovery conflict: {message}")


def _identity(path: Path) -> list[int]:
    stat = path.stat()
    return [stat.st_dev, stat.st_ino]


def _safe_file(root: Path, relative: str) -> Path:
    try:
        return governed._artifact_path(root, relative)
    except ValueError as exc:
        raise SystemExit(f"governed recovery conflict: {exc}") from None


def _file_digest(path: Path) -> str | None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        _conflict(f"not a regular owned file: {path}")
    return sha256_file(path) if path.is_file() else None


def _requests(pending: dict[str, object]) -> dict[str, m.InitializeRepositoryRequest]:
    from span.core import model as m
    from span.shell.structural import repository_id_from_config

    result: dict[str, m.InitializeRepositoryRequest] = {}
    for item in governed._array(pending["setup_requests"]):
        request = m.from_canonical(m.InitializeRepositoryRequest, item)
        repository_id = repository_id_from_config(request.repository_locator)
        if repository_id in result:
            _conflict(f"duplicate selected repository: {repository_id}")
        result[repository_id] = request
    return result


def _database_names(pending: dict[str, object]) -> tuple[str, ...]:
    return tuple(sorted(f"{name}.db" for name in _requests(pending))) + (
        _INSTALLATION_DB,
    )


def _generated_files(pending: dict[str, object]) -> dict[str, Path]:
    requests = _requests(pending)
    identities = governed._object(pending["root_identities"])
    if set(identities) != set(requests):
        _conflict("selected root identities differ from the pending configuration")
    for repository_id, request in requests.items():
        root = Path(request.repository_locator)
        if (
            not root.is_absolute()
            or root.resolve() != root
            or not root.is_dir()
            or _identity(root) != identities[repository_id]
        ):
            _conflict(f"registered root identity changed: {root}")
    result: dict[str, Path] = {}
    for repository_id, raw in governed._object(pending["repositories"]).items():
        entry = governed._object(raw)
        root = Path(governed._string(entry["root"]))
        if (
            repository_id not in requests
            or str(root) != requests[repository_id].repository_locator
        ):
            _conflict(f"generated root differs from selected root: {repository_id}")
        for locator, digest in governed._object(entry["artifacts"]).items():
            if (
                locator != governed.BOOTSTRAP
                and locator != f".span/functional-pyramid/{digest}.json"
            ):
                _conflict(f"unexpected generated path: {repository_id}/{locator}")
            key = f"governed-targets/{repository_id}/{locator}"
            result[key] = _safe_file(root, locator)
    return result


def _planned_files(pending: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {_POINTER: pending["pointer_digest"]}
    for repository_id, raw in governed._object(pending["repositories"]).items():
        for locator, digest in governed._object(
            governed._object(raw)["artifacts"]
        ).items():
            result[f"governed-targets/{repository_id}/{locator}"] = digest
    return result


def _manifest_entries(manifest: BackupManifest) -> dict[str, BackupArtifact | None]:
    entries: dict[str, BackupArtifact | None] = {
        item.path: item for item in manifest.artifacts
    }
    entries.update({item.path: None for item in manifest.absent})
    return entries


def _verified_manifest(
    backup: Path, data_dir: Path, digest: object, required: set[str], label: str
) -> dict[str, BackupArtifact | None]:
    if backup.resolve() != backup:
        _conflict(f"noncanonical backup identity: {backup}")
    if sha256_file(backup / BACKUP_MANIFEST) != digest:
        _conflict(f"manifest digest differs: {backup}")
    report = verify_backup(backup)
    if not report.ok:
        _conflict(f"unverified backup: {backup}: {report.failures}")
    manifest = _load_manifest(backup)
    entries = _manifest_entries(manifest)
    if (
        manifest.data_dir != str(data_dir.resolve())
        or manifest.label != label
        or not required.issubset(entries)
    ):
        _conflict(f"backup scope or identity differs: {backup}")
    return entries


def _backup_digest(backup: str | None) -> str:
    if backup is None:
        raise SystemExit("governed recovery conflict: required backup was not created")
    report = verify_backup(backup)
    if not report.ok:
        _conflict(f"backup verification failed: {report.failures}")
    return sha256_file(Path(backup) / BACKUP_MANIFEST)


def protect_setup(
    data_dir: Path,
    prior: dict[str, object],
    pending: dict[str, object],
    requests: tuple[m.InitializeRepositoryRequest, ...],
    pointer: dict[str, str],
) -> str | None:
    """Protect the exact pre-setup state before pending or managed-file publication."""
    from span.core import model as m

    canonical = m.to_canonical(requests)
    pointer_digest = hashlib.sha256(
        (json.dumps(pointer, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    if governed.PENDING in prior:
        if "restore_intent" in pending:
            _conflict("restore is in progress; resume the authorized restore")
        if "setup_requests" in pending and (
            pending["setup_requests"] != canonical
            or pending["pointer_digest"] != pointer_digest
        ):
            _conflict("selected authority configuration or indexer pointer changed")
        saved = pending.get("backup")
        if "backup_manifest_digest" in pending:
            required_names = set(_database_names(pending)) | set(_generated_files(pending))
            _verified_manifest(
                Path(governed._string(saved)),
                data_dir,
                pending["backup_manifest_digest"],
                required_names | {_POINTER, _RECEIPT},
                "governed-pre-setup",
            )
        return None if saved is None else governed._string(saved)

    pending["setup_requests"] = canonical
    pending["pointer_digest"] = pointer_digest
    pending["root_identities"] = {
        repository_id: _identity(Path(request.repository_locator))
        for repository_id, request in _requests(pending).items()
    }
    names = _database_names(pending)
    store_paths = {name: _safe_file(data_dir, name) for name in names}
    pending["prior_store_identities"] = {
        name: _identity(path) if path.is_file() else None
        for name, path in store_paths.items()
    }
    pending["created_stores"] = {}
    pending["staging_started"] = []
    files = _generated_files(pending)
    backup = create_backup(
        data_dir,
        label="governed-pre-setup",
        required_databases=names,
        governed_files=files,
    )
    pending["backup_manifest_digest"] = _backup_digest(backup)
    return str(Path(governed._string(backup)).resolve())


def _stage_path(data_dir: Path, pending: dict[str, object], name: str) -> Path:
    backup_name = Path(governed._string(pending["backup"])).name
    return _safe_file(data_dir, f".governed-store-staging/{backup_name}/{name}")


def _retire_stage(stage: Path, identity: object) -> None:
    if stage.exists():
        if _identity(stage) != identity:
            _conflict(f"staged store identity differs: {stage}")
        durable_unlink(stage)
    # Only remove the operation's empty staging directories, never other files.
    parent = stage.parent
    while parent.name != ".governed-store-staging":
        try:
            parent.rmdir()
        except OSError:
            break
        fsync_directory(parent.parent)
        parent = parent.parent


def _save_pending(data_dir: Path, pending: dict[str, object]) -> None:
    receipt = read_receipt(data_dir)
    if receipt is None or governed.PENDING not in receipt:
        _conflict("pending receipt disappeared")
    write_receipt(data_dir, {**receipt, governed.PENDING: pending})


def _empty_store_digest(create: Callable[[Path], None]) -> str:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "expected.db"
        create(path)
        return _database_digest(path)


def prepare_store(
    data_dir: Path,
    pending: dict[str, object],
    destination: Path,
    create: Callable[[Path], None],
) -> None:
    """Reserve the inode of an empty store before publishing its canonical path."""
    name = destination.relative_to(data_dir).as_posix()
    prior = governed._object(pending["prior_store_identities"])
    if name not in prior:
        _conflict(f"unselected store: {name}")
    destination = _safe_file(data_dir, name)
    if prior[name] is not None:
        if not destination.is_file() or _identity(destination) != prior[name]:
            _conflict(f"prior store identity changed: {name}")
        return

    created = governed._object(pending["created_stores"])
    stage = _stage_path(data_dir, pending, name)
    if destination.exists():
        if created.get(name) != _identity(destination):
            _conflict(f"unexplained store creation: {name}")
        _retire_stage(stage, created[name])
        return
    if name not in created:
        started = governed._array(pending["staging_started"])
        if name not in started:
            if stage.exists():
                _conflict(f"unverified staged store: {stage}")
            pending["staging_started"] = [*started, name]
            _save_pending(data_dir, pending)
        stage.parent.mkdir(parents=True, exist_ok=True)
        if not stage.exists():
            stage.touch(exist_ok=False)
        if stage.stat().st_size == 0:
            create(stage)
        if _database_digest(stage) != _empty_store_digest(create):
            _conflict(f"staged store is not the canonical empty state: {stage}")
        with stage.open("rb") as handle:
            os.fsync(handle.fileno())
        fsync_directory(stage.parent)
        created[name] = _identity(stage)
        pending["created_stores"] = created
        _save_pending(data_dir, pending)
    if not stage.is_file() or _identity(stage) != created[name]:
        _conflict(f"reserved staged store unavailable: {stage}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.link(stage, destination)
    fsync_directory(destination.parent)
    _retire_stage(stage, created[name])


def _database_digest(path: Path) -> str:
    with contextlib.closing(sqlite3.connect(read_only_uri(path), uri=True)) as db:
        return logical_database_digest(db)


def _expected_repository_states(
    baseline: Path | None, repository_id: str, request: m.InitializeRepositoryRequest
) -> set[str | None]:
    from tempfile import TemporaryDirectory

    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore

    with TemporaryDirectory() as tmp:
        expected = Path(tmp) / "expected.db"
        if baseline is not None:
            copy_database(baseline, expected)
        store = LifecycleStore(
            expected,
            retention=DEFAULT_LIFECYCLE_RETENTION,
            initialize_schema=baseline is None,
        )
        try:
            allowed: set[str | None] = {_database_digest(expected)}
            if baseline is None:
                allowed.add(None)
            store.register_repository(
                repository_id,
                request.repository_locator,
                authority_seeds=(
                    store.load_authority_seeds(repository_id)
                    if request.authority_seeds is None
                    else request.authority_seeds
                ),
                authority_bindings=(
                    store.load_authority_bindings(repository_id)
                    if request.authority_bindings is None
                    else request.authority_bindings
                ),
            )
            allowed.add(_database_digest(expected))
        finally:
            store.close()
        return allowed


def _empty_database_digest(name: str) -> str:
    from span.shell.context import (
        create_empty_installation_store,
        create_empty_repository_store,
    )

    create = (
        create_empty_installation_store
        if name == _INSTALLATION_DB
        else create_empty_repository_store
    )
    return _empty_store_digest(create)


def owned_empty_repository_store(
    data_dir: Path, pending: dict[str, object], repository_id: str
) -> bool:
    """A reserved published empty store is a recoverable pre-registration state."""
    if "prior_store_identities" not in pending:
        return False
    name = f"{repository_id}.db"
    prior = governed._object(pending["prior_store_identities"])
    created = governed._object(pending["created_stores"])
    path = _safe_file(data_dir, name)
    return (
        name in prior
        and prior[name] is None
        and path.is_file()
        and created.get(name) == _identity(path)
        and _database_digest(path) == _empty_database_digest(name)
    )


def _assert_unaccepted(
    pending: dict[str, object], connection: sqlite3.Connection | None
) -> None:
    from span.core import model as m
    from span.shell.sqlite_store.functional_pyramid import _receipt

    request = pending.get("request_id")
    if request is None:
        return
    if pending.get("accepted_pyramid_id") is not None:
        _conflict("participation was accepted; resume the original request")
    if connection is not None:
        connection.row_factory = sqlite3.Row
        if _receipt(connection, m.RequestId(governed._string(request))) is not None:
            _conflict("participation was accepted; resume the original request")


def _database_preconditions(
    data_dir: Path,
    pending: dict[str, object],
    backup: Path,
    baseline: dict[str, BackupArtifact | None],
    connections: dict[str, sqlite3.Connection],
) -> dict[str, str | None]:
    """Prove all selected store contents, including every retained semantic row."""
    _assert_unaccepted(pending, connections.get(_INSTALLATION_DB))
    prior = governed._object(pending["prior_store_identities"])
    created = governed._object(pending["created_stores"])
    requests = _requests(pending)
    result: dict[str, str | None] = {}
    for name in _database_names(pending):
        before = backup / name if baseline[name] is not None else None
        connection = connections.get(name)
        path = _safe_file(data_dir, name)
        if (before is None) != (prior.get(name) is None):
            _conflict(f"prior database ownership differs from backup: {name}")
        if connection is not None:
            identity = prior[name] if before is not None else created.get(name)
            if identity is None or _identity(path) != identity:
                _conflict(f"unexplained database identity: {name}")
        current = None if connection is None else logical_database_digest(connection)
        if name == _INSTALLATION_DB:
            allowed: set[str | None] = (
                {_database_digest(before)}
                if before is not None
                else {None, _empty_database_digest(name)}
            )
        else:
            repository_id = Path(name).stem
            allowed = _expected_repository_states(
                before, repository_id, requests[repository_id]
            )
        if current not in allowed:
            _conflict(f"independent or unverifiable store changes: {name}")
        stage = _stage_path(data_dir, pending, name)
        if stage.exists() and created.get(name) != _identity(stage):
            if (
                connection is not None
                or before is not None
                or name in created
                or name not in governed._array(pending["staging_started"])
                or (
                    stage.stat().st_size != 0
                    and _database_digest(stage) != _empty_database_digest(name)
                )
            ):
                _conflict(f"unverified staged store: {stage}")
            created[name] = _identity(stage)
            pending["created_stores"] = created
        if before is None and connection is not None:
            if any(
                Path(str(path) + suffix).exists()
                for suffix in ("-wal", "-shm", "-journal")
            ):
                _conflict(f"database sidecar prevents safe retirement: {name}")
        result[name] = current
    return result


def _file_preconditions(
    paths: dict[str, Path],
    baseline: dict[str, BackupArtifact | None],
    planned: dict[str, object],
) -> dict[str, str | None]:
    result = {}
    for name, path in paths.items():
        old = baseline[name]
        before = None if old is None else old.sha256
        current = _file_digest(path)
        if current not in (before, planned[name]):
            _conflict(f"unexpected generated/support bytes: {path}")
        result[name] = current
    return result


def _snapshot_states(
    snapshot: Path,
    entries: dict[str, BackupArtifact | None],
    names: tuple[str, ...],
    files: dict[str, Path],
) -> dict[str, str | None]:
    states = {
        name: None if entries[name] is None else _database_digest(snapshot / name)
        for name in names
    }
    for name in files:
        item = entries[name]
        states[name] = None if item is None else item.sha256
    return states


def _restore_snapshot(
    data_dir: Path,
    receipt: dict[str, object],
    pending: dict[str, object],
    backup: Path,
    backup_root: str | Path | None,
    names: tuple[str, ...],
    files: dict[str, Path],
    connections: dict[str, sqlite3.Connection],
    current: dict[str, str | None],
    baseline: dict[str, str | None],
) -> Path:
    required = set(names) | set(files) | {_RECEIPT}
    if "restore_intent" in pending:
        intent = governed._object(pending["restore_intent"])
        if (
            intent.get("backup") != str(backup)
            or intent.get("backup_digest") != pending["backup_manifest_digest"]
            or intent.get("effects") != sorted(required)
        ):
            _conflict("restore intent differs from requested baseline or scope")
        snapshot = Path(governed._string(intent["snapshot"]))
        entries = _verified_manifest(
            snapshot,
            data_dir,
            intent["snapshot_digest"],
            required,
            "governed-pre-restore",
        )
        observed = _snapshot_states(snapshot, entries, names, files)
        for name, state in current.items():
            if state not in (observed[name], baseline[name]):
                _conflict(f"state changed after restore intent: {name}")
        return snapshot

    snapshot_name = create_backup(
        data_dir,
        backup_root=backup_root,
        label="governed-pre-restore",
        required_databases=names,
        governed_files={name: path for name, path in files.items() if name != _POINTER},
        locked_databases=connections,
    )
    digest = _backup_digest(snapshot_name)
    snapshot = Path(governed._string(snapshot_name)).resolve()
    pending["restore_intent"] = {
        "backup": str(backup),
        "backup_digest": pending["backup_manifest_digest"],
        "snapshot": str(snapshot),
        "snapshot_digest": digest,
        "effects": sorted(required),
    }
    write_receipt(data_dir, {**receipt, governed.PENDING: pending})
    return snapshot


def _restore_file(path: Path, backup: Path, item: BackupArtifact | None) -> None:
    expected = None if item is None else item.sha256
    if _file_digest(path) == expected:
        return
    if item is None:
        durable_unlink(path)
    else:
        publish_install_bytes(path, (backup / item.path).read_bytes(), replace=True)
    if _file_digest(path) != expected:
        _conflict(f"restored bytes differ: {path}")


def _restore_database(
    path: Path,
    backup: Path,
    item: BackupArtifact | None,
    connection: sqlite3.Connection | None,
) -> None:
    if item is None:
        if connection is not None:
            durable_unlink(path)
        if path.exists():
            _conflict(f"retired database remains present: {path}")
        return
    if connection is None:
        _conflict(f"prior database is absent: {path}")
        return
    source = backup / item.path
    expected = _database_digest(source)
    if logical_database_digest(connection) != expected:
        with contextlib.closing(
            sqlite3.connect(read_only_uri(source), uri=True)
        ) as src:
            src.backup(connection)
    if logical_database_digest(connection) != expected:
        _conflict(f"restored database differs: {path}")


def _restore_effects(
    data_dir: Path,
    pending: dict[str, object],
    backup: Path,
    entries: dict[str, BackupArtifact | None],
    files: dict[str, Path],
    names: tuple[str, ...],
    connections: dict[str, sqlite3.Connection],
    current: dict[str, str | None],
) -> tuple[str, ...]:
    created = governed._object(pending["created_stores"])
    restored = []
    for name, path in sorted(files.items()):
        if _file_digest(path) != current[name]:
            _conflict(f"file changed after restore verification: {path}")
        _restore_file(path, backup, entries[name])
        restored.append(str(path))
    for name in names:
        stage = _stage_path(data_dir, pending, name)
        if stage.exists():
            _retire_stage(stage, created.get(name))
        path = _safe_file(data_dir, name)
        _restore_database(path, backup, entries[name], connections.get(name))
        restored.append(str(path))
    # Verify the entire affected scope again before the final receipt.
    if _generated_files(pending) != {
        name: path for name, path in files.items() if name != _POINTER
    }:
        _conflict("generated root scope changed during restore")
    for name, path in files.items():
        item = entries[name]
        if _file_digest(path) != (None if item is None else item.sha256):
            _conflict(f"restored file state changed: {path}")
    for name in names:
        item = entries[name]
        path = _safe_file(data_dir, name)
        if item is None:
            if path.exists():
                _conflict(f"retired database reappeared: {name}")
        elif not path.is_file() or logical_database_digest(
            connections[name]
        ) != _database_digest(backup / name):
            _conflict(f"restored database state changed: {name}")
    # Receipt is the final publication; it cannot hide incomplete reconciliation.
    _restore_file(data_dir / _RECEIPT, backup, entries[_RECEIPT])
    restored.append(str(data_dir / _RECEIPT))
    return tuple(restored)


def _restore_pending(
    backup: Path,
    data_dir: Path,
    backup_root: str | Path | None,
    receipt: dict[str, object],
    connections: dict[str, sqlite3.Connection],
) -> RestoreResult:
    pending = governed._object(receipt[governed.PENDING])
    if "backup_manifest_digest" not in pending:
        _conflict(
            "legacy pending setup lacks verified preimages; resume its original input"
        )
    if backup.resolve() != Path(governed._string(pending["backup"])):
        _conflict("restore requires the exact original pre-setup backup")
    backup = backup.resolve()
    files = _generated_files(pending)
    files[_POINTER] = _safe_file(data_dir, _POINTER)
    names = _database_names(pending)
    required = set(names) | set(files) | {_RECEIPT}
    entries = _verified_manifest(
        backup,
        data_dir,
        pending["backup_manifest_digest"],
        required,
        "governed-pre-setup",
    )
    current = _database_preconditions(data_dir, pending, backup, entries, connections)
    current.update(_file_preconditions(files, entries, _planned_files(pending)))
    baseline = _snapshot_states(backup, entries, names, files)
    snapshot = _restore_snapshot(
        data_dir,
        receipt,
        pending,
        backup,
        backup_root,
        names,
        files,
        connections,
        current,
        baseline,
    )
    restored = _restore_effects(
        data_dir, pending, backup, entries, files, names, connections, current
    )
    return RestoreResult(
        restored=restored, pre_restore_backup=str(snapshot), schema_actions=()
    )


def pending_restore(
    backup: Path, data_dir: Path, backup_root: str | Path | None
) -> RestoreResult | None:
    """Dispatch only pending governed abandonment; ordinary restore is unchanged."""
    from span.shell.sqlite_ownership import (
        StoreHeldError,
        exclusive_ownership,
        store_use_ownership,
    )

    receipt_path = data_dir / _RECEIPT
    if not receipt_path.is_file():
        return None
    try:
        raw = json.loads(receipt_path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or governed.PENDING not in raw:
        return None
    try:
        with (
            store_use_ownership(data_dir, exclusive=True),
            contextlib.ExitStack() as stack,
        ):
            receipt = read_receipt(data_dir)
            if receipt is None or governed.PENDING not in receipt:
                _conflict("pending receipt changed before recovery ownership")
                return None
            databases = sorted(data_dir.glob("*.db"))
            installation = data_dir / _INSTALLATION_DB
            if installation.is_file():
                databases.append(installation)
            connections = {
                path.relative_to(data_dir).as_posix(): stack.enter_context(
                    exclusive_ownership(
                        _safe_file(data_dir, path.relative_to(data_dir).as_posix())
                    )
                )
                for path in databases
            }
            return _restore_pending(backup, data_dir, backup_root, receipt, connections)
    except (StoreHeldError, OSError, sqlite3.Error, ValueError, KeyError) as exc:
        raise SystemExit(f"governed recovery conflict: {exc}") from None
