"""Complete scope algebra for recording admission (FD-59)."""

import dataclasses
import unittest

from span.core import model as m


class EvidenceScopeTest(unittest.TestCase):
    def test_containment_preserves_empty_scope_meaning(self):
        whole = m.EvidenceScope()
        parent = m.EvidenceScope(paths=("src",))
        child = m.EvidenceScope(paths=("src/service",))
        other = m.EvidenceScope(paths=("ui",))
        for outer, inner, expected in (
            (whole, whole, True),
            (whole, child, True),
            (parent, whole, False),
            (parent, child, True),
            (child, parent, False),
            (parent, other, False),
        ):
            with self.subTest(outer=outer, inner=inner):
                self.assertEqual(m.evidence_scope_contains(outer, inner), expected)

    def test_exact_references_and_path_membership(self):
        ref = m.EvidenceRef(
            evidence_id=m.EvidenceId("e-1"),
            repository_id="repo-1",
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="src/a.py",
        )
        refs = m.EvidenceScope(evidence_refs=(ref,))
        self.assertTrue(m.evidence_scope_contains(refs, refs))
        self.assertTrue(
            m.evidence_scope_contains(m.EvidenceScope(paths=("src",)), refs)
        )
        self.assertFalse(
            m.evidence_scope_contains(refs, m.EvidenceScope(paths=("src",)))
        )
        self.assertFalse(
            m.evidence_scope_contains(m.EvidenceScope(paths=("docs",)), refs)
        )

    def test_union_is_deterministic_and_preserves_references(self):
        ref = m.EvidenceRef(
            evidence_id=m.EvidenceId("e-1"),
            repository_id="repo-1",
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="src/a.py",
        )
        other = dataclasses.replace(ref, evidence_id=m.EvidenceId("e-2"))
        scopes = (
            m.EvidenceScope(paths=("z", "a"), evidence_refs=(other, ref)),
            m.EvidenceScope(paths=("a",), evidence_refs=(ref,)),
        )
        expected = m.EvidenceScope(paths=("a", "z"), evidence_refs=(ref, other))
        self.assertEqual(m.evidence_scope_union(scopes), expected)
        self.assertEqual(m.evidence_scope_union(reversed(scopes)), expected)

    def test_repository_wide_union_absorbs_narrow_requirements(self):
        whole = m.EvidenceScope()
        narrow = m.EvidenceScope(paths=("docs/plan.md",))
        self.assertEqual(m.evidence_scope_union((narrow, whole)), whole)
        self.assertEqual(m.evidence_scope_union((whole, narrow)), whole)

    def test_missing_requirements_are_not_repository_wide_scope(self):
        with self.assertRaises(ValueError):
            m.evidence_scope_union(())
