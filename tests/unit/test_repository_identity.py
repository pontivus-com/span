"""Repository identity: provenance, conflict rejection, nested reporting.

Identity is still the directory basename. What changes is that a store now
records which canonical root it belongs to, so two roots with the same name can
never silently share one store, and a moved root has a named way forward.
"""

import tempfile
import unittest
from pathlib import Path

from span.core import model as m
from span.service import initialize_repository
from span.service.requests import SemanticInitializeRepositoryRequest
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp import McpAdapter
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
)

FILES = {"README.md": "# fixture\n"}


def _structural(repo: str):
    return InMemoryStructuralSource(
        repo, (InMemoryFile("README.md", FILES["README.md"]),), (), ()
    )


class RegistrationConflictTest(unittest.TestCase):
    def test_two_roots_with_one_basename_conflict(self):
        adapter = McpAdapter()
        with (
            tempfile.TemporaryDirectory() as left,
            tempfile.TemporaryDirectory() as right,
        ):
            first = Path(left) / "src"
            second = Path(right) / "src"
            first.mkdir()
            second.mkdir()
            adapter.register_repository_locator("src", str(first))
            # Same canonical root is idempotent.
            adapter.register_repository_locator("src", str(first))
            with self.assertRaises(m.RepositoryIdentityConflict) as caught:
                adapter.register_repository_locator("src", str(second))
            self.assertEqual(caught.exception.existing_root, str(first.resolve()))
            self.assertEqual(caught.exception.incoming_root, str(second.resolve()))

    def test_conflict_names_both_dispositions(self):
        with (
            tempfile.TemporaryDirectory() as left,
            tempfile.TemporaryDirectory() as right,
        ):
            error = m.RepositoryIdentityConflict(
                "src", str(Path(left).resolve()), str(Path(right).resolve())
            )
            message = str(error)
            self.assertIn("Purge", message)
            self.assertIn("re-initialize", message)


class ProvenanceTest(unittest.TestCase):
    def test_initialize_records_and_rejects_a_foreign_root(self):
        store = SqliteSemanticStore(":memory:")
        try:
            result = initialize_repository(
                SemanticInitializeRepositoryRequest(
                    repository_locator="fixture", authority_seeds=()
                ),
                repository_id="repo",
                structural=_structural("repo"),
                evidence=FixtureEvidenceSource("repo", dict(FILES)),
                store=store,
                canonical_root="/roots/a/fixture",
            )
            self.assertEqual(result.canonical_root, "/roots/a/fixture")
            self.assertEqual(store.repository_root("repo"), "/roots/a/fixture")

            with self.assertRaises(m.RepositoryIdentityConflict):
                store.record_repository_root("repo", "/roots/b/fixture")
        finally:
            store.close()

    def test_same_root_is_idempotent(self):
        store = SqliteSemanticStore(":memory:")
        try:
            store.record_repository_root("repo", "/roots/a/fixture")
            store.record_repository_root("repo", "/roots/a/fixture")
            self.assertEqual(store.repository_root("repo"), "/roots/a/fixture")
        finally:
            store.close()

    def test_uninitialized_store_has_no_provenance(self):
        store = SqliteSemanticStore(":memory:")
        try:
            self.assertIsNone(store.repository_root("repo"))
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
