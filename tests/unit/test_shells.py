"""Deterministic shell tests (plan Phase 1.5/1.6/1.7).

Covers the in-memory structural source, fixture evidence source and
interpreter, and the minimum SQLite store. All deterministic; no
network, no provider SDKs.
"""

import pathlib
import unittest

from span.core import model as m
from span.ports.structural import StructuralDirection
from span.shell.evidence import FixtureEvidenceSource
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.sqlite_store import SCHEMA_VERSION, SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _repo():
    files = (
        InMemoryFile("README.md", "# pay-svc\nProcesses payments.\n"),
        InMemoryFile("src/payments.py", "class Handler:\n    pass\n"),
        InMemoryFile("src/refunds.py", "class Handler:\n    pass\n"),
    )
    subjects = (
        InMemorySubject("src/payments.py", m.SubjectKind.COMPONENT, "payments"),
        InMemorySubject(
            "src/payments.py:Handler", m.SubjectKind.CODE_SYMBOL, "Handler"
        ),
        InMemorySubject(
            "src/refunds.py:Handler", m.SubjectKind.CODE_SYMBOL, "Handler"
        ),
    )
    edges = (
        InMemoryEdge(
            "src/payments.py:Handler",
            m.StructuralEdgeKind.DEFINES,
            "src/payments.py",
        ),
    )
    return InMemoryStructuralSource("repo-1", files, subjects, edges)


class MemorySourceTest(unittest.TestCase):
    def test_repository_state_fingerprint_stable(self):
        first = _repo().repository_state("repo-1")
        second = _repo().repository_state("repo-1")
        self.assertEqual(first.state_fingerprint, second.state_fingerprint)
        self.assertFalse(first.dirty)
        self.assertIsNotNone(first.observed_at.tzinfo)

    def test_unknown_repository_rejected(self):
        with self.assertRaises(ValueError):
            _repo().repository_state("nope")

    def test_exact_locator_resolution(self):
        resolution = _repo().resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "src/payments.py", (), None),
            _bounds(),
        )
        self.assertIs(resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED)
        candidate = resolution.candidates[0]
        self.assertIs(
            candidate.rank_basis, m.CandidateRankBasis.EXACT_LOCATOR
        )

    def test_shared_name_is_ambiguous(self):
        resolution = _repo().resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "Handler", (), None),
            _bounds(),
        )
        self.assertIs(resolution.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS)
        self.assertEqual(len(resolution.candidates), 2)

    def test_unknown_name_not_found(self):
        resolution = _repo().resolve_subject(
            "repo-1",
            m.SubjectSelector(None, "Nope", (), None),
            _bounds(),
        )
        self.assertIs(resolution.ambiguity, m.ResolutionAmbiguity.NOT_FOUND)

    def test_locations(self):
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/payments.py",
        )
        page = _repo().locations("repo-1", sid, _bounds())
        self.assertEqual(len(page.items), 1)
        self.assertFalse(page.unsupported)

    def test_edges_direction(self):
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.CODE_SYMBOL,
            canonical_locator="src/payments.py:Handler",
        )
        down = _repo().edges(
            "repo-1", sid, (), StructuralDirection.DOWNSTREAM, _bounds()
        )
        self.assertEqual(len(down.items), 1)
        up = _repo().edges(
            "repo-1", sid, (), StructuralDirection.UPSTREAM, _bounds()
        )
        self.assertEqual(up.items, ())

    def test_reach_bounded(self):
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.CODE_SYMBOL,
            canonical_locator="src/payments.py:Handler",
        )
        page = _repo().reach(
            "repo-1", sid, (), StructuralDirection.BOTH, 3, _bounds()
        )
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].depth, 1)
        empty = _repo().reach(
            "repo-1", sid, (), StructuralDirection.BOTH, 0, _bounds()
        )
        self.assertEqual(empty.items, ())


def _files():
    return {
        "README.md": "# pay-svc\nProcesses payments.\n",
        "src/payments.py": "class Handler:\n    pass\n",
    }


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(_files()[path]),
    )


