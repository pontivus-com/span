"""Candidate schema-10 lifecycle store tests."""

from __future__ import annotations

import datetime
import pathlib
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

from span.core import model as m
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    create_challenge,
)
from span.shell.sqlite_store.lifecycle import (
    LifecycleStore,
    LifecycleStoreError,
    SchemaVersionError,
    SourceObservationRecord,
)

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)
LATER = datetime.datetime(2026, 10, 31, 13, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)


def _evidence(
    evidence_id: str = "ev-1",
    repository_id: str = "repo-1",
    locator: str = "src/a.py",
) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(evidence_id),
        repository_id=repository_id,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=locator,
    )


def _observation() -> SourceObservationRecord:
    return SourceObservationRecord(
        observation_id=m.SourceObservationId("obs-1"),
        repository_id="repo-1",
        evidence=_evidence(),
        content_digest=m.ContentDigest("sha256:abc"),
        captured_at=NOW,
        total_lines=1,
        whole_file=True,
        excerpt="A does X",
    )


def _basis() -> m.SemanticBasis:
    return m.SemanticBasis(
        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        summary="read source",
        input_refs=(_evidence(),),
    )


def _authority_binding(evidence_id: str = "auth-ev-1") -> m.AuthorityBinding:
    return m.AuthorityBinding(
        evidence_ref=_evidence(evidence_id, "repo-1", "docs/rule.md"),
        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _proposed_with(
    conclusion_id: str,
    statement: str,
    support: tuple[m.SupportDependency, ...],
) -> m.ProposedConclusion:
    return m.ProposedConclusion(
        conclusion_id=m.ConclusionId(conclusion_id),
        statement=statement,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        scope=m.EvidenceScope(paths=("src/a.py",)),
        support=support,
        basis=_basis(),
    )


def _content(statement: str = "A does X") -> dict[str, object]:
    return {
        "statement": statement,
        "assertion_nature": m.AssertionNature.DESCRIPTIVE,
        "scope": m.EvidenceScope(paths=("src/a.py",)),
        "support": (m.SourceSupport(observation_id=m.SourceObservationId("obs-1")),),
        "basis": _basis(),
    }


def _identity(submission: str = "sub-1") -> m.RecordingIdentity:
    return m.RecordingIdentity(
        repository_id="repo-1",
        context_id=m.InvestigationContextId("ctx-1"),
        submission_id=m.SubmissionId(submission),
    )


def _context(
    *,
    created_at: datetime.datetime = NOW,
    expires_at: datetime.datetime | None = None,
) -> m.InvestigationContext:
    return m.InvestigationContext(
        context_id=m.InvestigationContextId("ctx-1"),
        repository_id="repo-1",
        request_id=m.RequestId("req-1"),
        request_digest=m.ContentDigest("sha256:request"),
        origin=m.ContextOrigin.EVIDENCE_ONLY,
        state=m.ContextState.LIVE,
        scope=m.EvidenceScope(paths=("src/a.py",)),
        created_at=created_at,
        expires_at=expires_at,
    )


def _create_command(
    *, submission: str = "sub-1", statement: str = "A does X"
) -> m.CreateUnderstandingCommand:
    return m.CreateUnderstandingCommand(
        identity=_identity(submission),
        target=m.ExplicitTarget(
            question="What does A do?",
            scope=m.EvidenceScope(paths=("src/a.py",)),
        ),
        conclusions=(
            m.ProposedConclusion(
                conclusion_id=m.ConclusionId("c-1"),
                **_content(statement),
            ),
        ),
    )


def _update_command(
    *, expected: int = 1, submission: str = "sub-2"
) -> m.UpdateUnderstandingCommand:
    return m.UpdateUnderstandingCommand(
        identity=_identity(submission),
        understanding_id=m.UnderstandingId("u-1"),
        expected_version=m.UnderstandingVersionNumber(expected),
        confirm=(
            m.ConfirmConclusion(
                conclusion_id=m.ConclusionId("c-1"),
                **_content("A does X, reassessed"),
            ),
        ),
    )


def _verification_command(submission: str = "sub-v") -> m.RecordVerificationCommand:
    return m.RecordVerificationCommand(
        identity=_identity(submission),
        run=m.ProposedVerificationRun(
            repository_id="repo-1",
            scope=m.VerificationScope(
                description="probe",
                scope=m.EvidenceScope(paths=("src/a.py",)),
            ),
            observations=(m.SourceObservationId("obs-1"),),
            command="python3 -m unittest",
            scenario=None,
            outcome=m.VerificationOutcome.PASS,
            observed_at=NOW,
            observer="test",
        ),
    )


def _challenge(
    challenge_id: str = "ch-1",
    *,
    target_revision: int = 1,
    evidence: tuple[m.EvidenceRef, ...] | None = None,
) -> m.Challenge:
    return create_challenge(
        challenge_id=m.ChallengeId(challenge_id),
        understanding_id=m.UnderstandingId("u-1"),
        target_version=m.UnderstandingVersionNumber(target_revision),
        target_conclusions=(
            m.ConclusionRevisionRef(
                understanding_id=m.UnderstandingId("u-1"),
                conclusion_id=m.ConclusionId("c-1"),
                revision=m.ConclusionRevisionNumber(target_revision),
            ),
        ),
        reason="the conclusion is disputed",
        evidence=(_evidence(),) if evidence is None else evidence,
        provenance="test",
        now=NOW,
    )


def _challenge_command(
    submission: str = "sub-ch-create",
    reason: str = "the conclusion is disputed",
) -> m.CreateChallengeCommand:
    return m.CreateChallengeCommand(
        identity=_identity(submission),
        understanding_id=m.UnderstandingId("u-1"),
        target_version=m.UnderstandingVersionNumber(1),
        target_conclusions=(
            m.ConclusionRevisionRef(
                understanding_id=m.UnderstandingId("u-1"),
                conclusion_id=m.ConclusionId("c-1"),
                revision=m.ConclusionRevisionNumber(1),
            ),
        ),
        reason=reason,
        evidence=(_evidence(),),
        provenance="test",
    )


def _unresolved(challenge_id: str, expected: int) -> m.ChallengeDisposition:
    return m.UnresolvedChallengeDisposition(
        challenge_id=m.ChallengeId(challenge_id),
        expected_challenge_revision=m.ChallengeRevision(expected),
        remaining_question="what evidence settles this?",
        basis="the dispute remains open",
    )


def _resolved(challenge_id: str, expected: int) -> m.ChallengeDisposition:
    return m.ResolvedChallengeDisposition(
        challenge_id=m.ChallengeId(challenge_id),
        expected_challenge_revision=m.ChallengeRevision(expected),
        reasoning="checked the recorded source",
        resulting_understanding_id=m.UnderstandingId("u-1"),
        resulting_version=m.UnderstandingVersionNumber(expected + 1),
        conclusions=(
            m.ConclusionRevisionRef(
                understanding_id=m.UnderstandingId("u-1"),
                conclusion_id=m.ConclusionId("c-1"),
                revision=m.ConclusionRevisionNumber(expected + 1),
            ),
        ),
    )


def _disposition_command(
    expected_version: int,
    submission: str,
    dispositions: tuple[m.ChallengeDisposition, ...],
) -> m.UpdateUnderstandingCommand:
    return m.UpdateUnderstandingCommand(
        identity=_identity(submission),
        understanding_id=m.UnderstandingId("u-1"),
        expected_version=m.UnderstandingVersionNumber(expected_version),
        confirm=(
            m.ConfirmConclusion(
                conclusion_id=m.ConclusionId("c-1"),
                **_content("A does X, reassessed"),
            ),
        ),
        challenge_dispositions=dispositions,
    )


class LifecycleStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = pathlib.Path(self._tmp.name) / "lifecycle.db"
        self.store = LifecycleStore(self.path, retention=RETENTION, clock=lambda: NOW)
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", "/repo/one")
        self.store.put_source_observation(_observation())

    def test_schema_version_is_ten(self) -> None:
        row = self.store._connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        self.assertEqual(row["value"], "10")

    def test_create_replay_and_conflict(self) -> None:
        self.store.put_context(_context())
        command = _create_command()
        receipt = self.store.record_understanding(
            command, understanding_id=m.UnderstandingId("u-1")
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(receipt.replay_expires_at, NOW + RETENTION.replay_retention)
        replay = self.store.record_understanding(
            command, understanding_id=m.UnderstandingId("u-1")
        )
        self.assertEqual(replay.committed_at, receipt.committed_at)
        with self.assertRaises(RecordingConflict):
            self.store.record_understanding(
                _create_command(statement="different content"),
                understanding_id=m.UnderstandingId("u-1"),
            )

    def test_update_cas_and_history(self) -> None:
        self.store.put_context(_context())
        self.store.record_understanding(
            _create_command(), understanding_id=m.UnderstandingId("u-1")
        )
        receipt = self.store.record_understanding(
            _update_command(), understanding_id=m.UnderstandingId("u-1")
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 2)
        understanding = self.store.get_understanding("u-1")
        self.assertEqual(understanding.current_version.value, 2)
        version = self.store.get_version("u-1", 2)
        self.assertEqual(len(version.conclusions), 1)
        self.assertEqual(version.conclusions[0].revision.value, 2)
        self.assertEqual(len(self.store.get_conclusions("u-1")), 2)
        with self.assertRaises(RecordingConflict):
            self.store.record_understanding(
                _update_command(expected=1, submission="sub-3"),
                understanding_id=m.UnderstandingId("u-1"),
            )
        self.assertEqual(self.store.get_understanding("u-1").current_version.value, 2)

    def test_verification_run(self) -> None:
        self.store.put_context(_context())
        receipt = self.store.record_verification(_verification_command())
        self.assertEqual(len(receipt.accepted_verification_run_ids), 1)
        run = self.store.get_verification_run(
            receipt.accepted_verification_run_ids[0].value
        )
        self.assertEqual(run.outcome, m.VerificationOutcome.PASS)

    def _seed_understanding(self) -> None:
        self.store.put_context(_context())
        self.store.record_understanding(
            _create_command(), understanding_id=m.UnderstandingId("u-1")
        )

    def test_source_observation_is_immutable(self) -> None:
        self.store.put_source_observation(_observation())
        changed = SourceObservationRecord(
            observation_id=m.SourceObservationId("obs-1"),
            repository_id="repo-1",
            evidence=_evidence(),
            content_digest=m.ContentDigest("sha256:changed"),
            captured_at=NOW,
            total_lines=1,
            whole_file=True,
            excerpt="A does X",
        )
        with self.assertRaises(LifecycleStoreError):
            self.store.put_source_observation(changed)

    def test_cross_repository_context_evidence_rejected(self) -> None:
        self.store.register_repository("repo-2", "/repo/two")
        self.store.put_source_observation(
            SourceObservationRecord(
                observation_id=m.SourceObservationId("obs-2"),
                repository_id="repo-2",
                evidence=_evidence("ev-2", "repo-2", "src/b.py"),
                content_digest=m.ContentDigest("sha256:def"),
                captured_at=NOW,
                total_lines=1,
                whole_file=True,
                excerpt="A does X",
            )
        )
        self.store.put_context(_context())
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_context_evidence("ctx-1", "obs-2")

    def test_discovery_observation_admission(self) -> None:
        self.store.put_context(_context())
        observation = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-1"),
            repository_id="repo-1",
            scope=m.EvidenceScope(paths=("src",)),
            membership_fingerprint="sha256:members",
            captured_at=NOW,
        )
        self.store.put_discovery_observation(observation)
        self.assertEqual(self.store.get_discovery_observation("disc-1"), observation)
        self.assertFalse(self.store.has_admitted_discovery("ctx-1", "disc-1"))
        self.store.add_context_discovery_evidence("ctx-1", "disc-1")
        self.assertTrue(self.store.has_admitted_discovery("ctx-1", "disc-1"))
        changed = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-1"),
            repository_id="repo-1",
            scope=m.EvidenceScope(paths=("src",)),
            membership_fingerprint="sha256:other",
            captured_at=NOW,
        )
        with self.assertRaises(LifecycleStoreError):
            self.store.put_discovery_observation(changed)

    def test_discovery_admission_is_repository_bound(self) -> None:
        self.store.register_repository("repo-2", "/repo/two")
        self.store.put_context(_context())
        observation = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-2"),
            repository_id="repo-2",
            scope=m.EvidenceScope(paths=("src",)),
            membership_fingerprint="sha256:members",
            captured_at=NOW,
        )
        self.store.put_discovery_observation(observation)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_context_discovery_evidence("ctx-1", "disc-2")

    def test_verification_observations_are_recorded(self) -> None:
        self.store.put_context(_context())
        self.store.record_verification(_verification_command())
        rows = self.store._connection.execute(
            "SELECT repository_id, observation_id" " FROM verification_observations"
        ).fetchall()
        self.assertEqual([(row[0], row[1]) for row in rows], [("repo-1", "obs-1")])

    def test_concurrent_challenge_disposition_advances_once(self) -> None:
        self._seed_understanding()
        self.store.create_challenge(_challenge("ch-1"))
        second = LifecycleStore(self.path, retention=RETENTION, clock=lambda: NOW)
        self.addCleanup(second.close)
        outcomes: list[str] = []
        barrier = threading.Barrier(2)

        def run(store: LifecycleStore, submission: str) -> None:
            barrier.wait()
            try:
                store.record_understanding(
                    _disposition_command(1, submission, (_unresolved("ch-1", 1),))
                )
                outcomes.append("committed")
            except RecordingConflict:
                outcomes.append("conflict")

        threads = [
            threading.Thread(target=run, args=(self.store, "sub-c1")),
            threading.Thread(target=run, args=(second, "sub-c2")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["committed", "conflict"])
        self.assertEqual(self.store.get_challenge("ch-1").challenge_revision.value, 2)
        self.assertEqual(self.store.get_understanding("u-1").current_version.value, 2)

    def test_challenge_create_replay_and_conflict(self) -> None:
        self._seed_understanding()
        command = _challenge_command()
        receipt = self.store.record_challenge(command)
        self.assertEqual(
            receipt.accepted_challenge_ids[0].value,
            "ch:ctx-1:sub-ch-create",
        )
        replay = self.store.record_challenge(command)
        self.assertEqual(replay.committed_at, receipt.committed_at)
        self.assertEqual(len(self.store.get_challenges("u-1")), 1)
        with self.assertRaises(RecordingConflict):
            self.store.record_challenge(_challenge_command(reason="different content"))

    def test_challenge_unresolved_disposition(self) -> None:
        self._seed_understanding()
        self.store.create_challenge(_challenge("ch-1"))
        self.assertEqual(self.store.get_challenge("ch-1"), _challenge("ch-1"))
        with self.assertRaises(LifecycleStoreError):
            self.store.create_challenge(_challenge("ch-1"))
        receipt = self.store.record_understanding(
            _disposition_command(1, "sub-ch-1", (_unresolved("ch-1", 1),))
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 2)
        updated = self.store.get_challenge("ch-1")
        self.assertEqual(updated.challenge_revision.value, 2)
        self.assertEqual(updated.state, m.ChallengeState.UNRESOLVED)
        replay = self.store.record_understanding(
            _disposition_command(1, "sub-ch-1", (_unresolved("ch-1", 1),))
        )
        self.assertEqual(replay.committed_at, receipt.committed_at)
        self.assertEqual(self.store.get_challenge("ch-1").challenge_revision.value, 2)

    def test_challenge_resolved_disposition(self) -> None:
        self._seed_understanding()
        self.store.create_challenge(_challenge("ch-1"))
        receipt = self.store.record_understanding(
            _disposition_command(1, "sub-ch-r", (_resolved("ch-1", 1),))
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 2)
        updated = self.store.get_challenge("ch-1")
        self.assertEqual(updated.state, m.ChallengeState.RESOLVED)
        self.assertEqual(updated.challenge_revision.value, 2)
        self.assertIsNotNone(updated.resolution)
        assert updated.resolution is not None
        self.assertEqual(updated.resolution.resulting_version.value, 2)

    def test_mixed_resolved_and_unresolved_challenges(self) -> None:
        self._seed_understanding()
        self.store.create_challenge(_challenge("ch-1"))
        self.store.create_challenge(_challenge("ch-2"))
        self.store.record_understanding(
            _disposition_command(
                1,
                "sub-mixed-status",
                (_resolved("ch-1", 1), _unresolved("ch-2", 1)),
            )
        )
        self.assertEqual(
            self.store.get_challenge("ch-1").state, m.ChallengeState.RESOLVED
        )
        self.assertEqual(
            self.store.get_challenge("ch-2").state,
            m.ChallengeState.UNRESOLVED,
        )
        self.assertEqual(self.store.get_challenge("ch-1").challenge_revision.value, 2)
        self.assertEqual(self.store.get_challenge("ch-2").challenge_revision.value, 2)

    def test_multi_challenge_mismatch_rejects_all(self) -> None:
        self._seed_understanding()
        self.store.create_challenge(_challenge("ch-1"))
        self.store.create_challenge(_challenge("ch-2"))
        with self.assertRaises(RecordingConflict):
            self.store.record_understanding(
                _disposition_command(
                    1,
                    "sub-mixed",
                    (_unresolved("ch-1", 1), _unresolved("ch-2", 9)),
                )
            )
        self.assertEqual(self.store.get_challenge("ch-1").challenge_revision.value, 1)
        self.assertEqual(self.store.get_challenge("ch-2").challenge_revision.value, 1)
        self.assertEqual(self.store.get_understanding("u-1").current_version.value, 1)

    def test_multiple_challenge_settlement_advances_each_once(self) -> None:
        self._seed_understanding()
        self.store.create_challenge(_challenge("ch-1"))
        self.store.create_challenge(_challenge("ch-2"))
        command = _disposition_command(
            1,
            "sub-multi",
            (_unresolved("ch-1", 1), _unresolved("ch-2", 1)),
        )
        receipt = self.store.record_understanding(command)
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 2)
        self.assertEqual(self.store.get_challenge("ch-1").challenge_revision.value, 2)
        self.assertEqual(self.store.get_challenge("ch-2").challenge_revision.value, 2)
        replay = self.store.record_understanding(command)
        self.assertEqual(replay.committed_at, receipt.committed_at)
        self.assertEqual(self.store.get_challenge("ch-1").challenge_revision.value, 2)
        self.assertEqual(self.store.get_challenge("ch-2").challenge_revision.value, 2)

    def test_duplicate_challenge_ids_reject(self) -> None:
        with self.assertRaises(ValueError):
            _disposition_command(
                1,
                "sub-dup",
                (_unresolved("ch-1", 1), _unresolved("ch-1", 1)),
            )

    def test_challenge_cross_repository_evidence_rejected(self) -> None:
        self._seed_understanding()
        with self.assertRaises(RecordingValidationError):
            self.store.create_challenge(
                _challenge("ch-x", evidence=(_evidence("ev-x", "repo-2"),))
            )

    def test_challenge_target_revision_must_exist(self) -> None:
        self._seed_understanding()
        with self.assertRaises(LifecycleStoreError):
            self.store.create_challenge(_challenge("ch-x", target_revision=5))

    def test_expired_context_rejects(self) -> None:
        self.store.put_context(
            _context(
                created_at=NOW - datetime.timedelta(hours=2),
                expires_at=NOW - datetime.timedelta(hours=1),
            )
        )
        with self.assertRaises(Exception):
            self.store.record_understanding(
                _create_command(), understanding_id=m.UnderstandingId("u-1")
            )

    def test_reaping_removes_context_but_not_receipt(self) -> None:
        self.store.put_context(_context(expires_at=NOW + datetime.timedelta(hours=1)))
        receipt = self.store.record_understanding(
            _create_command(), understanding_id=m.UnderstandingId("u-1")
        )
        self.store.reap_expired(NOW + datetime.timedelta(hours=2))
        with self.assertRaises(LifecycleStoreError):
            self.store.get_context("ctx-1")
        self.assertEqual(self.store.get_receipt(_identity()), receipt)

    def test_failure_before_commit_rolls_back_every_effect(self) -> None:
        self.store.put_context(_context())
        with mock.patch.object(
            self.store,
            "_write_receipt",
            side_effect=RuntimeError("injected failure before commit"),
        ):
            with self.assertRaises(RuntimeError):
                self.store.record_understanding(
                    _create_command(), understanding_id=m.UnderstandingId("u-1")
                )
        for table in (
            "understandings",
            "understanding_versions",
            "conclusions",
            "understanding_membership",
            "record_receipts",
        ):
            count = self.store._connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            self.assertEqual(count, 0, table)
        receipt = self.store.record_understanding(
            _create_command(), understanding_id=m.UnderstandingId("u-1")
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)

    def test_abandon_context_keeps_accepted_state(self) -> None:
        self.store.put_context(_context())
        self.store.add_context_evidence("ctx-1", "obs-1")
        receipt = self.store.record_understanding(
            _create_command(), understanding_id=m.UnderstandingId("u-1")
        )
        self.assertTrue(self.store.abandon_context("ctx-1"))
        with self.assertRaises(LifecycleStoreError):
            self.store.get_context("ctx-1")
        remaining = self.store._connection.execute(
            "SELECT COUNT(*) FROM context_evidence"
        ).fetchone()[0]
        self.assertEqual(remaining, 0)
        self.assertEqual(self.store.get_receipt(_identity()), receipt)
        self.assertEqual(
            self.store.record_understanding(
                _create_command(), understanding_id=m.UnderstandingId("u-1")
            ),
            receipt,
        )
        self.assertFalse(self.store.abandon_context("ctx-1"))

    def test_concurrent_different_content_rejects_one(self) -> None:
        self.store.put_context(_context())
        second = LifecycleStore(self.path, retention=RETENTION, clock=lambda: NOW)
        self.addCleanup(second.close)
        outcomes: list[str] = []
        barrier = threading.Barrier(2)

        def run(store: LifecycleStore, statement: str) -> None:
            barrier.wait()
            try:
                store.record_understanding(
                    _create_command(statement=statement),
                    understanding_id=m.UnderstandingId("u-1"),
                )
                outcomes.append("committed")
            except RecordingConflict:
                outcomes.append("conflict")

        threads = [
            threading.Thread(target=run, args=(self.store, "first content")),
            threading.Thread(target=run, args=(second, "second content")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["committed", "conflict"])
        self.assertEqual(len(self.store.get_conclusions("u-1")), 1)

    def test_old_schema_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "old.db"
            connection = sqlite3.connect(str(path))
            with connection:
                connection.execute(
                    "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)"
                )
                connection.execute(
                    "INSERT INTO meta(key, value) VALUES('schema_version', '9')"
                )
            connection.close()
            with self.assertRaises(SchemaVersionError):
                LifecycleStore(path, retention=RETENTION)
            check = sqlite3.connect(str(path))
            try:
                tables = {
                    row[0]
                    for row in check.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            finally:
                check.close()
            self.assertEqual(tables, {"meta"})

    def test_unknown_existing_store_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "foreign.db"
            connection = sqlite3.connect(str(path))
            with connection:
                connection.execute("CREATE TABLE subjects(id TEXT PRIMARY KEY)")
            connection.close()
            with self.assertRaises(SchemaVersionError):
                LifecycleStore(path, retention=RETENTION)
            check = sqlite3.connect(str(path))
            try:
                tables = {
                    row[0]
                    for row in check.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            finally:
                check.close()
            self.assertEqual(tables, {"subjects"})

    def test_declared_authority_resolution(self) -> None:
        binding = _authority_binding()
        self.store.register_repository(
            "repo-1", "/repo/one", authority_bindings=(binding,)
        )
        self.assertEqual(self.store.resolve_authority("repo-1", "auth-ev-1"), binding)
        with self.assertRaises(RecordingValidationError):
            self.store.resolve_authority("repo-1", "auth-missing")

    def test_support_dependency_index(self) -> None:
        self._seed_understanding()
        binding = _authority_binding()
        self.store.record_understanding(
            m.UpdateUnderstandingCommand(
                identity=_identity("sub-auth"),
                understanding_id=m.UnderstandingId("u-1"),
                expected_version=m.UnderstandingVersionNumber(1),
                add=(
                    _proposed_with(
                        "c-2",
                        "A is governed by the rule",
                        (m.AuthoritySupportDependency(authority=binding),),
                    ),
                ),
            )
        )
        self.assertEqual(
            self.store.support_dependents("AUTHORITY", "auth-ev-1"),
            (
                m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u-1"),
                    conclusion_id=m.ConclusionId("c-2"),
                    revision=m.ConclusionRevisionNumber(1),
                ),
            ),
        )
        self.assertEqual(
            self.store.support_dependents("SOURCE", "obs-1"),
            (
                m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u-1"),
                    conclusion_id=m.ConclusionId("c-1"),
                    revision=m.ConclusionRevisionNumber(1),
                ),
            ),
        )
        premise = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-1"),
            conclusion_id=m.ConclusionId("c-1"),
            revision=m.ConclusionRevisionNumber(1),
        )
        self.store.record_understanding(
            m.UpdateUnderstandingCommand(
                identity=_identity("sub-premise"),
                understanding_id=m.UnderstandingId("u-1"),
                expected_version=m.UnderstandingVersionNumber(2),
                add=(
                    _proposed_with(
                        "c-3",
                        "A depends on the earlier conclusion",
                        (m.PremiseSupport(premise=premise),),
                    ),
                    _proposed_with(
                        "c-4",
                        "A was inspected completely",
                        (
                            m.DiscoverySupport(
                                observation_id=m.DiscoveryObservationId("disc-1")
                            ),
                        ),
                    ),
                ),
            )
        )
        self.assertEqual(
            self.store.support_dependents("PREMISE", "u-1/c-1@1"),
            (
                m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u-1"),
                    conclusion_id=m.ConclusionId("c-3"),
                    revision=m.ConclusionRevisionNumber(1),
                ),
            ),
        )
        self.assertEqual(
            self.store.support_dependents("DISCOVERY", "disc-1"),
            (
                m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u-1"),
                    conclusion_id=m.ConclusionId("c-4"),
                    revision=m.ConclusionRevisionNumber(1),
                ),
            ),
        )

    def test_repository_rebind_rejected(self) -> None:
        self.store.register_repository("repo-1", "/repo/one")
        with self.assertRaises(LifecycleStoreError):
            self.store.register_repository("repo-1", "/repo/two")
        with self.assertRaises(LifecycleStoreError):
            self.store.require_repository("repo-unknown")

    def test_admitted_evidence_resolves_by_observation_or_evidence_id(self) -> None:
        evidence = _evidence()
        self.store.put_source_observation(
            SourceObservationRecord(
                observation_id=m.SourceObservationId("obs-1"),
                repository_id="repo-1",
                evidence=evidence,
                content_digest=m.ContentDigest("sha256:abc"),
                captured_at=NOW,
                total_lines=1,
                whole_file=True,
                excerpt="A does X",
            )
        )
        self.store.put_context(_context())
        self.assertIsNone(self.store.find_admitted_evidence("ctx-1", "ev-1"))
        self.store.add_context_evidence("ctx-1", "obs-1")
        self.assertEqual(self.store.find_admitted_evidence("ctx-1", "ev-1"), evidence)
        self.assertEqual(self.store.find_admitted_evidence("ctx-1", "obs-1"), evidence)
        self.assertTrue(self.store.has_admitted_observation("ctx-1", "obs-1"))

    def test_concurrent_same_submission_commits_once(self) -> None:
        self.store.put_context(_context())
        second = LifecycleStore(self.path, retention=RETENTION, clock=lambda: NOW)
        self.addCleanup(second.close)
        receipts: list[m.RecordReceipt] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def run(store: LifecycleStore) -> None:
            barrier.wait()
            try:
                receipts.append(
                    store.record_understanding(
                        _create_command(), understanding_id=m.UnderstandingId("u-1")
                    )
                )
            except BaseException as exc:  # noqa: BLE001 - surfaced in assertion
                errors.append(exc)

        threads = [
            threading.Thread(target=run, args=(self.store,)),
            threading.Thread(target=run, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[0].committed_at, receipts[1].committed_at)
        self.assertEqual(len(self.store.get_conclusions("u-1")), 1)

    def test_replay_survives_context_expiry_within_replay_retention(self) -> None:
        now = [NOW]
        store = LifecycleStore(
            pathlib.Path(self._tmp.name) / "replay.db",
            retention=RETENTION,
            clock=lambda: now[0],
        )
        self.addCleanup(store.close)
        store.register_repository("repo-1", "/repo/one")
        store.put_context(_context(expires_at=NOW + RETENTION.context_lifetime))
        command = _create_command()
        receipt = store.record_understanding(
            command, understanding_id=m.UnderstandingId("u-1")
        )
        now[0] = NOW + RETENTION.context_lifetime + datetime.timedelta(minutes=1)
        with self.assertRaises(Exception):
            store.record_understanding(
                _create_command(submission="sub-2", statement="new"),
                understanding_id=m.UnderstandingId("u-2"),
            )
        self.assertEqual(
            store.record_understanding(
                command, understanding_id=m.UnderstandingId("u-1")
            ),
            receipt,
        )

    def test_receipt_is_not_retained_after_replay_expiry(self) -> None:
        now = [NOW]
        store = LifecycleStore(
            pathlib.Path(self._tmp.name) / "expiry.db",
            retention=RETENTION,
            clock=lambda: now[0],
        )
        self.addCleanup(store.close)
        store.register_repository("repo-1", "/repo/one")
        store.put_context(_context(expires_at=NOW + RETENTION.context_lifetime))
        receipt = store.record_understanding(
            _create_command(), understanding_id=m.UnderstandingId("u-1")
        )
        now[0] = NOW + RETENTION.replay_retention + datetime.timedelta(minutes=1)
        self.assertIsNone(store.get_receipt(receipt.identity))
        with self.assertRaises(Exception):
            store.record_understanding(
                _create_command(), understanding_id=m.UnderstandingId("u-1")
            )


if __name__ == "__main__":
    unittest.main()
