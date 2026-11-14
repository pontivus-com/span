"""Reconsideration composition (FD-17–FD-22)."""

from __future__ import annotations

import datetime
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.core.recording import RecordingValidationError
from span.core import support_rules
from span.service.reconsider import ReconsiderService
from span.service.support import SupportService
from span.shell.filesystem_evidence import FilesystemEvidenceSource
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


class ReconsiderServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "repo"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src/a.py").write_text("a\n", encoding="utf-8")
        (self.root / "src/b.py").write_text("b\n", encoding="utf-8")
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
        self.store.put_source_observation(
            m.SourceObservation(
                observation_id=m.SourceObservationId("obs-a"),
                repository_id="repo-1",
                evidence=m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-a"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator="src/a.py",
                    revision_or_fingerprint="a",
                ),
                content_digest=m.ContentDigest("sha256:a"),
                captured_at=NOW,
                total_lines=1,
                whole_file=True,
                excerpt="a",
            )
        )
        self.store.put_source_observation(
            m.SourceObservation(
                observation_id=m.SourceObservationId("obs-b"),
                repository_id="repo-1",
                evidence=m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-b"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator="src/b.py",
                    revision_or_fingerprint="b",
                ),
                content_digest=m.ContentDigest("sha256:b"),
                captured_at=NOW,
                total_lines=1,
                whole_file=True,
                excerpt="b",
            )
        )
        self._create(
            "u-a",
            "src/a.py",
            "src/a.py",
            m.SourceSupport(observation_id=m.SourceObservationId("obs-a")),
        )
        premise = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-a"),
            conclusion_id=m.ConclusionId("c-1"),
            revision=m.ConclusionRevisionNumber(1),
        )
        self._create(
            "u-b",
            "src/b.py",
            "src/b.py",
            m.PremiseSupport(premise=premise),
        )
        self.service = ReconsiderService(store=self.store)

    def _create(
        self,
        understanding_id: str,
        surface_locator: str,
        scope_path: str,
        support: m.SupportDependency,
        *,
        scope: m.EvidenceScope | None = None,
        surface_kind: m.SurfaceKind = m.SurfaceKind.FILE,
    ) -> None:
        semantic_scope = (
            m.EvidenceScope(paths=(scope_path,)) if scope is None else scope
        )
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId(f"req-{understanding_id}"),
                    context_id=CONTEXT_ID,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=surface_kind,
                    locator=surface_locator,
                ),
                target=m.ExplicitTarget(
                    question="What does this do?",
                    scope=semantic_scope,
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="It does something.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=semantic_scope,
                        support=(support,),
                        basis=_basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId(understanding_id),
        )

    def test_changed_path_maps_containment_direct_and_indirect(self) -> None:
        result = self.service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertFalse(result.truncated)
        self.assertEqual(
            [item.surface.locator for item in result.surfaces],
            ["src/a.py", "src/b.py", "svc"],
        )
        by_surface = {item.surface.locator: item for item in result.surfaces}
        self.assertEqual(
            set(by_surface["src/a.py"].reasons),
            {m.ChangeReason.CONTAINMENT, m.ChangeReason.DIRECT},
        )
        self.assertEqual(by_surface["src/b.py"].reasons, (m.ChangeReason.INDIRECT,))
        self.assertEqual(by_surface["svc"].reasons, (m.ChangeReason.CONTAINMENT,))
        self.assertEqual(
            by_surface["src/b.py"].conclusions[0].ref.understanding_id.value,
            "u-b",
        )
        self.assertEqual(
            by_surface["src/b.py"].conclusions[0].expected_version.value, 1
        )

    def test_historical_revision_is_not_an_actionable_change_target(self) -> None:
        self.store.record_understanding(
            m.UpdateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-u-a-correct"),
                    context_id=CONTEXT_ID,
                ),
                understanding_id=m.UnderstandingId("u-a"),
                expected_version=m.UnderstandingVersionNumber(1),
                correct=(
                    m.CorrectConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="It does something else.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py",)),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-a")
                            ),
                        ),
                        basis=m.SemanticBasis(
                            derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                            summary="corrected",
                            input_refs=(),
                        ),
                    ),
                ),
            ),
            content_digest=m.ContentDigest("sha256:correct"),
        )

        result = self.service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        by_surface = {item.surface.locator: item for item in result.surfaces}

        # The historical premise revision is still walked: u-b depends on
        # u-a c-1@1 and remains a current, actionable dependent.
        self.assertIn("src/b.py", by_surface)
        dependent = by_surface["src/b.py"].conclusions[0]
        self.assertEqual(dependent.ref.understanding_id.value, "u-b")
        self.assertEqual(dependent.expected_version.value, 1)

        # u-a's current membership is c-1@2; the historical c-1@1 is not
        # emitted as an actionable target even though traversal saw it.
        a_conclusions = by_surface["src/a.py"].conclusions
        self.assertEqual(
            [
                (item.ref.conclusion_id.value, item.ref.revision.value)
                for item in a_conclusions
            ],
            [("c-1", 2)],
        )
        self.assertEqual(a_conclusions[0].expected_version.value, 2)

    def test_unowned_path_reports_only_its_path_surface(self) -> None:
        result = self.service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("docs/readme.md",),
            )
        )
        self.assertEqual(len(result.surfaces), 1)
        self.assertEqual(result.surfaces[0].surface.locator, "docs/readme.md")
        self.assertEqual(result.surfaces[0].conclusions, ())

    def test_bound_reports_truncation_not_unaffected(self) -> None:
        service = ReconsiderService(
            store=self.store,
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=m.QueryBounds(
                    max_results=1,
                    max_depth=1,
                    max_subjects=1,
                    max_evidence_units=1,
                    max_evidence_bytes=1_000,
                    max_candidate_claims=1,
                    max_candidate_relationships=1,
                ),
                maximum_query_bounds=m.QueryBounds(
                    max_results=1,
                    max_depth=1,
                    max_subjects=1,
                    max_evidence_units=1,
                    max_evidence_bytes=1_000,
                    max_candidate_claims=1,
                    max_candidate_relationships=1,
                ),
                hook_fast_bounds=m.QueryBounds(
                    max_results=1,
                    max_depth=1,
                    max_subjects=1,
                    max_evidence_units=1,
                    max_evidence_bytes=1_000,
                    max_candidate_claims=1,
                    max_candidate_relationships=1,
                ),
            ),
        )
        result = service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertTrue(result.truncated)
        self.assertEqual(len(result.surfaces), 1)
        self.assertEqual(result.unaffected, ())
        self.assertTrue(result.omitted)

    def test_depth_bound_stops_the_walk_and_reports_the_limit(self) -> None:
        self._create(
            "u-c",
            "src/c.py",
            "src/c.py",
            m.PremiseSupport(
                premise=m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u-b"),
                    conclusion_id=m.ConclusionId("c-1"),
                    revision=m.ConclusionRevisionNumber(1),
                )
            ),
        )
        bounds = m.QueryBounds(
            max_results=10,
            max_depth=1,
            max_subjects=8,
            max_evidence_units=8,
            max_evidence_bytes=10_000,
            max_candidate_claims=8,
            max_candidate_relationships=8,
        )
        service = ReconsiderService(
            store=self.store,
            policy=m.ServiceBoundsPolicy(
                default_query_bounds=bounds,
                maximum_query_bounds=bounds,
                hook_fast_bounds=bounds,
            ),
        )
        result = service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertTrue(result.truncated)
        self.assertEqual(result.unaffected, ())
        self.assertTrue(
            any("traversal bound" in item for item in result.omitted),
            result.omitted,
        )
        locators = [item.surface.locator for item in result.surfaces]
        self.assertIn("src/b.py", locators)
        self.assertNotIn("src/c.py", locators)

    def test_challenge_is_raised_through_reconsider(self) -> None:
        target = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-a"),
            conclusion_id=m.ConclusionId("c-1"),
            revision=m.ConclusionRevisionNumber(1),
        )
        result = self.service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                challenge=m.ChallengeRaise(
                    request_id="req-challenge",
                    context=m.InvestigationContextRef(
                        repository_id="repo-1",
                        context_id=CONTEXT_ID,
                    ),
                    understanding_id="u-a",
                    target_version=1,
                    target_conclusions=(
                        m.ChallengeConclusionRef(
                            understanding_id="u-a",
                            conclusion_id="c-1",
                            revision=1,
                        ),
                    ),
                    reason="The cited source does not support this statement.",
                ),
            )
        )
        self.assertIsInstance(result, m.Challenged)
        assert isinstance(result, m.Challenged)
        self.assertEqual(result.challenge.understanding_id.value, "u-a")
        self.assertEqual(result.challenge.target_conclusions, (target,))
        self.assertEqual(result.challenge.state, m.ChallengeState.OPEN)

    def test_challenge_rejects_unadmitted_evidence(self) -> None:
        with self.assertRaisesRegex(RecordingValidationError, "not admitted"):
            self.service.reconsider(
                m.ReconsiderRequest(
                    repository_id="repo-1",
                    challenge=m.ChallengeRaise(
                        request_id="req-challenge-2",
                        context=m.InvestigationContextRef(
                        repository_id="repo-1",
                        context_id=CONTEXT_ID,
                    ),
                        understanding_id="u-a",
                        target_version=1,
                        target_conclusions=(
                            m.ChallengeConclusionRef(
                                understanding_id="u-a",
                                conclusion_id="c-1",
                                revision=1,
                            ),
                        ),
                        reason="Check this.",
                        evidence=(
                            m.EvidenceRef(
                                evidence_id=m.EvidenceId("ev-missing"),
                                repository_id="repo-1",
                                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                                locator="src/a.py",
                                revision_or_fingerprint="sha256:a",
                            ),
                        ),
                    ),
                )
            )

    def test_discovery_membership_change_is_direct(self) -> None:
        evidence = FilesystemEvidenceSource("repo-1", self.root)
        pairs, _ = evidence.list_inventory_entries(
            "repo-1", m.EvidenceScope(paths=("src",))
        )
        observation = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-1"),
            repository_id="repo-1",
            scope=m.EvidenceScope(paths=("src",)),
            membership_fingerprint=support_rules.discovery_membership_fingerprint(
                pairs
            ),
            captured_at=NOW,
        )
        self.store.put_discovery_observation(observation)
        self._create(
            "u-discovery",
            "src/d.py",
            "src/d.py",
            m.DiscoverySupport(observation_id=m.DiscoveryObservationId("disc-1")),
        )
        support = SupportService(
            store=self.store,
            evidence=evidence,
            authority=self.store,
            clock=lambda: NOW,
        )
        service = ReconsiderService(store=self.store, support=support)
        result = service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        owner = next(
            item for item in result.surfaces if item.surface.locator == "src/d.py"
        )
        refs = [item.ref.understanding_id.value for item in owner.conclusions]
        self.assertIn("u-discovery", refs)
        changed = next(
            item
            for item in owner.conclusions
            if item.ref.understanding_id.value == "u-discovery"
        )
        self.assertIn(m.ChangeReason.DIRECT, changed.reasons)

    def test_refs_only_discovery_tracks_only_the_referenced_changed_path(self):
        reference = self.store.get_source_observation("obs-a").evidence
        scope = m.EvidenceScope(evidence_refs=(reference,))
        source = FilesystemEvidenceSource("repo-1", self.root)
        pairs, _ = source.list_inventory_entries("repo-1", scope)
        observation = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-refs"),
            repository_id="repo-1",
            scope=scope,
            membership_fingerprint=support_rules.discovery_membership_fingerprint(
                pairs
            ),
            captured_at=NOW,
        )
        self.store.put_discovery_observation(observation)
        self._create(
            "u-discovery-refs",
            "src/discovery.py",
            "src/discovery.py",
            m.DiscoverySupport(observation_id=observation.observation_id),
        )
        for path, expected in (("src/b.py", False), ("src/a.py", True)):
            with self.subTest(path=path):
                result = self.service.reconsider(
                    m.ReconsiderRequest(repository_id="repo-1", changed_paths=(path,))
                )
                direct = {
                    item.ref.understanding_id.value
                    for surface in result.surfaces
                    for item in surface.conclusions
                    if m.ChangeReason.DIRECT in item.reasons
                }
                self.assertEqual("u-discovery-refs" in direct, expected)

    def test_repeated_changed_scope_gets_a_fresh_context_after_expiry(self) -> None:
        now = [NOW]
        issued = iter(("ctx-reconsider-1", "ctx-reconsider-2"))
        service = ReconsiderService(
            store=self.store,
            clock=lambda: now[0],
            new_context_id=lambda: next(issued),
        )
        first = service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        now[0] = NOW + datetime.timedelta(hours=2)
        second = service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertNotEqual(second.context, first.context)
        context = self.store.get_context(second.context.context_id.value)
        self.assertEqual(context.state, m.ContextState.LIVE)

    def test_refs_only_challenge_context_retains_scope_for_symbol_and_declared_owner(
        self,
    ):
        import dataclasses

        reference = dataclasses.replace(
            self.store.get_source_observation("obs-a").evidence, locator="src/a.py::f"
        )
        scope = m.EvidenceScope(evidence_refs=(reference,))
        self.store.put_surface(
            m.Surface(
                key=m.SurfaceKey("repo-1", m.SurfaceKind.SERVICE, "symbols-only"),
                boundary=m.SurfaceBoundary(symbols=(reference.locator,)),
            )
        )
        for index, (kind, locator) in enumerate(
            (
                (m.SurfaceKind.SYMBOL, reference.locator),
                (m.SurfaceKind.SERVICE, "symbols-only"),
            )
        ):
            with self.subTest(kind=kind):
                uid = f"u-ref-challenge-{index}"
                self._create(
                    uid,
                    locator,
                    reference.locator,
                    m.SourceSupport(observation_id=m.SourceObservationId("obs-a")),
                    scope=scope,
                    surface_kind=kind,
                )
                challenged = self.service.reconsider(
                    m.ReconsiderRequest(
                        repository_id="repo-1",
                        challenge=m.ChallengeRaise(
                            request_id=f"challenge-refs-{index}",
                            understanding_id=uid,
                            target_version=1,
                            target_conclusions=(
                                m.ChallengeConclusionRef(
                                    understanding_id=uid,
                                    conclusion_id="c-1",
                                    revision=1,
                                ),
                            ),
                            reason="Recheck the exact symbol scope.",
                        ),
                    )
                )
                context = self.store.get_context(challenged.context.context_id.value)
                self.assertEqual(context.scope, scope)
                self.assertFalse(
                    m.evidence_scope_contains(
                        context.scope, m.EvidenceScope(paths=("src/b.py",))
                    )
                )
