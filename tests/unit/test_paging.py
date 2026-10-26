"""Paging mechanic tests (plan §5, I-39; Addendum I S4 §5.4 pgq).

Listing cursors (`pg:<offset>`) paginate one truncated store listing.
Answer-level cursors use the single grammar
(`pgq:<digest>:<claims>:<rels>:<questions>`) bound to the selected
question. Old `pg:` service cursors are rejected. Interpretation
continuations are distinct and never appear here.
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
    def test_none_is_zero_zero_zero(self):
        self.assertEqual(paging.parse_service_token(None), (0, 0, 0))

    def test_composite_round_trip(self):
        token = paging.format_service_token(3, 0, 0)
        assert token is not None
        self.assertTrue(token.startswith("pgq:"))
        self.assertEqual(paging.parse_service_token(token), (3, 0, 0))

    def test_question_token_binds_digest(self):
        digest = paging.question_digest("EXPLAIN", "r", "a.py", "slice", "CQ_01")
        token = paging.format_question_token(digest, 1, 2, 3)
        assert token is not None
        got_digest, c, r, q = paging.parse_question_token(token)
        self.assertEqual(got_digest, digest)
        self.assertEqual((c, r, q), (1, 2, 3))

    def test_old_service_cursor_rejected(self):
        for bad in ("pg:1:2:3", "pg:0:0:0"):
            with self.assertRaises(ValueError, msg=bad):
                paging.parse_service_token(bad)

    def test_both_exhausted_is_none(self):
        self.assertIsNone(paging.format_service_token(None, None, 0))
        token = paging.format_service_token(5, 5, 2)
        assert token is not None
        self.assertEqual(paging.parse_service_token(token), (5, 5, 2))

    def test_malformed_fails_closed(self):
        for bad in ("bogus", "pg:", "pgq:", "pgq:bad", "pgq:d:1:2", "trunc:c:3"):
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
            brief=m.TaskBrief(),
            bounds=m.QueryBounds(50, 2, 8, 24, 96_000, 64, 64),
        )
        self.assertEqual(request.operation_intent, m.SemanticIntent.EXPLAIN)
        self.assertIsNone(request.proposed_change)


class ScopeTokenTest(unittest.TestCase):
    """A scope page can stop at a subject and inside that subject's lists.

    The cursor carries both positions, so a page that cut its own items is
    resumable instead of advancing the frontier past them.
    """

    def test_none_starts_at_the_first_subject(self):
        self.assertEqual(paging.parse_scope_token(None), (0, 0, 0, 0))

    def test_round_trip(self):
        token = paging.format_scope_token("ab" * 16, 3, 4, 5, 6)
        self.assertTrue(token.startswith("pgv:"))
        self.assertEqual(paging.parse_scope_token(token), (3, 4, 5, 6))

    def test_version_binds_the_cursor(self):
        token = paging.format_scope_token("ab" * 16, 1)
        self.assertEqual(
            paging.parse_scope_token(token, version="ab" * 16), (1, 0, 0, 0)
        )
        with self.assertRaises(ValueError) as ctx:
            paging.parse_scope_token(token, version="cd" * 16)
        self.assertIn("stale listing continuation", str(ctx.exception))
        self.assertIn("cd" * 16, str(ctx.exception))

    def test_a_structural_cursor_is_not_a_scope_cursor(self):
        # `locate`/`neighbors` use the same prefix with one offset. The two
        # grammars are never interchanged.
        structural = paging.format_versioned_token("ab" * 16, 2)
        with self.assertRaises(ValueError):
            paging.parse_scope_token(structural)
        with self.assertRaises(ValueError):
            paging.parse_versioned_token(
                paging.format_scope_token("ab" * 16, 2), version="ab" * 16
            )

    def test_malformed_fails_closed(self):
        for bad in (
            "bogus",
            "pg:1",
            "pgv:",
            "pgv:v",
            "pgv:v:1:2:3",
            "pgv:v:1:2:3:4:5",
            "pgv:v:-1:0:0:0",
            "pgv:v:1:x:0:0",
        ):
            with self.assertRaises(ValueError, msg=bad):
                paging.parse_scope_token(bad)


if __name__ == "__main__":
    unittest.main()
