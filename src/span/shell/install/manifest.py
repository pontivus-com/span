"""Typed carrier for the recovery manifest boundary (stdlib only).

The installer writes one manifest per backup artifact and the verifier/restorer
consume the same carrier. Creating serializes a :class:`BackupManifest`;
parsing validates every field and rejects an unknown format, so there is one
canonical shape rather than a second dict interpretation.

No ``span.*`` semantic import: this module runs before Span is installed.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Mapping

MANIFEST_FORMAT = "span-data-backup/1"


class BackupManifestError(ValueError):
    """The payload is not a recovery manifest this version can consume."""


def _mapping(payload: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise BackupManifestError(f"{field} must be an object")
    return value


def _only_keys(payload: Mapping[str, object], field: str, allowed: set[str]) -> None:
    unknown = set(payload) - allowed
    if unknown:
        raise BackupManifestError(f"{field} has unknown keys: {sorted(unknown)}")


def _string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise BackupManifestError(f"{field} must be a non-empty string")
    return value


def _optional_string(payload: Mapping[str, object], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise BackupManifestError(f"{field} must be a non-empty string or null")
    return value


def _integer(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BackupManifestError(f"{field} must be a non-negative integer")
    return value


def _optional_integer(payload: Mapping[str, object], field: str) -> int | None:
    value = payload.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BackupManifestError(f"{field} must be a non-negative integer or null")
    return value


def _digest(payload: Mapping[str, object], field: str) -> str:
    value = _string(payload, field)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise BackupManifestError(f"{field} must be a lowercase sha256 digest")
    return value


def _relative_path(payload: Mapping[str, object], field: str) -> str:
    value = _string(payload, field)
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise BackupManifestError(f"{field} must stay inside the artifact")
    return value


def _items(
    payload: Mapping[str, object], field: str
) -> tuple[Mapping[str, object], ...]:
    value = payload.get(field)
    if not isinstance(value, list):
        raise BackupManifestError(f"{field} must be a list")
    items: list[Mapping[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise BackupManifestError(f"{field}[{index}] must be an object")
        items.append(item)
    return tuple(items)


@dataclasses.dataclass(frozen=True)
class DatabaseFacts:
    """Observed facts for one backed-up database."""

    schema_version: int | None
    integrity: str
    max_conclusion_revision: int | None

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "integrity": self.integrity,
            "max_conclusion_revision": self.max_conclusion_revision,
        }

    @classmethod
    def parse(cls, payload: Mapping[str, object]) -> DatabaseFacts:
        _only_keys(
            payload,
            "database",
            {"schema_version", "integrity", "max_conclusion_revision"},
        )
        return cls(
            schema_version=_optional_integer(payload, "schema_version"),
            integrity=_string(payload, "integrity"),
            max_conclusion_revision=_optional_integer(
                payload, "max_conclusion_revision"
            ),
        )


@dataclasses.dataclass(frozen=True)
class BackupArtifact:
    """One file recorded in a recovery artifact."""

    path: str
    sha256: str
    size_bytes: int
    database: DatabaseFacts | None = None

    def payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }
        if self.database is not None:
            payload["database"] = self.database.payload()
        return payload

    @classmethod
    def parse(cls, payload: Mapping[str, object]) -> BackupArtifact:
        _only_keys(payload, "artifact", {"path", "sha256", "size_bytes", "database"})
        database: DatabaseFacts | None = None
        if payload.get("database") is not None:
            database = DatabaseFacts.parse(_mapping(payload, "database"))
        return cls(
            path=_relative_path(payload, "path"),
            sha256=_digest(payload, "sha256"),
            size_bytes=_integer(payload, "size_bytes"),
            database=database,
        )


@dataclasses.dataclass(frozen=True)
class ManifestReason:
    """A path with the stated reason it is absent or excluded."""

    path: str
    reason: str

    def payload(self) -> dict[str, object]:
        return {"path": self.path, "reason": self.reason}

    @classmethod
    def parse(cls, payload: Mapping[str, object]) -> ManifestReason:
        _only_keys(payload, "reason entry", {"path", "reason"})
        return cls(
            path=_string(payload, "path"),
            reason=_string(payload, "reason"),
        )


@dataclasses.dataclass(frozen=True)
class BackupManifest:
    """The canonical recovery-manifest boundary."""

    label: str
    created_at: str
    data_dir: str
    install_version: int
    span_version: str | None
    artifacts: tuple[BackupArtifact, ...]
    absent: tuple[ManifestReason, ...]
    excluded: tuple[ManifestReason, ...]
    format: str = MANIFEST_FORMAT

    def payload(self) -> dict[str, object]:
        return {
            "format": self.format,
            "label": self.label,
            "created_at": self.created_at,
            "data_dir": self.data_dir,
            "installer": {
                "install_version": self.install_version,
                "span_version": self.span_version,
            },
            "artifacts": [artifact.payload() for artifact in self.artifacts],
            "absent": [item.payload() for item in self.absent],
            "excluded": [item.payload() for item in self.excluded],
        }

    @classmethod
    def parse(cls, payload: Mapping[str, object]) -> BackupManifest:
        _only_keys(
            payload,
            "manifest",
            {
                "format",
                "label",
                "created_at",
                "data_dir",
                "installer",
                "artifacts",
                "absent",
                "excluded",
            },
        )
        manifest_format = _string(payload, "format")
        if manifest_format != MANIFEST_FORMAT:
            raise BackupManifestError(
                f"format {manifest_format!r} is not {MANIFEST_FORMAT!r}"
            )
        installer = _mapping(payload, "installer")
        _only_keys(installer, "installer", {"install_version", "span_version"})
        return cls(
            label=_string(payload, "label"),
            created_at=_string(payload, "created_at"),
            data_dir=_string(payload, "data_dir"),
            install_version=_integer(installer, "install_version"),
            span_version=_optional_string(installer, "span_version"),
            artifacts=tuple(
                BackupArtifact.parse(item) for item in _items(payload, "artifacts")
            ),
            absent=tuple(
                ManifestReason.parse(item) for item in _items(payload, "absent")
            ),
            excluded=tuple(
                ManifestReason.parse(item) for item in _items(payload, "excluded")
            ),
        )


@dataclasses.dataclass(frozen=True)
class VerifiedArtifact:
    """One artifact's verification result."""

    path: str
    sha256: str
    size_bytes: int
    sha256_ok: bool
    size_ok: bool
    database: DatabaseFacts | None
    missing: bool = False
    unreadable: str | None = None

    def payload(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "sha256_ok": self.sha256_ok,
            "size_ok": self.size_ok,
            "database": (
                self.database.payload() if self.database is not None else None
            ),
            "missing": self.missing,
            "unreadable": self.unreadable,
        }


