"""Administrative readiness is observational and never provisions."""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sqlite3
import tempfile
import unittest

from span.shell import install_verify
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.readiness import (
    probe_functional_pyramid_repository,
    probe_store,
    probe_structural,
)
from span.shell.sqlite_store.functional_pyramid import (
    FunctionalPyramidInstallationStore,
)
from span.shell.sqlite_store.lifecycle import LifecycleStore


def _ready(data: pathlib.Path, repository_id: str, root: pathlib.Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    store = LifecycleStore(
        data / f"{repository_id}.db", retention=DEFAULT_LIFECYCLE_RETENTION
    )
    try:
        store.register_repository(repository_id, str(root.resolve()))
    finally:
        store.close()


class StoreProbeTest(unittest.TestCase):
    def test_missing_store_reports_setup_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            readiness = probe_store(data, "repo")
            self.assertFalse(readiness.ready)
            self.assertFalse(readiness.exists)
            self.assertIn("installer", readiness.action)
            self.assertEqual(list(data.iterdir()), [])

    def test_old_schema_reports_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            connection = sqlite3.connect(data / "repo.db")
            try:
                connection.executescript(
                    "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);"
                    "INSERT INTO meta VALUES('schema_version','9');"
                )
                connection.commit()
            finally:
                connection.close()
            readiness = probe_store(data, "repo")
            self.assertFalse(readiness.ready)
            self.assertEqual(readiness.schema_version, 9)
            self.assertIn("--transition-store", readiness.action)

    def test_bound_current_store_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "repo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            _ready(data, "repo", root)
            readiness = probe_store(data, "repo")
            self.assertTrue(readiness.ready)
            self.assertEqual(readiness.expected_version, 15)
            self.assertEqual(readiness.bound_root, str(root.resolve()))

    def test_provider_probe_reports_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            self.assertEqual(probe_structural(data, "repo")["status"], "absent")
            (data / "structural" / "repo").mkdir(parents=True)
            self.assertEqual(probe_structural(data, "repo")["status"], "present")

    def test_functional_pyramid_probe_treats_bootstrap_as_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            root = pathlib.Path(tmp) / "repo"
            root.mkdir()

            report = probe_functional_pyramid_repository(data, "repo", root)

            self.assertEqual(report["declarations"]["status"], "absent")
            self.assertTrue(report["declarations"]["valid"])
            self.assertEqual(report["participation"]["state"], "UNAVAILABLE")
            self.assertEqual(
                report["activation_readiness"]["status"], "requires_candidate"
            )
            self.assertEqual(list(data.iterdir()), [])
            self.assertFalse(any(root.rglob("*")))

    def test_functional_pyramid_probe_validates_bootstrap_and_declarations(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            root = pathlib.Path(tmp) / "repo"
            (root / ".span").mkdir(parents=True)
            (root / "docs").mkdir()
            (root / ".span" / "functional-pyramid.json").write_text(
                json.dumps(
                    {
                        "version": 2,
                        "declaration_sources": [
                            {
                                "locator": "docs/functional-pyramid.json",
                                "ranges": [],
                            }
                        ],
                    }
                )
            )
            (root / "docs" / "functional-pyramid.json").write_text(
                json.dumps(
                    {
                        "version": 2,
                        "placements": [
                            {
                                "document": {
                                    "repository_id": "repo",
                                    "document_ref": "docs/foundation.md",
                                    "layer": "P0",
                                },
                                "scope": ".",
                                "governing_placements": ["ROOT"],
                            }
                        ],
                    }
                )
            )
            (root / "docs" / "foundation.md").write_text("# Foundation\n")

            report = probe_functional_pyramid_repository(data, "repo", root)

            self.assertEqual(report["declarations"]["status"], "ready")
            self.assertTrue(report["declarations"]["valid"])
            self.assertEqual(report["declarations"]["sources"][0]["status"], "valid")

            (root / "docs" / "functional-pyramid.json").write_text(
                json.dumps(
                    {
                        "version": 2,
                        "placements": [],
                        "unexpected": True,
                    }
                )
            )
            invalid = probe_functional_pyramid_repository(data, "repo", root)
            self.assertEqual(invalid["declarations"]["status"], "invalid")
            self.assertFalse(invalid["declarations"]["valid"])

    def test_functional_pyramid_probe_reads_participation_without_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            root = pathlib.Path(tmp) / "repo"
            root.mkdir()
            store = FunctionalPyramidInstallationStore.create(
                data / "installation" / "functional-pyramid.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            try:
                with store.transaction() as transaction:
                    transaction.set_excluded("repo", True)
            finally:
                store.close()

            before = (data / "installation" / "functional-pyramid.db").read_bytes()
            report = probe_functional_pyramid_repository(data, "repo", root)
            after = (data / "installation" / "functional-pyramid.db").read_bytes()

            self.assertEqual(report["participation"]["state"], "EXCLUDED")
            self.assertEqual(before, after)


class InstallVerifyTest(unittest.TestCase):
    def test_verify_only_is_observational(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                install_verify.main(["--data-dir", str(data), "--repo", str(repo)])
            payload = json.loads(stream.getvalue())
            self.assertTrue(payload["restart_required"])
            store = payload["repos"][0]["store"]
            self.assertFalse(store["ready"])
            self.assertIn("installer", store["action"])
            self.assertEqual(list(data.iterdir()), [])
            self.assertFalse(any(repo.rglob("*")))
            self.assertEqual(
                payload["repos"][0]["functional_pyramid"]["declarations"]["status"],
                "absent",
            )
            self.assertEqual(
                payload["repos"][0]["functional_pyramid"]["participation"]["state"],
                "UNAVAILABLE",
            )

    def test_verify_only_reports_a_ready_bound_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "repo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            _ready(data, "repo", root)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                install_verify.main(["--data-dir", str(data), "--repo", str(root)])
            payload = json.loads(stream.getvalue())
            self.assertTrue(payload["repos"][0]["store"]["ready"])
            self.assertEqual(payload["repos"][0]["store"]["schema_version"], 15)


if __name__ == "__main__":
    unittest.main()
