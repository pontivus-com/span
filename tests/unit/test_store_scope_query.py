"""Scoped subject queries: membership, keyset paging, and index use.

The store's SQL predicate must be the same set as
``evidence_scope_allows``. The matrix below is the equivalence proof; it is
deliberately built from the in-memory predicate rather than a second
hand-written expectation, so the two cannot drift apart silently.
"""

import unittest

from span.core import model as m
from span.shell.sqlite_store import SqliteSemanticStore, _scope_range_queries

REPO = "scope-fixture"

LOCATORS = (
    ("a/b", m.SubjectKind.COMPONENT),
    ("a/b/c.py", m.SubjectKind.COMPONENT),
    ("a/b/c.py:Thing", m.SubjectKind.CODE_SYMBOL),
    ("a/b#frag", m.SubjectKind.COMPONENT),
    ("a/b:12", m.SubjectKind.COMPONENT),
    ("a/bc", m.SubjectKind.COMPONENT),
    ("a/bc/d.py", m.SubjectKind.COMPONENT),
    ("z/y", m.SubjectKind.COMPONENT),
    ("top.md", m.SubjectKind.DOCUMENT),
)


def _bounds(max_subjects: int = 100) -> m.QueryBounds:
    return m.QueryBounds(
        max_results=50,
        max_depth=0,
        max_subjects=max_subjects,
        max_evidence_units=24,
        max_evidence_bytes=96_000,
        max_candidate_claims=64,
        max_candidate_relationships=64,
    )


def _ref(locator: str) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{locator}"),
        repository_id=REPO,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=locator,
    )


def _store() -> SqliteSemanticStore:
    store = SqliteSemanticStore(":memory:")
    subjects = tuple(
        m.Subject(
            subject_id=m.SubjectId(
                repository_id=REPO, subject_kind=kind, canonical_locator=locator
            ),
            display_name=locator,
            declared_kind=None,
        )
        for locator, kind in LOCATORS
    )
    store.write_index_batch(m.CanonicalIndexBatch(subjects=subjects))
    return store


SCOPES = (
    m.EvidenceScope(paths=("a/b",), evidence_refs=()),
    m.EvidenceScope(paths=("a/b/",), evidence_refs=()),
    m.EvidenceScope(paths=("a",), evidence_refs=()),
    m.EvidenceScope(paths=("a/b", "z"), evidence_refs=()),
    m.EvidenceScope(paths=(), evidence_refs=(_ref("a/b"),)),
    m.EvidenceScope(paths=("a/b",), evidence_refs=(_ref("z/y"),)),
    m.EvidenceScope(paths=("missing",), evidence_refs=()),
)


class ScopeQueryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _store()

    def tearDown(self) -> None:
        self.store.close()

    def _loaded(self, scope: m.EvidenceScope) -> set[str]:
        page = self.store.load_subjects_in_scope(REPO, scope, _bounds())
        return {item.subject_id.canonical_locator for item in page.items}

    def test_membership_matches_the_canonical_predicate(self):
        for scope in SCOPES:
            expected = {
                locator
                for locator, _kind in LOCATORS
                if m.evidence_scope_allows(locator, scope)
            }
            self.assertEqual(
                self._loaded(scope),
                expected,
                f"scope {scope.paths!r}/{len(scope.evidence_refs)} refs",
            )

    def test_segment_boundary_is_not_a_prefix_guess(self):
        scope = m.EvidenceScope(paths=("a/b",), evidence_refs=())
        loaded = self._loaded(scope)
        self.assertNotIn("a/bc", loaded)
        self.assertNotIn("a/bc/d.py", loaded)
        self.assertIn("a/b", loaded)
        self.assertIn("a/b/c.py", loaded)
        self.assertIn("a/b#frag", loaded)
        self.assertIn("a/b:12", loaded)
        self.assertIn("a/b/c.py:Thing", loaded)

    def test_keyset_pages_are_disjoint_and_complete(self):
        scope = m.EvidenceScope(paths=("a",), evidence_refs=())
        expected = self._loaded(scope)

        seen: list[str] = []
        after: tuple[str, str] | None = None
        for _ in range(10):
            page = self.store.load_subjects_in_scope(
                REPO, scope, _bounds(max_subjects=2), after=after
            )
            if not page.items:
                break
            seen.extend(item.subject_id.canonical_locator for item in page.items)
            last = page.items[-1].subject_id
            after = (last.canonical_locator, last.subject_kind.value)
            if not page.bound_info.truncated:
                break

        self.assertEqual(len(seen), len(set(seen)), "a subject appeared twice")
        self.assertEqual(set(seen), expected)
        self.assertEqual(
            seen,
            sorted(seen, key=lambda locator: locator),
            "pages are not in locator order",
        )

    def test_empty_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.load_subjects_in_scope(
                REPO, m.EvidenceScope(paths=(), evidence_refs=()), _bounds()
            )

    def test_count_matches_loaded_membership(self):
        for scope in SCOPES:
            self.assertEqual(
                self.store.count_subjects_in_scope(REPO, scope),
                len(self._loaded(scope)),
            )

    def test_page_is_fetched_by_index_range_not_a_partition_scan(self):
        scope = m.EvidenceScope(paths=("a/b",), evidence_refs=())
        plans = []
        for where, params in _scope_range_queries(scope):
            sql = (
                "SELECT locator, kind, canonical_json FROM subjects "
                "WHERE repository_id=? AND " + where + " ORDER BY locator, kind LIMIT ?"
            )
            plans.extend(
                self.store._db.execute(
                    "EXPLAIN QUERY PLAN " + sql, (REPO, *params, 2)
                ).fetchall()
            )
        text = " ".join(str(row[-1]) for row in plans)
        self.assertIn("locator>?", text)
        self.assertIn("locator<?", text)
        self.assertNotIn("SCAN subjects", text)


if __name__ == "__main__":
    unittest.main()
