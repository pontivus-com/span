"""Verification is a link plus a record; currency is derived (Step 17).

A claim may attest a candidate or say unknown. It cannot assert a pass. Status
projects CURRENT_PASS / CURRENT_FAIL / STALE / UNKNOWN from the single execution
record for the link's evidence scope, compared against the current revision.
"""

import dataclasses
import datetime
import json
import pathlib
import sqlite3
import tempfile
import unittest

from span.core import model as m
from span.core import validation as core_validation
from span.shell.agent_exchange.continuations import ContinuationStore
from span.service.requests import SemanticInitializeRepositoryRequest
from span.shell.sqlite_store import SqliteSemanticStore, migrate_store
from span import service as ops
from span.service.operations.status import _derived_verification_status
from tests.support.agent_exchange import (
    REPO,
    _bounds,
    _establish,
    _harness,
    _seeds,
)

SUBJECT = m.SubjectId(REPO, m.SubjectKind.COMPONENT, "src/a.py")
VERIFIED = m.SubjectId(REPO, m.SubjectKind.TEST_OR_GATE, "test/test_a.py")
SCOPE = m.EvidenceScope(paths=("src/a.py",), evidence_refs=())
SCOPE_FP = m.evidence_scope_fingerprint(SCOPE)


def _state(revision="rev-1"):
    return m.RepositoryState(
        repository_id=REPO,
        revision_id=revision,
        dirty=False,
        state_fingerprint="fp",
        observed_at=datetime.datetime.now(datetime.timezone.utc),
    )


def _claim():
    return m.SemanticClaim(
        claim_id=m.ClaimId("c-v"),
        subject=SUBJECT,
        kind=m.ClaimKind.VERIFICATION,
        value=m.VerificationValue(VERIFIED, m.VerificationKind.TEST),
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        evidence=(
            m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-a"),
                repository_id=REPO,
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/a.py",
                revision_or_fingerprint="hash",
            ),
        ),
        trust=m.TrustState.ESTABLISHED,
        freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
        basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION, ""),
    )


def _record(revision="rev-1", exit_status=0):
    return m.VerificationRecord(
        repository_id=REPO,
        subject=VERIFIED,
        scope_fingerprint=SCOPE_FP,
        command="pytest tests/unit/test_a.py",
        exit_status=exit_status,
        observed_revision=revision,
        observed_at=datetime.datetime.now(datetime.timezone.utc),
        observer="ci",
    )


def _write_record(store, record):
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=(m.Subject(SUBJECT, "a", None),),
            verification_records=(record,),
        )
    )


def _execution(exit_status=0, subject=VERIFIED):
    return m.ExecutedVerification(
        repository_id=REPO,
        subject=subject,
        command="pytest tests/unit/test_a.py",
        exit_status=exit_status,
        observed_revision="rev-1",
        observed_at=datetime.datetime.now(datetime.timezone.utc),
        observer="ci",
    )


