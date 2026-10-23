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
        self.assertIs(
            g.NODE_SUBJECT_KIND["enum"], m.SubjectKind.CODE_SYMBOL
        )
        self.assertIs(
            g.RELATION_EDGE_KIND["extends"], m.StructuralEdgeKind.DEPENDS_ON
        )
        self.assertIs(
            g.RELATION_EDGE_KIND["implements"],
            m.StructuralEdgeKind.DEPENDS_ON,
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

    def test_enum_extends_implements_parse(self):
        wiring = _wiring()
        wiring["nodes"] = list(wiring["nodes"]) + [
            {
                "id": "src/types.ts#DataSource", "name": "DataSource",
                "kind": "enum", "path": "src/types.ts",
                "span": "L1-L4", "signature": None,
                "body_hash": "ff06",
            },
            {
                "id": "src/base.ts#Base", "name": "Base",
                "kind": "class", "path": "src/base.ts",
                "span": "L1-L2", "signature": None,
                "body_hash": "gg07",
            },
        ]
        wiring["edges"] = list(wiring["edges"]) + [
            {
                "source": "src/orders.js#place",
                "target": "src/base.ts#Base",
                "relation": "extends",
            },
            {
                "source": "src/orders.js#place",
                "target": "src/types.ts#DataSource",
                "relation": "implements",
            },
        ]
        src = g.GraftStructuralSource("repo-1", ".", wiring=wiring)
        enum_resolution = src.resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "DataSource", (), None),
            _bounds(),
        )
        self.assertIs(
            enum_resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED
        )
        self.assertIs(
            enum_resolution.candidates[0].subject.subject_id.subject_kind,
            m.SubjectKind.CODE_SYMBOL,
        )
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.CODE_SYMBOL,
            canonical_locator="src/orders.js#place",
        )
        kinds = {
            e.kind
            for e in src.edges(
                "repo-1", sid, (), StructuralDirection.DOWNSTREAM,
                _bounds(),
            ).items
        }
        self.assertIn(m.StructuralEdgeKind.DEPENDS_ON, kinds)

    def test_missing_index_defers_to_setup(self):
        # Lifecycle contract: construction never builds and never fails
        # for a missing index so explicit setup can run ensure_current.
        # Ordinary reads fail closed as unavailable.
        src = g.GraftStructuralSource(
            "repo-1",
            "/nonexistent-path-xyz",
            artifact_dir="/nonexistent-artifact-path-xyz",
        )
        self.assertFalse(src.has_index())
        with self.assertRaises(g.GraftUnavailableError):
            src.resolve_subject(
                "repo-1",
                m.SubjectSelector(None, "x", (), None),
                _bounds(),
            )
        freshness = src.describe_current("repo-1")
        self.assertIs(
            freshness.state, m.FreshnessState.UNVERIFIABLE
        )

    def test_malformed_wiring_raises(self):
        with self.assertRaises(g.GraftShapeError):
            g.GraftStructuralSource("repo-1", ".", wiring={"nope": []})

    def test_dangling_edges_skipped_not_crashed(self):
        """Edges to unindexed modules (stdlib imports) parse cleanly.

        Graft emits import edges to modules with no node entry
        (`typing`); they carry no canonical identity (§4.2) and are
        skipped while indexed edges keep serving.
        """
        wiring = _wiring()
        wiring["edges"] = list(wiring["edges"]) + [
            {
                "source": "src/orders.js#place",
                "target": "typing",
                "relation": "imports",
            },
        ]
        src = g.GraftStructuralSource("repo-1", ".", wiring=wiring)
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

    def test_search_exact_matches_bare_symbol_names(self):
        # EXACT/CONTAINS parity: a bare symbol name must resolve under
        # EXACT (exact-name basis), not only under CONTAINS. EXACT stays
        # exact-only: partial names still match nothing.
        import hashlib
        import tempfile
        from span.shell.structural import graft as _graft

        body = "export function place(order) {\n  return order;\n}\n"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory(prefix="span-exact-") as tmp:
            import pathlib

            root = pathlib.Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "orders.js").write_text(
                body, encoding="utf-8"
            )
            src = _graft.GraftStructuralSource(
                "repo-1",
                root,
                wiring={
                    "nodes": [{
                        "id": "src/orders.js", "name": "orders.js",
                        "kind": "file", "path": "src/orders.js",
                        "body_hash": digest,
                    }, {
                        "id": "src/orders.js#place", "name": "place",
                        "kind": "function", "path": "src/orders.js",
                        "span": "L1-L3",
                        "signature": "function place(order)",
                        "body_hash": digest,
                    }],
                    "edges": [],
                },
            )
            exact = src.search_symbols(
                "repo-1", "place", m.StructuralLocateMatch.EXACT,
                _bounds(),
            )
            self.assertEqual(len(exact.items), 1)
            self.assertEqual(
                exact.items[0].candidate.subject.subject_id.canonical_locator,
                "src/orders.js#place",
            )
            self.assertIs(
                exact.items[0].candidate.rank_basis,
                m.CandidateRankBasis.EXACT_DECLARATION,
            )
            full_id = src.search_symbols(
                "repo-1", "src/orders.js#place",
                m.StructuralLocateMatch.EXACT, _bounds(),
            )
            self.assertEqual(len(full_id.items), 1)
            self.assertIs(
                full_id.items[0].candidate.rank_basis,
                m.CandidateRankBasis.EXACT_LOCATOR,
            )
            partial = src.search_symbols(
                "repo-1", "plac", m.StructuralLocateMatch.EXACT,
                _bounds(),
            )
            self.assertEqual(partial.items, ())
            contains = src.search_symbols(
                "repo-1", "place", m.StructuralLocateMatch.CONTAINS,
                _bounds(),
            )
            self.assertTrue(
                any(
                    h.candidate.subject.subject_id.canonical_locator
                    == "src/orders.js#place"
                    for h in contains.items
                )
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

    def test_reach_unknown_subject_returns_empty_page(self):
        # Semantic-only area subjects are never structural nodes.
        # reach() must return the empty page (skipped, never guessed),
        # not leak KeyError — impact() on an admitted area depends on it.
        src = _source()
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.OTHER,
            canonical_locator="some-area",
        )
        page = src.reach(
            "repo-1", sid, (), StructuralDirection.BOTH, 3, _bounds()
        )
        self.assertEqual(page.items, ())
        self.assertFalse(page.unsupported)

    def test_factory_rejects_unknown_config(self):
        import tempfile

        from span.shell.structural import structural_source_from_config

        with self.assertRaises(ValueError):
            structural_source_from_config("nope:xyz", "/tmp/span-data")

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            src, rid = structural_source_from_config(tmp, data_dir)
            self.assertEqual(rid, pathlib.Path(tmp).name)
            # Missing index defers to setup: construction succeeds,
            # reads fail closed, no target artifacts created.
            self.assertFalse(src.has_index())
            self.assertFalse((pathlib.Path(tmp) / "graft").exists())
            # Provider prefixes never reach the public locator surface.
            with self.assertRaises(ValueError):
                structural_source_from_config(f"graft:{tmp}", data_dir)

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


    def test_repeated_resolutions_bound_subprocesses(self):
        # Perf regression: resolving several subjects must not fan out
        # one full index fingerprint plus git subprocesses per subject.
        # The fingerprint is memoized on the wiring stat; git runs once
        # per status call, not per node.
        import hashlib
        import subprocess
        import tempfile
        from unittest import mock

        bodies = {
            f"src/f{i}.js": f"export function f{i}() {{}}\n"
            for i in range(5)
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "src").mkdir()
            nodes = []
            for rel, body in bodies.items():
                (root / rel).write_text(body, encoding="utf-8")
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
                stem = pathlib.Path(rel).stem
                nodes.append({
                    "id": rel, "name": pathlib.Path(rel).name,
                    "kind": "file", "path": rel, "body_hash": digest,
                })
                nodes.append({
                    "id": f"{rel}#{stem}", "name": stem,
                    "kind": "function", "path": rel,
                    "body_hash": digest,
                })
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
            (root / "structural" / "repo-1" / ".graph").mkdir(
                parents=True
            )
            import json

            (
                root / "structural" / "repo-1" / ".graph" / "wiring.json"
            ).write_text(
                json.dumps({"nodes": nodes, "edges": []}),
                encoding="utf-8",
            )
            src = g.GraftStructuralSource(
                "repo-1", root, artifact_dir=root / "structural" / "repo-1"
            )
            real_run = subprocess.run
            calls = []

            def counting_run(*args, **kwargs):
                calls.append(args[0][:3])
                return real_run(*args, **kwargs)

            with mock.patch.object(
                g._subprocess, "run", side_effect=counting_run
            ):
                for rel in sorted(bodies):
                    page = src.locations(
                        "repo-1",
                        m.SubjectId(
                            repository_id="repo-1",
                            subject_kind=m.SubjectKind.COMPONENT,
                            canonical_locator=rel,
                        ),
                        _bounds(),
                    )
                    self.assertEqual(len(page.items), 1)
            # One git status per locations() call (5) plus the search
            # path is gone here; the bound bites only on fan-out
            # regressions (pre-fix: full fingerprint walk per call).
            self.assertLessEqual(len(calls), 10)
            self.assertTrue(
                all(cmd[0] == "git" for cmd in calls)
            )


