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


def _declaration_sources(
    repository_id: str,
    entries: tuple[m.FunctionalDocumentDeclaration, ...],
) -> tuple[tuple[str, m.FunctionalPyramidDeclaration], ...]:
    """Group test placements into one Version-3 source per declared scope."""
    grouped: dict[str, list[m.FunctionalDocumentDeclaration]] = {}
    for entry in entries:
        grouped.setdefault(entry.placement.scope, []).append(entry)
    grouped.setdefault(".", [])
    sources: list[tuple[str, m.FunctionalPyramidDeclaration]] = []
    for scope in sorted(grouped):
        scope_entries = tuple(grouped[scope])
        sources.append(
            (
                repository_id,
                m.FunctionalPyramidDeclaration(
                    version=3,
                    source_id=f"{repository_id}:{scope}",
                    kind=(
                        m.FunctionalPyramidSourceKind.REPOSITORY
                        if scope == "."
                        else m.FunctionalPyramidSourceKind.AREA
                    ),
                    scope=scope,
                    documents=tuple(
                        dict.fromkeys(
                            entry.placement.document.identity for entry in scope_entries
                        )
                    ),
                    placements=scope_entries,
                ),
            )
        )
    return tuple(sources)


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
        self.declaration_entries = (
            _declaration(self.p0, "ROOT"),
            _declaration(self.p1, self.p0),
            _declaration(self.p3, self.p1),
            _declaration(self.sibling, self.p0),
        )
        self.declarations = _declaration_sources("repo-a", self.declaration_entries)
        self.authorities = {
            ("repo-a", "docs/foundation.md"): _authority(
                "repo-a", "docs/foundation.md", "a0"
            ),
            ("repo-a", "docs/product.md"): _authority(
                "repo-a", "docs/product.md", "a1"
            ),
            ("repo-a", "docs/design.md"): _authority("repo-a", "docs/design.md", "a3"),
            ("repo-a", "docs/ui.md"): _authority("repo-a", "docs/ui.md", "aui"),
        }

    def _directory(self, directory: str) -> m.FunctionalPyramidResolution:
        return fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory=directory,
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        )

    @staticmethod
    def _public(
        placement: m.FunctionalDocumentPlacement,
    ) -> m.FunctionalPyramidPlacementView:
        return m.FunctionalPyramidPlacementView(
            declaring_repository_id=placement.declaring_repository_id,
            document_repository_id=placement.document.repository_id,
            layer=placement.document.layer,
            document=m.FunctionalPyramidPath(
                placement.document.repository_id, placement.document.document_ref
            ),
            scope=m.FunctionalPyramidPath(
                placement.declaring_repository_id, placement.scope
            ),
        )

    def test_root_totality_and_additive_ancestor_composition(self) -> None:
        root = self._directory(".").view
        self.assertEqual(root.placements, (self._public(self.p0),))
        nested = self._directory("src/service").view
        self.assertEqual(
            nested.placements,
            (self._public(self.p0), self._public(self.p1), self._public(self.p3)),
        )
        self.assertNotIn(self._public(self.sibling), nested.placements)
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
        src = self._directory("src").view
        self.assertEqual(src.placements, (self._public(self.p0), self._public(self.p1)))
        self.assertNotIn(self._public(self.p3), src.placements)

    def test_directory_without_own_placement_inherits_all_ancestors(self) -> None:
        leaf = self._directory("src/service/leaf").view
        self.assertEqual(
            leaf.placements,
            (self._public(self.p0), self._public(self.p1), self._public(self.p3)),
        )
        self.assertEqual(leaf.status, m.FunctionalPyramidRouteStatus.RESOLVED)

    def test_disconnected_placements_apply_only_at_their_declared_scopes(self) -> None:
        service = self._directory("src/service").view
        ui = self._directory("ui").view
        self.assertNotIn(self._public(self.sibling), service.placements)
        self.assertEqual(ui.placements, (self._public(self.p0), self._public(self.sibling)))

    def test_document_locator_never_infers_applicability(self) -> None:
        deceptive = _placement(
            "repo-a",
            "repo-a",
            "src/service/looks-governing.md",
            m.FunctionalPyramidLayer.P3,
            "ui",
        )
        declarations = _declaration_sources(
            "repo-a",
            (
                _declaration(self.p0, "ROOT"),
                _declaration(deceptive, self.p0),
            ),
        )
        authorities = {
            ("repo-a", "docs/foundation.md"): self.authorities[
                ("repo-a", "docs/foundation.md")
            ],
            ("repo-a", "src/service/looks-governing.md"): _authority(
                "repo-a",
                "src/service/looks-governing.md",
                "deceptive",
            ),
        }
        view = fp.resolve_functional_pyramid_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            surface=m.SurfaceKey(
                repository_id="repo-a",
                kind=m.SurfaceKind.FILE,
                locator="src/service/app.py",
            ),
            semantic_scope=m.EvidenceScope(paths=("src/service/app.py",)),
            declarations=declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=authorities,
        ).view
        self.assertEqual(view.placements, (self._public(self.p0),))
        self.assertNotIn(self._public(deceptive), view.placements)

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
        declarations = _declaration_sources(
            "repo-a",
            (
                _declaration(self.p0, "ROOT"),
                _declaration(narrow_parent, self.p0),
                _declaration(broad, narrow_parent),
            ),
        )
        health, findings = fp.evaluate_functional_pyramid_health(
            (_member("repo-a"),),
            declarations,
            frozenset({"repo-a"}),
        )
        self.assertEqual(health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertIn(
            m.FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
            {finding.reason for finding in findings},
        )

    def test_missing_root_is_structural_health_finding(self) -> None:
        declarations = _declaration_sources("repo-a", (_declaration(self.p3, self.p1),))
        health, findings = fp.evaluate_functional_pyramid_health(
            (_member("repo-a"),),
            declarations,
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
        view = fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
            declaration_findings=(finding,),
        ).view
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)

    def test_multi_path_summary_is_union_not_intersection_or_last_path(self) -> None:
        resolution = fp.resolve_functional_pyramid_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            surface=m.SurfaceKey(
                repository_id="repo-a",
                kind=m.SurfaceKind.DOMAIN,
                locator="domain",
            ),
            semantic_scope=m.EvidenceScope(paths=("src/service", "ui")),
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        )
        view = resolution.view
        self.assertEqual(
            view.placements,
            tuple(
                self._public(item) for item in (self.p0, self.p1, self.p3, self.sibling)
            ),
        )
        self.assertEqual(
            view.declared_layers,
            (
                m.FunctionalPyramidLayer.P0,
                m.FunctionalPyramidLayer.P1,
                m.FunctionalPyramidLayer.P3,
            ),
        )
        self.assertEqual(len(resolution.provenance), 2)
        self.assertEqual(
            tuple(item.directory for item in resolution.provenance),
            ("src/service", "ui"),
        )

    def test_repository_wide_semantic_scope_selects_all_placements(self) -> None:
        view = fp.resolve_functional_pyramid_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            surface=m.SurfaceKey(
                repository_id="repo-a",
                kind=m.SurfaceKind.DOMAIN,
                locator="domain",
            ),
            semantic_scope=m.EvidenceScope(),
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        ).view
        self.assertEqual(
            set(view.placements),
            {self._public(item) for item in (self.p0, self.p1, self.p3, self.sibling)},
        )

    def test_unrelated_member_does_not_change_route_identity(self) -> None:
        first = fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        ).identity
        repo_b_root = _placement(
            "repo-b",
            "repo-b",
            "docs/foundation.md",
            m.FunctionalPyramidLayer.P0,
            ".",
        )
        repo_b_declarations = _declaration_sources(
            "repo-b", (_declaration(repo_b_root, "ROOT"),)
        )
        second = fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(2),
            members=(_member("repo-a"), _member("repo-b")),
            repository_id="repo-a",
            directory="src/service",
            declarations=(*self.declarations, *repo_b_declarations),
            available_repositories=frozenset({"repo-a", "repo-b"}),
            authority_bindings={
                **self.authorities,
                ("repo-b", "docs/foundation.md"): _authority(
                    "repo-b", "docs/foundation.md", "b0"
                ),
            },
        ).identity
        self.assertEqual(first, second)

    def test_material_applicability_change_changes_route_identity(self) -> None:
        first = self._directory("src/service").identity
        changed = _placement(
            "repo-a",
            "repo-a",
            "docs/extra.md",
            m.FunctionalPyramidLayer.P4,
            "src/service",
        )
        declarations = _declaration_sources(
            "repo-a",
            (*self.declaration_entries, _declaration(changed, self.p3)),
        )
        second = fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={
                **self.authorities,
                ("repo-a", "docs/extra.md"): _authority(
                    "repo-a", "docs/extra.md", "a4"
                ),
            },
        ).identity
        self.assertNotEqual(first, second)

    def test_authority_currency_does_not_change_route_identity_or_health(self) -> None:
        first_resolution = self._directory("src/service")
        draft = dict(self.authorities)
        draft[("repo-a", "docs/design.md")] = m.AuthorityBinding(
            evidence_ref=_evidence("repo-a", "docs/design.md", "a3-draft"),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.DRAFT,
        )
        second_resolution = fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=draft,
        )
        self.assertEqual(first_resolution.identity, second_resolution.identity)
        self.assertEqual(
            first_resolution.view.status, m.FunctionalPyramidRouteStatus.RESOLVED
        )
        self.assertEqual(
            second_resolution.view.status, m.FunctionalPyramidRouteStatus.RESOLVED
        )
        health, findings = fp.evaluate_functional_pyramid_health(
            (_member("repo-a"),), self.declarations, frozenset({"repo-a"})
        )
        self.assertEqual(health, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(findings, ())

    def test_explicit_p2w_to_p2s_governing_edge_is_valid(self) -> None:
        p2s = _placement(
            "repo-a",
            "repo-a",
            "docs/shared-contract.md",
            m.FunctionalPyramidLayer.P2S,
            "src",
        )
        p2w = _placement(
            "repo-a",
            "repo-a",
            "docs/workflow-contract.md",
            m.FunctionalPyramidLayer.P2W,
            "src/service",
        )
        declarations = _declaration_sources(
            "repo-a",
            (
                _declaration(self.p0, "ROOT"),
                _declaration(p2s, self.p0),
                _declaration(p2w, p2s),
            ),
        )
        health, findings = fp.evaluate_functional_pyramid_health(
            (_member("repo-a"),),
            declarations,
            frozenset({"repo-a"}),
        )
        self.assertEqual(health, m.FunctionalPyramidHealth.VALID)
        self.assertEqual(findings, ())

    def test_reverse_p2s_to_p2w_governing_edge_is_invalid(self) -> None:
        p2s = _placement(
            "repo-a",
            "repo-a",
            "docs/shared-contract.md",
            m.FunctionalPyramidLayer.P2S,
            "src/service",
        )
        p2w = _placement(
            "repo-a",
            "repo-a",
            "docs/workflow-contract.md",
            m.FunctionalPyramidLayer.P2W,
            "src",
        )
        declarations = _declaration_sources(
            "repo-a",
            (
                _declaration(self.p0, "ROOT"),
                _declaration(p2w, self.p0),
                _declaration(p2s, p2w),
            ),
        )
        _, findings = fp.evaluate_functional_pyramid_health(
            (_member("repo-a"),),
            declarations,
            frozenset({"repo-a"}),
        )
        self.assertIn(
            m.FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
            {finding.reason for finding in findings},
        )

    def test_same_contract_sublayer_governing_edges_are_invalid(self) -> None:
        for layer in (m.FunctionalPyramidLayer.P2S, m.FunctionalPyramidLayer.P2W):
            with self.subTest(layer=layer):
                parent = _placement(
                    "repo-a",
                    "repo-a",
                    "docs/parent-contract.md",
                    layer,
                    "src",
                )
                child = _placement(
                    "repo-a",
                    "repo-a",
                    "docs/child-contract.md",
                    layer,
                    "src/service",
                )
                declarations = _declaration_sources(
                    "repo-a",
                    (
                        _declaration(self.p0, "ROOT"),
                        _declaration(parent, self.p0),
                        _declaration(child, parent),
                    ),
                )
                _, findings = fp.evaluate_functional_pyramid_health(
                    (_member("repo-a"),),
                    declarations,
                    frozenset({"repo-a"}),
                )
                self.assertIn(
                    m.FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                    {finding.reason for finding in findings},
                )

    def test_route_identity_tracks_applicability_not_pyramid_version(self) -> None:
        first = fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        ).identity
        second = fp.resolve_functional_pyramid_directory_route(
            roots={"repo-a": "/repos/repo-a", "repo-b": "/repos/repo-b"},
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(2),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="src/service",
            declarations=self.declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings=self.authorities,
        ).identity
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
