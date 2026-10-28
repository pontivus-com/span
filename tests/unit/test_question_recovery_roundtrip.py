"""0.8.3 D1: the stored recipe reproduces the persisted question identity."""

from __future__ import annotations

import unittest

from span import service as ops
from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.ports.structural import StructuralDirection
from span.service.questions.slices import effective_impact_slice
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.agent_exchange import REPO, _bounds, _harness, _sid
from tests.support.factories import proposed_question

SELECTOR = m.SubjectSelector(None, "src/flow.py", (), None)
SUBJECT = _sid("src/flow.py")


def _pending_decision() -> m.SemanticQuestionDecision:
    return m.SemanticQuestionDecision(
        disposition=m.SemanticQuestionDisposition.PENDING,
        disposition_basis="persisted pending for recovery",
    )


def _submit(result, *, structural, evidence, store, continuations, continuation):
    return ops.submit_interpretation(
        continuation,
        result,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )


def _stored_question(store, question):
    (coverage,) = [
        coverage
        for coverage in store.load_all_question_coverages(
            REPO, None, (question.subject,)
        )
        if coverage.question == question
    ]
    return coverage


class _Recovery:
    """One admitted question, its stored recipe, and its replayed request."""

    def __init__(self, request, op, structural, evidence, store):
        self.continuations = ContinuationStore()
        first = op(
            request,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=self.continuations,
        )
        assert isinstance(first, PendingInterpretation), type(first)
        self.question = first.request.question
        answer = _submit(
            m.SemanticInterpretationResult(question_decision=_pending_decision()),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=self.continuations,
            continuation=first.continuation,
        )
        self.answer = answer
        self.coverage = _stored_question(store, self.question)
        self.recovery = self.coverage.recovery
        assert self.recovery is not None, "admitted question lost its recipe"
        self.request = _replayed_request(self.recovery)


def _replayed_request(recovery: m.QuestionRecovery):
    """What a client does with the recipe: re-run the originating request."""
    if isinstance(recovery, m.ExplainReplay):
        return ops.SemanticExplainRequest(
            repository_id=REPO,
            target=recovery.target,
            bounds=recovery.bounds,
            establish_baseline=recovery.establish_baseline,
            question_selection=recovery.question_selection,
        )
    if isinstance(recovery, m.ImpactReplay):
        change = recovery.proposed_change
        return ops.SemanticImpactRequest(
            repository_id=REPO,
            target=recovery.target,
            change_kind=change.change_kind,
            change_description=change.change_description,
            affected_assertions=change.affected_assertions,
            bounds=recovery.bounds,
            question_selection=recovery.question_selection,
        )
    if isinstance(recovery, m.TraceReplay):
        return ops.SemanticTraceRequest(
            repository_id=REPO,
            target=recovery.target,
            direction=recovery.direction,
            relationship_filter=recovery.relationship_filter,
            boundary_only=recovery.boundary_only,
            bounds=recovery.bounds,
            question_selection=recovery.question_selection,
        )
    return ops.SemanticAuthorityRequest(
        repository_id=REPO,
        target=recovery.target,
        bounds=recovery.bounds,
        question_selection=recovery.question_selection,
    )


