"""Version-3 Functional Pyramid source, membership and route-relevance rules."""

import json
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
        self.assertIn(
            "DOCUMENT_SET_INCOMPLETE",
            {item.reason.value for item in affected.unresolved},
        )
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
                self.assertIn(
                    "DOCUMENT_AMBIGUOUS",
                    {item.reason.value for item in view.unresolved},
                )

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
        self.assertIn(
            "DECLARATION_INVALID", {item.reason.value for item in view.unresolved}
        )

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


def _classification_row(
    repository_id: str,
    document_ref: str,
    layer: m.FunctionalPyramidLayer | None,
    scope: str | None,
    *governing: m.FunctionalDocumentIdentity
    | tuple[str, m.FunctionalDocumentIdentity]
    | str,
    disposition: m.FunctionalPyramidClassificationDisposition = (
        m.FunctionalPyramidClassificationDisposition.PLACE
    ),
    reason: str | None = None,
    declaring_repository_id: str | None = None,
) -> m.FunctionalPyramidClassificationRow:
    return m.FunctionalPyramidClassificationRow(
        declaring_repository_id=declaring_repository_id or repository_id,
        repository_id=repository_id,
        document_ref=document_ref,
        disposition=disposition,
        layer=layer,
        scope=scope,
        governing_documents=tuple(
            (
                (parent.repository_id, parent)
                if isinstance(parent, m.FunctionalDocumentIdentity)
                else parent
            )
            for parent in governing
        ),
        exclusion_reason=reason,
        authority_kind=(
            m.AuthorityKind.REPOSITORY_RULE
            if disposition is m.FunctionalPyramidClassificationDisposition.PLACE
            else None
        ),
        authority_status=(
            m.AuthorityStatus.ACCEPTED
            if disposition is m.FunctionalPyramidClassificationDisposition.PLACE
            else None
        ),
    )


