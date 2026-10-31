"""Repository identity: one root binding, conflict rejection, idempotence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from span.core import model as m
from span.shell.context import provision_repository
from span.shell.mcp import McpAdapter
from span.shell.sqlite_store.lifecycle import LifecycleStore
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION


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


class BindingTest(unittest.TestCase):
    def _store(self, tmp: str) -> LifecycleStore:
        return LifecycleStore(
            Path(tmp) / "repo.db", retention=DEFAULT_LIFECYCLE_RETENTION
        )

    def test_initialize_binds_and_rejects_a_foreign_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            try:
                store.register_repository("repo", "/roots/a/fixture")
                self.assertEqual(store.require_repository("repo"), "/roots/a/fixture")
                with self.assertRaises(ValueError):
                    store.register_repository("repo", "/roots/b/fixture")
            finally:
                store.close()

    def test_same_root_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            try:
                store.register_repository("repo", "/roots/a/fixture")
                store.register_repository("repo", "/roots/a/fixture")
                self.assertEqual(store.require_repository("repo"), "/roots/a/fixture")
            finally:
                store.close()

    def test_unregistered_store_has_no_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            try:
                with self.assertRaises(ValueError):
                    store.require_repository("repo")
            finally:
                store.close()

    def test_provision_binds_the_canonical_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "README.md").write_text("# fixture\n", encoding="utf-8")
            data = Path(tmp) / "data"
            context, result = provision_repository(
                data,
                m.InitializeRepositoryRequest(
                    repository_locator=str(root), authority_seeds=()
                ),
            )
            try:
                self.assertEqual(result.canonical_root, str(root.resolve()))
                self.assertEqual(result.repository_id, "repo")
                self.assertEqual(result.schema_version, 10)
                self.assertTrue(result.store_ready)
                self.assertEqual(list(data.glob("*.db")), [data / "repo.db"])
            finally:
                context.store.close()


if __name__ == "__main__":
    unittest.main()
