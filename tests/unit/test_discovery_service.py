"""Bounded discovery tests: scope association, wording, truncation, limits."""

from __future__ import annotations

import datetime
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.service.understanding_discovery import DiscoveryService
from span.shell.sqlite_store.lifecycle import LifecycleStore

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)
BOUNDS = m.QueryBounds(
    max_results=10,
    max_depth=2,
    max_subjects=8,
    max_evidence_units=10,
    max_evidence_bytes=10_000,
    max_candidate_claims=64,
    max_candidate_relationships=64,
)
CONTEXT_ID = m.InvestigationContextId("ctx-1")


def _context() -> m.InvestigationContext:
    return m.InvestigationContext(
        context_id=CONTEXT_ID,
        repository_id="repo-1",
        request_id=m.RequestId("req-1"),
        request_digest=m.ContentDigest("sha256:request"),
        origin=m.ContextOrigin.EVIDENCE_ONLY,
        state=m.ContextState.LIVE,
        scope=m.EvidenceScope(),
        created_at=NOW,
        expires_at=NOW + RETENTION.context_lifetime,
    )


def _seed(
    store: LifecycleStore,
    *,
    understanding_id: str,
    submission: str,
    question: str,
    scope: m.EvidenceScope,
    statement: str,
) -> None:
    command = m.CreateUnderstandingCommand(
        identity=m.RecordingIdentity(
            repository_id="repo-1",
            context_id=CONTEXT_ID,
            submission_id=m.SubmissionId(submission),
        ),
        target=m.ExplicitTarget(question=question, scope=scope),
        conclusions=(
            m.ProposedConclusion(
                conclusion_id=m.ConclusionId("c-1"),
                statement=statement,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                scope=scope,
                support=(
                    m.SourceSupport(observation_id=m.SourceObservationId("obs-1")),
                ),
                basis=m.SemanticBasis(
                    derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                    summary="read source",
                    input_refs=(),
                ),
            ),
        ),
    )
    store.record_understanding(
        command, understanding_id=m.UnderstandingId(understanding_id)
    )


class DiscoveryServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = LifecycleStore(
            pathlib.Path(self._tmp.name) / "lifecycle.db",
            retention=RETENTION,
            clock=lambda: NOW,
        )
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", "/repo/one")
        self.store.put_context(_context())
        _seed(
            self.store,
            understanding_id="u-a",
            submission="sub-a",
            question="What does A do?",
            scope=m.EvidenceScope(paths=("src/a.py",)),
            statement="A validates input.",
        )
        _seed(
            self.store,
            understanding_id="u-b",
            submission="sub-b",
            question="How is billing computed?",
            scope=m.EvidenceScope(paths=("src/billing.py",)),
            statement="Billing sums line items.",
        )
        self.service = DiscoveryService(store=self.store)

    def test_scope_association_finds_different_wording(self) -> None:
        result = self.service.discover(
            "repo-1",
            m.EvidenceScope(paths=("src/a.py",)),
            "Explain the validation path",
            BOUNDS,
        )
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.understanding_id.value, "u-a")
        self.assertTrue(candidate.scope_associated)
        self.assertIn("scope-associated", candidate.match_reasons)
        self.assertIsNone(result.limit_reason)

    def test_lexical_overlap_finds_without_scope(self) -> None:
        result = self.service.discover(
            "repo-1",
            m.EvidenceScope(),
            "billing line items",
            BOUNDS,
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].understanding_id.value, "u-b")
        self.assertFalse(result.candidates[0].scope_associated)
        self.assertGreater(result.candidates[0].lexical_overlap, 0)

    def test_scope_candidates_order_before_lexical_only(self) -> None:
        _seed(
            self.store,
            understanding_id="u-c",
            submission="sub-c",
            question="A related note",
            scope=m.EvidenceScope(paths=("docs/note.md",)),
            statement="A validates configuration.",
        )
        result = self.service.discover(
            "repo-1",
            m.EvidenceScope(paths=("src/a.py",)),
            "A validates",
            BOUNDS,
        )
        self.assertEqual(
            [item.understanding_id.value for item in result.candidates],
            ["u-a", "u-c"],
        )

    def test_truncation_is_explicit(self) -> None:
        bounds = m.QueryBounds(
            max_results=1,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=10,
            max_evidence_bytes=10_000,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )
        result = self.service.discover(
            "repo-1", m.EvidenceScope(), "billing validates", bounds
        )
        self.assertTrue(result.bound_info.truncated)
        self.assertEqual(result.bound_info.returned_results, 1)
        self.assertIsNotNone(result.limit_reason)

    def test_no_candidate_with_scope_is_not_global_absence(self) -> None:
        result = self.service.discover(
            "repo-1",
            m.EvidenceScope(paths=("src/unknown.py",)),
            "nothing matches",
            BOUNDS,
        )
        self.assertEqual(result.candidates, ())
        self.assertIn("not judged absent", result.limit_reason or "")

    def test_no_scope_and_no_wording_requests_clarification(self) -> None:
        result = self.service.discover("repo-1", m.EvidenceScope(), None, BOUNDS)
        self.assertEqual(result.candidates, ())
        self.assertIn("provide a concrete scope", result.limit_reason or "")


if __name__ == "__main__":
    unittest.main()
