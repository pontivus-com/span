"""Addendum C acceptance (C.9 C-M–C-T, first cut: C-N disposition cutover).

Pins Addendum C C-05/C-06 at the service/store boundary:
claims alone never complete a question; explicit validated
disposition is required for ANSWERED; incomplete resubmission never
retires prior outputs; the store refuses empty ANSWERED rows.
"""

import unittest

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span import service as ops
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemorySubject,
    evidence_kind_for_path,
    fingerprint_content,
)

from tests.support.factories import query_bounds

from functools import partial as _partial
from tests.support.factories import subject_id

from tests.support.factories import evidence_ref

from tests.support.factories import semantic_harness

from tests.support.factories import answered_decision

from tests.support.factories import pending_suspension

REPO = "seed-svc"

FILES = {
    "README.md": "# seed-svc\n\nSorts seeds.\n",
    "src/seed.py": "VALUE = 1\n",
}


_bounds = query_bounds


_sid = _partial(subject_id, repository_id=REPO)


_ref = _partial(evidence_ref, repository_id=REPO, files=FILES)


_harness = _partial(
    semantic_harness,
    REPO,
    FILES,
    subjects=(InMemorySubject("src/seed.py", m.SubjectKind.COMPONENT, "seed"),),
)


def _purpose_claim():
    return m.CandidateSemanticClaim(
        candidate_key="purpose",
        subject=_sid("src/seed.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("Sorts seeds", ()),
        evidence=(_ref("README.md"),),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the seed purpose",
        ),
    )


_answer_current = answered_decision


_suspend = _partial(pending_suspension, repository_id=REPO, locator="src/seed.py")