@dataclasses.dataclass(frozen=True)
class BackupVerification:
    """The verification outcome for one recovery artifact."""

    ok: bool
    backup: str
    label: str
    created_at: str
    artifacts: tuple[VerifiedArtifact, ...]
    excluded: tuple[ManifestReason, ...]
    failures: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "backup": self.backup,
            "label": self.label,
            "created_at": self.created_at,
            "artifacts": [artifact.payload() for artifact in self.artifacts],
            "excluded": [item.payload() for item in self.excluded],
            "failures": self.failures,
        }


@dataclasses.dataclass(frozen=True)
class RestoreResult:
    """The outcome of restoring one verified artifact."""

    restored: tuple[str, ...]
    pre_restore_backup: str | None
    schema_actions: tuple[str, ...]
    dry_run: bool = False

    def payload(self) -> dict[str, object]:
        return {
            "restored": self.restored,
            "pre_restore_backup": self.pre_restore_backup,
            "schema_actions": self.schema_actions,
            "dry_run": self.dry_run,
        }


REPOSITORY_MANIFEST_FORMAT = "span-repository-backup/1"


@dataclasses.dataclass(frozen=True)
class RepositoryBackupManifest:
    """One repository's deployable artifact, stored inside that repository."""

    repository_id: str
    source_root: str
    created_at: str
    span_version: str | None
    artifact: BackupArtifact
    format: str = REPOSITORY_MANIFEST_FORMAT

    def payload(self) -> dict[str, object]:
        return {
            "format": self.format,
            "repository_id": self.repository_id,
            "source_root": self.source_root,
            "created_at": self.created_at,
            "span_version": self.span_version,
            "artifact": self.artifact.payload(),
        }

    @classmethod
    def parse(cls, payload: Mapping[str, object]) -> RepositoryBackupManifest:
        _only_keys(
            payload,
            "repository manifest",
            {
                "format",
                "repository_id",
                "source_root",
                "created_at",
                "span_version",
                "artifact",
            },
        )
        manifest_format = _string(payload, "format")
        if manifest_format != REPOSITORY_MANIFEST_FORMAT:
            raise BackupManifestError(
                f"format {manifest_format!r} is not " f"{REPOSITORY_MANIFEST_FORMAT!r}"
            )
        repository_id = _string(payload, "repository_id")
        source_root = _string(payload, "source_root")
        if not Path(source_root).is_absolute():
            raise BackupManifestError("source_root must be an absolute path")
        artifact = BackupArtifact.parse(_mapping(payload, "artifact"))
        if artifact.database is None:
            raise BackupManifestError("artifact must carry database facts")
        if artifact.path != f"{repository_id}.db":
            raise BackupManifestError(
                "artifact path must be the repository store " f"{repository_id}.db"
            )
        return cls(
            repository_id=repository_id,
            source_root=source_root,
            created_at=_string(payload, "created_at"),
            span_version=_optional_string(payload, "span_version"),
            artifact=artifact,
        )


@dataclasses.dataclass(frozen=True)
class RepositoryVerification:
    """Verification outcome for one repository artifact."""

    ok: bool
    artifact_dir: str
    manifest: RepositoryBackupManifest
    artifact: VerifiedArtifact
    failures: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "artifact_dir": self.artifact_dir,
            "repository_id": self.manifest.repository_id,
            "source_root": self.manifest.source_root,
            "artifact": self.artifact.payload(),
            "failures": self.failures,
        }


@dataclasses.dataclass(frozen=True)
class RepositoryLoadResult:
    """The outcome of loading one repository artifact for deployment."""

    repository_id: str
    root: str
    restored_store: str
    pre_load_backup: str | None
    rebound_from: str | None
    dry_run: bool = False

    def payload(self) -> dict[str, object]:
        return {
            "repository_id": self.repository_id,
            "root": self.root,
            "restored_store": self.restored_store,
            "pre_load_backup": self.pre_load_backup,
            "rebound_from": self.rebound_from,
            "dry_run": self.dry_run,
        }
