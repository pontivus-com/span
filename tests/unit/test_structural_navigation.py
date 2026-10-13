"""Addendum F: structural navigation carriers, providers, and operations.

Twelve-operation surface: `locate` (SYMBOL/FILE_OUTLINE/TARGET_MEMBERS)
and `neighbors` (resumable BFS) over the extended StructuralSource port.
Tests pin two-tier freshness, version-bound cursors, exhaustive
traversal, the four neighbors outcomes, and strict transport mapping.
"""

import unittest

from span.core import model as m
from span import service as ops
from span.ports.structural import StaleContinuationError
from span.ports.structural import StructuralDirection
from span.shell import paging as _paging
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

REPO = "struct-nav-svc"

FILES = {
    "README.md": "# struct-nav-svc\n\nServes structure.\n",
    "src/tools.py": "run = True\n",
    "src/extra.py": "EXTRA = 1\n",
}


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _memory_harness(files=None, subjects=None, edges=()):
    files = files if files is not None else dict(FILES)
    if subjects is None:
        subjects = (
            InMemorySubject(
                "src/tools.py", m.SubjectKind.COMPONENT, "tools"),
        )
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        tuple(subjects),
        tuple(edges),
    )
    evidence = FixtureEvidenceSource(REPO, dict(files))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id=REPO, structural=structural, evidence=evidence,
        store=store,
    )
    return structural, evidence, store


def _sid(loc, kind=m.SubjectKind.COMPONENT):
    return m.SubjectId(
        repository_id=REPO, subject_kind=kind, canonical_locator=loc)


class CarrierInvariantTest(unittest.TestCase):
    def test_unsupported_requires_empty(self):
        res = m.StructuralNeighborsResult(
            resolution=m.SubjectResolution(
                candidates=(), ambiguity=m.ResolutionAmbiguity.NOT_FOUND,
                bound_info=m.BoundInfo(50, 0, 0, False, None, None),
            ),
            repository_state=None,  # type: ignore[arg-type]
            bound_info=m.BoundInfo(50, 0, 0, False, None, None),
        )
        self.assertFalse(res.unsupported)
        with self.assertRaises(ValueError):
            m.StructuralNeighborsResult(
                resolution=res.resolution,
                repository_state=res.repository_state,
                bound_info=res.bound_info,
                edges=(
                    m.StructuralEdge(
                        source=_sid("a.py"), kind=m.StructuralEdgeKind.CALLS,
                        target=_sid("b.py"),
                        evidence=m.EvidenceRef(
                            evidence_id=m.EvidenceId("ev-a.py"),
                            repository_id=REPO,
                            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                            locator="a.py",
                        ),
                    ),
                ),
                unsupported=True,
            )

    def test_negative_stale_rejected(self):
        with self.assertRaises(ValueError):
            m.StructuralLocateResult(
                entries=(),
                repository_state=None,  # type: ignore[arg-type]
                bound_info=m.BoundInfo(50, 0, 0, False, None, None),
                stale_omitted=-1,
            )

    def test_coverage_detail_round_trip(self):
        import datetime
        result = m.StructuralLocateResult(
            entries=(),
            repository_state=m.RepositoryState(
                repository_id=REPO, revision_id=None, dirty=False,
                state_fingerprint="s",
                observed_at=datetime.datetime.now(datetime.timezone.utc),
            ),
            bound_info=m.BoundInfo(50, 0, 0, False, None, None),
            coverage=m.ScopeCoverage.UNVERIFIED,
            coverage_detail="dirty-tree+touched-file-mismatch",
        )
        data = m.to_canonical(result)
        back = m.from_canonical(m.StructuralLocateResult, data)
        self.assertEqual(back, result)
        with self.assertRaises(ValueError):
            m.StructuralLocateResult(
                entries=(), repository_state=result.repository_state,
                bound_info=result.bound_info,
                coverage=m.ScopeCoverage.UNVERIFIED,
                coverage_detail="bogus-token",
            )

    def test_memory_verify_detail_clean_and_stale(self):
        structural, _, _ = _memory_harness()
        clean = structural.verify_files(REPO, ("src/tools.py",))
        self.assertIs(clean.coverage, m.ScopeCoverage.VERIFIED)
        self.assertEqual(clean.coverage_detail, "clean-verified")
        stale = structural.verify_files(REPO, ("ghost.py",))
        self.assertIs(stale.coverage, m.ScopeCoverage.UNVERIFIED)
        self.assertEqual(stale.coverage_detail, "touched-file-mismatch")

    def test_round_trip_and_strict_decode(self):
        result = m.StructuralLocateResult(
            entries=(
                m.StructuralLocateEntry(
                    evidence_ref=m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-a.py"),
                        repository_id=REPO,
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="a.py",
                    ),
                    content_fingerprint="fp",
                    subject=_sid("a.py"),
                    span_text="L1-L2",
                    signature_text=None,
                ),
            ),
            repository_state=m.RepositoryState(
                repository_id=REPO, revision_id=None, dirty=False,
                state_fingerprint="s",
                observed_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc),
            ),
            bound_info=m.BoundInfo(50, 0, 1, False, None, None),
            stale_omitted=0,
            coverage=m.ScopeCoverage.VERIFIED,
        )
        data = m.to_canonical(result)
        back = m.from_canonical(m.StructuralLocateResult, data)
        self.assertEqual(back, result)
        bad = dict(data)
        bad["retired_field"] = 1
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.StructuralLocateResult, bad)


