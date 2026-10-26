"""Addendum E acceptance: deterministic target admission.

A target is one area. Admission computes membership from the manifest, writes
one service-owned CQ-01 seed when the area has no current question, and returns
a question unit. No unit binds the inventory for a model to account for, and an
``ANSWERED`` decision must assert something.
"""

import unittest

from span import service as ops
from span.core import model as m
from span.core.validation import InterpretationUnitRejected
from span.ports.interpretation import PendingInterpretation
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.structural.memory import (
    InMemorySubject,
)

from functools import partial as _partial

from tests.support.factories import query_bounds, semantic_harness

REPO = "e13h-oracle"
FILES = {
    "billing_a1.py": "BILLING_A1 = 1\n",
    "billing_a2.py": "BILLING_A2 = 2\n",
    "shipping_b.py": "import billing_a1\nSHIP = billing_a1.BILLING_A1\n",
    "vendor_c.py": "THIRD_PARTY = True\n",
    "config_d.py": "# config, no components\n",
    "legacy_e.py": "LEGACY = 0\n",
}

_HARNESS_SUBJECTS = tuple(
    InMemorySubject(p, m.SubjectKind.COMPONENT, p.split(".")[0].split("_")[0])
    for p in FILES
)
_harness = _partial(semantic_harness, REPO, FILES, subjects=_HARNESS_SUBJECTS)
OBJECTIVE = "Establish the billing and shipping area."


_bounds = query_bounds


def _scope():
    return m.EvidenceScope(paths=tuple(sorted(FILES)), evidence_refs=())


def _target_id(objective=OBJECTIVE):
    scope, canonical_objective = m.canonicalize_target_scope(REPO, _scope(), objective)
    return m.derive_target_id(REPO, scope, canonical_objective)


def _admit(structural, evidence, store, continuations, objective=OBJECTIVE):
    return ops.initialize_target(
        ops.SemanticInitializeTargetRequest(
            repository_id=REPO,
            target=_scope(),
            objective=objective,
            bounds=_bounds(),
        ),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        authority_seeds=(),
    )


def _association(store, objective=OBJECTIVE):
    assoc = store.load_target_association(REPO, _target_id(objective))
    assert assoc is not None
    return assoc


def _area_locator():
    return "."


