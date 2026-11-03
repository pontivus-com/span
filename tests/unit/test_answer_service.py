"""Answer composition and document view (FD-23–FD-29)."""

from __future__ import annotations

import datetime
import hashlib
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.service.answer import AnswerService
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.evidence import EvidenceService
from span.service.support import SupportService
from span.shell.sqlite_store.lifecycle import LifecycleStore

NOW = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)
CONTEXT_ID = m.InvestigationContextId("ctx-1")


def _basis() -> m.SemanticBasis:
    return m.SemanticBasis(
        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        summary="read",
        input_refs=(),
    )


class AnswerServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "repo"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src/a.py").write_text("a\n", encoding="utf-8")
        self.store = LifecycleStore(
            pathlib.Path(self._tmp.name) / "lifecycle.db",
            retention=RETENTION,
            clock=lambda: NOW,
        )
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", str(self.root))
        self.store.put_context(
            m.InvestigationContext(
                context_id=CONTEXT_ID,
                repository_id="repo-1",
                request_id=m.RequestId("req-1"),
                request_digest=m.ContentDigest("sha256:request"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(),
                created_at=NOW,
                expires_at=NOW + RETENTION.context_lifetime,
            )
        )
        self.evidence = FilesystemEvidenceSource("repo-1", self.root)
        self.support = SupportService(
            store=self.store,
            evidence=self.evidence,
            authority=self.store,
            clock=lambda: NOW,
        )
        self.service = AnswerService(
            store=self.store,
            support=self.support,
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
        )
        self._observation("obs-a", "src/a.py")
        self._create("u-a", "src/a.py", "What does A do?")

    def _observation(self, observation_id: str, locator: str) -> None:
        data = (self.root / locator).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        self.store.put_source_observation(
            m.SourceObservation(
                observation_id=m.SourceObservationId(observation_id),
                repository_id="repo-1",
                evidence=m.EvidenceRef(
                    evidence_id=m.EvidenceId(f"ev-{locator}"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator=locator,
                    revision_or_fingerprint=digest,
                ),
                content_digest=m.ContentDigest(f"sha256:{digest}"),
                captured_at=NOW,
                total_lines=1,
                whole_file=True,
                excerpt=data.decode("utf-8"),
            )
        )

    def _create(
        self,
        understanding_id: str,
        locator: str,
        question: str,
        *,
        conclusions: int = 1,
    ) -> None:
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId(f"req-{understanding_id}"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator=locator,
                ),
                target=m.ExplicitTarget(
                    question=question,
                    scope=m.EvidenceScope(paths=(locator,)),
                ),
                conclusions=tuple(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId(f"c-{index}"),
                        statement=f"A does X number {index}.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=(locator,)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-a")
                            ),
                        ),
                        basis=_basis(),
                    )
                    for index in range(1, conclusions + 1)
                ),
            ),
            understanding_id=m.UnderstandingId(understanding_id),
        )

    def _service(self, max_bytes: int) -> AnswerService:
        bounds = m.QueryBounds(
            max_results=50,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=24,
            max_evidence_bytes=max_bytes,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )
        return AnswerService(
            store=self.store,
            support=self.support,
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=bounds,
                maximum_query_bounds=bounds,
                hook_fast_bounds=bounds,
                max_response_bytes=max_bytes,
            ),
        )

    def _ask(self, reference: str, question: str | None, request_id: str = "req-ask"):
        return self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id=request_id,
                reference=reference,
                question=question,
            )
        )

    def test_declared_surface_status_counts_unexamined_members(self) -> None:
        (self.root / "src/b.py").write_text("b\n", encoding="utf-8")
        service_surface = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.SERVICE, locator="svc"
        )
        self.store.put_surface(
            m.Surface(
                key=service_surface,
                boundary=m.SurfaceBoundary(paths=("src",)),
            )
        )
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-svc"),
                    context_id=CONTEXT_ID,
                ),
                surface=service_surface,
                target=m.ExplicitTarget(
                    question="What does the service do?",
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="The service exposes A.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-a")
                            ),
                        ),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-svc"),
        )
        result = self._ask("svc", "What does the service do?")
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(result.status.unexamined, 1)
        self.assertTrue(result.status.unexamined_limited)
        self.assertEqual(result.status.descendants, ())

    def test_descendant_status_is_reported_separately(self) -> None:
        parent = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.DOMAIN, locator="domain"
        )
        child = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.SERVICE, locator="svc"
        )
        self.store.put_surface(
            m.Surface(
                key=parent,
                boundary=m.SurfaceBoundary(paths=("src",)),
            )
        )
        self.store.put_surface(
            m.Surface(
                key=child,
                boundary=m.SurfaceBoundary(paths=("src",)),
                parent=parent,
            )
        )
        for key, understanding_id, request in (
            (parent, "u-domain", "req-domain"),
            (child, "u-child", "req-child"),
        ):
            self.store.record_understanding(
                m.CreateUnderstandingCommand(
                    identity=m.RecordingIdentity(
                        repository_id="repo-1",
                        request_id=m.RequestId(request),
                        context_id=CONTEXT_ID,
                    ),
                    surface=key,
                    target=m.ExplicitTarget(
                        question=f"What does {key.locator} do?",
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                    ),
                    conclusions=(
                        m.ProposedConclusion(
                            conclusion_id=m.ConclusionId("c-1"),
                            statement="It exposes A.",
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            scope=m.EvidenceScope(paths=("src/a.py",)),
                            support=(
                                m.SourceSupport(
                                    observation_id=m.SourceObservationId("obs-a")
                                ),
                            ),
                            basis=_basis(),
                        ),
                    ),
                ),
                understanding_id=m.UnderstandingId(understanding_id),
            )
        result = self._ask("domain", "What does domain do?")
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(len(result.status.descendants), 1)
        self.assertEqual(result.status.descendants[0].surface, child)
        self.assertEqual(result.status.current, 1)
        self.assertEqual(result.status.descendants[0].current, 1)

    def test_ranged_support_ignores_an_unrelated_edit(self) -> None:
        (self.root / "src/a.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
        evidence = EvidenceService(
            store=self.store, evidence=self.evidence, clock=lambda: NOW
        )
        context = self.store.get_context(CONTEXT_ID.value)
        admission = evidence.admit(
            context,
            (m.EvidenceRequest("src/a.py", ranges=(m.SourceRange(1, 2),)),),
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
        )
        observation = next(
            item.observation_id
            for item in admission.outcomes
            if isinstance(item, m.AdmittedEvidence)
        )
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-range"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/a.py",
                ),
                target=m.ExplicitTarget(
                    question="What are the first two lines?",
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="The first two lines are one and two.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(m.SourceSupport(observation_id=observation),),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-range"),
        )
        first = self._ask("src/a.py", "What are the first two lines?")
        self.assertIsInstance(first, m.Answer)
        (self.root / "src/a.py").write_text("one\ntwo\nchanged\n", encoding="utf-8")
        after_unrelated = self._ask("src/a.py", "What are the first two lines?")
        self.assertIsInstance(after_unrelated, m.Answer)
        (self.root / "src/a.py").write_text("changed\ntwo\nchanged\n", encoding="utf-8")
        after_range = self._ask("src/a.py", "What are the first two lines?")
        self.assertIsInstance(after_range, m.Gap)
        assert isinstance(after_range, m.Gap)
        self.assertEqual(after_range.reason, m.GapReason.INVALIDATED)

    def test_unbound_range_falls_back_to_the_whole_file(self) -> None:
        (self.root / "src/a.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
        evidence = EvidenceService(
            store=self.store, evidence=self.evidence, clock=lambda: NOW
        )
        context = self.store.get_context(CONTEXT_ID.value)
        admission = evidence.admit(
            context,
            (m.EvidenceRequest("src/a.py", ranges=(m.SourceRange(2, 3),)),),
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
        )
        observation = next(
            item.observation_id
            for item in admission.outcomes
            if isinstance(item, m.AdmittedEvidence)
        )
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-unbound"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/a.py",
                ),
                target=m.ExplicitTarget(
                    question="What are the last two lines?",
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="The last two lines are two and three.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(m.SourceSupport(observation_id=observation),),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-unbound"),
        )
        # The range can no longer bind; the whole file still matches.
        (self.root / "src/a.py").write_text("one\ntwo\n", encoding="utf-8")
        unbound = self._ask("src/a.py", "What are the last two lines?")
        self.assertIsInstance(unbound, m.Gap)
        assert isinstance(unbound, m.Gap)
        self.assertEqual(unbound.reason, m.GapReason.INVALIDATED)
        (self.root / "src/a.py").write_text("zero\ntwo\n", encoding="utf-8")
        changed = self._ask("src/a.py", "What are the last two lines?")
        self.assertIsInstance(changed, m.Gap)

    def test_legacy_ranged_row_is_validated_against_the_whole_file(self) -> None:
        path = self.root / "src/a.py"
        path.write_text("one\ntwo\nthree\n", encoding="utf-8")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        self.store.put_source_observation(
            m.SourceObservation(
                observation_id=m.SourceObservationId("obs-legacy"),
                repository_id="repo-1",
                evidence=m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-legacy"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator="src/a.py",
                    revision_or_fingerprint=digest,
                ),
                content_digest=m.ContentDigest(f"sha256:{digest}"),
                captured_at=NOW,
                total_lines=3,
                delivered_ranges=(m.SourceRange(1, 2),),
                whole_file=False,
                excerpt="one\ntwo\n",
            )
        )
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-legacy"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/a.py",
                ),
                target=m.ExplicitTarget(
                    question="What are the first two lines?",
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="The first two lines are one and two.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-legacy")
                            ),
                        ),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-legacy"),
        )
        path.write_text("one\ntwo\nchanged\n", encoding="utf-8")
        result = self._ask("src/a.py", "What are the first two lines?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.INVALIDATED)

    def test_current_content_is_an_answer(self) -> None:
        result = self._ask("src/a.py", "What does A do?")
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(result.question, "What does A do?")
        self.assertEqual(len(result.conclusions), 1)
        self.assertEqual(result.status.current, 1)

    def test_changed_source_is_an_invalidated_gap(self) -> None:
        (self.root / "src/a.py").write_text("changed\n", encoding="utf-8")
        result = self._ask("src/a.py", "What does A do?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.INVALIDATED)
        self.assertEqual(len(result.historical), 1)

    def test_unknown_surface_is_unassessed(self) -> None:
        result = self._ask("src/missing.py", "What does it do?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.UNASSESSED)

    def test_question_without_match_is_no_match(self) -> None:
        result = self._ask("src/a.py", "What else?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.NO_MATCH)

    def test_no_match_gap_names_document_view(self) -> None:
        result = self._ask("src/a.py", "Why does A exist?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.NO_MATCH)
        self.assertIn("without a question", result.recovery)
        self.assertIn("document view", result.recovery)

    def test_surface_document_view_is_reuse_path(self) -> None:
        result = self._ask("src/a.py", None)
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(result.question, "")
        self.assertEqual(
            [group.question for group in result.groups],
            ["What does A do?"],
        )

    def test_verification_run_appears_only_on_its_scope(self) -> None:
        verification_context = m.InvestigationContextId("ctx-ver")
        self.store.put_context(
            m.InvestigationContext(
                context_id=verification_context,
                repository_id="repo-1",
                request_id=m.RequestId("req-ver"),
                request_digest=m.ContentDigest("sha256:ver"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(),
                created_at=NOW,
                expires_at=NOW + RETENTION.context_lifetime,
            )
        )
        self.store.record_verification(
            m.RecordVerificationCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-ver"),
                    context_id=verification_context,
                ),
                run=m.ProposedVerificationRun(
                    repository_id="repo-1",
                    scope=m.VerificationScope(
                        description="a only",
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                    ),
                    observations=(m.SourceObservationId("obs-a"),),
                    command="python3 -m unittest",
                    scenario=None,
                    outcome=m.VerificationOutcome.PASS,
                    observed_at=NOW,
                    observer="test",
                ),
            )
        )
        on_scope = self._ask("src/a.py", "What does A do?")
        assert isinstance(on_scope, m.Answer)
        self.assertEqual(len(on_scope.verification), 1)

        (self.root / "src/b.py").write_text("b\n", encoding="utf-8")
        self._observation("obs-b", "src/b.py")
        self._create("u-b", "src/b.py", "What does B do?")
        off_scope = self._ask("src/b.py", "What does B do?", "req-ask-b")
        assert isinstance(off_scope, m.Answer)
        self.assertEqual(off_scope.verification, ())

    def test_multiple_granularities_are_ambiguous(self) -> None:
        self.store.put_surface(
            m.Surface(
                key=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.SERVICE,
                    locator="svc",
                ),
                boundary=m.SurfaceBoundary(paths=("src",)),
            )
        )
        result = self._ask("src/a.py", "What does A do?")
        self.assertIsInstance(result, m.AmbiguousSurface)
        assert isinstance(result, m.AmbiguousSurface)
        self.assertIn(m.SurfaceKind.SERVICE, [item.kind for item in result.candidates])

    def test_oversized_answer_states_every_omission(self) -> None:
        (self.root / "src/b.py").write_text("b\n", encoding="utf-8")
        self._observation("obs-b", "src/b.py")
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-wide"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/b.py",
                ),
                target=m.ExplicitTarget(
                    question="What does B do?",
                    scope=m.EvidenceScope(paths=("src/b.py",)),
                ),
                conclusions=tuple(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId(f"x-{index}"),
                        statement=f"Extra finding {index}.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/b.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-b")
                            ),
                        ),
                        basis=_basis(),
                    )
                    for index in range(1, 15)
                ),
            ),
            understanding_id=m.UnderstandingId("u-wide"),
        )
        result = self._service(3_000).ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-fit",
                reference="src/b.py",
                question="What does B do?",
            )
        )
        assert isinstance(result, m.Answer)
        self.assertTrue(result.truncated)
        self.assertTrue(result.omitted)
        self.assertTrue(result.conclusions)
        self.assertIn("u-wide", result.references)

    def test_budget_below_minimum_is_refused(self) -> None:
        result = self._service(10).ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-tiny",
                reference="src/a.py",
                question="What does A do?",
            )
        )
        assert isinstance(result, m.Unavailable)
        self.assertIn("budget", result.failure)
        self.assertTrue(result.recovery)

    def test_no_question_groups_current_content(self) -> None:
        result = self._ask("src/a.py", None)
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(result.question, "")
        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[0].question, "What does A do?")

    def test_exact_surface_resolves_by_identity(self) -> None:
        result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-exact",
                surface=m.SurfaceReference(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                question="What does A do?",
            )
        )
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(result.surface.locator, "src/a.py")
        self.assertEqual(result.conclusions[0].ref.understanding_id.value, "u-a")
        self.assertEqual(result.conclusions[0].statement, "A does X number 1.")

    def test_ambiguous_reference_is_resolved_by_exact_surface(self) -> None:
        self.store.put_surface(
            m.Surface(
                key=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.SERVICE,
                    locator="svc",
                ),
                boundary=m.SurfaceBoundary(paths=("src",)),
            )
        )
        ambiguous = self._ask("src/a.py", "What does A do?")
        self.assertIsInstance(ambiguous, m.AmbiguousSurface)
        assert isinstance(ambiguous, m.AmbiguousSurface)
        selected = next(
            item for item in ambiguous.candidates if item.kind is m.SurfaceKind.FILE
        )
        resolved = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-copy",
                surface=m.SurfaceReference(
                    kind=selected.kind,
                    locator=selected.locator,
                    repository_id=selected.repository_id,
                ),
                question="What does A do?",
            )
        )
        self.assertIsInstance(resolved, m.Answer)

    def test_gap_continuation_returns_an_evidence_page(self) -> None:
        (self.root / "src/big.py").write_text("line\n" * 400, encoding="utf-8")
        import dataclasses

        bounds = dataclasses.replace(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            max_evidence_bytes=100_000,
        )
        policy = m.ServiceBoundsPolicy(
            default_query_bounds=bounds,
            maximum_query_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
            hook_fast_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds,
            max_response_bytes=1500,
        )
        service = AnswerService(
            store=self.store,
            support=self.support,
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            policy=policy,
        )
        first = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-page",
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.FILE, locator="src/big.py"
                ),
                question="What is here?",
            )
        )
        self.assertIsInstance(first, m.Gap)
        assert isinstance(first, m.Gap)
        self.assertTrue(first.continuation)
        page = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                continuation=first.continuation,
            )
        )
        self.assertIsInstance(page, m.EvidencePage)
        assert isinstance(page, m.EvidencePage)
        self.assertTrue(page.evidence)

    def test_snapshot_selector_returns_history_not_an_answer(self) -> None:
        result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                selector=m.UnderstandingSnapshotSelector(
                    repository_id="repo-1", understanding_id="u-a", version=1
                ),
            )
        )
        self.assertIsInstance(result, m.RetrievedUnderstanding)
        self.assertNotIsInstance(result, m.Answer)

    def test_receipt_selector_returns_history_not_an_answer(self) -> None:
        result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                selector=m.ReceiptRetrievalSelector(
                    repository_id="repo-1", request_id="req-u-a"
                ),
            )
        )
        self.assertIsInstance(result, m.RetrievedReceipt)
        self.assertNotIsInstance(result, m.Answer)

    def _page_service(self, *, clock=None):
        import dataclasses

        bounds = dataclasses.replace(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            max_evidence_bytes=100_000,
        )
        return AnswerService(
            store=self.store,
            support=self.support,
            evidence=EvidenceService(
                store=self.store, evidence=self.evidence, clock=clock
            ),
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=bounds,
                maximum_query_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
                hook_fast_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds,
                max_response_bytes=1500,
            ),
            clock=clock,
        )

    def _cold_page(self, service):
        (self.root / "src/big.py").write_text("line\n" * 400, encoding="utf-8")
        first = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-page",
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.FILE, locator="src/big.py"
                ),
                question="What is here?",
            )
        )
        assert isinstance(first, m.Gap)
        self.assertTrue(first.continuation)
        return first

    def test_continuation_replay_is_stable(self) -> None:
        service = self._page_service()
        first = self._cold_page(service)
        page = service.ask(
            m.AskRequest(repository_id="repo-1", continuation=first.continuation)
        )
        again = service.ask(
            m.AskRequest(repository_id="repo-1", continuation=first.continuation)
        )
        self.assertIsInstance(page, m.EvidencePage)
        self.assertEqual(page, again)

    def test_abandoned_context_rejects_the_continuation(self) -> None:
        service = self._page_service()
        first = self._cold_page(service)
        assert first.context is not None
        self.store.abandon_context(first.context.value)
        page = service.ask(
            m.AskRequest(repository_id="repo-1", continuation=first.continuation)
        )
        self.assertIsInstance(page, m.Unavailable)

    def test_expired_context_rejects_the_continuation(self) -> None:
        now = [NOW]
        service = self._page_service(clock=lambda: now[0])
        first = self._cold_page(service)
        now[0] = NOW + datetime.timedelta(hours=2)
        page = service.ask(
            m.AskRequest(repository_id="repo-1", continuation=first.continuation)
        )
        self.assertIsInstance(page, m.Unavailable)

    def test_wrong_repository_continuation_is_rejected(self) -> None:
        self.store.register_repository("repo-2", str(self.root))
        service = self._page_service()
        first = self._cold_page(service)
        page = service.ask(
            m.AskRequest(repository_id="repo-2", continuation=first.continuation)
        )
        self.assertIsInstance(page, m.Unavailable)

    def test_one_line_too_large_is_refused(self) -> None:
        import dataclasses

        (self.root / "src/huge.py").write_text("x" * 5000 + "\n", encoding="utf-8")
        bounds = dataclasses.replace(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            max_evidence_bytes=100_000,
        )
        service = AnswerService(
            store=self.store,
            support=self.support,
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=bounds,
                maximum_query_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
                hook_fast_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds,
                max_response_bytes=1500,
            ),
        )
        first = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-huge",
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.FILE, locator="src/huge.py"
                ),
                question="What is here?",
            )
        )
        assert isinstance(first, m.Gap)
        page = service.ask(
            m.AskRequest(repository_id="repo-1", continuation=first.continuation)
        )
        self.assertIsInstance(page, m.Unavailable)
