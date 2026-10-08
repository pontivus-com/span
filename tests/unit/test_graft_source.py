"""Graft structural provider tests (plan Phase 2.1/2.2).

Covers the closed mapping tables, explicit errors for unknown
vocabulary and missing indexes, port behavior over parsed wiring,
and fingerprint stability. No semantic interpretation anywhere in
this module's tests.
"""

import pathlib
import unittest

from span.core import model as m
from span.ports.structural import StructuralDirection
from span.shell.structural import graft as g


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _wiring():
    return {
        "nodes": [
            {
                "id": "src/inventory.js", "name": "inventory.js",
                "kind": "file", "path": "src/inventory.js",
                "span": "L1-L4", "signature": None,
                "body_hash": "aa01",
            },
            {
                "id": "src/inventory.js#reserve", "name": "reserve",
                "kind": "function", "path": "src/inventory.js",
                "span": "L1-L3", "signature": "function reserve(sku)",
                "body_hash": "bb02",
            },
            {
                "id": "src/orders.js", "name": "orders.js",
                "kind": "file", "path": "src/orders.js",
                "span": "L1-L6", "signature": None,
                "body_hash": "cc03",
            },
            {
                "id": "src/orders.js#place", "name": "place",
                "kind": "function", "path": "src/orders.js",
                "span": "L3-L5", "signature": "function place(order)",
                "body_hash": "dd04",
            },
            {
                "id": "README.md", "name": "README.md",
                "kind": "file", "path": "README.md",
                "span": None, "signature": None,
                "body_hash": "ee05",
            },
        ],
        "edges": [
            {
                "source": "src/inventory.js",
                "target": "src/inventory.js#reserve",
                "relation": "contains",
            },
            {
                "source": "src/orders.js",
                "target": "src/orders.js#place",
                "relation": "contains",
            },
            {
                "source": "src/orders.js",
                "target": "src/inventory.js",
                "relation": "imports",
            },
            {
                "source": "src/orders.js#place",
                "target": "src/inventory.js#reserve",
                "relation": "calls",
            },
        ],
    }


def _source(tmp=None):
    import pathlib

    repo = pathlib.Path(tmp) if tmp else None
    return g.GraftStructuralSource("repo-1", repo or ".", wiring=_wiring())


class GraftMappingTest(unittest.TestCase):
    def test_closed_tables(self):
        self.assertIs(
            g.RELATION_EDGE_KIND["contains"], m.StructuralEdgeKind.DEFINES
        )
        self.assertIs(
            g.RELATION_EDGE_KIND["imports"], m.StructuralEdgeKind.IMPORTS
        )
        self.assertIs(
            g.RELATION_EDGE_KIND["calls"], m.StructuralEdgeKind.CALLS
        )
        self.assertIs(
            g.NODE_SUBJECT_KIND["file"], m.SubjectKind.COMPONENT
        )
        self.assertIs(
            g.NODE_SUBJECT_KIND["function"], m.SubjectKind.CODE_SYMBOL
        )

    def test_unknown_node_kind_raises(self):
        wiring = _wiring()
        wiring["nodes"] = [
            {
                "id": "x", "name": "x", "kind": "macro",
                "path": "x.h", "span": None, "body_hash": None,
            }
        ]
        with self.assertRaises(g.GraftVocabularyError):
            g.GraftStructuralSource("repo-1", ".", wiring=wiring)

    def test_unknown_relation_raises(self):
        wiring = _wiring()
        wiring["edges"] = [
            {"source": "a", "target": "b", "relation": "teleports"}
        ]
        with self.assertRaises(g.GraftVocabularyError):
            g.GraftStructuralSource("repo-1", ".", wiring=wiring)

    def test_missing_index_raises(self):
        with self.assertRaises(g.GraftUnavailableError):
            g.GraftStructuralSource(
                "repo-1", "/nonexistent-path-xyz"
            )

    def test_malformed_wiring_raises(self):
        with self.assertRaises(g.GraftShapeError):
            g.GraftStructuralSource("repo-1", ".", wiring={"nope": []})


