"""Version-3 Functional Pyramid source, membership and route-relevance rules."""

import unittest

from span.core import functional_pyramid as fp
from span.core import model as m


def _evidence(repository_id: str, locator: str) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{repository_id}-{locator}"),
        repository_id=repository_id,
        source_kind=m.EvidenceSourceKind.DOCUMENTATION,
        locator=locator,
        revision_or_fingerprint="rev",
    )


def _authority(repository_id: str, locator: str) -> m.AuthorityBinding:
    return m.AuthorityBinding(
        evidence_ref=_evidence(repository_id, locator),
        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _member(repository_id: str) -> m.FunctionalPyramidMemberView:
    return m.FunctionalPyramidMemberView(
        repository_id=repository_id,
        declaration_refs=(_evidence(repository_id, ".span/decl.json"),),
    )


def _placement(
    repository_id: str,
    document_ref: str,
    layer: m.FunctionalPyramidLayer,
    scope: str,
    *,
    document_repository_id: str | None = None,
) -> m.FunctionalDocumentPlacement:
    return m.FunctionalDocumentPlacement(
        declaring_repository_id=repository_id,
        document=m.FunctionalDocumentRef(
            repository_id=document_repository_id or repository_id,
            document_ref=document_ref,
            layer=layer,
        ),
        scope=scope,
    )


def _entry(
    placement: m.FunctionalDocumentPlacement,
    *parents: m.FunctionalDocumentPlacement | str,
) -> m.FunctionalDocumentDeclaration:
    return m.FunctionalDocumentDeclaration(
        placement=placement,
        governing_placements=tuple(parents),
    )


def _source(
    repository_id: str,
    scope: str,
    kind: m.FunctionalPyramidSourceKind,
    documents: tuple[m.FunctionalDocumentIdentity, ...],
    entries: tuple[m.FunctionalDocumentDeclaration, ...],
    *,
    source_id: str | None = None,
) -> tuple[str, m.FunctionalPyramidDeclaration]:
    return (
        repository_id,
        m.FunctionalPyramidDeclaration(
            version=3,
            source_id=source_id or f"{repository_id}:{scope}",
            kind=kind,
            scope=scope,
            documents=documents,
            placements=entries,
        ),
    )


def _identity(repository_id: str, document_ref: str) -> m.FunctionalDocumentIdentity:
    return m.FunctionalDocumentIdentity(repository_id, document_ref)


def _reasons(findings: tuple[m.FunctionalPyramidFinding, ...]) -> set[str]:
    return {finding.reason.value for finding in findings}


def _root_placement(repository_id: str = "repo-a") -> m.FunctionalDocumentPlacement:
    return _placement(repository_id, "docs/goals.md", m.FunctionalPyramidLayer.P0, ".")


def _root_source(
    repository_id: str = "repo-a",
) -> tuple[str, m.FunctionalPyramidDeclaration]:
    placement = _root_placement(repository_id)
    return _source(
        repository_id,
        ".",
        m.FunctionalPyramidSourceKind.REPOSITORY,
        (placement.document.identity,),
        (_entry(placement, "ROOT"),),
    )


class FunctionalPyramidSourceSetTest(unittest.TestCase):
    def test_repository_kind_source_is_mandatory_at_root(self) -> None:
        area = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/a.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/a.md", m.FunctionalPyramidLayer.P3, "src"
                    ),
                    "ROOT",
                ),
            ),
        )
        findings = fp.evaluate_functional_pyramid_source_structure((area,))
        self.assertIn("INVALID_DECLARATION", _reasons(findings))

    def test_multiple_repository_kind_sources_are_invalid(self) -> None:
        root = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (_identity("repo-a", "docs/goals.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, "."
                    ),
                    "ROOT",
                ),
            ),
        )
        second = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (),
            (),
            source_id="repo-a:second",
        )
        findings = fp.evaluate_functional_pyramid_source_structure((root, second))
        self.assertIn("INVALID_DECLARATION", _reasons(findings))

    def test_repository_kind_source_must_be_root_and_area_must_not(self) -> None:
        repository_at_area = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (),
            (),
        )
        area_at_root = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.AREA,
            (),
            (),
            source_id="repo-a:area",
        )
        findings = fp.evaluate_functional_pyramid_source_structure(
            (repository_at_area, area_at_root)
        )
        self.assertIn("INVALID_DECLARATION", _reasons(findings))

    def test_duplicate_source_identity_and_scope_are_invalid(self) -> None:
        first = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (),
            (),
            source_id="repo-a:same",
        )
        second = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (),
            (),
            source_id="repo-a:same",
        )
        third = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (),
            (),
            source_id="repo-a:other",
        )
        findings = fp.evaluate_functional_pyramid_source_structure(
            (first, second, third)
        )
        self.assertIn("INVALID_DECLARATION", _reasons(findings))


