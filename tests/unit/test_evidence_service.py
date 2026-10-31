"""Evidence admission service tests: exact sources, ranges, reuse, bounds."""

from __future__ import annotations

import datetime
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.core.recording import RecordingConflict
from span.service.evidence import EvidenceService
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


def _write(root: pathlib.Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class EvidenceServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = pathlib.Path(self._tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        _write(self.root, "src/app.py", "line1\nline2\nline3\nline4\n")
        _write(self.root, "styles/site.css", "body { color: red; }\n")
        _write(self.root, "config/app.toml", "[section]\nkey = 1\n")
        (self.root / "assets").mkdir()
        (self.root / "assets" / "blob.dat").write_bytes(b"\x00\x01\x02")
        self.store = LifecycleStore(
            base / "lifecycle.db", retention=RETENTION, clock=lambda: NOW
        )
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", str(self.root))
        self.evidence = FilesystemEvidenceSource("repo-1", self.root)
        self.service = EvidenceService(
            store=self.store,
            evidence=self.evidence,
            clock=lambda: NOW,
            new_context_id=lambda: "ctx-ev-1",
        )

    def _start(
        self,
        requests: tuple[m.EvidenceRequest, ...],
        *,
        scope_paths: tuple[str, ...] = (),
        request_id: str = "req-ev-1",
        bounds: m.QueryBounds = BOUNDS,
    ) -> m.EvidenceAdmissionResult:
        return self.service.start(
            m.EvidenceStartRequest(
                repository_id="repo-1",
                request_id=m.RequestId(request_id),
                scope=m.EvidenceScope(paths=scope_paths),
                requests=requests,
                bounds=bounds,
            )
        )

    def test_cross_file_batch_admits_each_source(self) -> None:
        result = self._start(
            (
                m.EvidenceRequest("src/app.py"),
                m.EvidenceRequest("styles/site.css"),
                m.EvidenceRequest("config/app.toml"),
            ),
            scope_paths=("src", "styles", "config"),
        )
        self.assertEqual(
            [type(item).__name__ for item in result.outcomes],
            ["AdmittedEvidence", "AdmittedEvidence", "AdmittedEvidence"],
        )
        self.assertEqual(result.context.origin, m.ContextOrigin.EVIDENCE_ONLY)
        self.assertIsNone(result.context.question)
        self.assertEqual(len(self.service.admitted("ctx-ev-1")), 3)

    def test_duplicate_request_reuses_observation(self) -> None:
        result = self._start(
            (
                m.EvidenceRequest("src/app.py"),
                m.EvidenceRequest("src/app.py"),
            )
        )
        self.assertIsInstance(result.outcomes[0], m.AdmittedEvidence)
        self.assertIsInstance(result.outcomes[1], m.AlreadyAdmittedEvidence)
        self.assertEqual(
            result.outcomes[0].observation_id, result.outcomes[1].observation_id
        )

    def test_range_request_slices_exactly(self) -> None:
        result = self._start(
            (
                m.EvidenceRequest(
                    "src/app.py",
                    (m.SourceRange(start_line=2, end_line=3),),
                ),
            )
        )
        admitted = result.outcomes[0]
        self.assertIsInstance(admitted, m.AdmittedEvidence)
        assert isinstance(admitted, m.AdmittedEvidence)
        self.assertFalse(admitted.whole_file)
        units = self.service.read("ctx-ev-1", (admitted.observation_id.value,), BOUNDS)
        self.assertEqual(units[0].content, "line2\nline3\n")
        self.assertIsNotNone(units[0].content_range)
        assert units[0].content_range is not None
        self.assertEqual(units[0].content_range.start_line, 2)
        self.assertEqual(units[0].content_range.end_line, 3)
        self.assertEqual(units[0].content_range.total_lines, 4)

    def test_out_of_range_request_is_omitted(self) -> None:
        result = self._start(
            (
                m.EvidenceRequest(
                    "src/app.py",
                    (m.SourceRange(start_line=3, end_line=99),),
                ),
            )
        )
        self.assertIsInstance(result.outcomes[0], m.OmittedEvidence)
        self.assertEqual(self.service.admitted("ctx-ev-1"), ())

    def test_missing_and_unreadable_are_distinct_and_success_survives(self) -> None:
        result = self._start(
            (
                m.EvidenceRequest("src/app.py"),
                m.EvidenceRequest("src/missing.py"),
                m.EvidenceRequest("assets/blob.dat"),
            )
        )
        self.assertIsInstance(result.outcomes[0], m.AdmittedEvidence)
        missing = result.outcomes[1]
        unreadable = result.outcomes[2]
        self.assertIsInstance(missing, m.EvidenceSourceFailure)
        self.assertIsInstance(unreadable, m.EvidenceSourceFailure)
        assert isinstance(missing, m.EvidenceSourceFailure)
        assert isinstance(unreadable, m.EvidenceSourceFailure)
        self.assertEqual(missing.kind, m.EvidenceSourceFailureKind.MISSING)
        self.assertEqual(unreadable.kind, m.EvidenceSourceFailureKind.UNREADABLE)
        self.assertEqual(len(self.service.admitted("ctx-ev-1")), 1)

    def test_locator_outside_scope_is_omitted(self) -> None:
        result = self._start(
            (
                m.EvidenceRequest("src/app.py"),
                m.EvidenceRequest("styles/site.css"),
            ),
            scope_paths=("src",),
        )
        self.assertIsInstance(result.outcomes[0], m.AdmittedEvidence)
        self.assertIsInstance(result.outcomes[1], m.OmittedEvidence)

    def test_unit_bound_omits_remainder(self) -> None:
        bounds = m.QueryBounds(
            max_results=10,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=1,
            max_evidence_bytes=10_000,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )
        result = self._start(
            (
                m.EvidenceRequest("src/app.py"),
                m.EvidenceRequest("styles/site.css"),
            ),
            bounds=bounds,
        )
        self.assertIsInstance(result.outcomes[0], m.AdmittedEvidence)
        self.assertIsInstance(result.outcomes[1], m.OmittedEvidence)

    def test_total_byte_bound_omits_remainder(self) -> None:
        bounds = m.QueryBounds(
            max_results=10,
            max_depth=2,
            max_subjects=8,
            max_evidence_units=10,
            max_evidence_bytes=40,
            max_candidate_claims=64,
            max_candidate_relationships=64,
        )
        result = self._start(
            (
                m.EvidenceRequest("src/app.py"),
                m.EvidenceRequest("styles/site.css"),
            ),
            bounds=bounds,
        )
        self.assertIsInstance(result.outcomes[0], m.AdmittedEvidence)
        self.assertIsInstance(result.outcomes[1], m.OmittedEvidence)

    def test_extend_keeps_same_context(self) -> None:
        first = self._start((m.EvidenceRequest("src/app.py"),))
        extended = self.service.extend(
            m.EvidenceExtendRequest(
                repository_id="repo-1",
                context_id=first.context.context_id,
                requests=(m.EvidenceRequest("styles/site.css"),),
                bounds=BOUNDS,
            )
        )
        self.assertEqual(extended.context.context_id, first.context.context_id)
        self.assertEqual(len(self.service.admitted("ctx-ev-1")), 2)

    def test_retry_same_start_reuses_context_and_observations(self) -> None:
        requests = (m.EvidenceRequest("src/app.py"),)
        first = self._start(requests)
        second = self._start(requests)
        self.assertEqual(second.context.context_id, first.context.context_id)
        self.assertIsInstance(second.outcomes[0], m.AlreadyAdmittedEvidence)

    def test_changed_batch_under_same_request_rejects(self) -> None:
        self._start((m.EvidenceRequest("src/app.py"),))
        with self.assertRaises(RecordingConflict):
            self._start((m.EvidenceRequest("styles/site.css"),))

    def test_read_rejects_unadmitted_observation(self) -> None:
        self._start((m.EvidenceRequest("src/app.py"),))
        with self.assertRaises(Exception):
            self.service.read("ctx-ev-1", ("obs-unknown",), BOUNDS)

    def test_ambiguous_source_outcome_is_preserved(self) -> None:
        class AmbiguousSource:
            def read_exact(self, repository_id, request, bounds):
                return m.EvidenceSourceFailure(
                    request,
                    m.EvidenceSourceFailureKind.AMBIGUOUS,
                    "two candidate sources",
                )

        service = EvidenceService(
            store=self.store,
            evidence=AmbiguousSource(),
            clock=lambda: NOW,
            new_context_id=lambda: "ctx-ambiguous",
        )
        result = service.start(
            m.EvidenceStartRequest(
                repository_id="repo-1",
                request_id=m.RequestId("req-ambiguous"),
                scope=m.EvidenceScope(),
                requests=(m.EvidenceRequest("src/app.py"),),
                bounds=BOUNDS,
            )
        )
        self.assertIsInstance(result.outcomes[0], m.EvidenceSourceFailure)
        assert isinstance(result.outcomes[0], m.EvidenceSourceFailure)
        self.assertEqual(result.outcomes[0].kind, m.EvidenceSourceFailureKind.AMBIGUOUS)

    def test_provider_failure_propagates(self) -> None:
        class FailingSource:
            def read_exact(self, repository_id, request, bounds):
                raise RuntimeError("provider down")

        service = EvidenceService(
            store=self.store,
            evidence=FailingSource(),
            clock=lambda: NOW,
            new_context_id=lambda: "ctx-failing",
        )
        with self.assertRaises(RuntimeError):
            service.start(
                m.EvidenceStartRequest(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-failing"),
                    scope=m.EvidenceScope(),
                    requests=(m.EvidenceRequest("src/app.py"),),
                    bounds=BOUNDS,
                )
            )


if __name__ == "__main__":
    unittest.main()
