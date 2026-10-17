"""Addendum J J-10 acceptance — structural search scope is a provider
boundary: scope is applied before ranking/pagination, and continuation
identity is bound to the exact scope. Exercised on the in-memory
structural provider (same port contract as Graft)."""

import unittest

from span.core import model as m
from span.ports.structural import StaleContinuationError
from span.shell.structural.memory import (
    InMemoryStructuralSource,
    InMemorySubject,
)

REPO = "scope-repo"


def _bounds(max_results=10):
    return m.QueryBounds(max_results, 5, 8, 24, 96_000, 64, 64)


def _source():
    return InMemoryStructuralSource(
        REPO,
        (),
        (
            InMemorySubject("other/c.py", m.SubjectKind.COMPONENT, "alpha_out"),
            InMemorySubject("pkg/b.py", m.SubjectKind.COMPONENT, "alpha_two"),
            InMemorySubject("pkg/a.py", m.SubjectKind.COMPONENT, "alpha"),
        ),
    )


class StructuralSearchScopeTest(unittest.TestCase):
    def test_scope_filters_before_pagination(self):
        src = _source()
        page = src.search_symbols(
            REPO, "alpha", m.StructuralLocateMatch.CONTAINS, _bounds(),
            scope=m.EvidenceScope(paths=("pkg",)),
        )
        locators = {
            h.candidate.subject.subject_id.canonical_locator
            for h in page.items
        }
        self.assertEqual(locators, {"pkg/a.py", "pkg/b.py"})

    def test_out_of_scope_match_cannot_consume_the_page(self):
        # A scoped page of one must return the in-scope hit, never an
        # out-of-scope global match that sorts ahead of it.
        src = _source()
        page = src.search_symbols(
            REPO, "alpha", m.StructuralLocateMatch.CONTAINS,
            _bounds(max_results=1), scope=m.EvidenceScope(paths=("pkg",)),
        )
        self.assertEqual(len(page.items), 1)
        self.assertEqual(
            page.items[0].candidate.subject.subject_id.canonical_locator,
            "pkg/a.py",
        )

    def test_unscoped_search_returns_the_whole_population(self):
        src = _source()
        page = src.search_symbols(
            REPO, "alpha", m.StructuralLocateMatch.CONTAINS, _bounds()
        )
        locators = {
            h.candidate.subject.subject_id.canonical_locator
            for h in page.items
        }
        self.assertEqual(
            locators, {"other/c.py", "pkg/a.py", "pkg/b.py"}
        )

    def test_scope_binds_continuation_token(self):
        src = _source()
        page = src.search_symbols(
            REPO, "alpha", m.StructuralLocateMatch.CONTAINS,
            _bounds(max_results=1), scope=m.EvidenceScope(paths=("pkg",)),
        )
        token = page.bound_info.continuation_token
        self.assertIsNotNone(token)
        with self.assertRaises(StaleContinuationError):
            src.search_symbols(
                REPO, "alpha", m.StructuralLocateMatch.CONTAINS,
                _bounds(max_results=1), page_token=token,
                scope=m.EvidenceScope(paths=("other",)),
            )

    def test_scope_predicate_is_canonical(self):
        scope = m.EvidenceScope(
            paths=("pkg", "src/x.py"),
            evidence_refs=(),
        )
        self.assertTrue(m.evidence_scope_allows("pkg/a.py", scope))
        self.assertTrue(m.evidence_scope_allows("pkg", scope))
        self.assertTrue(m.evidence_scope_allows("pkg/a.py#Sym", scope))
        self.assertTrue(m.evidence_scope_allows("src/x.py", scope))
        self.assertFalse(m.evidence_scope_allows("other/c.py", scope))


if __name__ == "__main__":
    unittest.main()