class FunctionalPyramidMembershipTest(unittest.TestCase):
    def test_mismatch_missing_and_unlisted_coexist(self) -> None:
        source = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (
                _identity("repo-a", "docs/a.md"),
                _identity("repo-a", "docs/b.md"),
            ),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/a.md", m.FunctionalPyramidLayer.P3, "src"
                    ),
                    "ROOT",
                ),
                _entry(
                    _placement("repo-a", "docs/c.md", m.FunctionalPyramidLayer.P3, "."),
                    "ROOT",
                ),
            ),
        )
        findings = fp.evaluate_functional_pyramid_source_structure((source,))
        reasons = _reasons(findings)
        self.assertIn("DOCUMENT_SCOPE_MISMATCH", reasons)
        self.assertIn("MISSING_AREA_DOCUMENT", reasons)
        self.assertIn("UNLISTED_AREA_DOCUMENT", reasons)

    def test_duplicate_membership_within_one_source(self) -> None:
        source = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (
                _identity("repo-a", "docs/a.md"),
                _identity("repo-a", "docs/a.md"),
            ),
            (
                _entry(
                    _placement("repo-a", "docs/a.md", m.FunctionalPyramidLayer.P0, "."),
                    "ROOT",
                ),
            ),
        )
        findings = fp.evaluate_functional_pyramid_source_structure((source,))
        self.assertIn("DUPLICATE_DOCUMENT_SOURCE", _reasons(findings))

    def test_duplicate_membership_across_sources(self) -> None:
        root = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (
                _identity("repo-a", "docs/goals.md"),
                _identity("repo-a", "docs/shared.md"),
            ),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, "."
                    ),
                    "ROOT",
                ),
                _entry(
                    _placement(
                        "repo-a", "docs/shared.md", m.FunctionalPyramidLayer.P0, "."
                    ),
                    "ROOT",
                ),
            ),
        )
        area = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/shared.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/shared.md", m.FunctionalPyramidLayer.P3, "src"
                    ),
                    _root_placement(),
                ),
            ),
        )
        findings = fp.evaluate_functional_pyramid_source_structure((root, area))
        self.assertIn("DUPLICATE_DOCUMENT_SOURCE", _reasons(findings))

    def test_duplicate_layer_and_scope(self) -> None:
        root = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (_identity("repo-a", "docs/goals.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, "."
                    ),
                    "ROOT",
                ),
            ),
        )
        layer_source = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/shared.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/shared.md", m.FunctionalPyramidLayer.P3, "src"
                    ),
                    _root_placement(),
                ),
            ),
        )
        scope_source = _source(
            "repo-a",
            "src/service",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/shared.md"),),
            (
                _entry(
                    _placement(
                        "repo-a",
                        "docs/shared.md",
                        m.FunctionalPyramidLayer.P4,
                        "src/service",
                    ),
                    "ROOT",
                ),
            ),
        )
        findings = fp.evaluate_functional_pyramid_source_structure(
            (root, layer_source, scope_source)
        )
        reasons = _reasons(findings)
        self.assertIn("DUPLICATE_DOCUMENT_LAYER", reasons)
        self.assertIn("DUPLICATE_DOCUMENT_SCOPE", reasons)

    def test_repeated_placement_identity_is_duplicate_whether_identical(self) -> None:
        placement = _placement(
            "repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, "."
        )
        source = (
            "repo-a",
            m.FunctionalPyramidDeclaration(
                version=3,
                source_id="repo-a:repository",
                kind=m.FunctionalPyramidSourceKind.REPOSITORY,
                scope=".",
                documents=(placement.document.identity,),
                placements=(
                    _entry(placement, "ROOT"),
                    _entry(placement, "ROOT"),
                ),
            ),
        )
        findings = fp.evaluate_functional_pyramid_source_structure((source,))
        self.assertIn("DUPLICATE_DOCUMENT_PLACEMENT", _reasons(findings))

    def test_missing_root_placement(self) -> None:
        source = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (_identity("repo-a", "docs/design.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/design.md", m.FunctionalPyramidLayer.P3, "."
                    ),
                    "ROOT",
                ),
            ),
        )
        findings = fp.evaluate_functional_pyramid_source_structure((source,))
        self.assertIn("MISSING_ROOT_PLACEMENT", _reasons(findings))


