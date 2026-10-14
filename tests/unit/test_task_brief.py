"""Task-brief tests (addendum D TASK-D-01, §8)."""

import dataclasses
import unittest

from span.core import model as m
from span import service as ops
from span.service.interpretation import prepare_interpretation_task
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

REPO = "repo-1"

FILES = {
    "README.md": "# svc\n\nDoes things.\n",
    "src/main.py": "VALUE = 1\n",
}

SUBJECTS = (
    InMemorySubject("src/main.py", m.SubjectKind.COMPONENT, "main"),
)


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _sid():
    return m.SubjectId(
        repository_id=REPO, subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator="src/main.py",
    )


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


def _candidate():
    return m.CandidateSemanticClaim(
        candidate_key="purpose-main",
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("does things", ()),
        evidence=(_ref("README.md"), _ref("src/main.py")),
        candidate_authority=m.CandidateAuthority(
            binding=m.AuthorityBinding(
                evidence_ref=_ref("README.md"),
                authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                status=m.AuthorityStatus.ACCEPTED,
            ),
            support=m.AuthoritySupport(
                quoted_span="Does things",
                status_section="README.md",
                applicability_section=None,
            ),
        ),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the service purpose",
        ),
    )


def _harness():
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        SUBJECTS,
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural, evidence=evidence, store=store,
    )
    return structural, evidence, store


def _subject():
    return m.Subject(_sid(), "main", None)


