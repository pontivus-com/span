"""Unit tests for the shared SQLite exclusive-ownership rule."""

import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from span.shell.sqlite_ownership import StoreHeldError, exclusive_ownership


class ExclusiveOwnershipTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = pathlib.Path(self._tmp.name) / "store.db"
        connection = sqlite3.connect(str(self.path))
        connection.execute("CREATE TABLE t(x TEXT)")
        connection.commit()
        connection.close()

    def test_holds_the_store_for_the_context(self):
        with exclusive_ownership(self.path):
            other = sqlite3.connect(str(self.path), timeout=0.1)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    other.execute("BEGIN EXCLUSIVE")
            finally:
                other.close()

    def test_releases_after_the_context(self):
        with exclusive_ownership(self.path):
            pass
        other = sqlite3.connect(str(self.path), timeout=0.1, isolation_level=None)
        try:
            other.execute("BEGIN EXCLUSIVE")
            other.execute("COMMIT")
        finally:
            other.close()

    def test_refuses_a_held_store(self):
        holder = sqlite3.connect(str(self.path), isolation_level=None)
        try:
            holder.execute("BEGIN EXCLUSIVE")
            with self.assertRaises(StoreHeldError):
                with exclusive_ownership(self.path, timeout_seconds=0.1):
                    pass
        finally:
            holder.close()


if __name__ == "__main__":
    unittest.main()