class FixtureEvidenceTest(unittest.TestCase):
    def test_inventory_and_read(self):
        src = FixtureEvidenceSource("repo-1", _files())
        page = src.inventory_evidence(
            "repo-1", m.EvidenceScope(("README.md",), ()), _bounds()
        )
        self.assertEqual(len(page.items), 1)
        units = src.read_evidence((page.items[0].evidence_ref,), _bounds())
        self.assertEqual(units[0].content, _files()["README.md"])
        self.assertEqual(
            units[0].content_fingerprint,
            fingerprint_content(_files()["README.md"]),
        )

    def test_byte_bound_raises(self):
        src = FixtureEvidenceSource("repo-1", _files())
        with self.assertRaises(ValueError):
            src.read_evidence((_ref("README.md"),), _bounds(max_evidence_bytes=4))

    def test_selection_prefers_seeds_then_context(self):
        src = FixtureEvidenceSource("repo-1", _files())
        selection = src.select_evidence(
            "repo-1",
            m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator="src/payments.py",
            ),
            (),
            (_ref("README.md"),),
            _bounds(),
        )
        self.assertEqual(
            [r.locator for r in selection.selected_refs], ["README.md"]
        )


class FixtureAgentTest(unittest.TestCase):
    def _request(self, locator="src/payments.py"):
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator=locator,
        )
        return m.SemanticInterpretationRequest(
            repository_id="repo-1",
            subjects=(m.Subject(sid, "payments", None),),
            evidence_units=(),
            structural_observations=(),
            allowed_claim_kinds=tuple(m.ClaimKind),
            allowed_relationship_kinds=tuple(m.RelationshipKind),
            identity_bindings=(sid,),
            brief=m.TaskBrief(),
            bounds=_bounds(),
        )

    def test_canned_candidates_returned(self):
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/payments.py",
        )
        candidate = m.CandidateSemanticClaim(
            subject=sid,
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("processes payments", ()),
            evidence=(_ref("README.md"),),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "README states the payment purpose",
            ),
        )
        interp = FixtureAgent(
            {"src/payments.py": FixtureCandidates((candidate,), ())}
        )
        result = interp.perform(self._request())
        self.assertEqual(len(result.claims), 1)
        self.assertEqual(result.diagnostics, ("fixture: 1 subjects, 1 claims, 0 relationships",))

    def test_disallowed_kinds_filtered(self):
        base = self._request()
        sid = base.subjects[0].subject_id
        candidate = m.CandidateSemanticClaim(
            subject=sid,
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("processes payments", ()),
            evidence=(_ref("README.md"),),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "README states the payment purpose",
            ),
        )
        interp = FixtureAgent(
            {"src/payments.py": FixtureCandidates((candidate,), ())}
        )
        narrow = m.SemanticInterpretationRequest(
            repository_id=base.repository_id,
            subjects=base.subjects,
            evidence_units=base.evidence_units,
            structural_observations=base.structural_observations,
            allowed_claim_kinds=(m.ClaimKind.RESPONSIBILITY,),
            allowed_relationship_kinds=base.allowed_relationship_kinds,
            identity_bindings=base.identity_bindings,
            brief=base.brief,
            bounds=base.bounds,
        )
        result = interp.perform(narrow)
        self.assertEqual(result.claims, ())


def _claim(cid="c-9", locator="src/payments.py"):
    import datetime as dt

    sid = m.SubjectId(
        repository_id="repo-1",
        subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator=locator,
    )
    return m.SemanticClaim(
        claim_id=m.ClaimId(cid),
        subject=sid,
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("does X", ()),
        evidence=(_ref("src/payments.py"),),
        trust=m.TrustState.ESTABLISHED,
        freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
        basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
    )


