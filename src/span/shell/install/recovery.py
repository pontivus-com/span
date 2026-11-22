"""Operator-facing data-directory backup, verification, restore and reaping.

Stdlib only at import time: the installer runs from a source checkout before
Span is installed, so this module may not import ``span.*`` eagerly. Semantic
imports happen lazily inside the checks that need the store contract.

The recovery artifact is one directory holding:

- every top-level ``*.db`` copied through the SQLite online backup API;
- the install receipt and managed indexer pointer, when present;
- ``manifest.json``, the serialized canonical :class:`BackupManifest`;
- ``manifest.sha256`` binding the manifest itself.

``structural/`` and ``transitions/`` are excluded for stated reasons recorded in
the manifest: the structural index is regenerable from the target tree, and
transition archives are rollback copies of superseded stores rather than part
of current recoverable state. The policy and operator runbook live in
``docs/recovery.md``.
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
    sha256_file,
    utc_stamp,
)
from span.shell.install.constants import INSTALL_VERSION
from span.shell.install.manifest import (
    BackupArtifact,
    BackupManifest,
    BackupManifestError,
    BackupVerification,
    ManifestReason,
    RestoreResult,
    VerifiedArtifact,
)

BACKUP_MANIFEST = "manifest.json"
BACKUP_MANIFEST_DIGEST = "manifest.sha256"

#: Data-directory files that carry recoverable installation state.
SUPPORT_FILES = ("install.json", "structural-indexer.json")

#: Directories excluded from every backup artifact, with the reason recorded.
EXCLUDED_DIRECTORIES = (
    (
        "structural",
        "regenerable structural index: rebuilt from the target tree; "
        "not state of record",
    ),
    (
        "transitions",
        "superseded-store rollback archives: not current state; the "
        "transition command owns that rollback path",
    ),
)


def _installer_identity():
    """Record the running code version, not an unrelated installed package.

    The installer may run from a source checkout while a different Span
    distribution is installed elsewhere; the artifact's compatibility fact must
    describe the code that produced it.
    """
    try:
        from span import __version__ as version
    except (ImportError, AttributeError):
        version = None
    return {"install_version": INSTALL_VERSION, "span_version": version}


def _backup_root(data_dir, backup_root):
    return Path(backup_root) if backup_root is not None else Path(data_dir) / "backups"


def create_backup(data_dir, backup_root=None, label="operator", dry_run=False):
    """Take one verified point-in-time backup and write its manifest.

    Returns the artifact directory, or ``None`` when the data dir or its
    databases are absent (a fresh install has nothing to protect). A partial
    artifact is removed rather than left as a false recovery point.
    """
    data_dir = Path(data_dir)
    if dry_run or not data_dir.is_dir():
        return None
    installation_db = data_dir / "installation" / "functional-pyramid.db"
    databases = sorted(
        [
            *(path for path in data_dir.glob("*.db") if path.is_file()),
            *([installation_db] if installation_db.is_file() else []),
        ]
    )
    if not databases:
        return None
    root = _backup_root(data_dir, backup_root)
    destination = root / utc_stamp()
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SystemExit(f"cannot create backup dir {destination}: {exc}")
    try:
        artifacts = []
        absent = []
        for db in databases:
            relative = db.relative_to(data_dir)
            copied = destination / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            copy_database(db, copied)
            artifacts.append(
                BackupArtifact(
                    path=str(relative),
                    sha256=sha256_file(copied),
                    size_bytes=copied.stat().st_size,
                    database=database_facts(copied),
                )
            )
        for name in SUPPORT_FILES:
            source = data_dir / name
            if not source.is_file():
                absent.append(
                    ManifestReason(path=name, reason="not present at backup time")
                )
                continue
            copied = destination / name
            shutil.copy2(source, copied)
            artifacts.append(
                BackupArtifact(
                    path=name,
                    sha256=sha256_file(copied),
                    size_bytes=copied.stat().st_size,
                )
            )
        identity = _installer_identity()
        manifest = BackupManifest(
            label=label,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            data_dir=str(data_dir.resolve()),
            install_version=identity["install_version"],
            span_version=identity["span_version"],
            artifacts=tuple(artifacts),
            absent=tuple(absent),
            excluded=tuple(
                ManifestReason(path=path, reason=reason)
                for path, reason in EXCLUDED_DIRECTORIES
            ),
        )
        manifest_bytes = (
            json.dumps(manifest.payload(), indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        (destination / BACKUP_MANIFEST).write_bytes(manifest_bytes)
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        (destination / BACKUP_MANIFEST_DIGEST).write_text(
            f"{digest}  {BACKUP_MANIFEST}\n"
        )
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    print(
        f"data dir backed up: {destination} "
        f"({len(databases)} databases, {len(artifacts) - len(databases)} files)."
    )
    return str(destination)


def _supported_schemas():
    """Return the current schema and the offline-transition source schemas."""
    try:
        from span.shell.sqlite_store.lifecycle import SCHEMA_VERSION
        from span.shell.store_transition import SUPPORTED_SOURCE_SCHEMAS
    except Exception as exc:  # pragma: no cover - broken checkout only
        raise SystemExit(
            "cannot determine the supported store schema from this checkout: "
            f"{exc}. Recovery verification needs an intact Span source tree."
        )
    return SCHEMA_VERSION, frozenset(SUPPORTED_SOURCE_SCHEMAS)


def _database_schema_supported(
    name: str,
    version: int,
    current: int,
    supported: frozenset[int],
) -> bool:
    """Recognize repository lifecycle and installation-store schema identities."""
    if name == "installation/functional-pyramid.db":
        from span.shell.sqlite_store.functional_pyramid import (
            INSTALLATION_SCHEMA_VERSION,
        )

        return version == INSTALLATION_SCHEMA_VERSION
    return version == current or version in supported


def _load_manifest(backup_dir):
    backup_dir = Path(backup_dir)
    manifest_path = backup_dir / BACKUP_MANIFEST
    digest_path = backup_dir / BACKUP_MANIFEST_DIGEST
    if not manifest_path.is_file():
        raise SystemExit(
            f"not a recovery artifact (no {BACKUP_MANIFEST}): {backup_dir}"
        )
    if not digest_path.is_file():
        raise SystemExit(
            f"recovery artifact has no {BACKUP_MANIFEST_DIGEST}: {backup_dir}"
        )
    manifest_bytes = manifest_path.read_bytes()
    line = digest_path.read_text().strip().split()
    if len(line) != 2 or line[1] != BACKUP_MANIFEST:
        raise SystemExit(f"malformed {BACKUP_MANIFEST_DIGEST} in {backup_dir}")
    if hashlib.sha256(manifest_bytes).hexdigest() != line[0]:
        raise SystemExit(f"{BACKUP_MANIFEST} does not match its digest: {backup_dir}")
    try:
        payload = json.loads(manifest_bytes)
    except ValueError as exc:
        raise SystemExit(f"unreadable {BACKUP_MANIFEST} in {backup_dir}: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit(f"unsupported recovery artifact format in {backup_dir}")
    try:
        return BackupManifest.parse(payload)
    except BackupManifestError as exc:
        raise SystemExit(
            f"unsupported recovery manifest in {backup_dir}: {exc}"
        ) from None


def _artifact_path(backup_dir, name):
    candidate = Path(name)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SystemExit(f"recovery artifact path escapes the backup: {name}")
    return Path(backup_dir) / candidate


def verify_backup(backup_dir):
    """Verify artifact identity, database integrity and schema compatibility."""
    backup_dir = Path(backup_dir)
    manifest = _load_manifest(backup_dir)
    current, supported = _supported_schemas()
    failures: list[str] = []
    results: list[VerifiedArtifact] = []
    for artifact in manifest.artifacts:
        name = artifact.path
        path = _artifact_path(backup_dir, name)
        if not path.is_file():
            failures.append(f"{name}: missing")
            results.append(
                VerifiedArtifact(
                    path=name,
                    sha256=artifact.sha256,
                    size_bytes=artifact.size_bytes,
                    sha256_ok=False,
                    size_ok=False,
                    database=artifact.database,
                    missing=True,
                )
            )
            continue
        size_ok = path.stat().st_size == artifact.size_bytes
        sha256_ok = sha256_file(path) == artifact.sha256
        if not size_ok:
            failures.append(f"{name}: size does not match the manifest")
        if not sha256_ok:
            failures.append(f"{name}: sha256 does not match the manifest")
        database = artifact.database
        unreadable = None
        if path.suffix == ".db":
            try:
                database = database_facts(path)
            except sqlite3.Error as exc:
                unreadable = f"unreadable: {exc}"
                failures.append(f"{name}: unreadable database ({exc})")
            else:
                if database.integrity != "ok":
                    failures.append(
                        f"{name}: integrity check reported {database.integrity}"
                    )
                version = database.schema_version
                if version is None:
                    failures.append(f"{name}: no readable meta.schema_version")
                elif not _database_schema_supported(name, version, current, supported):
                    failures.append(f"{name}: unsupported database schema {version}")
        results.append(
            VerifiedArtifact(
                path=name,
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
                sha256_ok=sha256_ok,
                size_ok=size_ok,
                database=database,
                unreadable=unreadable,
            )
        )
    return BackupVerification(
        ok=not failures,
        backup=str(backup_dir),
        label=manifest.label,
        created_at=manifest.created_at,
        artifacts=tuple(results),
        excluded=manifest.excluded,
        failures=tuple(failures),
    )


def _assert_quiescent(data_dir):
    """Hold the shared exclusive-ownership rule for every current store."""
    from span.shell.sqlite_ownership import StoreHeldError, exclusive_ownership

    with ExitStack() as stack:
        installation_db = Path(data_dir) / "installation" / "functional-pyramid.db"
        databases = [
            *sorted(Path(data_dir).glob("*.db")),
            *([installation_db] if installation_db.is_file() else []),
        ]
        for db in databases:
            try:
                stack.enter_context(exclusive_ownership(db))
            except StoreHeldError as exc:
                raise SystemExit(
                    "store is held by a live process; stop every Span "
                    f"server and hook before restoring ({db}: {exc})"
                ) from None


def _restore_artifact(backup_dir, data_dir, artifact):
    source = _artifact_path(backup_dir, artifact.path)
    destination = Path(data_dir) / artifact.path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix == ".db":
        for suffix in ("-wal", "-shm", "-journal"):
            stale = Path(str(destination) + suffix)
            if stale.exists():
                stale.unlink()
    shutil.copy2(source, destination)
    if sha256_file(destination) != artifact.sha256:
        raise SystemExit(f"restored file does not match the manifest: {destination}")
    return destination


def restore_backup(backup_dir, data_dir, confirm, backup_root=None, dry_run=False):
    """Restore one verified artifact into ``data_dir``.

    The caller must repeat the artifact directory name in ``confirm``. The
    current data dir is snapshotted before anything is replaced. ``structural/``
    is left in place because it is regenerable; the report says so.
    """
    backup_dir = Path(backup_dir)
    data_dir = Path(data_dir)
    if confirm != backup_dir.name:
        raise SystemExit(
            "restore requires --restore-confirm "
            f"{backup_dir.name!r} (the artifact directory name)"
        )
    report = verify_backup(backup_dir)
    if not report.ok:
        for failure in report.failures:
            print(f"  {failure}", file=sys.stderr)
        raise SystemExit(f"refusing to restore an unverified artifact: {backup_dir}")
    _assert_quiescent(data_dir)
    snapshot = create_backup(data_dir, backup_root=backup_root, label="pre-restore")
    if dry_run:
        print(f"+ restore (dry-run, not executed): {backup_dir} -> {data_dir}")
        return RestoreResult(
            restored=(), pre_restore_backup=snapshot, schema_actions=(), dry_run=True
        )
    restored = []
    for artifact in report.artifacts:
        destination = _restore_artifact(backup_dir, data_dir, artifact)
        restored.append(str(destination))
    current, _ = _supported_schemas()
    actions = []
    for artifact in report.artifacts:
        if artifact.database is None:
            continue
        if artifact.path == "installation/functional-pyramid.db":
            continue
        repository_id = Path(artifact.path).stem
        if artifact.database.schema_version != current:
            actions.append(
                f"run `span-install --data-dir {data_dir} --transition-store "
                f"{repository_id} --transition-phase inspect --transition-root "
                "<TARGET_REPO>` before using this store"
            )
    print(f"data dir restored: {backup_dir} -> {data_dir} ({len(restored)} files).")
    print(f"pre-restore snapshot: {snapshot}")
    print(
        "structural index left in place: it is regenerable and rebuilt from "
        "the target tree when stale."
    )
    for action in actions:
        print(f"action: {action}")
    return RestoreResult(
        restored=tuple(restored),
        pre_restore_backup=snapshot,
        schema_actions=tuple(actions),
    )


def _managed_backup_dirs(backup_root):
    root = Path(backup_root)
    if not root.is_dir():
        return []
    managed = []
    for candidate in sorted(root.iterdir(), reverse=True):
        if not candidate.is_dir():
            continue
        try:
            manifest = _load_manifest(candidate)
        except SystemExit:
            continue
        managed.append((candidate, manifest))
    return managed


def reap_backups(backup_root, keep, dry_run=False):
    """Delete all but the newest ``keep`` recognized recovery artifacts.

    ``keep`` is required and never defaulted: the recovery window is an
    operator decision, and Span does not invent a retention interval.
    Directories without a valid Span manifest are reported and left untouched.
    """
    if keep is None:
        raise SystemExit("--reap-backups requires an explicit KEEP count")
    if keep < 0:
        raise SystemExit("--reap-backups KEEP must be zero or greater")
    root = Path(backup_root)
    managed = _managed_backup_dirs(root)
    kept = managed[:keep]
    reaped = managed[keep:]
    for candidate, manifest in kept:
        print(f"+ keep backup: {candidate} ({manifest.label})")
    for candidate, manifest in reaped:
        print(f"+ reap backup: {candidate} ({manifest.label})")
        if not dry_run:
            shutil.rmtree(candidate)
    recognized = {candidate for candidate, _ in managed}
    for candidate in sorted(root.iterdir()) if root.is_dir() else []:
        if candidate.is_dir() and candidate not in recognized:
            print(f"unmanaged directory left untouched: {candidate}")
    return {
        "kept": [str(candidate) for candidate, _ in kept],
        "reaped": [str(candidate) for candidate, _ in reaped],
        "dry_run": bool(dry_run),
    }
