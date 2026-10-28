"""0.8.3 D3: status names the recovery action a persisted question carries."""

from __future__ import annotations

import unittest

from span.core import model as m
from span.service.operations.status.requirements import (
    _pending_exchange_requirements,
)
from span.service.questions import effective_question_view
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.agent_exchange import REPO, _bounds, _sid

SUBJECT = _sid("src/flow.py")
SELECTOR = m.SubjectSelector(exact_subject_id=SUBJECT)


def _question() -> m.SemanticQuestionScope:
    return m.SemanticQuestionScope(
        scope_root=SUBJECT,
        subject=SUBJECT,
        question_class=m.SemanticQuestionClass.CQ_01,
        question_slice="purpose",
        materiality_basis="status recovery test",
    )


def _view(
    recovery: m.QuestionRecovery | None = None,
) -> m.SemanticQuestionCoverageView:
    return m.SemanticQuestionCoverageView(
        question=_question(),
        recorded_disposition=m.SemanticQuestionDisposition.PENDING,
        effective_disposition=m.SemanticQuestionDisposition.PENDING,
        freshness=m.Freshness(m.FreshnessState.CURRENT, reason="test"),
        recovery=recovery,
    )


def _requirement(view: m.SemanticQuestionCoverageView, **kwargs) -> str:
    (requirement,) = _pending_exchange_requirements(
        REPO,
        (view,),
        ContinuationStore(),
        **kwargs,
    )
    return requirement.description


class RecipeInstructionTest(unittest.TestCase):
    def test_explain_recipe_names_operation_and_target(self):
        description = _requirement(
            _view(
                m.ExplainReplay(
                    target=SELECTOR,
                    bounds=_bounds(),
                    establish_baseline=True,
                )
            )
        )
        self.assertIn("re-run explain", description)
        self.assertIn("src/flow.py", description)
        self.assertIn("establish_baseline=true", description)
        self.assertNotIn("refresh", description)

    def test_impact_recipe_names_the_proposal(self):
        description = _requirement(
            _view(
                m.ImpactReplay(
                    target=SELECTOR,
                    proposed_change=m.ProposedChange(
                        change_kind=m.ChangeKind.BEHAVIOR,
                        change_description="swap helper",
                    ),
                    bounds=_bounds(),
                )
            )
        )
        self.assertIn("re-run impact", description)
        self.assertIn("change_kind=BEHAVIOR", description)
        self.assertIn("swap helper", description)

    def test_trace_recipe_names_traversal(self):
        description = _requirement(
            _view(
                m.TraceReplay(
                    target=SELECTOR,
                    bounds=_bounds(),
                    direction=m.StructuralDirection.UPSTREAM,
                    relationship_filter=(),
                    boundary_only=True,
                )
            )
        )
        self.assertIn("re-run trace", description)
        self.assertIn("direction=UPSTREAM", description)
        self.assertIn("relationship_filter=NONE", description)
        self.assertIn("boundary_only=true", description)

    def test_authority_recipe_names_authority(self):
        description = _requirement(
            _view(
                m.AuthorityReplay(
                    target=SELECTOR,
                    bounds=_bounds(),
                )
            )
        )
        self.assertIn("re-run authority", description)
        self.assertIn("src/flow.py", description)


class NoRecipeInstructionTest(unittest.TestCase):
    def test_no_recipe_recovers_through_refresh(self):
        description = _requirement(_view())
        self.assertIn("refresh", description)
        self.assertIn("src/flow.py", description)
        self.assertNotIn("re-run explain", description)

    def test_durable_origin_text_is_kept(self):
        description = _requirement(_view(), recovery_operation="initialize_target")
        self.assertIn("initialize_target", description)
        self.assertIn("no live continuation", description)


class ViewProjectionTest(unittest.TestCase):
    def test_view_carries_recovery(self):
        recovery = m.AuthorityReplay(target=SELECTOR, bounds=_bounds())
        coverage = m.InterpretationCoverage(
            subjects=(SUBJECT,),
            question_slice="purpose",
            question=_question(),
            disposition=m.SemanticQuestionDisposition.PENDING,
            disposition_basis="pending",
            recovery=recovery,
        )
        view = effective_question_view(coverage)
        self.assertEqual(view.recovery, recovery)


if __name__ == "__main__":
    unittest.main()