if __name__ == "__main__":
    unittest.main()


class DottedModuleMappingTest(unittest.TestCase):
    """Dotted import endpoints attach to known file nodes.

    Adapter-local evidence join: `pkg.sub` resolves to `pkg/sub.py`
    (or `pkg/sub/__init__.py`); ties, symbol fragments, and unknown
    modules stay unmapped and the edge is skipped exactly as before.
    No guessing, no cross-repo joins."""

    def _nodes(self, *paths):
        nodes = []
        for p in paths:
            nodes.append({
                "id": p, "name": p.split("/")[-1], "kind": "file",
                "path": p, "span": "L1-L2", "signature": None,
                "body_hash": "aa01",
            })
        return nodes

    def _src(self, nodes, edges):
        import tempfile
        tmp = tempfile.mkdtemp()
        return g.GraftStructuralSource(
            "repo-1", tmp,
            wiring={"nodes": self._nodes(*nodes), "edges": edges},
        )

    def _edge(self, source, target):
        return {"source": source, "target": target, "relation": "imports"}

    def test_dotted_module_resolves_to_file(self):
        src = self._src(
            ("pkg/sub.py", "app/main.py"),
            [self._edge("app.main", "pkg.sub")],
        )
        self.assertIn(("app/main.py", "pkg/sub.py", "imports"), src._edges)

    def test_ambiguous_package_module_stays_unmapped(self):
        src = self._src(
            ("pkg/sub.py", "pkg/sub/__init__.py", "app/main.py"),
            [self._edge("app.main", "pkg.sub")],
        )
        self.assertNotIn(
            ("app/main.py", "pkg/sub.py", "imports"), src._edges,
        )
        self.assertEqual(src._edges, [])

    def test_symbol_fragment_never_maps(self):
        src = self._src(
            ("pkg/sub.py",),
            [self._edge("pkg.sub#helper", "pkg.sub")],
        )
        self.assertEqual(src._edges, [])

    def test_unknown_module_stays_unmapped(self):
        src = self._src(
            ("app/main.py",),
            [self._edge("app.main", "stdlib.os")],
        )
        self.assertEqual(src._edges, [])

    def test_known_ids_untouched(self):
        src = self._src(
            ("a.py", "b.py"),
            [self._edge("a.py", "b.py")],
        )
        self.assertIn(("a.py", "b.py", "imports"), src._edges)
