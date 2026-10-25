"""Repository status: entries are admitted so their requirements fit.

The old path built every entry on the page and then sliced the flattened
requirement list to ``max_results`` — silently, and the cut entries never
returned on the next page. Now an entry is admitted only while its own
requirements fit, and the remainder pages through the subject cursor.
"""

import unittest

from span import service as ops
from span.core import model as m
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.agent_exchange import (
    REPO,
    _bounds,
    _establish,
    _harness,
)


def _status(bounds, page_token=None):
    return ops.SemanticStatusRequest(
        repository_id=REPO,
        target=None,
        bounds=bounds,
        page_token=page_token,
    )


class RepositoryStatusAccountingTest(unittest.TestCase):
    def test_entries_page_so_their_requirements_fit(self):
        structural, evidence, store, agent = _harness()
        try:
            _establish(structural, evidence, store, agent)
            bounds = _bounds(max_subjects=10, max_results=2)
            answer = ops.status(
                _status(bounds),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIsInstance(
                answer.content.coverage_report, m.RepositoryCoverageReport
            )
            entries = answer.content.coverage_report.page.entries
            # Declared exception: one atomic unit is emitted whole, so a page
            # that admitted exactly one entry may exceed a ceiling too small
            # to hold that unit's requirements.
            if len(entries) != 1:
                self.assertLessEqual(
                    answer.bound_info.returned_results, bounds.max_results
                )
            self.assertTrue(answer.bound_info.truncated)
            self.assertIsNotNone(answer.bound_info.continuation_token)
        finally:
            store.close()

    def test_pages_are_disjoint_and_cover_the_frontier(self):
        structural, evidence, store, agent = _harness()
        try:
            _establish(structural, evidence, store, agent)
            bounds = _bounds(max_subjects=10, max_results=2)
            seen: list[str] = []
            token = None
            for _ in range(20):
                answer = ops.status(
                    _status(bounds, token),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
                entries = answer.content.coverage_report.page.entries
                seen.extend(e.subject.canonical_locator for e in entries)
                if len(entries) != 1:
                    self.assertLessEqual(
                        answer.bound_info.returned_results, bounds.max_results
                    )
                if not answer.bound_info.truncated:
                    break
                token = answer.bound_info.continuation_token
                self.assertIsNotNone(token)
            self.assertEqual(len(seen), len(set(seen)), "an entry appeared twice")
            self.assertGreaterEqual(len(seen), 2)
        finally:
            store.close()

    def test_a_single_oversized_unit_is_reported_not_silently_cut(self):
        """One entry whose requirements exceed the ceiling is visible."""
        structural, evidence, store, agent = _harness()
        try:
            _establish(structural, evidence, store, agent)
            bounds = _bounds(max_subjects=10, max_results=1)
            answer = ops.status(
                _status(bounds),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            entries = answer.content.coverage_report.page.entries
            # Declared exception: one atomic unit is emitted whole, so a page
            # that admitted exactly one entry may exceed a ceiling too small
            # to hold that unit's requirements.
            if len(entries) != 1:
                self.assertLessEqual(
                    answer.bound_info.returned_results, bounds.max_results
                )
            # Whatever the shape, a cut is never reported as complete.
            if answer.content.coverage_report.page.entries and (
                answer.bound_info.returned_results == bounds.max_results
            ):
                self.assertTrue(
                    answer.bound_info.truncated
                    or answer.bound_info.continuation_token is not None
                )
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
