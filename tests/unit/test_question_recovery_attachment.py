"""0.8.3 D1: the per-origin recovery attachment rule, row by row."""

from __future__ import annotations

import unittest

from span import service as ops
from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.ports.structural import StructuralDirection
from span.service.interpretation.coverage import _first_admission_coverage
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.agent_exchange import (
    REPO,
    _bounds,
    _exchange,
    _harness,
    _sid,
)
from tests.support.factories import proposed_question

SUBJECT = _sid("src/flow.py")
SELECTOR = m.SubjectSelector(None, "src/flow.py", (), None)


def _recoveries(store, subject):
    return [
        coverage.recovery
        for coverage in store.load_all_question_coverages(REPO, None, (subject,))
        if coverage.recovery is not None
    ]


def _pending_decision() -> m.SemanticQuestionDecision:
    return m.SemanticQuestionDecision(
        disposition=m.SemanticQuestionDisposition.PENDING,
        disposition_basis="deliberate deferral in this unit",
    )


def _drive(op, request, build_result):
    """Drive one operation to its first committed answer."""
    structural, evidence, store = _harness()[:3]
    try:
        continuations = ContinuationStore()
        current = op(
            request,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
        if not isinstance(current, PendingInterpretation):
            return current, store
        return (
            ops.submit_interpretation(
                current.continuation,
                build_result(current.request),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            ),
            store,
        )
    except BaseException:
        store.close()
        raise


class AdmittedOperationTest(unittest.TestCase):
    """Row 1: a bound question admitted by a suspending operation."""

    def test_explain_attaches_resolved_recipe(self):
        current, store = _drive(
            ops.explain,
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=SELECTOR,
                bounds=_bounds(),
                establish_baseline=True,
            ),
            lambda request: m.SemanticInterpretationResult(
                question_decision=_pending_decision()
            ),
        )
        try:
            (recovery,) = _recoveries(store, SUBJECT)
            self.assertIsInstance(recovery, m.ExplainReplay)
            self.assertEqual(recovery.target.exact_subject_id, SUBJECT)
            self.assertEqual(recovery.bounds, _bounds())
            self.assertTrue(recovery.establish_baseline)
        finally:
            store.close()

    def test_impact_attaches_proposed_change(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticImpactRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    change_kind=m.ChangeKind.BEHAVIOR,
                    change_description="swap helper",
                    bounds=_bounds(),
                ),
                ops.impact,
                structural,
                evidence,
                store,
                agent,
            )
            (recovery,) = _recoveries(store, SUBJECT)
            self.assertIsInstance(recovery, m.ImpactReplay)
            self.assertEqual(recovery.target.exact_subject_id, SUBJECT)
            self.assertEqual(recovery.bounds, _bounds())
            self.assertIs(recovery.proposed_change.change_kind, m.ChangeKind.BEHAVIOR)
            self.assertEqual(recovery.proposed_change.change_description, "swap helper")
        finally:
            store.close()

    def test_trace_attaches_traversal_inputs(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticTraceRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    direction=StructuralDirection.UPSTREAM,
                    relationship_filter=None,
                    boundary_only=True,
                    bounds=_bounds(),
                ),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            recoveries = _recoveries(store, SUBJECT)
            self.assertTrue(recoveries)
            for recovery in recoveries:
                self.assertIsInstance(recovery, m.TraceReplay)
                self.assertIs(recovery.direction, StructuralDirection.UPSTREAM)
                self.assertIsNone(recovery.relationship_filter)
                self.assertTrue(recovery.boundary_only)
        finally:
            store.close()

    def test_trace_distinguishes_empty_filter_from_no_filter(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticTraceRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    direction=StructuralDirection.BOTH,
                    relationship_filter=(),
                    bounds=_bounds(),
                ),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            recoveries = _recoveries(store, SUBJECT)
            self.assertTrue(recoveries)
            for recovery in recoveries:
                self.assertIsInstance(recovery, m.TraceReplay)
                self.assertEqual(recovery.relationship_filter, ())
        finally:
            store.close()

    def test_authority_attaches_recipe(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticAuthorityRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    bounds=_bounds(),
                ),
                ops.authority,
                structural,
                evidence,
                store,
                agent,
            )
            (recovery,) = _recoveries(store, SUBJECT)
            self.assertIsInstance(recovery, m.AuthorityReplay)
            self.assertEqual(recovery.target.exact_subject_id, SUBJECT)
        finally:
            store.close()


