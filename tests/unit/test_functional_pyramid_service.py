"""Functional Pyramid source/service orchestration tests (T02)."""

import contextlib
import datetime
import threading
import unittest

from span.core import model as m
from span.core.recording import RecordingConflict
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidRepositoryUnavailable,
)
from span.service.functional_pyramid import FunctionalPyramidService


def _ref(repository_id: str, locator: str) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{repository_id}-{locator}"),
        repository_id=repository_id,
        source_kind=m.EvidenceSourceKind.CONFIGURATION,
        locator=locator,
        revision_or_fingerprint=f"digest-{repository_id}-{locator}",
    )


def _scope() -> m.FunctionalScope:
    return m.FunctionalScope(
        (m.FunctionalScopeSelector(m.FunctionalScopeSelectorKind.PREFIX, path="src"),)
    )


def _declaration() -> m.FunctionalPyramidDeclaration:
    return m.FunctionalPyramidDeclaration(
        version=1,
        contexts=(
            m.FunctionalContextDeclaration(
                context_id="ctx",
                coverage=_scope(),
            ),
        ),
    )


class _Declarations:
    def __init__(self) -> None:
        self.bootstrap: tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None = None
        self.results: dict[
            tuple[str, str],
            (
                tuple[m.EvidenceRef, m.FunctionalPyramidDeclaration]
                | m.EvidenceSourceFailure
                | Exception
            ),
        ] = {}
        self.calls: list[tuple[str, m.EvidenceRequest]] = []

    def read_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        return self.bootstrap

    def read_declaration(
        self, repository_id: str, request: m.EvidenceRequest
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidDeclaration] | m.EvidenceSourceFailure:
        self.calls.append((repository_id, request))
        result = self.results[(repository_id, request.locator)]
        if isinstance(result, Exception):
            raise result
        return result


class _Authority:
    def __init__(self) -> None:
        self.bindings: dict[tuple[str, str], m.AuthorityBinding] = {}
        self.calls: list[tuple[str, str]] = []

    def resolve_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding:
        self.calls.append((repository_id, authority_ref))
        try:
            return self.bindings[(repository_id, authority_ref)]
        except KeyError as exc:
            raise ValueError("unknown authority") from exc


class _State:
    def __init__(self) -> None:
        self.retention = m.LifecycleRetention(
            context_lifetime=datetime.timedelta(hours=1),
            replay_retention=datetime.timedelta(hours=2),
        )
        self.active: dict[str, m.FunctionalPyramidId] = {}
        self.versions: dict[m.FunctionalPyramidId, m.FunctionalPyramidVersion] = {}
        self.members: dict[
            tuple[m.FunctionalPyramidId, m.FunctionalPyramidVersion],
            tuple[m.FunctionalPyramidMemberView, ...],
        ] = {}
        self.excluded: set[str] = set()
        self.receipts: dict[str, m.RetrievedFunctionalPyramidReceipt] = {}
        self.transaction_paths: list[tuple[tuple[str, str], ...]] = []

    def active_pyramid_id(self, repository_id: str) -> m.FunctionalPyramidId | None:
        return self.active.get(repository_id)

    def pyramid_version(
        self, pyramid_id: m.FunctionalPyramidId
    ) -> m.FunctionalPyramidVersion | None:
        return self.versions.get(pyramid_id)

    def pyramid_members(
        self,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion | None = None,
    ) -> tuple[m.FunctionalPyramidMemberView, ...]:
        selected = version or self.versions.get(pyramid_id)
        if selected is None:
            return ()
        return self.members.get((pyramid_id, selected), ())

    def is_excluded(self, repository_id: str) -> bool:
        return repository_id in self.excluded

    def receipt(
        self, request_id: m.RequestId
    ) -> m.RetrievedFunctionalPyramidReceipt | None:
        return self.receipts.get(request_id.value)

    @contextlib.contextmanager
    def transaction(self, repository_paths=()):
        paths = tuple(repository_paths)
        self.transaction_paths.append(paths)
        yield self

    def write_pyramid_version(
        self,
        *,
        pyramid_id,
        version,
        content_digest,
        committed_at,
        members,
    ) -> None:
        del content_digest, committed_at
        self.versions[pyramid_id] = version
        self.members[(pyramid_id, version)] = members

    def set_current_pyramid(self, *, pyramid_id, version, members) -> None:
        for repository_id, active_id in tuple(self.active.items()):
            if active_id == pyramid_id:
                del self.active[repository_id]
        for member in members:
            self.active[member.repository_id] = pyramid_id
            self.excluded.discard(member.repository_id)
        self.versions[pyramid_id] = version

    def clear_current_pyramid(self, pyramid_id) -> None:
        for repository_id, active_id in tuple(self.active.items()):
            if active_id == pyramid_id:
                del self.active[repository_id]
        self.versions.pop(pyramid_id, None)

    def set_excluded(self, repository_id: str, excluded: bool) -> None:
        if excluded:
            self.excluded.add(repository_id)
        else:
            self.excluded.discard(repository_id)

    def write_receipt(self, receipt, *, replay_expires_at) -> None:
        del replay_expires_at
        self.receipts[receipt.request_id.value] = receipt

    def write_reestablishment_context(
        self,
        context,
        *,
        source_observation_ids=(),
        discovery_observation_ids=(),
    ) -> None:
        del context, source_observation_ids, discovery_observation_ids


class FunctionalPyramidServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.declarations = _Declarations()
        self.authority = _Authority()
        self.service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=self.authority,
        )
        self.state = _State()
        self.effect_calls = []
        self.retained_effect_calls = []

        def project_effects(transaction, action, pyramid_id, old_members, new_members):
            self.effect_calls.append(
                (transaction, action, pyramid_id, old_members, new_members)
            )
            return (), (), ()

        def project_retained(transaction, refs):
            self.retained_effect_calls.append((transaction, refs))
            return (), ()

        self.admin_service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=self.authority,
            state=self.state,
            registered_repository_ids=lambda: ("repo-a", "repo-b"),
            repository_paths=lambda repository_ids: tuple(
                (repository_id, f"/stores/{repository_id}.db")
                for repository_id in sorted(repository_ids)
            ),
            effect_projection=project_effects,
            retained_effect_projection=project_retained,
            clock=lambda: datetime.datetime(
                2026, 11, 21, 0, 0, tzinfo=datetime.timezone.utc
            ),
        )

    def test_optional_bootstrap_absence_does_not_imply_exclusion(self):
        self.assertIsNone(self.service.discover_bootstrap("repo-a"))

    def test_ranged_candidate_source_is_rejected_before_port_read(self):
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(
                m.EvidenceRequest(
                    "decl.json",
                    ranges=(m.SourceRange(1, 3),),
                ),
            ),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        members, declarations, available, validation, graph = (
            self.service.load_candidate_members((intent,))
        )
        self.assertEqual(self.declarations.calls, [])
        self.assertEqual(members, ())
        self.assertEqual(declarations, ())
        self.assertEqual(available, frozenset({"repo-a"}))
        self.assertEqual(
            {item.reason for item in validation},
            {m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE},
        )
        self.assertEqual(
            {item.reason for item in graph},
            {m.FunctionalPyramidFindingReason.INVALID_DECLARATION},
        )

    def test_missing_and_invalid_sources_use_closed_candidate_reasons(self):
        missing_request = m.EvidenceRequest("missing.json")
        invalid_request = m.EvidenceRequest("invalid.json")
        self.declarations.results[("repo-a", "missing.json")] = m.EvidenceSourceFailure(
            missing_request,
            m.EvidenceSourceFailureKind.MISSING,
            "missing",
        )
        self.declarations.results[("repo-a", "invalid.json")] = (
            FunctionalPyramidDeclarationInvalid("invalid declaration")
        )
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(missing_request, invalid_request),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )

        _, _, _, validation, graph = self.service.load_candidate_members((intent,))
        self.assertEqual(
            {item.reason for item in validation},
            {
                m.FunctionalPyramidValidationReason.MISSING_DECLARATION_SOURCE,
                m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE,
            },
        )
        self.assertEqual(
            {item.reason for item in graph},
            {m.FunctionalPyramidFindingReason.INVALID_DECLARATION},
        )

    def test_repository_unavailability_is_graph_state_not_unknown_identity(self):
        request = m.EvidenceRequest("decl.json")
        self.declarations.results[("repo-a", "decl.json")] = (
            FunctionalPyramidRepositoryUnavailable("offline")
        )
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(request,),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        _, _, available, validation, graph = self.service.load_candidate_members(
            (intent,)
        )
        self.assertEqual(available, frozenset())
        self.assertEqual(validation, ())
        self.assertEqual(
            {item.reason for item in graph},
            {m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE},
        )

    def test_valid_candidate_source_returns_resolved_member_view(self):
        request = m.EvidenceRequest("decl.json")
        self.declarations.results[("repo-a", "decl.json")] = (
            _ref("repo-a", "decl.json"),
            _declaration(),
        )
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(request,),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        members, declarations, available, validation, graph = (
            self.service.load_candidate_members((intent,))
        )
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].declaration_refs, (_ref("repo-a", "decl.json"),))
        self.assertEqual(declarations, (("repo-a", _declaration()),))
        self.assertEqual(available, frozenset({"repo-a"}))
        self.assertEqual(validation, ())
        self.assertEqual(graph, ())

    def test_rule_owner_uses_existing_authority_resolver(self):
        declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx",
                    coverage=_scope(),
                    rules=(m.FunctionalGraphRef("repo-a", "rule-p0"),),
                ),
            ),
            rules=(
                m.FunctionalRuleDeclaration(
                    rule_id="rule-p0",
                    layer=m.FunctionalPyramidLayer.P0,
                    owner=m.FunctionalRuleOwner("repo-a", "rules/p0.md"),
                    governing_rule_ids=("ROOT",),
                ),
            ),
        )
        self.declarations.results[("repo-a", "decl.json")] = (
            _ref("repo-a", "decl.json"),
            declaration,
        )
        binding = m.AuthorityBinding(
            evidence_ref=m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-p0"),
                repository_id="repo-a",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="rules/p0.md",
                revision_or_fingerprint="digest-p0",
            ),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        self.authority.bindings[("repo-a", "rules/p0.md")] = binding
        member = m.FunctionalPyramidMemberView(
            repository_id="repo-a",
            declaration_refs=(_ref("repo-a", "decl.json"),),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )

        view, _ = self.service.resolve(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=(member,),
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
        )
        self.assertEqual(self.authority.calls, [("repo-a", "rules/p0.md")])
        self.assertEqual(view.rules[0].authority, binding)

    def test_status_projects_inactive_and_live_active_health(self):
        self.assertEqual(
            self.admin_service.status(
                m.FunctionalPyramidSelector(repository_id="repo-a")
            ),
            m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.UNCONFIGURED
            ),
        )
        self.state.excluded.add("repo-a")
        self.assertEqual(
            self.admin_service.status(
                m.FunctionalPyramidSelector(repository_id="repo-a")
            ),
            m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.EXCLUDED
            ),
        )

        self.state.excluded.clear()
        pyramid_id = m.FunctionalPyramidId("fp-1")
        version = m.FunctionalPyramidVersion(1)
        member = m.FunctionalPyramidMemberView(
            repository_id="repo-a",
            declaration_refs=(_ref("repo-a", "decl.json"),),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        self.state.active["repo-a"] = pyramid_id
        self.state.versions[pyramid_id] = version
        self.state.members[(pyramid_id, version)] = (member,)
        self.declarations.results[("repo-a", "decl.json")] = (
            _ref("repo-a", "decl.json"),
            _declaration(),
        )
        status = self.admin_service.status(
            m.FunctionalPyramidSelector(repository_id="repo-a")
        )
        self.assertEqual(status.state, m.FunctionalPyramidParticipationState.ACTIVE)
        self.assertEqual(status.health, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(status.findings, ())
        self.assertEqual(status.pyramid_id, pyramid_id)
        self.assertEqual(status.version, version)

    def test_candidate_reports_duplicate_unregistered_and_other_active_members(self):
        request = m.EvidenceRequest("decl.json")
        intent_a = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(request,),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        intent_unknown = m.FunctionalPyramidMemberIntent(
            repository_id="repo-x",
            declaration_sources=(request,),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        self.state.active["repo-a"] = m.FunctionalPyramidId("fp-other")
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(intent_a, intent_a, intent_unknown),
            )
        )
        self.assertFalse(candidate.activation_ready)
        self.assertEqual(
            {finding.reason for finding in candidate.validation_findings},
            {
                m.FunctionalPyramidValidationReason.DUPLICATE_MEMBER,
                m.FunctionalPyramidValidationReason.UNREGISTERED_MEMBER,
                m.FunctionalPyramidValidationReason.MEMBER_ALREADY_ACTIVE,
            },
        )
        self.assertEqual(candidate.members, ())

    def test_revision_candidate_reports_unknown_and_stale_target(self):
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(m.EvidenceRequest("decl.json"),),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        unknown = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.REVISE,
                members=(intent,),
                pyramid_id=m.FunctionalPyramidId("missing"),
                expected_version=m.FunctionalPyramidVersion(1),
            )
        )
        self.assertIn(
            m.FunctionalPyramidValidationReason.UNKNOWN_PYRAMID,
            {finding.reason for finding in unknown.validation_findings},
        )

        pyramid_id = m.FunctionalPyramidId("fp-1")
        self.state.versions[pyramid_id] = m.FunctionalPyramidVersion(2)
        self.state.active["repo-a"] = pyramid_id
        self.declarations.results[("repo-a", "decl.json")] = (
            _ref("repo-a", "decl.json"),
            _declaration(),
        )
        stale = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.REVISE,
                members=(intent,),
                pyramid_id=pyramid_id,
                expected_version=m.FunctionalPyramidVersion(1),
            )
        )
        finding = next(
            item
            for item in stale.validation_findings
            if item.reason is m.FunctionalPyramidValidationReason.STALE_PYRAMID_VERSION
        )
        self.assertEqual(finding.expected_version, m.FunctionalPyramidVersion(1))
        self.assertEqual(finding.current_version, m.FunctionalPyramidVersion(2))

    def test_complete_coverage_remainder_is_candidate_validation_finding(self):
        request = m.EvidenceRequest("decl.json")
        self.declarations.results[("repo-a", "decl.json")] = (
            _ref("repo-a", "decl.json"),
            m.FunctionalPyramidDeclaration(
                version=1,
                contexts=(
                    m.FunctionalContextDeclaration(
                        context_id="child",
                        coverage=m.FunctionalScope(
                            (
                                m.FunctionalScopeSelector(
                                    m.FunctionalScopeSelectorKind.PREFIX,
                                    path="src/covered",
                                ),
                            )
                        ),
                    ),
                ),
            ),
        )
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(request,),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.COMPLETE,
        )
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(intent,),
            )
        )
        self.assertFalse(candidate.activation_ready)
        self.assertEqual(candidate.graph_findings, ())
        self.assertIn(
            m.FunctionalPyramidValidationReason.INCOMPLETE_COMPLETE_COVERAGE,
            {finding.reason for finding in candidate.validation_findings},
        )

    def test_valid_activate_candidate_is_ready(self):
        request = m.EvidenceRequest("decl.json")
        self.declarations.results[("repo-a", "decl.json")] = (
            _ref("repo-a", "decl.json"),
            _declaration(),
        )
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(request,),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(intent,),
            )
        )
        self.assertTrue(candidate.activation_ready)
        self.assertEqual(candidate.validation_findings, ())
        self.assertEqual(candidate.graph_findings, ())
        self.assertEqual(len(candidate.members), 1)
        self.assertEqual(self.state.active, {})
        self.assertEqual(self.state.excluded, set())
        self.assertEqual(self.state.versions, {})
        self.assertEqual(self.state.receipts, {})

    def _intent(self, repository_id: str) -> m.FunctionalPyramidMemberIntent:
        request = m.EvidenceRequest("decl.json")
        self.declarations.results[(repository_id, "decl.json")] = (
            _ref(repository_id, "decl.json"),
            m.FunctionalPyramidDeclaration(
                version=1,
                contexts=(
                    m.FunctionalContextDeclaration(
                        context_id=f"ctx-{repository_id}",
                        coverage=_scope(),
                    ),
                ),
            ),
        )
        return m.FunctionalPyramidMemberIntent(
            repository_id=repository_id,
            declaration_sources=(request,),
            functional_scope=_scope(),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )

    def test_invalid_activation_leaves_participation_state_unchanged(self):
        intent = self._intent("repo-a")
        self.declarations.results[("repo-a", "decl.json")] = m.EvidenceSourceFailure(
            request=m.EvidenceRequest("decl.json"),
            kind=m.EvidenceSourceFailureKind.MISSING,
            reason="missing",
        )

        with self.assertRaises(ValueError):
            self.admin_service.record(
                request_id=m.RequestId("activate-invalid"),
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(intent,),
            )

        self.assertEqual(self.state.active, {})
        self.assertEqual(self.state.excluded, set())
        self.assertEqual(self.state.versions, {})
        self.assertIsNone(self.state.receipt(m.RequestId("activate-invalid")))

    def test_activation_handoff_status_matches_committed_result(self):
        result = self.admin_service.record(
            request_id=m.RequestId("activate-handoff"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"), self._intent("repo-b")),
        )
        assert result.pyramid_id is not None
        assert result.version is not None

        status = self.admin_service.status(
            m.FunctionalPyramidSelector(pyramid_id=result.pyramid_id)
        )

        self.assertEqual(status.state, m.FunctionalPyramidParticipationState.ACTIVE)
        self.assertEqual(status.health, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(status.pyramid_id, result.pyramid_id)
        self.assertEqual(status.version, result.version)
        self.assertEqual(status.members, result.members)
        self.assertEqual(status.findings, ())

    def test_record_activate_commits_members_effects_and_receipt(self):
        result = self.admin_service.record(
            request_id=m.RequestId("activate-1"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"), self._intent("repo-b")),
        )

        self.assertEqual(result.pyramid_id, m.FunctionalPyramidId("fp:activate-1"))
        self.assertEqual(result.version, m.FunctionalPyramidVersion(1))
        self.assertEqual(
            tuple(effect.repository_id for effect in result.participation_effects),
            ("repo-a", "repo-b"),
        )
        self.assertTrue(
            all(
                effect.state is m.FunctionalPyramidParticipationState.ACTIVE
                for effect in result.participation_effects
            )
        )
        self.assertEqual(
            self.state.active,
            {
                "repo-a": m.FunctionalPyramidId("fp:activate-1"),
                "repo-b": m.FunctionalPyramidId("fp:activate-1"),
            },
        )
        receipt = self.state.receipt(m.RequestId("activate-1"))
        self.assertIsNotNone(receipt)
        self.assertEqual(len(self.effect_calls), 1)
        self.assertEqual(
            self.state.transaction_paths[-1],
            (("repo-a", "/stores/repo-a.db"), ("repo-b", "/stores/repo-b.db")),
        )

    def test_record_replay_preserves_receipt_without_new_effect_discovery(self):
        intent = self._intent("repo-a")
        first = self.admin_service.record(
            request_id=m.RequestId("activate-replay"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        self.assertEqual(len(self.effect_calls), 1)

        replay = self.admin_service.record(
            request_id=m.RequestId("activate-replay"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        self.assertEqual(replay.receipt_selector, first.receipt_selector)
        self.assertEqual(replay.committed_at, first.committed_at)
        self.assertEqual(len(self.effect_calls), 1)
        self.assertEqual(self.retained_effect_calls, [])

    def test_record_replay_live_projects_only_retained_effect_refs(self):
        affected_ref = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-effect"),
            conclusion_id=m.ConclusionId("c-effect"),
            revision=m.ConclusionRevisionNumber(1),
        )
        affected_surface = m.ChangedSurface(
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            reasons=(m.ChangeReason.DIRECT,),
        )
        initial_context = m.InvestigationContextRef(
            repository_id="repo-a",
            context_id=m.InvestigationContextId("ctx-effect-initial"),
        )
        fresh_context = m.InvestigationContextRef(
            repository_id="repo-a",
            context_id=m.InvestigationContextId("ctx-effect-fresh"),
        )
        effect_calls = []
        retained_calls = []
        live_projection = [[(affected_surface,), (fresh_context,)]]

        def project_effects(transaction, action, pyramid_id, old_members, new_members):
            effect_calls.append(
                (transaction, action, pyramid_id, old_members, new_members)
            )
            return (affected_surface,), (initial_context,), (affected_ref,)

        def project_retained(transaction, refs):
            retained_calls.append((transaction, refs))
            surfaces, contexts = live_projection[0]
            return surfaces, contexts

        service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=self.authority,
            state=self.state,
            registered_repository_ids=lambda: ("repo-a", "repo-b"),
            repository_paths=lambda repository_ids: tuple(
                (repository_id, f"/stores/{repository_id}.db")
                for repository_id in sorted(repository_ids)
            ),
            effect_projection=project_effects,
            retained_effect_projection=project_retained,
            clock=lambda: datetime.datetime(
                2026, 11, 21, 0, 0, tzinfo=datetime.timezone.utc
            ),
        )
        intent = self._intent("repo-a")

        first = service.record(
            request_id=m.RequestId("activate-live-replay"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        receipt = self.state.receipt(m.RequestId("activate-live-replay"))
        assert receipt is not None
        self.assertEqual(first.dependent_effects, (affected_surface,))
        self.assertEqual(first.reestablishment_contexts, (initial_context,))
        self.assertEqual(receipt.dependent_effect_refs, (affected_ref,))

        replay = service.record(
            request_id=m.RequestId("activate-live-replay"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        self.assertEqual(replay.dependent_effects, (affected_surface,))
        self.assertEqual(replay.reestablishment_contexts, (fresh_context,))
        self.assertEqual(self.state.receipt(receipt.request_id), receipt)
        self.assertEqual(len(effect_calls), 1)
        self.assertEqual(retained_calls[-1][1], (affected_ref,))

        live_projection[0] = [(), ()]
        repaired = service.record(
            request_id=m.RequestId("activate-live-replay"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        self.assertEqual(repaired.dependent_effects, ())
        self.assertEqual(repaired.reestablishment_contexts, ())
        self.assertEqual(self.state.receipt(receipt.request_id), receipt)
        self.assertEqual(len(effect_calls), 1)
        self.assertEqual(
            tuple(refs for _, refs in retained_calls),
            ((affected_ref,), (affected_ref,)),
        )

    def test_record_replay_conflict_rejects_different_content(self):
        self.admin_service.record(
            request_id=m.RequestId("same-id"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"),),
        )
        with self.assertRaises(RecordingConflict):
            self.admin_service.record(
                request_id=m.RequestId("same-id"),
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(self._intent("repo-b"),),
            )

    def test_record_revise_only_reports_actual_participation_changes(self):
        activation = self.admin_service.record(
            request_id=m.RequestId("activate-revise"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"), self._intent("repo-b")),
        )
        assert activation.pyramid_id is not None
        assert activation.version is not None

        revision = self.admin_service.record(
            request_id=m.RequestId("revise-1"),
            action=m.FunctionalPyramidAction.REVISE,
            members=(self._intent("repo-a"),),
            pyramid_id=activation.pyramid_id,
            expected_version=activation.version,
        )
        self.assertEqual(revision.pyramid_id, activation.pyramid_id)
        self.assertEqual(revision.version, m.FunctionalPyramidVersion(2))
        self.assertEqual(
            tuple(member.repository_id for member in revision.members),
            ("repo-a",),
        )
        self.assertEqual(
            revision.participation_effects,
            (
                m.FunctionalPyramidParticipationEffect(
                    repository_id="repo-b",
                    state=m.FunctionalPyramidParticipationState.UNCONFIGURED,
                ),
            ),
        )
        self.assertNotIn("repo-b", self.state.active)
        self.assertNotIn("repo-b", self.state.excluded)

        status = self.admin_service.status(
            m.FunctionalPyramidSelector(pyramid_id=activation.pyramid_id)
        )
        self.assertEqual(status.state, m.FunctionalPyramidParticipationState.ACTIVE)
        self.assertEqual(status.health, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(status.pyramid_id, revision.pyramid_id)
        self.assertEqual(status.version, revision.version)
        self.assertEqual(status.members, revision.members)
        self.assertEqual(status.findings, ())

    def test_record_revise_enforces_version_cas(self):
        activation = self.admin_service.record(
            request_id=m.RequestId("activate-cas"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"),),
        )
        assert activation.pyramid_id is not None
        self.state.versions[activation.pyramid_id] = m.FunctionalPyramidVersion(2)

        with self.assertRaises(RecordingConflict):
            self.admin_service.record(
                request_id=m.RequestId("revise-stale"),
                action=m.FunctionalPyramidAction.REVISE,
                members=(self._intent("repo-a"),),
                pyramid_id=activation.pyramid_id,
                expected_version=m.FunctionalPyramidVersion(1),
            )

    def test_concurrent_revise_and_deactivate_obey_version_cas(self):
        activation = self.admin_service.record(
            request_id=m.RequestId("activate-concurrent-cas"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"), self._intent("repo-b")),
        )
        assert activation.pyramid_id is not None
        assert activation.version is not None

        lock = threading.Lock()
        barrier = threading.Barrier(3)

        @contextlib.contextmanager
        def serialized_transaction(repository_paths=()):
            paths = tuple(repository_paths)
            self.state.transaction_paths.append(paths)
            with lock:
                yield self.state

        self.state.transaction = serialized_transaction
        successes: list[m.FunctionalPyramidAction] = []
        failures: list[BaseException] = []

        def revise() -> None:
            try:
                barrier.wait()
                self.admin_service.record(
                    request_id=m.RequestId("revise-concurrent"),
                    action=m.FunctionalPyramidAction.REVISE,
                    members=(self._intent("repo-a"), self._intent("repo-b")),
                    pyramid_id=activation.pyramid_id,
                    expected_version=activation.version,
                )
                successes.append(m.FunctionalPyramidAction.REVISE)
            except BaseException as exc:
                failures.append(exc)

        def deactivate() -> None:
            try:
                barrier.wait()
                self.admin_service.record(
                    request_id=m.RequestId("deactivate-concurrent"),
                    action=m.FunctionalPyramidAction.DEACTIVATE,
                    pyramid_id=activation.pyramid_id,
                    expected_version=activation.version,
                )
                successes.append(m.FunctionalPyramidAction.DEACTIVATE)
            except BaseException as exc:
                failures.append(exc)

        threads = (threading.Thread(target=revise), threading.Thread(target=deactivate))
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        if successes == [m.FunctionalPyramidAction.REVISE]:
            self.assertEqual(
                self.state.versions[activation.pyramid_id],
                m.FunctionalPyramidVersion(2),
            )
            self.assertEqual(
                set(self.state.active),
                {"repo-a", "repo-b"},
            )
            self.assertEqual(self.state.excluded, set())
        else:
            self.assertEqual(
                successes,
                [m.FunctionalPyramidAction.DEACTIVATE],
            )
            self.assertNotIn(activation.pyramid_id, self.state.versions)
            self.assertEqual(self.state.active, {})
            self.assertEqual(self.state.excluded, {"repo-a", "repo-b"})

    def test_record_deactivate_enforces_version_cas(self):
        activation = self.admin_service.record(
            request_id=m.RequestId("activate-deactivate-cas"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"),),
        )
        assert activation.pyramid_id is not None
        self.state.versions[activation.pyramid_id] = m.FunctionalPyramidVersion(2)

        with self.assertRaises(RecordingConflict):
            self.admin_service.record(
                request_id=m.RequestId("deactivate-stale"),
                action=m.FunctionalPyramidAction.DEACTIVATE,
                pyramid_id=activation.pyramid_id,
                expected_version=m.FunctionalPyramidVersion(1),
            )

        self.assertEqual(
            self.state.active["repo-a"],
            activation.pyramid_id,
        )
        self.assertNotIn("repo-a", self.state.excluded)

    def test_record_deactivate_moves_all_members_to_excluded(self):
        activation = self.admin_service.record(
            request_id=m.RequestId("activate-deactivate"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._intent("repo-a"), self._intent("repo-b")),
        )
        assert activation.pyramid_id is not None
        assert activation.version is not None

        result = self.admin_service.record(
            request_id=m.RequestId("deactivate-1"),
            action=m.FunctionalPyramidAction.DEACTIVATE,
            pyramid_id=activation.pyramid_id,
            expected_version=activation.version,
        )
        self.assertEqual(result.members, ())
        self.assertEqual(
            {effect.repository_id for effect in result.participation_effects},
            {"repo-a", "repo-b"},
        )
        self.assertTrue(
            all(
                effect.state is m.FunctionalPyramidParticipationState.EXCLUDED
                for effect in result.participation_effects
            )
        )
        self.assertEqual(self.state.active, {})
        self.assertEqual(self.state.excluded, {"repo-a", "repo-b"})

    def test_record_exclude_has_no_semantic_effect_projection(self):
        result = self.admin_service.record(
            request_id=m.RequestId("exclude-1"),
            action=m.FunctionalPyramidAction.EXCLUDE,
            repository_id="repo-a",
        )
        self.assertEqual(
            result.participation_effects,
            (
                m.FunctionalPyramidParticipationEffect(
                    repository_id="repo-a",
                    state=m.FunctionalPyramidParticipationState.EXCLUDED,
                ),
            ),
        )
        self.assertEqual(result.dependent_effects, ())
        self.assertEqual(result.reestablishment_contexts, ())
        self.assertEqual(self.effect_calls, [])
        self.assertIn("repo-a", self.state.excluded)