class TaskBriefTest(unittest.TestCase):
    def _task(self, intent=m.SemanticIntent.EXPLAIN):
        structural, evidence, store = _harness()
        self.addCleanup(store.close)
        state = structural.repository_state(REPO)
        return prepare_interpretation_task(
            REPO, _subject(), structural=structural, evidence=evidence,
            bounds=_bounds(), state=state, operation_intent=intent,
        )

    def test_brief_carries_c04_aspects_for_class(self):
        task = self._task(m.SemanticIntent.EXPLAIN)
        self.assertIsNotNone(task.request.brief)
        self.assertEqual(
            task.request.brief.material_aspects,
            m.QUESTION_CLASS_ASPECTS[m.SemanticQuestionClass.CQ_01],
        )
        self.assertIn("Purpose", task.request.brief.material_aspects)

    def test_brief_differs_by_question_class(self):
        explain = self._task(m.SemanticIntent.EXPLAIN)
        trace = self._task(m.SemanticIntent.TRACE)
        self.assertEqual(
            trace.request.brief.material_aspects,
            m.QUESTION_CLASS_ASPECTS[m.SemanticQuestionClass.CQ_04],
        )
        self.assertNotEqual(
            explain.request.brief.material_aspects,
            trace.request.brief.material_aspects,
        )

    def test_brief_boundaries_and_rules_are_canonical(self):
        task = self._task()
        brief = task.request.brief
        self.assertIn("scope root: src/main.py", brief.scope_boundaries)
        self.assertIn("structural anchor: src/main.py", brief.scope_boundaries)
        # Rules are the canonical constants — no per-unit invention.
        # The only permitted addition is the deterministic S3.4
        # task-bound PENDING submission template in submission_rules.
        self.assertEqual(brief.open_handling, m.TASK_BRIEF_OPEN_HANDLING)
        self.assertEqual(
            brief.submission_rules[: len(m.TASK_BRIEF_SUBMISSION_RULES)],
            m.TASK_BRIEF_SUBMISSION_RULES,
        )
        self.assertTrue(
            brief.submission_rules[-1].startswith(
                "Minimal submission template (unfinished, PENDING"
            )
        )
        self.assertTrue(brief.open_handling and brief.submission_rules)

    def test_brief_exposes_the_complete_compact_quality_card(self):
        task = self._task()
        brief = task.request.brief

        self.assertIn("src/main.py", brief.objective)
        self.assertEqual(brief.material_path, m.TASK_BRIEF_MATERIAL_PATH)
        self.assertEqual(
            brief.semantic_result, m.TASK_BRIEF_SEMANTIC_RESULT
        )
        self.assertEqual(
            brief.adversarial_checks, m.TASK_BRIEF_ADVERSARIAL_CHECKS
        )
        self.assertEqual(brief.readback, m.TASK_BRIEF_READBACK)
        self.assertTrue(any("Evidence examined:" in item
                            for item in brief.evidence_authority))
        self.assertTrue(any("Governing authority:" in item
                            for item in brief.evidence_authority))
        self.assertEqual(
            task.request.analysis_obligations,
            m.SA_ANALYSIS_OBLIGATIONS,
        )

    def test_brief_points_to_locate_for_missing_evidence(self):
        brief = self._task().request.brief
        self.assertTrue(
            any(
                "locate" in item and "TARGET_MEMBERS" in item
                for item in brief.evidence_authority
            )
        )

    def test_quality_card_is_uniform_across_operation_intents(self):
        explain = self._task(m.SemanticIntent.EXPLAIN).request
        trace = self._task(m.SemanticIntent.TRACE).request

        self.assertEqual(explain.brief.objective, trace.brief.objective)
        self.assertEqual(
            explain.brief.evidence_authority,
            trace.brief.evidence_authority,
        )
        self.assertEqual(explain.brief.material_path, trace.brief.material_path)
        self.assertEqual(
            explain.brief.adversarial_checks,
            trace.brief.adversarial_checks,
        )
        self.assertEqual(explain.brief.readback, trace.brief.readback)
        self.assertEqual(
            explain.analysis_obligations,
            trace.analysis_obligations,
        )
        self.assertNotEqual(
            explain.brief.material_aspects,
            trace.brief.material_aspects,
        )

    def test_tampered_brief_changes_nothing(self):
        # Validation ignores the brief: swapping in another class's
        # aspects (the "wrong brief") neither confers validity nor
        # alters materialization. Substantive failure stays with the
        # oracles, which judge content against fixture truth.
        # Structural reason: the submitted result carrier has no brief
        # field at all, so tampering cannot reach materialization even
        # in principle.
        import dataclasses as _dc

        self.assertNotIn(
            "brief",
            [f.name for f in _dc.fields(m.SemanticInterpretationResult)],
        )
        structural, evidence, store = _harness()
        try:
            state = structural.repository_state(REPO)
            task = prepare_interpretation_task(
                REPO, _subject(), structural=structural,
                evidence=evidence, bounds=_bounds(), state=state,
            )
            wrong = dataclasses.replace(
                task.request,
                brief=dataclasses.replace(
                    task.request.brief,
                    material_aspects=m.QUESTION_CLASS_ASPECTS[
                        m.SemanticQuestionClass.CQ_07
                    ],
                ),
            )
            agent = FixtureAgent(
                {"src/main.py": FixtureCandidates((_candidate(),), ())},
                complete_questions=True,
            )
            cont = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=cont, authority_seeds=(_ref("README.md"),),
            )
            from span.ports.interpretation import PendingInterpretation
            self.assertIsInstance(pending, PendingInterpretation)
            result = agent.perform(wrong)
            answer = ops.submit_interpretation(
                pending.continuation, result, structural=structural,
                evidence=evidence, store=store, continuations=cont,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
        finally:
            store.close()

    def test_brief_is_required_no_legacy_path(self):
        # No brief-less legacy support (antipattern): omitting the
        # brief fails construction instead of silently defaulting.
        with self.assertRaises(TypeError):
            m.SemanticInterpretationRequest(
                repository_id=REPO,
                subjects=(_subject(),),
                evidence_units=(),
                structural_observations=(),
                allowed_claim_kinds=tuple(m.ClaimKind),
                allowed_relationship_kinds=tuple(m.RelationshipKind),
                identity_bindings=(_sid(),),
                bounds=_bounds(),
            )

    def test_brief_quotes_recorded_open_requirements(self):
        # F-02 slice instance: an OPEN recorded for this exact scope
        # appears quoted in the next prepared brief; scopes without
        # OPEN/PENDING carry none. Quoted, never inferred.
        from span.ports.interpretation import PendingInterpretation

        structural, evidence, store = _harness()
        try:
            cont = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/main.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence,
                store=store, continuations=cont,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            question = pending.request.question
            submitted = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        m.InterpretationCoverage(
                            subjects=(question.subject,),
                            question_slice=question.question_slice,
                            evidence_scope=m.EvidenceScope(
                                paths=(), evidence_refs=()
                            ),
                            declared_complete=False,
                            question=question,
                            disposition=(
                                m.SemanticQuestionDisposition.OPEN
                            ),
                            result_refs=(),
                            resolution_requirements=(
                                m.ResolutionRequirement(
                                    kind=(
                                        m.ResolutionKind
                                        .MISSING_SEMANTIC_COVERAGE
                                    ),
                                    subject_or_claim=_sid(),
                                    description="main purpose unexamined",
                                    supporting_context=(),
                                ),
                            ),
                            disposition_basis="scope left open",
                            question_evidence=(),
                        ),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence,
                store=store, continuations=cont,
            )
            self.assertIsInstance(submitted, m.SemanticAnswer)
            state = structural.repository_state(REPO)
            retasked = prepare_interpretation_task(
                REPO, _subject(), structural=structural,
                evidence=evidence, bounds=_bounds(), state=state,
                store=store,
            )
            descriptions = [
                req.description
                for req in retasked.request.brief.open_requirements
            ]
            self.assertIn("main purpose unexamined", descriptions)
        finally:
            store.close()

    def test_sibling_slice_requirements_stay_out(self):
        # F-02 narrow-stays-narrow: an OPEN recorded for the same
        # subject under a DIFFERENT slice never enters this slice's
        # brief, even though class guidance is shared.
        from span.ports.interpretation import PendingInterpretation

        structural, evidence, store = _harness()
        try:
            cont = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/main.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence,
                store=store, continuations=cont,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            other = m.SemanticQuestionScope(
                scope_root=_sid(),
                subject=_sid(),
                question_class=(
                    pending.request.question.question_class
                ),
                question_slice="unrelated-slice",
                materiality_basis="sibling",
            )
            submitted = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        m.InterpretationCoverage(
                            subjects=(_sid(),),
                            question_slice="unrelated-slice",
                            evidence_scope=m.EvidenceScope(
                                paths=(), evidence_refs=()
                            ),
                            declared_complete=False,
                            question=other,
                            disposition=(
                                m.SemanticQuestionDisposition.OPEN
                            ),
                            result_refs=(),
                            resolution_requirements=(
                                m.ResolutionRequirement(
                                    kind=(
                                        m.ResolutionKind
                                        .MISSING_SEMANTIC_COVERAGE
                                    ),
                                    subject_or_claim=_sid(),
                                    description="sibling slice req",
                                    supporting_context=(),
                                ),
                            ),
                            disposition_basis="sibling open",
                            question_evidence=(),
                        ),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence,
                store=store, continuations=cont,
            )
            self.assertIsInstance(submitted, m.SemanticAnswer)
            state = structural.repository_state(REPO)
            retasked = prepare_interpretation_task(
                REPO, _subject(), structural=structural,
                evidence=evidence, bounds=_bounds(), state=state,
                store=store,
            )
            descriptions = [
                req.description
                for req in retasked.request.brief.open_requirements
            ]
            self.assertNotIn("sibling slice req", descriptions)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
