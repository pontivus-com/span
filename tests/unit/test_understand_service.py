"""Understand composition tests: candidates, cold evidence, retrieval."""

from __future__ import annotations

import datetime
import itertools
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.service.understanding_discovery import DiscoveryService
from span.service.evidence import EvidenceService
from span.service.understand import UnderstandService
from span.service.support import SupportService
from span.shell.filesystem_evidence import FilesystemEvidenceSource
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
CONTEXT_ID = m.InvestigationContextId("ctx-seed")


def _write(root: pathlib.Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class UnderstandServiceTest(unittest.TestCase):
    def _build(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = pathlib.Path(self._tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        _write(self.root, "src/app.py", "line1\nline2\nline3\n")
        _write(self.root, "styles/site.css", "body { color: red; }\n")
        self.store = LifecycleStore(
            base / "lifecycle.db", retention=RETENTION, clock=lambda: NOW
        )
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", str(self.root))
        self.evidence_source = FilesystemEvidenceSource("repo-1", self.root)
        counter = itertools.count(1)
        self.evidence = EvidenceService(
            store=self.store,
            evidence=self.evidence_source,
            clock=lambda: NOW,
            new_context_id=lambda: f"ctx-ev-{next(counter)}",
        )
        self.discovery = DiscoveryService(store=self.store)
        self.support = SupportService(
            store=self.store,
            evidence=self.evidence_source,
            authority=self.store,
            clock=lambda: NOW,
        )
        self.understand = UnderstandService(
            store=self.store,
            discovery=self.discovery,
            evidence=self.evidence,
            evidence_source=self.evidence_source,
            support=self.support,
            clock=lambda: NOW,
            new_context_id=lambda: f"ctx-u-{next(counter)}",
        )

    def _seed(self, statement: str = "A validates input.") -> None:
        self.store.put_context(
            m.InvestigationContext(
                context_id=CONTEXT_ID,
                repository_id="repo-1",
                request_id=m.RequestId("req-seed"),
                request_digest=m.ContentDigest("sha256:seed"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(),
                created_at=NOW,
                expires_at=NOW + RETENTION.context_lifetime,
            )
        )
        scope = m.EvidenceScope(paths=("src/app.py",))
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    context_id=CONTEXT_ID,
                    submission_id=m.SubmissionId("sub-seed"),
                ),
                target=m.ExplicitTarget(question="What does A do?", scope=scope),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement=statement,
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=scope,
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-1")
                            ),
                        ),
                        basis=m.SemanticBasis(
                            derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                            summary="read source",
                            input_refs=(),
                        ),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-a"),
        )

    def _request(
        self,
        question: str,
        scope: m.EvidenceScope,
    ) -> m.UnderstandQuestionRequest:
        return m.UnderstandQuestionRequest(
            repository_id="repo-1",
            request_id=m.RequestId("req-q-1"),
            question=question,
            scope=scope,
            bounds=BOUNDS,
        )

    def test_candidate_path_returns_snapshot_not_answer(self) -> None:
        self._build()
        self._seed()
        result = self.understand.question(
            self._request(
                "Explain the validation path",
                m.EvidenceScope(paths=("src/app.py",)),
            )
        )
        self.assertIsInstance(result, m.UnderstandingCandidateAnswer)
        assert isinstance(result, m.UnderstandingCandidateAnswer)
        self.assertEqual(result.context.origin, m.ContextOrigin.QUESTION)
        self.assertEqual(len(result.retrieved), 1)
        self.assertEqual(
            result.retrieved[0].conclusions[0].content.statement,
            "A validates input.",
        )

    def test_cold_question_admits_inspectable_evidence(self) -> None:
        self._build()
        result = self.understand.question(
            self._request(
                "What happens in the app?",
                m.EvidenceScope(paths=("src",)),
            )
        )
        self.assertIsInstance(result, m.InvestigationNeeded)
        assert isinstance(result, m.InvestigationNeeded)
        self.assertEqual(result.context.origin, m.ContextOrigin.QUESTION)
        self.assertEqual(len(result.evidence), 1)
        self.assertIn("line1", result.evidence[0].content)
        self.assertTrue(
            any(isinstance(item, m.AdmittedEvidence) for item in result.outcomes)
        )
        self.assertIsNotNone(result.discovery_observation_id)
        assert result.discovery_observation_id is not None
        self.assertTrue(
            self.store.has_admitted_discovery(
                result.context.context_id.value,
                result.discovery_observation_id.value,
            )
        )

    def test_truncated_inventory_creates_no_complete_scope_observation(self) -> None:
        self._build()
        bounds = m.QueryBounds(
            max_results=10,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=1,
            max_evidence_bytes=90_000,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )
        result = self.understand.question(
            m.UnderstandQuestionRequest(
                repository_id="repo-1",
                request_id=m.RequestId("req-truncated"),
                question="What happens across the app and styles?",
                scope=m.EvidenceScope(paths=("src", "styles")),
                bounds=bounds,
            )
        )
        self.assertIsInstance(result, m.InvestigationNeeded)
        assert isinstance(result, m.InvestigationNeeded)
        self.assertTrue(result.bound_info is not None)
        self.assertTrue(result.bound_info.truncated)
        self.assertIsNone(result.discovery_observation_id)
        self.assertIn("truncated", result.reason)

    def test_first_oversized_snapshot_is_a_reference(self) -> None:
        self._build()
        self._seed(statement="A" * 5_000)
        bounds = m.QueryBounds(
            max_results=10,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=10,
            max_evidence_bytes=10,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )
        result = self.understand.question(
            m.UnderstandQuestionRequest(
                repository_id="repo-1",
                request_id=m.RequestId("req-budget"),
                question="Explain the validation path",
                scope=m.EvidenceScope(paths=("src/app.py",)),
                bounds=bounds,
            )
        )
        self.assertIsInstance(result, m.UnderstandingCandidateAnswer)
        assert isinstance(result, m.UnderstandingCandidateAnswer)
        self.assertTrue(result.bound_info is not None)
        self.assertTrue(result.bound_info.truncated)
        self.assertEqual(len(result.retrieved), 1)
        self.assertIsInstance(result.retrieved[0], m.UnderstandingSnapshotReference)
        reference = result.retrieved[0]
        assert isinstance(reference, m.UnderstandingSnapshotReference)
        self.assertEqual(reference.understanding_id.value, "u-a")
        retrieved = self.understand.retrieve(
            m.UnderstandingSnapshotSelector(
                repository_id="repo-1", understanding_id="u-a"
            )
        )
        assert isinstance(retrieved, m.RetrievedUnderstanding)
        self.assertEqual(retrieved.conclusions[0].content.statement, "A" * 5_000)

    def test_cold_question_without_scope_returns_limit(self) -> None:
        self._build()
        result = self.understand.question(
            self._request("What happens in the app?", m.EvidenceScope())
        )
        self.assertIsInstance(result, m.DiscoveryLimit)
        assert isinstance(result, m.DiscoveryLimit)
        self.assertIn("provide a concrete scope", result.discovery.limit_reason or "")

    def test_retrieve_returns_exact_current_snapshot(self) -> None:
        self._build()
        self._seed()
        retrieved = self.understand.retrieve(
            m.UnderstandingSnapshotSelector(
                repository_id="repo-1", understanding_id="u-a"
            )
        )
        assert isinstance(retrieved, m.RetrievedUnderstanding)
        self.assertEqual(retrieved.understanding.understanding_id.value, "u-a")
        self.assertEqual(retrieved.version.version.value, 1)
        self.assertEqual(len(retrieved.conclusions), 1)
        self.assertEqual(retrieved.challenges, ())


if __name__ == "__main__":
    unittest.main()