class VersionedTokenTest(unittest.TestCase):
    def test_round_trip(self):
        token = _paging.format_versioned_token("v1", 7)
        self.assertEqual(
            _paging.parse_versioned_token(token, version="v1"), 7)
        self.assertEqual(
            _paging.parse_versioned_token(None, version="v1"), 0)

    def test_drift_and_malformed(self):
        token = _paging.format_versioned_token("v1", 7)
        with self.assertRaises(ValueError) as ctx:
            _paging.parse_versioned_token(token, version="v2")
        self.assertIn("stale listing continuation", str(ctx.exception))
        for bad in ("pg:7", "pgv:v1", "pgv:v1:-1", "nope"):
            with self.assertRaises(ValueError, msg=bad):
                _paging.parse_versioned_token(bad, version="v1")
        with self.assertRaises(ValueError):
            _paging.format_versioned_token("has:colon", 0)

    def test_traversal_token_round_trip_and_drift(self):
        from span.service.operations.neighbors import (
            decode_traversal_token,
            encode_traversal_token,
        )
        token = encode_traversal_token("v9", ("a", "b"), (("c", 1),))
        visited, frontier = decode_traversal_token(token, version="v9")
        self.assertEqual(visited, ("a", "b"))
        self.assertEqual(frontier, (("c", 1),))
        with self.assertRaises(StaleContinuationError):
            decode_traversal_token(token, version="v8")
        with self.assertRaises(ValueError):
            decode_traversal_token("pg:0", version="v9")


