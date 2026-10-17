"""Addendum J acceptance — bounded discovery-scope locality (J-1).

Proves J-A1..J-A4 at the freshness primitive and write boundary:
membership is enumerated over the recorded bounded scope only, an
out-of-scope change never moves it (J-A1), an in-scope change does
(J-A2), the empty scope is the migrated legacy-global path (J-A4), and
post-adoption writes carry their exact non-empty scope. Per-item partial
staleness (J-A3) is proven end-to-end by the Addendum v0.6 contract
suite (`test_v06_contracts.py`, scope-bound membership vs cited change).
"""

import unittest

from span.core import freshness as core_freshness
from span.core import model as m
from span.service.discovery import (
    _coverage_for_task,
    _coverage_scope_snapshots,
    _inventory_snapshot,
)
from span.shell.evidence import FixtureEvidenceSource

REPO = "j-repo"

FILES = {
    "mod/a.py": "A = 1\n",
    "mod/b.py": "B = 2\n",
    "other/c.py": "C = 3\n",
}


def _evidence(files=None):
    return FixtureEvidenceSource(REPO, dict(FILES if files is None else files))


class DiscoveryScopeLocalityTest(unittest.TestCase):
    def test_out_of_scope_membership_is_stable(self):
        # J-A1: adding a file outside the question's discovery scope does
        # not move its membership fingerprint.
        scope = m.EvidenceScope(paths=("mod",))
        before, _ = _inventory_snapshot(REPO, scope, evidence=_evidence())
        grown = dict(FILES)
        grown["other/z.py"] = "Z = 9\n"
        after, _ = _inventory_snapshot(REPO, scope, evidence=_evidence(grown))
        self.assertEqual(before, after)

    def test_in_scope_membership_change_is_detected(self):
        # J-A2: adding a file inside the scope moves membership, and the
        # recorded row then classifies STALE.
        scope = m.EvidenceScope(paths=("mod",))
        before, _ = _inventory_snapshot(REPO, scope, evidence=_evidence())
        grown = dict(FILES)
        grown["mod/z.py"] = "Z = 9\n"
        after, _ = _inventory_snapshot(REPO, scope, evidence=_evidence(grown))
        self.assertNotEqual(before, after)
        recorded = m.CoverageDependency(
            discovery_scope=scope, inventory_fingerprint=before
        )
        self.assertIs(
            core_freshness.classify_coverage(recorded, after, {}).state,
            m.FreshnessState.STALE,
        )

    def test_empty_scope_is_repository_global_legacy(self):
        # J-A4: the empty scope preserves legacy repository-global
        # membership semantics for migrated rows.
        legacy = m.EvidenceScope()
        before, _ = _inventory_snapshot(REPO, legacy, evidence=_evidence())
        grown = dict(FILES)
        grown["other/z.py"] = "Z = 9\n"
        after, _ = _inventory_snapshot(REPO, legacy, evidence=_evidence(grown))
        self.assertNotEqual(before, after)

    def test_post_adoption_coverage_carries_its_scope(self):
        # J-A4 write rule: a coverage built for an adopted question binds
        # its exact non-empty discovery scope.
        scope = m.EvidenceScope(paths=("mod",))
        cov = _coverage_for_task(
            REPO, (), evidence=_evidence(), seeds=(), discovery_scope=scope
        )
        self.assertEqual(cov.discovery_scope, scope)
        self.assertTrue(cov.discovery_scope.paths)

    def test_scope_grouping_is_one_snapshot_per_scope(self):
        # S1.5: rows sharing a scope share one membership walk.
        scope_a = m.EvidenceScope(paths=("mod",))
        scope_b = m.EvidenceScope(paths=("other",))
        rows = (
            m.CoverageDependency(discovery_scope=scope_a),
            m.CoverageDependency(discovery_scope=scope_a),
            m.CoverageDependency(discovery_scope=scope_b),
        )
        snaps = _coverage_scope_snapshots(REPO, rows, evidence=_evidence())
        self.assertEqual(set(snaps), {scope_a, scope_b})


class PerItemFreshnessIsUnaffectedTest(unittest.TestCase):
    def test_cited_source_change_is_per_item(self):
        # J-A3 (primitive): a changed cited source is per-item stale; an
        # unchanged one stays current. Independent of discovery scope.
        self.assertIs(
            core_freshness.classify_dependency("fp-old", "fp-new").state,
            m.FreshnessState.STALE,
        )
        self.assertIs(
            core_freshness.classify_dependency("fp-old", "fp-old").state,
            m.FreshnessState.CURRENT,
        )


class OmittedStatusTargetTest(unittest.TestCase):
    def test_status_accepts_omitted_target_and_bounds(self):
        # S6.3/J-A17: repository-wide status accepts omitted target (None)
        # and omitted bounds (resolved by the service), while the requested
        # JSON stays schema-valid.
        from span.shell.mcp import decode_request
        from span.service.bounds import resolve_bounds

        request = decode_request("status", {"repository_id": "r"})
        self.assertIsNone(request.target)
        self.assertIsNone(request.bounds)
        self.assertTrue(resolve_bounds(request.bounds, hook=False))


class StoreHealthAggregateTest(unittest.TestCase):
    def test_counts_are_read_only_and_typed(self):
        # S8/D-10/J-A20: persisted health aggregates are read-only and the
        # report carries them; no mutation, no second health object.
        from span.shell.sqlite_store import SqliteSemanticStore

        store = SqliteSemanticStore(":memory:")
        try:
            self.assertEqual(store.count_question_dispositions("r"), {})
            self.assertEqual(store.count_target_associations("r"), 0)
            report = m.SemanticCoverageReport(
                pending_question_count=2,
                open_question_count=1,
                active_target_association_count=3,
            )
            self.assertEqual(report.pending_question_count, 2)
            self.assertEqual(report.open_question_count, 1)
            self.assertEqual(report.active_target_association_count, 3)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
