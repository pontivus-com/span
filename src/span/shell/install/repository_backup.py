"""Repository-portable backup, verification, load and reaping (stdlib only).

One repository's artifact lives inside that repository at
``<root>/.span/backups/<timestamp>/`` and is intended to be committed with the
code. Loading verifies the artifact, replaces the local store and explicitly
rebinds the recorded repository root to the clone's canonical root.

Stdlib only at import time: the installer runs from a source checkout before
Span is installed. Semantic imports happen lazily in load.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import sqlite3
import sys
from contextlib import ExitStack
from pathlib import Path

from span.shell.install.backup_io import (
    copy_database,
    database_facts,
    read_only_uri,
    sha256_file,
    utc_stamp,
)
from span.shell.install.manifest import (
    BackupArtifact,
    BackupManifestError,
    RepositoryBackupManifest,
    RepositoryLoadResult,
    RepositoryVerification,
    VerifiedArtifact,
)

MANIFEST = "manifest.json"
MANIFEST_DIGEST = "manifest.sha256"
BACKUP_DIRECTORY = Path(".span") / "backups"


def _running_version():
    try:
        from span import __version__ as version
    except (ImportError, AttributeError):
        return None
    return version


def _backup_root(root) -> Path:
    return Path(root) / BACKUP_DIRECTORY


def _store_path(data_dir, repository_id) -> Path:
    return Path(data_dir) / f"{repository_id}.db"


def _recorded_root(store, repository_id):
    connection = sqlite3.connect(read_only_uri(store), uri=True)
    try:
        row = connection.execute(
            "SELECT root FROM repositories WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
    finally:
        connection.close()
    return None if row is None else str(row[0])


def _load_manifest(artifact_dir) -> RepositoryBackupManifest:
    artifact_dir = Path(artifact_dir)
    manifest_path = artifact_dir / MANIFEST
    digest_path = artifact_dir / MANIFEST_DIGEST
    if not manifest_path.is_file():
        raise SystemExit(f"not a repository artifact (no {MANIFEST}): {artifact_dir}")
    if not digest_path.is_file():
        raise SystemExit(
            f"repository artifact has no {MANIFEST_DIGEST}: {artifact_dir}"
        )
    manifest_bytes = manifest_path.read_bytes()
    line = digest_path.read_text().strip().split()
    if len(line) != 2 or line[1] != MANIFEST:
        raise SystemExit(f"malformed {MANIFEST_DIGEST} in {artifact_dir}")
    if hashlib.sha256(manifest_bytes).hexdigest() != line[0]:
        raise SystemExit(f"{MANIFEST} does not match its digest: {artifact_dir}")
    try:
        payload = json.loads(manifest_bytes)
    except ValueError as exc:
        raise SystemExit(f"unreadable {MANIFEST} in {artifact_dir}: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit(f"unsupported repository artifact in {artifact_dir}")
    try:
        return RepositoryBackupManifest.parse(payload)
    except BackupManifestError as exc:
        raise SystemExit(
            f"unsupported repository manifest in {artifact_dir}: {exc}"
        ) from None


def _current_schema() -> int:
    try:
        from span.shell.sqlite_store.lifecycle import SCHEMA_VERSION
    except Exception as exc:  # pragma: no cover - broken checkout only
        raise SystemExit(
            "cannot determine the supported store schema from this checkout: "
            f"{exc}. Repository load needs an intact Span source tree."
        )
    return SCHEMA_VERSION


def create_repository_backup(root, data_dir, dry_run=False):
    """Write one deployable artifact into the repository and return its path."""
    root = Path(root).resolve()
    if dry_run:
        print(f"+ backup repository (dry-run, not executed): {root}")
        return None
    repository_id = root.name
    store = _store_path(data_dir, repository_id)
    if not store.is_file():
        raise SystemExit(
            f"no store for repository {repository_id!r} in {data_dir}; "
            f"run `span-install --repo {root}` first"
        )
    recorded = _recorded_root(store, repository_id)
    if recorded is None:
        raise SystemExit(
            f"store {store} has no binding for {repository_id!r}; "
            f"run `span-install --repo {root}` first"
        )
    if recorded != str(root):
        raise SystemExit(
            f"store {store} is bound to {recorded!r}, not {str(root)!r}; "
            "back up from the bound checkout or install this root first"
        )
    destination = _backup_root(root) / utc_stamp()
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SystemExit(f"cannot create artifact dir {destination}: {exc}")
    try:
        copied = destination / f"{repository_id}.db"
        copy_database(store, copied)
        artifact = BackupArtifact(
            path=f"{repository_id}.db",
            sha256=sha256_file(copied),
            size_bytes=copied.stat().st_size,
            database=database_facts(copied),
        )
        manifest = RepositoryBackupManifest(
            repository_id=repository_id,
            source_root=str(root),
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            span_version=_running_version(),
            artifact=artifact,
        )
        manifest_bytes = (
            json.dumps(manifest.payload(), indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        (destination / MANIFEST).write_bytes(manifest_bytes)
        (destination / MANIFEST_DIGEST).write_text(
            f"{hashlib.sha256(manifest_bytes).hexdigest()}  {MANIFEST}\n"
        )
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    print(
        f"repository backed up: {destination} "
        f"({artifact.size_bytes} bytes). Commit it with the repository."
    )
    return str(destination)


def verify_repository_backup(artifact_dir):
    """Verify one repository artifact without changing anything."""
    artifact_dir = Path(artifact_dir)
    manifest = _load_manifest(artifact_dir)
    current = _current_schema()
    failures: list[str] = []
    path = artifact_dir / manifest.artifact.path
    sha_ok = False
    size_ok = False
    database = manifest.artifact.database
    unreadable = None
    if not path.is_file():
        failures.append(f"{manifest.artifact.path}: missing")
    else:
        size_ok = path.stat().st_size == manifest.artifact.size_bytes
        sha_ok = sha256_file(path) == manifest.artifact.sha256
        if not size_ok:
            failures.append(f"{manifest.artifact.path}: size mismatch")
        if not sha_ok:
            failures.append(f"{manifest.artifact.path}: sha256 mismatch")
        try:
            database = database_facts(path)
        except sqlite3.Error as exc:
            unreadable = f"unreadable: {exc}"
            failures.append(f"{manifest.artifact.path}: unreadable database")
        else:
            if database.integrity != "ok":
                failures.append(
                    f"{manifest.artifact.path}: integrity " f"{database.integrity}"
                )
            if database.schema_version != current:
                failures.append(
                    f"{manifest.artifact.path}: schema "
                    f"{database.schema_version} is not current ({current})"
                )
    return RepositoryVerification(
        ok=not failures,
        artifact_dir=str(artifact_dir),
        manifest=manifest,
        artifact=VerifiedArtifact(
            path=manifest.artifact.path,
            sha256=manifest.artifact.sha256,
            size_bytes=manifest.artifact.size_bytes,
            sha256_ok=sha_ok,
            size_ok=size_ok,
            database=database,
            missing=not path.is_file(),
            unreadable=unreadable,
        ),
        failures=tuple(failures),
    )


def _newest_artifact(root) -> Path:
    candidates = []
    directory = _backup_root(root)
    if directory.is_dir():
        for candidate in sorted(directory.iterdir(), reverse=True):
            if not candidate.is_dir():
                continue
            try:
                _load_manifest(candidate)
            except SystemExit:
                continue
            candidates.append(candidate)
    if not candidates:
        raise SystemExit(
            f"no repository artifact under {directory}; "
            "back up the repository and commit the artifact first"
        )
    return candidates[0]


def _assert_quiescent(store):
    from span.shell.sqlite_ownership import StoreHeldError, exclusive_ownership

    if not Path(store).is_file():
        return
    with ExitStack() as stack:
        try:
            stack.enter_context(exclusive_ownership(store))
        except StoreHeldError as exc:
            raise SystemExit(
                "store is held by a live process; stop every Span server and "
                f"hook before loading ({store}: {exc})"
            ) from None


def load_repository_backup(root, data_dir, artifact=None, dry_run=False):
    """Load one verified repository artifact into the local data directory."""
    root = Path(root).resolve()
    repository_id = root.name
    artifact_dir = Path(artifact) if artifact is not None else _newest_artifact(root)
    report = verify_repository_backup(artifact_dir)
    if not report.ok:
        for failure in report.failures:
            print(f"  {failure}", file=sys.stderr)
        raise SystemExit(f"refusing to load an unverified artifact: {artifact_dir}")
    if report.manifest.repository_id != repository_id:
        raise SystemExit(
            f"artifact belongs to repository "
            f"{report.manifest.repository_id!r}, not {repository_id!r}; "
            "the clone directory name must match the artifact"
        )
    store = _store_path(data_dir, repository_id)
    _assert_quiescent(store)
    pre_load = None
    if Path(data_dir).is_dir() and any(Path(data_dir).glob("*.db")):
        from span.shell.install.recovery import create_backup

        pre_load = create_backup(data_dir, label="pre-load")
    if dry_run:
        print(
            f"+ load repository (dry-run, not executed): " f"{artifact_dir} -> {store}"
        )
        return RepositoryLoadResult(
            repository_id=repository_id,
            root=str(root),
            restored_store=str(store),
            pre_load_backup=pre_load,
            rebound_from=report.manifest.source_root,
            dry_run=True,
        )
    store.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm", "-journal"):
        stale = Path(str(store) + suffix)
        if stale.exists():
            stale.unlink()
    shutil.copy2(artifact_dir / report.manifest.artifact.path, store)
    if sha256_file(store) != report.manifest.artifact.sha256:
        raise SystemExit(f"restored store does not match the artifact: {store}")

    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore

    lifecycle = LifecycleStore(store, retention=DEFAULT_LIFECYCLE_RETENTION)
    try:
        lifecycle.rebind_repository(
            repository_id,
            str(root),
            expected_root=report.manifest.source_root,
        )
    finally:
        lifecycle.close()

    from span.shell.readiness import probe_store

    readiness = probe_store(data_dir, repository_id)
    print(f"repository loaded: {artifact_dir} -> {store} " f"(bound root {root})")
    print(f"pre-load backup: {pre_load}")
    print(f"store readiness: {readiness.payload()}")
    if not readiness.ready:
        raise SystemExit(
            f"loaded store is not ready: {readiness.action or 'unknown state'}"
        )
    return RepositoryLoadResult(
        repository_id=repository_id,
        root=str(root),
        restored_store=str(store),
        pre_load_backup=pre_load,
        rebound_from=report.manifest.source_root,
    )


def reap_repository_backups(root, keep, dry_run=False):
    """Delete all but the newest KEEP working-tree artifacts."""
    if keep is None:
        raise SystemExit("--reap-repository-backups requires an explicit KEEP")
    if keep < 0:
        raise SystemExit("--reap-repository-backups KEEP must be zero or greater")
    directory = _backup_root(root)
    managed = []
    if directory.is_dir():
        for candidate in sorted(directory.iterdir(), reverse=True):
            if not candidate.is_dir():
                continue
            try:
                manifest = _load_manifest(candidate)
            except SystemExit:
                continue
            managed.append((candidate, manifest))
    kept = managed[:keep]
    reaped = managed[keep:]
    for candidate, manifest in kept:
        print(f"+ keep artifact: {candidate} ({manifest.repository_id})")
    for candidate, manifest in reaped:
        print(f"+ reap artifact: {candidate} ({manifest.repository_id})")
        if not dry_run:
            shutil.rmtree(candidate)
    recognized = {candidate for candidate, _ in managed}
    if directory.is_dir():
        for candidate in sorted(directory.iterdir()):
            if candidate.is_dir() and candidate not in recognized:
                print(f"unmanaged directory left untouched: {candidate}")
    return {
        "kept": [str(candidate) for candidate, _ in kept],
        "reaped": [str(candidate) for candidate, _ in reaped],
        "dry_run": bool(dry_run),
    }
