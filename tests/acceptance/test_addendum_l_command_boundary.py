"""Addendum L acceptance: compact question command, canonical persistence.

These tests submit through the public command carriers
(``question_decision`` / ``proposed_questions``) and assert the canonical
persisted ``InterpretationCoverage`` Span derives, proving the command /
persistence ownership split does not change semantic outcomes.
"""

import unittest

from span.core import model as m
from span.core import schema as _schema
from span.core.validation import InterpretationUnitRejected
from span.ports.interpretation import PendingInterpretation
from span import service as ops
from span.service.questions import effective_question_view
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp import TOOL_SCHEMAS, decode_request
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

REPO = "cmd-boundary-svc"

FILES = {
    "README.md": "# cmd-boundary-svc\n\nRoutes commands.\n",
    "src/router.py": "ROUTE = 1\n",
    "src/sink.py": "SINK = 1\n",
}


def _bounds():
    return m.QueryBounds(50, 2, 8, 24, 96_000, 64, 64)


def _sid(locator):
    return m.SubjectId(
        repository_id=REPO,
        subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator=locator,
    )


def _ref(path):
    return _ref_from(FILES, path)


def _ref_from(files, path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=(
            m.EvidenceSourceKind.DOCUMENTATION
            if path.endswith(".md")
            else m.EvidenceSourceKind.SOURCE_CODE
        ),
        locator=path,
        revision_or_fingerprint=fingerprint_content(files[path]),
    )


def _changed_evidence(**changes):
    files = dict(FILES)
    files.update(changes)
    return files, FixtureEvidenceSource(REPO, files)


def _harness():
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        (
            InMemorySubject("src/router.py", m.SubjectKind.COMPONENT, "router"),
            InMemorySubject("src/sink.py", m.SubjectKind.COMPONENT, "sink"),
        ),
        (
            InMemoryEdge(
                "src/router.py", m.StructuralEdgeKind.DEPENDS_ON, "src/sink.py"
            ),
        ),
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
        ),
        repository_id=REPO,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return structural, evidence, store


def _purpose_claim():
    return m.CandidateSemanticClaim(
        candidate_key="purpose",
        subject=_sid("src/router.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("Routes commands", ()),
        evidence=(_ref("README.md"),),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the routing purpose",
        ),
    )


def _scope(slice_text, cls=m.SemanticQuestionClass.CQ_01):
    return m.SemanticQuestionScope(
        scope_root=_sid("src/router.py"),
        subject=_sid("src/router.py"),
        question_class=cls,
        question_slice=slice_text,
        materiality_basis="agent-owned test materiality",
    )