class GraftPortBehaviorTest(unittest.TestCase):
    def test_resolve_exact_and_name(self):
        src = _source()
        exact = src.resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "src/orders.js#place", (), None),
            _bounds(),
        )
        self.assertIs(exact.ambiguity, m.ResolutionAmbiguity.RESOLVED)
        named = src.resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "place", (), None),
            _bounds(),
        )
        self.assertIs(named.ambiguity, m.ResolutionAmbiguity.RESOLVED)
        self.assertIs(
            named.candidates[0].rank_basis,
            m.CandidateRankBasis.EXACT_DECLARATION,
        )

    def test_file_subject_kinds(self):
        src = _source()
        resolution = src.resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "src/orders.js", (), None),
            _bounds(),
        )
        subject = resolution.candidates[0].subject
        self.assertIs(
            subject.subject_id.subject_kind, m.SubjectKind.COMPONENT
        )
        readme = src.resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "README.md", (), None),
            _bounds(),
        )
        self.assertIs(
            readme.candidates[0].subject.subject_id.subject_kind,
            m.SubjectKind.DOCUMENT,
        )

    def test_edges_mapped_kinds(self):
        src = _source()
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.CODE_SYMBOL,
            canonical_locator="src/orders.js#place",
        )
        page = src.edges(
            "repo-1", sid, (), StructuralDirection.DOWNSTREAM, _bounds()
        )
        self.assertEqual(len(page.items), 1)
        self.assertIs(page.items[0].kind, m.StructuralEdgeKind.CALLS)
        file_sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/orders.js",
        )
        both = src.edges(
            "repo-1", file_sid, (), StructuralDirection.BOTH, _bounds()
        )
        kinds = {e.kind for e in both.items}
        self.assertEqual(
            kinds,
            {m.StructuralEdgeKind.DEFINES, m.StructuralEdgeKind.IMPORTS},
        )

    def test_locations_carry_spans_and_hashes(self):
        src = _source()
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.CODE_SYMBOL,
            canonical_locator="src/orders.js#place",
        )
        page = src.locations("repo-1", sid, _bounds())
        self.assertEqual(len(page.items), 1)
        ref = page.items[0].location
        self.assertEqual(ref.locator, "src/orders.js")
        self.assertEqual(ref.section_or_span, "L3-L5")
        self.assertEqual(ref.revision_or_fingerprint, "dd04")

    def test_reach_and_state_stable(self):
        src = _source()
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.CODE_SYMBOL,
            canonical_locator="src/orders.js#place",
        )
        page = src.reach(
            "repo-1", sid, (), StructuralDirection.BOTH, 3, _bounds()
        )
        locators = {n.subject.canonical_locator for n in page.items}
        self.assertIn("src/inventory.js#reserve", locators)
        first = src.repository_state("repo-1")
        second = src.repository_state("repo-1")
        self.assertEqual(first.state_fingerprint, second.state_fingerprint)

    def test_factory_rejects_unknown_config(self):
        from span.shell.structural import structural_source_from_config

        with self.assertRaises(ValueError):
            structural_source_from_config("nope:xyz")

    def test_dirty_tree_reported_from_git(self):
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "orders.js").write_text(
                "place();\n", encoding="utf-8"
            )
            subprocess.run(
                ("git", "-C", str(root), "init", "-q"),
                check=True, timeout=60,
            )
            subprocess.run(
                ("git", "-C", str(root), "add", "-A"),
                check=True, timeout=60,
            )
            subprocess.run(
                (
                    "git", "-C", str(root),
                    "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "x",
                ),
                check=True, timeout=60,
            )
            src = g.GraftStructuralSource(
                "repo-1", root, wiring=_wiring()
            )
            clean = src.repository_state("repo-1")
            self.assertFalse(clean.dirty)
            self.assertTrue(clean.revision_id)
            (root / "src" / "orders.js").write_text(
                "place();\n// touched\n", encoding="utf-8"
            )
            dirty = src.repository_state("repo-1")
            self.assertTrue(dirty.dirty)
            # A commit alone does not move the wiring fingerprint;
            # content-addressed body hashes do.
            self.assertEqual(
                clean.state_fingerprint, dirty.state_fingerprint
            )

    def test_wiring_fingerprint_follows_body_hashes(self):
        src = _source()
        first = src.repository_state("repo-1").state_fingerprint
        altered = _wiring()
        altered["nodes"][0]["body_hash"] = "zz99"
        other = g.GraftStructuralSource(
            "repo-1", pathlib.Path("."), wiring=altered
        )
        self.assertNotEqual(
            first, other.repository_state("repo-1").state_fingerprint
        )


if __name__ == "__main__":
    unittest.main()
