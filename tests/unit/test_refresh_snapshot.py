"""0.8.3 D2: refresh drains a finite per-subject snapshot once per member."""

from __future__ import annotations

import inspect
import unittest

from span import service as ops
from span.core import model as m
from span.core.validation import InterpretationUnitRejected
from span.ports.interpretation import PendingInterpretation
from span.service.exchange.resume import _resume_refresh_cycle
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.structural.memory import InMemorySubject
from tests.support.factories import (
    evidence_ref,
    query_bounds,
    semantic_harness,
    subject_id,
)

REPOSITORY_ID = "repo-1"
FILES = {
    "README.md": "# svc\n\nDoes things.\n",
    "src/main.py": "VALUE = 1\n",
}
SUBJECTS = (InMemorySubject("src/main.py", m.SubjectKind.COMPONENT, "main"),)
SUBJECT = subject_id("src/main.py")


def _pending_question(
    question_class: m.SemanticQuestionClass,
    question_slice: str,
) -> m.SemanticQuestionScope:
    return m.SemanticQuestionScope(
        scope_root=SUBJECT,
        subject=SUBJECT,
        question_class=question_class,
        question_slice=question_slice,
        materiality_basis="refresh snapshot test",
    )


def _write_pending(
    store: object,
    question: m.SemanticQuestionScope,
    result_refs: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
) -> None:
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=(m.Subject(SUBJECT, "main", None),),
            coverage=(
                m.InterpretationCoverage(
                    subjects=(SUBJECT,),
                    question_slice=question.question_slice,
                    evidence_scope=m.EvidenceScope(),
                    question=question,
                    disposition=m.SemanticQuestionDisposition.PENDING,
                    result_refs=result_refs,
                    disposition_basis="admitted",
                ),
            ),
        )
    )


SHARED_CLAIM = m.SemanticClaim(
    claim_id=m.ClaimId("clm-shared"),
    subject=SUBJECT,
    kind=m.ClaimKind.PURPOSE,
    value=m.PurposeValue("shared basis", ()),
    assertion_nature=m.AssertionNature.DESCRIPTIVE,
    freshness=m.Freshness(m.FreshnessState.CURRENT, reason="fixture current"),
)


def _write_answered_dependent(
    store: object,
    question: m.SemanticQuestionScope,
) -> None:
    """A current question whose result the first submission withdraws.

    It is not eligible when the snapshot is taken; the withdrawal reopens it
    mid-chain, so it must be deferred rather than attempted in this chain.
    """
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=(m.Subject(SUBJECT, "main", None),),
            claims=(SHARED_CLAIM,),
            coverage=(
                m.InterpretationCoverage(
                    subjects=(SUBJECT,),
                    question_slice=question.question_slice,
                    evidence_scope=m.EvidenceScope(),
                    question=question,
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    result_refs=(m.ClaimRef(id=SHARED_CLAIM.claim_id),),
                    disposition_basis="established from shared basis",
                ),
            ),
        )
    )


def _pending_decision(basis: str) -> m.SemanticQuestionDecision:
    return m.SemanticQuestionDecision(
        disposition=m.SemanticQuestionDisposition.PENDING,
        disposition_basis=basis,
    )


def _refresh(
    structural: object,
    evidence: object,
    store: object,
    continuations: object,
) -> m.SemanticAnswer | PendingInterpretation:
    return ops.refresh(
        ops.SemanticRefreshRequest(
            repository_id=REPOSITORY_ID,
            target=m.SubjectSelector(None, "src/main.py", (), None),
            bounds=query_bounds(),
        ),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )


