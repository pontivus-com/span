"""Administrative readiness is observational and never provisions."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import pathlib
import sqlite3
import tempfile
import unittest

from span.core import model as m
from span.shell import install_verify
from span.shell.install.constants import INSTALL_VERSION
from span.shell.install.receipt import write_receipt
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.readiness import (
    probe_functional_pyramid_repository,
    probe_governed_provenance,
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
                report["activation_readiness"]["status"], "requires_governed_install"
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
                        "version": 3,
                        "source_id": "repo:repository",
                        "kind": "repository",
                        "scope": ".",
                        "documents": [
                            {
                                "repository_id": "repo",
                                "document_ref": "docs/foundation.md",
                            }
                        ],
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
                        "version": 3,
                        "source_id": "repo:repository",
                        "kind": "repository",
                        "scope": ".",
                        "documents": [],
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


class FunctionalPyramidProvenanceTest(unittest.TestCase):
    @staticmethod
    def _binding(locator: str) -> m.AuthorityBinding:
        return m.AuthorityBinding(
            evidence_ref=m.EvidenceRef(
                evidence_id=m.EvidenceId(f"authority-{locator}"),
                repository_id="repo",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator=locator,
                revision_or_fingerprint="rev",
            ),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )

    def _fixture(self, tmp: str):
        root = pathlib.Path(tmp) / "repo"
        (root / "docs").mkdir(parents=True)
        (root / ".span").mkdir()
        declaration = root / "docs" / "decl.json"
        declaration.write_text(
            json.dumps(
                {
                    "version": 3,
                    "source_id": "repo:repository",
                    "kind": "repository",
                    "scope": ".",
                    "documents": [],
                    "placements": [],
                }
            ),
            encoding="utf-8",
        )
        bootstrap = root / ".span" / "functional-pyramid.json"
        bootstrap.write_text(
            json.dumps(
                {
                    "version": 2,
                    "declaration_sources": [
                        {"locator": "docs/decl.json", "ranges": []}
                    ],
                }
            ),
            encoding="utf-8",
        )
        bindings = root / "docs" / "authority-bindings.json"
        binding = self._binding("docs/goals.md")
        bindings.write_text(json.dumps([m.to_canonical(binding)]), encoding="utf-8")
        data = pathlib.Path(tmp) / "data"
        data.mkdir()
        store = LifecycleStore(data / "repo.db", retention=DEFAULT_LIFECYCLE_RETENTION)
        try:
            store.register_repository(
                "repo",
                str(root.resolve()),
                authority_bindings=(binding,),
            )
        finally:
            store.close()
        inputs = [
            {
                "role": "bootstrap",
                "locator": ".span/functional-pyramid.json",
                "digest": hashlib.sha256(bootstrap.read_bytes()).hexdigest(),
            },
            {
                "role": "declaration_source",
                "locator": "docs/decl.json",
                "digest": hashlib.sha256(declaration.read_bytes()).hexdigest(),
            },
            {
                "role": "authority_binding",
                "locator": "docs/authority-bindings.json",
                "digest": hashlib.sha256(bindings.read_bytes()).hexdigest(),
            },
        ]
        write_receipt(
            data,
            {
                "install_version": INSTALL_VERSION,
                "repos": [str(root)],
                "host_registration": {},
                "preflight_facts": {
                    str(root): {
                        "repository_id": "repo",
                        "governed_inputs": inputs,
                    }
                },
            },
        )
        return root, data, declaration, binding

    def test_matching_governed_inputs_report_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data, _, _ = self._fixture(tmp)
            result = probe_governed_provenance(data, "repo", root)
            self.assertEqual(result["state"], "PROVENANCE_MATCH")
            self.assertEqual(result["mismatches"], [])

    def test_changed_declaration_reports_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data, declaration, _ = self._fixture(tmp)
            declaration.write_text(
                declaration.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )
            result = probe_governed_provenance(data, "repo", root)
            self.assertEqual(result["state"], "PROVENANCE_MISMATCH")
            self.assertIn(
                "digest_mismatch",
                {item["reason"] for item in result["mismatches"]},
            )

    def test_installed_binding_difference_reports_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data, _, _ = self._fixture(tmp)
            store = LifecycleStore(
                data / "repo.db", retention=DEFAULT_LIFECYCLE_RETENTION
            )
            try:
                store.register_repository(
                    "repo",
                    str(root.resolve()),
                    authority_bindings=(self._binding("docs/other.md"),),
                )
            finally:
                store.close()
            result = probe_governed_provenance(data, "repo", root)
            self.assertEqual(result["state"], "PROVENANCE_MISMATCH")
            self.assertIn(
                "installed_binding_set_differs",
                {item["reason"] for item in result["mismatches"]},
            )

    def test_absent_recorded_inputs_report_not_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "repo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            write_receipt(
                data,
                {
                    "install_version": INSTALL_VERSION,
                    "repos": [str(root)],
                    "host_registration": {},
                },
            )
            result = probe_governed_provenance(data, "repo", root)
            self.assertEqual(result["state"], "PROVENANCE_NOT_RECORDED")


if __name__ == "__main__":
    unittest.main()
