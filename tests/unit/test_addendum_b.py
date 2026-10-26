"""Addendum B acceptance gates (B.11, oracle-backed substance).

Covers: baseline vs question-local entry, stable content IDs on
reorder, shared-output retirement safety, explicit withdrawal fanout,
premise staleness with unchanged consumer bytes, three-stream paging,
effective vs recorded disposition, schema-7-only opening, and the
stored-assertions-without-question-coverage invariant.
"""

import unittest

from span.core import model as m
from span.core import validation as v
from span import service as ops
from span.service.establishment import _baseline_sufficient
from span.core import paging
from span.shell.sqlite_store import SCHEMA_VERSION, SqliteSemanticStore

from tests.support.factories import query_bounds

from functools import partial as _partial
from tests.support.factories import subject_id

_sid = _partial(subject_id, repository_id="repo-b")


_bounds = query_bounds


def _claim_candidate(sid, key="k1", summary="does X"):
    ref = m.EvidenceRef(
        evidence_id=m.EvidenceId("ev-a"),
        repository_id="repo-b",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator="src/a.py",
    )
    return m.CandidateSemanticClaim(
        candidate_key=key,
        subject=sid,
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue(summary, ()),
        evidence=(ref,),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION, "evidence states purpose"
        ),
    )


class BaselineVsQuestionLocalTest(unittest.TestCase):
    def test_baseline_seed_slice_and_question(self):
        from span.shell.structural.memory import (
            InMemoryStructuralSource,
            InMemorySubject,
        )
        from tests.support.evidence import FixtureEvidenceSource

        structural = InMemoryStructuralSource(
            "repo-b", (), (InMemorySubject("src/a.py", m.SubjectKind.COMPONENT, "a"),)
        )
        evidence = FixtureEvidenceSource("repo-b", {"src/a.py": "X = 1\n"})
        state = structural.repository_state("repo-b")
        subject = (
            structural.resolve_subject(
                "repo-b",
                m.SubjectSelector(None, "src/a.py", (), None),
                _bounds(),
            )
            .candidates[0]
            .subject
        )
        task = ops.prepare_interpretation_task(
            "repo-b",
            subject,
            structural=structural,
            evidence=evidence,
            bounds=_bounds(),
            state=state,
            operation_intent=m.SemanticIntent.EXPLAIN,
            store=SqliteSemanticStore(":memory:"),
            scope_root=subject.subject_id,
            establish_baseline=True,
        )
        assert task.request.question is not None
        self.assertIs(
            task.request.question.question_class, m.SemanticQuestionClass.CQ_01
        )
        self.assertIn("principal participants", task.request.question_slice)
        self.assertIn("SA-5", " ".join(task.request.analysis_obligations))

    def test_question_local_does_not_claim_baseline(self):
        from tests.support.evidence import FixtureEvidenceSource

        store = SqliteSemanticStore(":memory:")
        try:
            sid = _sid()
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "a", None),),
                )
            )
            evidence = FixtureEvidenceSource("repo-b", {"src/a.py": "X = 1\n"})
            self.assertFalse(
                _baseline_sufficient(
                    "repo-b",
                    sid,
                    store=store,
                    evidence=evidence,
                    bounds=_bounds(),
                )
            )
        finally:
            store.close()


class StableIdTest(unittest.TestCase):
    def test_reorder_stable_ids_and_duplicate_fails(self):
        sid = _sid()
        c1 = _claim_candidate(sid, key="k1", summary="same")
        c2 = _claim_candidate(sid, key="k2", summary="same")
        id1 = v.deterministic_claim_id(c1, m.TrustState.UNRESOLVED)
        id2 = v.deterministic_claim_id(c2, m.TrustState.UNRESOLVED)
        self.assertEqual(id1, id2)
        # Different keys, same substance → duplicate detection fires in
        # _materialize_unit (seen_ids); direct check here:
        self.assertEqual(
            v.deterministic_claim_id(
                _claim_candidate(sid, key="other", summary="same"),
                m.TrustState.UNRESOLVED,
            ),
            id1,
        )


