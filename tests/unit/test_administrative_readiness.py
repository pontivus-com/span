"""Administrative readiness is observational and never provisions."""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import io
import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from span.core import model as m
from span.shell import install_verify
from span.shell.install.constants import INSTALL_VERSION
from span.shell.install.receipt import write_receipt
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.readiness import (
    probe_active_functional_pyramid,
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
                report["activation_readiness"]["status"], "unavailable"
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


class ActivationGuidanceTest(unittest.TestCase):
    def _installation(self, data):
        return FunctionalPyramidInstallationStore.create(
            data / "installation" / "functional-pyramid.db",
            retention=DEFAULT_LIFECYCLE_RETENTION,
        )

    def _member(self, data, root):
        root.mkdir()
        (root / "foundation.md").write_text("# Foundation")
        document = {"repository_id": root.name, "document_ref": "foundation.md", "layer": "P0"}
        source = root / "declaration.json"
        source.write_text(json.dumps({
            "version": 3, "source_id": f"{root.name}:repository",
            "kind": "repository", "scope": ".",
            "documents": [{"repository_id": root.name, "document_ref": "foundation.md"}],
            "placements": [{"document": document, "scope": ".", "governing_placements": ["ROOT"]}],
        }))
        binding = m.AuthorityBinding(
            evidence_ref=m.EvidenceRef(
                evidence_id=m.EvidenceId(f"{root.name}-foundation"),
                repository_id=root.name,
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="foundation.md",
            ),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        store = LifecycleStore(data / f"{root.name}.db", retention=DEFAULT_LIFECYCLE_RETENTION)
        try:
            store.register_repository(root.name, str(root.resolve()), authority_bindings=(binding,))
        finally:
            store.close()
        return m.FunctionalPyramidMemberView(
            repository_id=root.name,
            declaration_refs=(m.EvidenceRef(
                evidence_id=m.EvidenceId(f"{root.name}-declaration"),
                repository_id=root.name,
                source_kind=m.EvidenceSourceKind.CONFIGURATION,
                locator="declaration.json",
                revision_or_fingerprint=hashlib.sha256(source.read_bytes()).hexdigest(),
            ),),
        )

    def _activate(self, store, name, members):
        identity = m.FunctionalPyramidId(name)
        version = m.FunctionalPyramidVersion(1)
        with store.transaction() as transaction:
            transaction.write_pyramid_version(
                pyramid_id=identity, version=version, content_digest=m.ContentDigest("digest"),
                committed_at=datetime.datetime.now(datetime.timezone.utc), members=members,
            )
            transaction.set_current_pyramid(pyramid_id=identity, version=version, members=members)

    def test_ordinary_excluded_and_explicit_governed_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root, data = base / "repo", base / "data"
            root.mkdir()
            _ready(data, "repo", root)
            store = self._installation(data)
            try:
                report = probe_functional_pyramid_repository(data, "repo", root)
                self.assertEqual(report["activation_readiness"], {"status": "not_required", "action": None})
                with store.transaction() as transaction:
                    transaction.set_excluded("repo", True)
                report = probe_functional_pyramid_repository(data, "repo", root)
                self.assertEqual(report["participation"]["state"], "EXCLUDED")
                self.assertEqual(report["activation_readiness"], {"status": "not_required", "action": None})
                with store.transaction() as transaction:
                    transaction.set_excluded("repo", False)
                receipt = {"install_version": INSTALL_VERSION, "repos": [str(root)], "host_registration": {},
                           "governed_initialization": {"repo": {"root": str(root)}}}
                # Exercise the projection with explicit retained intent rather than manufacturing provenance.
                from span.shell.readiness import project_activation_guidance
                guidance = project_activation_guidance(
                    "repo", probe_functional_pyramid_repository(data, "repo", root),
                    {"ready": True}, {}, receipt, {},
                )
                self.assertEqual(guidance["status"], "requires_governed_install")
            finally:
                store.close()

    def test_pending_guidance_precedes_unavailable_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root, data = base / "repo", base / "data"
            root.mkdir()
            data.mkdir()
            for pending in ({"backup_manifest_digest": "digest"}, {"accepted_pyramid_id": "p"}, {"restore_intent": {"backup": "backup"}}):
                with self.subTest(pending=pending):
                    write_receipt(data, {"install_version": INSTALL_VERSION, "repos": [str(root)], "host_registration": {},
                                         "pending_governed_initialization": pending})
                    before = (data / "install.json").read_bytes()
                    guidance = probe_functional_pyramid_repository(data, "repo", root)["activation_readiness"]
                    self.assertEqual(guidance["status"], "pending_recovery")
                    if "restore_intent" in pending:
                        self.assertIn("--restore-backup", guidance["action"])
                    self.assertEqual((data / "install.json").read_bytes(), before)
                    self.assertFalse((data / "repo.db").exists())

    def test_active_observation_expands_members_and_separates_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            data = base / "data"
            data.mkdir()
            roots = {name: base / name for name in ("a", "b", "c")}
            members = {name: self._member(data, root) for name, root in roots.items()}
            store = self._installation(data)
            try:
                self._activate(store, "first", (members["a"], members["b"]))
                self._activate(store, "second", (members["c"],))
            finally:
                store.close()
            selected = {"a": roots["a"], "c": roots["c"]}
            graph = probe_active_functional_pyramid(data, selected)
            self.assertEqual(graph["status"], "valid", graph)
            self.assertEqual({frozenset(member["repository_id"] for member in instance["members"]) for instance in graph["instances"]}, {frozenset(("a", "b")), frozenset(("c",))})
            report = probe_functional_pyramid_repository(data, "a", roots["a"])
            self.assertEqual(report["activation_readiness"], {"status": "not_required", "action": None})
            (roots["b"] / "declaration.json").write_text("{invalid")
            report = probe_functional_pyramid_repository(data, "a", roots["a"])
            self.assertEqual(report["activation_readiness"]["status"], "requires_repair")
            self.assertEqual(probe_functional_pyramid_repository(data, "c", roots["c"])["activation_readiness"]["status"], "not_required")
            roots["b"].rename(base / "unavailable")
            report = probe_functional_pyramid_repository(data, "a", roots["a"])
            self.assertEqual(report["activation_readiness"]["status"], "unavailable")

    def test_changing_membership_observation_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            data = base / "data"
            data.mkdir()
            root = base / "a"
            member = self._member(data, root)
            store = self._installation(data)
            self._activate(store, "first", (member,))
            store.close()
            from span.shell import readiness
            actual = readiness._retained_instances(data, ("a",))
            with patch.object(readiness, "_retained_instances", side_effect=[actual, ()]):
                graph = probe_active_functional_pyramid(data, {"a": root})
            self.assertEqual(graph["status"], "unavailable")


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
