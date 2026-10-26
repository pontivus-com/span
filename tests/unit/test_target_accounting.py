"""Target admission: membership is computed, questions are asked.

The target association is established deterministically. Inventory membership
is never a model unit: every member is assigned to the scope's area subject,
one service-owned CQ-01 seed is admitted, and the exchange asks only the
semantic question. A restart resumes that question instead of re-asking a new
one.
"""

import unittest

from span import service as ops
from span.core import model as m
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.structural.memory import (
    InMemorySubject,
)

from tests.support.factories import query_bounds

from functools import partial as _partial

from tests.support.factories import semantic_harness

REPO = "target-acct-svc"

FILES = {
    "README.md": "# target-acct-svc\n\nTracks balances.\n",
    "src/postings.py": "POSTING = 1\n",
    "src/inventory.py": "STOCK = {}\n",
}

TARGET_PATHS = ("src/postings.py", "src/inventory.py")
OBJECTIVE = "Establish reusable memory for the postings scope."


_bounds = query_bounds


_harness = _partial(
    semantic_harness,
    REPO,
    FILES,
    subjects=(
        InMemorySubject("src/postings.py", m.SubjectKind.COMPONENT, "postings"),
        InMemorySubject("src/inventory.py", m.SubjectKind.COMPONENT, "inventory"),
    ),
)


def _admit(structural, evidence, store, continuations, paths=TARGET_PATHS):
    return ops.initialize_target(
        ops.SemanticInitializeTargetRequest(
            repository_id=REPO,
            target=m.EvidenceScope(paths=paths, evidence_refs=()),
            objective=OBJECTIVE,
            bounds=_bounds(),
        ),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        authority_seeds=(),
    )


def _association(store):
    scope, objective = m.canonicalize_target_scope(
        REPO, m.EvidenceScope(paths=TARGET_PATHS, evidence_refs=()), OBJECTIVE
    )
    target_id = m.derive_target_id(REPO, scope, objective)
    assoc = store.load_target_association(REPO, target_id)
    assert assoc is not None
    return assoc


class TargetAdmissionTest(unittest.TestCase):
    def test_admission_accounts_inventory_without_a_model_unit(self):
        structural, evidence, store = _harness()
        try:
            live = ContinuationStore()
            pending = _admit(structural, evidence, store, live)
            self.assertTrue(hasattr(pending, "continuation"))
            request = pending.request
            self.assertIsNotNone(
                request.question, "admission must ask a question, not request mapping"
            )
            self.assertEqual(
                request.question.question_class, m.SemanticQuestionClass.CQ_01
            )
            assoc = _association(store)
            self.assertEqual(len(assoc.inventory_accounting), len(TARGET_PATHS))
            self.assertEqual(len(assoc.target_questions), 1)
            self.assertEqual(
                assoc.area_subjects[0].canonical_locator,
                "src",
                "the scope's own root directory is the area",
            )
            for account in assoc.inventory_accounting:
                self.assertEqual(
                    account.assigned_area_subjects, (assoc.area_subjects[0],)
                )
        finally:
            store.close()

    def test_restart_resumes_the_same_pending_question(self):
        structural, evidence, store = _harness()
        try:
            first = _admit(structural, evidence, store, ContinuationStore())
            self.assertTrue(hasattr(first, "continuation"))
            second = _admit(structural, evidence, store, ContinuationStore())
            self.assertTrue(hasattr(second, "continuation"))
            self.assertEqual(
                first.request.question,
                second.request.question,
                "a restart must resume the admitted question, not mint a new one",
            )
            assoc = _association(store)
            self.assertEqual(len(assoc.inventory_accounting), len(TARGET_PATHS))
            self.assertEqual(len(assoc.target_questions), 1)
        finally:
            store.close()

    def test_an_answered_question_is_persisted_and_not_reasked(self):
        structural, evidence, store = _harness()
        try:
            live = ContinuationStore()
            pending = _admit(structural, evidence, store, live)
            self.assertTrue(hasattr(pending, "continuation"))
            request = pending.request
            ref = request.task_evidence.evidence_units[0].evidence_ref
            subject = request.subjects[0].subject_id
            claim = m.CandidateSemanticClaim(
                subject=subject,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Postings root.", ()),
                evidence=(ref,),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "test purpose",
                ),
            )
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(claim,),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        evidence_scope=m.EvidenceScope(evidence_refs=(ref,)),
                        resolution_requirements=(),
                        disposition_basis="answered from the unit evidence",
                    ),
                    proposed_questions=(),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=live,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            coverages = store.load_all_question_coverages(REPO, subject, (subject,))
            self.assertTrue(
                any(
                    cov.disposition is m.SemanticQuestionDisposition.ANSWERED
                    for cov in coverages
                ),
                "the answered question must persist as terminal",
            )
            again = _admit(structural, evidence, store, ContinuationStore())
            self.assertNotIsInstance(
                again,
                type(pending),
                "an answered area must not suspend again",
            )
        finally:
            store.close()

    def test_an_empty_answered_submission_is_rejected(self):
        structural, evidence, store = _harness()
        try:
            live = ContinuationStore()
            pending = _admit(structural, evidence, store, live)
            self.assertTrue(hasattr(pending, "continuation"))
            with self.assertRaises(Exception) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(),
                        relationships=(),
                        governing_source_refs=(),
                        diagnostics=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        question_decision=m.SemanticQuestionDecision(
                            disposition=m.SemanticQuestionDisposition.ANSWERED,
                            evidence_scope=m.EvidenceScope(),
                            resolution_requirements=(),
                            disposition_basis="nothing established",
                        ),
                        proposed_questions=(),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=live,
                )
            self.assertIn("assertion", str(ctx.exception).lower())
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
