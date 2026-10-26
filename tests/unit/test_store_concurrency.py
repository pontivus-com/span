"""Shared-store concurrency contract (L7).

The store is the shared durable medium: several processes may read it, writes
are serialized by SQLite, and a second writer waits for the lock. Continuations
are deliberately not shared; that boundary is documented and tested at the
handle level, not here.
"""

import pathlib
import tempfile
import unittest

from span.core import model as m
from span.shell.sqlite_store import (
    SQLITE_BUSY_TIMEOUT_MS,
    SqliteSemanticStore,
)

from tests.support.factories import query_bounds

from functools import partial as _partial

REPO = "shared-svc"


def _subject(locator):
    return m.Subject(m.SubjectId(REPO, m.SubjectKind.COMPONENT, locator), locator, None)


_bounds = _partial(query_bounds, max_depth=2)


class SharedStoreConcurrencyTest(unittest.TestCase):
    def test_two_sessions_share_one_durable_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            first = SqliteSemanticStore(str(path))
            second = SqliteSemanticStore(str(path))
            try:
                first.write_index_batch(
                    m.CanonicalIndexBatch(subjects=(_subject("src/a.py"),))
                )
                second.write_index_batch(
                    m.CanonicalIndexBatch(subjects=(_subject("src/b.py"),))
                )
                for store in (first, second):
                    loaded = store.load_subjects(
                        REPO,
                        (
                            _subject("src/a.py").subject_id,
                            _subject("src/b.py").subject_id,
                        ),
                    )
                    self.assertEqual(
                        sorted(s.subject_id.canonical_locator for s in loaded),
                        ["src/a.py", "src/b.py"],
                    )
            finally:
                first.close()
                second.close()

    def test_writer_lock_wait_is_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "store.db"))
            try:
                (value,) = store._db.execute("PRAGMA busy_timeout").fetchone()
                self.assertEqual(value, SQLITE_BUSY_TIMEOUT_MS)
            finally:
                store.close()

    def test_a_second_session_sees_committed_state_without_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            first = SqliteSemanticStore(str(path))
            second = SqliteSemanticStore(str(path))
            try:
                first.write_index_batch(
                    m.CanonicalIndexBatch(subjects=(_subject("src/a.py"),))
                )
                page = second.load_subjects_by_locator(REPO, "src/a.py", (), _bounds())
                self.assertEqual(len(page.items), 1)
            finally:
                first.close()
                second.close()


if __name__ == "__main__":
    unittest.main()