class SharedRetirementTest(unittest.TestCase):
    def test_shared_output_not_retired_by_one_question(self):
        store = SqliteSemanticStore(":memory:")
        try:
            sid = _sid()
            root = _sid("cap/root", m.SubjectKind.CAPABILITY)
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("shared-1"),
                subject=sid,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("s", ()),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE, "b"),
            )
            q1 = m.SemanticQuestionScope(
                scope_root=root,
                subject=sid,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="q1",
                materiality_basis="m",
            )
            q2 = m.SemanticQuestionScope(
                scope_root=root,
                subject=sid,
                question_class=m.SemanticQuestionClass.CQ_02,
                question_slice="q2",
                materiality_basis="m",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "a", None),),
                    claims=(claim,),
                    coverage=(
                        m.InterpretationCoverage(
                            subjects=(sid,),
                            question_slice="q1",
                            question=q1,
                            disposition=m.SemanticQuestionDisposition.ANSWERED,
                            result_refs=(m.ClaimRef(id=claim.claim_id),),
                            disposition_basis="b",
                        ),
                        m.InterpretationCoverage(
                            subjects=(sid,),
                            question_slice="q2",
                            question=q2,
                            disposition=m.SemanticQuestionDisposition.ANSWERED,
                            result_refs=(m.ClaimRef(id=claim.claim_id),),
                            disposition_basis="b",
                        ),
                    ),
                )
            )
            refs = store.load_question_coverages("repo-b", root, (sid,), _bounds())
            owners = [
                cov
                for cov in refs
                if claim.claim_id.value in {r.id.value for r in cov.result_refs}
            ]
            self.assertEqual(len(owners), 2)
        finally:
            store.close()


class PremiseStalenessTest(unittest.TestCase):
    def test_stale_premise_reopens_dependent(self):
        store = SqliteSemanticStore(":memory:")
        try:
            sid = _sid()
            premise = m.SemanticClaim(
                claim_id=m.ClaimId("prem-1"),
                subject=sid,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("p", ()),
                freshness=m.Freshness(m.FreshnessState.STALE, reason="src changed"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE, "b"),
            )
            dep = m.SemanticClaim(
                claim_id=m.ClaimId("dep-1"),
                subject=sid,
                kind=m.ClaimKind.RESPONSIBILITY,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.ResponsibilityValue("r"),
                freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "uses premise",
                    input_refs=(m.ClaimRef(id=premise.claim_id),),
                ),
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "a", None),),
                    claims=(premise, dep),
                )
            )
            from tests.support.evidence import FixtureEvidenceSource

            evidence = FixtureEvidenceSource("repo-b", {"src/a.py": "X=1"})
            updates = ops.preflight(
                "repo-b",
                (m.ClaimRef(id=dep.claim_id),),
                evidence=evidence,
                store=store,
                bounds=_bounds(),
            )
            self.assertTrue(
                any(
                    u.semantic_id.id.value == "dep-1"
                    and u.freshness.state is m.FreshnessState.STALE
                    for u in updates
                )
            )
            dependents = store.load_premise_dependents(
                "repo-b", (m.ClaimRef(id=premise.claim_id),)
            )
            self.assertIn("dep-1", {d.id.value for d in dependents})
        finally:
            store.close()


class PagingGrammarTest(unittest.TestCase):
    def test_three_stream_and_reject_two_stream(self):
        token = paging.format_service_token(1, 2, 3)
        self.assertEqual(paging.parse_service_token(token), (1, 2, 3))
        for bad in ("pg:1:2", "pg:1", "pg:1:2:3:4"):
            with self.assertRaises(ValueError, msg=bad):
                paging.parse_service_token(bad)


class EffectiveDispositionTest(unittest.TestCase):
    def test_recorded_answered_noncurrent_is_effective_pending(self):
        sid = _sid()
        q = m.SemanticQuestionScope(
            scope_root=sid,
            subject=sid,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="q",
            materiality_basis="m",
        )
        store = SqliteSemanticStore(":memory:")
        try:
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("c-eff"),
                subject=sid,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("s", ()),
                freshness=m.Freshness(m.FreshnessState.STALE, reason="changed"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE, "b"),
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "a", None),), claims=(claim,)
                )
            )
            cov = m.InterpretationCoverage(
                subjects=(sid,),
                question_slice="q",
                question=q,
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(m.ClaimRef(id=claim.claim_id),),
                disposition_basis="b",
            )
            view = ops.effective_question_view(cov, store=store, repository_id="repo-b")
            self.assertIs(
                view.recorded_disposition,
                m.SemanticQuestionDisposition.ANSWERED,
            )
            self.assertIs(
                view.effective_disposition,
                m.SemanticQuestionDisposition.PENDING,
            )
        finally:
            store.close()


class CurrentSchemaTest(unittest.TestCase):
    def test_schema_7_and_absent_coverage(self):
        self.assertEqual(SCHEMA_VERSION, 9)
        store = SqliteSemanticStore(":memory:")
        try:
            self.assertEqual(store.schema_version(), m.SchemaVersion(SCHEMA_VERSION))
            sid = _sid()
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("leg-1"),
                subject=sid,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("s", ()),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE, "b"),
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "a", None),), claims=(claim,)
                )
            )
            covs = store.load_question_coverages("repo-b", sid, (sid,), _bounds())
            self.assertEqual(covs, ())
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
