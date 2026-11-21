"""Functional Pyramid declaration/resolution tests (T02)."""

import json
import unittest

from span.core import functional_pyramid as fp
from span.core import model as m


def _selector(
    kind: m.FunctionalScopeSelectorKind,
    path: str | None = None,
    locator: str | None = None,
) -> m.FunctionalScopeSelector:
    return m.FunctionalScopeSelector(kind=kind, path=path, locator=locator)


def _scope(*selectors: m.FunctionalScopeSelector) -> m.FunctionalScope:
    return m.FunctionalScope(selectors=selectors)


def _graph_ref(repository_id: str, identity: str) -> m.FunctionalGraphRef:
    return m.FunctionalGraphRef(repository_id=repository_id, identity=identity)


def _evidence_ref(
    repository_id: str, locator: str = "docs/functional-pyramid.json"
) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{repository_id}-{locator}"),
        repository_id=repository_id,
        source_kind=m.EvidenceSourceKind.CONFIGURATION,
        locator=locator,
        revision_or_fingerprint=f"digest-{repository_id}-{locator}",
    )


def _member(
    repository_id: str,
    *,
    coverage: m.FunctionalPyramidCoverage = m.FunctionalPyramidCoverage.PARTIAL,
    scope: m.FunctionalScope | None = None,
) -> m.FunctionalPyramidMemberView:
    return m.FunctionalPyramidMemberView(
        repository_id=repository_id,
        declaration_refs=(_evidence_ref(repository_id),),
        functional_scope=scope
        or _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src")),
        coverage=coverage,
    )


def _authority(repository_id: str, locator: str) -> m.AuthorityBinding:
    return m.AuthorityBinding(
        evidence_ref=m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{repository_id}-{locator}"),
            repository_id=repository_id,
            source_kind=m.EvidenceSourceKind.DOCUMENTATION,
            locator=locator,
            revision_or_fingerprint=f"digest-{locator}",
        ),
        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _rule(
    repository_id: str,
    rule_id: str,
    layer: m.FunctionalPyramidLayer,
    parents: tuple[m.FunctionalGraphRef | str, ...],
) -> m.FunctionalRuleDeclaration:
    return m.FunctionalRuleDeclaration(
        rule_id=rule_id,
        layer=layer,
        owner=m.FunctionalRuleOwner(
            repository_id=repository_id,
            authority_ref=f"rules/{rule_id}.md",
        ),
        governing_rule_ids=parents,
    )


def _base_graph() -> tuple[
    tuple[m.FunctionalPyramidMemberView, ...],
    tuple[tuple[str, m.FunctionalPyramidDeclaration], ...],
    dict[tuple[str, str], m.AuthorityBinding],
]:
    members = (_member("repo-a"), _member("repo-b"))
    repo_a = m.FunctionalPyramidDeclaration(
        version=1,
        contexts=(
            m.FunctionalContextDeclaration(
                context_id="ctx-platform",
                coverage=_scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src")),
                rules=(_graph_ref("repo-a", "rule-p3"),),
            ),
            m.FunctionalContextDeclaration(
                context_id="ctx-workflow",
                coverage=_scope(
                    _selector(m.FunctionalScopeSelectorKind.PATH, "src/a.py")
                ),
                inherits=(_graph_ref("repo-b", "ctx-shared"),),
                rules=(_graph_ref("repo-a", "rule-p4"),),
            ),
        ),
        rules=(
            _rule(
                "repo-a",
                "rule-p3",
                m.FunctionalPyramidLayer.P3,
                (_graph_ref("repo-b", "rule-p1"),),
            ),
            _rule(
                "repo-a",
                "rule-p4",
                m.FunctionalPyramidLayer.P4,
                (_graph_ref("repo-a", "rule-p3"),),
            ),
        ),
    )
    repo_b = m.FunctionalPyramidDeclaration(
        version=1,
        contexts=(
            m.FunctionalContextDeclaration(
                context_id="ctx-shared",
                coverage=_scope(
                    _selector(m.FunctionalScopeSelectorKind.PREFIX, "shared")
                ),
                rules=(_graph_ref("repo-b", "rule-p1"),),
            ),
        ),
        rules=(
            _rule("repo-b", "rule-p0", m.FunctionalPyramidLayer.P0, ("ROOT",)),
            _rule(
                "repo-b",
                "rule-p1",
                m.FunctionalPyramidLayer.P1,
                (_graph_ref("repo-b", "rule-p0"),),
            ),
        ),
    )
    authorities = {
        ("repo-a", "rules/rule-p3.md"): _authority("repo-a", "rules/rule-p3.md"),
        ("repo-a", "rules/rule-p4.md"): _authority("repo-a", "rules/rule-p4.md"),
        ("repo-b", "rules/rule-p0.md"): _authority("repo-b", "rules/rule-p0.md"),
        ("repo-b", "rules/rule-p1.md"): _authority("repo-b", "rules/rule-p1.md"),
    }
    return members, (("repo-a", repo_a), ("repo-b", repo_b)), authorities