def _pending(structural, evidence, store, continuations, locator="src/router.py"):
    result = ops.explain(
        ops.SemanticExplainRequest(
            repository_id=REPO,
            target=m.SubjectSelector(name_or_locator=locator),
            bounds=_bounds(),
        ),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    assert isinstance(result, PendingInterpretation), result
    return result


def _coverage(store, scope):
    rows = store.load_all_question_coverages(REPO, scope.scope_root, (scope.subject,))
    matches = [row for row in rows if row.question == scope]
    assert len(matches) == 1, matches
    return matches[0]


class CompactCommandTest(unittest.TestCase):
    def test_bound_answer_derives_canonical_coverage(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            bound = pending.request.question
            result = m.SemanticInterpretationResult(
                claims=(_purpose_claim(),),
                question_decision=m.SemanticQuestionDecision(
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    disposition_basis="examined the admitted readme",
                ),
            )
            # The command representation never contains InterpretationCoverage.
            payload = m.to_canonical(result)
            self.assertIn("question_decision", payload)
            self.assertNotIn("proposed_question_coverages", payload)
            self.assertNotIn(
                "InterpretationCoverage",
                repr(payload),
            )

            answer = ops.submit_interpretation(
                pending.continuation,
                result,
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)

            coverage = _coverage(store, bound)
            self.assertEqual(coverage.question, bound)
            self.assertEqual(coverage.question_slice, bound.question_slice)
            self.assertEqual(coverage.subjects, (bound.subject,))
            self.assertIs(coverage.disposition, m.SemanticQuestionDisposition.ANSWERED)
            # declared_complete is a deterministic consequence of ANSWERED.
            self.assertTrue(coverage.declared_complete)
            self.assertEqual(len(coverage.result_refs), 1)
            self.assertIsInstance(coverage.result_refs[0], m.ClaimRef)
            # Span derives question evidence from admitted canonical evidence.
            self.assertTrue(coverage.question_evidence)
            self.assertTrue(
                all(
                    obs.observed_fingerprint
                    == fingerprint_content(FILES[obs.evidence_ref.locator])
                    for obs in coverage.question_evidence
                )
            )
        finally:
            store.close()

    def test_open_preserves_disposition(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            requirement = m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_AUTHORITY,
                subject_or_claim=_sid("src/router.py"),
                description="governing routing decision not found",
                supporting_context=(),
            )
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.OPEN,
                        evidence_scope=m.EvidenceScope(
                            evidence_refs=(_ref("README.md"),)
                        ),
                        resolution_requirements=(requirement,),
                        disposition_basis="ownership text absent",
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            opened = _coverage(store, pending.request.question)
            self.assertIs(opened.disposition, m.SemanticQuestionDisposition.OPEN)
            self.assertFalse(opened.declared_complete)
            self.assertEqual(opened.result_refs, ())
            self.assertEqual(opened.resolution_requirements, (requirement,))
            self.assertTrue(opened.question_evidence)
        finally:
            store.close()

    def test_not_applicable_preserves_disposition(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=(m.SemanticQuestionDisposition.NOT_APPLICABLE),
                        evidence_scope=m.EvidenceScope(
                            evidence_refs=(_ref("README.md"),)
                        ),
                        disposition_basis="no test artifact in bounded scope",
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            na = _coverage(store, pending.request.question)
            self.assertIs(
                na.disposition,
                m.SemanticQuestionDisposition.NOT_APPLICABLE,
            )
            self.assertFalse(na.declared_complete)
            self.assertEqual(na.result_refs, ())
            self.assertTrue(na.disposition_basis)
            # Direct evidence support keeps it freshness-trackable/reopenable.
            self.assertTrue(na.question_evidence)
        finally:
            store.close()

    def test_agent_owns_additional_question_materiality(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            follow_pending = _scope("what does the router persist?")
            follow_open = _scope("which authority governs routing?")
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="readme examined",
                    ),
                    proposed_questions=(
                        m.ProposedSemanticQuestion(
                            follow_pending,
                            m.SemanticQuestionDecision(
                                disposition=(m.SemanticQuestionDisposition.PENDING),
                                disposition_basis="agent-admitted follow-up",
                            ),
                        ),
                        m.ProposedSemanticQuestion(
                            follow_open,
                            m.SemanticQuestionDecision(
                                disposition=m.SemanticQuestionDisposition.OPEN,
                                resolution_requirements=(
                                    m.ResolutionRequirement(
                                        kind=(m.ResolutionKind.MISSING_AUTHORITY),
                                        subject_or_claim=_sid("src/router.py"),
                                        description="authority not examined",
                                        supporting_context=(),
                                    ),
                                ),
                                disposition_basis="authority not examined",
                            ),
                        ),
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIs(
                _coverage(store, pending.request.question).disposition,
                m.SemanticQuestionDisposition.ANSWERED,
            )
            self.assertIs(
                _coverage(store, follow_pending).disposition,
                m.SemanticQuestionDisposition.PENDING,
            )
            self.assertIs(
                _coverage(store, follow_open).disposition,
                m.SemanticQuestionDisposition.OPEN,
            )
        finally:
            store.close()


class WireCeremonyTest(unittest.TestCase):
    def test_mapping_submission_template_decodes_every_bound_member(self):
        import json

        from span.service.interpretation import _mapping_submission_template

        def _item(index):
            return m.EvidenceInventoryItem(
                evidence_ref=m.EvidenceRef(
                    evidence_id=m.EvidenceId(f"ev-{index}"),
                    repository_id="r",
                    locator=f"src/f{index}.py",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                ),
                content_fingerprint=f"fp-{index}",
            )

        text = _mapping_submission_template((_item(0), _item(1)))
        self.assertNotIn("InterpretationCoverage", text)
        payload = json.loads(text.split(": ", 1)[1])
        self.assertNotIn("question_decision", payload)
        decoded = _schema.from_wire(m.SemanticInterpretationResult, payload)
        self.assertIsNone(decoded.question_decision)
        self.assertEqual(
            [
                acc.evidence_id.value
                for acc in decoded.proposed_target_inventory_accounting
            ],
            ["ev-0", "ev-1"],
        )
        # A mapping unit never pretends to answer a bound semantic question.
        self.assertNotIn("question", payload)

    def test_selector_accepts_omitted_null_key(self):
        request = decode_request(
            "explain",
            {
                "repository_id": "r",
                "target": {"name_or_locator": "src/foo.py"},
            },
        )
        self.assertIsNone(request.target.exact_subject_id)
        self.assertEqual(request.target.name_or_locator, "src/foo.py")

    def test_selector_exact_id_precedence_is_preserved(self):
        request = decode_request(
            "explain",
            {
                "repository_id": "r",
                "target": {
                    "exact_subject_id": {
                        "repository_id": "r",
                        "subject_kind": "COMPONENT",
                        "canonical_locator": "src/foo.py",
                    },
                    "name_or_locator": "src/other.py",
                },
            },
        )
        self.assertIsNotNone(request.target.exact_subject_id)
        self.assertEqual(
            request.target.exact_subject_id.canonical_locator,
            "src/foo.py",
        )
        self.assertEqual(request.target.name_or_locator, "src/other.py")

    def test_refresh_target_is_required_and_not_nullable(self):
        schema = TOOL_SCHEMAS["refresh"]
        self.assertIn("target", schema["required"])
        self.assertFalse(
            any(
                branch == {"type": "null"}
                for branch in schema["properties"]["target"].get("anyOf", [])
            )
        )


def _obs_ids(coverage):
    return tuple(
        obs.evidence_ref.evidence_id.value for obs in coverage.question_evidence
    )


def _result_ids(coverage):
    return tuple(ref.id.value for ref in coverage.result_refs)


def _refresh_pending(structural, evidence, store, continuations):
    result = ops.refresh(
        ops.SemanticRefreshRequest(
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


class QuestionEvidenceIsolationTest(unittest.TestCase):
    """R1–R4: direct evidence is exact selected/material support only."""

    def test_r1_not_applicable_tracks_only_selected_evidence(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            selected = _ref("README.md")
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=(m.SemanticQuestionDisposition.NOT_APPLICABLE),
                        evidence_scope=m.EvidenceScope(evidence_refs=(selected,)),
                        disposition_basis="readme has no routing tests",
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            coverage = _coverage(store, pending.request.question)
            self.assertEqual(_obs_ids(coverage), ("ev-README.md",))

            _, changed_b = _changed_evidence(**{"src/router.py": "ROUTE = 2\n"})
            view = effective_question_view(
                coverage,
                evidence=changed_b,
                store=store,
                repository_id=REPO,
            )
            self.assertIs(view.freshness.state, m.FreshnessState.CURRENT)

            _, changed_a = _changed_evidence(**{"README.md": "# changed\n"})
            view = effective_question_view(
                coverage,
                evidence=changed_a,
                store=store,
                repository_id=REPO,
            )
            self.assertIsNot(view.freshness.state, m.FreshnessState.CURRENT)
            self.assertIs(
                view.effective_disposition,
                m.SemanticQuestionDisposition.PENDING,
            )
        finally:
            store.close()

    def test_r2_unsupported_negative_has_no_incidental_evidence(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=(m.SemanticQuestionDisposition.NOT_APPLICABLE),
                        disposition_basis="nothing in the bounded scope",
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            coverage = _coverage(store, pending.request.question)
            self.assertEqual(coverage.result_refs, ())
            self.assertEqual(coverage.question_evidence, ())
            view = effective_question_view(
                coverage,
                evidence=evidence,
                store=store,
                repository_id=REPO,
            )
            self.assertIs(
                view.freshness.state,
                m.FreshnessState.UNVERIFIABLE,
            )
        finally:
            store.close()

    def test_r3_open_tracks_only_selected_evidence(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            selected = _ref("README.md")
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.OPEN,
                        evidence_scope=m.EvidenceScope(evidence_refs=(selected,)),
                        resolution_requirements=(
                            m.ResolutionRequirement(
                                kind=m.ResolutionKind.MISSING_AUTHORITY,
                                subject_or_claim=_sid("src/router.py"),
                                description="authority not found",
                                supporting_context=(),
                            ),
                        ),
                        disposition_basis="authority remains unresolved",
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            coverage = _coverage(store, pending.request.question)
            self.assertEqual(_obs_ids(coverage), ("ev-README.md",))

            _, changed_b = _changed_evidence(**{"src/router.py": "ROUTE = 2\n"})
            view = effective_question_view(
                coverage,
                evidence=changed_b,
                store=store,
                repository_id=REPO,
            )
            self.assertIs(view.freshness.state, m.FreshnessState.CURRENT)

            _, changed_a = _changed_evidence(**{"README.md": "# changed\n"})
            view = effective_question_view(
                coverage,
                evidence=changed_a,
                store=store,
                repository_id=REPO,
            )
            self.assertIsNot(view.freshness.state, m.FreshnessState.CURRENT)
        finally:
            store.close()

    def test_r4_proposed_question_evidence_is_isolated(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            bound_ref = _ref("README.md")
            follow_ref = _ref("src/router.py")
            follow = _scope("what does the router persist?")
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="purpose",
                            subject=_sid("src/router.py"),
                            kind=m.ClaimKind.PURPOSE,
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.PurposeValue("Routes commands", ()),
                            evidence=(bound_ref,),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "readme states routing purpose",
                            ),
                        ),
                    ),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="readme examined",
                    ),
                    proposed_questions=(
                        m.ProposedSemanticQuestion(
                            follow,
                            m.SemanticQuestionDecision(
                                disposition=(m.SemanticQuestionDisposition.PENDING),
                                evidence_scope=m.EvidenceScope(
                                    evidence_refs=(follow_ref,)
                                ),
                                disposition_basis="agent-admitted follow-up",
                            ),
                        ),
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            bound_cov = _coverage(store, pending.request.question)
            follow_cov = _coverage(store, follow)
            self.assertEqual(_obs_ids(bound_cov), ("ev-README.md",))
            self.assertEqual(_obs_ids(follow_cov), ("ev-src/router.py",))
            self.assertEqual(follow_cov.result_refs, ())
        finally:
            store.close()


class PriorOwnershipTest(unittest.TestCase):
    """R5–R8: OPEN/PENDING retain prior ownership; replacement retires."""

    def _establish(self, structural, evidence, store, continuations):
        pending = _pending(structural, evidence, store, continuations)
        claim_ref = _ref("README.md")
        ops.submit_interpretation(
            pending.continuation,
            m.SemanticInterpretationResult(
                claims=(
                    m.CandidateSemanticClaim(
                        candidate_key="purpose",
                        subject=_sid("src/router.py"),
                        kind=m.ClaimKind.PURPOSE,
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        value=m.PurposeValue("Routes commands", ()),
                        evidence=(claim_ref,),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION,
                            "readme states routing purpose",
                        ),
                    ),
                ),
                question_decision=m.SemanticQuestionDecision(
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    disposition_basis="readme examined",
                ),
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
        coverage = _coverage(store, pending.request.question)
        return pending.request.question, coverage

    def test_r5_answered_to_open_preserves_ownership(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            scope, answered = self._establish(
                structural, evidence, store, continuations
            )
            (claim_id,) = _result_ids(answered)

            _, changed = _changed_evidence(**{"README.md": "# changed\n"})
            refresh = _refresh_pending(structural, changed, store, continuations)
            ops.submit_interpretation(
                refresh.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.OPEN,
                        resolution_requirements=(
                            m.ResolutionRequirement(
                                kind=m.ResolutionKind.MISSING_AUTHORITY,
                                subject_or_claim=_sid("src/router.py"),
                                description="authority not re-established",
                                supporting_context=(),
                            ),
                        ),
                        disposition_basis="authority not re-established",
                    ),
                ),
                structural=structural,
                evidence=changed,
                store=store,
                continuations=continuations,
            )
            reopened = _coverage(store, scope)
            self.assertIs(reopened.disposition, m.SemanticQuestionDisposition.OPEN)
            self.assertIn(claim_id, _result_ids(reopened))
            view = effective_question_view(
                reopened,
                evidence=changed,
                store=store,
                repository_id=REPO,
            )
            self.assertIsNot(
                view.effective_disposition,
                m.SemanticQuestionDisposition.ANSWERED,
            )
        finally:
            store.close()

    def test_r6_answered_to_pending_preserves_ownership(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            scope, answered = self._establish(
                structural, evidence, store, continuations
            )
            (claim_id,) = _result_ids(answered)

            _, changed = _changed_evidence(**{"README.md": "# changed\n"})
            refresh = _refresh_pending(structural, changed, store, continuations)
            ops.submit_interpretation(
                refresh.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.PENDING,
                        disposition_basis="reassessment pending",
                    ),
                ),
                structural=structural,
                evidence=changed,
                store=store,
                continuations=continuations,
            )
            pending = _coverage(store, scope)
            self.assertIs(pending.disposition, m.SemanticQuestionDisposition.PENDING)
            self.assertIn(claim_id, _result_ids(pending))
        finally:
            store.close()

    def test_r7_later_answer_retires_prior_after_open(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            scope, answered = self._establish(
                structural, evidence, store, continuations
            )
            (old_id,) = _result_ids(answered)

            _, changed = _changed_evidence(**{"README.md": "# changed\n"})
            refresh = _refresh_pending(structural, changed, store, continuations)
            ops.submit_interpretation(
                refresh.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.OPEN,
                        resolution_requirements=(
                            m.ResolutionRequirement(
                                kind=m.ResolutionKind.MISSING_AUTHORITY,
                                subject_or_claim=_sid("src/router.py"),
                                description="authority not re-established",
                                supporting_context=(),
                            ),
                        ),
                        disposition_basis="authority not re-established",
                    ),
                ),
                structural=structural,
                evidence=changed,
                store=store,
                continuations=continuations,
            )
            self.assertIn(old_id, _result_ids(_coverage(store, scope)))

            _, changed_again = _changed_evidence(**{"README.md": "# changed again\n"})
            refresh = _refresh_pending(structural, changed_again, store, continuations)
            new_ref = _ref_from(
                dict(FILES, **{"README.md": "# changed again\n"}), "README.md"
            )
            ops.submit_interpretation(
                refresh.continuation,
                m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="purpose-v2",
                            subject=_sid("src/router.py"),
                            kind=m.ClaimKind.PURPOSE,
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.PurposeValue("Routes commands v2", ()),
                            evidence=(new_ref,),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "changed readme states routing purpose",
                            ),
                        ),
                    ),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=(m.SemanticQuestionDisposition.ANSWERED),
                        disposition_basis="changed readme examined",
                    ),
                ),
                structural=structural,
                evidence=changed_again,
                store=store,
                continuations=continuations,
            )
            final = _coverage(store, scope)
            final_ids = _result_ids(final)
            self.assertEqual(len(final_ids), 1)
            self.assertNotIn(old_id, final_ids)
            with self.assertRaises(ValueError):
                store.load_by_refs(REPO, (m.ClaimRef(id=m.ClaimId(old_id)),))
        finally:
            store.close()

    def test_r8_explicit_withdrawal_overrides_preservation(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            scope, answered = self._establish(
                structural, evidence, store, continuations
            )
            (old_id,) = _result_ids(answered)
            old_ref = m.ClaimRef(id=m.ClaimId(old_id))

            _, changed = _changed_evidence(**{"README.md": "# changed\n"})
            refresh = _refresh_pending(structural, changed, store, continuations)
            ops.submit_interpretation(
                refresh.continuation,
                m.SemanticInterpretationResult(
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.OPEN,
                        resolution_requirements=(
                            m.ResolutionRequirement(
                                kind=m.ResolutionKind.MISSING_AUTHORITY,
                                subject_or_claim=_sid("src/router.py"),
                                description="authority withdrawn",
                                supporting_context=(),
                            ),
                        ),
                        disposition_basis="prior output explicitly withdrawn",
                    ),
                    candidate_withdrawals=(
                        m.CandidateSemanticWithdrawal(
                            target=old_ref,
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "withdrawn by the interpreting agent",
                            ),
                            evidence=(_ref("README.md"),),
                        ),
                    ),
                ),
                structural=structural,
                evidence=changed,
                store=store,
                continuations=continuations,
            )
            reopened = _coverage(store, scope)
            self.assertNotIn(old_id, _result_ids(reopened))
        finally:
            store.close()


