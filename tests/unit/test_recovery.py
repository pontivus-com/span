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
                "utc_stamp",
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


class GovernedRecoveryTests(unittest.TestCase):
    def _fixture(self, root, *, existing=False, unrelated=False):
        from span.shell.context import (
            create_empty_installation_store,
            create_empty_repository_store,
        )
        from span.shell.install import governed, governed_recovery
        from span.shell.install.constants import INSTALL_VERSION
        from span.shell.install.indexer import indexer_pointer_payload
        from span.shell.install.preflight import validate_authority_files
        from span.shell.install.receipt import write_receipt
        from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
        from span.shell.sqlite_store.lifecycle import LifecycleStore

        data = root / "data"
        data.mkdir()
        repo = root / "repo-a"
        docs = repo / "docs"
        docs.mkdir(parents=True)
        (docs / "foundation.md").write_text("# Foundation\n")
        classification = docs / "classification.json"
        classification.write_text(
            json.dumps(
                {
                    "version": 1,
                    "rows": [
                        {
                            "declaring_repository_id": repo.name,
                            "repository_id": repo.name,
                            "document_ref": "docs/foundation.md",
                            "disposition": "place",
                            "layer": "P0",
                            "scope": ".",
                            "governing_documents": ["ROOT"],
                            "authority_kind": "REPOSITORY_RULE",
                            "authority_status": "ACCEPTED",
                        }
                    ],
                }
            )
        )
        prior = {}
        if existing or unrelated:
            create_empty_installation_store(data / "installation/functional-pyramid.db")
            prior = {
                "install_version": INSTALL_VERSION,
                "repos": [],
                "host_registration": {},
            }
            for selected in ([repo] if existing else []) + (
                [root / "repo-c"] if unrelated else []
            ):
                selected.mkdir(exist_ok=True)
                store_path = data / f"{selected.name}.db"
                create_empty_repository_store(store_path)
                store = LifecycleStore(
                    store_path,
                    retention=DEFAULT_LIFECYCLE_RETENTION,
                    initialize_schema=False,
                )
                try:
                    store.register_repository(selected.name, str(selected))
                finally:
                    store.close()
                prior["repos"].append(str(selected))
            write_receipt(data, prior)
            (data / "structural-indexer.json").write_text('{"prior": true}\n')
        pending, artifacts = governed.prepare(
            data, (repo,), [[repo.name, str(classification)]], [], prior
        )
        requests = validate_authority_files((repo,), {}, governed.bindings_for(pending))
        backup = pathlib.Path(
            governed_recovery.protect_setup(
                data, prior, pending, requests, indexer_pointer_payload("/graft")
            )
        )
        self.assertTrue(install.verify_backup(backup).ok)
        return data, repo, prior, pending, artifacts, requests, backup

    def _publish(self, fixture, boundary):
        from span.shell.context import (
            create_empty_installation_store,
            create_empty_repository_store,
        )
        from span.shell.install import governed, governed_recovery
        from span.shell.install.indexer import write_indexer_pointer
        from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
        from span.shell.sqlite_store.lifecycle import LifecycleStore

        data, repo, prior, pending, artifacts, requests, backup = fixture
        governed.retain_pending(data, prior, pending, str(backup))
        if boundary < 1:
            return
        write_indexer_pointer(data, "/graft")
        if boundary < 2:
            return
        governed.publish(pending, artifacts, bootstrap=False)
        if boundary < 3:
            return
        governed_recovery.prepare_store(
            data,
            pending,
            data / "installation/functional-pyramid.db",
            create_empty_installation_store,
        )
        if boundary < 4:
            return
        governed_recovery.prepare_store(
            data, pending, data / "repo-a.db", create_empty_repository_store
        )
        if boundary < 5:
            return
        store = LifecycleStore(
            data / "repo-a.db",
            retention=DEFAULT_LIFECYCLE_RETENTION,
            initialize_schema=False,
        )
        try:
            store.register_repository(
                repo.name,
                str(repo),
                authority_seeds=requests[0].authority_seeds or (),
                authority_bindings=requests[0].authority_bindings,
            )
        finally:
            store.close()

    def _restore(self, fixture):
        data, _, _, _, _, _, backup = fixture
        from span.shell.install.receipt import administrative_ownership

        with administrative_ownership(data):
            return install.restore_backup(backup, data, confirm=backup.name)

    def _assert_restored(self, fixture):
        from span.shell.install.governed_recovery import _database_digest

        data, repo, _, _, artifacts, _, backup = fixture
        for name in ("install.json", "structural-indexer.json"):
            before = backup / name
            after = data / name
            if before.exists():
                self.assertEqual(after.read_bytes(), before.read_bytes())
            else:
                self.assertFalse(after.exists())
        for name in ("repo-a.db", "installation/functional-pyramid.db"):
            before = backup / name
            after = data / name
            if before.exists():
                self.assertEqual(_database_digest(after), _database_digest(before))
            else:
                self.assertFalse(after.exists())
        for _, locator in artifacts:
            self.assertFalse((repo / locator).exists())

    def test_governed_restore_every_setup_publication_boundary(self):
        for existing in (False, True):
            for boundary in range(6):
                with (
                    self.subTest(existing=existing, boundary=boundary),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    fixture = self._fixture(pathlib.Path(tmp), existing=existing)
                    data, _, _, _, _, _, backup = fixture
                    # Baseline capture itself does not publish pending or mutate data.
                    self.assertEqual(
                        (data / "install.json").exists(),
                        (backup / "install.json").exists(),
                    )
                    self._publish(fixture, boundary)
                    result = self._restore(fixture)
                    self._assert_restored(fixture)
                    self.assertTrue(install.verify_backup(result.pre_restore_backup).ok)

    def test_interrupted_restore_reuses_snapshot_and_excludes_idle_runtime(self):
        from span.shell.install import governed_recovery
        from span.shell.install.receipt import read_receipt
        from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
        from span.shell.sqlite_ownership import StoreHeldError, store_use_ownership
        from span.shell.sqlite_store.lifecycle import LifecycleStore

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(pathlib.Path(tmp))
            data = fixture[0]
            self._publish(fixture, 5)
            holder = LifecycleStore(
                data / "repo-a.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
                initialize_schema=False,
                ownership_root=data,
            )
            try:
                with self.assertRaisesRegex(SystemExit, "ownership"):
                    self._restore(fixture)
            finally:
                holder.close()
            original = governed_recovery._restore_database

            def interrupt(*args):
                with self.assertRaises(StoreHeldError):
                    with store_use_ownership(data / ".." / data.name):
                        self.fail("runtime admitted during exclusive recovery")
                original(*args)
                raise RuntimeError("interrupted after database reconciliation")

            with mock.patch.object(
                governed_recovery, "_restore_database", side_effect=interrupt
            ):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    self._restore(fixture)
            pending = read_receipt(data)["pending_governed_initialization"]
            snapshot = pending["restore_intent"]["snapshot"]
            count = len(list((data / "backups").iterdir()))
            completed = self._restore(fixture)
            self.assertEqual(completed.pre_restore_backup, snapshot)
            self.assertEqual(len(list((data / "backups").iterdir())), count)
            self._assert_restored(fixture)

    def test_restore_resumes_after_each_reconciliation_boundary(self):
        from span.shell.install import governed_recovery
        from span.shell.install.receipt import read_receipt

        for existing in (False, True):
            for target in (
                "pointer",
                "generated",
                "repository",
                "installation",
                "receipt",
            ):
                with (
                    self.subTest(existing=existing, target=target),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    fixture = self._fixture(pathlib.Path(tmp), existing=existing)
                    data, _, _, _, _, _, _ = fixture
                    self._publish(fixture, 5)
                    file_restore = governed_recovery._restore_file
                    database_restore = governed_recovery._restore_database

                    def interrupt_file(path, *args):
                        file_restore(path, *args)
                        selected = (
                            target == "pointer"
                            and path.name == "structural-indexer.json"
                            or target == "generated"
                            and ".span" in path.parts
                            or target == "receipt"
                            and path.name == "install.json"
                        )
                        if selected:
                            raise RuntimeError("interrupted file restore")

                    def interrupt_db(path, *args):
                        database_restore(path, *args)
                        if (
                            target == "repository"
                            and path.name == "repo-a.db"
                            or target == "installation"
                            and path.name == "functional-pyramid.db"
                        ):
                            raise RuntimeError("interrupted database restore")

                    with (
                        mock.patch.object(
                            governed_recovery,
                            "_restore_file",
                            side_effect=interrupt_file,
                        ),
                        mock.patch.object(
                            governed_recovery,
                            "_restore_database",
                            side_effect=interrupt_db,
                        ),
                        self.assertRaisesRegex(RuntimeError, "interrupted"),
                    ):
                        self._restore(fixture)
                    if target != "receipt":
                        pending = read_receipt(data)["pending_governed_initialization"]
                        snapshot = pending["restore_intent"]["snapshot"]
                        self.assertEqual(
                            self._restore(fixture).pre_restore_backup, snapshot
                        )
                    self._assert_restored(fixture)

    def test_recovery_conflicts_before_mutating_independent_or_unowned_state(self):
        from span.shell.context import create_empty_repository_store

        for case in (
            "unexplained",
            "fresh-write",
            "existing-write",
            "shared-write",
            "generated",
        ):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                fixture = self._fixture(
                    pathlib.Path(tmp), existing=case == "existing-write"
                )
                data, repo, _, _, artifacts, _, _ = fixture
                self._publish(fixture, 2 if case == "unexplained" else 5)
                if case == "unexplained":
                    create_empty_repository_store(data / "repo-a.db")
                elif case in ("fresh-write", "existing-write", "shared-write"):
                    path = (
                        data / "installation/functional-pyramid.db"
                        if case == "shared-write"
                        else data / "repo-a.db"
                    )
                    with sqlite3.connect(path) as connection:
                        connection.execute(
                            "INSERT INTO meta VALUES('independent', 'write')"
                        )
                    connection.close()
                else:
                    locator = next(
                        locator
                        for _, locator in artifacts
                        if (repo / locator).is_file()
                    )
                    (repo / locator).write_text("independent modification")
                receipt = (data / "install.json").read_bytes()
                pointer = (data / "structural-indexer.json").read_bytes()
                with self.assertRaisesRegex(SystemExit, "governed recovery conflict"):
                    self._restore(fixture)
                self.assertEqual((data / "install.json").read_bytes(), receipt)
                self.assertEqual(
                    (data / "structural-indexer.json").read_bytes(), pointer
                )

    def test_unrelated_repository_is_not_restored_from_full_backup(self):
        from span.shell.install.governed_recovery import _database_digest

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(pathlib.Path(tmp), existing=True, unrelated=True)
            data = fixture[0]
            self._publish(fixture, 5)
            with sqlite3.connect(data / "repo-c.db") as connection:
                connection.execute("INSERT INTO meta VALUES('independent', 'later')")
            connection.close()
            current = _database_digest(data / "repo-c.db")
            self._restore(fixture)
            self.assertEqual(_database_digest(data / "repo-c.db"), current)
            self._assert_restored(fixture)

    def test_owned_empty_store_can_resume_original_setup(self):
        from span.shell.install import governed, governed_recovery
        from span.shell.install.indexer import indexer_pointer_payload
        from span.shell.install.receipt import read_receipt

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(pathlib.Path(tmp))
            data, repo, _, _, _, requests, backup = fixture
            self._publish(fixture, 4)
            prior = read_receipt(data)
            pending, _ = governed.prepare(
                data,
                (repo,),
                [[repo.name, str(repo / "docs/classification.json")]],
                [],
                prior,
            )
            self.assertEqual(
                governed_recovery.protect_setup(
                    data, prior, pending, requests, indexer_pointer_payload("/graft")
                ),
                str(backup),
            )
            self._restore(fixture)
            self._assert_restored(fixture)


if __name__ == "__main__":
    unittest.main()