class FunctionalPyramidRouteRelevanceTest(unittest.TestCase):
    def _root(
        self, repository_id: str = "repo-a"
    ) -> tuple[str, m.FunctionalPyramidDeclaration]:
        return _root_source(repository_id)

    def _resolve(
        self,
        declarations: tuple[tuple[str, m.FunctionalPyramidDeclaration], ...],
        directory: str,
        *,
        repository_id: str = "repo-a",
        members: tuple[m.FunctionalPyramidMemberView, ...] | None = None,
    ) -> m.FunctionalPyramidView:
        view = fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("pyramid"),
            version=m.FunctionalPyramidVersion(1),
            members=members or (_member(repository_id),),
            repository_id=repository_id,
            directory=directory,
            declarations=declarations,
            available_repositories=frozenset(
                member.repository_id
                for member in (members or (_member(repository_id),))
            ),
            authority_bindings={
                (repository_id, "docs/goals.md"): _authority(
                    repository_id, "docs/goals.md"
                ),
                (repository_id, "docs/src.md"): _authority(
                    repository_id, "docs/src.md"
                ),
                (repository_id, "docs/ui.md"): _authority(repository_id, "docs/ui.md"),
                (repository_id, "docs/shared.md"): _authority(
                    repository_id, "docs/shared.md"
                ),
            },
        ).view
        return view

    def test_placement_less_finding_affects_its_area_only(self) -> None:
        missing = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/src.md"),),
            (),
        )
        ui = _source(
            "repo-a",
            "ui",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/ui.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/ui.md", m.FunctionalPyramidLayer.P3, "ui"
                    ),
                    _root_placement(),
                ),
            ),
        )
        declarations = (self._root(), missing, ui)
        affected = self._resolve(declarations, "src")
        unrelated = self._resolve(declarations, "ui")
        self.assertEqual(affected.status, m.FunctionalPyramidRouteStatus.UNRESOLVED)
        self.assertIn("MISSING_AREA_DOCUMENT", _reasons(affected.unresolved))
        self.assertEqual(unrelated.status, m.FunctionalPyramidRouteStatus.RESOLVED)

    def test_cross_source_duplicate_reaches_every_affected_route(self) -> None:
        src = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/shared.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/shared.md", m.FunctionalPyramidLayer.P3, "src"
                    ),
                    _root_placement(),
                ),
            ),
        )
        ui = _source(
            "repo-a",
            "ui",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/shared.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/shared.md", m.FunctionalPyramidLayer.P3, "ui"
                    ),
                    _root_placement(),
                ),
            ),
        )
        declarations = (self._root(), src, ui)
        for directory in ("src", "ui"):
            with self.subTest(directory=directory):
                view = self._resolve(declarations, directory)
                self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.UNRESOLVED)
                self.assertIn("DUPLICATE_DOCUMENT_SOURCE", _reasons(view.unresolved))

    def test_mismatched_placement_is_reported_at_its_actual_scope(self) -> None:
        misplaced = _source(
            "repo-a",
            "ui",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/shared.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/shared.md", m.FunctionalPyramidLayer.P3, "src"
                    ),
                    _root_placement(),
                ),
            ),
        )
        view = self._resolve((self._root(), misplaced), "src")
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.UNRESOLVED)
        self.assertIn("DOCUMENT_SCOPE_MISMATCH", _reasons(view.unresolved))

    def test_unrelated_member_defect_does_not_unresolve_a_route(self) -> None:
        valid_area = _source(
            "repo-a",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-a", "docs/src.md"),),
            (
                _entry(
                    _placement(
                        "repo-a", "docs/src.md", m.FunctionalPyramidLayer.P3, "src"
                    ),
                    _root_placement(),
                ),
            ),
        )
        other_missing = _source(
            "repo-b",
            "src",
            m.FunctionalPyramidSourceKind.AREA,
            (_identity("repo-b", "docs/other.md"),),
            (),
        )
        declarations = (self._root(), valid_area, other_missing)
        view = self._resolve(
            declarations,
            "src",
            members=(_member("repo-a"), _member("repo-b")),
        )
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)


