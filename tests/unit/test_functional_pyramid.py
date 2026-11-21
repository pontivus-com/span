"""Version-1 Functional Pyramid domain/algebra tests (T01)."""

import datetime
import unittest

from span.core import model as m
from span.core.functional_pyramid import (
    functional_scope_contains,
    functional_scope_intersects,
    functional_scope_selector_contains,
    functional_scope_selector_intersects,
    functional_scope_uncovered,
    functional_scope_union,
    normalize_functional_scope,
)


def _selector(
    kind: m.FunctionalScopeSelectorKind,
    path: str | None = None,
    locator: str | None = None,
) -> m.FunctionalScopeSelector:
    return m.FunctionalScopeSelector(kind=kind, path=path, locator=locator)


def _scope(*selectors: m.FunctionalScopeSelector) -> m.FunctionalScope:
    return m.FunctionalScope(selectors=selectors)


def _member_intent(repository_id: str = "repo-a") -> m.FunctionalPyramidMemberIntent:
    return m.FunctionalPyramidMemberIntent(
        repository_id=repository_id,
        declaration_sources=(m.EvidenceRequest("docs/functional-pyramid.json"),),
        functional_scope=_scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src")),
        coverage=m.FunctionalPyramidCoverage.PARTIAL,
    )


def _declaration_ref(repository_id: str = "repo-a") -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{repository_id}-functional-pyramid"),
        repository_id=repository_id,
        source_kind=m.EvidenceSourceKind.CONFIGURATION,
        locator="docs/functional-pyramid.json",
        revision_or_fingerprint="digest",
    )


def _member_view(repository_id: str = "repo-a") -> m.FunctionalPyramidMemberView:
    return m.FunctionalPyramidMemberView(
        repository_id=repository_id,
        declaration_refs=(_declaration_ref(repository_id),),
        functional_scope=_scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src")),
        coverage=m.FunctionalPyramidCoverage.PARTIAL,
    )


class FunctionalScopeCarrierTest(unittest.TestCase):
    def test_selector_grammar_is_closed_and_strict(self):
        whole = _selector(m.FunctionalScopeSelectorKind.REPOSITORY)
        self.assertIsNone(whole.path)

        with self.assertRaises(ValueError):
            _selector(m.FunctionalScopeSelectorKind.REPOSITORY, "src")
        with self.assertRaises(ValueError):
            _selector(m.FunctionalScopeSelectorKind.PATH)
        with self.assertRaises(ValueError):
            _selector(m.FunctionalScopeSelectorKind.PATH, "src/a.py", "symbol")
        with self.assertRaises(ValueError):
            _selector(m.FunctionalScopeSelectorKind.SYMBOL, "src/a.py")

        for invalid in (
            "",
            "/src/a.py",
            "./src/a.py",
            "src/../a.py",
            "src//a.py",
            "src/a.py/",
            r"src\a.py",
        ):
            with self.subTest(path=invalid):
                with self.assertRaises(ValueError):
                    _selector(m.FunctionalScopeSelectorKind.PATH, invalid)

    def test_scope_is_non_empty_and_has_no_duplicate_selector(self):
        path = _selector(m.FunctionalScopeSelectorKind.PATH, "src/a.py")
        with self.assertRaises(ValueError):
            m.FunctionalScope(())
        with self.assertRaises(ValueError):
            m.FunctionalScope((path, path))

    def test_selector_containment_and_intersection_follow_symbolic_rules(self):
        repo = _selector(m.FunctionalScopeSelectorKind.REPOSITORY)
        prefix = _selector(m.FunctionalScopeSelectorKind.PREFIX, "src")
        nested = _selector(m.FunctionalScopeSelectorKind.PREFIX, "src/service")
        path = _selector(m.FunctionalScopeSelectorKind.PATH, "src/service/a.py")
        symbol = _selector(
            m.FunctionalScopeSelectorKind.SYMBOL,
            "src/service/a.py",
            "Service.run",
        )
        other = _selector(m.FunctionalScopeSelectorKind.PATH, "ui/view.py")

        self.assertTrue(functional_scope_selector_contains(repo, other))
        self.assertTrue(functional_scope_selector_contains(prefix, nested))
        self.assertTrue(functional_scope_selector_contains(prefix, path))
        self.assertTrue(functional_scope_selector_contains(path, symbol))
        self.assertFalse(functional_scope_selector_contains(path, nested))
        self.assertTrue(functional_scope_selector_intersects(nested, path))
        self.assertFalse(functional_scope_selector_intersects(prefix, other))

    def test_normalization_removes_redundancy_deterministically(self):
        prefix = _selector(m.FunctionalScopeSelectorKind.PREFIX, "src")
        path = _selector(m.FunctionalScopeSelectorKind.PATH, "src/a.py")
        symbol = _selector(m.FunctionalScopeSelectorKind.SYMBOL, "src/a.py", "main")
        other = _selector(m.FunctionalScopeSelectorKind.PATH, "README.md")

        normalized = normalize_functional_scope((symbol, path, prefix, other))
        self.assertEqual(
            normalized,
            _scope(prefix, other),
        )
        self.assertEqual(
            normalize_functional_scope(reversed((symbol, path, prefix, other))),
            normalized,
        )

    def test_scope_union_containment_and_intersection_are_symbolic(self):
        src = _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src"))
        child = _scope(
            _selector(m.FunctionalScopeSelectorKind.PATH, "src/service/a.py")
        )
        docs = _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "docs"))

        self.assertTrue(functional_scope_contains(src, child))
        self.assertFalse(functional_scope_contains(child, src))
        self.assertTrue(functional_scope_intersects(src, child))
        self.assertFalse(functional_scope_intersects(src, docs))
        self.assertEqual(
            functional_scope_union((child, src)),
            src,
        )

    def test_child_prefixes_do_not_prove_open_parent_complete(self):
        member = _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src"))
        coverage = (
            _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src/a")),
            _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src/b")),
        )
        self.assertEqual(
            functional_scope_uncovered(member, coverage),
            member.selectors,
        )

    def test_repository_selector_absorbs_every_narrow_selector(self):
        repo = _scope(_selector(m.FunctionalScopeSelectorKind.REPOSITORY))
        narrow = _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src"))
        self.assertEqual(functional_scope_union((narrow, repo)), repo)
        self.assertTrue(functional_scope_contains(repo, narrow))
        self.assertEqual(functional_scope_uncovered(repo, (narrow,)), repo.selectors)


