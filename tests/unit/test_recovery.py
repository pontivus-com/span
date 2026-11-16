"""Unit tests for operator-facing backup, verify, restore and reaping.

These exercise the installer package's recovery module directly. The module
is stdlib-only at import time; schema compatibility is resolved lazily from
the store contract.
"""

import hashlib
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from span.shell import install
from span.shell.install import recovery
from span.shell.install.manifest import MANIFEST_FORMAT


def _make_store(path, schema_version=11, rows=("v1",), table="t"):
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        connection.execute(
            "INSERT INTO meta VALUES('schema_version', ?)", (str(schema_version),)
        )
        connection.execute(
            "CREATE TABLE conclusions(conclusion_id TEXT, revision INTEGER)"
        )
        for index, row in enumerate(rows, start=1):
            connection.execute("INSERT INTO conclusions VALUES(?, ?)", (row, index))
        connection.execute(f"CREATE TABLE {table}(x TEXT)")
        connection.execute(f"INSERT INTO {table} VALUES('payload')")
        connection.commit()
    finally:
        connection.close()


def _read_payload(path, table="t"):
    connection = sqlite3.connect(str(path))
    try:
        return connection.execute(f"SELECT x FROM {table}").fetchall()
    finally:
        connection.close()


def _set_payload(path, value, table="t"):
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(f"UPDATE {table} SET x=?", (value,))
        connection.commit()
    finally:
        connection.close()


