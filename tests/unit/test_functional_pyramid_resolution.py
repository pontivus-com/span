import unittest

from span.core import functional_pyramid as fp
from span.core import model as m


def _evidence(repository_id: str, locator: str, identity: str) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(identity),
        repository_id=repository_id,
        source_kind=m.EvidenceSourceKind.DOCUMENTATION,
        locator=locator,
        revision_or_fingerprint="rev",
    )


def _authority(repository_id: str, locator: str, identity: str) -> m.AuthorityBinding:
    return m.AuthorityBinding(
        evidence_ref=_evidence(repository_id, locator, identity),
        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _placement(
    declaring_repository_id: str,
    document_repository_id: str,
    locator: str,
    layer: m.FunctionalPyramidLayer,
    scope: str,
) -> m.FunctionalDocumentPlacement:
    return m.FunctionalDocumentPlacement(
        declaring_repository_id=declaring_repository_id,
        document=m.FunctionalDocumentRef(
            repository_id=document_repository_id,
            document_ref=locator,
            layer=layer,
        ),
        scope=scope,
    )


def _declaration(
    placement: m.FunctionalDocumentPlacement,
    *parents: m.FunctionalDocumentPlacement | str,
) -> m.FunctionalDocumentDeclaration:
    return m.FunctionalDocumentDeclaration(
        placement=placement,
        governing_placements=tuple(parents),
    )


def _member(repository_id: str) -> m.FunctionalPyramidMemberView:
    return m.FunctionalPyramidMemberView(
        repository_id=repository_id,
        declaration_refs=(
            _evidence(repository_id, ".span/pyramid.json", f"decl-{repository_id}"),
        ),
    )


class FunctionalPyramidResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.p0 = _placement(
            "repo-a",
            "repo-a",
            "docs/foundation.md",
            m.FunctionalPyramidLayer.P0,
            ".",
        )
        self.p1 = _placement(
            "repo-a",
            "repo-a",
            "docs/product.md",
            m.FunctionalPyramidLayer.P1,
            "src",
        )
        self.p3 = _placement(
            "repo-a",
            "repo-a",
            "docs/design.md",
            m.FunctionalPyramidLayer.P3,
            "src/service",
        )
        self.sibling = _placement(
            "repo-a",
            "repo-a",
            "docs/ui.md",
            m.FunctionalPyramidLayer.P3,
            "ui",
        )
        self.declaration = m.FunctionalPyramidDeclaration(
            version=2,
            placements=(
                _declaration(self.p0, "ROOT"),
                _declaration(self.p1, self.p0),
                _declaration(self.p3, self.p1),
                _declaration(self.sibling, self.p0),
            ),
        )
        self.authorities = {
            ("repo-a", "docs/foundation.md"): _authority(
                "repo-a", "docs/foundation.md", "a0"
            ),
            ("repo-a", "docs/product.md"): _authority(
                "repo-a", "docs/product.md", "a1"
            ),
            ("repo-a", "docs/design.md"): _authority(
                "repo-a", "docs/design.md", "a3"
            ),
            ("repo-a", "docs/ui.md"): _authority("repo-a", "docs/ui.md", "aui"),
        }

    def _directory(self, directory: str) -> tuple[m.FunctionalPyramidView, m.FunctionalRouteIdentity]:
        return fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory=directory,
            declarations=(("repo-a", self.declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        )

    def test_root_totality_and_additive_ancestor_composition(self) -> None:
        root, _ = self._directory(".")
        self.assertEqual(root.placements, (self.p0,))
        nested, _ = self._directory("src/service")
        self.assertEqual(nested.placements, (self.p0, self.p1, self.p3))
        self.assertNotIn(self.sibling, nested.placements)
        self.assertEqual(
            nested.declared_layers,
            (
                m.FunctionalPyramidLayer.P0,
                m.FunctionalPyramidLayer.P1,
                m.FunctionalPyramidLayer.P3,
            ),
        )
        self.assertEqual(
            nested.absent_layers,
            (
                m.FunctionalPyramidLayer.P2S,
                m.FunctionalPyramidLayer.P2W,
                m.FunctionalPyramidLayer.P4,
            ),
        )
        self.assertEqual(nested.status, m.FunctionalPyramidRouteStatus.RESOLVED)

    def test_descendant_placement_does_not_apply_to_ancestor(self) -> None:
        src, _ = self._directory("src")
        self.assertEqual(src.placements, (self.p0, self.p1))
        self.assertNotIn(self.p3, src.placements)

    def test_narrower_governing_scope_is_invalid(self) -> None:
        broad = _placement(
            "repo-a",
            "repo-a",
            "docs/broad.md",
            m.FunctionalPyramidLayer.P3,
            "src",
        )
        narrow_parent = _placement(
            "repo-a",
            "repo-a",
            "docs/narrow.md",
            m.FunctionalPyramidLayer.P1,
            "src/service",
        )
        declaration = m.FunctionalPyramidDeclaration(
            version=2,
            placements=(
                _declaration(self.p0, "ROOT"),
                _declaration(narrow_parent, self.p0),
                _declaration(broad, narrow_parent),
            ),
        )
        health, findings = fp.evaluate_functional_pyramid_health(
            (_member("repo-a"),),
            (("repo-a", declaration),),
            frozenset({"repo-a"}),
        )
        self.assertEqual(health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertIn(
            m.FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
            {finding.reason for finding in findings},
        )

    def test_missing_root_is_structural_health_finding(self) -> None:
        declaration = m.FunctionalPyramidDeclaration(
            version=2,
            placements=(_declaration(self.p3, self.p1),),
        )
        health, findings = fp.evaluate_functional_pyramid_health(
            (_member("repo-a"),),
            (("repo-a", declaration),),
            frozenset({"repo-a"}),
        )
        self.assertEqual(health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertIn(
            m.FunctionalPyramidFindingReason.MISSING_ROOT_PLACEMENT,
            {finding.reason for finding in findings},
        )

    def test_unaffected_route_can_resolve_while_health_is_degraded(self) -> None:
        unrelated = _placement(
            "repo-a",
            "repo-a",
            "docs/bad.md",
            m.FunctionalPyramidLayer.P3,
            "broken",
        )
        finding = m.FunctionalPyramidFinding(
            reason=m.FunctionalPyramidFindingReason.DOCUMENT_UNAVAILABLE,
            repository_id="repo-a",
            placement=unrelated,
            detail="bad document unavailable",
            recovery="restore it",
        )
        view, _ = fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=(("repo-a", self.declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
            declaration_findings=(finding,),
        )
        self.assertEqual(view.health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)

    def test_multi_path_summary_is_union_not_intersection_or_last_path(self) -> None:
        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            surface=m.SurfaceKey(
                repository_id="repo-a",
                kind=m.SurfaceKind.DOMAIN,
                locator="domain",
            ),
            semantic_scope=m.EvidenceScope(paths=("src/service", "ui")),
            declarations=(("repo-a", self.declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        )
        self.assertEqual(
            view.placements,
            (self.p0, self.p1, self.p3, self.sibling),
        )
        self.assertEqual(
            view.declared_layers,
            (
                m.FunctionalPyramidLayer.P0,
                m.FunctionalPyramidLayer.P1,
                m.FunctionalPyramidLayer.P3,
            ),
        )
        self.assertEqual(len(view.provenance), 2)
        self.assertEqual(
            tuple(item.directory for item in view.provenance),
            ("src/service", "ui"),
        )

    def test_repository_wide_semantic_scope_selects_all_placements(self) -> None:
        view, _ = fp.resolve_functional_pyramid_route(
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            surface=m.SurfaceKey(
                repository_id="repo-a",
                kind=m.SurfaceKind.DOMAIN,
                locator="domain",
            ),
            semantic_scope=m.EvidenceScope(),
            declarations=(("repo-a", self.declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        )
        self.assertEqual(set(view.placements), {self.p0, self.p1, self.p3, self.sibling})

    def test_route_identity_tracks_applicability_not_pyramid_version(self) -> None:
        _, first = fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=(("repo-a", self.declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        )
        _, second = fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(2),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=(("repo-a", self.declaration),),
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
