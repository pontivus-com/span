"""Addendum F F-7: adversarial structural-navigation acceptance.

Real Graft provider over throwaway repos (no git unless noted):
stale exclusion, new-caller UNVERIFIED, empty-stale-search, reload
without restart, rebuild-between-pages, high-degree recovery, and
non-indexed members. A successful campaign alone proves none of these.
"""

import json
import os
import shutil
import tempfile
import unittest

from span.core import model as m
from span import service as ops
from span.ports.structural import StaleContinuationError
from span.ports.structural import StructuralDirection
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.graft import GraftStructuralSource
from span.shell.structural.memory import fingerprint_content

REPO = "f-nav"


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _wiring(files, edges=()):
    nodes = []
    for path, content in files.items():
        nodes.append({
            "id": path, "name": path.rsplit("/", 1)[-1],
            "kind": "file", "path": path, "span": None,
            "signature": None,
            "body_hash": fingerprint_content(content),
        })
    return {"nodes": nodes, "edges": [
        {"source": s, "target": t, "relation": r} for s, t, r in edges
    ]}


def _write_repo(files):
    tmp = tempfile.mkdtemp(prefix="f-nav-")
    for path, content in files.items():
        full = os.path.join(tmp, path)
        os.makedirs(os.path.dirname(full) or tmp, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
    return tmp


def _write_wiring(tmp, wiring):
    graph = os.path.join(tmp, "graft", ".graph")
    os.makedirs(graph, exist_ok=True)
    path = os.path.join(graph, "wiring.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(wiring))
    return path


def _harness(tmp, files, wiring=None):
    structural = GraftStructuralSource(REPO, tmp, wiring=wiring)
    evidence = FixtureEvidenceSource(REPO, dict(files))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator=f"graft:{tmp}",
            structural_provider_config=f"graft:{tmp}",
            authority_seeds=(),
        ),
        repository_id=REPO, structural=structural, evidence=evidence,
        store=store,
    )
    return structural, evidence, store


def _locate_symbol(structural, evidence, store, query, **overrides):
    base = dict(
        repository_id=REPO, mode=m.StructuralLocateMode.SYMBOL,
        bounds=_bounds(), query=query,
    )
    base.update(overrides)
    return ops.locate(
        ops.SemanticStructuralLocateRequest(**base),
        structural=structural, evidence=evidence, store=store,
    )


