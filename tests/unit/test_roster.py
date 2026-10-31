"""Roster proposal tests (addendum D ROSTER-D-01, §9).

Territories are topological facts presented without ranking: members,
proven entries, observed edge kinds, deterministic order. No scores,
no importance, no fixed counts.
"""

import dataclasses
import unittest

from span.core import model as m
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
)
from integrations.hosts.roster import Roster, Territory, propose_territories

from tests.support.factories import query_bounds

from functools import partial as _partial
from tests.support.factories import subject_id

REPO = "roster-svc"


_bounds = query_bounds


FILES = (
    InMemoryFile("src/entry.py", "ENTRY = 1\n"),
    InMemoryFile("src/mid.py", "MID = 2\n"),
    InMemoryFile("src/leaf.py", "LEAF = 3\n"),
    InMemoryFile("src/solo.py", "SOLO = 4\n"),
)

SUBJECTS = (
    InMemorySubject("src/entry.py", m.SubjectKind.COMPONENT, "entry"),
    InMemorySubject("src/mid.py", m.SubjectKind.COMPONENT, "mid"),
    InMemorySubject("src/leaf.py", m.SubjectKind.COMPONENT, "leaf"),
    InMemorySubject("src/solo.py", m.SubjectKind.COMPONENT, "solo"),
)

EDGES = (
    InMemoryEdge("src/entry.py", m.StructuralEdgeKind.DEPENDS_ON, "src/mid.py"),
    InMemoryEdge("src/mid.py", m.StructuralEdgeKind.DEPENDS_ON, "src/leaf.py"),
)


_sid = _partial(subject_id, repository_id=REPO)


def _structural():
    return InMemoryStructuralSource(REPO, FILES, SUBJECTS, EDGES)


class RosterTest(unittest.TestCase):
    def test_chain_and_island_form_two_territories(self):
        roster = propose_territories(
            REPO,
            (_sid("src/mid.py"), _sid("src/solo.py")),
            structural=_structural(),
            bounds=_bounds(),
        )
        self.assertIsInstance(roster, Roster)
        self.assertEqual(len(roster.territories), 2)
        chain, island = roster.territories
        self.assertEqual(
            [s.canonical_locator for s in chain.members],
            ["src/entry.py", "src/leaf.py", "src/mid.py"],
        )
        self.assertEqual(
            [s.canonical_locator for s in chain.entry_points],
            ["src/entry.py"],
        )
        self.assertIn(m.StructuralEdgeKind.DEPENDS_ON, chain.edge_kinds)
        self.assertEqual(
            [s.canonical_locator for s in island.members],
            ["src/solo.py"],
        )
        self.assertEqual(
            [s.canonical_locator for s in island.entry_points],
            ["src/solo.py"],
        )

    def test_overlapping_seeds_merge(self):
        roster = propose_territories(
            REPO,
            (_sid("src/entry.py"), _sid("src/leaf.py")),
            structural=_structural(),
            bounds=_bounds(),
        )
        self.assertEqual(len(roster.territories), 1)
        self.assertEqual(len(roster.territories[0].members), 3)

    def test_empty_seeds_yield_empty_roster(self):
        roster = propose_territories(
            REPO, (), structural=_structural(), bounds=_bounds()
        )
        self.assertEqual(roster.territories, ())

    def test_unknown_seed_skipped(self):
        roster = propose_territories(
            REPO,
            (_sid("src/missing.py"), _sid("src/solo.py")),
            structural=_structural(),
            bounds=_bounds(),
        )
        self.assertEqual(len(roster.territories), 1)

    def test_no_ranking_or_scores(self):
        territory_fields = {f.name for f in dataclasses.fields(Territory)}
        self.assertEqual(territory_fields, {"members", "entry_points", "edge_kinds"})
        self.assertFalse(
            any(
                "rank" in name or "score" in name or "weight" in name
                for name in territory_fields
            )
        )

    def test_deterministic_order(self):
        first = propose_territories(
            REPO,
            (_sid("src/solo.py"), _sid("src/mid.py")),
            structural=_structural(),
            bounds=_bounds(),
        )
        second = propose_territories(
            REPO,
            (_sid("src/mid.py"), _sid("src/solo.py")),
            structural=_structural(),
            bounds=_bounds(),
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
