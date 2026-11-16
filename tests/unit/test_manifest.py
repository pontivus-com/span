"""Unit tests for the canonical recovery-manifest carrier."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from span.shell.install.manifest import (
    BackupArtifact,
    BackupManifest,
    BackupManifestError,
    DatabaseFacts,
    ManifestReason,
)


def sample_manifest() -> BackupManifest:
    return BackupManifest(
        label="operator",
        created_at="2026-11-16T00:00:00+00:00",
        data_dir="/data",
        install_version=2,
        span_version="0.10.4",
        artifacts=(
            BackupArtifact(
                path="repo.db",
                sha256="a" * 64,
                size_bytes=10,
                database=DatabaseFacts(
                    schema_version=11,
                    integrity="ok",
                    max_conclusion_revision=3,
                ),
            ),
            BackupArtifact(
                path="install.json",
                sha256="b" * 64,
                size_bytes=5,
            ),
        ),
        absent=(ManifestReason(path="structural-indexer.json", reason="not present"),),
        excluded=(ManifestReason(path="structural", reason="regenerable"),),
    )


class ManifestCarrierTest(unittest.TestCase):
    def test_round_trip(self):
        manifest = sample_manifest()
        self.assertEqual(BackupManifest.parse(manifest.payload()), manifest)

    def test_rejects_unknown_format(self):
        payload = sample_manifest().payload()
        payload["format"] = "span-data-backup/2"
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_unknown_manifest_key(self):
        payload = sample_manifest().payload()
        payload["extra"] = True
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_unknown_artifact_key(self):
        payload = sample_manifest().payload()
        payload["artifacts"][0]["extra"] = True
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_escaping_artifact_path(self):
        payload = sample_manifest().payload()
        payload["artifacts"][0]["path"] = "../outside.db"
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_absolute_artifact_path(self):
        payload = sample_manifest().payload()
        payload["artifacts"][0]["path"] = "/etc/passwd"
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_malformed_digest(self):
        payload = sample_manifest().payload()
        payload["artifacts"][0]["sha256"] = "not-a-digest"
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_boolean_size(self):
        payload = sample_manifest().payload()
        payload["artifacts"][0]["size_bytes"] = True
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_non_object_installer(self):
        payload = sample_manifest().payload()
        payload["installer"] = "2"
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)

    def test_rejects_missing_list(self):
        payload = sample_manifest().payload()
        del payload["excluded"]
        with self.assertRaises(BackupManifestError):
            BackupManifest.parse(payload)


if __name__ == "__main__":
    unittest.main()


class RepositoryManifestTest(unittest.TestCase):
    def _manifest(self):
        from span.shell.install.manifest import (
            BackupArtifact,
            DatabaseFacts,
            RepositoryBackupManifest,
        )

        return RepositoryBackupManifest(
            repository_id="repo",
            source_root="/source/repo",
            created_at="2026-11-16T00:00:00+00:00",
            span_version="0.10.5",
            artifact=BackupArtifact(
                path="repo.db",
                sha256="c" * 64,
                size_bytes=100,
                database=DatabaseFacts(
                    schema_version=12,
                    integrity="ok",
                    max_conclusion_revision=4,
                ),
            ),
        )

    def test_round_trip(self):
        from span.shell.install.manifest import RepositoryBackupManifest

        manifest = self._manifest()
        self.assertEqual(RepositoryBackupManifest.parse(manifest.payload()), manifest)

    def test_rejects_artifact_name_mismatch(self):
        from span.shell.install.manifest import (
            BackupManifestError,
            RepositoryBackupManifest,
        )

        payload = self._manifest().payload()
        payload["artifact"]["path"] = "other.db"
        with self.assertRaises(BackupManifestError):
            RepositoryBackupManifest.parse(payload)

    def test_rejects_relative_source_root(self):
        from span.shell.install.manifest import (
            BackupManifestError,
            RepositoryBackupManifest,
        )

        payload = self._manifest().payload()
        payload["source_root"] = "repo"
        with self.assertRaises(BackupManifestError):
            RepositoryBackupManifest.parse(payload)

    def test_rejects_unknown_key(self):
        from span.shell.install.manifest import (
            BackupManifestError,
            RepositoryBackupManifest,
        )

        payload = self._manifest().payload()
        payload["extra"] = True
        with self.assertRaises(BackupManifestError):
            RepositoryBackupManifest.parse(payload)