class ExplicitDecisionTest(unittest.TestCase):
    """Rows 1 and 2 with an explicit decision and a synthesized PENDING."""

    def test_explicit_pending_decision_attaches(self):
        answer, store = _drive(
            ops.explain,
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=SELECTOR,
                bounds=_bounds(),
            ),
            lambda request: m.SemanticInterpretationResult(
                question_decision=_pending_decision()
            ),
        )
        try:
            self.assertIsInstance(answer, m.SemanticAnswer)
            (recovery,) = _recoveries(store, SUBJECT)
            self.assertIsInstance(recovery, m.ExplainReplay)
        finally:
            store.close()

    def test_synthesized_pending_attaches(self):
        answer, store = _drive(
            ops.explain,
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=SELECTOR,
                bounds=_bounds(),
            ),
            lambda request: m.SemanticInterpretationResult(),
        )
        try:
            self.assertIsInstance(answer, m.SemanticAnswer)
            (recovery,) = _recoveries(store, SUBJECT)
            self.assertIsInstance(recovery, m.ExplainReplay)
        finally:
            store.close()


class RewriteTest(unittest.TestCase):
    """Row 3: an existing question preserves its stored recipe."""

    def test_refresh_rewrite_preserves_recipe(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=SELECTOR,
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            (before,) = _recoveries(store, SUBJECT)
            self.assertIsInstance(before, m.ExplainReplay)

            continuations = ContinuationStore()
            current = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(exact_subject_id=SUBJECT),
                    bounds=_bounds(),
                    stale_only=False,
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(current, PendingInterpretation)
            answer = ops.submit_interpretation(
                current.continuation,
                m.SemanticInterpretationResult(question_decision=_pending_decision()),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            (after,) = _recoveries(store, SUBJECT)
            self.assertEqual(after, before)
        finally:
            store.close()


class NoOriginTest(unittest.TestCase):
    """Rows 4 and 5: agent proposals and service seeds carry no recipe."""

    def test_agent_proposed_question_has_no_recipe(self):
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
        answer, store = _drive(
            ops.explain,
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=SELECTOR,
                bounds=_bounds(),
            ),
            lambda request: m.SemanticInterpretationResult(
                question_decision=_pending_decision(),
                proposed_questions=(proposed,),
            ),
        )
        try:
            self.assertIsInstance(answer, m.SemanticAnswer)
            coverages = store.load_all_question_coverages(REPO, None, (SUBJECT,))
            proposed_rows = [
                coverage
                for coverage in coverages
                if coverage.question is not None
                and coverage.question.question_slice == "agent-proposed-governance"
            ]
            self.assertEqual(len(proposed_rows), 1)
            self.assertIsNone(proposed_rows[0].recovery)
        finally:
            store.close()

    def test_service_seed_has_no_recipe(self):
        seed = _first_admission_coverage(SUBJECT, ())
        self.assertIsNone(seed.recovery)


class DecodeTest(unittest.TestCase):
    """Row 6: a row written before the change still decodes."""

    def test_row_without_recovery_decodes(self):
        replay = m.ExplainReplay(
            target=m.SubjectSelector(exact_subject_id=SUBJECT),
            bounds=_bounds(),
        )
        coverage = m.InterpretationCoverage(
            subjects=(SUBJECT,),
            question_slice="legacy",
            recovery=replay,
        )
        encoded = m.to_canonical(coverage)
        self.assertIsNotNone(
            m.from_canonical(m.InterpretationCoverage, encoded).recovery
        )
        legacy = {key: value for key, value in encoded.items() if key != "recovery"}
        decoded = m.from_canonical(m.InterpretationCoverage, legacy)
        self.assertIsNone(decoded.recovery)


if __name__ == "__main__":
    unittest.main()