class SqliteStoreTest(unittest.TestCase):
    def test_schema_version(self):
        store = SqliteSemanticStore(":memory:")
        try:
            self.assertEqual(store.schema_version(), m.SchemaVersion(5))
            self.assertEqual(SCHEMA_VERSION, 5)
        finally:
            store.close()

    def test_write_and_load_round_trip(self):
        store = SqliteSemanticStore(":memory:")
        try:
            claim = _claim()
            batch = m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(claim.subject, "payments", None),
                ),
                claims=(claim,),
                relationships=(),
                evidence_dependencies=(
                    m.EvidenceDependency(
                        m.ClaimRef(id=claim.claim_id),
                        m.EvidenceRef(
                            evidence_id=m.EvidenceId("ev-src/payments.py"),
                            repository_id="repo-1",
                            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                            locator="src/payments.py",
                            revision_or_fingerprint="fp",
                        ),
                        "fp",
                    ),
                ),
            )
            result = store.write_index_batch(batch)
            self.assertGreater(result.written_count, 0)
            page = store.load_claims(
                "repo-1", (claim.subject,), (), _bounds()
            )
            self.assertEqual(len(page.items), 1)
            self.assertEqual(page.items[0], claim)
            subjects = store.load_subjects("repo-1", (claim.subject,))
            self.assertEqual(len(subjects), 1)
            deps = store.load_evidence_dependencies(
                "repo-1", (m.ClaimRef(id=claim.claim_id),)
            )
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0].observed_fingerprint, "fp")
        finally:
            store.close()

    def test_mark_freshness_updates_canonical(self):
        store = SqliteSemanticStore(":memory:")
        try:
            claim = _claim()
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    (m.Subject(claim.subject, "payments", None),),
                    (claim,), (), (),
                )
            )
            update = m.FreshnessUpdate(
                m.ClaimRef(id=claim.claim_id),
                m.Freshness(m.FreshnessState.STALE, reason="changed"),
            )
            result = store.mark_freshness((update,))
            self.assertEqual(result.written_count, 1)
            page = store.load_claims(
                "repo-1", (claim.subject,), (), _bounds()
            )
            self.assertIs(
                page.items[0].freshness.state, m.FreshnessState.STALE
            )
        finally:
            store.close()

    def test_kind_filter(self):
        store = SqliteSemanticStore(":memory:")
        try:
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    (m.Subject(_claim().subject, "payments", None),),
                    (_claim(),), (), (),
                )
            )
            page = store.load_claims(
                "repo-1",
                (_claim().subject,),
                (m.ClaimKind.RESPONSIBILITY,),
                _bounds(),
            )
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_load_by_refs_unknown_fails_closed(self):
        store = SqliteSemanticStore(":memory:")
        try:
            with self.assertRaises(ValueError):
                store.load_by_refs(
                    "repo-1", (m.ClaimRef(id=m.ClaimId("c-nope")),)
                )
        finally:
            store.close()

    def test_retire_moves_history(self):
        import sqlite3

        store = SqliteSemanticStore(":memory:")
        try:
            claim = _claim()
            subject = m.Subject(claim.subject, "payments", None)
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    (subject,), (claim,), (), (),
                )
            )
            replacement = m.SemanticClaim(
                claim_id=m.ClaimId("c-10"),
                subject=claim.subject,
                kind=claim.kind,
                value=claim.value,
                assertion_nature=claim.assertion_nature,
                evidence=claim.evidence,
                trust=claim.trust,
                freshness=claim.freshness,
                basis=claim.basis,
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(subject,),
                    claims=(replacement,),
                    retires_claims=(
                        m.ClaimRef(id=claim.claim_id),
                    ),
                )
            )
            page = store.load_claims(
                "repo-1", (claim.subject,), (), _bounds()
            )
            self.assertEqual(
                [c.claim_id.value for c in page.items], ["c-10"]
            )
            rows = store._db.execute(
                "SELECT claim_id FROM retired_claims"
            ).fetchall()
            self.assertEqual([r[0] for r in rows], ["c-9"])
            with self.assertRaises(ValueError):
                store.write_index_batch(
                    m.CanonicalIndexBatch(
                        subjects=(subject,),
                        retires_claims=(
                            m.ClaimRef(id=m.ClaimId("c-gone")),
                        ),
                    )
                )
        finally:
            store.close()

    def test_claims_paging_redeems(self):
        store = SqliteSemanticStore(":memory:")
        try:
            subject = _claim().subject
            claims = tuple(
                m.SemanticClaim(
                    claim_id=m.ClaimId(f"c-{n}"),
                    subject=subject,
                    kind=m.ClaimKind.PURPOSE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue(f"s{n}", ()),
                    evidence=(),
                    basis=m.SemanticBasis(
                        m.DerivationKind.EXPLICIT_EVIDENCE
                    ),
                )
                for n in range(5)
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    (m.Subject(subject, "payments", None),),
                    claims, (), (),
                )
            )
            bounds = _bounds()
            first = store.load_claims(
                "repo-1", (subject,), (), bounds
            )
            # Default test bounds exceed 5 items: force paging.
            import dataclasses

            small = dataclasses.replace(bounds, max_results=2)
            page1 = store.load_claims(
                "repo-1", (subject,), (), small
            )
            self.assertTrue(page1.bound_info.truncated)
            token = page1.bound_info.continuation_token
            self.assertTrue(token.startswith("pg:"))
            seen = [c.claim_id.value for c in page1.items]
            while token is not None:
                page = store.load_claims(
                    "repo-1", (subject,), (), small,
                    page_token=token,
                )
                seen.extend(c.claim_id.value for c in page.items)
                token = page.bound_info.continuation_token
            self.assertEqual(len(seen), 5)
            self.assertEqual(len(set(seen)), 5)
            with self.assertRaises(ValueError):
                store.load_claims(
                    "repo-1", (subject,), (), small,
                    page_token="bogus",
                )
        finally:
            store.close()


    def test_filesystem_evidence_round_trip(self):
        import tempfile

        from span.shell.filesystem_evidence import FilesystemEvidenceSource

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "README.md").write_text(
                "# svc\n\nServes.\n", encoding="utf-8"
            )
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text(
                "X = 1\n", encoding="utf-8"
            )
            (root / "bin.dat").write_bytes(b"\x00\x01\x02binary")
            source = FilesystemEvidenceSource("repo-fs", root)
            page = source.inventory_evidence(
                "repo-fs", m.EvidenceScope(), _bounds()
            )
            locators = sorted(
                item.evidence_ref.locator for item in page.items
            )
            self.assertEqual(locators, ["README.md", "src/a.py"])
            first = {
                item.evidence_ref.locator: item.content_fingerprint
                for item in page.items
            }
            selection = source.select_evidence(
                "repo-fs",
                _claim().subject,
                (),
                (),
                _bounds(),
            )
            self.assertEqual(selection.selected_refs, ())
            units = source.read_evidence(
                tuple(
                    item.evidence_ref for item in page.items
                ),
                _bounds(),
            )
            self.assertEqual(len(units), 2)
            # Fingerprints are stable across reads.
            page2 = source.inventory_evidence(
                "repo-fs", m.EvidenceScope(), _bounds()
            )
            self.assertEqual(
                {
                    item.evidence_ref.locator: item.content_fingerprint
                    for item in page2.items
                },
                first,
            )
            with self.assertRaises(ValueError):
                source.read_evidence(
                    (
                        m.EvidenceRef(
                            evidence_id=m.EvidenceId("ev-nope"),
                            repository_id="repo-fs",
                            source_kind=(
                                m.EvidenceSourceKind.SOURCE_CODE
                            ),
                            locator="../escape.md",
                        ),
                    ),
                    _bounds(),
                )


