"""Functional Pyramid source/service orchestration tests (T02)."""

import unittest

from span.core import model as m
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
        self.active: dict[str, m.FunctionalPyramidId] = {}
        self.versions: dict[m.FunctionalPyramidId, m.FunctionalPyramidVersion] = {}
        self.members: dict[
            tuple[m.FunctionalPyramidId, m.FunctionalPyramidVersion],
            tuple[m.FunctionalPyramidMemberView, ...],
        ] = {}
        self.excluded: set[str] = set()

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
        return None

    def transaction(self, repository_paths=()):
        raise AssertionError("candidate/status do not write state")


class FunctionalPyramidServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.declarations = _Declarations()
        self.authority = _Authority()
        self.service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=self.authority,
        )
        self.state = _State()
        self.admin_service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=self.authority,
            state=self.state,
            registered_repository_ids=lambda: ("repo-a", "repo-b"),
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