class MemorySearchTest(unittest.TestCase):
    def test_exact_and_contains(self):
        structural, _, _ = _memory_harness()
        exact = structural.search_symbols(
            REPO, "src/tools.py", m.StructuralLocateMatch.EXACT,
            _bounds(),
        )
        self.assertEqual(len(exact.items), 1)
        self.assertEqual(
            exact.items[0].candidate.rank_basis,
            m.CandidateRankBasis.EXACT_LOCATOR,
        )
        self.assertEqual(exact.coverage, m.ScopeCoverage.VERIFIED)
        contains = structural.search_symbols(
            REPO, "tools", m.StructuralLocateMatch.CONTAINS, _bounds(),
        )
        self.assertTrue(
            any(
                h.candidate.subject.subject_id.canonical_locator
                == "src/tools.py"
                for h in contains.items
            )
        )
        missing = structural.search_symbols(
            REPO, "nope", m.StructuralLocateMatch.EXACT, _bounds(),
        )
        self.assertEqual(missing.items, ())

    def test_exact_matches_bare_display_names(self):
        structural, _, _ = _memory_harness(
            {"src/main.py": "VALUE = 1\n"},
            (InMemorySubject(
                "src/main.py", m.SubjectKind.COMPONENT, "main",
            ),),
        )
        by_locator = structural.search_symbols(
            REPO, "src/main.py", m.StructuralLocateMatch.EXACT,
            _bounds(),
        )
        self.assertEqual(len(by_locator.items), 1)
        by_name = structural.search_symbols(
            REPO, "main", m.StructuralLocateMatch.EXACT, _bounds(),
        )
        self.assertEqual(len(by_name.items), 1)
        self.assertEqual(
            by_name.items[0].candidate.rank_basis,
            m.CandidateRankBasis.EXACT_DECLARATION,
        )
        partial = structural.search_symbols(
            REPO, "mai", m.StructuralLocateMatch.EXACT, _bounds(),
        )
        self.assertEqual(partial.items, ())

    def test_pagination_and_resume(self):
        subjects = tuple(
            InMemorySubject(f"s{i}.py", m.SubjectKind.COMPONENT, f"s{i}")
            for i in range(5)
        )
        files = {f"s{i}.py": f"X{i} = 1\n" for i in range(5)}
        structural, _, _ = _memory_harness(files, subjects)
        first = structural.search_symbols(
            REPO, ".py", m.StructuralLocateMatch.CONTAINS,
            _bounds(max_results=2),
        )
        self.assertTrue(first.bound_info.truncated)
        token = first.bound_info.continuation_token
        assert token is not None
        second = structural.search_symbols(
            REPO, ".py", m.StructuralLocateMatch.CONTAINS,
            _bounds(max_results=2), token,
        )
        first_locs = {
            h.candidate.subject.subject_id.canonical_locator
            for h in first.items
        }
        second_locs = {
            h.candidate.subject.subject_id.canonical_locator
            for h in second.items
        }
        self.assertFalse(first_locs & second_locs)
        drifted = _paging.format_versioned_token("other-version", 0)
        with self.assertRaises(StaleContinuationError):
            structural.search_symbols(
                REPO, ".py", m.StructuralLocateMatch.CONTAINS,
                _bounds(max_results=2), drifted,
            )
        with self.assertRaises(ValueError):
            structural.search_symbols(
                REPO, ".py", m.StructuralLocateMatch.CONTAINS,
                _bounds(max_results=2), token + "x",
            )

    def test_outline_and_unknown_file(self):
        structural, _, _ = _memory_harness()
        page = structural.file_outline(REPO, "src/tools.py", _bounds())
        self.assertEqual(len(page.items), 1)
        self.assertEqual(
            page.items[0].subject.subject_id.canonical_locator,
            "src/tools.py",
        )
        # File on disk but no indexed subject: empty + UNVERIFIED.
        naked = structural.file_outline(REPO, "src/extra.py", _bounds())
        self.assertEqual(naked.items, ())
        self.assertEqual(naked.coverage, m.ScopeCoverage.UNVERIFIED)
        # File nowhere: empty + vacuous VERIFIED.
        void = structural.file_outline(REPO, "absent.py", _bounds())
        self.assertEqual(void.items, ())
        self.assertEqual(void.coverage, m.ScopeCoverage.VERIFIED)

    def test_verify_files(self):
        structural, _, _ = _memory_harness()
        report = structural.verify_files(REPO, ("src/tools.py",))
        self.assertEqual(report.stale_files, ())
        self.assertEqual(report.coverage, m.ScopeCoverage.VERIFIED)
        report = structural.verify_files(REPO, ("absent.py",))
        self.assertEqual(report.stale_files, ("absent.py",))
        self.assertEqual(report.coverage, m.ScopeCoverage.UNVERIFIED)