class RoundTripTest(unittest.TestCase):
    def _assert_recovered(self, request, op):
        structural, evidence, store = _harness()[:3]
        try:
            admitted = _Recovery(request, op, structural, evidence, store)
            # The continuation is gone: a new store has no live records.
            replayed = op(
                admitted.request,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(replayed, PendingInterpretation)
            self.assertEqual(replayed.request.question, admitted.question)
            self.assertEqual(
                replayed.request.question.question_slice,
                admitted.question.question_slice,
            )
            return admitted, store
        except BaseException:
            store.close()
            raise

    def test_explain_round_trip(self):
        admitted, store = self._assert_recovered(
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=SELECTOR,
                bounds=_bounds(),
            ),
            ops.explain,
        )
        try:
            self.assertIsInstance(admitted.recovery, m.ExplainReplay)
        finally:
            store.close()

    def test_impact_round_trip_reproduces_the_slice(self):
        selection = m.SemanticQuestionSelection(
            question_slice="material-effect",
            materiality_basis="impact recovery test",
            question_anchors=(),
        )
        structural, evidence, store = _harness()[:3]
        try:
            admitted = _Recovery(
                ops.SemanticImpactRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    change_kind=m.ChangeKind.BEHAVIOR,
                    change_description="swap helper",
                    bounds=_bounds(),
                    question_selection=selection,
                ),
                ops.impact,
                structural,
                evidence,
                store,
            )
            self.assertIsInstance(admitted.recovery, m.ImpactReplay)
            self.assertEqual(admitted.recovery.question_selection, selection)
            self.assertEqual(
                effective_impact_slice(
                    selection.question_slice,
                    m.ChangeKind.BEHAVIOR,
                    "swap helper",
                    (),
                ),
                admitted.question.question_slice,
            )
            # Replaying recognizes the persisted identity and does not create
            # a second question for the same subject: the stored slice stays
            # the only impact question on that subject.
            continuations = ContinuationStore()
            current = ops.impact(
                admitted.request,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            for _ in range(5):
                if not isinstance(current, PendingInterpretation):
                    break
                current = _submit(
                    m.SemanticInterpretationResult(
                        question_decision=_pending_decision()
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                    continuation=current.continuation,
                )
            slices = {
                coverage.question.question_slice
                for coverage in store.load_all_question_coverages(
                    REPO, None, (SUBJECT,)
                )
                if coverage.question is not None
            }
            self.assertEqual(slices, {admitted.question.question_slice})
        finally:
            store.close()

    def test_trace_round_trip(self):
        admitted, store = self._assert_recovered(
            ops.SemanticTraceRequest(
                repository_id=REPO,
                target=SELECTOR,
                direction=StructuralDirection.BOTH,
                relationship_filter=(),
                boundary_only=False,
                bounds=_bounds(),
            ),
            ops.trace,
        )
        try:
            self.assertIsInstance(admitted.recovery, m.TraceReplay)
            self.assertEqual(admitted.recovery.relationship_filter, ())
        finally:
            store.close()

    def test_authority_round_trip(self):
        admitted, store = self._assert_recovered(
            ops.SemanticAuthorityRequest(
                repository_id=REPO,
                target=SELECTOR,
                bounds=_bounds(),
            ),
            ops.authority,
        )
        try:
            self.assertIsInstance(admitted.recovery, m.AuthorityReplay)
        finally:
            store.close()

    def test_answer_view_carries_the_recipe(self):
        structural, evidence, store = _harness()[:3]
        try:
            admitted = _Recovery(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
            )
            self.assertIsInstance(admitted.answer, m.SemanticAnswer)
            views = {
                view.question: view
                for view in admitted.answer.content.question_coverage
            }
            self.assertEqual(views[admitted.question].recovery, admitted.recovery)
        finally:
            store.close()


class NoOriginRoundTripTest(unittest.TestCase):
    def test_agent_proposed_question_recovers_through_refresh(self):
        structural, evidence, store = _harness()[:3]
        try:
            proposed = proposed_question(
                m.SemanticQuestionScope(
                    scope_root=SUBJECT,
                    subject=SUBJECT,
                    question_class=m.SemanticQuestionClass.CQ_06,
                    question_slice="agent-proposed-governance",
                    materiality_basis="agent nominated this question",
                ),
                m.SemanticQuestionDisposition.PENDING,
                basis="agent nomination",
            )
            continuations = ContinuationStore()
            first = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(first, PendingInterpretation)
            _submit(
                m.SemanticInterpretationResult(
                    question_decision=_pending_decision(),
                    proposed_questions=(proposed,),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                continuation=first.continuation,
            )
            stored = _stored_question(store, proposed.question)
            self.assertIsNone(stored.recovery)

            # A refresh chain binds the subject's persisted questions one at
            # a time; the proposed question is among them and is re-bound
            # under its stored identity.
            continuations = ContinuationStore()
            current = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(exact_subject_id=SUBJECT),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            bound = []
            for _ in range(5):
                if not isinstance(current, PendingInterpretation):
                    break
                bound.append(current.request.question)
                current = _submit(
                    m.SemanticInterpretationResult(
                        question_decision=_pending_decision()
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                    continuation=current.continuation,
                )
            self.assertIn(proposed.question, bound)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
