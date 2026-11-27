"""Reconsideration composition (FD-17–FD-22)."""

from __future__ import annotations

import datetime
import pathlib
import tempfile
import unittest
from unittest import mock

from span.core import model as m
from span.core.recording import RecordingValidationError
from span.core import support_rules
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.effects import DependencyEffectService
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
                binding_digest=m.ContentDigest("sha256:request"),
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
        self.support = SupportService(
            store=self.store,
            evidence=FilesystemEvidenceSource("repo-1", self.root),
            authority=self.store,
            functional_route_resolver=lambda _dependency, _surface: (
                m.FunctionalPyramidParticipation(
                    m.FunctionalPyramidParticipationState.UNCONFIGURED
                ),
                None,
            ),
            clock=lambda: NOW,
        )
        self.service = self._service()

    def _effects(
        self,
        *,
        support=None,
        clock=None,
        new_context_id=None,
        functional_route_impacts=None,
    ) -> DependencyEffectService:
        selected_support = self.support if support is None else support
        selected_clock = clock or (lambda: NOW)
        runtime = mock.Mock(
            repository_id="repo-1",
            root=str(self.root),
            store=self.store,
            evidence=FilesystemEvidenceSource("repo-1", self.root),
        )

        def repository_runtime(repository_id):
            if repository_id != "repo-1":
                self.fail(f"unexpected repository: {repository_id}")
            return runtime

        def support_for_repository(repository_id):
            if repository_id != "repo-1":
                self.fail(f"unexpected repository: {repository_id}")
            return selected_support

        return DependencyEffectService(
            repository_runtime=repository_runtime,
            registered_repository_ids=lambda: ("repo-1",),
            support_for_repository=support_for_repository,
            functional_route_impacts=(
                functional_route_impacts
                or (lambda _repository_id, _paths, _surfaces: ())
            ),
            clock=selected_clock,
            new_context_id=new_context_id,
        )

    def _service(
        self,
        *,
        support=None,
        evidence=None,
        policy=None,
        clock=None,
        new_context_id=None,
        effects=None,
    ) -> ReconsiderService:
        selected_clock = clock or (lambda: NOW)
        selected_policy = policy or DEFAULT_SERVICE_BOUNDS_POLICY
        if effects is None:
            effects = self._effects(
                support=support,
                clock=selected_clock,
                new_context_id=new_context_id,
            )
        return ReconsiderService(
            store=self.store,
            evidence=evidence,
            policy=selected_policy,
            clock=selected_clock,
            new_context_id=new_context_id,
            effects=effects,
        )

    def _create(
        self,
        understanding_id: str,
        surface_locator: str,
        scope_path: str,
        support: m.SupportDependency,
        *,
        scope: m.EvidenceScope | None = None,
        surface_kind: m.SurfaceKind = m.SurfaceKind.FILE,
        repository_id: str = "repo-1",
        context_id: m.InvestigationContextId = CONTEXT_ID,
        assertion_nature: m.AssertionNature = m.AssertionNature.DESCRIPTIVE,
        store: LifecycleStore | None = None,
    ) -> None:
        semantic_scope = (
            m.EvidenceScope(paths=(scope_path,)) if scope is None else scope
        )
        selected_store = self.store if store is None else store
        selected_store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id=repository_id,
                    request_id=m.RequestId(f"req-{understanding_id}"),
                    context_id=context_id,
                ),
                surface=m.SurfaceKey(
                    repository_id=repository_id,
                    kind=surface_kind,
                    locator=surface_locator,
                ),
                target=m.ExplicitTarget(
                    question=f"What does {understanding_id} do?",
                    scope=semantic_scope,
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="It does something.",
                        assertion_nature=assertion_nature,
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
        context = self.store.get_context(
            result.reestablishment_contexts[0].context_id.value
        )
        self.assertEqual(context.origin, m.ContextOrigin.CHANGED_SUPPORT)
        self.assertEqual(
            context.scope,
            m.EvidenceScope(
                paths=("src/a.py", "src/b.py"),
                evidence_refs=(self.store.get_source_observation("obs-a").evidence,),
            ),
        )

    def test_interrupted_discovery_returns_no_partial_effect_or_context(self) -> None:
        request = m.ReconsiderRequest(
            repository_id="repo-1",
            changed_paths=("src/a.py",),
        )
        reverse_lookup = self.store.support_dependents

        def interrupted(kind, ref):
            if kind == "PREMISE":
                raise OSError("reverse index unavailable")
            return reverse_lookup(kind, ref)

        for lookup, fault in (
            ("source_observation_ids_for_locator", OSError("source index unavailable")),
            ("support_dependents", interrupted),
        ):
            with (
                self.subTest(lookup=lookup),
                mock.patch.object(self.store, lookup, side_effect=fault),
                mock.patch.object(self.store, "put_context") as write_context,
            ):
                result = self.service.reconsider(request)
                self.assertIsInstance(result, m.Unavailable)
                assert isinstance(result, m.Unavailable)
                self.assertEqual(result.operation, "reconsider")
                self.assertIn("original repository_id", result.recovery)
                self.assertIn("changed_paths and changed_surfaces", result.recovery)
                write_context.assert_not_called()

        retried = self.service.reconsider(request)
        assert isinstance(retried, m.Changed)
        self.assertEqual(
            {item.surface.locator for item in retried.surfaces},
            {"src/a.py", "src/b.py", "svc"},
        )

    def test_reasons_are_specific_to_the_revision_not_its_surface(self) -> None:
        self._create(
            "u-b-direct",
            "src/b.py",
            "src/b.py",
            m.SourceSupport(observation_id=m.SourceObservationId("obs-a")),
        )
        result = self.service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        assert isinstance(result, m.Changed)
        affected = next(
            item for item in result.surfaces if item.surface.locator == "src/b.py"
        )
        reasons = {
            item.ref.understanding_id.value: set(item.reasons)
            for item in affected.conclusions
        }
        self.assertEqual(
            reasons,
            {
                "u-b": {m.ChangeReason.INDIRECT},
                "u-b-direct": {m.ChangeReason.DIRECT},
            },
        )
        self.assertEqual(
            set(affected.reasons), {m.ChangeReason.DIRECT, m.ChangeReason.INDIRECT}
        )

    def test_direct_seed_reached_as_premise_retains_both_reasons(self) -> None:
        direct = m.ConclusionRevisionRef(
            m.UnderstandingId("u-a"),
            m.ConclusionId("c-1"),
            m.ConclusionRevisionNumber(1),
        )
        dependent = m.ConclusionRevisionRef(
            m.UnderstandingId("u-b"),
            m.ConclusionId("c-1"),
            m.ConclusionRevisionNumber(1),
        )
        result = support_rules.dependency_change_reasons(
            {direct, dependent}, {dependent}
        )
        self.assertEqual(result[direct], {m.ChangeReason.DIRECT})
        self.assertEqual(
            result[dependent], {m.ChangeReason.DIRECT, m.ChangeReason.INDIRECT}
        )
        self.assertEqual(
            support_rules.unvisited_premises((dependent, direct), {direct}),
            (dependent,),
        )

    def test_curated_revision_reconsiders_without_mutating_curation(self) -> None:
        self.store.record_understanding(
            m.UpdateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-u-a-curate"),
                    context_id=CONTEXT_ID,
                ),
                understanding_id=m.UnderstandingId("u-a"),
                expected_version=m.UnderstandingVersionNumber(1),
                curate=(
                    m.CurateConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        reasoning="reviewed for shared reuse",
                    ),
                ),
                provenance="reviewer-session",
            )
        )
        before = self.store.get_curations("u-a")
        self.assertEqual(len(before), 1)

        result = self.service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )

        affected = next(
            conclusion
            for surface in result.surfaces
            for conclusion in surface.conclusions
            if conclusion.ref.understanding_id.value == "u-a"
        )
        self.assertEqual(affected.ref.revision.value, 1)
        self.assertEqual(affected.expected_version.value, 2)
        self.assertEqual(self.store.get_curations("u-a"), before)

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

    def test_changed_scope_context_does_not_admit_current_support(self) -> None:
        support = mock.Mock(spec=SupportService)
        support.qualify_support.side_effect = lambda evaluation: m.compact_support(
            evaluation, ()
        )
        support.evaluate_revision.return_value = support_rules.evaluation(
            m.SupportState.CURRENT,
            NOW,
            "",
        )
        service = self._service(support=support)
        (self.root / "src/new-member.py").write_text("new\n", encoding="utf-8")
        result = service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertEqual(result.reestablishment_contexts, ())

    def test_changed_scope_context_admits_existing_source_support(self) -> None:
        result = self.service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertTrue(
            self.store.has_admitted_observation(
                result.reestablishment_contexts[0].context_id.value, "obs-a"
            )
        )

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

    def test_result_bound_does_not_cut_dependency_discovery(self) -> None:
        policy = m.ServiceBoundsPolicy(
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
        )
        service = self._service(policy=policy)
        result = service.preview_changed_scope(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertFalse(result.truncated)
        self.assertEqual(
            {item.surface.locator for item in result.surfaces},
            {"src/a.py", "src/b.py", "svc"},
        )
        self.assertEqual(result.reestablishment_contexts, ())

    def test_depth_bound_does_not_cut_dependency_discovery(self) -> None:
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
        policy = m.ServiceBoundsPolicy(
            default_query_bounds=bounds,
            maximum_query_bounds=bounds,
            hook_fast_bounds=bounds,
        )
        service = self._service(policy=policy)
        result = service.preview_changed_scope(
            m.ReconsiderRequest(
                repository_id="repo-1",
                changed_paths=("src/a.py",),
            )
        )
        self.assertFalse(result.truncated)
        locators = {item.surface.locator for item in result.surfaces}
        self.assertTrue({"src/b.py", "src/c.py"} <= locators)
        self.assertEqual(result.reestablishment_contexts, ())

    def test_installation_effect_engine_uses_repository_runtime(self) -> None:
        self._create(
            "u-installation-engine",
            "src/coordinator.py",
            "src/coordinator.py",
            m.SourceSupport(observation_id=m.SourceObservationId("obs-a")),
            assertion_nature=m.AssertionNature.NORMATIVE,
        )
        runtime = mock.Mock(
            repository_id="repo-1",
            root=str(self.root),
            store=self.store,
            evidence=FilesystemEvidenceSource("repo-1", str(self.root)),
        )
        engine = DependencyEffectService(
            repository_runtime=lambda repository_id: (
                runtime
                if repository_id == "repo-1"
                else self.fail(f"unexpected repository: {repository_id}")
            ),
            registered_repository_ids=lambda: ("repo-1",),
            support_for_repository=lambda repository_id: (
                self.support
                if repository_id == "repo-1"
                else self.fail(f"unexpected repository: {repository_id}")
            ),
            functional_route_impacts=lambda _repository_id, _paths, _surfaces: (),
            clock=lambda: NOW,
            new_context_id=lambda: "ctx-fp-installation-engine",
        )

        surfaces, contexts, refs = engine.functional_pyramid_change(
            newly_active_repositories=("repo-1",),
        )

        affected = next(
            conclusion
            for surface in surfaces
            for conclusion in surface.conclusions
            if conclusion.ref.understanding_id.value == "u-installation-engine"
        )
        self.assertIsInstance(affected.support, m.SupportQualification)
        assert isinstance(affected.support, m.SupportQualification)
        self.assertEqual(
            affected.support.state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        self.assertEqual(refs, (affected.ref,))
        self.assertEqual(
            tuple(context.repository_id for context in contexts),
            ("repo-1",),
        )
        context = self.store.get_context(contexts[0].context_id.value)
        self.assertEqual(context.origin, m.ContextOrigin.CHANGED_SUPPORT)

    def test_newly_active_repository_reassesses_pre_route_normative_revision(
        self,
    ) -> None:
        self._create(
            "u-pre-route",
            "src/pre_route.py",
            "src/pre_route.py",
            m.SourceSupport(observation_id=m.SourceObservationId("obs-a")),
            assertion_nature=m.AssertionNature.NORMATIVE,
        )
        effects = self._effects(
            new_context_id=lambda: "ctx-fp-activate",
            clock=lambda: NOW,
        )

        surfaces, contexts, refs = effects.functional_pyramid_change(
            newly_active_repositories=("repo-1",)
        )

        affected = next(
            conclusion
            for surface in surfaces
            for conclusion in surface.conclusions
            if conclusion.ref.understanding_id.value == "u-pre-route"
        )
        self.assertIsInstance(affected.support, m.SupportQualification)
        assert isinstance(affected.support, m.SupportQualification)
        self.assertEqual(
            affected.support.state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        self.assertIn(affected.ref, refs)
        self.assertEqual(
            tuple(context.repository_id for context in contexts),
            ("repo-1",),
        )

    def test_retained_activation_effect_stays_actionable_without_route_support(
        self,
    ) -> None:
        self._create(
            "u-pre-route-retained",
            "src/pre_route_retained.py",
            "src/pre_route_retained.py",
            m.SourceSupport(observation_id=m.SourceObservationId("obs-a")),
            assertion_nature=m.AssertionNature.NORMATIVE,
        )
        effects = self._effects(
            new_context_id=lambda: "ctx-fp-retained",
            clock=lambda: NOW,
        )
        _, _, refs = effects.functional_pyramid_change(
            newly_active_repositories=("repo-1",)
        )

        surfaces, contexts = effects.retained_functional_pyramid_effects(refs)

        retained = next(
            conclusion
            for surface in surfaces
            for conclusion in surface.conclusions
            if conclusion.ref.understanding_id.value == "u-pre-route-retained"
        )
        self.assertIsInstance(retained.support, m.SupportQualification)
        assert isinstance(retained.support, m.SupportQualification)
        self.assertEqual(
            retained.support.state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        self.assertIn("governing support", retained.support.reason)
        self.assertEqual(
            tuple(context.repository_id for context in contexts),
            ("repo-1",),
        )

    def test_deliberately_inactive_repository_reassesses_recorded_route(
        self,
    ) -> None:
        self._create(
            "u-governed",
            "src/governed.py",
            "src/governed.py",
            m.FunctionalRouteSupport(
                repository_id="repo-1",
                pyramid_id=m.FunctionalPyramidId("fp-1"),
                semantic_scope=m.EvidenceScope(paths=("src/governed.py",)),
                route_identity=m.FunctionalRouteIdentity("route-old"),
            ),
            assertion_nature=m.AssertionNature.NORMATIVE,
        )
        effects = self._effects(
            new_context_id=lambda: "ctx-fp-deactivate",
            clock=lambda: NOW,
        )

        surfaces, contexts, refs = effects.functional_pyramid_change(
            deliberately_inactive_repositories=("repo-1",)
        )

        affected = next(
            conclusion
            for surface in surfaces
            for conclusion in surface.conclusions
            if conclusion.ref.understanding_id.value == "u-governed"
        )
        self.assertIsInstance(affected.support, m.SupportQualification)
        assert isinstance(affected.support, m.SupportQualification)
        self.assertEqual(
            affected.support.state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        self.assertIn(affected.ref, refs)
        self.assertEqual(contexts[0].repository_id, "repo-1")

    def test_authority_source_change_is_considered_not_forced_stale(self) -> None:
        root_auth = pathlib.Path(self._tmp.name) / "repo-auth"
        root_auth.mkdir()
        (root_auth / "rules").mkdir()
        (root_auth / "rules/governance.md").write_text("governance\n", encoding="utf-8")
        authority = m.AuthorityBinding(
            evidence_ref=m.EvidenceRef(
                evidence_id=m.EvidenceId("authority-1"),
                repository_id="repo-auth",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="rules/governance.md",
                revision_or_fingerprint="sha256:authority",
            ),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        store_auth = LifecycleStore(
            pathlib.Path(self._tmp.name) / "repo-auth.db",
            retention=RETENTION,
            clock=lambda: NOW,
        )
        self.addCleanup(store_auth.close)
        store_auth.register_repository(
            "repo-auth",
            str(root_auth),
            authority_bindings=(authority,),
        )
        context_auth = m.InvestigationContextId("ctx-repo-auth")
        store_auth.put_context(
            m.InvestigationContext(
                context_id=context_auth,
                repository_id="repo-auth",
                request_id=m.RequestId("req-repo-auth"),
                binding_digest=m.ContentDigest("sha256:repo-auth"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(),
                created_at=NOW,
                expires_at=NOW + RETENTION.context_lifetime,
            )
        )
        self._create(
            "u-authority",
            "src/authority_user.py",
            "src/authority_user.py",
            m.AuthoritySupportDependency(authority=authority),
            repository_id="repo-auth",
            context_id=context_auth,
            assertion_nature=m.AssertionNature.NORMATIVE,
            store=store_auth,
        )
        support = mock.Mock(spec=SupportService)
        support.qualify_support.side_effect = lambda evaluation: m.compact_support(
            evaluation, ()
        )
        support.evaluate_revision.return_value = support_rules.evaluation(
            m.SupportState.CURRENT,
            NOW,
            "",
        )
        runtime_auth = mock.Mock(
            repository_id="repo-auth",
            root=str(root_auth),
            store=store_auth,
            evidence=FilesystemEvidenceSource("repo-auth", root_auth),
        )
        effects = DependencyEffectService(
            repository_runtime=lambda repository_id: (
                runtime_auth
                if repository_id == "repo-auth"
                else self.fail(f"unexpected repository: {repository_id}")
            ),
            registered_repository_ids=lambda: ("repo-auth",),
            support_for_repository=lambda repository_id: (
                support
                if repository_id == "repo-auth"
                else self.fail(f"unexpected repository: {repository_id}")
            ),
            functional_route_impacts=lambda _repository_id, _paths, _surfaces: (),
            clock=lambda: NOW,
        )
        service = ReconsiderService(
            store=store_auth,
            effects=effects,
            clock=lambda: NOW,
        )

        result = service.reconsider(
            m.ReconsiderRequest(
                repository_id="repo-auth",
                changed_paths=("rules/governance.md",),
            )
        )

        affected = next(
            conclusion
            for surface in result.surfaces
            for conclusion in surface.conclusions
            if conclusion.ref.understanding_id.value == "u-authority"
        )
        self.assertIn(m.ChangeReason.DIRECT, affected.reasons)
        self.assertIsInstance(affected.support, m.SupportQualification)
        assert isinstance(affected.support, m.SupportQualification)
        self.assertEqual(affected.support.state, m.SupportState.CURRENT)
        self.assertEqual(result.reestablishment_contexts, ())

        # A removed binding cannot be rediscovered from the post-replacement
        # store. The installer supplies its old identity to the same engine.
        store_auth.register_repository(
            "repo-auth", str(root_auth), authority_bindings=()
        )
        support.evaluate_revision.return_value = support_rules.evaluation(
            m.SupportState.REASSESSMENT_REQUIRED,
            NOW,
            "authority binding removed",
        )
        surfaces, contexts, refs = effects.functional_pyramid_change(
            changed_authority_refs=(authority.evidence_ref,)
        )
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].understanding_id.value, "u-authority")
        self.assertEqual(len(contexts), 1)
        self.assertEqual(
            surfaces[0].conclusions[0].support.state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )

    def test_governance_only_change_crosses_physical_repository_boundary(
        self,
    ) -> None:
        root_two = pathlib.Path(self._tmp.name) / "repo-two"
        root_two.mkdir()
        (root_two / "src").mkdir()
        store_two = LifecycleStore(
            pathlib.Path(self._tmp.name) / "repo-two.db",
            retention=RETENTION,
            clock=lambda: NOW,
        )
        self.addCleanup(store_two.close)
        store_two.register_repository("repo-2", str(root_two))
        context_two = m.InvestigationContextId("ctx-repo-2")
        store_two.put_context(
            m.InvestigationContext(
                context_id=context_two,
                repository_id="repo-2",
                request_id=m.RequestId("req-repo-2"),
                binding_digest=m.ContentDigest("sha256:repo-2"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(),
                created_at=NOW,
                expires_at=NOW + RETENTION.context_lifetime,
            )
        )
        route_id = m.FunctionalRouteIdentity("route-cross-repo")
        self._create(
            "u-repo-2",
            "src/remote.py",
            "src/remote.py",
            m.FunctionalRouteSupport(
                repository_id="repo-2",
                pyramid_id=m.FunctionalPyramidId("fp-1"),
                semantic_scope=m.EvidenceScope(paths=("src/remote.py",)),
                route_identity=route_id,
            ),
            repository_id="repo-2",
            context_id=context_two,
            assertion_nature=m.AssertionNature.NORMATIVE,
            store=store_two,
        )
        support = mock.Mock(spec=SupportService)
        support.qualify_support.side_effect = lambda evaluation: m.compact_support(
            evaluation, ()
        )
        support.evaluate_revision.return_value = support_rules.evaluation(
            m.SupportState.REASSESSMENT_REQUIRED,
            NOW,
            "governing route changed",
        )
        runtime_one = mock.Mock(
            repository_id="repo-1",
            root=str(self.root),
            store=self.store,
            evidence=FilesystemEvidenceSource("repo-1", self.root),
        )
        runtime_two = mock.Mock(
            repository_id="repo-2",
            root=str(root_two),
            store=store_two,
            evidence=FilesystemEvidenceSource("repo-2", root_two),
        )
        runtimes = {"repo-1": runtime_one, "repo-2": runtime_two}
        effects = DependencyEffectService(
            repository_runtime=lambda repository_id: runtimes[repository_id],
            registered_repository_ids=lambda: ("repo-1", "repo-2"),
            support_for_repository=lambda repository_id: support,
            functional_route_impacts=lambda repository_id, paths, surfaces: (
                (route_id,)
                if repository_id == "repo-1"
                and paths == ("docs/functional-pyramid.json",)
                and not surfaces
                else ()
            ),
            new_context_id=lambda: "ctx-cross-repo",
            clock=lambda: NOW,
        )
        service = self._service(
            support=support,
            effects=effects,
        )
        request = m.ReconsiderRequest(
            repository_id="repo-1",
            changed_paths=("docs/functional-pyramid.json",),
        )
        before_one = tuple(self.store._connection.iterdump())
        before_two = tuple(store_two._connection.iterdump())

        preview = service.preview_changed_scope(request)

        self.assertEqual(tuple(self.store._connection.iterdump()), before_one)
        self.assertEqual(tuple(store_two._connection.iterdump()), before_two)
        self.assertEqual(preview.reestablishment_contexts, ())
        result = service.reconsider(request)
        self.assertEqual(preview.surfaces, result.surfaces)
        self.assertEqual(preview.omitted, result.omitted)
        self.assertEqual(preview.truncated, result.truncated)

        remote = next(
            surface
            for surface in result.surfaces
            if surface.surface.repository_id == "repo-2"
        )
        self.assertEqual(remote.reasons, (m.ChangeReason.DIRECT,))
        self.assertEqual(
            remote.conclusions[0].support.state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        self.assertEqual(
            tuple(context.repository_id for context in result.reestablishment_contexts),
            ("repo-2",),
        )
        context = store_two.get_context(
            result.reestablishment_contexts[0].context_id.value
        )
        self.assertEqual(context.repository_id, "repo-2")
        self.assertEqual(context.origin, m.ContextOrigin.CHANGED_SUPPORT)

    def test_unknown_challenge_understanding_is_rejected(self) -> None:
        with self.assertRaises(RecordingValidationError):
            self.service.reconsider(
                m.ReconsiderRequest(
                    repository_id="repo-1",
                    challenge=m.ChallengeRaise(
                        request_id="challenge-missing",
                        understanding_id="u:missing",
                        target_version=1,
                        target_conclusions=(
                            m.ChallengeConclusionRef(
                                understanding_id="u:missing",
                                conclusion_id="c-1",
                                revision=1,
                            ),
                        ),
                        reason="disputed",
                    ),
                )
            )

    def test_challenge_is_raised_through_reconsider(self) -> None:
        target = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-a"),
            conclusion_id=m.ConclusionId("c-1"),
            revision=m.ConclusionRevisionNumber(1),
        )
        result = self.service.reconsider(
            m.ReconsiderRequest(
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
        service = self._service(support=support)
        (self.root / "src/new-member.py").write_text("new\n", encoding="utf-8")
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
        self.assertTrue(
            self.store.has_admitted_discovery(
                result.reestablishment_contexts[0].context_id.value, "disc-1"
            )
        )

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
        service = self._service(
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
        self.assertNotEqual(
            second.reestablishment_contexts, first.reestablishment_contexts
        )
        context = self.store.get_context(
            second.reestablishment_contexts[0].context_id.value
        )
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
                self.assertEqual(context.origin, m.ContextOrigin.CHALLENGE)
                self.assertEqual(context.scope, scope)
                self.assertFalse(
                    m.evidence_scope_contains(
                        context.scope, m.EvidenceScope(paths=("src/b.py",))
                    )
                )

    def test_changed_scope_preview_reuses_projection_without_context_issuance(self):
        request = m.ReconsiderRequest(
            repository_id="repo-1",
            changed_paths=("src/a.py",),
        )
        before = tuple(self.store._connection.iterdump())

        preview = self.service.preview_changed_scope(request)

        self.assertEqual(tuple(self.store._connection.iterdump()), before)
        normal = self.service.reconsider(request)
        self.assertEqual(preview.surfaces, normal.surfaces)
        self.assertEqual(preview.omitted, normal.omitted)
        self.assertEqual(preview.truncated, normal.truncated)
        self.assertEqual(preview.reestablishment_contexts, ())
        self.assertTrue(normal.reestablishment_contexts)
        by_surface = {item.surface.locator: item for item in preview.surfaces}
        self.assertIn(m.ChangeReason.DIRECT, by_surface["src/a.py"].reasons)
        self.assertIn(m.ChangeReason.INDIRECT, by_surface["src/b.py"].reasons)