class TargetEvidenceIsolationTest(unittest.TestCase):
    """R14: target proposed questions keep their own selected support."""

    def test_target_proposed_questions_do_not_cross_contaminate(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            area = m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.OTHER,
                canonical_locator="routing-area",
            )
            mapped = ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=REPO,
                    target=m.EvidenceScope(paths=("src",)),
                    objective="Establish routing area semantics.",
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(mapped, PendingInterpretation)
            items = mapped.request.target_inventory_items
            self.assertTrue(items)
            ops.submit_interpretation(
                mapped.continuation,
                m.SemanticInterpretationResult(
                    candidate_subjects=(
                        m.CandidateSubject(
                            provisional_locator="routing-area",
                            kind=m.SubjectKind.OTHER,
                            display_name="routing",
                            declared_kind="routing",
                            evidence=(items[0].evidence_ref,),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "src files form the routing area",
                            ),
                        ),
                    ),
                    proposed_target_inventory_accounting=tuple(
                        m.CandidateTargetInventoryAccount(
                            evidence_id=item.evidence_ref.evidence_id,
                            assigned_area_subjects=(area,),
                        )
                        for item in items
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            semantic = ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=REPO,
                    target=m.EvidenceScope(paths=("src",)),
                    objective="Establish routing area semantics.",
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(semantic, PendingInterpretation)
            seed = semantic.request.question
            self.assertIsNotNone(seed)
            qa = m.SemanticQuestionScope(
                scope_root=area,
                subject=area,
                question_class=m.SemanticQuestionClass.CQ_04,
                question_slice="what does routing depend on?",
                materiality_basis="agent-owned target materiality",
            )
            qb = m.SemanticQuestionScope(
                scope_root=area,
                subject=area,
                question_class=m.SemanticQuestionClass.CQ_05,
                question_slice="what representation crosses the boundary?",
                materiality_basis="agent-owned target materiality",
            )
            answer = ops.submit_interpretation(
                semantic.continuation,
                m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="area-purpose",
                            subject=area,
                            kind=m.ClaimKind.PURPOSE,
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.PurposeValue("Routes commands", ()),
                            evidence=(items[0].evidence_ref,),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "routing area purpose",
                            ),
                        ),
                    ),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="seed examined",
                    ),
                    proposed_questions=(
                        m.ProposedSemanticQuestion(
                            qa,
                            m.SemanticQuestionDecision(
                                disposition=(m.SemanticQuestionDisposition.PENDING),
                                evidence_scope=m.EvidenceScope(
                                    evidence_refs=(items[0].evidence_ref,)
                                ),
                                disposition_basis="target follow-up",
                            ),
                        ),
                        m.ProposedSemanticQuestion(
                            qb,
                            m.SemanticQuestionDecision(
                                disposition=(m.SemanticQuestionDisposition.PENDING),
                                evidence_scope=m.EvidenceScope(
                                    evidence_refs=(items[1].evidence_ref,)
                                ),
                                disposition_basis="target follow-up",
                            ),
                        ),
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, PendingInterpretation)
            association = store.load_target_association(
                REPO, semantic.request.target_id
            )
            self.assertIsNotNone(association)
            self.assertEqual({qa, qb} - set(association.target_questions), set())
            self.assertEqual(
                _obs_ids(_coverage(store, qa)),
                (items[0].evidence_ref.evidence_id.value,),
            )
            self.assertEqual(
                _obs_ids(_coverage(store, qb)),
                (items[1].evidence_ref.evidence_id.value,),
            )
        finally:
            store.close()


