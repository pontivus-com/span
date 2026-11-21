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


class FunctionalPyramidServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.declarations = _Declarations()
        self.authority = _Authority()
        self.service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=self.authority,
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
