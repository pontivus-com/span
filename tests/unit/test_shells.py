"""Deterministic shell tests (plan Phase 1.5/1.6/1.7).

Covers the in-memory structural source, fixture evidence source and
interpreter, and the minimum SQLite store. All deterministic; no
network, no provider SDKs.
"""

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
            value=m.PurposeValue("processes payments", ()),
            evidence=(_ref("README.md"),),
            basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION),
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
            value=m.PurposeValue("processes payments", ()),
            evidence=(_ref("README.md"),),
            basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION),
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
            self.assertEqual(store.schema_version(), m.SchemaVersion(1))
            self.assertEqual(SCHEMA_VERSION, 1)
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
                        claim.claim_id,
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
                "repo-1", (claim.claim_id,)
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
                m.CanonicalIndexBatch((), (claim,), (), ())
            )
            update = m.FreshnessUpdate(
                claim.claim_id,
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
                m.CanonicalIndexBatch((), (_claim(),), (), ())
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


if __name__ == "__main__":
    unittest.main()