class CommandRoleTest(unittest.TestCase):
    """R9–R13: role enforcement and the correction exception."""

    def test_r9_bound_question_through_proposed_questions_rejects(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        proposed_questions=(
                            m.ProposedSemanticQuestion(
                                pending.request.question,
                                m.SemanticQuestionDecision(
                                    disposition=(m.SemanticQuestionDisposition.PENDING),
                                    disposition_basis="wrong channel",
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
                "must be answered through question_decision",
                str(ctx.exception),
            )
            # No write, and the continuation remains usable.
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=(m.SemanticQuestionDisposition.ANSWERED),
                        disposition_basis="corrected submission",
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
        finally:
            store.close()

    def test_r10_additional_answered_question_rejects(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            follow = _scope("what does the router persist?")
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),),
                        question_decision=m.SemanticQuestionDecision(
                            disposition=(m.SemanticQuestionDisposition.ANSWERED),
                            disposition_basis="bound examined",
                        ),
                        proposed_questions=(
                            m.ProposedSemanticQuestion(
                                follow,
                                m.SemanticQuestionDecision(
                                    disposition=(
                                        m.SemanticQuestionDisposition.ANSWERED
                                    ),
                                    disposition_basis="not allowed",
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
                "only the currently bound question may be newly ANSWERED",
                str(ctx.exception),
            )
            rows = store.load_all_question_coverages(
                REPO,
                pending.request.question.scope_root,
                (pending.request.question.subject,),
            )
            self.assertEqual(rows, ())
        finally:
            store.close()

    def test_r11_allowed_followup_dispositions_succeed(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _pending(structural, evidence, store, continuations)
            scopes = {
                disposition: _scope(f"follow-{disposition.value}")
                for disposition in (
                    m.SemanticQuestionDisposition.PENDING,
                    m.SemanticQuestionDisposition.OPEN,
                    m.SemanticQuestionDisposition.NOT_APPLICABLE,
                )
            }
            proposed = []
            for disposition, scope in scopes.items():
                requirement = (
                    m.ResolutionRequirement(
                        kind=m.ResolutionKind.MISSING_AUTHORITY,
                        subject_or_claim=_sid("src/router.py"),
                        description="follow-up gap",
                        supporting_context=(),
                    ),
                )
                proposed.append(
                    m.ProposedSemanticQuestion(
                        scope,
                        m.SemanticQuestionDecision(
                            disposition=disposition,
                            evidence_scope=m.EvidenceScope(
                                evidence_refs=(_ref("README.md"),)
                            ),
                            resolution_requirements=(
                                requirement
                                if disposition is m.SemanticQuestionDisposition.OPEN
                                else ()
                            ),
                            disposition_basis="agent follow-up",
                        ),
                    )
                )
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="bound examined",
                    ),
                    proposed_questions=tuple(proposed),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            for disposition, scope in scopes.items():
                self.assertIs(_coverage(store, scope).disposition, disposition)
        finally:
            store.close()

    def _establish(self, structural, evidence, store, continuations):
        pending = _pending(structural, evidence, store, continuations)
        ops.submit_interpretation(
            pending.continuation,
            m.SemanticInterpretationResult(
                claims=(_purpose_claim(),),
                question_decision=m.SemanticQuestionDecision(
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    disposition_basis="readme examined",
                ),
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
        return pending.request.question

    def _challenge(self, structural, evidence, store, continuations):
        result = ops.refresh(
            ops.SemanticRefreshRequest(
                repository_id=REPO,
                target=m.SubjectSelector(name_or_locator="src/router.py"),
                bounds=_bounds(),
                stale_only=False,
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
        assert isinstance(result, PendingInterpretation), result
        return result

    def test_r12_correction_answered_exception(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original = self._establish(structural, evidence, store, continuations)
            challenged = self._challenge(structural, evidence, store, continuations)
            self.assertNotEqual(challenged.request.question, original)
            new_claim = m.CandidateSemanticClaim(
                candidate_key="purpose-v2",
                subject=_sid("src/router.py"),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Routes commands v2", ()),
                evidence=(_ref("README.md"),),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "corrected readme reading",
                ),
            )
            ops.submit_interpretation(
                challenged.continuation,
                m.SemanticInterpretationResult(
                    claims=(new_claim,),
                    proposed_questions=(
                        m.ProposedSemanticQuestion(
                            original,
                            m.SemanticQuestionDecision(
                                disposition=(m.SemanticQuestionDisposition.ANSWERED),
                                disposition_basis="corrected reading",
                            ),
                        ),
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            corrected = _coverage(store, original)
            self.assertIs(
                corrected.disposition,
                m.SemanticQuestionDisposition.ANSWERED,
            )
            self.assertEqual(len(corrected.result_refs), 1)
            # The fallback scaffolding question is never persisted.
            rows = store.load_all_question_coverages(
                REPO,
                challenged.request.question.scope_root,
                (challenged.request.question.subject,),
            )
            self.assertFalse(
                any(row.question == challenged.request.question for row in rows)
            )
        finally:
            store.close()

    def test_r13_correction_open_preserves_ownership(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original = self._establish(structural, evidence, store, continuations)
            before = _coverage(store, original)
            (claim_id,) = _result_ids(before)
            challenged = self._challenge(structural, evidence, store, continuations)
            ops.submit_interpretation(
                challenged.continuation,
                m.SemanticInterpretationResult(
                    proposed_questions=(
                        m.ProposedSemanticQuestion(
                            original,
                            m.SemanticQuestionDecision(
                                disposition=m.SemanticQuestionDisposition.OPEN,
                                resolution_requirements=(
                                    m.ResolutionRequirement(
                                        kind=(m.ResolutionKind.MISSING_AUTHORITY),
                                        subject_or_claim=_sid("src/router.py"),
                                        description="challenge unresolved",
                                        supporting_context=(),
                                    ),
                                ),
                                disposition_basis="challenge unresolved",
                            ),
                        ),
                    ),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            corrected = _coverage(store, original)
            self.assertIs(
                corrected.disposition,
                m.SemanticQuestionDisposition.OPEN,
            )
            self.assertIn(claim_id, _result_ids(corrected))
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
