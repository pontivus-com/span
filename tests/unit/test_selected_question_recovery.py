"""Selected-question recovery after a lost interpretation continuation."""

import unittest

from span import service as ops
from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.ports.structural import StructuralDirection
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.structural.memory import InMemorySubject
from tests.support.factories import query_bounds, semantic_harness

FILES = {"src/main.py": "VALUE = 1\n"}
_BOUNDS = query_bounds()
_TARGET = m.SubjectSelector(None, "src/main.py", (), None)


def _selection(label: str, basis: str | None = None) -> m.SemanticQuestionSelection:
    return m.SemanticQuestionSelection(
        question_slice=f"selected-{label}", materiality_basis=basis
    )


def _pending_result() -> m.SemanticInterpretationResult:
    return m.SemanticInterpretationResult(
        question_decision=m.SemanticQuestionDecision(
            disposition=m.SemanticQuestionDisposition.PENDING
        )
    )


class SelectedQuestionRecoveryTest(unittest.TestCase):
    def _selected_harness(self):
        return semantic_harness(
            "repo-1",
            FILES,
            subjects=(InMemorySubject("src/main.py", m.SubjectKind.COMPONENT, "main"),),
        )

    def _request(self, operation: str, *, basis: str | None = None):
        selection = _selection(operation, basis)
        if operation == "explain":
            return ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=_TARGET,
                bounds=_BOUNDS,
                question_selection=selection,
            )
        if operation == "authority":
            return ops.SemanticAuthorityRequest(
                repository_id="repo-1",
                target=_TARGET,
                bounds=_BOUNDS,
                question_selection=selection,
            )
        if operation == "impact":
            return ops.SemanticImpactRequest(
                repository_id="repo-1",
                target=_TARGET,
                change_kind=m.ChangeKind.BEHAVIOR,
                change_description="change selected behavior",
                bounds=_BOUNDS,
                question_selection=selection,
            )
        if operation == "trace":
            return ops.SemanticTraceRequest(
                repository_id="repo-1",
                target=_TARGET,
                direction=StructuralDirection.BOTH,
                bounds=_BOUNDS,
                question_selection=selection,
            )
        raise AssertionError(operation)

    def _call(self, operation: str, request, structural, evidence, store, conts):
        return getattr(ops, operation)(
            request,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=conts,
        )

    def test_lost_continuation_reissues_selected_question_for_all_paths(self):
        for operation in ("explain", "authority", "impact", "trace"):
            with self.subTest(operation=operation):
                structural, evidence, store = self._selected_harness()
                try:
                    request = self._request(operation)
                    first_conts = ContinuationStore()
                    first = self._call(
                        operation,
                        request,
                        structural,
                        evidence,
                        store,
                        first_conts,
                    )
                    self.assertIsInstance(first, PendingInterpretation)
                    question = first.request.question
                    self.assertIsNotNone(question)

                    ops.submit_interpretation(
                        first.continuation,
                        _pending_result(),
                        structural=structural,
                        evidence=evidence,
                        store=store,
                        continuations=first_conts,
                    )

                    second = self._call(
                        operation,
                        request,
                        structural,
                        evidence,
                        store,
                        ContinuationStore(),
                    )
                    self.assertIsInstance(second, PendingInterpretation)
                    self.assertEqual(second.request.question, question)
                finally:
                    store.close()

    def test_live_selected_question_is_not_duplicated(self):
        for operation in ("explain", "authority", "impact", "trace"):
            with self.subTest(operation=operation):
                structural, evidence, store = self._selected_harness()
                try:
                    request = self._request(operation)
                    continuations = ContinuationStore()
                    first = self._call(
                        operation,
                        request,
                        structural,
                        evidence,
                        store,
                        continuations,
                    )
                    self.assertIsInstance(first, PendingInterpretation)
                    second = self._call(
                        operation,
                        request,
                        structural,
                        evidence,
                        store,
                        continuations,
                    )
                    self.assertIsInstance(second, m.SemanticAnswer)
                    self.assertEqual(len(continuations), 1)
                    self.assertTrue(
                        any(
                            f"live {operation}" in requirement.description
                            for requirement in second.resolution_requirements
                        )
                    )
                finally:
                    store.close()

    def test_non_pending_selected_question_is_answered_across_basis_change(self):
        structural, evidence, store = self._selected_harness()
        try:
            sid = m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator="src/main.py",
            )
            question = m.SemanticQuestionScope(
                scope_root=sid,
                subject=sid,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="selected-answer",
                materiality_basis="basis-A",
            )
            coverage = m.InterpretationCoverage(
                subjects=(sid,),
                question_slice="selected-answer",
                question=question,
                disposition=m.SemanticQuestionDisposition.NOT_APPLICABLE,
                disposition_basis="test",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "main", None),),
                    coverage=(coverage,),
                )
            )
            request = ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=_TARGET,
                bounds=_BOUNDS,
                question_selection=_selection("answer", "basis-B"),
            )
            answer = ops.explain(
                request,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
        finally:
            store.close()

    def test_live_guard_matches_identity_across_basis_change(self):
        structural, evidence, store = self._selected_harness()
        try:
            continuations = ContinuationStore()
            first = ops.explain(
                self._request("explain", basis="basis-A"),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(first, PendingInterpretation)
            second = ops.explain(
                self._request("explain", basis="basis-B"),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()

    def test_refresh_resumes_recorded_pending_question(self):
        structural, evidence, store = self._selected_harness()
        try:
            continuations = ContinuationStore()
            first = ops.explain(
                self._request("explain"),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(first, PendingInterpretation)
            ops.submit_interpretation(
                first.continuation,
                _pending_result(),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            refreshed = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=_TARGET,
                    bounds=_BOUNDS,
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(refreshed, PendingInterpretation)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
