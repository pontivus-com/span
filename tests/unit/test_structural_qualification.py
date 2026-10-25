"""Step 11: stale structure is qualified, never presented as current.

``impact`` and ``trace`` both read structural pages that can be stale. The
policy is one rule (D6): a VERIFIED page is silent; an UNVERIFIED page adds a
resolution requirement naming the reason and the operation that restores
currency. ``neighbors`` keeps filtering stale edges and is not covered here.

The wrapper below forces coverage on a fixture source. It does not change what
the provider returns — only what the page says about its own currency — so the
operations are exercised through their real composition path.
"""

import dataclasses
import unittest

from span.core import model as m
from span.ports.structural import StructuralDirection
from span import service as ops
from span.core.answers import (
    merge_coverage_detail,
    structural_coverage_requirement,
)
from tests.support.agent_exchange import (
    REPO,
    _bounds,
    _exchange,
    _harness,
)

_QUALIFIED = "structural facts that are not current"


def _forced(page, detail):
    return dataclasses.replace(
        page,
        coverage=m.ScopeCoverage.UNVERIFIED,
        coverage_detail=detail,
    )


class _UnverifiedSource:
    """Fixture source whose page reads report an unverified verdict."""

    def __init__(self, inner, detail="touched-file-mismatch"):
        self._inner = inner
        self._detail = detail

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def locations(self, *args, **kwargs):
        return _forced(self._inner.locations(*args, **kwargs), self._detail)

    def edges(self, *args, **kwargs):
        return _forced(self._inner.edges(*args, **kwargs), self._detail)

    def reach(self, *args, **kwargs):
        return _forced(self._inner.reach(*args, **kwargs), self._detail)


def _impact(structural):
    structural_source, evidence, store, agent = _harness()
    wrapped = structural_source if structural is None else structural(structural_source)
    try:
        return _exchange(
            ops.SemanticImpactRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, "src/flow.py", (), None),
                change_kind=ops.ChangeKind.BEHAVIOR,
                change_description=None,
                bounds=_bounds(),
                affected_assertions=(),
            ),
            ops.impact,
            wrapped,
            evidence,
            store,
            agent,
        )
    finally:
        store.close()


def _trace(structural):
    structural_source, evidence, store, agent = _harness()
    wrapped = structural_source if structural is None else structural(structural_source)
    try:
        return _exchange(
            ops.SemanticTraceRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, "src/flow.py", (), None),
                direction=StructuralDirection.BOTH,
                relationship_filter=None,
                boundary_only=False,
                bounds=_bounds(),
            ),
            ops.trace,
            wrapped,
            evidence,
            store,
            agent,
        )
    finally:
        store.close()


def _qualifications(answer):
    return [
        requirement
        for requirement in answer.resolution_requirements
        if _QUALIFIED in requirement.description
    ]


class CoveragePolicyTest(unittest.TestCase):
    def test_verified_is_silent(self):
        self.assertIsNone(
            structural_coverage_requirement(
                "impact", m.ScopeCoverage.VERIFIED, "clean-verified"
            )
        )

    def test_stale_structure_names_stale_evidence(self):
        requirement = structural_coverage_requirement(
            "impact", m.ScopeCoverage.UNVERIFIED, "touched-file-mismatch"
        )
        self.assertIs(requirement.kind, m.ResolutionKind.STALE_EVIDENCE)
        self.assertIn("refresh", requirement.description)

    def test_unverifiable_structure_names_unverifiable_freshness(self):
        requirement = structural_coverage_requirement(
            "trace", m.ScopeCoverage.UNVERIFIED, "unverifiable-file"
        )
        self.assertIs(requirement.kind, m.ResolutionKind.UNVERIFIABLE_FRESHNESS)

    def test_details_merge_in_canonical_order(self):
        self.assertEqual(
            merge_coverage_detail(
                ("unverifiable-file", "touched-file-mismatch+injected-index")
            ),
            "injected-index+touched-file-mismatch+unverifiable-file",
        )

    def test_clean_verified_never_survives_a_reason(self):
        self.assertEqual(
            merge_coverage_detail(("clean-verified", "dirty-tree")), "dirty-tree"
        )


class ImpactQualificationTest(unittest.TestCase):
    def test_clean_structure_carries_no_qualification(self):
        answer = _impact(None)
        self.assertEqual(_qualifications(answer), [])

    def test_stale_reach_is_qualified(self):
        answer = _impact(_UnverifiedSource)
        (requirement,) = _qualifications(answer)
        self.assertIs(requirement.kind, m.ResolutionKind.STALE_EVIDENCE)
        self.assertIn("touched-file-mismatch", requirement.description)

    def test_unverifiable_reach_is_qualified(self):
        answer = _impact(lambda inner: _UnverifiedSource(inner, "unverifiable-file"))
        (requirement,) = _qualifications(answer)
        self.assertIs(requirement.kind, m.ResolutionKind.UNVERIFIABLE_FRESHNESS)


class TraceQualificationTest(unittest.TestCase):
    def test_clean_structure_carries_no_qualification(self):
        answer = _trace(None)
        self.assertEqual(_qualifications(answer), [])

    def test_stale_edges_are_qualified(self):
        answer = _trace(_UnverifiedSource)
        (requirement,) = _qualifications(answer)
        self.assertIs(requirement.kind, m.ResolutionKind.STALE_EVIDENCE)
        self.assertIn("touched-file-mismatch", requirement.description)

    def test_unverifiable_edges_are_qualified(self):
        answer = _trace(lambda inner: _UnverifiedSource(inner, "unverifiable-file"))
        (requirement,) = _qualifications(answer)
        self.assertIs(requirement.kind, m.ResolutionKind.UNVERIFIABLE_FRESHNESS)


if __name__ == "__main__":
    unittest.main()
