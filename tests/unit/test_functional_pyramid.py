import json
import unittest

from span.core import functional_pyramid as fp
from span.core import model as m


def _doc(
    repository_id: str,
    locator: str,
    layer: m.FunctionalPyramidLayer,
) -> dict[str, object]:
    return {
        "repository_id": repository_id,
        "document_ref": locator,
        "layer": layer.value,
    }


class FunctionalDirectoryScopeTest(unittest.TestCase):
    def test_root_and_canonical_relative_scopes_are_valid(self) -> None:
        self.assertEqual(fp.normalize_directory_scope("."), ".")
        self.assertEqual(fp.normalize_directory_scope("src"), "src")
        self.assertEqual(fp.normalize_directory_scope("src/service"), "src/service")

    def test_noncanonical_scopes_are_rejected(self) -> None:
        for value in (
            "",
            "/src",
            "src/",
            "src//service",
            "./src",
            "src/./service",
            "src/../service",
            r"src\service",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fp.normalize_directory_scope(value)

    def test_containment_and_intersection_are_directionally_correct(self) -> None:
        self.assertTrue(fp.directory_scope_contains(".", "src/service"))
        self.assertTrue(fp.directory_scope_contains("src", "src/service"))
        self.assertFalse(fp.directory_scope_contains("src/service", "src"))
        self.assertTrue(fp.directory_scope_intersects("src/service", "src"))
        self.assertFalse(fp.directory_scope_intersects("src", "docs"))


class FunctionalPyramidCarrierTest(unittest.TestCase):
    def test_retired_model_is_absent_from_public_carriers(self) -> None:
        retired = {
            "FunctionalScope",
            "FunctionalScopeRelation",
            "FunctionalPyramidCoverage",
            "FunctionalRuleDeclaration",
            "FunctionalRuleRoute",
            "FunctionalContextDeclaration",
            "FunctionalContextRoute",
            "FunctionalGraphRef",
        }
        self.assertTrue(retired.isdisjoint(set(m.__all__)))

    def test_closed_finding_vocabularies_match_beta5_contract(self) -> None:
        self.assertEqual(
            {reason.value for reason in m.FunctionalPyramidFindingReason},
            {
                "INVALID_DECLARATION",
                "INVALID_PLACEMENT_SCOPE",
                "DUPLICATE_DOCUMENT_PLACEMENT",
                "DUPLICATE_DOCUMENT_SOURCE",
                "DUPLICATE_DOCUMENT_LAYER",
                "DUPLICATE_DOCUMENT_SCOPE",
                "DOCUMENT_SCOPE_MISMATCH",
                "MISSING_AREA_DOCUMENT",
                "UNLISTED_AREA_DOCUMENT",
                "INVALID_DOCUMENT_REFERENCE",
                "MISSING_DOCUMENT_AUTHORITY",
                "AMBIGUOUS_DOCUMENT_AUTHORITY",
                "NONCANONICAL_DOCUMENT_AUTHORITY",
                "DOCUMENT_UNAVAILABLE",
                "UNKNOWN_DOCUMENT",
                "DOCUMENT_CYCLE",
                "INVALID_GOVERNING_EDGE",
                "UNRESOLVED_DOCUMENT_PARENT",
                "REPOSITORY_UNAVAILABLE",
                "MISSING_ROOT_PLACEMENT",
            },
        )
        self.assertEqual(
            {reason.value for reason in m.FunctionalPyramidValidationReason},
            {
                "UNREGISTERED_MEMBER",
                "DUPLICATE_MEMBER",
                "MEMBER_ALREADY_ACTIVE",
                "UNKNOWN_PYRAMID",
                "STALE_PYRAMID_VERSION",
                "MISSING_DECLARATION_SOURCE",
                "INVALID_DECLARATION_SOURCE",
            },
        )

    def test_public_governance_findings_exclude_internal_diagnostics(self) -> None:
        from span.core.schema import schema_for_result, to_wire_root

        for reason in m.FunctionalPyramidFindingReason:
            finding = m.public_pyramid_finding(m.FunctionalPyramidFinding(
                reason=reason, detail="internal secret.json", recovery="secret.json",
                declaration_locator="secret.json",
            ))
            payload = json.dumps(to_wire_root(type(finding), m.to_canonical(finding)))
            self.assertNotIn("declaration_locator", payload)
            self.assertNotIn("secret.json", payload)
            self.assertIn(finding.reason, tuple(m.FunctionalPyramidPublicReason))
        for carrier in (m.FunctionalPyramidView, m.FunctionalPyramidStatus, m.FunctionalPyramidCandidate):
            schema = json.dumps(schema_for_result(carrier))
            self.assertNotIn("declaration_locator", schema)
            self.assertNotIn("INVALID_PLACEMENT_SCOPE", schema)
            self.assertNotIn("INVALID_DECLARATION_SOURCE", schema)

    def test_document_placement_identity_includes_scope_and_layer(self) -> None:
        ref = m.FunctionalDocumentRef(
            repository_id="repo-a",
            document_ref="docs/foundation.md",
            layer=m.FunctionalPyramidLayer.P0,
        )
        root = m.FunctionalDocumentPlacement("repo-a", ref, ".")
        local = m.FunctionalDocumentPlacement("repo-a", ref, "src")
        self.assertNotEqual(root, local)

    def test_view_requires_one_selection_and_complete_layer_partition(self) -> None:
        with self.assertRaises(ValueError):
            m.FunctionalPyramidView(
                pyramid_id=m.FunctionalPyramidId("p"),
                version=m.FunctionalPyramidVersion(1),
                status=m.FunctionalPyramidRouteStatus.RESOLVED,
                directory=".",
                semantic_scope=m.EvidenceScope(),
                placements=(),
                declared_layers=(),
                absent_layers=tuple(m.FunctionalPyramidLayer),
            )


class FunctionalPyramidVersion3DecodeTest(unittest.TestCase):
    def test_bootstrap_is_version2_only(self) -> None:
        bootstrap = fp.decode_functional_pyramid_bootstrap(
            json.dumps(
                {
                    "version": 2,
                    "declaration_sources": [{"locator": ".span/pyramid.json"}],
                }
            )
        )
        self.assertEqual(bootstrap.version, 2)
        with self.assertRaises(ValueError):
            fp.decode_functional_pyramid_bootstrap(
                json.dumps(
                    {
                        "version": 1,
                        "declaration_sources": [{"locator": ".span/pyramid.json"}],
                    }
                )
            )

    @staticmethod
    def _baseline() -> dict[str, object]:
        return {
            "version": 3,
            "source_id": "repo-a:repository",
            "kind": "repository",
            "scope": ".",
            "documents": [
                {"repository_id": "repo-a", "document_ref": "docs/foundation.md"}
            ],
            "placements": [
                {
                    "document": _doc(
                        "repo-a", "docs/foundation.md", m.FunctionalPyramidLayer.P0
                    ),
                    "scope": ".",
                    "governing_placements": ["ROOT"],
                }
            ],
        }

    def test_decode_requires_fully_qualified_governing_placement(self) -> None:
        payload = self._baseline()
        payload["placements"] = [
            *payload["placements"],  # type: ignore[misc]
            {
                "document": _doc(
                    "repo-a", "docs/design.md", m.FunctionalPyramidLayer.P3
                ),
                "scope": ".",
                "governing_placements": [
                    {
                        "document": _doc(
                            "repo-a",
                            "docs/foundation.md",
                            m.FunctionalPyramidLayer.P0,
                        ),
                        "scope": ".",
                    }
                ],
            },
        ]
        payload["documents"] = [
            *payload["documents"],  # type: ignore[misc]
            {"repository_id": "repo-a", "document_ref": "docs/design.md"},
        ]
        with self.assertRaises(ValueError):
            fp.decode_functional_pyramid_declaration(
                json.dumps(payload),
                repository_id="repo-a",
                declaration_locator=".span/pyramid.json",
            )

    def test_invalid_scope_is_graph_finding_not_source_failure(self) -> None:
        payload = self._baseline()
        payload["placements"] = [
            {
                "document": _doc(
                    "repo-a", "docs/foundation.md", m.FunctionalPyramidLayer.P0
                ),
                "scope": "../outside",
                "governing_placements": ["ROOT"],
            }
        ]
        declaration, findings = fp.decode_functional_pyramid_declaration(
            json.dumps(payload),
            repository_id="repo-a",
            declaration_locator=".span/pyramid.json",
        )
        self.assertEqual(declaration.version, 3)
        self.assertEqual(declaration.placements, ())
        self.assertEqual(
            declaration.documents,
            (m.FunctionalDocumentIdentity("repo-a", "docs/foundation.md"),),
        )
        self.assertEqual(
            tuple(finding.reason for finding in findings),
            (m.FunctionalPyramidFindingReason.INVALID_PLACEMENT_SCOPE,),
        )
        self.assertEqual(findings[0].repository_id, "repo-a")
        self.assertIsNone(findings[0].placement)

    def test_invalid_json_and_unsupported_versions_are_source_failures(self) -> None:
        payloads: list[str] = ["{"]
        for version in (1, 2):
            payload = self._baseline()
            payload["version"] = version
            payloads.append(json.dumps(payload))
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                fp.decode_functional_pyramid_declaration(
                    payload,
                    repository_id="repo-a",
                    declaration_locator=".span/pyramid.json",
                )

    def test_malformed_source_metadata_is_a_decoding_failure(self) -> None:
        mutations = (
            ("source_id", ""),
            ("kind", "unknown"),
            ("scope", "../outside"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                payload = self._baseline()
                payload[field] = value
                with self.assertRaises(ValueError):
                    fp.decode_functional_pyramid_declaration(
                        json.dumps(payload),
                        repository_id="repo-a",
                        declaration_locator=".span/pyramid.json",
                    )
        missing = self._baseline()
        del missing["documents"]
        with self.assertRaises(ValueError):
            fp.decode_functional_pyramid_declaration(
                json.dumps(missing),
                repository_id="repo-a",
                declaration_locator=".span/pyramid.json",
            )

    def test_valid_declaration_round_trips_canonical_carriers(self) -> None:
        payload = self._baseline()
        payload["placements"] = [
            {
                "document": _doc(
                    "repo-a", "docs/foundation.md", m.FunctionalPyramidLayer.P0
                ),
                "scope": ".",
                "governing_placements": ["ROOT"],
            },
            {
                "document": _doc(
                    "repo-a", "docs/design.md", m.FunctionalPyramidLayer.P3
                ),
                "scope": "src/service",
                "governing_placements": [
                    {
                        "declaring_repository_id": "repo-a",
                        "document": _doc(
                            "repo-a",
                            "docs/foundation.md",
                            m.FunctionalPyramidLayer.P0,
                        ),
                        "scope": ".",
                    }
                ],
            },
        ]
        payload["documents"] = [
            {"repository_id": "repo-a", "document_ref": "docs/foundation.md"},
            {"repository_id": "repo-a", "document_ref": "docs/design.md"},
        ]
        declaration, findings = fp.decode_functional_pyramid_declaration(
            json.dumps(payload),
            repository_id="repo-a",
            declaration_locator=".span/pyramid.json",
        )
        self.assertEqual(findings, ())
        self.assertEqual(declaration.source_id, "repo-a:repository")
        self.assertEqual(declaration.scope, ".")
        self.assertEqual(len(declaration.documents), 2)
        self.assertEqual(len(declaration.placements), 2)
        restored = m.from_canonical(
            m.FunctionalPyramidDeclaration,
            m.to_canonical(declaration),
        )
        self.assertEqual(restored, declaration)


if __name__ == "__main__":
    unittest.main()