class ExecutionIngressTest(unittest.TestCase):
    def _result(self, *executions):
        return m.SemanticInterpretationResult(verification_records=tuple(executions))

    def test_the_record_identity_is_derived_from_the_link(self):
        (record,) = core_validation.validate_verification_records(
            REPO, self._result(_execution()), (_claim(),)
        )
        self.assertEqual(record.scope_fingerprint, SCOPE_FP)
        self.assertFalse(hasattr(_execution(), "scope_fingerprint"))

    def test_an_execution_without_a_link_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no submitted verification link"):
            core_validation.validate_verification_records(
                REPO, self._result(_execution()), ()
            )

    def test_two_different_scopes_for_one_subject_are_ambiguous(self):
        other = dataclasses.replace(
            _claim(),
            evidence=(
                m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-b"),
                    repository_id=REPO,
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator="src/b.py",
                    revision_or_fingerprint="hash",
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "ambiguous verification scope"):
            core_validation.validate_verification_records(
                REPO, self._result(_execution()), (_claim(), other)
            )

    def test_execution_enters_through_the_exchange_and_is_stored(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            current = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                authority_seeds=_seeds(),
            )
            first = True
            for _ in range(8):
                if isinstance(current, m.SemanticAnswer):
                    break
                result = agent.perform(current.request)
                if first:
                    flow_verified = m.SubjectId(
                        REPO, m.SubjectKind.TEST_OR_GATE, "test/test_flow.py"
                    )
                    result = dataclasses.replace(
                        result,
                        verification_records=(_execution(subject=flow_verified),),
                    )
                    first = False
                current = ops.submit_interpretation(
                    current.continuation,
                    result,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
            flow_fp = m.evidence_scope_fingerprint(
                m.EvidenceScope(paths=("src/flow.py",), evidence_refs=())
            )
            record = store.load_verification_record(REPO, flow_verified, flow_fp)
            self.assertIsNotNone(record)
            self.assertEqual(record.exit_status, 0)
            self.assertEqual(record.observer, "ci")
        finally:
            store.close()


class DerivedCurrencyTest(unittest.TestCase):
    def test_matching_revision_reads_current_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "s.db"))
            try:
                _write_record(store, _record(exit_status=0))
                status = _derived_verification_status(
                    REPO, _state("rev-1"), _claim(), store=store
                )
                self.assertIs(status.currency, m.DerivedCurrency.CURRENT_PASS)
            finally:
                store.close()

    def test_non_zero_exit_reads_current_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "s.db"))
            try:
                _write_record(store, _record(exit_status=1))
                status = _derived_verification_status(
                    REPO, _state("rev-1"), _claim(), store=store
                )
                self.assertIs(status.currency, m.DerivedCurrency.CURRENT_FAIL)
            finally:
                store.close()

    def test_moved_revision_reads_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "s.db"))
            try:
                _write_record(store, _record(revision="rev-0"))
                status = _derived_verification_status(
                    REPO, _state("rev-1"), _claim(), store=store
                )
                self.assertIs(status.currency, m.DerivedCurrency.STALE)
            finally:
                store.close()

    def test_absent_record_reads_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "s.db"))
            try:
                status = _derived_verification_status(
                    REPO, _state(), _claim(), store=store
                )
                self.assertIs(status.currency, m.DerivedCurrency.UNKNOWN)
            finally:
                store.close()

    def test_repeated_writes_leave_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "s.db"))
            try:
                _write_record(store, _record(exit_status=0))
                _write_record(store, _record(exit_status=1))
                (count,) = store._db.execute(
                    "SELECT COUNT(*) FROM verification_records"
                ).fetchone()
                self.assertEqual(count, 1)
            finally:
                store.close()


class PurgeRemovesRecordsTest(unittest.TestCase):
    def test_purging_the_repository_removes_its_records(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            store = SqliteSemanticStore(str(data / "repo.db"))
            try:
                _write_record(store, _record())
            finally:
                store.close()
            install.purge_repository(data, "repo")
            reopened = SqliteSemanticStore(str(data / "repo.db"))
            try:
                self.assertIsNone(
                    reopened.load_verification_record(REPO, VERIFIED, SCOPE_FP)
                )
            finally:
                reopened.close()


class AttestedVocabularyTest(unittest.TestCase):
    def test_a_pass_cannot_be_attested(self):
        self.assertEqual(
            {member.value for member in m.AttestedCurrency},
            {"CANDIDATE", "UNKNOWN"},
        )

    def test_decode_rejects_an_asserted_pass(self):
        payload = m.to_canonical(_claim())
        payload["value"]["attested_currency"] = "CURRENT_PASS"
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.SemanticClaim, payload)


class StatusPublicationTest(unittest.TestCase):
    def _status(self, structural, evidence, store):
        return ops.status(
            ops.SemanticStatusRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, "src/flow.py", (), None),
                bounds=_bounds(),
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=ContinuationStore(),
        )

    def test_status_never_publishes_an_attested_pass(self):
        structural, evidence, store, agent = _harness()
        try:
            _establish(structural, evidence, store, agent)
            answer = self._status(structural, evidence, store)
            currencies = {
                status.currency for status in answer.content.verification_status
            }
            self.assertTrue(currencies)
            self.assertNotIn(m.DerivedCurrency.CURRENT_PASS, currencies)
            self.assertEqual(currencies, {m.DerivedCurrency.UNKNOWN})
        finally:
            store.close()

    def test_status_publishes_a_recorded_pass(self):
        structural, evidence, store, agent = _harness()
        try:
            _establish(structural, evidence, store, agent)
            state = structural.repository_state(REPO)
            verified = m.SubjectId(
                REPO, m.SubjectKind.TEST_OR_GATE, "test/test_flow.py"
            )
            # Both fixture links cite src/flow.py, so one record covers
            # both and the key stays (subject, scope).
            scope = m.EvidenceScope(paths=("src/flow.py",), evidence_refs=())
            subject = store.load_subjects(REPO, (_subject_of(store),))[0]
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(subject,),
                    verification_records=(
                        m.VerificationRecord(
                            repository_id=REPO,
                            subject=verified,
                            scope_fingerprint=m.evidence_scope_fingerprint(scope),
                            command="pytest tests/unit/test_flow.py",
                            exit_status=0,
                            observed_revision=state.revision_id,
                            observed_at=datetime.datetime.now(datetime.timezone.utc),
                            observer="ci",
                        ),
                    ),
                )
            )
            answer = self._status(structural, evidence, store)
            currencies = {
                status.currency for status in answer.content.verification_status
            }
            self.assertEqual(currencies, {m.DerivedCurrency.CURRENT_PASS})
        finally:
            store.close()