class FunctionalPyramidClassificationDerivationTest(unittest.TestCase):
    def _rows(self) -> tuple[m.FunctionalPyramidClassificationRow, ...]:
        goals = m.FunctionalDocumentIdentity("repo-a", "docs/goals.md")
        invariants = m.FunctionalDocumentIdentity("repo-a", "docs/invariants.md")
        return (
            _classification_row(
                "repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
            ),
            _classification_row(
                "repo-a",
                "docs/invariants.md",
                m.FunctionalPyramidLayer.P1,
                ".",
                goals,
            ),
            _classification_row(
                "repo-a",
                "area-a/contract.md",
                m.FunctionalPyramidLayer.P2S,
                "area-a",
                invariants,
            ),
            _classification_row(
                "repo-a",
                "docs/legacy.md",
                None,
                None,
                disposition=m.FunctionalPyramidClassificationDisposition.EXCLUDE,
                reason="superseded",
            ),
        )

    def test_derives_sources_membership_placements_and_exclusions(self) -> None:
        derivation = fp.derive_functional_pyramid_declarations(
            m.FunctionalPyramidClassification(rows=self._rows())
        )

        self.assertEqual(
            [declaration.source_id for _, declaration in derivation.declarations],
            ["repo-a:.", "repo-a:area-a"],
        )
        root_source = derivation.declarations[0][1]
        self.assertIs(root_source.kind, m.FunctionalPyramidSourceKind.REPOSITORY)
        self.assertEqual(
            [identity.document_ref for identity in root_source.documents],
            ["docs/goals.md", "docs/invariants.md"],
        )
        goals, invariants = root_source.placements
        self.assertEqual(goals.governing_placements, ("ROOT",))
        self.assertEqual(
            [entry.placement.document.layer for entry in root_source.placements],
            [m.FunctionalPyramidLayer.P0, m.FunctionalPyramidLayer.P1],
        )
        self.assertEqual(invariants.governing_placements, (goals.placement,))

        area_source = derivation.declarations[1][1]
        self.assertIs(area_source.kind, m.FunctionalPyramidSourceKind.AREA)
        self.assertEqual(area_source.scope, "area-a")
        (contract,) = area_source.placements
        self.assertEqual(contract.governing_placements, (invariants.placement,))
        self.assertEqual(
            derivation.exclusions,
            (
                m.FunctionalPyramidClassificationExclusion(
                    "repo-a", "repo-a", "docs/legacy.md", "superseded"
                ),
            ),
        )
        self.assertEqual(
            fp.evaluate_functional_pyramid_source_structure(derivation.declarations),
            (),
        )

    def test_derivation_is_deterministic_across_row_order(self) -> None:
        self.assertEqual(
            fp.derive_functional_pyramid_declarations(
                m.FunctionalPyramidClassification(rows=self._rows())
            ),
            fp.derive_functional_pyramid_declarations(
                m.FunctionalPyramidClassification(rows=tuple(reversed(self._rows())))
            ),
        )

    def test_missing_root_is_a_structural_finding_not_a_derivation_shortcut(
        self,
    ) -> None:
        derivation = fp.derive_functional_pyramid_declarations(
            m.FunctionalPyramidClassification(
                rows=(
                    _classification_row(
                        "repo-a",
                        "area-a/contract.md",
                        m.FunctionalPyramidLayer.P0,
                        "area-a",
                        "ROOT",
                    ),
                )
            )
        )
        reasons = {
            finding.reason
            for finding in fp.evaluate_functional_pyramid_source_structure(
                derivation.declarations
            )
        }
        self.assertIn(m.FunctionalPyramidFindingReason.MISSING_ROOT_PLACEMENT, reasons)

    def test_invalid_rows_fail_at_ingress(self) -> None:
        goals = m.FunctionalDocumentIdentity("repo-a", "docs/goals.md")

        def classification(*rows, version=1):
            return m.FunctionalPyramidClassification(rows=rows, version=version)

        cases = [
            (
                "duplicate document",
                lambda: classification(
                    _classification_row(
                        "repo-a", "docs/a.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
                    ),
                    _classification_row(
                        "repo-a", "docs/a.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
                    ),
                ),
                "unique per document",
            ),
            ("empty classification", classification, "at least one row"),
            (
                "exclude without reason",
                lambda: classification(
                    _classification_row(
                        "repo-a",
                        "docs/a.md",
                        None,
                        None,
                        disposition=m.FunctionalPyramidClassificationDisposition.EXCLUDE,
                    )
                ),
                "requires an exclusion reason",
            ),
            (
                "exclude with scope",
                lambda: classification(
                    _classification_row(
                        "repo-a",
                        "docs/a.md",
                        None,
                        ".",
                        disposition=m.FunctionalPyramidClassificationDisposition.EXCLUDE,
                        reason="none",
                    )
                ),
                "carries no layer",
            ),
            (
                "place without scope",
                lambda: classification(
                    _classification_row(
                        "repo-a", "docs/a.md", m.FunctionalPyramidLayer.P0, None
                    )
                ),
                "requires layer and scope",
            ),
            (
                "place without layer",
                lambda: classification(
                    _classification_row("repo-a", "docs/a.md", None, ".")
                ),
                "requires layer and scope",
            ),
            (
                "non-P0 without parent",
                lambda: classification(
                    _classification_row(
                        "repo-a", "docs/a.md", m.FunctionalPyramidLayer.P1, "."
                    )
                ),
                "requires at least one governing document",
            ),
            (
                "non-P0 with ROOT",
                lambda: classification(
                    _classification_row(
                        "repo-a",
                        "docs/a.md",
                        m.FunctionalPyramidLayer.P1,
                        ".",
                        "ROOT",
                    )
                ),
                "ROOT governs only P0",
            ),
            (
                "P0 with document parent",
                lambda: classification(
                    _classification_row(
                        "repo-a",
                        "docs/a.md",
                        m.FunctionalPyramidLayer.P0,
                        ".",
                        goals,
                    )
                ),
                "governed by ROOT",
            ),
            (
                "self-governing",
                lambda: classification(
                    _classification_row(
                        "repo-a",
                        "docs/a.md",
                        m.FunctionalPyramidLayer.P1,
                        ".",
                        m.FunctionalDocumentIdentity("repo-a", "docs/a.md"),
                    )
                ),
                "cannot govern itself",
            ),
            (
                "non-canonical document",
                lambda: classification(
                    _classification_row(
                        "repo-a",
                        "./docs/a.md",
                        m.FunctionalPyramidLayer.P0,
                        ".",
                        "ROOT",
                    )
                ),
                "dot, or traversal",
            ),
            (
                "unsupported version",
                lambda: classification(
                    _classification_row(
                        "repo-a", "docs/a.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
                    ),
                    version=2,
                ),
                "version must be 1",
            ),
        ]
        for name, build, message in cases:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, message):
                    build()

    def test_all_excluded_member_cannot_disappear_from_derivation(self) -> None:
        rows = self._rows() + (
            _classification_row(
                "repo-b",
                "docs/legacy.md",
                None,
                None,
                disposition=m.FunctionalPyramidClassificationDisposition.EXCLUDE,
                reason="superseded",
            ),
        )
        with self.assertRaisesRegex(ValueError, "require placed documents: repo-b"):
            fp.derive_functional_pyramid_declarations(
                m.FunctionalPyramidClassification(rows=rows)
            )

    def test_cross_repository_governing_order_is_deterministic(self) -> None:
        roots = (
            _classification_row(
                "repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
            ),
            _classification_row(
                "repo-b", "docs/goals.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
            ),
        )
        parents = (
            m.FunctionalDocumentIdentity("repo-a", "docs/goals.md"),
            m.FunctionalDocumentIdentity("repo-b", "docs/goals.md"),
        )

        def derive(
            governing: tuple[m.FunctionalDocumentIdentity, ...],
        ) -> m.FunctionalPyramidDerivation:
            return fp.derive_functional_pyramid_declarations(
                m.FunctionalPyramidClassification(
                    rows=roots
                    + (
                        _classification_row(
                            "repo-a",
                            "docs/invariants.md",
                            m.FunctionalPyramidLayer.P1,
                            ".",
                            *governing,
                        ),
                    )
                )
            )

        first = derive(parents)
        self.assertEqual(first, derive(tuple(reversed(parents))))
        self.assertEqual(
            fp.evaluate_functional_pyramid_source_structure(first.declarations),
            (),
        )

    def test_shared_document_placement_preserves_declaring_identity(self) -> None:
        shared = m.FunctionalDocumentIdentity("repo-b", "docs/goals.md")
        root = _classification_row(
            "repo-b", "docs/goals.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
        )
        adopted = _classification_row(
            "repo-b",
            "docs/goals.md",
            m.FunctionalPyramidLayer.P0,
            ".",
            "ROOT",
            declaring_repository_id="repo-a",
        )
        child = _classification_row(
            "repo-b",
            "docs/invariants.md",
            m.FunctionalPyramidLayer.P1,
            ".",
            ("repo-a", shared),
            declaring_repository_id="repo-a",
        )
        classification = m.FunctionalPyramidClassification(rows=(root, adopted, child))
        result = fp.derive_functional_pyramid_declarations(classification)
        first = result.declarations[0][1]
        self.assertEqual(
            first.placements[0].placement.declaring_repository_id, "repo-a"
        )
        self.assertEqual(first.placements[0].placement.document.identity, shared)
        self.assertEqual(
            first.placements[1].governing_placements, (first.placements[0].placement,)
        )
        self.assertEqual(
            fp.evaluate_functional_pyramid_source_structure(result.declarations), ()
        )
        bindings, owned = fp.reconcile_functional_pyramid_bindings(
            classification,
            fingerprints={
                shared: "live",
                m.FunctionalDocumentIdentity("repo-b", "docs/invariants.md"): "live",
            },
            registered=(),
            previously_owned=(),
        )
        self.assertEqual(len(bindings), 2)
        self.assertEqual(bindings, owned)

    def test_derived_source_bytes_round_trip_and_are_content_addressed(self) -> None:
        derivation = fp.derive_functional_pyramid_declarations(
            m.FunctionalPyramidClassification(rows=self._rows())
        )
        members = fp.derive_functional_pyramid_member_intents(derivation)
        self.assertEqual(len(members), 1)
        member = members[0]
        self.assertEqual(len(member.declaration_sources), 2)
        for (repository, declaration), request in zip(
            derivation.declarations, member.declaration_sources, strict=True
        ):
            payload = fp.encode_functional_pyramid_declaration(repository, declaration)
            decoded, findings = fp.decode_functional_pyramid_declaration(
                payload.decode("utf-8"),
                repository_id=repository,
                declaration_locator=request.locator,
            )
            self.assertEqual(decoded, declaration)
            self.assertEqual(findings, ())
            self.assertEqual(
                request, fp.functional_pyramid_declaration_request(repository, decoded)
            )
        bootstrap = m.FunctionalPyramidBootstrap(
            version=2, declaration_sources=member.declaration_sources
        )
        self.assertEqual(
            fp.decode_functional_pyramid_bootstrap(
                fp.encode_functional_pyramid_bootstrap(bootstrap).decode("utf-8")
            ),
            bootstrap,
        )

    def test_classification_reconciles_authority_without_claiming_ordinary_ownership(
        self,
    ) -> None:
        classification = m.FunctionalPyramidClassification(rows=self._rows())
        fingerprints = {
            m.FunctionalDocumentIdentity(row.repository_id, row.document_ref): "live"
            for row in classification.rows
        }
        independent = _authority("repo-a", "docs/goals.md")
        legacy = _authority("repo-a", "docs/legacy.md")
        ordinary = (independent, legacy)
        bindings, owned = fp.reconcile_functional_pyramid_bindings(
            classification,
            fingerprints=fingerprints,
            registered=ordinary,
            previously_owned=(),
        )
        self.assertIn(independent, bindings)
        self.assertIn(legacy, bindings)
        self.assertNotIn(independent, owned)
        self.assertNotIn(legacy, owned)
        self.assertEqual(len(owned), 2)
        self.assertEqual(
            fp.reconcile_functional_pyramid_bindings(
                classification,
                fingerprints=fingerprints,
                registered=bindings,
                previously_owned=owned,
            ),
            (bindings, owned),
        )
        revised = m.FunctionalPyramidClassification(rows=self._rows()[:1])
        remaining, owned_after = fp.reconcile_functional_pyramid_bindings(
            revised,
            fingerprints=fingerprints,
            registered=bindings,
            previously_owned=owned,
        )
        self.assertEqual(set(remaining), set(ordinary))
        self.assertEqual(owned_after, ())

    def test_classification_rejects_competing_authority(self) -> None:
        classification = m.FunctionalPyramidClassification(rows=self._rows())
        fingerprints = {
            m.FunctionalDocumentIdentity(row.repository_id, row.document_ref): "live"
            for row in classification.rows
        }
        independent = m.AuthorityBinding(
            evidence_ref=_evidence("repo-a", "docs/goals.md"),
            authority_kind=m.AuthorityKind.TERMINOLOGY,
            status=m.AuthorityStatus.ACCEPTED,
        )
        with self.assertRaisesRegex(
            ValueError, "independent authority binding conflict"
        ):
            fp.reconcile_functional_pyramid_bindings(
                classification,
                fingerprints=fingerprints,
                registered=(independent,),
                previously_owned=(),
            )

    def test_strict_classification_document(self) -> None:
        root: dict[str, object] = {
            "declaring_repository_id": "repo-a",
            "repository_id": "repo-a",
            "document_ref": "docs/goals.md",
            "disposition": "place",
            "layer": "P0",
            "scope": ".",
            "governing_documents": ["ROOT"],
            "authority_kind": "DECISION_RECORD",
            "authority_status": "DRAFT",
        }
        exclusion: dict[str, object] = {
            "declaring_repository_id": "repo-a",
            "repository_id": "repo-a",
            "document_ref": "docs/legacy.md",
            "disposition": "exclude",
            "exclusion_reason": "superseded",
        }

        def decode(
            rows: list[dict[str, object]], version: object = 1
        ) -> m.FunctionalPyramidClassification:
            return fp.decode_functional_pyramid_classification(
                json.dumps({"version": version, "rows": rows}),
                repository_id="repo-a",
            )

        result = decode([root, exclusion])
        self.assertIs(result.rows[0].authority_kind, m.AuthorityKind.DECISION_RECORD)
        self.assertIs(result.rows[0].authority_status, m.AuthorityStatus.DRAFT)
        self.assertIsNone(result.rows[1].authority_kind)
        invalid: list[tuple[list[dict[str, object]], object]] = [
            ([root], True),
            ([root], 1.0),
            ([root, root], 1),
            ([{**root, "governing_documents": []}], 1),
            ([{**root, "declaring_repository_id": "repo-b"}], 1),
            ([{**root, "authority_kind": "unknown"}], 1),
            ([{**root, "authority_status": None}], 1),
            ([{**root, "extra": True}], 1),
            ([{**root, "document_ref": "../goals.md"}], 1),
            ([{**exclusion, "authority_kind": "DECISION_RECORD"}], 1),
            ([{**exclusion, "exclusion_reason": " "}], 1),
            ([{k: v for k, v in root.items() if k != "authority_kind"}], 1),
            ([{k: v for k, v in root.items() if k != "authority_status"}], 1),
        ]
        for rows, version in invalid:
            with self.subTest(rows=rows, version=version):
                with self.assertRaises(ValueError):
                    decode(rows, version)
        with self.assertRaisesRegex(ValueError, "duplicate classification JSON field"):
            fp.decode_functional_pyramid_classification(
                '{"version":1,"version":1,"rows":[]}', repository_id="repo-a"
            )

    def test_missing_governing_document_fails_derivation(self) -> None:
        classification = m.FunctionalPyramidClassification(
            rows=(
                _classification_row(
                    "repo-a", "docs/goals.md", m.FunctionalPyramidLayer.P0, ".", "ROOT"
                ),
                _classification_row(
                    "repo-a",
                    "docs/invariants.md",
                    m.FunctionalPyramidLayer.P1,
                    ".",
                    m.FunctionalDocumentIdentity("repo-a", "docs/missing.md"),
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "not a placed document"):
            fp.derive_functional_pyramid_declarations(classification)


if __name__ == "__main__":
    unittest.main()