def _submit(
    pending: PendingInterpretation,
    *,
    structural: object,
    evidence: object,
    store: object,
    continuations: object,
    proposed: tuple[m.ProposedSemanticQuestion, ...] = (),
    withdrawals: tuple[m.CandidateSemanticWithdrawal, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    return ops.submit_interpretation(
        pending.continuation,
        m.SemanticInterpretationResult(
            question_decision=_pending_decision("still under examination"),
            proposed_questions=proposed,
            candidate_withdrawals=withdrawals,
        ),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )


class RefreshSnapshotTest(unittest.TestCase):
    def test_two_pending_questions_are_attempted_once_each(self):
        structural, evidence, store = semantic_harness(
            REPOSITORY_ID, FILES, subjects=SUBJECTS
        )
        try:
            continuations = ContinuationStore()
            alpha = _pending_question(m.SemanticQuestionClass.CQ_02, "alpha slice")
            zeta = _pending_question(m.SemanticQuestionClass.CQ_03, "zeta slice")
            _write_pending(store, zeta)
            _write_pending(store, alpha)

            first = _refresh(structural, evidence, store, continuations)
            self.assertIsInstance(first, PendingInterpretation)
            self.assertEqual(first.request.question.question_slice, "alpha slice")

            second = _submit(
                first,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(second, PendingInterpretation)
            self.assertEqual(second.request.question.question_slice, "zeta slice")

            final = _submit(
                second,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(final, m.SemanticAnswer)
            views = final.content.question_coverage
            self.assertEqual(
                {v.question.question_slice for v in views},
                {"alpha slice", "zeta slice"},
            )
            self.assertTrue(
                all(
                    v.effective_disposition is m.SemanticQuestionDisposition.PENDING
                    for v in views
                )
            )
            self.assertIn(
                "coverage: 0 answered, 2 open of 2 questions", final.state_explanation
            )
        finally:
            store.close()

    def test_repeated_pending_submission_terminates(self):
        structural, evidence, store = semantic_harness(
            REPOSITORY_ID, FILES, subjects=SUBJECTS
        )
        try:
            continuations = ContinuationStore()
            _write_pending(
                store,
                _pending_question(m.SemanticQuestionClass.CQ_02, "alpha slice"),
            )
            _write_pending(
                store,
                _pending_question(m.SemanticQuestionClass.CQ_03, "zeta slice"),
            )
            pending = _refresh(structural, evidence, store, continuations)
            self.assertIsInstance(pending, PendingInterpretation)
            for _ in range(2):
                result = _submit(
                    pending,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
                if isinstance(result, m.SemanticAnswer):
                    break
                pending = result
            self.assertIsInstance(result, m.SemanticAnswer)
            self.assertIn(
                "coverage: 0 answered, 2 open of 2 questions",
                result.state_explanation,
            )
        finally:
            store.close()

    def test_question_reopened_mid_chain_is_deferred_not_attempted(self):
        structural, evidence, store = semantic_harness(
            REPOSITORY_ID, FILES, subjects=SUBJECTS
        )
        try:
            continuations = ContinuationStore()
            _write_answered_dependent(
                store,
                _pending_question(m.SemanticQuestionClass.CQ_04, "late slice"),
            )
            _write_pending(
                store,
                _pending_question(m.SemanticQuestionClass.CQ_02, "alpha slice"),
                result_refs=(m.ClaimRef(id=SHARED_CLAIM.claim_id),),
            )
            pending = _refresh(structural, evidence, store, continuations)
            self.assertIsInstance(pending, PendingInterpretation)

            final = _submit(
                pending,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                withdrawals=(
                    m.CandidateSemanticWithdrawal(
                        target=m.ClaimRef(id=SHARED_CLAIM.claim_id),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION,
                            "retracted: superseded by new evidence",
                        ),
                        evidence=(
                            evidence_ref(
                                "README.md",
                                repository_id=REPOSITORY_ID,
                                files=FILES,
                            ),
                        ),
                    ),
                ),
            )
            self.assertIsInstance(final, m.SemanticAnswer)
            descriptions = " ".join(
                requirement.description for requirement in final.resolution_requirements
            )
            self.assertIn("late slice", descriptions)
            self.assertIn("deferred", descriptions)
            self.assertEqual(
                {v.question.question_slice for v in final.content.question_coverage},
                {"alpha slice", "late slice"},
            )
        finally:
            store.close()

    def test_no_iteration_cap_constant(self):
        source = inspect.getsource(_resume_refresh_cycle)
        self.assertNotIn("while ", source)
        self.assertNotIn("MAX_", source)
        self.assertNotIn("refresh_cap", source)

    def test_new_question_proposal_is_rejected_not_silently_deferred(self):
        """A brand-new identity cannot enter a refresh chain at all.

        The snapshot/deferral rule covers identities that become eligible
        during the chain, such as a question reopened by a withdrawal. A
        newly proposed question is not such an identity: refresh treats any
        non-bound submitted question as a correction nomination and rejects
        it unless the exact scope is already persisted. That rejection is
        loud, persists nothing, and leaves the continuation usable.
        """
        structural, evidence, store = semantic_harness(
            REPOSITORY_ID, FILES, subjects=SUBJECTS
        )
        try:
            continuations = ContinuationStore()
            _write_pending(
                store,
                _pending_question(m.SemanticQuestionClass.CQ_02, "alpha slice"),
            )
            _write_pending(
                store,
                _pending_question(m.SemanticQuestionClass.CQ_03, "zeta slice"),
            )
            pending = _refresh(structural, evidence, store, continuations)
            self.assertIsInstance(pending, PendingInterpretation)

            proposed_question = m.SemanticQuestionScope(
                scope_root=SUBJECT,
                subject=SUBJECT,
                question_class=m.SemanticQuestionClass.CQ_05,
                question_slice="proposed mid-chain",
                materiality_basis="proposed during a refresh unit",
            )
            with self.assertRaises(InterpretationUnitRejected) as caught:
                _submit(
                    pending,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                    proposed=(
                        m.ProposedSemanticQuestion(
                            proposed_question,
                            _pending_decision("proposed mid-chain"),
                        ),
                    ),
                )
            self.assertIn("not an exact persisted", str(caught.exception))

            stored = store.load_all_question_coverages(REPOSITORY_ID, None, (SUBJECT,))
            self.assertNotIn(
                "proposed mid-chain",
                {
                    coverage.question.question_slice
                    for coverage in stored
                    if coverage.question is not None
                },
            )

            # The rejected unit did not consume the continuation or the
            # snapshot: the next valid submission still advances to zeta.
            second = _submit(
                pending,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(second, PendingInterpretation)
            self.assertEqual(second.request.question.question_slice, "zeta slice")
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
