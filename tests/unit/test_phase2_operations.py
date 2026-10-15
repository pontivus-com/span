"""Phase 2 operation tests (plan §7 exchange, §6 discovery, §8 reuse,
§9 refresh, §11.1 init, §11.12 submit).

All deterministic; the FixtureAgent stands in for the invoking agent.
"""

import datetime
import pathlib
import unittest

from span.core import model as m
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
    PendingInterpretation,
)
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span import service as ops
from span.service.discovery import _inventory_snapshot, _read_units_within_bytes
from span.service.resolution import _resolve_query_subject
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


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


FILES = {
    "README.md": "# svc\n\nDoes things.\n",
    "src/main.py": "VALUE = 1\n",
}

SUBJECTS = (
    InMemorySubject("src/main.py", m.SubjectKind.COMPONENT, "main"),
)


def _sid():
    return m.SubjectId(
        repository_id="repo-1",
        subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator="src/main.py",
    )


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id="repo-1",
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


def _agent(complete_questions=False):
    return FixtureAgent(
        {"src/main.py": FixtureCandidates((_candidate(),), ())},
        complete_questions=complete_questions,
    )


def _state():
    return m.RepositoryState(
        repository_id="repo-1", revision_id="r1", dirty=False,
        state_fingerprint="fp",
        observed_at=datetime.datetime(
            2026, 1, 1, tzinfo=datetime.timezone.utc
        ),
    )


def _bare_request():
    return m.SemanticInterpretationRequest(
        repository_id="repo-1",
        subjects=(m.Subject(_sid(), "main", None),),
        evidence_units=(),
        structural_observations=(),
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        identity_bindings=(_sid(),),
        brief=m.TaskBrief(),
        bounds=_bounds(),
    )


def _harness(files=None):
    files = FILES if files is None else files
    structural = InMemoryStructuralSource(
        "repo-1",
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        SUBJECTS,
    )
    evidence = FixtureEvidenceSource("repo-1", dict(files))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id="repo-1",
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return structural, evidence, store


def _explain_request():
    return ops.SemanticExplainRequest(
        repository_id="repo-1",
        target=m.SubjectSelector(None, "src/main.py", (), None),
        bounds=_bounds(),
    )


def _run_exchange(explain_request, structural, evidence, store, agent,
                  seeds=(), continuations=None):
    """Drive one full suspend→perform→submit cycle; returns the answer."""
    continuations = continuations or ContinuationStore()
    pending = ops.explain(
        explain_request, structural=structural, evidence=evidence,
        store=store, continuations=continuations, authority_seeds=seeds,
    )
    assert isinstance(pending, PendingInterpretation), type(pending)
    result = agent.perform(pending.request)
    return ops.submit_interpretation(
        pending.continuation, result, structural=structural,
        evidence=evidence, store=store, continuations=continuations,
    )