class FunctionalPyramidDeclarationDecodeTest(unittest.TestCase):
    def test_strict_declaration_requires_qualified_graph_refs(self):
        payload = {
            "version": 1,
            "contexts": [
                {
                    "context_id": "ctx",
                    "coverage": [{"kind": "PREFIX", "path": "src"}],
                    "inherits": [{"repository_id": "repo-b", "identity": "shared"}],
                    "rules": [{"repository_id": "repo-a", "identity": "rule-p3"}],
                }
            ],
            "rules": [
                {
                    "rule_id": "rule-p3",
                    "layer": "P3",
                    "owner": {
                        "repository_id": "repo-a",
                        "authority_ref": "rules/p3.md",
                    },
                    "governing_rule_ids": [
                        {"repository_id": "repo-b", "identity": "rule-p1"}
                    ],
                }
            ],
        }
        declaration = fp.decode_functional_pyramid_declaration(json.dumps(payload))
        self.assertEqual(
            declaration.contexts[0].inherits,
            (_graph_ref("repo-b", "shared"),),
        )

        payload["contexts"][0]["inherits"] = ["shared"]
        with self.assertRaises(ValueError):
            fp.decode_functional_pyramid_declaration(json.dumps(payload))

    def test_decoder_rejects_unknown_fields_and_normalizes_scope(self):
        payload = {
            "version": 1,
            "contexts": [
                {
                    "context_id": "ctx",
                    "coverage": [
                        {"kind": "PATH", "path": "src/a.py"},
                        {"kind": "PREFIX", "path": "src"},
                    ],
                    "inherits": [],
                    "rules": [],
                    "extra": True,
                }
            ],
            "rules": [],
        }
        with self.assertRaises(ValueError):
            fp.decode_functional_pyramid_declaration(json.dumps(payload))

        del payload["contexts"][0]["extra"]
        declaration = fp.decode_functional_pyramid_declaration(json.dumps(payload))
        self.assertEqual(
            declaration.contexts[0].coverage,
            _scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src")),
        )

    def test_bootstrap_is_optional_navigation_shape_not_authority(self):
        payload = {
            "version": 1,
            "functional_scope": [{"kind": "PREFIX", "path": "src"}],
            "coverage": "PARTIAL",
            "declaration_sources": [
                {"locator": "docs/functional-pyramid.json", "ranges": []}
            ],
        }
        bootstrap = fp.decode_functional_pyramid_bootstrap(json.dumps(payload))
        self.assertEqual(bootstrap.version, 1)
        self.assertEqual(
            bootstrap.declaration_sources,
            (m.EvidenceRequest("docs/functional-pyramid.json"),),
        )


