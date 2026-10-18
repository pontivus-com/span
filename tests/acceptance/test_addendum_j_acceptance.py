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
from span.shell.sqlite_store import SqliteSemanticStore

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

    def test_repository_status_groups_snapshots_by_recorded_scope(self):
        # J-A4/S1.5: exercise the actual repository-status projection, not
        # only the grouping helper. Two subjects share one scope and one
        # subject uses another; status must perform exactly one walk per
        # distinct recorded scope and never fall back to an unconditional
        # repository-global walk.
        import datetime

        from span.service.operations.status import (
            _compose_repository_status_answer,
        )

        class CountingEvidence(FixtureEvidenceSource):
            def __init__(self, files):
                super().__init__(REPO, files)
                self.scopes = []

            def list_inventory_entries(
                self, repository_id, scope, fingerprint_locators=()
            ):
                self.scopes.append(scope)
                return super().list_inventory_entries(
                    repository_id, scope, fingerprint_locators
                )

        files = {
            "mod/a.py": "A = 1\n",
            "mod/b.py": "B = 2\n",
            "other/c.py": "C = 3\n",
        }
        evidence = CountingEvidence(files)
        subjects = tuple(
            m.Subject(
                subject_id=m.SubjectId(
                    repository_id=REPO,
                    subject_kind=m.SubjectKind.COMPONENT,
                    canonical_locator=path,
                ),
                display_name=path,
                declared_kind=None,
            )
            for path in files
        )
        scope_mod = m.EvidenceScope(paths=("mod",))
        scope_other = m.EvidenceScope(paths=("other",))
        dependencies = []
        coverages = []
        for subject, scope in zip(
            subjects, (scope_mod, scope_mod, scope_other)
        ):
            question = m.SemanticQuestionScope(
                scope_root=subject.subject_id,
                subject=subject.subject_id,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice=f"purpose:{subject.display_name}",
                materiality_basis="status locality test",
            )
            dependencies.append(
                m.CoverageDependency(
                    scope_subjects=(subject.subject_id,),
                    discovery_scope=scope,
                    question=question,
                )
            )
            coverages.append(
                m.InterpretationCoverage(
                    subjects=(subject.subject_id,),
                    question_slice=question.question_slice,
                    evidence_scope=scope,
                    question=question,
                    disposition=m.SemanticQuestionDisposition.OPEN,
                    resolution_requirements=(
                        m.ResolutionRequirement(
                            kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                            description="status locality test",
                        ),
                    ),
                    disposition_basis="status locality test",
                )
            )
        store = SqliteSemanticStore(":memory:")
        try:
            bounds = m.QueryBounds(
                max_results=50,
                max_depth=5,
                max_subjects=8,
                max_evidence_units=24,
                max_evidence_bytes=96_000,
                max_candidate_claims=64,
                max_candidate_relationships=64,
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=subjects,
                    coverage_dependencies=tuple(dependencies),
                    coverage=tuple(coverages),
                )
            )
            _compose_repository_status_answer(
                REPO,
                evidence=evidence,
                store=store,
                bounds=bounds,
                state=m.RepositoryState(
                    repository_id=REPO,
                    revision_id="fixture",
                    dirty=False,
                    state_fingerprint="fixture",
                    observed_at=datetime.datetime.now(datetime.timezone.utc),
                ),
            )
        finally:
            store.close()
        self.assertEqual(
            evidence.scopes,
            [scope_mod, scope_other],
        )


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
                stale_effective_question_count=1,
                active_target_association_count=3,
                persisted_target_accounted_count=4,
                persisted_target_unresolved_count=2,
                bounded_live_target_unaccounted_count=1,
            )
            self.assertEqual(report.pending_question_count, 2)
            self.assertEqual(report.open_question_count, 1)
            self.assertEqual(report.stale_effective_question_count, 1)
            self.assertEqual(report.active_target_association_count, 3)
            self.assertEqual(report.persisted_target_accounted_count, 4)
            self.assertEqual(report.persisted_target_unresolved_count, 2)
            self.assertEqual(report.bounded_live_target_unaccounted_count, 1)
            self.assertIs(
                report.question_disposition_scope,
                m.SemanticCoverageAggregateScope.PERSISTED_GLOBAL,
            )
            self.assertIs(
                report.target_burden_live_scope,
                m.SemanticCoverageAggregateScope.BOUNDED_LIVE,
            )
        finally:
            store.close()

    def test_target_burden_aggregates_are_store_owned(self):
        store = SqliteSemanticStore(":memory:")
        try:
            subject = m.SubjectId(
                repository_id="r",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator="src/a.py",
            )
            ref = m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-a"),
                repository_id="r",
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/a.py",
                revision_or_fingerprint="fp-a",
            )
            unresolved = m.TargetInventoryAccount(
                evidence_ref=ref,
                resolution_requirements=(m.ResolutionRequirement(
                    kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                    description="unresolved mapping",
                ),),
            )
            accounted = m.TargetInventoryAccount(
                evidence_ref=m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-b"),
                    repository_id="r",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator="src/b.py",
                    revision_or_fingerprint="fp-b",
                ),
                assigned_area_subjects=(subject,),
            )
            association = m.TargetAssociation(
                target_id=m.TargetId("target-r"),
                repository_id="r",
                target_scope=m.EvidenceScope(paths=("src/",)),
                objective="test target burden",
                area_subjects=(subject,),
                inventory_accounting=(accounted, unresolved),
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(target_associations=(association,))
            )
            self.assertEqual(store.count_target_associations("r"), 1)
            self.assertEqual(
                store.count_target_inventory_outcomes("r"), (1, 1)
            )
            self.assertEqual(
                store.load_active_target_associations("r"), (association,)
            )
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