class RecoveryTests(unittest.TestCase):
    def test_create_backup_covers_state_and_records_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db", rows=("a", "b"))
            (data / "install.json").write_text('{"install_version": 2}\n')
            (data / "structural-indexer.json").write_text('{"version": "1"}\n')
            (data / "structural" / "repo").mkdir(parents=True)
            (data / "structural" / "repo" / "wiring.json").write_text("{}\n")
            (data / "transitions" / "repo").mkdir(parents=True)
            (data / "transitions" / "repo" / "old.db").write_text("old\n")

            destination = pathlib.Path(install.create_backup(data))

            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["format"], MANIFEST_FORMAT)
            from span import __version__ as span_version

            self.assertEqual(manifest["installer"]["span_version"], span_version)
            self.assertEqual(manifest["label"], "operator")
            names = {item["path"] for item in manifest["artifacts"]}
            self.assertEqual(
                names, {"repo.db", "install.json", "structural-indexer.json"}
            )
            database = next(
                item for item in manifest["artifacts"] if item["path"] == "repo.db"
            )
            self.assertEqual(database["database"]["schema_version"], 11)
            self.assertEqual(database["database"]["integrity"], "ok")
            self.assertEqual(database["database"]["max_conclusion_revision"], 2)
            self.assertEqual(
                {item["path"] for item in manifest["excluded"]},
                {"structural", "transitions"},
            )
            self.assertFalse((destination / "structural").exists())
            self.assertFalse((destination / "transitions").exists())
            digest_line = (destination / "manifest.sha256").read_text().split()
            self.assertEqual(
                digest_line[0],
                hashlib.sha256(
                    (destination / "manifest.json").read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(digest_line[1], "manifest.json")
            self.assertTrue(install.verify_backup(destination).ok)

    def test_install_backup_delegates_to_verified_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            destination = install.backup_data_dir(data)
            self.assertIsNotNone(destination)
            self.assertTrue((pathlib.Path(destination) / "manifest.json").is_file())
            self.assertTrue(install.verify_backup(destination).ok)
            self.assertIsNone(install.backup_data_dir(data / "absent"))

    def test_verify_backup_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            destination = pathlib.Path(install.create_backup(data))

            with (destination / "repo.db").open("ab") as handle:
                handle.write(b"tampered")
            report = install.verify_backup(destination)
            self.assertFalse(report.ok)
            self.assertTrue(any("sha256" in failure for failure in report.failures))

            (destination / "manifest.json").write_text("{}\n")
            with self.assertRaises(SystemExit):
                install.verify_backup(destination)

    def test_verify_rejects_unsupported_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db", schema_version=6)
            destination = install.create_backup(data)
            report = install.verify_backup(destination)
            self.assertFalse(report.ok)
            self.assertTrue(any("schema 6" in failure for failure in report.failures))

    def test_restore_round_trip_into_isolated_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            live = root / "live"
            live.mkdir()
            _make_store(live / "repo.db")
            (live / "install.json").write_text('{"install.json": "before"}\n')
            backup = pathlib.Path(install.create_backup(live))
            _set_payload(live / "repo.db", "after")

            isolated = root / "isolated"
            report = install.restore_backup(backup, isolated, confirm=backup.name)

            self.assertEqual(_read_payload(isolated / "repo.db"), [("payload",)])
            self.assertEqual(_read_payload(live / "repo.db"), [("after",)])
            self.assertEqual(
                (isolated / "install.json").read_text(),
                '{"install.json": "before"}\n',
            )
            self.assertIsNone(report.pre_restore_backup)
            self.assertTrue(pathlib.Path(report.restored[0]).is_file())

    def test_restore_replaces_live_store_and_clears_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            backup = pathlib.Path(install.create_backup(data))
            _set_payload(data / "repo.db", "after")
            stale_wal = pathlib.Path(str(data / "repo.db") + "-wal")
            stale_wal.write_text("stale")
            stale_shm = pathlib.Path(str(data / "repo.db") + "-shm")
            stale_shm.write_text("stale")

            report = install.restore_backup(backup, data, confirm=backup.name)

            self.assertEqual(_read_payload(data / "repo.db"), [("payload",)])
            self.assertFalse(stale_wal.exists())
            self.assertFalse(stale_shm.exists())
            snapshot = pathlib.Path(report.pre_restore_backup)
            self.assertTrue((snapshot / "manifest.json").is_file())
            self.assertEqual(_read_payload(snapshot / "repo.db"), [("after",)])

    def test_restore_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            backup = pathlib.Path(install.create_backup(data))
            with self.assertRaises(SystemExit):
                install.restore_backup(backup, data, confirm=None)
            with self.assertRaises(SystemExit):
                install.restore_backup(backup, data, confirm="other-name")

    def test_restore_refuses_while_store_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            backup = pathlib.Path(install.create_backup(data))
            holder = sqlite3.connect(str(data / "repo.db"), isolation_level=None)
            try:
                holder.execute("PRAGMA locking_mode = EXCLUSIVE")
                holder.execute("BEGIN EXCLUSIVE")
                with self.assertRaises(SystemExit):
                    install.restore_backup(backup, data, confirm=backup.name)
            finally:
                holder.close()

    def test_reap_requires_explicit_keep_and_leaves_unmanaged_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            with mock.patch.object(
                recovery,
                "_utc_stamp",
                side_effect=[
                    "20260101T000000",
                    "20260102T000000",
                    "20260103T000000",
                ],
            ):
                for _ in range(3):
                    install.create_backup(data)
            root = data / "backups"
            unmanaged = root / "upgrade-0.8.1-20261027T0630"
            unmanaged.mkdir()
            (unmanaged / "keep.txt").write_text("evidence\n")

            report = install.reap_backups(root, 2)

            self.assertEqual(len(report["kept"]), 2)
            self.assertEqual(len(report["reaped"]), 1)
            self.assertFalse((root / "20260101T000000").exists())
            self.assertTrue((root / "20260103T000000").exists())
            self.assertTrue(unmanaged.is_dir())
            with self.assertRaises(SystemExit):
                install.reap_backups(root, None)

            report = install.reap_backups(root, 0, dry_run=True)
            self.assertEqual(len(report["reaped"]), 2)
            self.assertTrue((root / "20260102T000000").exists())
            self.assertTrue((root / "20260103T000000").exists())

    def test_backup_root_places_artifact_outside_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            data = root / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            destination = pathlib.Path(
                install.create_backup(data, backup_root=root / "archive")
            )
            self.assertEqual(destination.parent, root / "archive")
            self.assertFalse((data / "backups").exists())

    def test_restore_refuses_artifact_with_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _make_store(data / "repo.db")
            backup = pathlib.Path(install.create_backup(data))
            (backup / "repo.db").unlink()
            with self.assertRaises(SystemExit):
                install.restore_backup(backup, data, confirm=backup.name)
            self.assertTrue((data / "repo.db").is_file())


if __name__ == "__main__":
    unittest.main()
