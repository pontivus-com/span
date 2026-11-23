"""Unit tests for repository-portable backup, load, rebind and reaping."""

import datetime
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from span.shell import install
from span.shell.install import repository_backup
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.readiness import probe_store
from span.shell.sqlite_store.lifecycle import LifecycleStore

NOW = datetime.datetime(2026, 11, 16, 12, 0, tzinfo=datetime.timezone.utc)


def _make_store(path, root):
    root.mkdir(parents=True, exist_ok=True)
    store = LifecycleStore(
        path, retention=DEFAULT_LIFECYCLE_RETENTION, clock=lambda: NOW
    )
    try:
        store.register_repository(root.name, str(root))
    finally:
        store.close()


class RepositoryBackupTest(unittest.TestCase):
    def test_backup_writes_repository_artifact_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "repo"
            data = base / "data"
            data.mkdir()
            _make_store(data / "repo.db", root)

            artifact = pathlib.Path(install.create_repository_backup(root, data))

            self.assertEqual(artifact.parent, root / ".span" / "backups")
            self.assertTrue((artifact / "repo.db").is_file())
            manifest = json.loads((artifact / "manifest.json").read_text())
            self.assertEqual(manifest["repository_id"], "repo")
            self.assertEqual(manifest["source_root"], str(root.resolve()))
            self.assertEqual(manifest["artifact"]["database"]["schema_version"], 15)
            self.assertTrue(
                (artifact / "manifest.sha256").read_text().endswith("  manifest.json\n")
            )
            report = install.verify_repository_backup(artifact)
            self.assertTrue(report.ok, report.failures)

    def test_verify_detects_tampering_and_legacy_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "repo"
            data = base / "data"
            data.mkdir()
            _make_store(data / "repo.db", root)
            artifact = pathlib.Path(install.create_repository_backup(root, data))
            with (artifact / "repo.db").open("ab") as handle:
                handle.write(b"tampered")
            report = install.verify_repository_backup(artifact)
            self.assertFalse(report.ok)
            self.assertTrue(any("sha256" in item for item in report.failures))

    def test_load_into_clone_rebinds_and_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            source = base / "source" / "repo"
            source_data = base / "source-data"
            source_data.mkdir()
            _make_store(source_data / "repo.db", source)
            artifact = pathlib.Path(
                install.create_repository_backup(source, source_data)
            )

            target = base / "deploy" / "repo"
            target.mkdir(parents=True)
            target_data = base / "target-data"
            target_data.mkdir()
            result = install.load_repository_backup(
                target, target_data, artifact=artifact
            )

            self.assertEqual(result.rebound_from, str(source.resolve()))
            self.assertEqual(result.pre_load_backup, None)
            readiness = probe_store(target_data, "repo")
            self.assertTrue(readiness.ready, readiness.action)
            self.assertEqual(readiness.bound_root, str(target.resolve()))
            self.assertTrue(pathlib.Path(result.restored_store).is_file())

    def test_load_snapshots_an_existing_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            source = base / "source" / "repo"
            source_data = base / "source-data"
            source_data.mkdir()
            _make_store(source_data / "repo.db", source)
            artifact = pathlib.Path(
                install.create_repository_backup(source, source_data)
            )
            target = base / "deploy" / "repo"
            target_data = base / "target-data"
            target_data.mkdir()
            _make_store(target_data / "repo.db", target)

            result = install.load_repository_backup(
                target, target_data, artifact=artifact
            )

            self.assertIsNotNone(result.pre_load_backup)
            self.assertTrue(
                pathlib.Path(result.pre_load_backup, "manifest.json").is_file()
            )

    def test_load_refuses_a_renamed_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            source = base / "source" / "repo"
            source_data = base / "source-data"
            source_data.mkdir()
            _make_store(source_data / "repo.db", source)
            artifact = pathlib.Path(
                install.create_repository_backup(source, source_data)
            )
            target = base / "deploy" / "other"
            target.mkdir(parents=True)
            with self.assertRaises(SystemExit):
                install.load_repository_backup(
                    target, base / "target-data", artifact=artifact
                )

    def test_load_refuses_a_held_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            source = base / "source" / "repo"
            source_data = base / "source-data"
            source_data.mkdir()
            _make_store(source_data / "repo.db", source)
            artifact = pathlib.Path(
                install.create_repository_backup(source, source_data)
            )
            target = base / "deploy" / "repo"
            target_data = base / "target-data"
            target_data.mkdir()
            _make_store(target_data / "repo.db", target)
            holder = sqlite3.connect(str(target_data / "repo.db"), isolation_level=None)
            try:
                holder.execute("PRAGMA locking_mode = EXCLUSIVE")
                holder.execute("BEGIN EXCLUSIVE")
                with self.assertRaises(SystemExit):
                    install.load_repository_backup(
                        target, target_data, artifact=artifact
                    )
            finally:
                holder.close()

    def test_backup_refuses_a_wrong_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            bound = base / "one" / "repo"
            other = base / "two" / "repo"
            data = base / "data"
            data.mkdir()
            _make_store(data / "repo.db", bound)
            with self.assertRaises(SystemExit):
                install.create_repository_backup(other, data)

    def test_reap_requires_explicit_keep_and_leaves_unmanaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "repo"
            data = base / "data"
            data.mkdir()
            _make_store(data / "repo.db", root)
            with mock.patch.object(
                repository_backup,
                "utc_stamp",
                side_effect=[
                    "20260101T000000",
                    "20260102T000000",
                    "20260103T000000",
                ],
            ):
                for _ in range(3):
                    install.create_repository_backup(root, data)
            directory = root / ".span" / "backups"
            unmanaged = directory / "notes"
            unmanaged.mkdir()
            (unmanaged / "keep.txt").write_text("evidence\n")

            report = install.reap_repository_backups(root, 2)

            self.assertEqual(len(report["kept"]), 2)
            self.assertEqual(len(report["reaped"]), 1)
            self.assertFalse((directory / "20260101T000000").exists())
            self.assertTrue(unmanaged.is_dir())
            with self.assertRaises(SystemExit):
                install.reap_repository_backups(root, None)

            report = install.reap_repository_backups(root, 0, dry_run=True)
            self.assertEqual(len(report["reaped"]), 2)
            self.assertTrue((directory / "20260102T000000").exists())


if __name__ == "__main__":
    unittest.main()
