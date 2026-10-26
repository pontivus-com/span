"""Branch characterization for the submission pipeline (plan §5, E8).

``_materialize_unit`` is the largest function in the product. Before it is
rewritten into stages (W3), each decision outcome it can produce is pinned
here: the same input must still produce the same observable result after the
rewrite. Cases are deliberately table-driven so a branch cannot disappear
silently.
"""

from __future__ import annotations

import unittest

from span import service as ops
from span.core import model as m
from span.core.validation import InterpretationUnitRejected
from span.ports.interpretation import PendingInterpretation
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.structural.memory import (
    InMemorySubject,
    fingerprint_content,
)

from tests.support.factories import query_bounds

from functools import partial as _partial
from tests.support.factories import subject_id

from tests.support.factories import evidence_ref

from tests.support.factories import semantic_harness

REPO = "submission-characterization"

FILES = {
    "README.md": "# submission-characterization\n\nRoutes commands.\n",
    "src/router.py": "ROUTE = 1\n",
    "src/sink.py": "SINK = 1\n",
}


_bounds = query_bounds


_sid = _partial(subject_id, repository_id=REPO)


_ref = _partial(evidence_ref, repository_id=REPO, files=FILES)


_harness = _partial(
    semantic_harness,
    REPO,
    FILES,
    subjects=(
        InMemorySubject("src/router.py", m.SubjectKind.COMPONENT, "router"),
        InMemorySubject("src/sink.py", m.SubjectKind.COMPONENT, "sink"),
    ),
)


def _pending(structural, evidence, store, continuations):
    result = ops.explain(
        ops.SemanticExplainRequest(
            repository_id=REPO,
            target=m.SubjectSelector(name_or_locator="src/router.py"),
            bounds=_bounds(),
        ),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    assert isinstance(result, PendingInterpretation), result
    return result


def _purpose_claim(subject: m.SubjectId | None = None) -> m.CandidateSemanticClaim:
    return m.CandidateSemanticClaim(
        candidate_key="purpose",
        subject=subject or _sid("src/router.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("Routes commands", ()),
        evidence=(_ref("README.md"),),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the routing purpose",
        ),
    )


def _question(
    slice_text: str,
    *,
    scope_root: m.SubjectId | None = None,
    subject: m.SubjectId | None = None,
    question_class: m.SemanticQuestionClass = m.SemanticQuestionClass.CQ_01,
) -> m.SemanticQuestionScope:
    root = scope_root or _sid("src/router.py")
    return m.SemanticQuestionScope(
        scope_root=root,
        subject=subject or root,
        question_class=question_class,
        question_slice=slice_text,
        materiality_basis="characterization case",
    )


class SubmissionCharacterizationTest(unittest.TestCase):
    """One case per decision outcome of the submission pipeline."""

    def _submit(self, result: m.SemanticInterpretationResult):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            return ops.submit_interpretation(
                pending.continuation,
                result,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
        finally:
            store.close()

    def test_accepted_answered_with_assertion(self):
        answer = self._submit(
            m.SemanticInterpretationResult(
                claims=(_purpose_claim(),),
                question_decision=m.SemanticQuestionDecision(
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    disposition_basis="examined",
                ),
            )
        )
        self.assertTrue(isinstance(answer, (m.SemanticAnswer, PendingInterpretation)))

    def test_rejected_answered_without_assertion(self):
        with self.assertRaises(InterpretationUnitRejected) as ctx:
            self._submit(
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="examined",
                    ),
                )
            )
        self.assertIn("ANSWERED requires at least one claim", str(ctx.exception))

    def test_accepted_not_applicable_with_basis(self):
        answer = self._submit(
            m.SemanticInterpretationResult(
                question_decision=m.SemanticQuestionDecision(
                    disposition=m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    disposition_basis="no assertion is warranted here",
                ),
            )
        )
        self.assertTrue(isinstance(answer, (m.SemanticAnswer, PendingInterpretation)))

    def test_accepted_open_with_requirement(self):
        answer = self._submit(
            m.SemanticInterpretationResult(
                question_decision=m.SemanticQuestionDecision(
                    disposition=m.SemanticQuestionDisposition.OPEN,
                    resolution_requirements=(
                        m.ResolutionRequirement(
                            kind=m.ResolutionKind.MISSING_AUTHORITY,
                            description="owner has not recorded a decision",
                        ),
                    ),
                    disposition_basis="open on purpose",
                ),
            )
        )
        self.assertTrue(isinstance(answer, (m.SemanticAnswer, PendingInterpretation)))

    def test_rejected_claim_with_unknown_evidence(self):
        bogus = m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-not-admitted"),
            repository_id=REPO,
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="src/router.py",
            revision_or_fingerprint=fingerprint_content(FILES["src/router.py"]),
        )
        claim = _purpose_claim()
        claim = m.CandidateSemanticClaim(
            candidate_key=claim.candidate_key,
            subject=claim.subject,
            kind=claim.kind,
            assertion_nature=claim.assertion_nature,
            value=claim.value,
            evidence=(bogus,),
            basis=claim.basis,
        )
        with self.assertRaises(InterpretationUnitRejected):
            self._submit(
                m.SemanticInterpretationResult(
                    claims=(claim,),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="examined",
                    ),
                )
            )

    def test_rejected_claim_on_foreign_subject(self):
        with self.assertRaises(InterpretationUnitRejected):
            self._submit(
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(_sid("src/ghost.py")),),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="examined",
                    ),
                )
            )

    def test_rejected_bound_question_repeated_as_proposed(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            duplicate = pending.request.question
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),),
                        question_decision=m.SemanticQuestionDecision(
                            disposition=m.SemanticQuestionDisposition.ANSWERED,
                            disposition_basis="examined",
                        ),
                        proposed_questions=(
                            m.ProposedSemanticQuestion(
                                duplicate,
                                m.SemanticQuestionDecision(
                                    disposition=m.SemanticQuestionDisposition.PENDING,
                                    disposition_basis="duplicate",
                                ),
                            ),
                        ),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
            self.assertIn(
                "must be answered through question_decision", str(ctx.exception)
            )
        finally:
            store.close()

    def test_rejected_proposed_question_with_foreign_scope_root(self):
        with self.assertRaises(InterpretationUnitRejected):
            self._submit(
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="examined",
                    ),
                    proposed_questions=(
                        m.ProposedSemanticQuestion(
                            _question(
                                "ghost scope",
                                scope_root=_sid("src/ghost.py"),
                            ),
                            m.SemanticQuestionDecision(
                                disposition=m.SemanticQuestionDisposition.PENDING,
                                disposition_basis="foreign",
                            ),
                        ),
                    ),
                )
            )

    def test_rejected_withdrawal_for_unknown_claim(self):
        with self.assertRaises(InterpretationUnitRejected):
            self._submit(
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="examined",
                    ),
                    candidate_withdrawals=(
                        m.CandidateSemanticWithdrawal(
                            target=m.ClaimRef(m.ClaimId("claim-not-persisted")),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "withdrawal of unknown claim",
                            ),
                        ),
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