def _subject_of(store):
    return m.SubjectId(REPO, m.SubjectKind.COMPONENT, "src/flow.py")


class MigrationPayloadRewriteTest(unittest.TestCase):
    def _store_with_old_pass(self, tmp):
        path = pathlib.Path(tmp) / "s.db"
        store = SqliteSemanticStore(str(path))
        try:
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(SUBJECT, "a", None),),
                    claims=(_claim(),),
                )
            )
            (payload,) = store._db.execute(
                "SELECT canonical_json FROM claims WHERE claim_id='c-v'"
            ).fetchone()
            data = json.loads(payload)
            data["value"]["currency"] = "CURRENT_PASS"
            data["value"]["observed_revision"] = "rev-1"
            with store._db:
                store._db.execute(
                    "UPDATE claims SET canonical_json=? WHERE claim_id='c-v'",
                    (json.dumps(data, sort_keys=True),),
                )
        finally:
            store.close()
        connection = sqlite3.connect(str(path))
        try:
            with connection:
                connection.execute("DROP TABLE verification_records")
                connection.execute(
                    "UPDATE meta SET value='7' WHERE key='schema_version'"
                )
        finally:
            connection.close()
        return path

    def test_asserted_pass_migrates_to_an_unknown_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._store_with_old_pass(tmp)
            report = migrate_store(path)
            self.assertEqual(report["rewritten_verifications"], 1)

            store = SqliteSemanticStore(str(path))
            try:
                (claim,) = store.load_claims(REPO, (SUBJECT,), (), _bounds()).items
                self.assertIsInstance(claim.value, m.VerificationValue)
                self.assertIs(claim.value.attested_currency, m.AttestedCurrency.UNKNOWN)
                self.assertFalse(hasattr(claim.value, "currency"))
            finally:
                store.close()

    def test_second_migration_rewrites_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._store_with_old_pass(tmp)
            migrate_store(path)
            self.assertEqual(migrate_store(path)["rewritten_verifications"], 0)


class MigratedStoreAnswersTest(unittest.TestCase):
    def test_migrated_store_reads_and_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "repo.db"
            structural, evidence, _unused, agent = _harness()
            store = SqliteSemanticStore(str(path))
            try:
                ops.initialize_repository(
                    SemanticInitializeRepositoryRequest(
                        repository_locator="fixture", authority_seeds=()
                    ),
                    repository_id=REPO,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                )
                _establish(structural, evidence, store, agent)
                rows = store._db.execute(
                    "SELECT claim_id, canonical_json FROM claims "
                    "WHERE kind='VERIFICATION'"
                ).fetchall()
                self.assertTrue(rows)
                with store._db:
                    for claim_id, payload in rows:
                        data = json.loads(payload)
                        data["value"]["currency"] = "CURRENT_PASS"
                        store._db.execute(
                            "UPDATE claims SET canonical_json=? " "WHERE claim_id=?",
                            (json.dumps(data, sort_keys=True), claim_id),
                        )
            finally:
                store.close()

            connection = sqlite3.connect(str(path))
            try:
                with connection:
                    connection.execute("DROP TABLE verification_records")
                    connection.execute(
                        "UPDATE meta SET value='7' WHERE key='schema_version'"
                    )
            finally:
                connection.close()

            report = migrate_store(path)
            self.assertEqual(report["rewritten_verifications"], len(rows))

            reopened = SqliteSemanticStore(str(path))
            try:
                answer = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/flow.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=reopened,
                    continuations=ContinuationStore(),
                )
                self.assertIsInstance(answer, m.SemanticAnswer)
                currencies = {
                    status.currency for status in answer.content.verification_status
                }
                self.assertEqual(currencies, {m.DerivedCurrency.UNKNOWN})
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