class FunctionalPyramidWorkedExampleTest(unittest.TestCase):
    def test_neutral_example_is_structurally_valid_and_resolves(self) -> None:
        goals = _placement("repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, ".")
        invariants = _placement(
            "repo-a", "docs/invariants.md", m.FunctionalPyramidLayer.P1, "."
        )
        contract = _placement(
            "repo-a", "area-a/contract.md", m.FunctionalPyramidLayer.P2S, "area-a"
        )
        shared = _placement(
            "repo-a", "areas/shared.md", m.FunctionalPyramidLayer.P2S, "areas"
        )
        repository = _source(
            "repo-a",
            ".",
            m.FunctionalPyramidSourceKind.REPOSITORY,
            (goals.document.identity, invariants.document.identity),
            (_entry(goals, "ROOT"), _entry(invariants, goals)),
        )
        area = _source(
            "repo-a",
            "area-a",
            m.FunctionalPyramidSourceKind.AREA,
            (contract.document.identity,),
            (_entry(contract, invariants),),
        )
        shared_source = _source(
            "repo-a",
            "areas",
            m.FunctionalPyramidSourceKind.AREA,
            (shared.document.identity,),
            (_entry(shared, invariants),),
        )
        declarations = (repository, area, shared_source)
        self.assertEqual(
            fp.evaluate_functional_pyramid_source_structure(declarations), ()
        )

        view = fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("example"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="area-a/nested",
            declarations=declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={
                ("repo-a", "docs/goals.md"): _authority("repo-a", "docs/goals.md"),
                ("repo-a", "docs/invariants.md"): _authority(
                    "repo-a", "docs/invariants.md"
                ),
                ("repo-a", "area-a/contract.md"): _authority(
                    "repo-a", "area-a/contract.md"
                ),
            },
        ).view
        self.assertEqual(view.status, m.FunctionalPyramidRouteStatus.RESOLVED)
        self.assertIn(contract, view.placements)
        self.assertIn(goals, view.placements)
        self.assertIn(m.FunctionalPyramidLayer.P2W, view.absent_layers)

        shared_view = fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("example"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="areas/one/nested",
            declarations=declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={
                ("repo-a", "docs/goals.md"): _authority("repo-a", "docs/goals.md"),
                ("repo-a", "docs/invariants.md"): _authority(
                    "repo-a", "docs/invariants.md"
                ),
                ("repo-a", "areas/shared.md"): _authority("repo-a", "areas/shared.md"),
            },
        ).view
        self.assertEqual(shared_view.status, m.FunctionalPyramidRouteStatus.RESOLVED)
        self.assertIn(shared, shared_view.placements)
        self.assertIn(goals, shared_view.placements)

        narrowless = fp.resolve_functional_pyramid_directory_route(
            pyramid_id=m.FunctionalPyramidId("example"),
            version=m.FunctionalPyramidVersion(1),
            members=(_member("repo-a"),),
            repository_id="repo-a",
            directory="unmapped/deep",
            declarations=declarations,
            available_repositories=frozenset({"repo-a"}),
            authority_bindings={
                ("repo-a", "docs/goals.md"): _authority("repo-a", "docs/goals.md"),
                ("repo-a", "docs/invariants.md"): _authority(
                    "repo-a", "docs/invariants.md"
                ),
            },
        ).view
        self.assertEqual(narrowless.status, m.FunctionalPyramidRouteStatus.RESOLVED)
        self.assertEqual(narrowless.placements, (goals, invariants))


if __name__ == "__main__":
    unittest.main()
