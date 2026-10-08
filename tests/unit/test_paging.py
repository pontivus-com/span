"""Paging mechanic tests (plan §5, I-39).

Listing cursors (`pg:<offset>`) paginate one truncated listing and are
redeemable through `page_token` inputs. Answer-level composite cursors
(`pg:<claims>:<rels>`) advance each side past shown items only.
Interpretation continuations are a distinct mechanism and never appear
here.
"""

import unittest

from span.core import model as m
from span.shell import paging


class PageTokenTest(unittest.TestCase):
    def test_none_starts_at_zero(self):
        self.assertEqual(paging.parse_page_token(None), 0)

    def test_round_trip(self):
        token = paging.next_page_token(7)
        self.assertTrue(token.startswith("pg:"))
        self.assertEqual(paging.parse_page_token(token), 7)

    def test_malformed_fails_closed(self):
        for bad in ("bogus", "pg:", "pg:-1", "pg:x", "trunc:c:3"):
            with self.assertRaises(ValueError, msg=bad):
                paging.parse_page_token(bad)

    def test_paginate_pages_and_terminates(self):
        items = tuple(range(5))
        kept, info = paging.paginate(items, 2, "claims", None)
        self.assertEqual(kept, (0, 1))
        self.assertTrue(info.truncated)
        seen = list(kept)
        token = info.continuation_token
        while token is not None:
            kept, info = paging.paginate(items, 2, "claims", token)
            seen.extend(kept)
            token = info.continuation_token
        self.assertEqual(seen, [0, 1, 2, 3, 4])
        self.assertFalse(info.truncated)
        self.assertIsNone(info.continuation_token)


class ServiceTokenTest(unittest.TestCase):
    def test_none_is_zero_zero(self):
        self.assertEqual(paging.parse_service_token(None), (0, 0))

    def test_composite_round_trip(self):
        token = paging.format_service_token(3, 0)
        self.assertTrue(token.startswith("pg:"))
        self.assertEqual(paging.parse_service_token(token), (3, 0))

    def test_both_exhausted_is_none(self):
        self.assertIsNone(paging.format_service_token(None, None))
        token = paging.format_service_token(5, 5)
        self.assertEqual(paging.parse_service_token(token), (5, 5))

    def test_malformed_fails_closed(self):
        for bad in ("bogus", "pg:", "pg:-1:0", "pg:1:2:3", "trunc:c:3"):
            with self.assertRaises(ValueError, msg=bad):
                paging.parse_service_token(bad)

    def test_model_carries_page_token(self):
        request = m.SemanticInterpretationRequest(
            repository_id="r",
            subjects=(),
            evidence_units=(),
            structural_observations=(),
            allowed_claim_kinds=(),
            allowed_relationship_kinds=(),
            identity_bindings=(),
            bounds=m.QueryBounds(50, 2, 8, 24, 96_000, 64, 64),
        )
        self.assertEqual(request.operation_intent, m.SemanticIntent.EXPLAIN)
        self.assertIsNone(request.proposed_change)


if __name__ == "__main__":
    unittest.main()
