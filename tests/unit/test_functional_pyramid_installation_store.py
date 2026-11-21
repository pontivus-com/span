"""Installation-scoped Functional Pyramid persistence tests (T07)."""

import datetime
import json
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.shell.install.recovery import create_backup, restore_backup, verify_backup
from span.shell.install.repository_backup import create_repository_backup
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.readiness import probe_functional_pyramid_installation_store
from span.shell.sqlite_store.functional_pyramid import (
    INSTALLATION_SCHEMA_VERSION,
    FunctionalPyramidInstallationSchemaError,
    FunctionalPyramidInstallationStore,
    ensure_functional_pyramid_installation_store,
    functional_pyramid_installation_path,
)
from span.shell.sqlite_store.lifecycle import LifecycleStore


NOW = datetime.datetime(2026, 11, 21, 12, 0, tzinfo=datetime.timezone.utc)


class FunctionalPyramidInstallationStoreTest(unittest.TestCase):
    def test_runtime_open_does_not_create_missing_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = functional_pyramid_installation_path(tmp)
            with self.assertRaises(FunctionalPyramidInstallationSchemaError):
                FunctionalPyramidInstallationStore(
                    path,
                    retention=DEFAULT_LIFECYCLE_RETENTION,
                )
            self.assertFalse(path.exists())

    def test_explicit_setup_creates_only_installation_owned_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ensure_functional_pyramid_installation_store(
                tmp,
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            self.addCleanup(store.close)
            self.assertEqual(store.schema_version(), INSTALLATION_SCHEMA_VERSION)
            tables = {
                row["name"]
                for row in store._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                    " AND name NOT LIKE 'sqlite_%'"
                )
            }
            self.assertEqual(
                tables,
                {
                    "meta",
                    "functional_pyramid_versions",
                    "functional_pyramids",
                    "functional_pyramid_active_members",
                    "functional_pyramid_exclusions",
                    "functional_pyramid_receipts",
                },
            )
            readiness = probe_functional_pyramid_installation_store(tmp)
            self.assertTrue(readiness["ready"])
            self.assertEqual(readiness["schema_version"], 1)

    def test_installation_receipt_retention_is_not_repository_owned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(tmp),
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            self.addCleanup(store.close)
            expired = NOW - datetime.timedelta(seconds=1)
            store._connection.execute(
                "INSERT INTO functional_pyramid_receipts("
                "request_id, content_digest, committed_at, replay_expires_at,"
                " action, pyramid_id, version, members_json,"
                " participation_effects_json, dependent_effect_refs_json"
                ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "req-1",
                    "digest",
                    NOW.isoformat(),
                    expired.isoformat(),
                    "exclude",
                    None,
                    None,
                    "[]",
                    "[]",
                    "[]",
                ),
            )
            store._connection.commit()
            self.assertEqual(store.reap_expired(NOW), 1)
            self.assertEqual(
                store._connection.execute(
                    "SELECT COUNT(*) FROM functional_pyramid_receipts"
                ).fetchone()[0],
                0,
            )

    def test_full_backup_and_restore_carry_installation_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            source = base / "source"
            source.mkdir()
            installation = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(source),
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            installation.close()

            backup_root = base / "backups"
            artifact = pathlib.Path(
                create_backup(source, backup_root=backup_root, label="fp-state")
            )
            self.assertTrue(
                (artifact / "installation" / "functional-pyramid.db").is_file()
            )
            manifest = json.loads((artifact / "manifest.json").read_text())
            paths = {item["path"] for item in manifest["artifacts"]}
            self.assertIn("installation/functional-pyramid.db", paths)
            report = verify_backup(artifact)
            self.assertTrue(report.ok, report.failures)

            target = base / "target"
            target.mkdir()
            restored = restore_backup(
                artifact,
                target,
                confirm=artifact.name,
                backup_root=base / "pre-restore",
            )
            self.assertIn(
                str(target / "installation" / "functional-pyramid.db"),
                restored.restored,
            )
            reopened = FunctionalPyramidInstallationStore(
                functional_pyramid_installation_path(target),
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            reopened.close()

    def test_repository_portable_backup_excludes_installation_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "repo"
            root.mkdir()
            data = base / "data"
            data.mkdir()

            repository = LifecycleStore(
                data / "repo.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            repository.register_repository("repo", str(root))
            repository.close()

            installation = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(data),
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            installation.close()

            artifact = pathlib.Path(create_repository_backup(root, data))
            self.assertTrue((artifact / "repo.db").is_file())
            self.assertFalse((artifact / "installation").exists())
            manifest = json.loads((artifact / "manifest.json").read_text())
            self.assertEqual(manifest["artifact"]["path"], "repo.db")


if __name__ == "__main__":
    unittest.main()
