"""Answer composition and document view (FD-23–FD-29)."""

from __future__ import annotations

import datetime
import hashlib
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.core.recording import RecordingValidationError
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.service.answer import AnswerService
from span.service.understand import UnderstandService
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.continuation import ContinuationCursor, encode_continuation
from span.service.evidence import EvidenceService
from span.service.support import SupportService
from span.shell.sqlite_store.lifecycle import LifecycleStore
from tests.support.functional_pyramid import functional_pyramid_view

NOW = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)
CONTEXT_ID = m.InvestigationContextId("ctx-1")
PAGED_SOURCE = "line\n" * 400
PAGED_RESPONSE_BUDGET = len(PAGED_SOURCE.encode("utf-8")) - 1


def _basis() -> m.SemanticBasis:
    return m.SemanticBasis(
        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        summary="read",
        input_refs=(),
    )


def _unconfigured_orientation(
    _repository_id: str,
    _surface: m.SurfaceKey,
    _scope: m.EvidenceScope | None,
) -> m.FunctionalPyramidParticipation:
    return m.FunctionalPyramidParticipation(
        m.FunctionalPyramidParticipationState.UNCONFIGURED
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
                binding_digest=m.ContentDigest("sha256:request"),
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
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            functional_pyramid_orientation=_unconfigured_orientation,
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
            )
        )

    def _create(
        self,
        understanding_id: str,
        locator: str,
        question: str,
        *,
        conclusions: int = 1,
        curate: bool = True,
        observation_id: str = "obs-a",
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
                                observation_id=m.SourceObservationId(observation_id)
                            ),
                        ),
                        basis=_basis(),
                    )
                    for index in range(1, conclusions + 1)
                ),
            ),
            understanding_id=m.UnderstandingId(understanding_id),
        )
        if curate:
            self._curate(understanding_id)

    def _curate(self, understanding_id: str, *, request_id: str | None = None) -> None:
        understanding = self.store.get_understanding(understanding_id)
        version = self.store.get_version(
            understanding_id,
            understanding.current_version.value,
        )
        self.store.record_understanding(
            m.UpdateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId(
                        request_id
                        or f"curate-{understanding_id}-{version.version.value}"
                    ),
                    context_id=CONTEXT_ID,
                ),
                understanding_id=m.UnderstandingId(understanding_id),
                expected_version=version.version,
                curate=tuple(
                    m.CurateConclusion(
                        conclusion_id=ref.conclusion_id,
                        reasoning="reviewed for shared reuse",
                    )
                    for ref in version.conclusions
                ),
                provenance="test-reviewer",
            )
        )

    def _service(
        self,
        max_bytes: int,
        *,
        max_results: int = 50,
        store: LifecycleStore | None = None,
        support: SupportService | None = None,
    ) -> AnswerService:
        selected_store = self.store if store is None else store
        selected_support = self.support if support is None else support
        bounds = m.QueryBounds(
            max_results=max_results,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=24,
            max_evidence_bytes=max_bytes,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )
        return AnswerService(
            store=selected_store,
            support=selected_support,
            understand=UnderstandService(
                store=selected_store, support=selected_support
            ),
            evidence=EvidenceService(store=selected_store, evidence=self.evidence),
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=bounds,
                maximum_query_bounds=bounds,
                hook_fast_bounds=bounds,
                max_response_bytes=max_bytes,
            ),
            functional_pyramid_orientation=_unconfigured_orientation,
        )

    def _ask(self, reference: str, question: str | None, request_id: str = "req-ask"):
        del question, request_id
        return self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                reference=reference,
            )
        )

    def test_oversized_governing_view_is_truncated_not_refused(self) -> None:
        (self.root / "src/c.py").write_text("c\n", encoding="utf-8")
        placements = tuple(
            m.FunctionalDocumentPlacement(
                "repo-1",
                m.FunctionalDocumentRef(
                    repository_id="repo-1",
                    document_ref=f"docs/foundation-{index}.md",
                    layer=m.FunctionalPyramidLayer.P0,
                ),
                ".",
            )
            for index in range(1200)
        )
        view = m.FunctionalPyramidView(
            pyramid_id=m.FunctionalPyramidId("fp"),
            version=m.FunctionalPyramidVersion(1),
            status=m.FunctionalPyramidRouteStatus.RESOLVED,
            semantic_scope=m.EvidenceScope(paths=("src/c.py",)),
            placements=placements,
            declared_layers=(m.FunctionalPyramidLayer.P0,),
            absent_layers=tuple(
                layer
                for layer in m.FunctionalPyramidLayer
                if layer is not m.FunctionalPyramidLayer.P0
            ),
        )

        def orientation(
            _repository_id: str,
            _surface: m.SurfaceKey,
            _scope: m.EvidenceScope | None,
        ) -> m.FunctionalPyramidView:
            return view

        service = AnswerService(
            store=self.store,
            support=self.support,
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            functional_pyramid_orientation=orientation,
        )
        result = service.ask(m.AskRequest(repository_id="repo-1", reference="src/c.py"))
        self.assertIsInstance(result, m.Gap)
        self.assertTrue(result.truncated)
        self.assertIsInstance(result.functional_pyramid, m.FunctionalPyramidView)
        governing = result.functional_pyramid
        assert isinstance(governing, m.FunctionalPyramidView)
        self.assertTrue(governing.truncated)
        self.assertTrue(governing.omitted)
        self.assertLess(len(governing.placements), len(placements))
        self.assertEqual(governing.unresolved, ())

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
        self._curate("u-svc")
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
            self._curate(understanding_id)
        result = self._ask("domain", "What does domain do?")
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(len(result.status.descendants), 1)
        self.assertEqual(result.status.descendants[0].surface, child)
        self.assertEqual(result.status.current, 1)
        self.assertEqual(result.status.descendants[0].current, 1)

    def test_descendant_stale_ref_is_not_merged_into_parent(self) -> None:
        (self.root / "src/b.py").write_text("b\n", encoding="utf-8")
        self._observation("obs-b", "src/b.py")
        parent = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.DOMAIN, locator="domain"
        )
        child = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.SERVICE, locator="svc"
        )
        self.store.put_surface(
            m.Surface(key=parent, boundary=m.SurfaceBoundary(paths=("src",)))
        )
        self.store.put_surface(
            m.Surface(
                key=child,
                boundary=m.SurfaceBoundary(paths=("src",)),
                parent=parent,
            )
        )
        self._create_on_surface("u-domain", parent, "What does domain do?")
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-child-stale"),
                    context_id=CONTEXT_ID,
                ),
                surface=child,
                target=m.ExplicitTarget(
                    question="What does svc do?",
                    scope=m.EvidenceScope(paths=("src/a.py", "src/b.py")),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="A does X.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-a")
                            ),
                        ),
                        basis=_basis(),
                    ),
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-2"),
                        statement="B does Y.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/b.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-b")
                            ),
                        ),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-child-stale"),
        )
        self._curate("u-child-stale")
        (self.root / "src/b.py").write_text("changed\n", encoding="utf-8")
        result = self._ask("domain", "What does domain do?")
        assert isinstance(result, m.Answer)
        self.assertEqual(result.status.stale, 0)
        self.assertEqual(result.status.stale_refs, ())
        self.assertEqual(len(result.status.descendants), 1)
        child_status = result.status.descendants[0]
        self.assertEqual(child_status.surface, child)
        self.assertEqual(child_status.stale, 1)
        self.assertEqual(child_status.stale_refs[0].ref.conclusion_id.value, "c-2")

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
        self._curate("u-range")
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
        self._curate("u-unbound")
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
        self._curate("u-legacy")
        path.write_text("one\ntwo\nchanged\n", encoding="utf-8")
        result = self._ask("src/a.py", "What are the first two lines?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.INVALIDATED)

    def test_current_content_is_an_answer(self) -> None:
        result = self._ask("src/a.py", "What does A do?")
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(
            sum(len(group.conclusions) for group in result.groups),
            1,
        )
        self.assertEqual(result.status.current, 1)

    def test_current_capture_is_pending_until_curated(self) -> None:
        path = self.root / "src/pending.py"
        path.write_text("pending\n", encoding="utf-8")
        self._observation("obs-pending", "src/pending.py")
        self._create(
            "u-pending",
            "src/pending.py",
            "What does pending do?",
            curate=False,
            observation_id="obs-pending",
        )
        selector = m.CurrentUnderstandingSelector(
            repository_id="repo-1",
            understanding_id="u-pending",
        )

        captured = self.service.ask(m.AskRequest(selector=selector))
        self.assertIsInstance(captured, m.Gap)
        assert isinstance(captured, m.Gap)
        self.assertIs(captured.reason, m.GapReason.PENDING_CURATION)
        self.assertEqual(captured.status.current, 0)
        self.assertEqual(captured.status.pending, 1)
        self.assertEqual(
            captured.status.pending_refs[0].ref.understanding_id.value,
            "u-pending",
        )

        self._curate("u-pending")
        curated = self.service.ask(m.AskRequest(selector=selector))
        self.assertIsInstance(curated, m.Answer)
        assert isinstance(curated, m.Answer)
        self.assertEqual(curated.status.current, 1)
        self.assertEqual(curated.status.pending, 0)
        self.assertEqual(len(curated.conclusions), 1)

    def test_mixed_curated_and_captured_surface_exposes_only_curated_answer(
        self,
    ) -> None:
        path = self.root / "src/mixed.py"
        path.write_text("mixed\n", encoding="utf-8")
        self._observation("obs-mixed", "src/mixed.py")
        self._create(
            "u-mixed-curated",
            "src/mixed.py",
            "What is stable?",
            observation_id="obs-mixed",
        )
        self._create(
            "u-mixed-pending",
            "src/mixed.py",
            "What still needs review?",
            curate=False,
            observation_id="obs-mixed",
        )

        result = self.service.ask(
            m.AskRequest(repository_id="repo-1", reference="src/mixed.py")
        )
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(result.status.current, 1)
        self.assertEqual(result.status.pending, 1)
        self.assertEqual(
            tuple(group.question for group in result.groups),
            ("What is stable?",),
        )

    def test_noncurrent_capture_is_stale_not_pending(self) -> None:
        path = self.root / "src/stale-capture.py"
        path.write_text("before\n", encoding="utf-8")
        self._observation("obs-stale-capture", "src/stale-capture.py")
        self._create(
            "u-stale-capture",
            "src/stale-capture.py",
            "What did this file do?",
            curate=False,
            observation_id="obs-stale-capture",
        )
        path.write_text("after\n", encoding="utf-8")

        result = self.service.ask(
            m.AskRequest(
                selector=m.CurrentUnderstandingSelector(
                    repository_id="repo-1",
                    understanding_id="u-stale-capture",
                )
            )
        )
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertIs(result.reason, m.GapReason.INVALIDATED)
        self.assertEqual(result.status.pending, 0)
        self.assertEqual(result.status.stale, 1)
        self.assertEqual(len(result.status.stale_refs), 1)

    def test_snapshot_curation_projection_is_version_aware(self) -> None:
        path = self.root / "src/audit.py"
        path.write_text("audit\n", encoding="utf-8")
        self._observation("obs-audit", "src/audit.py")
        self._create(
            "u-audit",
            "src/audit.py",
            "What does audit do?",
            curate=False,
            observation_id="obs-audit",
        )
        self._curate("u-audit")

        before = self.service.ask(
            m.AskRequest(
                selector=m.UnderstandingSnapshotSelector(
                    repository_id="repo-1",
                    understanding_id="u-audit",
                    version=1,
                )
            )
        )
        after = self.service.ask(
            m.AskRequest(
                selector=m.UnderstandingSnapshotSelector(
                    repository_id="repo-1",
                    understanding_id="u-audit",
                    version=2,
                )
            )
        )
        self.assertIsInstance(before, m.RetrievedUnderstanding)
        self.assertIsInstance(after, m.RetrievedUnderstanding)
        assert isinstance(before, m.RetrievedUnderstanding)
        assert isinstance(after, m.RetrievedUnderstanding)
        self.assertEqual(before.curations, ())
        before_content = before.conclusions[0].content
        after_content = after.conclusions[0].content
        assert isinstance(before_content, m.SupportedAuditContent)
        assert isinstance(after_content, m.SupportedAuditContent)
        self.assertEqual(before_content.maturity, m.CurationState.CAPTURED)
        self.assertEqual(after_content.maturity, m.CurationState.CURATED)
        self.assertEqual(before.version.value, 1)
        self.assertEqual(after.version.value, 2)
        self.assertEqual(before.conclusions[0].basis, after.conclusions[0].basis)
        self.assertEqual(
            before.conclusions[0].derivation, m.DerivationKind.EXPLICIT_EVIDENCE
        )
        self.assertEqual(before.conclusions[0].summary, "read")
        self.assertEqual(len(after.curations), 1)
        self.assertEqual(after.curations[0].ref.revision.value, 1)
        self.assertEqual(after.curations[0].accepted_in_version.value, 2)

    def test_pending_curation_keyset_paging_has_no_skip_or_duplicate(self) -> None:
        for suffix in ("a", "b"):
            locator = f"src/page-{suffix}.py"
            (self.root / locator).write_text(f"{suffix}\n", encoding="utf-8")
            observation_id = f"obs-page-{suffix}"
            self._observation(observation_id, locator)
            self._create(
                f"u-page-{suffix}",
                locator,
                f"What does page {suffix} do?",
                curate=False,
                observation_id=observation_id,
            )
        service = self._service(51_133, max_results=1)

        first = service.ask(
            m.AskRequest(selector=m.PendingCurationSelector(repository_id="repo-1"))
        )
        self.assertIsInstance(first, m.PendingCuration)
        assert isinstance(first, m.PendingCuration)
        self.assertTrue(first.truncated)
        self.assertEqual(len(first.items), 1)
        self.assertEqual(first.next_after, first.items[0].ref)

        second = service.ask(
            m.AskRequest(
                selector=m.PendingCurationSelector(
                    repository_id="repo-1",
                    after=first.next_after,
                )
            )
        )
        self.assertIsInstance(second, m.PendingCuration)
        assert isinstance(second, m.PendingCuration)
        self.assertFalse(second.truncated)
        self.assertIsNone(second.next_after)
        self.assertEqual(len(second.items), 1)
        self.assertNotEqual(first.items[0].ref, second.items[0].ref)
        self.assertEqual(
            {
                first.items[0].ref.understanding_id.value,
                second.items[0].ref.understanding_id.value,
            },
            {"u-page-a", "u-page-b"},
        )

    def test_pending_curation_keyset_paging_resumes_after_restart(self) -> None:
        for suffix in ("restart-a", "restart-b"):
            locator = f"src/{suffix}.py"
            (self.root / locator).write_text(f"{suffix}\n", encoding="utf-8")
            observation_id = f"obs-{suffix}"
            self._observation(observation_id, locator)
            self._create(
                f"u-{suffix}",
                locator,
                f"What does {suffix} do?",
                curate=False,
                observation_id=observation_id,
            )

        first = self._service(51_133, max_results=1).ask(
            m.AskRequest(selector=m.PendingCurationSelector(repository_id="repo-1"))
        )
        self.assertIsInstance(first, m.PendingCuration)
        assert isinstance(first, m.PendingCuration)
        self.assertTrue(first.truncated)
        self.assertEqual(len(first.items), 1)
        cursor = first.next_after
        self.assertIsNotNone(cursor)

        self.store.close()
        reopened = LifecycleStore(
            pathlib.Path(self._tmp.name) / "lifecycle.db",
            retention=RETENTION,
            clock=lambda: NOW,
        )
        self.addCleanup(reopened.close)
        reopened_support = SupportService(
            store=reopened,
            evidence=self.evidence,
            authority=reopened,
            clock=lambda: NOW,
        )
        second = self._service(
            51_133,
            max_results=1,
            store=reopened,
            support=reopened_support,
        ).ask(
            m.AskRequest(
                selector=m.PendingCurationSelector(
                    repository_id="repo-1",
                    after=cursor,
                )
            )
        )
        self.assertIsInstance(second, m.PendingCuration)
        assert isinstance(second, m.PendingCuration)
        self.assertFalse(second.truncated)
        self.assertIsNone(second.next_after)
        self.assertEqual(len(second.items), 1)
        self.assertNotEqual(first.items[0].ref, second.items[0].ref)
        self.assertEqual(
            {
                first.items[0].ref.understanding_id.value,
                second.items[0].ref.understanding_id.value,
            },
            {"u-restart-a", "u-restart-b"},
        )

    def test_changed_source_is_an_invalidated_gap(self) -> None:
        (self.root / "src/a.py").write_text("changed\n", encoding="utf-8")
        result = self._ask("src/a.py", "What does A do?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.INVALIDATED)
        self.assertEqual(len(result.historical), 1)
        historical = result.historical[0]
        self.assertEqual(historical.statement, "A does X number 1.")
        self.assertEqual(historical.understanding_version.value, 2)
        self.assertIs(historical.state, m.SupportState.REASSESSMENT_REQUIRED)
        version = self.store.get_version("u-a", 2)
        self.assertIsNotNone(
            self.store.find_curation(
                version.conclusions[0],
                as_of_version=version.version,
            )
        )
        self.assertEqual(
            [item.evidence_id.value for item in historical.evidence],
            ["ev-src/a.py"],
        )

    def test_stale_sibling_is_referenced_in_status(self) -> None:
        (self.root / "src/b.py").write_text("b\n", encoding="utf-8")
        self._observation("obs-b", "src/b.py")
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-sibling"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/a.py",
                ),
                target=m.ExplicitTarget(
                    question="What else does A do?",
                    scope=m.EvidenceScope(paths=("src/a.py", "src/b.py")),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="A does X.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-a")
                            ),
                        ),
                        basis=_basis(),
                    ),
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-2"),
                        statement="B does Y.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/b.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-b")
                            ),
                        ),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-sibling"),
        )
        self._curate("u-sibling")
        (self.root / "src/b.py").write_text("changed\n", encoding="utf-8")
        result = self._ask("src/a.py", "What else does A do?", "req-sibling-ask")
        assert isinstance(result, m.Answer)
        self.assertEqual(result.status.stale, 1)
        self.assertEqual(len(result.status.stale_refs), 1)
        stale = result.status.stale_refs[0]
        self.assertEqual(stale.ref.conclusion_id.value, "c-2")
        self.assertEqual(stale.ref.understanding_id.value, "u-sibling")
        self.assertEqual(stale.understanding_version.value, 2)
        self.assertIs(stale.state, m.SupportState.REASSESSMENT_REQUIRED)
        self.assertEqual(
            sum(len(group.conclusions) for group in result.groups),
            2,
        )

    def test_document_view_gap_carries_historical_content(self) -> None:
        (self.root / "src/a.py").write_text("changed\n", encoding="utf-8")
        result = self._ask("src/a.py", None)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.INVALIDATED)
        self.assertEqual(result.historical[0].statement, "A does X number 1.")

    def test_unknown_surface_is_unassessed(self) -> None:
        result = self._ask("src/missing.py", "What does it do?")
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.UNASSESSED)

    def test_unknown_current_understanding_selector_is_rejected(self) -> None:
        with self.assertRaises(RecordingValidationError):
            self.service.ask(
                m.AskRequest(
                    selector=m.CurrentUnderstandingSelector(
                        repository_id="repo-1",
                        understanding_id="u:missing",
                    )
                )
            )

    def test_exact_question_status_excludes_unrelated_capture(self) -> None:
        self._create("u-unrelated", "src/a.py", "Another question?", curate=False)
        result = self.service.ask(
            m.AskRequest(
                selector=m.RecordedQuestionSelector(
                    repository_id="repo-1",
                    surface=m.SurfaceReference(
                        kind=m.SurfaceKind.FILE, locator="src/a.py"
                    ),
                    question="What does A do?",
                )
            )
        )
        assert isinstance(result, m.Answer)
        self.assertEqual(result.status.current, 1)
        self.assertEqual(result.status.pending, 0)
        self.assertEqual(result.status.pending_refs, ())
        self.assertEqual(result.status.descendants, ())
        self.assertEqual(result.status.unexamined, 0)

    def test_exact_question_without_membership_is_unassessed(self) -> None:
        result = self.service.ask(
            m.AskRequest(
                selector=m.RecordedQuestionSelector(
                    repository_id="repo-1",
                    surface=m.SurfaceReference(
                        kind=m.SurfaceKind.FILE,
                        locator="src/a.py",
                    ),
                    question="What else?",
                )
            )
        )
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.UNASSESSED)
        self.assertEqual(result.missing, ("What else?",))

    def test_exact_question_selector_does_not_paraphrase_match(self) -> None:
        result = self.service.ask(
            m.AskRequest(
                selector=m.RecordedQuestionSelector(
                    repository_id="repo-1",
                    surface=m.SurfaceReference(
                        kind=m.SurfaceKind.FILE,
                        locator="src/a.py",
                    ),
                    question="Why does A exist?",
                )
            )
        )
        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.UNASSESSED)

    def test_surface_document_view_is_reuse_path(self) -> None:
        result = self._ask("src/a.py", None)
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
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
                binding_digest=m.ContentDigest("sha256:ver"),
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

    def _record_verification_paths(
        self,
        request_id: str,
        paths: tuple[str, ...],
        *,
        description: str | None = None,
        observed_at: datetime.datetime = NOW,
    ) -> m.RecordReceipt:
        verification_context = m.InvestigationContextId(f"ctx-{request_id}")
        self.store.put_context(
            m.InvestigationContext(
                context_id=verification_context,
                repository_id="repo-1",
                request_id=m.RequestId(request_id),
                binding_digest=m.ContentDigest(f"sha256:{request_id}"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(),
                created_at=NOW,
                expires_at=NOW + RETENTION.context_lifetime,
            )
        )
        return self.store.record_verification(
            m.RecordVerificationCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId(request_id),
                    context_id=verification_context,
                ),
                run=m.ProposedVerificationRun(
                    repository_id="repo-1",
                    scope=m.VerificationScope(
                        description=description or request_id,
                        scope=m.EvidenceScope(paths=paths),
                    ),
                    observations=(m.SourceObservationId("obs-a"),),
                    command="python3 -m unittest",
                    scenario=None,
                    outcome=m.VerificationOutcome.PASS,
                    observed_at=observed_at,
                    observer="test",
                ),
            )
        )

    def _create_on_surface(
        self,
        understanding_id: str,
        surface: m.SurfaceKey,
        question: str,
        *,
        conclusion_id: str = "c-1",
        curate: bool = True,
    ) -> None:
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId(f"req-{understanding_id}"),
                    context_id=CONTEXT_ID,
                ),
                surface=surface,
                target=m.ExplicitTarget(
                    question=question,
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId(conclusion_id),
                        statement="A does X.",
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
        if curate:
            self._curate(understanding_id)

    def test_multi_file_run_is_visible_on_each_file(self) -> None:
        (self.root / "src/b.py").write_text("b\n", encoding="utf-8")
        self._observation("obs-b", "src/b.py")
        self._create("u-b", "src/b.py", "What does B do?")
        self._record_verification_paths("req-multi", ("src/a.py", "src/b.py"))
        for reference, question, request_id in (
            ("src/a.py", "What does A do?", "req-ask-a"),
            ("src/b.py", "What does B do?", "req-ask-b"),
        ):
            result = self._ask(reference, question, request_id)
            assert isinstance(result, m.Answer)
            self.assertEqual(len(result.verification), 1, reference)

    def test_one_file_run_is_not_visible_on_a_broader_service(self) -> None:
        service_key = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.SERVICE, locator="svc"
        )
        self.store.put_surface(
            m.Surface(key=service_key, boundary=m.SurfaceBoundary(paths=("src",)))
        )
        self._create_on_surface("u-svc", service_key, "What does S do?")
        self._record_verification_paths("req-one", ("src/a.py",))
        result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                surface=m.SurfaceReference(kind=m.SurfaceKind.SERVICE, locator="svc"),
            )
        )
        assert isinstance(result, m.Answer)
        self.assertEqual(result.verification, ())

    def test_cold_governed_path_returns_gap_with_governing_view(self) -> None:
        seen: list[m.EvidenceScope] = []

        def orientation(
            repository_id: str,
            surface: m.SurfaceKey,
            semantic_scope: m.EvidenceScope,
        ) -> m.FunctionalPyramidView:
            self.assertEqual(repository_id, "repo-1")
            self.assertEqual(surface.locator, "src/missing.py")
            seen.append(semantic_scope)
            return functional_pyramid_view(
                semantic_scope,
                pyramid_id="fp-cold",
            )

        service = AnswerService(
            store=self.store,
            support=self.support,
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            functional_pyramid_orientation=orientation,
        )
        before = self.store.list_understandings("repo-1")

        result = service.ask(
            m.AskRequest(repository_id="repo-1", reference="src/missing.py")
        )

        self.assertIsInstance(result, m.Gap)
        assert isinstance(result, m.Gap)
        self.assertEqual(result.reason, m.GapReason.UNASSESSED)
        self.assertIsInstance(result.functional_pyramid, m.FunctionalPyramidView)
        self.assertEqual(
            seen,
            [m.EvidenceScope(paths=("src/missing.py",))],
        )
        self.assertEqual(self.store.list_understandings("repo-1"), before)

    def test_mixed_answer_excludes_noncurrent_normative_conclusion(self) -> None:
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-u-normative"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/a.py",
                ),
                target=m.ExplicitTarget(
                    question="What governs A?",
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-normative"),
                        statement="A conforms to the governing route.",
                        assertion_nature=m.AssertionNature.NORMATIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-a")
                            ),
                            m.FunctionalRouteSupport(
                                repository_id="repo-1",
                                pyramid_id=m.FunctionalPyramidId("fp-mixed"),
                                semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
                                route_identity=m.FunctionalRouteIdentity(
                                    "route-unresolved"
                                ),
                            ),
                        ),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-normative"),
        )

        def unresolved(scope: m.EvidenceScope) -> m.FunctionalPyramidView:
            return functional_pyramid_view(
                scope,
                pyramid_id="fp-mixed",
                status=m.FunctionalPyramidRouteStatus.UNRESOLVED,
            )

        support = SupportService(
            store=self.store,
            evidence=self.evidence,
            authority=self.store,
            functional_route_resolver=lambda dependency, _surface: (
                unresolved(dependency.semantic_scope),
                None,
            ),
        )
        service = AnswerService(
            store=self.store,
            support=support,
            understand=UnderstandService(store=self.store, support=support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            functional_pyramid_orientation=lambda _repository_id, _surface, scope: (
                unresolved(scope)
            ),
        )

        result = service.ask(m.AskRequest(repository_id="repo-1", reference="src/a.py"))

        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        statements = tuple(
            conclusion.statement
            for group in result.groups
            for conclusion in group.conclusions
        )
        self.assertIn("A does X number 1.", statements)
        self.assertNotIn("A conforms to the governing route.", statements)
        self.assertIsInstance(result.functional_pyramid, m.FunctionalPyramidView)
        assert isinstance(result.functional_pyramid, m.FunctionalPyramidView)
        self.assertEqual(
            result.functional_pyramid.status,
            m.FunctionalPyramidRouteStatus.UNRESOLVED,
        )

    def test_descriptive_answer_survives_unresolved_governing_route(self) -> None:
        def orientation(
            repository_id: str,
            surface: m.SurfaceKey,
            semantic_scope: m.EvidenceScope,
        ) -> m.FunctionalPyramidView:
            self.assertEqual(repository_id, "repo-1")
            self.assertEqual(surface.locator, "src/a.py")
            return functional_pyramid_view(
                semantic_scope,
                pyramid_id="fp-mixed",
                status=m.FunctionalPyramidRouteStatus.UNRESOLVED,
            )

        service = AnswerService(
            store=self.store,
            support=self.support,
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            functional_pyramid_orientation=orientation,
        )

        result = service.ask(m.AskRequest(repository_id="repo-1", reference="src/a.py"))

        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(
            result.groups[0].conclusions[0].statement, "A does X number 1."
        )
        self.assertIsInstance(result.functional_pyramid, m.FunctionalPyramidView)
        assert isinstance(result.functional_pyramid, m.FunctionalPyramidView)
        self.assertEqual(
            result.functional_pyramid.status,
            m.FunctionalPyramidRouteStatus.UNRESOLVED,
        )

    def test_declared_symbol_boundary_is_exact_functional_pyramid_scope(self) -> None:
        seen: list[m.EvidenceScope] = []

        def orientation(
            repository_id: str,
            surface: m.SurfaceKey,
            semantic_scope: m.EvidenceScope,
        ) -> m.FunctionalPyramidParticipation:
            self.assertEqual(repository_id, "repo-1")
            self.assertEqual(surface.kind, m.SurfaceKind.SERVICE)
            seen.append(semantic_scope)
            return m.FunctionalPyramidParticipation(
                m.FunctionalPyramidParticipationState.EXCLUDED
            )

        service_key = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.SERVICE, locator="symbol-svc"
        )
        self.store.put_surface(
            m.Surface(
                key=service_key,
                boundary=m.SurfaceBoundary(symbols=("src/a.py::A",)),
            )
        )
        service = AnswerService(
            store=self.store,
            support=self.support,
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            functional_pyramid_orientation=orientation,
        )

        result = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.SERVICE, locator="symbol-svc"
                ),
            )
        )

        self.assertIsInstance(result, m.Gap)
        self.assertEqual(
            seen,
            [m.EvidenceScope(paths=("src/a.py::A",))],
        )

    def test_service_wide_run_is_visible_on_service_and_files(self) -> None:
        service_key = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.SERVICE, locator="svc"
        )
        self.store.put_surface(
            m.Surface(key=service_key, boundary=m.SurfaceBoundary(paths=("src",)))
        )
        self._create_on_surface("u-svc", service_key, "What does S do?")
        self._record_verification_paths("req-service", ("src",))
        service_result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                surface=m.SurfaceReference(kind=m.SurfaceKind.SERVICE, locator="svc"),
            )
        )
        assert isinstance(service_result, m.Answer)
        self.assertEqual(len(service_result.verification), 1)
        file_result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                surface=m.SurfaceReference(kind=m.SurfaceKind.FILE, locator="src/a.py"),
            )
        )
        assert isinstance(file_result, m.Answer)
        self.assertEqual(len(file_result.verification), 1)

    def test_directory_scoped_run_covers_files_under_it(self) -> None:
        self._record_verification_paths("req-dir", ("src",))
        result = self._ask("src/a.py", "What does A do?", "req-dir-ask")
        assert isinstance(result, m.Answer)
        self.assertEqual(len(result.verification), 1)

    def test_repeated_verification_is_selected_by_relevance(self) -> None:
        for age, request in enumerate(("repeated-a", "repeated-b")):
            self._record_verification_paths(
                request,
                ("src/a.py",),
                description="Same verification scope",
                observed_at=NOW - datetime.timedelta(minutes=age),
            )
        result = self._ask("src/a.py", None)
        assert isinstance(result, m.Answer)
        self.assertEqual(len(result.verification), 1)
        self.assertEqual(result.verification[0].run.observed_at, NOW)

    def test_verification_selection_order_is_deterministic(self) -> None:
        first = self._record_verification_paths("req-order-a", ("src/a.py",))
        second = self._record_verification_paths("req-order-b", ("src/a.py",))
        result = self._ask("src/a.py", "What does A do?", "req-order-ask")
        assert isinstance(result, m.Answer)
        expected = [
            first.accepted_verification_run_ids[0].value,
            second.accepted_verification_run_ids[0].value,
        ]
        self.assertEqual(
            [view.run.run_id.value for view in result.verification],
            expected,
        )

    def test_symbol_run_matches_through_containing_file(self) -> None:
        symbol_key = m.SurfaceKey(
            repository_id="repo-1",
            kind=m.SurfaceKind.SYMBOL,
            locator="src/a.py::A",
        )
        self._create_on_surface("u-sym", symbol_key, "What is A?")
        self._record_verification_paths("req-sym", ("src/a.py",))
        result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.SYMBOL, locator="src/a.py::A"
                ),
            )
        )
        assert isinstance(result, m.Answer)
        self.assertEqual(len(result.verification), 1)

    def test_symbol_without_a_file_prefix_is_excluded(self) -> None:
        symbol_key = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.SYMBOL, locator="Money"
        )
        self._create_on_surface("u-money", symbol_key, "What is Money?")
        self._record_verification_paths("req-money", ("Money",))
        result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                surface=m.SurfaceReference(kind=m.SurfaceKind.SYMBOL, locator="Money"),
            )
        )
        assert isinstance(result, m.Answer)
        self.assertEqual(result.verification, ())

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
        self._curate("u-wide")
        result = self._service(3_000).ask(
            m.AskRequest(
                repository_id="repo-1",
                reference="src/b.py",
            )
        )
        assert isinstance(result, m.Answer)
        self.assertTrue(result.truncated)
        self.assertTrue(result.omitted)
        self.assertTrue(result.groups)
        self.assertTrue(result.groups[0].conclusions)
        self.assertIn("u-wide", result.references)

    def test_enriched_status_and_gap_fit_the_default_budget(self) -> None:
        from span.service.answer import _encoded_size

        limit = DEFAULT_SERVICE_BOUNDS_POLICY.max_response_bytes
        refs = tuple(
            m.StaleConclusionRef(
                ref=m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u-1"),
                    conclusion_id=m.ConclusionId(f"c-{index}"),
                    revision=m.ConclusionRevisionNumber(1),
                ),
                understanding_version=m.UnderstandingVersionNumber(1),
                state=m.SupportState.REASSESSMENT_REQUIRED,
            )
            for index in range(100)
        )
        status = m.SurfaceStatus(
            surface=m.SurfaceKey(
                repository_id="repo-1", kind=m.SurfaceKind.FILE, locator="src/a.py"
            ),
            current=1,
            stale=len(refs),
            stale_refs=refs,
        )
        self.assertLessEqual(_encoded_size(status), limit)
        historical = m.HistoricalConclusion(
            ref=refs[0].ref,
            understanding_version=refs[0].understanding_version,
            statement="A does X.",
            state=m.SupportState.REASSESSMENT_REQUIRED,
            evidence=(
                m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-src/a.py"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator="src/a.py",
                ),
            ),
        )
        gap = m.Gap(
            surface=status.surface,
            status=status,
            functional_pyramid=m.FunctionalPyramidParticipation(
                m.FunctionalPyramidParticipationState.UNCONFIGURED
            ),
            reason=m.GapReason.INVALIDATED,
            recovery="re-read the cited evidence, then record against the current revision",
            historical=(historical,),
        )
        self.assertLessEqual(_encoded_size(gap), limit)

    def test_truncated_gap_names_the_snapshot_retrieval_path(self) -> None:
        from span.service.answer import _encoded_size

        surface = m.SurfaceKey(
            repository_id="repo-1", kind=m.SurfaceKind.FILE, locator="src/a.py"
        )
        historical = m.HistoricalConclusion(
            ref=m.ConclusionRevisionRef(
                understanding_id=m.UnderstandingId("u-1"),
                conclusion_id=m.ConclusionId("c-1"),
                revision=m.ConclusionRevisionNumber(1),
            ),
            understanding_version=m.UnderstandingVersionNumber(1),
            statement="A does X.",
            state=m.SupportState.REASSESSMENT_REQUIRED,
            evidence=(
                m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-src/a.py"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator="src/a.py",
                ),
            ),
        )
        gap = m.Gap(
            surface=surface,
            status=m.SurfaceStatus(surface=surface),
            functional_pyramid=m.FunctionalPyramidParticipation(
                m.FunctionalPyramidParticipationState.UNCONFIGURED
            ),
            reason=m.GapReason.INVALIDATED,
            recovery="base recovery",
            historical=(historical,),
        )
        result = self.service._fit_gap(gap, _encoded_size(gap) - 1)
        assert isinstance(result, m.Gap)
        self.assertTrue(result.truncated)
        self.assertEqual(result.historical, ())
        self.assertIn("UnderstandingSnapshotSelector", result.recovery)

    def test_budget_below_minimum_is_refused(self) -> None:
        result = self._service(10).ask(
            m.AskRequest(
                repository_id="repo-1",
                reference="src/a.py",
            )
        )
        assert isinstance(result, m.Unavailable)
        self.assertIn("budget", result.failure)
        self.assertTrue(result.recovery)

    def test_no_question_groups_current_content(self) -> None:
        result = self._ask("src/a.py", None)
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[0].question, "What does A do?")

    def test_exact_surface_resolves_by_identity(self) -> None:
        result = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                surface=m.SurfaceReference(kind=m.SurfaceKind.FILE, locator="src/a.py"),
            )
        )
        self.assertIsInstance(result, m.Answer)
        assert isinstance(result, m.Answer)
        self.assertEqual(result.surface.locator, "src/a.py")
        self.assertEqual(
            result.groups[0].conclusions[0].ref.understanding_id.value,
            "u-a",
        )
        self.assertEqual(
            result.groups[0].conclusions[0].statement,
            "A does X number 1.",
        )

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
                surface=m.SurfaceReference(
                    kind=selected.kind,
                    locator=selected.locator,
                ),
            )
        )
        self.assertIsInstance(resolved, m.Answer)

    def test_gap_continuation_returns_an_evidence_page(self) -> None:
        (self.root / "src/big.py").write_text(PAGED_SOURCE, encoding="utf-8")
        import dataclasses

        bounds = dataclasses.replace(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            max_evidence_bytes=100_000,
        )
        policy = m.ServiceBoundsPolicy(
            default_query_bounds=bounds,
            maximum_query_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
            hook_fast_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds,
            max_response_bytes=PAGED_RESPONSE_BUDGET,
        )
        service = AnswerService(
            store=self.store,
            support=self.support,
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            policy=policy,
            functional_pyramid_orientation=_unconfigured_orientation,
        )
        first = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-page",
                evidence=(m.EvidenceRequest("src/big.py"),),
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.FILE, locator="src/big.py"
                ),
            )
        )
        self.assertIsInstance(first, m.Gap)
        assert isinstance(first, m.Gap)
        self.assertTrue(first.admission.continuation)
        page = service.ask(
            m.AskRequest(
                continuation=first.admission.continuation,
            )
        )
        self.assertIsInstance(page, m.EvidencePage)
        assert isinstance(page, m.EvidencePage)
        self.assertTrue(page.deliveries)

    def test_continuation_page_fits_the_budget_with_its_omission(self) -> None:
        """A line-split page must budget the omission label it carries."""
        from span.service.answer import _encoded_size

        (self.root / "styles").mkdir()
        lines = [
            f".rule-{index} {{ color: #{index % 0xFFFFFF:06x}; }}"
            for index in range(2000)
        ]
        (self.root / "styles/theme.css").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        gap = self.service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-css-post-edit",
                evidence=(m.EvidenceRequest("styles/theme.css"),),
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.FILE, locator="styles/theme.css"
                ),
            )
        )
        self.assertIsInstance(gap, m.Gap)
        assert isinstance(gap, m.Gap)
        self.assertTrue(gap.admission.continuation)
        page = self.service.ask(m.AskRequest(continuation=gap.admission.continuation))
        self.assertIsInstance(page, m.EvidencePage)
        assert isinstance(page, m.EvidencePage)
        self.assertTrue(page.omitted)
        self.assertLessEqual(
            _encoded_size(page),
            DEFAULT_SERVICE_BOUNDS_POLICY.max_response_bytes,
        )

    def test_snapshot_selector_returns_history_not_an_answer(self) -> None:
        result = self.service.ask(
            m.AskRequest(
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
                selector=m.ReceiptRetrievalSelector(
                    repository_id="repo-1", request_id="req-u-a"
                ),
            )
        )
        self.assertIsInstance(result, m.RetrievedReceipt)
        self.assertNotIsInstance(result, m.Answer)
        assert isinstance(result, m.RetrievedReceipt)
        self.assertEqual(result.receipt_selector.request_id, "req-u-a")
        self.assertEqual(result.committed_at, NOW)
        effect = result.accepted_effect
        self.assertIsInstance(effect, m.HistoricalAcceptanceDetailUnavailable)
        assert isinstance(effect, m.HistoricalAcceptanceDetailUnavailable)
        self.assertEqual(
            effect.understanding_versions,
            (
                m.UnderstandingVersionRef(
                    m.UnderstandingId("u-a"), m.UnderstandingVersionNumber(1)
                ),
            ),
        )
        payload = m.to_canonical(result)
        self.assertNotIn("content_digest", str(payload))
        self.assertNotIn("context_id", str(payload))

    def test_verification_receipt_retains_exact_execution_without_live_support(
        self,
    ) -> None:
        receipt = self._record_verification_paths("receipt-run", ("src/a.py",))
        run = self.store.get_verification_run(
            receipt.accepted_verification_run_ids[0].value
        )
        (self.root / "src/a.py").write_text("changed\n", encoding="utf-8")
        result = self.service.ask(
            m.AskRequest(
                selector=m.ReceiptRetrievalSelector(
                    repository_id="repo-1", request_id="receipt-run"
                )
            )
        )
        assert isinstance(result, m.RetrievedReceipt)
        self.assertEqual(result.accepted_effect, m.AcceptedVerificationReceipt((run,)))

    def _page_service(self, *, clock=None):
        import dataclasses

        bounds = dataclasses.replace(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            max_evidence_bytes=100_000,
        )
        return AnswerService(
            store=self.store,
            support=self.support,
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(
                store=self.store, evidence=self.evidence, clock=clock
            ),
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=bounds,
                maximum_query_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
                hook_fast_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds,
                max_response_bytes=PAGED_RESPONSE_BUDGET,
            ),
            clock=clock,
            functional_pyramid_orientation=_unconfigured_orientation,
        )

    def _cold_page(self, service):
        (self.root / "src/big.py").write_text(PAGED_SOURCE, encoding="utf-8")
        first = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-page",
                evidence=(m.EvidenceRequest("src/big.py"),),
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.FILE, locator="src/big.py"
                ),
            )
        )
        assert isinstance(first, m.Gap)
        self.assertTrue(first.admission.continuation)
        return first

    def _state_continuation(self, *, expires_at: datetime.datetime) -> tuple[str, str]:
        context_id = "ctx-continuation-state"
        request_id = m.RequestId("req-continuation-state")
        digest = m.ContentDigest("sha256:continuation-state")
        self.store.put_context(
            m.InvestigationContext(
                context_id=m.InvestigationContextId(context_id),
                repository_id="repo-1",
                request_id=request_id,
                binding_digest=digest,
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(paths=("src/a.py",)),
                created_at=NOW,
                expires_at=expires_at,
            )
        )
        token = encode_continuation(
            ContinuationCursor(
                repository_id="repo-1",
                context_id=context_id,
                request_id=request_id,
                binding_digest=digest,
            )
        )
        return token, context_id

    def test_binding_conflict_is_not_converted_to_a_semantic_gap(self) -> None:
        from unittest import mock

        from span.core.recording import RecordingConflict

        with mock.patch(
            "span.service.answer.issue_context",
            side_effect=RecordingConflict("sentinel binding conflict"),
        ):
            with self.assertRaises(RecordingConflict):
                self.service.ask(
                    m.AskRequest(
                        repository_id="repo-1",
                        request_id="req-conflict",
                        evidence=(m.EvidenceRequest("src/a.py"),),
                        surface=m.SurfaceReference(
                            kind=m.SurfaceKind.FILE, locator="src/a.py"
                        ),
                    )
                )

    def test_store_failure_is_not_converted_to_a_semantic_gap(self) -> None:
        from unittest import mock

        from span.shell.sqlite_store.lifecycle import LifecycleStoreError

        with mock.patch.object(
            self.service._evidence,
            "admit",
            side_effect=LifecycleStoreError("sentinel store failure"),
        ):
            with self.assertRaises(LifecycleStoreError):
                self.service.ask(
                    m.AskRequest(
                        repository_id="repo-1",
                        request_id="req-store-failure",
                        evidence=(m.EvidenceRequest("src/a.py"),),
                        surface=m.SurfaceReference(
                            kind=m.SurfaceKind.FILE, locator="src/a.py"
                        ),
                    )
                )

    def test_continuation_replay_is_stable(self) -> None:
        service = self._page_service()
        first = self._cold_page(service)
        page = service.ask(m.AskRequest(continuation=first.admission.continuation))
        again = service.ask(m.AskRequest(continuation=first.admission.continuation))
        self.assertIsInstance(page, m.EvidencePage)
        self.assertEqual(page, again)

    def test_abandoned_context_rejects_the_continuation(self) -> None:
        service = self._page_service()
        continuation, context_id = self._state_continuation(
            expires_at=NOW + RETENTION.context_lifetime
        )
        self.store.abandon_context(context_id)
        with self.assertRaises(RecordingValidationError) as raised:
            service.ask(m.AskRequest(continuation=continuation))
        self.assertIs(
            raised.exception.cause_kind, m.RejectionCauseKind.CONTINUATION_INVALID
        )
        self.assertNotIn("reaped", raised.exception.required_action.lower())

    def test_expired_context_rejects_the_continuation(self) -> None:
        now = [NOW]
        service = self._page_service(clock=lambda: now[0])
        continuation, _ = self._state_continuation(
            expires_at=NOW + RETENTION.context_lifetime
        )
        now[0] = NOW + datetime.timedelta(hours=2)
        with self.assertRaises(RecordingValidationError) as raised:
            service.ask(m.AskRequest(continuation=continuation))
        self.assertIs(
            raised.exception.cause_kind, m.RejectionCauseKind.CONTINUATION_INVALID
        )

    def test_malformed_continuation_is_a_typed_rejection(self) -> None:
        with self.assertRaises(RecordingValidationError) as raised:
            self.service.ask(m.AskRequest(continuation="span1_not-base64"))
        self.assertIs(
            raised.exception.cause_kind, m.RejectionCauseKind.CONTINUATION_INVALID
        )

    def test_continuation_rejects_a_repository_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "no repository override"):
            m.AskRequest(
                repository_id="repo-2",
                continuation="span1_token",
            )

    def test_one_line_too_large_is_refused(self) -> None:
        import dataclasses

        huge_line = "x" * 5000 + "\n"
        (self.root / "src/huge.py").write_text(huge_line, encoding="utf-8")
        bounds = dataclasses.replace(
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            max_evidence_bytes=100_000,
        )
        service = AnswerService(
            store=self.store,
            support=self.support,
            understand=UnderstandService(store=self.store, support=self.support),
            evidence=EvidenceService(store=self.store, evidence=self.evidence),
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=bounds,
                maximum_query_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
                hook_fast_bounds=DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds,
                max_response_bytes=len(huge_line.encode("utf-8")) - 1,
            ),
            functional_pyramid_orientation=_unconfigured_orientation,
        )
        first = service.ask(
            m.AskRequest(
                repository_id="repo-1",
                request_id="req-huge",
                evidence=(m.EvidenceRequest("src/huge.py"),),
                surface=m.SurfaceReference(
                    kind=m.SurfaceKind.FILE, locator="src/huge.py"
                ),
            )
        )
        assert isinstance(first, m.Gap)
        page = service.ask(m.AskRequest(continuation=first.admission.continuation))
        self.assertIsInstance(page, m.Unavailable)