class FunctionalPyramidResolverTest(unittest.TestCase):
    def test_service_scope_preserves_canonical_symbol_member(self) -> None:
        member = _member(
            "repo-a",
            scope=_scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src")),
        )
        declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-symbol",
                    coverage=_scope(
                        _selector(
                            m.FunctionalScopeSelectorKind.SYMBOL,
                            "src/a.py",
                            "src/a.py::A",
                        )
                    ),
                ),
            ),
        )

        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=(member,),
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.SERVICE, "svc"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py::A",)),
            declarations=(("repo-a", declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={},
        )

        self.assertEqual(view.scope_relation, m.FunctionalScopeRelation.COVERED)
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)
        self.assertEqual(
            tuple(context.context_id for context in view.contexts),
            ("ctx-symbol",),
        )

    def test_overlapping_direct_contexts_precede_inherited_contexts(self):
        members, declarations, authorities = _base_graph()
        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=declarations,
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings=authorities,
        )

        self.assertEqual(view.health, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(view.scope_relation, m.FunctionalScopeRelation.COVERED)
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)
        self.assertEqual(
            [(item.context_id, item.direct) for item in view.contexts],
            [
                ("ctx-platform", True),
                ("ctx-workflow", True),
                ("ctx-shared", False),
            ],
        )
        self.assertEqual(
            [item.rule_id for item in view.rules],
            ["rule-p0", "rule-p1", "rule-p3", "rule-p4"],
        )

    def test_degraded_health_recovers_without_participation_change(self):
        members, declarations, _ = _base_graph()

        degraded, degraded_findings = fp.evaluate_functional_pyramid_health(
            members,
            declarations,
            frozenset({"repo-a"}),
        )
        recovered, recovered_findings = fp.evaluate_functional_pyramid_health(
            members,
            declarations,
            frozenset({"repo-a", "repo-b"}),
        )

        self.assertEqual(degraded, m.FunctionalPyramidHealth.DEGRADED)
        self.assertIn(
            m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            {item.reason for item in degraded_findings},
        )
        self.assertEqual(recovered, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(recovered_findings, ())
        self.assertEqual(tuple(member.repository_id for member in members), ("repo-a", "repo-b"))

    def test_one_context_can_cover_disconnected_paths(self):
        member = _member(
            "repo-a",
            scope=_scope(_selector(m.FunctionalScopeSelectorKind.REPOSITORY)),
        )
        declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-disconnected",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "src/a.py"),
                        _selector(m.FunctionalScopeSelectorKind.PATH, "docs/b.md"),
                    ),
                ),
            ),
        )

        for path in ("src/a.py", "docs/b.md"):
            with self.subTest(path=path):
                view, _ = fp.resolve_functional_pyramid_route(
                    pyramid_id=m.FunctionalPyramidId("fp-disconnected"),
                    version=m.FunctionalPyramidVersion(1),
                    members=(member,),
                    surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, path),
                    semantic_scope=m.EvidenceScope(paths=(path,)),
                    declarations=(("repo-a", declaration),),
                    available_repositories=frozenset({"repo-a"}),
                    authority_bindings={},
                )
                self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)
                self.assertEqual(
                    tuple(context.context_id for context in view.contexts),
                    ("ctx-disconnected",),
                )

    def test_authority_graph_defects_are_explicit(self):
        members = (
            _member(
                "repo-a",
                scope=_scope(_selector(m.FunctionalScopeSelectorKind.REPOSITORY)),
            ),
            _member(
                "repo-b",
                scope=_scope(_selector(m.FunctionalScopeSelectorKind.REPOSITORY)),
            ),
        )
        repo_a = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-duplicate",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "src/a.py")
                    ),
                ),
                m.FunctionalContextDeclaration(
                    context_id="ctx-cycle-a",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "src/b.py")
                    ),
                    inherits=(_graph_ref("repo-a", "ctx-cycle-b"),),
                ),
                m.FunctionalContextDeclaration(
                    context_id="ctx-cycle-b",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "src/c.py")
                    ),
                    inherits=(_graph_ref("repo-a", "ctx-cycle-a"),),
                ),
                m.FunctionalContextDeclaration(
                    context_id="ctx-unknown-rule",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "src/d.py")
                    ),
                    rules=(_graph_ref("repo-a", "missing-rule"),),
                ),
            ),
            rules=(
                _rule(
                    "repo-a",
                    "rule-duplicate",
                    m.FunctionalPyramidLayer.P0,
                    ("ROOT",),
                ),
                _rule(
                    "repo-a",
                    "rule-no-parent",
                    m.FunctionalPyramidLayer.P1,
                    (),
                ),
                _rule(
                    "repo-a",
                    "rule-invalid-root",
                    m.FunctionalPyramidLayer.P1,
                    ("ROOT",),
                ),
                _rule(
                    "repo-a",
                    "rule-cycle-a",
                    m.FunctionalPyramidLayer.P2S,
                    (_graph_ref("repo-a", "rule-cycle-b"),),
                ),
                _rule(
                    "repo-a",
                    "rule-cycle-b",
                    m.FunctionalPyramidLayer.P2S,
                    (_graph_ref("repo-a", "rule-cycle-a"),),
                ),
            ),
        )
        repo_b = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-duplicate",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "other/a.py")
                    ),
                ),
            ),
            rules=(
                _rule(
                    "repo-b",
                    "rule-duplicate",
                    m.FunctionalPyramidLayer.P0,
                    ("ROOT",),
                ),
            ),
        )

        health, findings = fp.evaluate_functional_pyramid_health(
            members,
            (("repo-a", repo_a), ("repo-b", repo_b)),
            frozenset({"repo-a", "repo-b"}),
        )
        reasons = {item.reason for item in findings}

        self.assertEqual(health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertTrue(
            {
                m.FunctionalPyramidFindingReason.UNKNOWN_RULE,
                m.FunctionalPyramidFindingReason.DUPLICATE_RULE_OWNER,
                m.FunctionalPyramidFindingReason.CONTEXT_CYCLE,
                m.FunctionalPyramidFindingReason.RULE_CYCLE,
                m.FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                m.FunctionalPyramidFindingReason.UNRESOLVED_RULE_PARENT,
            }
            <= reasons
        )

    def test_route_identity_ignores_instance_version_and_unrelated_member(self):
        members, declarations, authorities = _base_graph()
        kwargs = dict(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=declarations,
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings=authorities,
        )
        _, first = fp.resolve_functional_pyramid_route(
            version=m.FunctionalPyramidVersion(1), **kwargs
        )
        _, second = fp.resolve_functional_pyramid_route(
            version=m.FunctionalPyramidVersion(2), **kwargs
        )
        self.assertEqual(first, second)

        extra_member = _member(
            "repo-c",
            scope=_scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "other")),
        )
        extra_declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-unrelated",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PREFIX, "other")
                    ),
                ),
            ),
        )
        _, third = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(3),
            members=members + (extra_member,),
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=declarations + (("repo-c", extra_declaration),),
            available_repositories=frozenset({"repo-a", "repo-b", "repo-c"}),
            authority_bindings=authorities,
        )
        self.assertEqual(first, third)

        _, service_a = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(3),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.SERVICE, "service-a"),
            semantic_scope=m.EvidenceScope(paths=("src",)),
            declarations=declarations,
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings=authorities,
        )
        _, service_b = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(3),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.SERVICE, "service-b"),
            semantic_scope=m.EvidenceScope(paths=("src",)),
            declarations=declarations,
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings=authorities,
        )
        self.assertEqual(service_a, service_b)

        missing_authority = dict(authorities)
        del missing_authority[("repo-b", "rules/rule-p1.md")]
        unresolved_view, fourth = fp.resolve_functional_pyramid_route(
            version=m.FunctionalPyramidVersion(4),
            authority_bindings=missing_authority,
            **{
                key: value
                for key, value in kwargs.items()
                if key != "authority_bindings"
            },
        )
        self.assertEqual(first, fourth)
        self.assertIn(
            m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
            {item.reason for item in unresolved_view.unresolved},
        )

    def test_wholly_outside_scope_is_resolved_empty_governance(self):
        members, declarations, authorities = _base_graph()
        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "README.md"),
            semantic_scope=m.EvidenceScope(paths=("README.md",)),
            declarations=declarations,
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings=authorities,
        )
        self.assertEqual(
            view.scope_relation,
            m.FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE,
        )
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)
        self.assertEqual(view.contexts, ())
        self.assertEqual(view.rules, ())
        self.assertEqual(view.unresolved, ())

    def test_broad_scope_crossing_boundary_is_mixed_and_resolved_when_covered(self):
        members, declarations, authorities = _base_graph()
        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.SERVICE, "service-a"),
            semantic_scope=m.EvidenceScope(paths=("src", "docs")),
            declarations=declarations,
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings=authorities,
        )
        self.assertEqual(view.scope_relation, m.FunctionalScopeRelation.MIXED)
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)
        self.assertEqual(
            {item.relation for item in view.provenance},
            {
                m.FunctionalScopeRelation.COVERED,
                m.FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE,
            },
        )

    def test_partial_uncovered_path_is_route_unresolved_but_health_valid(self):
        members = (_member("repo-a"),)
        declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-other",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PREFIX, "other")
                    ),
                ),
            ),
        )
        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=(("repo-a", declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={},
        )
        self.assertEqual(view.health, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(view.scope_relation, m.FunctionalScopeRelation.UNCOVERED)
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.UNRESOLVED)
        self.assertEqual(
            {item.reason for item in view.unresolved},
            {m.FunctionalPyramidFindingReason.UNCOVERED_PATH},
        )

    def test_complete_uncovered_scope_degrades_health(self):
        member = _member(
            "repo-a",
            coverage=m.FunctionalPyramidCoverage.COMPLETE,
            scope=_scope(_selector(m.FunctionalScopeSelectorKind.PREFIX, "src")),
        )
        declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-child",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PREFIX, "src/a")
                    ),
                ),
            ),
        )
        health, findings = fp.evaluate_functional_pyramid_health(
            (member,),
            (("repo-a", declaration),),
            frozenset({"repo-a"}),
        )
        self.assertEqual(health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertIn(
            m.FunctionalPyramidFindingReason.UNCOVERED_PATH,
            {item.reason for item in findings},
        )

    def test_unavailable_member_is_distinct_from_unknown_context(self):
        members, declarations, authorities = _base_graph()
        unavailable_view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=(declarations[0],),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=authorities,
        )
        self.assertIn(
            m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            {item.reason for item in unavailable_view.unresolved},
        )
        self.assertNotIn(
            m.FunctionalPyramidFindingReason.UNKNOWN_CONTEXT,
            {item.reason for item in unavailable_view.unresolved},
        )

        missing_b_context = m.FunctionalPyramidDeclaration(
            version=1,
            rules=declarations[1][1].rules,
        )
        unknown_view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=(declarations[0], ("repo-b", missing_b_context)),
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings=authorities,
        )
        self.assertIn(
            m.FunctionalPyramidFindingReason.UNKNOWN_CONTEXT,
            {item.reason for item in unknown_view.unresolved},
        )
        self.assertNotIn(
            m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            {item.reason for item in unknown_view.unresolved},
        )

    def test_reverse_context_dependents_include_inheritance_closure(self):
        member = _member("repo-a")
        declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-base",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "src/a.py")
                    ),
                    rules=(_graph_ref("repo-a", "rule-p0"),),
                ),
                m.FunctionalContextDeclaration(
                    context_id="ctx-dependent",
                    coverage=_scope(
                        _selector(m.FunctionalScopeSelectorKind.PATH, "src/b.py")
                    ),
                    inherits=(_graph_ref("repo-a", "ctx-base"),),
                ),
            ),
            rules=(
                _rule(
                    "repo-a",
                    "rule-p0",
                    m.FunctionalPyramidLayer.P0,
                    ("ROOT",),
                ),
            ),
        )
        authority = _authority("repo-a", "rules/rule-p0.md")
        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=(member,),
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=(("repo-a", declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={
                ("repo-a", "rules/rule-p0.md"): authority,
            },
        )

        rule = next(item for item in view.rules if item.rule_id == "rule-p0")
        self.assertEqual(
            rule.downstream_context_ids,
            ("ctx-base", "ctx-dependent"),
        )

    def test_surface_kind_prevents_filename_heuristic_scope_inference(self):
        members = (
            _member(
                "repo-a",
                scope=_scope(
                    _selector(m.FunctionalScopeSelectorKind.PREFIX, "src/a.py")
                ),
            ),
        )
        declaration = m.FunctionalPyramidDeclaration(
            version=1,
            contexts=(
                m.FunctionalContextDeclaration(
                    context_id="ctx-child",
                    coverage=_scope(
                        _selector(
                            m.FunctionalScopeSelectorKind.PREFIX,
                            "src/a.py/child",
                        )
                    ),
                ),
            ),
        )
        # FILE is exact even though the locator string can syntactically be a prefix.
        file_view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.FILE, "src/a.py"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=(("repo-a", declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={},
        )
        self.assertEqual(file_view.scope_relation, m.FunctionalScopeRelation.UNCOVERED)

        # SERVICE uses the same path string as a broad boundary.
        broad_view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            version=m.FunctionalPyramidVersion(1),
            members=members,
            surface=m.SurfaceKey("repo-a", m.SurfaceKind.SERVICE, "svc"),
            semantic_scope=m.EvidenceScope(paths=("src/a.py",)),
            declarations=(("repo-a", declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={},
        )
        self.assertEqual(broad_view.scope_relation, m.FunctionalScopeRelation.COVERED)
        self.assertIn("ctx-child", {item.context_id for item in broad_view.contexts})
