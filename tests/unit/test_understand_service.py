"""Exact retrieval composition tests."""

from __future__ import annotations

import datetime
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.service.support import SupportService
from span.service.understand import UnderstandService
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.sqlite_store.lifecycle import LifecycleStore

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)
CONTEXT_ID = m.InvestigationContextId("ctx-seed")


class UnderstandServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = pathlib.Path(self._tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text("line1\n", encoding="utf-8")
        self.store = LifecycleStore(
            base / "lifecycle.db", retention=RETENTION, clock=lambda: NOW
        )
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", str(self.root))
        self.evidence_source = FilesystemEvidenceSource("repo-1", self.root)
        self.support = SupportService(
            store=self.store,
            evidence=self.evidence_source,
            authority=self.store,
            clock=lambda: NOW,
        )
        self.understand = UnderstandService(store=self.store, support=self.support)

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
                    request_id=m.RequestId("sub-seed"),
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/app.py",
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

    def test_retrieve_returns_exact_current_snapshot(self) -> None:
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