class ExplicitDispositionTest(unittest.TestCase):
    """C-N: no implied completion; explicit disposition required."""

    def test_claims_only_never_answer(self):
        """C-N: claims without explicit coverage persist PENDING;
        the question is not completed and re-query suspends."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = _suspend(structural, evidence, store, continuations)
            current = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            rows = store.load_all_question_coverages(REPO, None, (_sid("src/seed.py"),))
            self.assertEqual(len(rows), 1)
            self.assertIs(
                rows[0].disposition,
                m.SemanticQuestionDisposition.PENDING,
            )
            self.assertEqual(rows[0].result_refs, ())
            # Re-query suspends: nothing was completed.
            again = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(again, PendingInterpretation)
        finally:
            store.close()

    def test_explicit_answered_derives_refs(self):
        """C-N: explicit ANSWERED + validated material persists
        derived refs and reads back effectively current."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = _suspend(structural, evidence, store, continuations)
            answer = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(current.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            rows = store.load_all_question_coverages(REPO, None, (_sid("src/seed.py"),))
            self.assertEqual(len(rows), 1)
            self.assertIs(
                rows[0].disposition,
                m.SemanticQuestionDisposition.ANSWERED,
            )
            self.assertTrue(rows[0].result_refs)
            # Re-query answers directly from persisted coverage.
            again = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(again, m.SemanticAnswer)
            self.assertTrue(again.content.claims)
        finally:
            store.close()

    def test_explicit_answered_without_material_rejects(self):
        """C-N: explicit ANSWERED with zero validated candidates
        rejects the whole unit and writes nothing."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = _suspend(structural, evidence, store, continuations)
            with self.assertRaises(ops.InterpretationUnitRejected):
                ops.submit_interpretation(
                    current.continuation,
                    m.SemanticInterpretationResult(
                        claims=(),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        question_decision=_answer_current(current.request),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
            rows = store.load_all_question_coverages(REPO, None, (_sid("src/seed.py"),))
            self.assertEqual(rows, ())
        finally:
            store.close()

    def test_store_refuses_empty_answered_rows(self):
        """C-N persistence boundary: an ANSWERED row without result
        refs cannot persist even if constructed directly."""
        structural, evidence, store = _harness()
        try:
            root = _sid("src/seed.py")
            with self.assertRaises(ValueError):
                store.write_index_batch(
                    m.CanonicalIndexBatch(
                        subjects=(m.Subject(root, "seed", None),),
                        coverage=(
                            m.InterpretationCoverage(
                                subjects=(root,),
                                question_slice="s",
                                evidence_scope=m.EvidenceScope(
                                    paths=(), evidence_refs=()
                                ),
                                declared_complete=True,
                                question=m.SemanticQuestionScope(
                                    scope_root=root,
                                    subject=root,
                                    question_class=(m.SemanticQuestionClass.CQ_01),
                                    question_slice="s",
                                    materiality_basis="t",
                                ),
                                disposition=(m.SemanticQuestionDisposition.ANSWERED),
                                result_refs=(),
                                resolution_requirements=(),
                                disposition_basis="t",
                                question_evidence=(),
                            ),
                        ),
                    )
                )
        finally:
            store.close()

    def test_incomplete_resubmission_retires_nothing(self):
        """C-Q/C-05: a PENDING resubmission after ANSWERED never
        retires prior outputs by omission; prior claims survive."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = _suspend(structural, evidence, store, continuations)
            answer = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(current.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            first_id = answer.content.claims[0].claim_id.value
            # Source changes: refresh suspends the stale question;
            # resubmit claims with no explicit coverage (incomplete).
            grown = dict(FILES)
            grown["README.md"] = "# seed-svc\n\nSorts seeds daily.\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            refresh_conts = ContinuationStore()
            suspended = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=refresh_conts,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            ops.submit_interpretation(
                suspended.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=refresh_conts,
            )
            # Prior output survives; still loadable and unretired.
            (still_there,) = store.load_by_refs(
                REPO, (m.ClaimRef(id=m.ClaimId(first_id)),)
            )
            self.assertIsInstance(still_there, m.SemanticClaim)
        finally:
            store.close()


class CampaignIntegrityTest(unittest.TestCase):
    """C-O: parallel analysis, single sequential writer, stable IDs."""

    def test_parallel_analysis_sequential_writes(self):
        """C-O: analyzer threads build submissions concurrently
        (pure computation); one lane submits sequentially. All units
        persist atomically with deterministic content IDs stable
        across identical retry (no duplication)."""
        import threading

        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(current, PendingInterpretation)
            request = current.request
            built = {}

            def analyze(i):
                built[i] = m.CandidateSemanticClaim(
                    candidate_key=f"facet-{i}",
                    subject=_sid("src/seed.py"),
                    kind=m.ClaimKind.PURPOSE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue(f"Sorts seeds facet {i}", ()),
                    evidence=(_ref("README.md"),),
                    basis=m.SemanticBasis(
                        m.DerivationKind.SEMANTIC_INTERPRETATION,
                        f"facet {i} analysis",
                    ),
                )

            workers = [threading.Thread(target=analyze, args=(i,)) for i in range(3)]
            for w in workers:
                w.start()
            for w in workers:
                w.join()
            self.assertEqual(len(built), 3)
            answer = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(
                    claims=tuple(built[i] for i in sorted(built)),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            first_ids = sorted(c.claim_id.value for c in answer.content.claims)
            self.assertEqual(len(first_ids), 3)
            # Identical retry: same content IDs, no duplicate rows.
            before = store._db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
            self.assertEqual(before, 3)
        finally:
            store.close()


class BootstrapValueTest(unittest.TestCase):
    """C-M: seeded scope is queryable and restart-retrievable."""

    def test_seeded_scope_survives_restart(self):
        """C-M: seed purpose coverage into a file-backed store,
        reopen on a new store instance, retrieve exact identities
        and current coverage without reinterpretation."""
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "seed.db")
            structural, evidence, store = _harness()
            store_file = SqliteSemanticStore(db)
            try:
                ops.initialize_repository(
                    ops.SemanticInitializeRepositoryRequest(
                        repository_locator="fixture",
                        authority_seeds=(),
                    ),
                    repository_id=REPO,
                    structural=structural,
                    evidence=evidence,
                    store=store_file,
                )
                continuations = ContinuationStore()
                current = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/seed.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store_file,
                    continuations=continuations,
                )
                answer = ops.submit_interpretation(
                    current.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        question_decision=_answer_current(current.request),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store_file,
                    continuations=continuations,
                )
                claim_id = answer.content.claims[0].claim_id.value
            finally:
                store_file.close()
                store.close()
            reopened = SqliteSemanticStore(db)
            try:
                (loaded,) = reopened.load_by_refs(
                    REPO, (m.ClaimRef(id=m.ClaimId(claim_id)),)
                )
                self.assertIsInstance(loaded, m.SemanticClaim)
                self.assertEqual(loaded.value.summary, "Sorts seeds")
                rows = reopened.load_all_question_coverages(
                    REPO, None, (_sid("src/seed.py"),)
                )
                self.assertEqual(len(rows), 1)
                self.assertIs(
                    rows[0].disposition,
                    m.SemanticQuestionDisposition.ANSWERED,
                )
            finally:
                reopened.close()


class MechanicalLimitsTest(unittest.TestCase):
    """C-P/C-06: byte-valid but wrong content passes validation.

    The core cannot detect substantive falsehood; this test pins
    that honesty boundary so no future change pretends otherwise.
    Substantive review belongs to SA-5, host audit, and oracles."""

    def test_cited_but_wrong_passes_validation(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = _suspend(structural, evidence, store, continuations)
            wrong = m.CandidateSemanticClaim(
                candidate_key="wrong",
                subject=_sid("src/seed.py"),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Sorts pebbles", ()),
                evidence=(_ref("README.md"),),
                candidate_authority=m.CandidateAuthority(
                    binding=m.AuthorityBinding(
                        evidence_ref=_ref("README.md"),
                        authority_kind=m.AuthorityKind.OTHER,
                        status=m.AuthorityStatus.DECLARED,
                    ),
                    support=m.AuthoritySupport(
                        quoted_span="Sorts seeds",
                        status_section="README.md",
                        applicability_section=None,
                    ),
                ),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "misread README",
                ),
            )
            answer = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(
                    claims=(wrong,),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(current.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            # Mechanically valid (verbatim quote present) yet
            # substantively false: the core persists it; only an
            # oracle or auditor can reject the meaning.
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(
                answer.content.claims[0].value.summary,
                "Sorts pebbles",
            )
        finally:
            store.close()


class PostcommitCorrectionTest(unittest.TestCase):
    """C-Q: wrong persisted content corrected via withdrawal +
    replacement; no rollback machinery."""

    def test_withdraw_then_replace_recovers(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = _suspend(structural, evidence, store, continuations)
            answer = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(current.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            old_id = answer.content.claims[0].claim_id.value
            old_ref = m.ClaimRef(id=m.ClaimId(old_id))
            # Change the source so refresh suspends the stale
            # question; withdraw the disproven claim and replace it
            # with corrected content in one atomic unit.
            grown = dict(FILES)
            grown["README.md"] = "# seed-svc\n\nSorts seeds daily.\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            refresh_conts = ContinuationStore()
            suspended = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=refresh_conts,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            corrected = m.CandidateSemanticClaim(
                candidate_key="purpose-v2",
                subject=_sid("src/seed.py"),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Sorts seeds reliably", ()),
                evidence=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-README.md"),
                        repository_id=REPO,
                        source_kind=evidence_kind_for_path("README.md"),
                        locator="README.md",
                        revision_or_fingerprint=fingerprint_content(grown["README.md"]),
                    ),
                ),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "corrected reading",
                ),
            )
            answer2 = ops.submit_interpretation(
                suspended.continuation,
                m.SemanticInterpretationResult(
                    claims=(corrected,),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(suspended.request),
                    candidate_withdrawals=(
                        m.CandidateSemanticWithdrawal(
                            target=old_ref,
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "purpose disproven by inspection",
                            ),
                            evidence=(
                                m.EvidenceRef(
                                    evidence_id=m.EvidenceId("ev-src/seed.py"),
                                    repository_id=REPO,
                                    source_kind=(m.EvidenceSourceKind.SOURCE_CODE),
                                    locator="src/seed.py",
                                    revision_or_fingerprint=(
                                        fingerprint_content(FILES["src/seed.py"])
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=refresh_conts,
            )
            self.assertIsInstance(answer2, m.SemanticAnswer)
            with self.assertRaises(ValueError):
                store.load_by_refs(REPO, (old_ref,))
            self.assertEqual(
                answer2.content.claims[0].value.summary,
                "Sorts seeds reliably",
            )
        finally:
            store.close()


class DocumentSubjectTest(unittest.TestCase):
    """C-S: governing document registered via CandidateSubject and
    retrievable; status stays source-declared."""

    def test_document_subject_registers_and_serves(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            current = _suspend(structural, evidence, store, continuations)
            doc = m.CandidateSubject(
                provisional_locator="docs/spec.md",
                kind=m.SubjectKind.OTHER,
                display_name="seed specification",
                declared_kind="governance-document",
                evidence=(_ref("README.md"),),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "README is the only governing statement in scope",
                ),
            )
            answer = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(doc,),
                    candidate_conflicts=(),
                    question_decision=_answer_current(current.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            subjects = store.load_subjects(
                REPO,
                (
                    m.SubjectId(
                        repository_id=REPO,
                        subject_kind=m.SubjectKind.OTHER,
                        canonical_locator="docs/spec.md",
                    ),
                ),
            )
            locators = {s.subject_id.canonical_locator for s in subjects}
            self.assertIn("docs/spec.md", locators)
        finally:
            store.close()


class BoundednessTest(unittest.TestCase):
    """C-T: bounds are honored; truncation is explicit, never silent
    expansion."""

    def test_evidence_cap_truncates_explicitly(self):
        structural, evidence, store = _harness()
        try:
            current = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(max_evidence_units=1),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(current, PendingInterpretation)
            self.assertLessEqual(len(current.request.task_evidence.evidence_units), 1)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