if __name__ == "__main__":
    unittest.main()


class PrefixExpansionTest(unittest.TestCase):
    def test_filesystem_expands_directory_scope(self):
        import tempfile

        from span.shell.filesystem_evidence import FilesystemEvidenceSource

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "wf").mkdir()
            (root / "wf" / "b.py").write_text("B = 1\n", encoding="utf-8")
            (root / "wf" / "a.py").write_text("A = 1\n", encoding="utf-8")
            (root / "top.py").write_text("T = 1\n", encoding="utf-8")
            source = FilesystemEvidenceSource("repo-fs", root)
            page = source.inventory_evidence(
                "repo-fs", m.EvidenceScope(paths=("wf",), evidence_refs=()),
                _bounds(),
            )
            self.assertEqual(
                sorted(i.evidence_ref.locator for i in page.items),
                ["wf/a.py", "wf/b.py"],
            )

    def test_fixture_expands_directory_scope(self):
        src = FixtureEvidenceSource(
            "repo-1",
            {"wf/b.py": "B", "wf/a.py": "A", "top.py": "T"},
        )
        page = src.inventory_evidence(
            "repo-1", m.EvidenceScope(paths=("wf",), evidence_refs=()),
            _bounds(),
        )
        self.assertEqual(
            sorted(i.evidence_ref.locator for i in page.items),
            ["wf/a.py", "wf/b.py"],
        )

    def test_store_only_subject_gets_prefix_evidence(self):
        from span import service as ops
        from span.shell.structural.memory import InMemoryStructuralSource

        structural = InMemoryStructuralSource("repo-1", (), (), ())
        src = FixtureEvidenceSource(
            "repo-1", {"wf/b.py": "B = 1\n", "wf/a.py": "A = 1\n"}
        )
        sid = m.SubjectId(
            repository_id="repo-1", subject_kind=m.SubjectKind.SUBSYSTEM,
            canonical_locator="wf",
        )
        subject = m.Subject(sid, "W", None)
        selection = ops.discover_evidence(
            "repo-1", subject, structural=structural, evidence=src,
            bounds=_bounds(), state=m.RepositoryState(
                repository_id="repo-1", revision_id=None, dirty=False,
                state_fingerprint="fp",
                observed_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc),
            ),
        )
        self.assertEqual(
            sorted(r.locator for r in selection.selected_refs),
            ["wf/a.py", "wf/b.py"],
        )