class StaleAdversarialTest(unittest.TestCase):
    def test_stale_file_excluded_and_counted(self):
        files = {"a.py": "A = 1\n", "b.py": "B = 2\n"}
        tmp = _write_repo(files)
        try:
            structural, evidence, store = _harness(
                tmp, files, _wiring(files))
            try:
                with open(os.path.join(tmp, "a.py"), "w") as handle:
                    handle.write("A = 999\n")
                ans = _locate_symbol(
                    structural, evidence, store, "a.py")
                locs = [e.evidence_ref.locator for e in ans.entries]
                self.assertNotIn("a.py", locs)
                self.assertGreaterEqual(ans.stale_omitted, 1)
                self.assertEqual(
                    ans.coverage, m.ScopeCoverage.UNVERIFIED)
            finally:
                store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_new_caller_unverified_and_empty_proves_nothing(self):
        files = {"a.py": "A = 1\n"}
        tmp = _write_repo(files)
        try:
            structural, evidence, store = _harness(
                tmp, files, _wiring(files))
            try:
                with open(os.path.join(tmp, "c.py"), "w") as handle:
                    handle.write("import a\nprint(a.A)\n")
                ans = _locate_symbol(
                    structural, evidence, store, "c.py")
                # The index never contained c.py: nothing returned, and
                # the empty page must not read as absence.
                self.assertEqual(ans.entries, ())
                self.assertEqual(
                    ans.coverage, m.ScopeCoverage.UNVERIFIED)
            finally:
                store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rebuild_visible_without_restart(self):
        files = {"a.py": "A = 1\n"}
        tmp = _write_repo(files)
        wiring_path = _write_wiring(tmp, _wiring(files))
        try:
            structural, evidence, store = _harness(tmp, files)
            try:
                before = _locate_symbol(
                    structural, evidence, store, "b.py")
                self.assertEqual(before.entries, ())
                grown = dict(files)
                grown["b.py"] = "B = 2\n"
                with open(os.path.join(tmp, "b.py"), "w") as handle:
                    handle.write(grown["b.py"])
                with open(wiring_path, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(_wiring(grown)))
                after = _locate_symbol(
                    structural, evidence, store, "b.py")
                self.assertEqual(len(after.entries), 1)
            finally:
                store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rebuild_between_pages_rejected(self):
        files = {f"f{i}.py": f"X{i} = 1\n" for i in range(4)}
        tmp = _write_repo(files)
        wiring_path = _write_wiring(tmp, _wiring(files))
        try:
            structural, evidence, store = _harness(tmp, files)
            try:
                first = _locate_symbol(
                    structural, evidence, store, ".py",
                    match=m.StructuralLocateMatch.CONTAINS,
                    bounds=_bounds(max_results=1),
                )
                self.assertTrue(first.bound_info.truncated)
                token = first.bound_info.continuation_token
                assert token is not None
                with open(wiring_path, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(
                        _wiring(dict(files, extra="E = 1\n"))))
                with self.assertRaises(StaleContinuationError):
                    _locate_symbol(
                        structural, evidence, store, ".py",
                        match=m.StructuralLocateMatch.CONTAINS,
                        bounds=_bounds(max_results=1),
                        page_token=token,
                    )
            finally:
                store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class HighDegreeRecoveryTest(unittest.TestCase):
    def test_all_branches_past_page_limit(self):
        files = {"hub.py": "H = 1\n"}
        files.update({f"leaf{i}.py": f"L{i} = 1\n" for i in range(8)})
        edges = [("hub.py", f"leaf{i}.py", "calls") for i in range(8)]
        tmp = _write_repo(files)
        try:
            structural, evidence, store = _harness(
                tmp, files, _wiring(files, edges))
            try:
                ans = ops.neighbors(
                    ops.SemanticStructuralNeighborsRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(
                            exact_subject_id=m.SubjectId(
                                repository_id=REPO,
                                subject_kind=m.SubjectKind.COMPONENT,
                                canonical_locator="hub.py",
                            ),
                            name_or_locator=None, expected_kinds=(),
                            retrieval_scope_hint=None,
                        ),
                        direction=StructuralDirection.DOWNSTREAM,
                        bounds=_bounds(max_results=3),
                    ),
                    structural=structural, store=store,
                )
                # Adjacency pages hold 3, but traversal exhausts them:
                # all 8 branches recovered (possibly across segments).
                seen = {
                    e.target.canonical_locator for e in ans.edges
                }
                token = ans.bound_info.continuation_token
                while ans.bound_info.truncated:
                    assert token is not None
                    ans = ops.neighbors(
                        ops.SemanticStructuralNeighborsRequest(
                            repository_id=REPO,
                            target=m.SubjectSelector(
                                exact_subject_id=m.SubjectId(
                                    repository_id=REPO,
                                    subject_kind=m.SubjectKind.COMPONENT,
                                    canonical_locator="hub.py",
                                ),
                                name_or_locator=None, expected_kinds=(),
                                retrieval_scope_hint=None,
                            ),
                            direction=StructuralDirection.DOWNSTREAM,
                            bounds=_bounds(max_results=3),
                            page_token=token,
                        ),
                        structural=structural, store=store,
                    )
                    new = {
                        e.target.canonical_locator for e in ans.edges
                    }
                    self.assertFalse(seen & new)
                    seen |= new
                    token = ans.bound_info.continuation_token
                self.assertEqual(
                    seen, {f"leaf{i}.py" for i in range(8)})
            finally:
                store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class NonIndexedMemberTest(unittest.TestCase):
    def test_member_without_subject_stays_full_member(self):
        files = {"a.py": "A = 1\n", "notes.txt": "design notes\n"}
        # Index covers only a.py; notes.txt is a member without a subject.
        wiring = _wiring({"a.py": files["a.py"]})
        tmp = _write_repo(files)
        try:
            structural, evidence, store = _harness(tmp, files, wiring)
            try:
                ans = ops.locate(
                    ops.SemanticStructuralLocateRequest(
                        repository_id=REPO,
                        mode=m.StructuralLocateMode.TARGET_MEMBERS,
                        bounds=_bounds(),
                        target=m.EvidenceScope(
                            paths=("a.py", "notes.txt"),
                            evidence_refs=(),
                        ),
                    ),
                    structural=structural, evidence=evidence,
                    store=store,
                )
                by_loc = {
                    e.evidence_ref.locator: e for e in ans.entries
                }
                self.assertEqual(set(by_loc), {"a.py", "notes.txt"})
                self.assertIsNotNone(by_loc["a.py"].subject)
                self.assertIsNone(by_loc["notes.txt"].subject)
            finally:
                store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class VerifiedCoverageGitTest(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("git"), "git required for VERIFIED coverage")
    def test_clean_tree_newer_index_verifies(self):
        import subprocess

        files = {"a.py": "A = 1\n"}
        tmp = _write_repo(files)
        try:
            wiring_path = _write_wiring(tmp, _wiring(files))
            subprocess.run(
                ["git", "init", "-q"], cwd=tmp, check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "add", "-A"], cwd=tmp, check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "init"],
                cwd=tmp, check=True, capture_output=True,
            )
            # Index rewritten after HEAD: it saw exactly this tree.
            with open(wiring_path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(_wiring(files)))
            structural, evidence, store = _harness(tmp, files)
            try:
                ans = _locate_symbol(
                    structural, evidence, store, "a.py")
                self.assertEqual(len(ans.entries), 1)
                self.assertEqual(
                    ans.coverage, m.ScopeCoverage.VERIFIED)
            finally:
                store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