class LocateServiceTest(unittest.TestCase):
    def _req(self, **overrides):
        base = dict(
            repository_id=REPO, mode=m.StructuralLocateMode.SYMBOL,
            bounds=_bounds(), query="src/tools.py",
        )
        base.update(overrides)
        return ops.SemanticStructuralLocateRequest(**base)

    def test_symbol_end_to_end(self):
        structural, evidence, store = _memory_harness()
        ans = ops.locate(
            self._req(), structural=structural, evidence=evidence,
            store=store,
        )
        self.assertEqual(len(ans.entries), 1)
        entry = ans.entries[0]
        self.assertEqual(entry.evidence_ref.locator, "src/tools.py")
        self.assertEqual(
            entry.content_fingerprint,
            fingerprint_content("run = True\n"),
        )
        self.assertIsNotNone(entry.subject)
        self.assertEqual(ans.coverage, m.ScopeCoverage.VERIFIED)
        self.assertEqual(ans.stale_omitted, 0)

    def test_mode_validation_rejects(self):
        structural, evidence, store = _memory_harness()
        cases = [
            # SYMBOL without query.
            dict(query=None),
            dict(query="  "),
            # FILE_OUTLINE with scope / non-default match.
            dict(mode=m.StructuralLocateMode.FILE_OUTLINE,
                 target=m.EvidenceScope(paths=(), evidence_refs=())),
            dict(mode=m.StructuralLocateMode.FILE_OUTLINE,
                 match=m.StructuralLocateMatch.CONTAINS),
            # TARGET_MEMBERS without scope / with query.
            dict(mode=m.StructuralLocateMode.TARGET_MEMBERS),
            dict(mode=m.StructuralLocateMode.TARGET_MEMBERS,
                 target=m.EvidenceScope(paths=("src/tools.py",),
                                        evidence_refs=()),
                 query="src/tools.py"),
        ]
        for kwargs in cases:
            with self.assertRaises(ValueError, msg=str(kwargs)):
                ops.locate(
                    self._req(**kwargs), structural=structural,
                    evidence=evidence, store=store,
                )

    def test_uninitialized_repo_rejected(self):
        structural, evidence, _ = _memory_harness()
        store = SqliteSemanticStore(":memory:")
        try:
            with self.assertRaises(ValueError):
                ops.locate(
                    self._req(), structural=structural, evidence=evidence,
                    store=store,
                )
        finally:
            store.close()

    def test_target_members_subject_and_null(self):
        structural, evidence, store = _memory_harness()
        ans = ops.locate(
            self._req(
                mode=m.StructuralLocateMode.TARGET_MEMBERS, query=None,
                target=m.EvidenceScope(
                    paths=("src/tools.py", "src/extra.py"),
                    evidence_refs=(),
                ),
            ),
            structural=structural, evidence=evidence, store=store,
        )
        by_loc = {e.evidence_ref.locator: e for e in ans.entries}
        self.assertEqual(
            set(by_loc), {"src/tools.py", "src/extra.py"})
        self.assertIsNotNone(by_loc["src/tools.py"].subject)
        # No indexed subject for extra.py: full member, null subject.
        self.assertIsNone(by_loc["src/extra.py"].subject)