class FunctionalPyramidCarrierTest(unittest.TestCase):
    def test_closed_vocabularies_match_functional_design(self):
        self.assertEqual(
            {item.value for item in m.FunctionalPyramidFindingReason},
            {
                "UNCOVERED_PATH",
                "INVALID_DECLARATION",
                "UNRESOLVED_SCOPE_INTERSECTION",
                "DUPLICATE_CONTEXT_OWNER",
                "UNKNOWN_CONTEXT",
                "CONTEXT_CYCLE",
                "REPOSITORY_UNAVAILABLE",
                "DUPLICATE_RULE_OWNER",
                "UNKNOWN_RULE",
                "RULE_CYCLE",
                "INVALID_GOVERNING_EDGE",
                "UNRESOLVED_RULE_PARENT",
            },
        )
        self.assertEqual(
            {item.value for item in m.FunctionalPyramidValidationReason},
            {
                "UNREGISTERED_MEMBER",
                "DUPLICATE_MEMBER",
                "MEMBER_ALREADY_ACTIVE",
                "UNKNOWN_PYRAMID",
                "STALE_PYRAMID_VERSION",
                "MISSING_DECLARATION_SOURCE",
                "INVALID_DECLARATION_SOURCE",
                "INVALID_FUNCTIONAL_SCOPE",
                "INCOMPLETE_COMPLETE_COVERAGE",
            },
        )
        self.assertEqual(
            {item.value for item in m.FunctionalPyramidLayer},
            {"P0", "P1", "P2S", "P2W", "P3", "P4"},
        )

    def test_graph_reference_is_repository_qualified(self):
        ref = m.FunctionalGraphRef("repo-a", "C1")
        self.assertEqual(ref.repository_id, "repo-a")
        self.assertEqual(ref.identity, "C1")
        with self.assertRaises(ValueError):
            m.FunctionalGraphRef("", "C1")
        with self.assertRaises(ValueError):
            m.FunctionalGraphRef("repo-a", "")

    def test_nominal_identity_and_version_are_strict(self):
        with self.assertRaises(ValueError):
            m.FunctionalPyramidId("")
        with self.assertRaises(ValueError):
            m.FunctionalRouteIdentity("")
        with self.assertRaises(ValueError):
            m.FunctionalPyramidVersion(0)

    def test_member_intent_requires_repository_and_declaration_source(self):
        with self.assertRaises(ValueError):
            m.FunctionalPyramidMemberIntent(
                repository_id="",
                declaration_sources=(m.EvidenceRequest("decl.json"),),
                functional_scope=_scope(
                    _selector(m.FunctionalScopeSelectorKind.REPOSITORY)
                ),
                coverage=m.FunctionalPyramidCoverage.PARTIAL,
            )
        with self.assertRaises(ValueError):
            m.FunctionalPyramidMemberIntent(
                repository_id="repo-a",
                declaration_sources=(),
                functional_scope=_scope(
                    _selector(m.FunctionalScopeSelectorKind.REPOSITORY)
                ),
                coverage=m.FunctionalPyramidCoverage.PARTIAL,
            )

    def test_candidate_selector_is_action_aware(self):
        member = _member_intent()
        activate = m.FunctionalPyramidCandidateSelector(
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(member,),
        )
        self.assertIsNone(activate.pyramid_id)

        with self.assertRaises(ValueError):
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.REVISE,
                members=(member,),
            )

        revise = m.FunctionalPyramidCandidateSelector(
            action=m.FunctionalPyramidAction.REVISE,
            members=(member,),
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            expected_version=m.FunctionalPyramidVersion(2),
        )
        self.assertEqual(revise.expected_version.value, 2)

    def test_status_keeps_participation_and_health_distinct(self):
        self.assertEqual(
            m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.UNCONFIGURED
            ).health,
            None,
        )
        with self.assertRaises(ValueError):
            m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.UNCONFIGURED,
                health=m.FunctionalPyramidHealth.VALID,
            )

        active = m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.ACTIVE,
            health=m.FunctionalPyramidHealth.VALID,
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member_view(),),
        )
        self.assertEqual(active.findings, ())

        finding = m.FunctionalPyramidFinding(
            reason=m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            repository_id="repo-a",
            detail="member cannot be read",
            recovery="restore repository availability",
        )
        with self.assertRaises(ValueError):
            m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.ACTIVE,
                health=m.FunctionalPyramidHealth.DEGRADED,
                pyramid_id=m.FunctionalPyramidId("fp-1"),
                version=m.FunctionalPyramidVersion(1),
                members=(_member_view(),),
            )
        degraded = m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.ACTIVE,
            health=m.FunctionalPyramidHealth.DEGRADED,
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member_view(),),
            findings=(finding,),
        )
        self.assertEqual(degraded.findings, (finding,))

    def test_declaration_wire_decode_is_strict(self):
        rule = m.FunctionalRuleDeclaration(
            rule_id="R1",
            layer=m.FunctionalPyramidLayer.P1,
            owner=m.FunctionalRuleOwner("repo-a", "docs/rules.md#r1"),
            governing_rule_ids=("ROOT",),
        )
        payload = m.to_canonical(rule)
        self.assertIsInstance(payload, dict)
        assert isinstance(payload, dict)

        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(
                m.FunctionalRuleDeclaration,
                {**payload, "unexpected": True},
            )

        invalid_layer = {**payload, "layer": "P9"}
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.FunctionalRuleDeclaration, invalid_layer)

    def test_route_support_uses_existing_support_union_shape(self):
        support = m.FunctionalRouteSupport(
            repository_id="repo-a",
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            route_identity=m.FunctionalRouteIdentity("route-1"),
        )
        encoded = m.to_canonical(support)
        self.assertEqual(encoded["$type"], "FunctionalRouteSupport")

    def test_receipt_action_shape_is_explicit(self):
        committed = datetime.datetime(2026, 11, 21, tzinfo=datetime.timezone.utc)
        receipt = m.RetrievedFunctionalPyramidReceipt(
            request_id=m.RequestId("fp-request-1"),
            content_digest=m.ContentDigest("digest-1"),
            committed_at=committed,
            action=m.FunctionalPyramidAction.ACTIVATE,
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member_view(),),
            participation_effects=(
                m.FunctionalPyramidParticipationEffect(
                    repository_id="repo-a",
                    state=m.FunctionalPyramidParticipationState.ACTIVE,
                ),
            ),
            dependent_effect_refs=(),
        )
        self.assertEqual(receipt.action, m.FunctionalPyramidAction.ACTIVATE)

        with self.assertRaises(ValueError):
            m.RetrievedFunctionalPyramidReceipt(
                request_id=m.RequestId("fp-request-2"),
                content_digest=m.ContentDigest("digest-2"),
                committed_at=committed,
                action=m.FunctionalPyramidAction.EXCLUDE,
                pyramid_id=m.FunctionalPyramidId("fp-1"),
                version=m.FunctionalPyramidVersion(1),
                members=(),
                participation_effects=(),
                dependent_effect_refs=(),
            )
