"""Scope frontier: merged membership, deterministic order, bound cursor.

The frontier is the union of persisted subjects in the scope and the
evidence-derived subjects the provider knows about, ordered by
``(locator, kind)``. The fingerprint binds a continuation to that exact
membership so a changed scope restarts instead of skipping a page.
"""

import unittest

from span.core import model as m
from span.service.resolution import frontier_fingerprint, resolve_scope_frontier
from tests.support.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
)

from functools import partial as _partial
from tests.support.factories import query_bounds

REPO = "frontier-fixture"

FILES = {
    "src/a.py": "a = 1\n",
    "src/b.py": "b = 2\n",
    "docs/readme.md": "# readme\n",
}

SUBJECTS = (
    InMemorySubject("src/a.py", m.SubjectKind.COMPONENT, "a"),
    InMemorySubject("src/b.py", m.SubjectKind.COMPONENT, "b"),
    InMemorySubject("docs/readme.md", m.SubjectKind.DOCUMENT, "readme"),
    InMemorySubject("cap/store", m.SubjectKind.CAPABILITY, "store-cap"),
)


_bounds = _partial(query_bounds, max_depth=2, max_subjects=10)


class ScopeFrontierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.structural = InMemoryStructuralSource(
            REPO,
            tuple(InMemoryFile(p, c) for p, c in FILES.items()),
            SUBJECTS,
            (InMemoryEdge("src/a.py", m.StructuralEdgeKind.REFERENCES, "src/b.py"),),
        )
        self.evidence = FixtureEvidenceSource(REPO, dict(FILES))
        self.store = SqliteSemanticStore(":memory:")
        # Persist two of the three files: the third must appear as evidence.
        self.store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=tuple(
                    m.Subject(
                        subject_id=m.SubjectId(
                            repository_id=REPO,
                            subject_kind=kind,
                            canonical_locator=locator,
                        ),
                        display_name=locator,
                        declared_kind=None,
                    )
                    for locator, kind in (
                        ("src/a.py", m.SubjectKind.COMPONENT),
                        ("docs/readme.md", m.SubjectKind.DOCUMENT),
                    )
                )
            )
        )

    def tearDown(self) -> None:
        self.store.close()

    def _frontier(self, scope, **kwargs):
        return resolve_scope_frontier(
            REPO,
            scope,
            structural=self.structural,
            evidence=self.evidence,
            store=self.store,
            **kwargs,
        )

    def test_union_is_ordered_by_locator_and_kind(self):
        page, total, _fingerprint = self._frontier(
            m.EvidenceScope(paths=("src",), evidence_refs=()), bounds=_bounds()
        )
        locators = [s.subject_id.canonical_locator for s in page]
        self.assertEqual(locators, sorted(locators))
        self.assertIn("src/a.py", locators)
        self.assertIn("src/b.py", locators)
        self.assertNotIn("docs/readme.md", locators)

    def test_persisted_survives_and_unpersisted_appears(self):
        scope = m.EvidenceScope(paths=("docs", "src"), evidence_refs=())
        page, _total, _fingerprint = self._frontier(scope, bounds=_bounds())
        by_locator = {s.subject_id.canonical_locator: s for s in page}
        # Every file in scope appears; persisted subjects keep their identity.
        self.assertEqual(set(by_locator), {"docs/readme.md", "src/a.py", "src/b.py"})

    def test_offsets_partition_the_frontier(self):
        scope = m.EvidenceScope(paths=("docs", "src"), evidence_refs=())
        full, total, _fingerprint = self._frontier(scope, bounds=_bounds())
        seen = []
        for offset in range(total):
            page, reported_total, _ = self._frontier(
                scope, bounds=_bounds(max_subjects=1), offset=offset
            )
            self.assertEqual(reported_total, total)
            self.assertEqual(len(page), 1)
            seen.append(page[0].subject_id.canonical_locator)
        self.assertEqual(seen, [s.subject_id.canonical_locator for s in full])

    def test_fingerprint_changes_with_membership(self):
        narrow = m.EvidenceScope(paths=("src",), evidence_refs=())
        wide = m.EvidenceScope(paths=("src", "docs"), evidence_refs=())
        _page, _total, narrow_fp = self._frontier(narrow, bounds=_bounds())
        _page, _total, wide_fp = self._frontier(wide, bounds=_bounds())
        self.assertNotEqual(narrow_fp, wide_fp)

    def test_fingerprint_is_stable_for_the_same_membership(self):
        scope = m.EvidenceScope(paths=("src",), evidence_refs=())
        _p, _t, first = self._frontier(scope, bounds=_bounds())
        _p, _t, second = self._frontier(scope, bounds=_bounds())
        self.assertEqual(first, second)
        self.assertEqual(first, frontier_fingerprint(_p))

    def test_empty_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            self._frontier(
                m.EvidenceScope(paths=(), evidence_refs=()), bounds=_bounds()
            )


if __name__ == "__main__":
    unittest.main()