class DeterministicAdmissionTest(unittest.TestCase):
    def test_admission_assigns_every_member_to_the_scope_area(self):
        structural, evidence, store = _harness()
        try:
            pending = _admit(structural, evidence, store, ContinuationStore())
            self.assertIsInstance(pending, PendingInterpretation)
            assoc = _association(store)
            self.assertEqual(
                [subject.canonical_locator for subject in assoc.area_subjects],
                [_area_locator()],
            )
            self.assertEqual(len(assoc.inventory_accounting), len(FILES))
            area = assoc.area_subjects[0]
            for account in assoc.inventory_accounting:
                self.assertEqual(account.assigned_area_subjects, (area,))
        finally:
            store.close()

    def test_first_admission_asks_exactly_one_service_owned_question(self):
        structural, evidence, store = _harness()
        try:
            pending = _admit(structural, evidence, store, ContinuationStore())
            question = pending.request.question
            assert question is not None
            self.assertIs(question.question_class, m.SemanticQuestionClass.CQ_01)
            self.assertEqual(question.scope_root, pending.request.question.scope_root)
            self.assertEqual(
                question.materiality_basis, "service-owned first-admission target seed"
            )
            assoc = _association(store)
            self.assertEqual(assoc.target_questions, (question,))
            coverages = store.load_all_question_coverages(
                REPO, question.scope_root, (question.scope_root,)
            )
            seeded = [cov for cov in coverages if cov.question == question]
            self.assertEqual(len(seeded), 1)
            self.assertIs(seeded[0].disposition, m.SemanticQuestionDisposition.PENDING)
        finally:
            store.close()

    def test_restart_resumes_the_same_question(self):
        structural, evidence, store = _harness()
        try:
            first = _admit(structural, evidence, store, ContinuationStore())
            second = _admit(structural, evidence, store, ContinuationStore())
            assert first.request.question is not None
            self.assertEqual(second.request.question, first.request.question)
            coverages = store.load_all_question_coverages(
                REPO,
                first.request.question.scope_root,
                (first.request.question.scope_root,),
            )
            seeded = [
                cov for cov in coverages if cov.question == first.request.question
            ]
            self.assertEqual(len(seeded), 1, "restart must not duplicate the seed")
        finally:
            store.close()

    def test_a_second_campaign_reuses_the_persisted_area_question(self):
        structural, evidence, store = _harness()
        try:
            first = _admit(structural, evidence, store, ContinuationStore())
            second = _admit(
                structural, evidence, store, ContinuationStore(), "second objective"
            )
            assert first.request.question is not None
            self.assertEqual(second.request.question, first.request.question)
            assoc = _association(store, "second objective")
            self.assertEqual(assoc.target_questions, (first.request.question,))
            self.assertEqual(len(assoc.inventory_accounting), len(FILES))
        finally:
            store.close()

    def test_status_reports_the_admitted_members(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _admit(structural, evidence, store, continuations)
            answer = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=pending.request.target_id,
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            assert isinstance(answer, m.SemanticAnswer)
            assert isinstance(answer.content, m.StatusContent)
            self.assertEqual(answer.content.target_total_count, len(FILES))
            self.assertIs(
                answer.content.target_disposition,
                m.SemanticCoverageDisposition.INCOMPLETE,
            )
        finally:
            store.close()


class AssertionOnlyAnswerTest(unittest.TestCase):
    def test_answered_requires_an_assertion(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _admit(structural, evidence, store, continuations)
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(),
                        relationships=(),
                        question_decision=m.SemanticQuestionDecision(
                            disposition=m.SemanticQuestionDisposition.ANSWERED,
                            disposition_basis="nothing to say",
                        ),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
            self.assertIn("ANSWERED requires at least one claim", str(ctx.exception))
        finally:
            store.close()

    def test_not_applicable_is_the_no_assertion_terminal(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _admit(structural, evidence, store, continuations)
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(),
                    relationships=(),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.NOT_APPLICABLE,
                        disposition_basis="the area carries no assertion",
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            question = pending.request.question
            assert question is not None
            coverages = store.load_all_question_coverages(
                REPO, question.scope_root, (question.scope_root,)
            )
            settled = [cov for cov in coverages if cov.question == question]
            self.assertEqual(len(settled), 1)
            self.assertIs(
                settled[0].disposition,
                m.SemanticQuestionDisposition.NOT_APPLICABLE,
            )
        finally:
            store.close()


class LegacyAnchorlessSignalTest(unittest.TestCase):
    """A persisted question whose subject never resolved stays visible.

    Legacy associations may still carry a question anchored to a subject that
    no structural or evidence source can resolve. ``status`` must name it as an
    unresolved requirement instead of silently dropping it.
    """

    def test_anchorless_legacy_signals_in_status(self):
        structural, evidence, store = _harness()
        try:
            from span.service.discovery import enumerate_target_inventory

            scope, obj = m.canonicalize_target_scope(REPO, _scope(), OBJECTIVE)
            tid = m.derive_target_id(REPO, scope, obj)
            inv_items = enumerate_target_inventory(
                REPO, scope, evidence=evidence, bounds=_bounds()
            )
            area = m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.OTHER,
                canonical_locator=_area_locator(),
            )
            ghost = m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.OTHER,
                canonical_locator="ghost.py",
            )
            assoc = m.TargetAssociation(
                target_id=tid,
                repository_id=REPO,
                target_scope=scope,
                objective=obj,
                area_subjects=(area,),
                target_questions=(
                    m.SemanticQuestionScope(
                        scope_root=area,
                        subject=ghost,
                        question_class=m.SemanticQuestionClass.CQ_01,
                        question_slice="ghost purpose",
                        materiality_basis="legacy admission",
                    ),
                ),
                inventory_accounting=tuple(
                    m.TargetInventoryAccount(
                        evidence_ref=item.evidence_ref,
                        assigned_area_subjects=(area,),
                    )
                    for item in inv_items
                ),
                inventory_fingerprint=m.target_inventory_fingerprint(tuple(inv_items)),
                observed_repository_state_fingerprint="test",
            )
            store.write_index_batch(m.CanonicalIndexBatch(target_associations=(assoc,)))
            answer = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO, target=tid, bounds=_bounds()
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
                authority_seeds=(),
            )
            assert isinstance(answer, m.SemanticAnswer)
            assert isinstance(answer.content, m.StatusContent)
            self.assertIs(
                answer.content.target_disposition,
                m.SemanticCoverageDisposition.INCOMPLETE,
            )
            named = [
                requirement
                for requirement in answer.resolution_requirements
                if requirement.subject_or_claim == ghost
            ]
            self.assertTrue(named)
            self.assertIn("CandidateSubject", named[0].description)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