class NeighborsServiceTest(unittest.TestCase):
    def _star(self):
        edges = tuple(
            InMemoryEdge(f"hub.py", m.StructuralEdgeKind.CALLS, f"m{i}.py")
            for i in range(3)
        ) + tuple(
            InMemoryEdge(f"m{i}.py", m.StructuralEdgeKind.CALLS, f"l{i}{j}.py")
            for i in range(3) for j in range(2)
        )
        files = {"hub.py": "H = 1\n"}
        files.update({f"m{i}.py": f"M{i} = 1\n" for i in range(3)})
        files.update(
            {f"l{i}{j}.py": f"L{i}{j} = 1\n"
             for i in range(3) for j in range(2)}
        )
        subjects = (InMemorySubject(
            "hub.py", m.SubjectKind.COMPONENT, "hub"),) + tuple(
            InMemorySubject(f"m{i}.py", m.SubjectKind.COMPONENT, f"m{i}")
            for i in range(3)
        ) + tuple(
            InMemorySubject(
                f"l{i}{j}.py", m.SubjectKind.COMPONENT, f"l{i}{j}")
            for i in range(3) for j in range(2)
        )
        return _memory_harness(files, subjects, edges)

    def _req(self, target_loc="hub.py", **overrides):
        base = dict(
            repository_id=REPO,
            target=m.SubjectSelector(
                exact_subject_id=_sid(target_loc),
                name_or_locator=None, expected_kinds=(),
                retrieval_scope_hint=None,
            ),
            direction=StructuralDirection.DOWNSTREAM,
            bounds=_bounds(),
        )
        base.update(overrides)
        return ops.SemanticStructuralNeighborsRequest(**base)

    def test_depth_one_complete(self):
        structural, _, store = self._star()
        ans = ops.neighbors(
            self._req(), structural=structural, store=store)
        self.assertEqual(
            ans.resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED)
        self.assertFalse(ans.unsupported)
        self.assertEqual(len(ans.edges), 3)
        self.assertFalse(ans.bound_info.truncated)

    def test_truncation_and_resume_no_duplicates(self):
        structural, _, store = self._star()
        seen: list[str] = []
        token = None
        segments = 0
        while True:
            ans = ops.neighbors(
                self._req(bounds=_bounds(max_subjects=2), max_depth=2,
                          page_token=token),
                structural=structural, store=store)
            segments += 1
            self.assertGreater(segments, 0)
            if segments > 10:
                raise AssertionError("traversal did not terminate")
            seen += [
                (e.source.canonical_locator, e.target.canonical_locator)
                for e in ans.edges
            ]
            token = ans.bound_info.continuation_token
            if not ans.bound_info.truncated:
                break
            assert token is not None
        # All 3 hub edges + all 6 mid edges, each exactly once.
        self.assertGreater(segments, 1)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 9)

    def test_ambiguous_and_not_found(self):
        subjects = (
            InMemorySubject("a.py", m.SubjectKind.COMPONENT, "same"),
            InMemorySubject("b.py", m.SubjectKind.COMPONENT, "same"),
        )
        files = {"a.py": "A = 1\n", "b.py": "B = 1\n"}
        structural, _, store = _memory_harness(files, subjects)
        amb = ops.neighbors(
            ops.SemanticStructuralNeighborsRequest(
                repository_id=REPO,
                target=m.SubjectSelector(
                    exact_subject_id=None, name_or_locator="same",
                    expected_kinds=(), retrieval_scope_hint=None),
                direction=StructuralDirection.DOWNSTREAM,
                bounds=_bounds(),
            ),
            structural=structural, store=store)
        self.assertEqual(
            amb.resolution.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS)
        self.assertEqual(amb.edges, ())
        self.assertFalse(amb.unsupported)
        missing = ops.neighbors(
            self._req(target_loc="absent.py"),
            structural=structural, store=store)
        self.assertEqual(
            missing.resolution.ambiguity, m.ResolutionAmbiguity.NOT_FOUND)
        self.assertEqual(missing.edges, ())

    def test_unsupported_passthrough(self):
        from span.shell.structural.memory import InMemoryStructuralSource

        class _UnsupportedEdges(InMemoryStructuralSource):
            def edges(self, repository_id, subject, edge_kinds,
                      direction, bounds, page_token=None):
                self._check_repository(repository_id)
                return m.StructuralEdgePage(
                    items=(),
                    repository_state=self.repository_state(repository_id),
                    bound_info=m.BoundInfo(
                        bounds.max_results, 0, 0, False, None, None),
                    unsupported=True,
                )

        files = {"hub.py": "H = 1\n"}
        structural = _UnsupportedEdges(
            REPO, tuple(InMemoryFile(p, c) for p, c in files.items()),
            (InMemorySubject(
                "hub.py", m.SubjectKind.COMPONENT, "hub"),),
        )
        evidence = FixtureEvidenceSource(REPO, dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id=REPO, structural=structural, evidence=evidence,
            store=store,
        )
        try:
            ans = ops.neighbors(
                self._req(), structural=structural, store=store)
            self.assertTrue(ans.unsupported)
            self.assertEqual(ans.edges, ())
        finally:
            store.close()

    def test_max_depth_validation(self):
        structural, _, store = self._star()
        for bad in (0, -1, True, "2"):
            with self.assertRaises(ValueError, msg=str(bad)):
                ops.neighbors(
                    self._req(max_depth=bad), structural=structural,
                    store=store)


class StaleContinuationEnvelopeTest(unittest.TestCase):
    def test_stale_token_maps_to_envelope(self):
        from span.shell.mcp import McpAdapter, ServiceContext

        structural, evidence, store = _memory_harness()
        try:
            adapter = McpAdapter(
                contexts={
                    REPO: ServiceContext(
                        structural=structural, evidence=evidence,
                        store=store,
                        continuations=ContinuationStore(),
                        authority_seeds=(),
                    )
                }
            )
            out = adapter.dispatch(
                "locate",
                {
                    "repository_id": REPO,
                    "mode": "SYMBOL",
                    "query": "src/tools.py",
                    "page_token": "pgv:deadbeef:0",
                },
            )
            self.assertTrue(out.is_error)
            self.assertIn("stale_continuation", out.content)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
