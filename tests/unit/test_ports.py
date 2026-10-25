"""Port contract tests (plan Phase 1.2).

Ports are typed interfaces only: these tests pin the exact §5 method
sets, the §5.2 direction vocabulary, and the §5.1 bounds policy and
ingress rules. No provider behavior is tested here.
"""

import dataclasses
import typing
import unittest

from span.core import model as m
from span.ports import (
    EvidenceSource,
    InterpretationUnavailable,
    PendingInterpretation,
    SemanticStore,
    StructuralDirection,
    StructuralSource,
)
from span import service as svc


def _bounds(**overrides):
    base = dict(
        max_results=50,
        max_depth=2,
        max_subjects=8,
        max_evidence_units=24,
        max_evidence_bytes=96_000,
        max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


class DirectionVocabularyTest(unittest.TestCase):
    def test_members(self):
        self.assertEqual(
            {e.value for e in StructuralDirection},
            {"UPSTREAM", "DOWNSTREAM", "BOTH"},
        )


class PortShapeTest(unittest.TestCase):
    def _assert_methods(self, protocol, expected):
        for name in expected:
            member = getattr(protocol, name, None)
            self.assertTrue(callable(member), f"{protocol.__name__}.{name}")
        actual = {name for name in dir(protocol) if not name.startswith("_")}
        self.assertEqual(actual, set(expected), protocol.__name__)

    def test_structural_source_methods(self):
        self._assert_methods(
            StructuralSource,
            {
                "repository_state",
                "resolve_subject",
                "locations",
                "edges",
                "reach",
                "search_symbols",
                "file_outline",
                "verify_files",
                "describe_current",
                "ensure_current",
            },
        )

    def test_evidence_source_methods(self):
        self._assert_methods(
            EvidenceSource,
            {
                "inventory_evidence",
                "list_inventory_entries",
                "select_evidence",
                "read_evidence",
            },
        )

    def test_interpretation_exchange_contract(self):
        pending = PendingInterpretation(
            continuation="cont-1",
            request=m.SemanticInterpretationRequest(
                repository_id="repo-1",
                subjects=(),
                evidence_units=(),
                structural_observations=(),
                allowed_claim_kinds=(),
                allowed_relationship_kinds=(),
                identity_bindings=(),
                brief=m.TaskBrief(),
                bounds=self._bounds(),
            ),
        )
        self.assertEqual(pending.continuation, "cont-1")
        with self.assertRaises(ValueError):
            PendingInterpretation(continuation="", request=pending.request)
        self.assertTrue(issubclass(InterpretationUnavailable, Exception))
        self.assertFalse(hasattr(svc, "reissue_interpretation"))

    def _bounds(self):
        return m.QueryBounds(
            max_results=50,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=24,
            max_evidence_bytes=96_000,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )

    def test_store_methods(self):
        self._assert_methods(
            SemanticStore,
            {
                "load_subjects",
                "load_by_refs",
                "load_claims",
                "load_subjects_by_locator",
                "load_repository_subjects",
                "repository_root",
                "record_repository_root",
                "load_subjects_in_scope",
                "count_subjects_in_scope",
                "count_repository_subjects",
                "count_question_dispositions",
                "count_target_associations",
                "count_target_inventory_outcomes",
                "load_active_target_associations",
                "load_relationships",
                "load_evidence_dependencies",
                "load_evidence_records",
                "load_coverage_dependencies",
                "load_question_coverages",
                "load_all_question_coverages",
                "count_question_coverages",
                "load_premise_dependents",
                "load_conflicts",
                "write_index_batch",
                "mark_freshness",
                "schema_version",
                "record_repository_initialization",
                "load_repository_authority_seeds",
                "load_repository_state",
                "load_target_association",
                "load_verification_record",
            },
        )

    def test_key_signatures(self):
        hints = typing.get_type_hints(StructuralSource.edges)
        self.assertIs(hints["direction"], StructuralDirection)
        hints = typing.get_type_hints(SemanticStore.load_relationships)
        self.assertIs(hints["direction"], StructuralDirection)

    def test_change_kind_single_home(self):
        from span import service as ops

        self.assertIs(ops.ChangeKind, m.ChangeKind)
        self.assertIs(ops.ProposedChange, m.ProposedChange)

    def test_store_batch_signature(self):
        hints = typing.get_type_hints(SemanticStore.write_index_batch)
        self.assertIs(hints["batch"], m.CanonicalIndexBatch)


class StructuralResultEnvelopeTest(unittest.TestCase):
    """Step 10: page operations cannot return items without coverage.

    One envelope serves every paginated port read, so coverage is a
    property of the return type rather than a per-provider convention.
    """

    _PAGES = {
        "locations": "StructuralLocation",
        "edges": "StructuralEdge",
        "reach": "StructuralReachNode",
        "search_symbols": "StructuralSearchHit",
        "file_outline": "StructuralOutlineEntry",
    }

    def test_every_page_operation_returns_the_envelope(self):
        for name, item in self._PAGES.items():
            with self.subTest(operation=name):
                hint = typing.get_type_hints(getattr(StructuralSource, name))["return"]
                self.assertIs(typing.get_origin(hint), m.StructuralResult)
                self.assertEqual(typing.get_args(hint), (getattr(m, item),))

    def test_envelope_declares_typed_coverage(self):
        hints = typing.get_type_hints(m.StructuralResult)
        self.assertIs(hints["coverage"], m.ScopeCoverage)
        self.assertEqual(hints["coverage_detail"], str | None)


class StructuralPageCoverageTest(unittest.TestCase):
    """Wire claim in ``docs/mcp.md``: structural pages carry coverage.

    Derived from the tool output map, so a structural result added later
    is enrolled without editing this test, and one that drops a coverage
    field fails here rather than in review.
    """

    def _structural_results(self):
        from span.shell import mcp as shell_mcp

        return {
            tool: result
            for tool, result in shell_mcp.TOOL_OUTPUT_TYPES.items()
            if getattr(result, "__name__", "").startswith("Structural")
        }

    def test_every_structural_result_declares_coverage(self):
        results = self._structural_results()
        self.assertTrue(results, "no structural result was found to check")
        for tool, result in results.items():
            fields = {field.name for field in dataclasses.fields(result)}
            self.assertIn("coverage", fields, tool)
            self.assertIn("coverage_detail", fields, tool)
            hints = typing.get_type_hints(result)
            self.assertIs(hints["coverage"], m.ScopeCoverage, tool)
            self.assertEqual(hints["coverage_detail"], str | None, tool)


class BoundsPolicyTest(unittest.TestCase):
    def test_initial_policy_values(self):
        policy = svc.DEFAULT_SERVICE_BOUNDS_POLICY
        self.assertEqual(
            policy.default_query_bounds,
            _bounds(),
        )
        self.assertEqual(
            policy.maximum_query_bounds,
            _bounds(
                max_results=250,
                max_depth=6,
                max_subjects=32,
                max_evidence_units=96,
                max_evidence_bytes=384_000,
                max_candidate_claims=256,
                max_candidate_relationships=256,
            ),
        )
        self.assertEqual(
            policy.hook_fast_bounds,
            _bounds(
                max_results=25,
                max_depth=0,
                max_subjects=8,
                max_evidence_units=16,
                max_evidence_bytes=64_000,
                max_candidate_claims=1,
                max_candidate_relationships=1,
            ),
        )

    def test_omitted_bounds_use_default(self):
        policy = svc.DEFAULT_SERVICE_BOUNDS_POLICY
        self.assertEqual(
            svc.resolve_bounds(None, hook=False), policy.default_query_bounds
        )

    def test_hooks_always_use_hook_fast(self):
        policy = svc.DEFAULT_SERVICE_BOUNDS_POLICY
        self.assertEqual(svc.resolve_bounds(None, hook=True), policy.hook_fast_bounds)
        # Even an explicitly supplied (valid) request is hook-fast.
        self.assertEqual(
            svc.resolve_bounds(_bounds(), hook=True), policy.hook_fast_bounds
        )

    def test_within_maximum_accepted(self):
        self.assertEqual(svc.resolve_bounds(_bounds(), hook=False), _bounds())
        self.assertEqual(
            svc.resolve_bounds(_bounds(max_results=250), hook=False),
            _bounds(max_results=250),
        )

    def test_above_maximum_rejected_never_clamped(self):
        with self.assertRaises(svc.BoundsRejectedError):
            svc.resolve_bounds(_bounds(max_results=251), hook=False)
        with self.assertRaises(svc.BoundsRejectedError):
            svc.resolve_bounds(_bounds(max_depth=7), hook=False)
        with self.assertRaises(svc.BoundsRejectedError):
            svc.resolve_bounds(_bounds(max_candidate_relationships=257), hook=False)


if __name__ == "__main__":
    unittest.main()