class ExchangeTest(unittest.TestCase):
    def test_suspend_then_submit_answers(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            self.assertTrue(pending.continuation)
            self.assertEqual(len(continuations), 1)
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
            self.assertEqual(len(continuations), 0)
        finally:
            store.close()

    def test_unknown_continuation_unavailable(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    "cont-999",
                    m.SemanticInterpretationResult((), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_expired_continuation_abandoned(self):
        now = [datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)]
        store_harness = _harness()
        structural, evidence, store = store_harness
        try:
            continuations = ContinuationStore(
                ttl_seconds=60, now=lambda: now[0]
            )
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            now[0] += datetime.timedelta(hours=1)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation,
                    _agent().perform(pending.request),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_reissue_once_then_abandoned(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            reissued = ops.reissue_interpretation(
                pending.continuation, continuations=continuations
            )
            self.assertIsInstance(reissued, PendingInterpretation)
            self.assertNotEqual(
                reissued.continuation, pending.continuation
            )
            self.assertEqual(
                reissued.request, pending.request
            )
            with self.assertRaises(InterpretationIngressFailure):
                ops.reissue_interpretation(
                    reissued.continuation, continuations=continuations
                )
            with self.assertRaises(InterpretationUnavailable):
                ops.reissue_interpretation(
                    "cont-999", continuations=continuations
                )
        finally:
            store.close()

    def test_reissued_continuation_submits_normally(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            reissued = ops.reissue_interpretation(
                pending.continuation, continuations=continuations
            )
            answer = ops.submit_interpretation(
                reissued.continuation, _agent().perform(reissued.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
        finally:
            store.close()

    def test_naive_clock_abandons(self):
        from span.shell.agent_exchange.continuations import SuspendedOperation

        naive = ContinuationStore(
            now=lambda: datetime.datetime(2026, 1, 1)
        )
        token = naive.pend(
            SuspendedOperation(
                op="explain", repository_id="repo-1",
                subject=m.Subject(_sid(), "main", None),
                request=_bare_request(),
                bounds=_bounds(),
                state=_state(),
            )
        )
        self.assertIsNone(naive.claim(token))

    def test_validation_failure_rejects_without_reissue(self):
        """Addendum H §4: validation rejection retains the live
        continuation (no reissue); a corrected resubmission under the
        same continuation then persists exactly once."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            bad = m.CandidateSemanticClaim(
                subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("ghost", ()),
                evidence=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-ghost"),
                        repository_id="repo-1",
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="ghost.py",
                    ),
                ),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION
                ),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult((bad,), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            # Continuation retained; nothing persisted.
            self.assertEqual(len(continuations), 1)
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
            # Corrected resubmission under the same continuation persists.
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(continuations), 0)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation, _agent().perform(pending.request),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_submitted_overflow_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            request = ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, "src/main.py", (), None),
                bounds=_bounds(max_candidate_claims=1),
            )
            pending = ops.explain(
                request, structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            overflow = m.SemanticInterpretationResult(
                tuple(
                    m.CandidateSemanticClaim(
                        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        value=m.PurposeValue(f"s-{n}", ()),
                        evidence=(_ref("README.md"),),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION
                        ),
                    )
                    for n in range(3)
                ),
                (), (), (),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation, overflow,
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()


class MappingDiagnosticsTest(unittest.TestCase):
    """Workflow-issues §3: field-misuse diagnostics name the required
    field without relaxing validation."""

    DOC_FILES = {
        "src/main.py": "VALUE = 1\n",
        "docs/guide.md": "# Guide\n",
    }

    def _doc_harness(self):
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(
                InMemoryFile(p, c) for p, c in self.DOC_FILES.items()
            ),
            (
                InMemorySubject(
                    "src/main.py", m.SubjectKind.COMPONENT, "main"
                ),
            ),
        )
        evidence = FixtureEvidenceSource("repo-1", dict(self.DOC_FILES))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural,
            evidence=evidence,
            store=store,
        )
        return structural, evidence, store

    def _doc_area(self):
        return m.SubjectId(
            repository_id="repo-1", subject_kind=m.SubjectKind.DOCUMENT,
            canonical_locator="docs/guide.md",
        )

    def _doc_question(self):
        area = self._doc_area()
        return m.SemanticQuestionScope(
            scope_root=area, subject=area,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="guide purpose",
            materiality_basis="mapping admits guide",
        )

    def _doc_item_ref(self):
        return m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-docs/guide.md"),
            repository_id="repo-1",
            source_kind=m.EvidenceSourceKind.DOCUMENTATION,
            locator="docs/guide.md",
            revision_or_fingerprint=fingerprint_content(
                self.DOC_FILES["docs/guide.md"]
            ),
            section_or_span=None,
        )

    def _mapping_pending(self, structural, evidence, store,
                         continuations):
        pending = ops.initialize_target(
            ops.SemanticInitializeTargetRequest(
                repository_id="repo-1",
                target=m.EvidenceScope(
                    paths=("docs/guide.md",), evidence_refs=()
                ),
                objective="diagnostics probe", bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        self.assertIsInstance(pending, PendingInterpretation)
        self.assertIsNone(pending.request.question)
        return pending

    def _new_area_result(self, item_ref, with_reuse):
        area = self._doc_area()
        return m.SemanticInterpretationResult(
            claims=(), relationships=(),
            candidate_subjects=(
                m.CandidateSubject(
                    provisional_locator="docs/guide.md",
                    kind=m.SubjectKind.DOCUMENT,
                    display_name="guide",
                    evidence=(item_ref,),
                    basis=m.SemanticBasis(
                        m.DerivationKind.SEMANTIC_INTERPRETATION,
                        "guide is a coherent area",
                    ),
                ),
            ),
            candidate_conflicts=(),
            proposed_question_coverages=(),
            candidate_withdrawals=(),
            proposed_target_inventory_accounting=(
                m.TargetInventoryAccount(
                    evidence_ref=item_ref,
                    assigned_area_subjects=(area,),
                ),
            ),
            proposed_target_questions=(
                (self._doc_question(),) if with_reuse else ()
            ),
        )

    def test_missing_reuse_names_pending_coverage_field(self):
        from span.core.validation import InterpretationUnitRejected

        structural, evidence, store = self._doc_harness()
        try:
            continuations = ContinuationStore()
            pending = self._mapping_pending(
                structural, evidence, store, continuations
            )
            item_ref = (
                pending.request.target_inventory_item.evidence_ref
            )
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    self._new_area_result(item_ref, with_reuse=True),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            self.assertTrue(
                any(
                    "proposed_question_coverages to create new PENDING "
                    "coverage" in diagnostic
                    for diagnostic in ctx.exception.diagnostics
                ),
                ctx.exception.diagnostics,
            )
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()

    def test_new_area_without_pending_names_same_unit_field(self):
        from span.core.validation import InterpretationUnitRejected

        structural, evidence, store = self._doc_harness()
        try:
            continuations = ContinuationStore()
            pending = self._mapping_pending(
                structural, evidence, store, continuations
            )
            item_ref = (
                pending.request.target_inventory_item.evidence_ref
            )
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    self._new_area_result(item_ref, with_reuse=False),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            self.assertTrue(
                any(
                    "submit one PENDING proposed_question_coverages "
                    "entry" in diagnostic
                    for diagnostic in ctx.exception.diagnostics
                ),
                ctx.exception.diagnostics,
            )
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()


class DiscoveryTest(unittest.TestCase):
    def test_discovery_finds_identity_anchored_evidence(self):
        structural, evidence, store = _harness()
        try:
            subject = m.Subject(_sid(), "main", None)
            state = structural.repository_state("repo-1")
            selection = ops.discover_evidence(
                "repo-1", subject, structural=structural, evidence=evidence,
                bounds=_bounds(), state=state,
                authority_seeds=(_ref("README.md"),),
            )
            locators = {r.locator for r in selection.selected_refs}
            self.assertTrue({"README.md", "src/main.py"} <= locators)
        finally:
            store.close()


class ReuseTest(unittest.TestCase):
    def test_second_query_answers_without_suspension(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            seeds = (_ref("README.md"),)
            answer = _run_exchange(
                _explain_request(), structural, evidence, store,
                _agent(complete_questions=True), seeds, continuations,
            )
            second = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=seeds,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(
                [c.claim_id for c in answer.content.claims],
                [c.claim_id for c in second.content.claims],
            )
        finally:
            store.close()


class RefreshExchangeTest(unittest.TestCase):
    def _indexed(self, continuations=None):
        structural, evidence, store = _harness()
        continuations = continuations or ContinuationStore()
        answer = _run_exchange(
            _explain_request(), structural, evidence, store,
            _agent(), (_ref("README.md"),), continuations,
        )
        return structural, evidence, store, continuations, answer

    def test_nothing_stale_answers_directly(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            observed = fingerprint_content(FILES["src/main.py"])
            # G-15: drain admitted pendings first (refresh now resumes
            # them in order); the all-clear path must then answer
            # directly with nothing outstanding.
            for _ in range(4):
                pending = [
                    cov for cov in store.load_all_question_coverages(
                        "repo-1", None, (_sid(),),
                    )
                    if cov.disposition
                    is m.SemanticQuestionDisposition.PENDING
                    and cov.question is not None
                ]
                if not pending:
                    break
                unit = ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id="repo-1",
                        target=m.SubjectSelector(
                            None, "src/main.py", (), None,
                        ),
                        bounds=_bounds(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                    authority_seeds=(_ref("README.md"),),
                )
                self.assertIsInstance(unit, PendingInterpretation)
                ops.submit_interpretation(
                    unit.continuation,
                    m.SemanticInterpretationResult(
                        claims=(), relationships=(),
                        governing_source_refs=(), diagnostics=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            m.InterpretationCoverage(
                                subjects=(unit.request.question.subject,),
                                question_slice=(
                                    unit.request.question.question_slice
                                ),
                                evidence_scope=m.EvidenceScope(),
                                declared_complete=False,
                                question=unit.request.question,
                                disposition=(
                                    m.SemanticQuestionDisposition
                                    .NOT_APPLICABLE
                                ),
                                result_refs=(), resolution_requirements=(),
                                disposition_basis="drain test",
                                question_evidence=(
                                    m.QuestionEvidenceObservation(
                                        evidence_ref=_ref("src/main.py"),
                                        observed_fingerprint=observed,
                                    ),
                                )),
                        ),
                        candidate_withdrawals=(),
                        proposed_target_inventory_accounting=(),
                        proposed_target_questions=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            answer = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertTrue(answer.content.freshness_items)
        finally:
            store.close()

    def test_stale_suspends_then_resumes_current(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            changed = dict(FILES)
            changed["src/main.py"] = "VALUE = 2\n"
            evidence_v2 = FixtureEvidenceSource("repo-1", changed)
            pending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            content = answer.content
            self.assertIsInstance(content, m.StatusContent)
            self.assertTrue(content.changed_dependencies)
            self.assertEqual(
                content.refresh_scope,
                m.EvidenceScope(paths=("src/main.py",), evidence_refs=()),
            )
        finally:
            store.close()

    def test_failed_unit_preserved_as_stale(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            changed = dict(FILES)
            changed["src/main.py"] = "VALUE = 2\n"
            evidence_v2 = FixtureEvidenceSource("repo-1", changed)
            pending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            bad = m.SemanticInterpretationResult(
                (
                    m.CandidateSemanticClaim(
                        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        value=m.PurposeValue("ghost", ()),
                        evidence=(
                            m.EvidenceRef(
                                evidence_id=m.EvidenceId("ev-ghost"),
                                repository_id="repo-1",
                                source_kind=(
                                    m.EvidenceSourceKind.SOURCE_CODE
                                ),
                                locator="ghost.py",
                            ),
                        ),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION
                        ),
                    ),
                ),
                (), (), (),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation, bad,
                    structural=structural, evidence=evidence_v2, store=store,
                    continuations=continuations,
                )
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertTrue(page.items)
        finally:
            store.close()

    def test_none_target_rejected(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            with self.assertRaises(ops.RefreshScopeError):
                ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id="repo-1", target=None, bounds=_bounds()
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_dirty_tree_uses_content_fingerprints(self):
        files = dict(FILES)
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            SUBJECTS,
            revision="r-dirty",
            dirty=True,
        )
        evidence = FixtureEvidenceSource("repo-1", files)
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural,
            evidence=evidence,
            store=store,
        )
        try:
            continuations = ContinuationStore()
            answer = _run_exchange(
                _explain_request(), structural, evidence, store,
                _agent(), (_ref("README.md"),), continuations,
            )
            for claim in answer.content.claims:
                self.assertIs(
                    claim.freshness.state, m.FreshnessState.CURRENT
                )
        finally:
            store.close()


class InitializeTest(unittest.TestCase):
    def test_init_returns_ready_without_interpretation(self):
        structural, evidence, store = _harness()
        try:
            result = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="/tmp/svc",
                    structural_provider_config="memory:spec",
                    authority_seeds=(_ref("README.md"),),
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
            )
            self.assertEqual(result.repository_id, "repo-1")
            self.assertIs(
                result.readiness, m.RepositoryReadiness.READY
            )
            self.assertEqual(result.structural_source_status, "ready")
            self.assertTrue(
                result.evidence_inventory_status.startswith("ready:")
            )
            self.assertTrue(
                result.semantic_store_status.startswith("ready:schema-")
            )
            self.assertEqual(result.warnings, ())
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_init_signature_has_no_interpretation_input(self):
        import inspect

        params = inspect.signature(ops.initialize_repository).parameters
        self.assertNotIn("interpreter", params)
        self.assertNotIn("agent", params)
        fields = (
            ops.SemanticInitializeRepositoryRequest.__dataclass_fields__
        )
        self.assertNotIn("semantic_provider_config", fields)

    def test_init_rejects_empty_locator(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(ValueError):
                ops.initialize_repository(
                    ops.SemanticInitializeRepositoryRequest(
                        repository_locator="",
                        structural_provider_config="x",
                    ),
                    repository_id="repo-1",
                    structural=structural,
                    evidence=evidence,
                    store=store,
                )
        finally:
            store.close()

    def test_init_ready_despite_truncation(self):
        """Bounded inventory never degrades operational readiness.

        Plan §4.8/I-31 (Q34): readiness answers whether the repository
        can service operations. Truncation is boundedness, reported in
        evidence_inventory_status + warnings — consistent with the
        HOOK_FAST path, which reports READY once initialized.
        """
        structural, evidence, store = _harness()
        try:
            result = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="/tmp/svc",
                    structural_provider_config="memory:spec",
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=_bounds(max_evidence_units=1),
            )
            self.assertIs(
                result.readiness, m.RepositoryReadiness.READY
            )
            self.assertTrue(result.warnings)
            self.assertTrue(
                result.evidence_inventory_status.startswith(
                    "degraded:truncated-at-"
                )
            )
        finally:
            store.close()


class InventorySnapshotTest(unittest.TestCase):
    """Membership-only snapshots match the paged inventory walk.

    `_inventory_snapshot` must produce the identical membership
    fingerprint as paging through `inventory_evidence`, while hashing
    only requested seed locators (§8.5/MI-07 unchanged, one metadata
    walk instead of one full re-hash per page).
    """

    def _paged_ids(self, evidence, bounds):
        ids = []
        token = None
        while True:
            page = evidence.inventory_evidence(
                "repo-1", m.EvidenceScope(paths=(), evidence_refs=()),
                bounds, token,
            )
            ids.extend(
                item.evidence_ref.evidence_id.value
                for item in page.items
            )
            token = page.bound_info.continuation_token
            if token is None:
                break
        return ids

    def test_fixture_snapshot_matches_paged_walk(self):
        import hashlib

        evidence = FixtureEvidenceSource("repo-1", dict(FILES))
        bounds = _bounds(max_evidence_units=1)
        expected = hashlib.sha256(
            repr(sorted(self._paged_ids(evidence, bounds))).encode()
        ).hexdigest()
        membership, seed_map = _inventory_snapshot(
            "repo-1",
            evidence=evidence,
            seeds=(("README.md", "ev-README.md"),
                   ("nope.md", "ev-nope.md")),
        )
        self.assertEqual(membership, expected)
        self.assertEqual(
            seed_map["ev-README.md"],
            fingerprint_content(FILES["README.md"]),
        )
        self.assertEqual(seed_map["ev-nope.md"], "")

    def test_filesystem_snapshot_matches_paged_walk(self):
        import hashlib
        import tempfile

        from span.shell.filesystem_evidence import (
            FilesystemEvidenceSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "a.py").write_text("A = 1\n", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.md").write_text("# b\n", encoding="utf-8")
            evidence = FilesystemEvidenceSource("repo-1", root)
            bounds = _bounds(max_evidence_units=1)
            expected = hashlib.sha256(
                repr(sorted(self._paged_ids(evidence, bounds))).encode()
            ).hexdigest()
            membership, seed_map = _inventory_snapshot(
                "repo-1",
                evidence=evidence,
                seeds=(("a.py", "ev-a.py"),),
            )
            self.assertEqual(membership, expected)
            self.assertTrue(seed_map["ev-a.py"])


class BoundedEvidenceReadTest(unittest.TestCase):
    """Byte-budget reads trim the selection instead of failing it.

    Discovery counts units; §8.4 bytes are enforced by keeping refs
    that fit (§6.2 bounded set) — never by widening bounds, never by
    failing a unit the agent could have answered partially.
    """

    def _ref(self, locator):
        return m.EvidenceRef(
            m.EvidenceId(f"ev-{locator}"), "repo-1",
            m.EvidenceSourceKind.SOURCE_CODE, locator,
        )

    def test_keeps_fitting_prefix(self):
        import tempfile

        from span.shell.filesystem_evidence import (
            FilesystemEvidenceSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "small.py").write_text("A = 1\n", encoding="utf-8")
            (root / "big.py").write_text(
                "X = '" + "y" * 200 + "'\n", encoding="utf-8"
            )
            evidence = FilesystemEvidenceSource("repo-1", root)
            units = _read_units_within_bytes(
                evidence,
                (self._ref("small.py"), self._ref("big.py")),
                _bounds(max_evidence_units=24, max_evidence_bytes=100),
            )
            self.assertEqual(
                [u.evidence_ref.locator for u in units], ["small.py"]
            )

    def test_fail_closed_when_nothing_fits(self):
        import tempfile

        from span.shell.filesystem_evidence import (
            FilesystemEvidenceSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "big.py").write_text(
                "X = '" + "y" * 200 + "'\n", encoding="utf-8"
            )
            evidence = FilesystemEvidenceSource("repo-1", root)
            with self.assertRaises(ValueError):
                _read_units_within_bytes(
                    evidence, (self._ref("big.py"),),
                    _bounds(max_evidence_units=24, max_evidence_bytes=10),
                )


class StoreResolutionTest(unittest.TestCase):
    """Addendum A, F1: registered subjects resolve at query time.

    Structural resolution stays first; an exact identity the index
    cannot resolve falls back to the stored record. Ambiguity is never
    overridden and name-only queries never reach the store.
    """

    def _empty_structural(self):
        return InMemoryStructuralSource("repo-1", (), ())

    def _store_with_workflow(self):
        from span.shell.sqlite_store import SqliteSemanticStore

        store = SqliteSemanticStore(":memory:")
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.SUBSYSTEM,
            canonical_locator="workflows/tta",
        )
        store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=(m.Subject(sid, "tta workflow", None),),
            )
        )
        return store, sid

    def test_store_subject_resolves_by_exact_id(self):
        structural = self._empty_structural()
        store, sid = self._store_with_workflow()
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(sid, None, (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            candidate = resolution.candidates[0]
            self.assertEqual(
                candidate.subject.subject_id.canonical_locator,
                "workflows/tta",
            )
            self.assertIs(
                candidate.rank_basis, m.CandidateRankBasis.EXACT_LOCATOR
            )
        finally:
            store.close()

    def test_store_subject_served_by_explain(self):
        from span.shell.evidence import FixtureEvidenceSource
        from span.shell.sqlite_store import SqliteSemanticStore

        structural = self._empty_structural()
        evidence = FixtureEvidenceSource("repo-1", {})
        store, sid = self._store_with_workflow()
        try:
            ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="fixture",
                    structural_provider_config="memory:test",
                    authority_seeds=(),
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
            )
            from span.shell.agent_exchange.continuations import (
                ContinuationStore,
            )

            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(sid, None, (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            # Reaches the subject (suspends for interpretation) instead
            # of answering NOT_FOUND.
            from span.ports.interpretation import PendingInterpretation

            self.assertIsInstance(pending, PendingInterpretation)
        finally:
            store.close()

    def test_ambiguous_identity_never_overridden(self):
        structural = InMemoryStructuralSource(
            "repo-1",
            (InMemoryFile("a.py", "x\n"), InMemoryFile("b.py", "x\n")),
            (
                InMemorySubject("a.py#dup", m.SubjectKind.CODE_SYMBOL, "dup"),
                InMemorySubject("b.py#dup", m.SubjectKind.CODE_SYMBOL, "dup"),
            ),
        )
        store, _ = self._store_with_workflow()
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "dup", (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
        finally:
            store.close()

    def test_name_only_query_never_reaches_store(self):
        # Addendum I S1 amends A-F1 narrowly: exact canonical locator
        # reaches the store; display-name text never does.
        structural = self._empty_structural()
        store, _ = self._store_with_workflow()
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "tta workflow", (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.NOT_FOUND
            )
        finally:
            store.close()

    def test_exact_locator_reaches_store(self):
        # S1 §5.1: exact ID and exact relative path recover the same
        # stored subject; exact stored locator wins over non-exact
        # structural candidates.
        structural = self._empty_structural()
        store, sid = self._store_with_workflow()
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "workflows/tta", (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                resolution.candidates[0].subject.subject_id, sid
            )
            self.assertIs(
                resolution.candidates[0].rank_basis,
                m.CandidateRankBasis.EXACT_LOCATOR,
            )
        finally:
            store.close()


class S1ExactLocatorEdgeTest(unittest.TestCase):
    """S1 §5.1 edge cases: case, kinds, non-canonical, truncation, plans."""

    def _empty_structural(self):
        return InMemoryStructuralSource("repo-1", (), ())

    def _store_with(self, subjects):
        from span.shell.sqlite_store import SqliteSemanticStore

        store = SqliteSemanticStore(":memory:")
        store.write_index_batch(
            m.CanonicalIndexBatch(subjects=tuple(subjects))
        )
        return store

    def _subject(self, locator, kind, display="d"):
        return m.Subject(
            m.SubjectId(
                repository_id="repo-1",
                subject_kind=kind,
                canonical_locator=locator,
            ),
            display,
            None,
        )

    def test_case_sensitive_no_fold(self):
        store = self._store_with(
            [self._subject("workflows/tta", m.SubjectKind.SUBSYSTEM, "tta")]
        )
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "Workflows/tta", (), None),
                structural=self._empty_structural(),
                store=store,
                bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.NOT_FOUND
            )
        finally:
            store.close()

    def test_same_locator_different_kinds_ambiguous(self):
        store = self._store_with(
            [
                self._subject(
                    "docs/guide.md", m.SubjectKind.DOCUMENT, "guide"
                ),
                self._subject(
                    "docs/guide.md", m.SubjectKind.COMPONENT, "guide"
                ),
            ]
        )
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "docs/guide.md", (), None),
                structural=self._empty_structural(),
                store=store,
                bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertEqual(len(resolution.candidates), 2)
            kinds = [
                c.subject.subject_id.subject_kind
                for c in resolution.candidates
            ]
            self.assertEqual(
                kinds,
                sorted(kinds, key=lambda k: k.value),
            )
        finally:
            store.close()

    def test_kind_filtered_uniqueness(self):
        store = self._store_with(
            [
                self._subject(
                    "docs/guide.md", m.SubjectKind.DOCUMENT, "guide"
                ),
                self._subject(
                    "docs/guide.md", m.SubjectKind.COMPONENT, "guide"
                ),
            ]
        )
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(
                    None,
                    "docs/guide.md",
                    (m.SubjectKind.DOCUMENT,),
                    None,
                ),
                structural=self._empty_structural(),
                store=store,
                bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertIs(
                resolution.candidates[0].subject.subject_id.subject_kind,
                m.SubjectKind.DOCUMENT,
            )
        finally:
            store.close()

    def test_non_canonical_never_via_store(self):
        store = self._store_with(
            [self._subject("workflows/tta", m.SubjectKind.SUBSYSTEM, "tta")]
        )
        try:
            for query in (
                "/workflows/tta",
                "workflows/../workflows/tta",
                "WORKFLOWS/TTA",
            ):
                if query == "WORKFLOWS/TTA":
                    continue
                resolution = _resolve_query_subject(
                    "repo-1",
                    m.SubjectSelector(None, query, (), None),
                    structural=self._empty_structural(),
                    store=store,
                    bounds=_bounds(),
                )
                self.assertIs(
                    resolution.ambiguity,
                    m.ResolutionAmbiguity.NOT_FOUND,
                    query,
                )
        finally:
            store.close()

    def test_exact_stored_beats_non_exact_structural(self):
        structural = InMemoryStructuralSource(
            "repo-1",
            (InMemoryFile("a.py", "x\n"),),
            (
                InMemorySubject("a.py#dup", m.SubjectKind.CODE_SYMBOL, "dup"),
            ),
        )
        store = self._store_with(
            [self._subject("dup", m.SubjectKind.SUBSYSTEM, "dup area")]
        )
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "dup", (), None),
                structural=structural,
                store=store,
                bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                resolution.candidates[0]
                .subject.subject_id.canonical_locator,
                "dup",
            )
        finally:
            store.close()

    def test_structural_exact_ambiguity_preserved(self):
        structural = InMemoryStructuralSource(
            "repo-1",
            (
                InMemoryFile("a.py", "x\n"),
                InMemoryFile("b.py", "x\n"),
            ),
            (
                InMemorySubject(
                    "shared.md", m.SubjectKind.COMPONENT, "shared"
                ),
            ),
        )
        # Force structural exact ambiguity by mirroring the stored locator
        # as an exact structural locator plus a second exact kind.
        store = self._store_with(
            [
                self._subject(
                    "shared.md", m.SubjectKind.DOCUMENT, "shared doc"
                ),
            ]
        )
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "shared.md", (), None),
                structural=structural,
                store=store,
                bounds=_bounds(),
            )
            # Stored exact plus structural exact with different kinds:
            # multiple exact identities remain ambiguous.
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
        finally:
            store.close()

    def test_truncated_never_resolves(self):
        store = self._store_with(
            [
                self._subject(
                    "docs/guide.md", m.SubjectKind.DOCUMENT, "guide"
                ),
                self._subject(
                    "docs/guide.md", m.SubjectKind.COMPONENT, "guide"
                ),
            ]
        )
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "docs/guide.md", (), None),
                structural=self._empty_structural(),
                store=store,
                bounds=_bounds(max_subjects=1),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(resolution.bound_info.truncated)
        finally:
            store.close()

    def test_store_lookup_uses_index_not_enumeration(self):
        from span.shell.sqlite_store import SqliteSemanticStore

        store = SqliteSemanticStore(":memory:")
        try:
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(
                        self._subject(
                            "a.py", m.SubjectKind.COMPONENT, "a"
                        ),
                        self._subject(
                            "b.py", m.SubjectKind.COMPONENT, "b"
                        ),
                    )
                )
            )
            plan = store._db.execute(
                "EXPLAIN QUERY PLAN SELECT canonical_json, kind FROM subjects "
                "WHERE repository_id=? AND locator=? ORDER BY kind LIMIT ?",
                ("repo-1", "a.py", 9),
            ).fetchall()
            text = " ".join(str(col) for row in plan for col in row)
            self.assertIn("SEARCH", text)
            self.assertNotIn("SCAN subjects", text)
            page = store.load_subjects_by_locator(
                "repo-1", "a.py", (), _bounds()
            )
            self.assertEqual(len(page.items), 1)
            self.assertEqual(
                page.items[0].subject_id.canonical_locator, "a.py"
            )
        finally:
            store.close()

    def test_graft_kind_filter_parity(self):
        from span.shell.structural.graft import GraftStructuralSource

        wiring = {
            "nodes": [
                {
                    "id": "src/a.py",
                    "name": "a.py",
                    "kind": "file",
                    "path": "src/a.py",
                    "span": None,
                    "signature": None,
                    "body_hash": "h1",
                },
                {
                    "id": "src/a.py#sym",
                    "name": "sym",
                    "kind": "function",
                    "path": "src/a.py",
                    "span": "L1-L2",
                    "signature": "def sym()",
                    "body_hash": "h2",
                },
            ],
            "edges": [],
        }
        graft = GraftStructuralSource("repo-1", ".", wiring=wiring)
        memory = InMemoryStructuralSource(
            "repo-1",
            (InMemoryFile("src/a.py", "x\n"),),
            (
                InMemorySubject(
                    "src/a.py", m.SubjectKind.COMPONENT, "a.py"
                ),
                InMemorySubject(
                    "src/a.py#sym",
                    m.SubjectKind.CODE_SYMBOL,
                    "sym",
                ),
            ),
        )
        selector = m.SubjectSelector(
            None, "sym", (m.SubjectKind.COMPONENT,), None
        )
        graft_res = graft.resolve_subject(
            "repo-1", selector, _bounds()
        )
        memory_res = memory.resolve_subject(
            "repo-1", selector, _bounds()
        )
        self.assertEqual(
            graft_res.ambiguity, memory_res.ambiguity
        )
        self.assertEqual(
            [c.subject.subject_id.canonical_locator for c in graft_res.candidates],
            [c.subject.subject_id.canonical_locator for c in memory_res.candidates],
        )

    def test_provider_failure_unavailable_envelope(self):
        from span.shell.mcp import McpAdapter, ServiceContext
        from span.shell.agent_exchange.continuations import (
            ContinuationStore,
        )
        from span.shell.structural.graft import GraftUnavailableError

        class _FailingStructural:
            def repository_state(self, repository_id):
                raise GraftUnavailableError("no usable structural index")

            def resolve_subject(self, repository_id, selector, bounds):
                raise GraftUnavailableError("no usable structural index")

        from span.shell.evidence import FixtureEvidenceSource

        evidence = FixtureEvidenceSource("repo-1", {})
        store = self._store_with([])
        try:
            adapter = McpAdapter(
                contexts={
                    "repo-1": ServiceContext(
                        structural=_FailingStructural(),  # type: ignore[arg-type]
                        evidence=evidence,
                        store=store,
                        continuations=ContinuationStore(),
                    )
                }
            )
            result = adapter.dispatch(
                "explain",
                {
                    "repository_id": "repo-1",
                    "target": {
                        "$type": "SubjectSelector",
                        "exact_subject_id": None,
                        "name_or_locator": "missing",
                        "expected_kinds": [],
                        "retrieval_scope_hint": None,
                    },
                },
            )
            self.assertTrue(result.is_error)
            self.assertIn("unavailable", result.content)
        finally:
            store.close()


class CrossUnitCitationTest(unittest.TestCase):
    """Addendum H §5: citations resolve against the canonical provider.

    A later unit may cite evidence established by an earlier unit;
    changed bytes admit the current observation (old rows keep old
    fingerprints and go stale through existing freshness) and unknown
    ids stay unknown.
    """

    FILES2 = {"a.py": "ALPHA = 1\n", "b.py": "BETA = 2\n"}

    def _harness2(self):
        from span.shell.evidence import FixtureEvidenceSource
        from span.shell.sqlite_store import SqliteSemanticStore

        files = dict(self.FILES2)
        subjects = (
            InMemorySubject("a.py", m.SubjectKind.COMPONENT, "aaa"),
            InMemorySubject("b.py", m.SubjectKind.COMPONENT, "bbb"),
        )
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            subjects,
        )
        evidence = FixtureEvidenceSource("repo-1", files)
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural,
            evidence=evidence,
            store=store,
        )
        return structural, evidence, store

    def _ref(self, path, fingerprint):
        return m.EvidenceRef(
            m.EvidenceId(f"ev-{path}"), "repo-1",
            m.EvidenceSourceKind.SOURCE_CODE, path,
            revision_or_fingerprint=fingerprint,
        )

    def _claim_for(self, locator, ref):
        return m.CandidateSemanticClaim(
            candidate_key="purpose",
            subject=m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator=locator,
            ),
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue(f"{locator} serves its module", ()),
            evidence=(ref,),
            candidate_authority=None,
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION, "test"
            ),
        )

    def _submit_for(self, locator, result, structural, evidence, store):
        from span.shell.agent_exchange.continuations import (
            ContinuationStore,
        )

        continuations = ContinuationStore()
        pending = ops.explain(
            ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, locator, (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        from span.ports.interpretation import PendingInterpretation

        self.assertIsInstance(pending, PendingInterpretation)
        return ops.submit_interpretation(
            pending.continuation, result, structural=structural,
            evidence=evidence, store=store,
            continuations=continuations,
        ), pending

    def test_cross_unit_citation_accepted_when_bytes_current(self):
        from span.shell.structural.memory import fingerprint_content

        structural, evidence, store = self._harness2()
        try:
            first, _ = self._submit_for(
                "a.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "a.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            self.assertIsInstance(first, m.SemanticAnswer)
            # Second unit cites a.py although its own task units cover
            # only b.py: established bytes admit the citation.
            second, _ = self._submit_for(
                "b.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "b.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(len(second.content.claims), 1)
        finally:
            store.close()

    def test_cross_unit_citation_admitted_when_bytes_changed(self):
        """Addendum H §5: changed source bytes admit a new current
        interpretation; the new dependency row carries the current
        fingerprint while the old row keeps its original observation."""
        from span.shell.structural.memory import fingerprint_content

        structural, evidence, store = self._harness2()
        try:
            self._submit_for(
                "a.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "a.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            evidence._files["a.py"] = "ALPHA = 99\n"
            current_fp = fingerprint_content("ALPHA = 99\n")
            second, _ = self._submit_for(
                "b.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "b.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(len(second.content.claims), 1)
            persisted_ref = second.content.claims[0].evidence[0]
            self.assertEqual(persisted_ref.evidence_id.value, "ev-a.py")
            self.assertEqual(persisted_ref.locator, "a.py")
            self.assertEqual(
                persisted_ref.revision_or_fingerprint, current_fp
            )
            deps = store.load_evidence_dependencies(
                "repo-1",
                (m.ClaimRef(id=second.content.claims[0].claim_id),),
            )
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0].observed_fingerprint, current_fp)
        finally:
            store.close()

    def test_unknown_evidence_still_rejected(self):
        structural, evidence, store = self._harness2()
        try:
            with self.assertRaises(ops.InterpretationUnitRejected) as cm:
                self._submit_for(
                    "b.py",
                    m.SemanticInterpretationResult(
                        claims=(
                            self._claim_for(
                                "b.py", self._ref("ghost.py", "fp"),
                            ),
                        ),
                        relationships=(),
                        governing_source_refs=(),
                        diagnostics=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                    ),
                    structural, evidence, store,
                )
            self.assertIn("ev-ghost.py", str(cm.exception))
        finally:
            store.close()


class SemanticOutcomeTest(unittest.TestCase):
    """Workflow questions get synthesized, served answers (F1+F2 end to end).

    Two per-file claims established in two units, a registered workflow
    subject, then a synthesis claim citing both files' established
    evidence — served back by exact locator with the synthesized content
    intact and trust honestly unestablished (no authority seeds).
    """

    FILES2 = {"a.py": "ALPHA = 1\n", "b.py": "BETA = 2\n"}
    SUMMARY = (
        "Alpha input configured with beta threshold."
    )

    def _harness2(self):
        from span.shell.evidence import FixtureEvidenceSource
        from span.shell.sqlite_store import SqliteSemanticStore

        files = dict(self.FILES2)
        subjects = (
            InMemorySubject("a.py", m.SubjectKind.COMPONENT, "aaa"),
            InMemorySubject("b.py", m.SubjectKind.COMPONENT, "bbb"),
        )
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            subjects,
        )
        evidence = FixtureEvidenceSource("repo-1", files)
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural,
            evidence=evidence,
            store=store,
        )
        return structural, evidence, store

    def _ref(self, path, fingerprint):
        return m.EvidenceRef(
            m.EvidenceId(f"ev-{path}"), "repo-1",
            m.EvidenceSourceKind.SOURCE_CODE, path,
            revision_or_fingerprint=fingerprint,
        )

    def _exchange(
        self, locator, result, structural, evidence, store,
        complete=False,
    ):
        from span.shell.agent_exchange.continuations import (
            ContinuationStore,
        )
        from span.ports.interpretation import PendingInterpretation

        continuations = ContinuationStore()
        pending = ops.explain(
            ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, locator, (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        self.assertIsInstance(pending, PendingInterpretation)
        if complete:
            # Addendum C C-05 cutover: explicit ANSWERED completion
            # intent for the bound question; the service derives refs.
            question = pending.request.question
            result = m.SemanticInterpretationResult(
                claims=result.claims,
                relationships=result.relationships,
                governing_source_refs=result.governing_source_refs,
                diagnostics=result.diagnostics,
                candidate_subjects=result.candidate_subjects,
                candidate_conflicts=result.candidate_conflicts,
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(question.subject,),
                        question_slice=question.question_slice,
                        evidence_scope=m.EvidenceScope(
                            paths=(), evidence_refs=()
                        ),
                        declared_complete=True,
                        question=question,
                        disposition=(
                            m.SemanticQuestionDisposition.ANSWERED
                        ),
                        result_refs=(),
                        resolution_requirements=(),
                        disposition_basis="test explicit completion",
                        question_evidence=(),
                    ),
                ),
                candidate_withdrawals=result.candidate_withdrawals,
            )
        return ops.submit_interpretation(
            pending.continuation, result, structural=structural,
            evidence=evidence, store=store,
            continuations=continuations,
        )

    def _purpose(self, locator, ref):
        return m.CandidateSemanticClaim(
            candidate_key="purpose",
            subject=m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator=locator,
            ),
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue(f"{locator} serves its module", ()),
            evidence=(ref,),
            candidate_authority=None,
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION, "test"
            ),
        )

    def _result(self, claims, subjects=()):
        return m.SemanticInterpretationResult(
            claims=tuple(claims),
            relationships=(),
            governing_source_refs=(),
            diagnostics=(),
            candidate_subjects=tuple(subjects),
            candidate_conflicts=(),
        )

    def test_workflow_synthesis_served_with_content(self):
        from span.shell.structural.memory import fingerprint_content

        structural, evidence, store = self._harness2()
        try:
            fp_a = fingerprint_content("ALPHA = 1\n")
            fp_b = fingerprint_content("BETA = 2\n")
            self._exchange(
                "a.py",
                self._result(
                    (self._purpose("a.py", self._ref("a.py", fp_a)),)
                ),
                structural, evidence, store,
                complete=True,
            )
            workflow = m.CandidateSubject(
                provisional_locator="workflows/tta",
                kind=m.SubjectKind.SUBSYSTEM,
                display_name="tta workflow",
                declared_kind=None,
                evidence=(self._ref("b.py", fp_b),),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "workflow owns both modules",
                ),
            )
            self._exchange(
                "b.py",
                self._result(
                    (self._purpose("b.py", self._ref("b.py", fp_b)),),
                    (workflow,),
                ),
                structural, evidence, store,
                complete=True,
            )
            synthesis = m.CandidateSemanticClaim(
                candidate_key="purpose",
                subject=m.SubjectId(
                    repository_id="repo-1",
                    subject_kind=m.SubjectKind.SUBSYSTEM,
                    canonical_locator="workflows/tta",
                ),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue(self.SUMMARY, ()),
                evidence=(
                    self._ref("a.py", fp_a), self._ref("b.py", fp_b),
                ),
                candidate_authority=None,
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "both module purposes combined",
                ),
            )
            from span.shell.agent_exchange.continuations import (
                ContinuationStore,
            )
            from span.ports.interpretation import PendingInterpretation

            continuations = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        m.SubjectId(
                            repository_id="repo-1",
                            subject_kind=m.SubjectKind.SUBSYSTEM,
                            canonical_locator="workflows/tta",
                        ),
                        None, (), None,
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(synthesis,),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    proposed_question_coverages=(
                        m.InterpretationCoverage(
                            subjects=(
                                pending.request.question.subject,
                            ),
                            question_slice=(
                                pending.request.question.question_slice
                            ),
                            evidence_scope=m.EvidenceScope(
                                paths=(), evidence_refs=()
                            ),
                            declared_complete=True,
                            question=pending.request.question,
                            disposition=(
                                m.SemanticQuestionDisposition.ANSWERED
                            ),
                            result_refs=(),
                            resolution_requirements=(),
                            disposition_basis="test explicit completion",
                            question_evidence=(),
                        ),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            (served,) = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        m.SubjectId(
                            repository_id="repo-1",
                            subject_kind=m.SubjectKind.SUBSYSTEM,
                            canonical_locator="workflows/tta",
                        ),
                        None, (), None,
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            ).content.claims
            self.assertEqual(served.value.summary, self.SUMMARY)
            self.assertEqual(
                {r.locator for r in served.evidence},
                {"a.py", "b.py"},
            )
            self.assertIs(served.trust, m.TrustState.UNRESOLVED)
            self.assertIs(
                served.freshness.state, m.FreshnessState.CURRENT
            )
        finally:
            store.close()


class ContextualResolutionTest(unittest.TestCase):
    """Path-to-semantic-context resolution (bounded retrieval only)."""

    CTX = "ctx-repo"

    def _bounds(self, **overrides):
        base = dict(
            max_results=50, max_depth=5, max_subjects=8,
            max_evidence_units=24, max_evidence_bytes=96_000,
            max_candidate_claims=64, max_candidate_relationships=64,
        )
        base.update(overrides)
        return m.QueryBounds(**base)

    def _harness(self, files, subjects, repo=None):
        repo = repo or self.CTX
        structural = InMemoryStructuralSource(
            repo,
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            tuple(subjects),
        )
        evidence = FixtureEvidenceSource(repo, dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id=repo,
            structural=structural,
            evidence=evidence,
            store=store,
        )
        return structural, evidence, store

    def _ref(self, repo, path, files):
        return m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{path}"),
            repository_id=repo,
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator=path,
            revision_or_fingerprint=fingerprint_content(files[path]),
        )

    def _sid(self, repo, locator, kind=m.SubjectKind.COMPONENT):
        return m.SubjectId(
            repository_id=repo, subject_kind=kind,
            canonical_locator=locator,
        )

    def _claim(self, cid, sid, value, eref, kind=m.ClaimKind.PURPOSE):
        return m.SemanticClaim(
            claim_id=m.ClaimId(cid), subject=sid, kind=kind,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=value, evidence=(eref,),
            trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )

    def _rel(self, rid, source, kind, target, eref):
        return m.SemanticRelationship(
            relationship_id=m.RelationshipId(rid),
            source=source, kind=kind, target=target,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            evidence=(eref,), trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )

    def _dep(self, ref, eref, fp):
        return m.EvidenceDependency(
            semantic_id=ref, evidence_ref=eref,
            observed_fingerprint=fp,
        )

    def _cq(self, scope_root, subject, qclass, qslice, refs):
        q = m.SemanticQuestionScope(
            scope_root=scope_root, subject=subject,
            question_class=qclass, question_slice=qslice,
            materiality_basis="test",
        )
        return m.InterpretationCoverage(
            subjects=(subject,), question_slice=qslice,
            declared_complete=True, question=q,
            disposition=m.SemanticQuestionDisposition.ANSWERED,
            result_refs=tuple(refs), disposition_basis="b",
        )

    def test_structural_only_hit_falls_through(self):
        from span.service.resolution import (
            _resolve_contextual_subjects,
            _resolve_query_subject,
        )
        repo = self.CTX
        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT, "candidate_packager",
            ),
        )
        structural, evidence, store = self._harness(files, subjects)
        try:
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(
                repo, "canonical_assembly/candidate_packager.py", files
            )
            fp = fingerprint_content(
                files["canonical_assembly/candidate_packager.py"]
            )
            claim = self._claim(
                "c-purpose", canon, m.PurposeValue("packs", ()), eref
            )
            rel = self._rel(
                "r-mem", canon, m.RelationshipKind.MEMBER_OF, root, eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=(claim,), relationships=(rel,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    ),
                ),
            ))
            direct = _resolve_query_subject(
                repo,
                m.SubjectSelector(
                    None, "canonical_assembly/candidate_packager.py",
                    (), None,
                ),
                structural=structural, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                direct.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            orientation, trace_root = _resolve_contextual_subjects(
                repo,
                m.SubjectSelector(
                    None, "canonical_assembly/candidate_packager.py",
                    (), None,
                ),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, canon
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                trace_root.candidates[0].subject.subject_id, root
            )
        finally:
            store.close()

    def test_membership_claim_representation_identical(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT, "candidate_packager",
            ),
        )
        structural, evidence, store = self._harness(files, subjects)
        try:
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(
                repo, "canonical_assembly/candidate_packager.py", files
            )
            fp = fingerprint_content(
                files["canonical_assembly/candidate_packager.py"]
            )
            claim = self._claim(
                "c-purpose", canon, m.PurposeValue("packs", ()), eref
            )
            membership = self._claim(
                "c-mem", canon,
                m.CapabilityMembershipValue(parent=root), eref,
                kind=m.ClaimKind.CAPABILITY_MEMBERSHIP,
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=(claim, membership),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.ClaimRef(id=membership.claim_id), eref, fp
                    ),
                ),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo,
                m.SubjectSelector(
                    None, "canonical_assembly/candidate_packager.py",
                    (), None,
                ),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, canon
            )
            self.assertEqual(
                trace_root.candidates[0].subject.subject_id, root
            )
        finally:
            store.close()

    def test_multiple_areas_common_root(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {
            "workflow/composition/a.py": "a=1\n",
            "workflow/canonical_assembly/b.py": "b=1\n",
        }
        structural, evidence, store = self._harness(files, ())
        try:
            comp = self._sid(repo, "composition")
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            deps = []
            claims = []
            rels = []
            for i, (path, sid) in enumerate((
                ("workflow/composition/a.py", comp),
                ("workflow/canonical_assembly/b.py", canon),
            )):
                eref = self._ref(repo, path, files)
                fp = fingerprint_content(files[path])
                claim = self._claim(
                    f"c-{i}", sid, m.PurposeValue(f"p{i}", ()), eref
                )
                rel = self._rel(
                    f"r-{i}", sid, m.RelationshipKind.MEMBER_OF,
                    root, eref,
                )
                claims.append(claim)
                rels.append(rel)
                deps.append(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp)
                )
                deps.append(
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    )
                )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(comp, "Composition", None),
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=tuple(claims), relationships=tuple(rels),
                evidence_dependencies=tuple(deps),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "workflow", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, root
            )
            self.assertEqual(
                trace_root.candidates[0].subject.subject_id, root
            )
        finally:
            store.close()

    def test_multiple_unrelated_roots_ambiguous(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"shared/a.py": "a=1\n", "shared/b.py": "b=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area_a = self._sid(repo, "area_a")
            area_b = self._sid(repo, "area_b")
            root_x = self._sid(
                repo, "feature_x", m.SubjectKind.SUBSYSTEM
            )
            root_y = self._sid(
                repo, "feature_y", m.SubjectKind.SUBSYSTEM
            )
            deps = []
            claims = []
            rels = []
            for i, (path, area, root) in enumerate((
                ("shared/a.py", area_a, root_x),
                ("shared/b.py", area_b, root_y),
            )):
                eref = self._ref(repo, path, files)
                fp = fingerprint_content(files[path])
                claim = self._claim(
                    f"c-{i}", area, m.PurposeValue(f"p{i}", ()), eref
                )
                rel = self._rel(
                    f"r-{i}", area, m.RelationshipKind.MEMBER_OF,
                    root, eref,
                )
                claims.append(claim)
                rels.append(rel)
                deps.append(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp)
                )
                deps.append(
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    )
                )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(area_a, "A", None),
                    m.Subject(area_b, "B", None),
                    m.Subject(root_x, "X", None),
                    m.Subject(root_y, "Y", None),
                ),
                claims=tuple(claims), relationships=tuple(rels),
                evidence_dependencies=tuple(deps),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "shared", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
        finally:
            store.close()

    def test_no_semantic_dependencies_not_found(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"lonely/file.py": "x=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "lonely/file.py", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.NOT_FOUND
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.NOT_FOUND
            )
        finally:
            store.close()

    def test_explicit_semantic_identity_precedence(self):
        repo = self.CTX
        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        file_sid = m.SubjectId(
            repository_id=repo, subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="canonical_assembly/candidate_packager.py",
        )
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT, "candidate_packager",
            ),
        )
        structural, evidence, store = self._harness(files, subjects)
        try:
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(
                repo, "canonical_assembly/candidate_packager.py", files
            )
            fp = fingerprint_content(
                files["canonical_assembly/candidate_packager.py"]
            )
            file_claim = self._claim(
                "c-file", file_sid, m.PurposeValue("file", ()), eref
            )
            canon_claim = self._claim(
                "c-canon", canon, m.PurposeValue("canon", ()), eref
            )
            cov = self._cq(
                file_sid, file_sid, m.SemanticQuestionClass.CQ_01,
                file_sid.canonical_locator,
                (m.ClaimRef(id=file_claim.claim_id),),
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(file_sid, "candidate_packager", None),
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=(file_claim, canon_claim),
                evidence_dependencies=(
                    self._dep(
                        m.ClaimRef(id=file_claim.claim_id), eref, fp
                    ),
                    self._dep(
                        m.ClaimRef(id=canon_claim.claim_id), eref, fp
                    ),
                ),
                coverage=(cov,),
            ))
            answer = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=repo,
                    target=m.SubjectSelector(
                        None, "canonical_assembly/candidate_packager.py",
                        (), None,
                    ),
                    bounds=self._bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(
                answer.subject_resolution.candidates[0].subject.subject_id,
                file_sid,
            )
        finally:
            store.close()

    def test_structural_failure_propagates(self):
        repo = self.CTX
        files = {"a.py": "x=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            state = structural.repository_state(repo)

            class _FailingStructural:
                def repository_state(self, repository_id):
                    return state

                def resolve_subject(
                    self, repository_id, target, bounds
                ):
                    raise ValueError("structural boom")

            with self.assertRaises(ValueError):
                ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=repo,
                        target=m.SubjectSelector(None, "a.py", (), None),
                        bounds=self._bounds(),
                    ),
                    structural=_FailingStructural(), evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_most_specific_common_ancestor(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"feat/a.py": "a=1\n", "feat/b.py": "b=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area_a = self._sid(repo, "area_a")
            area_b = self._sid(repo, "area_b")
            review = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            system = self._sid(
                repo, "larger_system", m.SubjectKind.SUBSYSTEM
            )
            deps = []
            claims = []
            rels = []
            for i, (path, area) in enumerate((
                ("feat/a.py", area_a), ("feat/b.py", area_b),
            )):
                eref = self._ref(repo, path, files)
                fp = fingerprint_content(files[path])
                claim = self._claim(
                    f"c-{i}", area, m.PurposeValue(f"p{i}", ()), eref
                )
                rel = self._rel(
                    f"r-{i}", area, m.RelationshipKind.MEMBER_OF,
                    review, eref,
                )
                claims.append(claim)
                rels.append(rel)
                deps.append(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp)
                )
                deps.append(
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    )
                )
            r_eref = self._ref(repo, "feat/a.py", files)
            r_fp = fingerprint_content(files["feat/a.py"])
            review_rel = self._rel(
                "r-review", review, m.RelationshipKind.MEMBER_OF,
                system, r_eref,
            )
            rels.append(review_rel)
            deps.append(
                self._dep(
                    m.RelationshipRef(id=review_rel.relationship_id),
                    r_eref, r_fp,
                )
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(area_a, "A", None),
                    m.Subject(area_b, "B", None),
                    m.Subject(review, "Review", None),
                    m.Subject(system, "System", None),
                ),
                claims=tuple(claims), relationships=tuple(rels),
                evidence_dependencies=tuple(deps),
            ))
            orientation, _ = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "feat", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, review
            )
        finally:
            store.close()

    def test_multi_parent_ambiguous(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"multi/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area = self._sid(repo, "area_a")
            feat_x = self._sid(
                repo, "feature_x", m.SubjectKind.SUBSYSTEM
            )
            feat_y = self._sid(
                repo, "feature_y", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(repo, "multi/a.py", files)
            fp = fingerprint_content(files["multi/a.py"])
            claim = self._claim(
                "c-a", area, m.PurposeValue("a", ()), eref
            )
            rel_x = self._rel(
                "r-x", area, m.RelationshipKind.MEMBER_OF, feat_x, eref
            )
            rel_y = self._rel(
                "r-y", area, m.RelationshipKind.MEMBER_OF, feat_y, eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(area, "A", None),
                    m.Subject(feat_x, "X", None),
                    m.Subject(feat_y, "Y", None),
                ),
                claims=(claim,), relationships=(rel_x, rel_y),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.RelationshipRef(id=rel_x.relationship_id),
                        eref, fp,
                    ),
                    self._dep(
                        m.RelationshipRef(id=rel_y.relationship_id),
                        eref, fp,
                    ),
                ),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "multi/a.py", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, area
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertEqual(len(trace_root.candidates), 2)
            self.assertFalse(trace_root.bound_info.truncated)
        finally:
            store.close()

    def test_parent_fanout_beyond_bounds_is_incomplete(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"multi/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area = self._sid(repo, "area_a")
            feat_x = self._sid(
                repo, "feature_x", m.SubjectKind.SUBSYSTEM
            )
            feat_y = self._sid(
                repo, "feature_y", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(repo, "multi/a.py", files)
            fp = fingerprint_content(files["multi/a.py"])
            claim = self._claim(
                "c-a", area, m.PurposeValue("a", ()), eref
            )
            rel_x = self._rel(
                "r-x", area, m.RelationshipKind.MEMBER_OF, feat_x, eref
            )
            rel_y = self._rel(
                "r-y", area, m.RelationshipKind.MEMBER_OF, feat_y, eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(area, "A", None),
                    m.Subject(feat_x, "X", None),
                    m.Subject(feat_y, "Y", None),
                ),
                claims=(claim,), relationships=(rel_x, rel_y),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.RelationshipRef(id=rel_x.relationship_id),
                        eref, fp,
                    ),
                    self._dep(
                        m.RelationshipRef(id=rel_y.relationship_id),
                        eref, fp,
                    ),
                ),
            ))
            bounds = self._bounds(max_subjects=1)
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "multi/a.py", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=bounds,
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(trace_root.bound_info.truncated)
            self.assertEqual(
                trace_root.bound_info.truncated_category, "context"
            )
            self.assertLessEqual(
                trace_root.bound_info.returned_results,
                trace_root.bound_info.requested_max_results,
            )
        finally:
            store.close()

    def test_contextual_candidates_use_non_exact_basis(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT, "candidate_packager",
            ),
        )
        structural, evidence, store = self._harness(files, subjects)
        try:
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(
                repo, "canonical_assembly/candidate_packager.py", files
            )
            fp = fingerprint_content(
                files["canonical_assembly/candidate_packager.py"]
            )
            claim = self._claim(
                "c-purpose", canon, m.PurposeValue("packs", ()), eref
            )
            rel = self._rel(
                "r-mem", canon, m.RelationshipKind.MEMBER_OF, root, eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=(claim,), relationships=(rel,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    ),
                ),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo,
                m.SubjectSelector(
                    None, "canonical_assembly/candidate_packager.py",
                    (), None,
                ),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            for resolution in (orientation, trace_root):
                for candidate in resolution.candidates:
                    self.assertIs(
                        candidate.rank_basis,
                        m.CandidateRankBasis.STRUCTURAL_PROXIMITY,
                    )
        finally:
            store.close()

    def test_bound_exhaustion_ambiguous(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"big/a.py": "a=1\n", "big/b.py": "b=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "big", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(max_results=1),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(orientation.bound_info.truncated)
            self.assertIn(
                orientation.bound_info.truncated_category,
                ("inventory", "context"),
            )
            answer = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=repo,
                    target=m.SubjectSelector(None, "big", (), None),
                    bounds=self._bounds(max_results=1),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            kinds = {
                req.kind for req in answer.resolution_requirements
            }
            self.assertIn(
                m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE, kinds
            )
        finally:
            store.close()

    def test_unknown_semantic_ref_fails_closed(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"g/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area = self._sid(repo, "area_g")
            eref = self._ref(repo, "g/a.py", files)
            fp = fingerprint_content(files["g/a.py"])
            claim = self._claim(
                "c-g", area, m.PurposeValue("g", ()), eref
            )
            ghost = m.EvidenceDependency(
                m.RelationshipRef(id=m.RelationshipId("r-ghost")),
                eref, fp,
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(m.Subject(area, "G", None),),
                claims=(claim,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    ghost,
                ),
            ))
            # Corrupt canonical state (dependency without its record)
            # must fail closed, never resolve from the surviving subset.
            with self.assertRaises(ValueError):
                _resolve_contextual_subjects(
                    repo, m.SubjectSelector(None, "g/a.py", (), None),
                    structural=structural, evidence=evidence, store=store,
                    bounds=self._bounds(),
                )
        finally:
            store.close()

    def test_missing_subject_row_does_not_collapse_ambiguity(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"m/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area_a = self._sid(repo, "area_a")
            area_b = self._sid(repo, "area_b")
            eref = self._ref(repo, "m/a.py", files)
            fp = fingerprint_content(files["m/a.py"])
            claim_a = self._claim(
                "c-a", area_a, m.PurposeValue("a", ()), eref
            )
            claim_b = self._claim(
                "c-b", area_b, m.PurposeValue("b", ()), eref
            )
            # Only area_a gets a canonical Subject row; area_b is
            # referenced by a persisted claim without one.
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(m.Subject(area_a, "A", None),),
                claims=(claim_a, claim_b),
                evidence_dependencies=(
                    self._dep(
                        m.ClaimRef(id=claim_a.claim_id), eref, fp
                    ),
                    self._dep(
                        m.ClaimRef(id=claim_b.claim_id), eref, fp
                    ),
                ),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "m/a.py", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(orientation.bound_info.truncated)
            self.assertEqual(
                orientation.bound_info.truncated_category, "context"
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
        finally:
            store.close()

    def test_expected_kinds_blocks_single_parent_promotion(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT, "candidate_packager",
            ),
        )
        structural, evidence, store = self._harness(files, subjects)
        try:
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(
                repo, "canonical_assembly/candidate_packager.py", files
            )
            fp = fingerprint_content(
                files["canonical_assembly/candidate_packager.py"]
            )
            claim = self._claim(
                "c-purpose", canon, m.PurposeValue("packs", ()), eref
            )
            rel = self._rel(
                "r-mem", canon, m.RelationshipKind.MEMBER_OF, root, eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=(claim,), relationships=(rel,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    ),
                ),
            ))
            selector = m.SubjectSelector(
                None, "canonical_assembly/candidate_packager.py",
                (m.SubjectKind.COMPONENT,), None,
            )
            orientation, trace_root = _resolve_contextual_subjects(
                repo, selector,
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, canon
            )
            # The SUBSYSTEM parent is outside expected_kinds: trace
            # must stay on the allowed local candidate.
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                trace_root.candidates[0].subject.subject_id, canon
            )
        finally:
            store.close()

    def test_expected_kinds_blocks_common_ancestor_resolution(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {
            "workflow/composition/a.py": "a=1\n",
            "workflow/canonical_assembly/b.py": "b=1\n",
        }
        structural, evidence, store = self._harness(files, ())
        try:
            comp = self._sid(repo, "composition")
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            deps = []
            claims = []
            rels = []
            for i, (path, sid) in enumerate((
                ("workflow/composition/a.py", comp),
                ("workflow/canonical_assembly/b.py", canon),
            )):
                eref = self._ref(repo, path, files)
                fp = fingerprint_content(files[path])
                claim = self._claim(
                    f"c-{i}", sid, m.PurposeValue(f"p{i}", ()), eref
                )
                rel = self._rel(
                    f"r-{i}", sid, m.RelationshipKind.MEMBER_OF,
                    root, eref,
                )
                claims.append(claim)
                rels.append(rel)
                deps.append(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp)
                )
                deps.append(
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    )
                )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(comp, "Composition", None),
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=tuple(claims), relationships=tuple(rels),
                evidence_dependencies=tuple(deps),
            ))
            selector = m.SubjectSelector(
                None, "workflow", (m.SubjectKind.COMPONENT,), None
            )
            orientation, trace_root = _resolve_contextual_subjects(
                repo, selector,
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            # The common ancestor is a SUBSYSTEM: it may not resolve
            # under a COMPONENT-only selector. Both stay ambiguous
            # over the allowed direct candidates.
            for resolution in (orientation, trace_root):
                self.assertIs(
                    resolution.ambiguity,
                    m.ResolutionAmbiguity.AMBIGUOUS,
                )
                self.assertFalse(resolution.bound_info.truncated)
                for candidate in resolution.candidates:
                    self.assertIs(
                        candidate.subject.subject_id.subject_kind,
                        m.SubjectKind.COMPONENT,
                    )
        finally:
            store.close()

    def test_fresh_token_stream_hits_paging_work_cap(self):
        import datetime
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"w/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            item = evidence.inventory_evidence(
                repo, m.EvidenceScope(paths=("w/a.py",), evidence_refs=()),
                self._bounds(),
            ).items[0]
            calls = []

            class _FreshTokenEvidence:
                def inventory_evidence(
                    self, repository_id, scope, bounds,
                    page_token=None,
                ):
                    calls.append(page_token)
                    token = f"tok-{len(calls)}"
                    return m.EvidenceInventoryPage(
                        items=(item,),
                        repository_state=m.RepositoryState(
                            repository_id=repo, revision_id=None,
                            dirty=False, state_fingerprint="fp",
                            observed_at=datetime.datetime.now(
                                datetime.timezone.utc
                            ),
                        ),
                        bound_info=m.BoundInfo(
                            requested_max_results=24,
                            requested_max_depth=0, returned_results=1,
                            truncated=True,
                            truncated_category="inventory",
                            continuation_token=token,
                        ),
                    )

            max_results = 3
            orientation, _ = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "w", (), None),
                structural=structural,
                evidence=_FreshTokenEvidence(), store=store,
                bounds=self._bounds(max_results=max_results),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(orientation.bound_info.truncated)
            # Distinct set stays at one forever; termination comes only
            # from the independent fetch-count ceiling.
            self.assertLessEqual(len(calls), max_results + 1)
        finally:
            store.close()
            store.close()

    def test_truncated_without_token_is_unproven(self):
        import datetime
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"t/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            item = evidence.inventory_evidence(
                repo, m.EvidenceScope(paths=("t/a.py",), evidence_refs=()),
                self._bounds(),
            ).items[0]

            class _NoTokenEvidence:
                def inventory_evidence(
                    self, repository_id, scope, bounds,
                    page_token=None,
                ):
                    return m.EvidenceInventoryPage(
                        items=(item,),
                        repository_state=m.RepositoryState(
                            repository_id=repo, revision_id=None,
                            dirty=False, state_fingerprint="fp",
                            observed_at=datetime.datetime.now(
                                datetime.timezone.utc
                            ),
                        ),
                        bound_info=m.BoundInfo(
                            requested_max_results=1,
                            requested_max_depth=0, returned_results=1,
                            truncated=True, truncated_category="inventory",
                            continuation_token=None,
                        ),
                    )

            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "t", (), None),
                structural=structural,
                evidence=_NoTokenEvidence(), store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(orientation.bound_info.truncated)
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
        finally:
            store.close()

    def test_continuation_token_cycle_is_unproven(self):
        import datetime
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"c/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            item = evidence.inventory_evidence(
                repo, m.EvidenceScope(paths=("c/a.py",), evidence_refs=()),
                self._bounds(),
            ).items[0]

            def _page(items, truncated, token):
                return m.EvidenceInventoryPage(
                    items=tuple(items),
                    repository_state=m.RepositoryState(
                        repository_id=repo, revision_id=None,
                        dirty=False, state_fingerprint="fp",
                        observed_at=datetime.datetime.now(
                            datetime.timezone.utc
                        ),
                    ),
                    bound_info=m.BoundInfo(
                        requested_max_results=24, requested_max_depth=0,
                        returned_results=len(items), truncated=truncated,
                        truncated_category=(
                            "inventory" if truncated else None
                        ),
                        continuation_token=token,
                    ),
                )

            pages = {
                None: _page((item,), True, "A"),
                # Non-empty identical duplicates: the only failure is
                # the repeated continuation state B -> A.
                "A": _page((item,), True, "B"),
                "B": _page((item,), True, "A"),
            }

            class _CyclingEvidence:
                def inventory_evidence(
                    self, repository_id, scope, bounds,
                    page_token=None,
                ):
                    return pages[page_token]

            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "c", (), None),
                structural=structural,
                evidence=_CyclingEvidence(), store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(orientation.bound_info.truncated)
        finally:
            store.close()

    def test_conflicting_evidence_identity_fails_closed(self):
        import datetime
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"k/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area = self._sid(repo, "area_k")
            eref = self._ref(repo, "k/a.py", files)
            fp = fingerprint_content(files["k/a.py"])
            claim = self._claim(
                "c-k", area, m.PurposeValue("k", ()), eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(m.Subject(area, "K", None),),
                claims=(claim,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                ),
            ))

            def _item(locator):
                return m.EvidenceInventoryItem(
                    evidence_ref=m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-k/a.py"),
                        repository_id=repo,
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator=locator,
                        revision_or_fingerprint="fp",
                    ),
                    content_fingerprint="fp",
                )

            class _ConflictingEvidence:
                def inventory_evidence(
                    self, repository_id, scope, bounds,
                    page_token=None,
                ):
                    return m.EvidenceInventoryPage(
                        items=(_item("k/a.py"), _item("k/renamed.py")),
                        repository_state=m.RepositoryState(
                            repository_id=repo, revision_id=None,
                            dirty=False, state_fingerprint="fp",
                            observed_at=datetime.datetime.now(
                                datetime.timezone.utc
                            ),
                        ),
                        bound_info=m.BoundInfo(
                            requested_max_results=24,
                            requested_max_depth=0, returned_results=2,
                            truncated=False, truncated_category=None,
                            continuation_token=None,
                        ),
                    )

            orientation, _ = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "k", (), None),
                structural=structural,
                evidence=_ConflictingEvidence(), store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
            self.assertTrue(orientation.bound_info.truncated)
        finally:
            store.close()

    def test_identical_duplicate_identity_does_not_consume_budget(self):
        import datetime
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"d/a.py": "a=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            area = self._sid(repo, "area_d")
            eref = self._ref(repo, "d/a.py", files)
            fp = fingerprint_content(files["d/a.py"])
            claim = self._claim(
                "c-d", area, m.PurposeValue("d", ()), eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(m.Subject(area, "D", None),),
                claims=(claim,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                ),
            ))
            item = evidence.inventory_evidence(
                repo, m.EvidenceScope(paths=("d/a.py",), evidence_refs=()),
                self._bounds(),
            ).items[0]

            class _DuplicatingEvidence:
                def inventory_evidence(
                    self, repository_id, scope, bounds,
                    page_token=None,
                ):
                    return m.EvidenceInventoryPage(
                        items=(item, item),
                        repository_state=m.RepositoryState(
                            repository_id=repo, revision_id=None,
                            dirty=False, state_fingerprint="fp",
                            observed_at=datetime.datetime.now(
                                datetime.timezone.utc
                            ),
                        ),
                        bound_info=m.BoundInfo(
                            requested_max_results=24,
                            requested_max_depth=0, returned_results=2,
                            truncated=False, truncated_category=None,
                            continuation_token=None,
                        ),
                    )

            orientation, _ = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "d/a.py", (), None),
                structural=structural,
                evidence=_DuplicatingEvidence(), store=store,
                bounds=self._bounds(max_results=1),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, area
            )
        finally:
            store.close()

    def test_arbitrary_endpoints_no_context(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"svc/local.py": "x=1\n"}
        structural, evidence, store = self._harness(files, ())
        try:
            local = self._sid(repo, "local_thing")
            shared = self._sid(repo, "shared_service")
            eref = self._ref(repo, "svc/local.py", files)
            fp = fingerprint_content(files["svc/local.py"])
            rel = self._rel(
                "r-dep", local, m.RelationshipKind.DEPENDS_ON,
                shared, eref,
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(local, "Local", None),
                    m.Subject(shared, "Shared", None),
                ),
                relationships=(rel,),
                evidence_dependencies=(
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    ),
                ),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo, m.SubjectSelector(None, "svc/local.py", (), None),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertIs(
                orientation.ambiguity, m.ResolutionAmbiguity.NOT_FOUND
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.NOT_FOUND
            )
        finally:
            store.close()

    def test_noncurrent_membership_no_redirect(self):
        from span.service.resolution import _resolve_contextual_subjects
        repo = self.CTX
        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT, "candidate_packager",
            ),
        )
        structural, evidence, store = self._harness(files, subjects)
        try:
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(
                repo, "canonical_assembly/candidate_packager.py", files
            )
            fp = fingerprint_content(
                files["canonical_assembly/candidate_packager.py"]
            )
            claim = self._claim(
                "c-purpose", canon, m.PurposeValue("packs", ()), eref
            )
            rel = self._rel(
                "r-mem", canon, m.RelationshipKind.MEMBER_OF, root, eref
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=(claim,), relationships=(rel,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, "stale-fingerprint",
                    ),
                ),
            ))
            orientation, trace_root = _resolve_contextual_subjects(
                repo,
                m.SubjectSelector(
                    None, "canonical_assembly/candidate_packager.py",
                    (), None,
                ),
                structural=structural, evidence=evidence, store=store,
                bounds=self._bounds(),
            )
            self.assertEqual(
                orientation.candidates[0].subject.subject_id, canon
            )
            self.assertIs(
                trace_root.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            self.assertEqual(
                trace_root.candidates[0].subject.subject_id, canon
            )
        finally:
            store.close()

    def test_explain_operation_path(self):
        repo = self.CTX
        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT, "candidate_packager",
            ),
        )
        structural, evidence, store = self._harness(files, subjects)
        try:
            canon = self._sid(repo, "canonical_assembly")
            root = self._sid(
                repo, "review_workflow", m.SubjectKind.SUBSYSTEM
            )
            eref = self._ref(
                repo, "canonical_assembly/candidate_packager.py", files
            )
            fp = fingerprint_content(
                files["canonical_assembly/candidate_packager.py"]
            )
            claim = self._claim(
                "c-purpose", canon, m.PurposeValue("packs", ()), eref
            )
            rel = self._rel(
                "r-mem", canon, m.RelationshipKind.MEMBER_OF, root, eref
            )
            cov = self._cq(
                canon, canon, m.SemanticQuestionClass.CQ_01,
                canon.canonical_locator,
                (m.ClaimRef(id=claim.claim_id),),
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                ),
                claims=(claim,), relationships=(rel,),
                evidence_dependencies=(
                    self._dep(m.ClaimRef(id=claim.claim_id), eref, fp),
                    self._dep(
                        m.RelationshipRef(id=rel.relationship_id),
                        eref, fp,
                    ),
                ),
                coverage=(cov,),
            ))
            answer = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=repo,
                    target=m.SubjectSelector(
                        None, "canonical_assembly/candidate_packager.py",
                        (), None,
                    ),
                    bounds=self._bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(
                answer.subject_resolution.candidates[0].subject.subject_id,
                canon,
            )
            self.assertTrue(answer.content.claims)
            kinds = {
                r.kind for r in answer.content.relationships
            }
            self.assertIn(m.RelationshipKind.MEMBER_OF, kinds)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
