"""Lifecycle service boundary tests: contexts, wire resolution, recording."""

from __future__ import annotations

import dataclasses
import datetime
import itertools
import pathlib
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

from span.core import model as m
from span.core.identity import understanding_identity
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    create_challenge,
)
from span.core.rejection import Rejection
from span.core.schema import record_wire as w
from span.service.evidence import EvidenceService
from span.service.lifecycle import LifecycleService
from span.service.support import SupportService
from span.shell.sqlite_store.lifecycle import (
    LifecycleStore,
    LifecycleStoreError,
    SourceObservationRecord,
)

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)


def _evidence(evidence_id: str = "ev-1") -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(evidence_id),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator="src/a.py",
        revision_or_fingerprint="sha256:abc",
    )


def _observation(evidence_id: str = "ev-1") -> SourceObservationRecord:
    return SourceObservationRecord(
        observation_id=m.SourceObservationId("obs-1"),
        repository_id="repo-1",
        evidence=_evidence(evidence_id),
        content_digest=m.ContentDigest("sha256:abc"),
        captured_at=NOW,
        total_lines=1,
        whole_file=True,
        excerpt="A does X",
    )


_SOURCE_CONTENT = "A does X\n"
_SOURCE_DIGEST = "abc"


class _CurrentEvidence:
    def read_exact(self, repository_id, request, _bounds):
        if request.locator != "src/a.py":
            return m.EvidenceSourceFailure(
                request,
                m.EvidenceSourceFailureKind.MISSING,
                "fixture source is missing",
            )
        return m.EvidenceUnit(
            evidence_ref=_evidence(),
            content=_SOURCE_CONTENT,
            content_fingerprint=_SOURCE_DIGEST,
        )

    def list_inventory_entries(self, repository_id, scope, fingerprint_locators=()):
        return (), {locator: _SOURCE_DIGEST for locator in fingerprint_locators}


class _Authority:
    def __init__(self) -> None:
        self.bindings = {
            "auth-1": m.AuthorityBinding(
                evidence_ref=_evidence("auth-1"),
                authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                status=m.AuthorityStatus.ACCEPTED,
            )
        }
        self.requests: list[tuple[str, str]] = []

    def resolve_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding:
        self.requests.append((repository_id, authority_ref))
        try:
            return self.bindings[authority_ref]
        except KeyError:
            raise RecordingValidationError(
                f"unknown authority reference: {authority_ref}"
            ) from None


@dataclasses.dataclass(frozen=True)
class _ConclusionSpec:
    statement: str = "A does X"
    assertion_nature: m.AssertionNature = m.AssertionNature.DESCRIPTIVE
    scope_paths: tuple[str, ...] = ("src/a.py",)
    support: tuple[w.SupportWire, ...] = (w.SourceSupportWire(locator="src/a.py"),)


def _conclusion(
    statement: str = "A does X",
    *,
    assertion_nature: m.AssertionNature = m.AssertionNature.DESCRIPTIVE,
    scope_paths: tuple[str, ...] = ("src/a.py",),
    support: tuple[w.SupportWire, ...] | None = None,
) -> _ConclusionSpec:
    return _ConclusionSpec(
        statement=statement,
        assertion_nature=assertion_nature,
        scope_paths=scope_paths,
        support=(
            support
            if support is not None
            else (w.SourceSupportWire(locator="src/a.py"),)
        ),
    )


def _context_ref(
    context_id: str | m.InvestigationContextId = "ctx-1",
) -> m.InvestigationContextRef:
    value = (
        context_id
        if isinstance(context_id, m.InvestigationContextId)
        else m.InvestigationContextId(context_id)
    )
    return m.InvestigationContextRef(repository_id="repo-1", context_id=value)


def _receipt(
    store: LifecycleStore, result: m.UnderstandingRecorded | m.VerificationRecorded
) -> m.RecordReceipt:
    selector = result.receipt_selector
    receipt = store.get_receipt(
        m.RecordingKey(
            repository_id=selector.repository_id,
            request_id=m.RequestId(selector.request_id),
        )
    )
    assert receipt is not None
    return receipt


def _create_wire(
    submission: str = "sub-create",
    *,
    conclusion: _ConclusionSpec | None = None,
) -> w.RecordRequestWire:
    spec = conclusion or _conclusion()
    return w.RecordRequestWire(
        request_id=submission,
        context=_context_ref(),
        kind=m.RecordKind.UNDERSTANDING,
        surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
        conclusion=spec.statement,
        assertion_nature=spec.assertion_nature,
        support=spec.support,
    )


class LifecycleServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = pathlib.Path(self._tmp.name) / "lifecycle.db"
        self.clock = [NOW]
        self._context_ids = itertools.count(1)
        self.store = LifecycleStore(
            self.path, retention=RETENTION, clock=lambda: self.clock[0]
        )
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", "/repo/one")
        self.authority = _Authority()
        self.support = SupportService(
            store=self.store,
            evidence=_CurrentEvidence(),
            authority=self.authority,
            clock=lambda: self.clock[0],
        )
        self.evidence_service = EvidenceService(
            store=self.store,
            evidence=_CurrentEvidence(),
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-1",
        )
        self.service = LifecycleService(
            store=self.store,
            authority=self.authority,
            support=self.support,
            evidence=self.evidence_service,
            clock=lambda: self.clock[0],
            new_context_id=lambda: f"ctx-{next(self._context_ids)}",
        )
        self.context = self.service.start_context(
            m.StartContextRequest(
                repository_id="repo-1",
                request_id=m.RequestId("req-1"),
                scope=m.EvidenceScope(paths=("src/a.py",)),
                question="What does A do?",
            )
        )
        self.store.put_source_observation(_observation())
        self.store.add_context_evidence("ctx-1", "obs-1")

    def _update(
        self,
        submission: str,
        actions: w.RecordActionsWire,
        expected: int,
        *,
        understanding_id: str = "u:sub-create",
        context_id: str | None = "ctx-1",
    ) -> m.UnderstandingRecorded:
        binding: dict[str, object] = (
            {"repository_id": "repo-1"}
            if context_id is None
            else {"context": _context_ref(context_id)}
        )
        result = self.service.record(
            w.RecordRequestWire(
                request_id=submission,
                kind=m.RecordKind.UNDERSTANDING,
                understanding_id=understanding_id,
                expected_version=expected,
                actions=actions,
                **binding,
            )
        )
        self.assertIsInstance(result, m.UnderstandingRecorded)
        return result

    def _record_add(self, expected: int, submission: str) -> m.RecordReceipt:
        return _receipt(
            self.store,
            self._update(
                submission,
                w.RecordActionsWire(
                    add=(
                        w.AddConclusionWire(
                            conclusion="Another conclusion",
                            locator="src/a.py",
                        ),
                    )
                ),
                expected,
            ),
        )

    def _version_conclusion_id(
        self, understanding_id: str, version: int, index: int = 0
    ) -> str:
        return (
            self.store.get_version(understanding_id, version)
            .conclusions[index]
            .conclusion_id.value
        )

    def _record_confirm(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return _receipt(
            self.store,
            self._update(
                submission,
                w.RecordActionsWire(
                    confirm=(
                        w.ConfirmConclusionWire(
                            conclusion_id=conclusion_id,
                            locator="src/a.py",
                        ),
                    )
                ),
                expected,
            ),
        )

    def _record_correct(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return _receipt(
            self.store,
            self._update(
                submission,
                w.RecordActionsWire(
                    correct=(
                        w.CorrectConclusionWire(
                            conclusion_id=conclusion_id,
                            conclusion="A does Y",
                            locator="src/a.py",
                        ),
                    )
                ),
                expected,
            ),
        )

    def _record_replace(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return _receipt(
            self.store,
            self._update(
                submission,
                w.RecordActionsWire(
                    replace=(
                        w.ReplaceActionWire(
                            conclusion_id=conclusion_id,
                            conclusion="A is now described by Z",
                            reason="A's behaviour changed.",
                            locator="src/a.py",
                        ),
                    )
                ),
                expected,
            ),
        )

    def _record_withdraw(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return _receipt(
            self.store,
            self._update(
                submission,
                w.RecordActionsWire(
                    withdraw=(
                        w.WithdrawActionWire(
                            conclusion_id=conclusion_id,
                            reason="withdrawn after re-check",
                        ),
                    )
                ),
                expected,
            ),
        )

    # -- contexts ----------------------------------------------------------

    def test_start_context_replays_and_rejects_changed_content(self) -> None:
        request = m.StartContextRequest(
            repository_id="repo-1",
            request_id=m.RequestId("req-1"),
            scope=m.EvidenceScope(paths=("src/a.py",)),
            question="What does A do?",
        )
        again = self.service.start_context(request)
        self.assertEqual(again.context_id, self.context.context_id)
        self.assertEqual(again.origin, m.ContextOrigin.QUESTION)
        self.assertEqual(again.expires_at, NOW + RETENTION.context_lifetime)
        with self.assertRaises(RecordingConflict):
            self.service.start_context(
                m.StartContextRequest(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-1"),
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                    question="A different question",
                )
            )

    def test_start_context_requires_registered_repository(self) -> None:
        with self.assertRaises(Exception):
            self.service.start_context(
                m.StartContextRequest(
                    repository_id="repo-unknown",
                    request_id=m.RequestId("req-2"),
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                )
            )

    def test_start_context_after_expiry_requires_new_request(self) -> None:
        self.clock[0] = NOW + RETENTION.context_lifetime + datetime.timedelta(minutes=1)
        with self.assertRaises(RecordingValidationError):
            self.service.start_context(
                m.StartContextRequest(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-1"),
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                    question="What does A do?",
                )
            )

    def test_concurrent_start_issues_one_context(self) -> None:
        second_store = LifecycleStore(
            self.path, retention=RETENTION, clock=lambda: self.clock[0]
        )
        self.addCleanup(second_store.close)
        first = LifecycleService(
            store=self.store,
            authority=self.authority,
            support=self.support,
            evidence=EvidenceService(
                store=self.store,
                evidence=_CurrentEvidence(),
                clock=lambda: self.clock[0],
            ),
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-first",
        )
        second = LifecycleService(
            store=second_store,
            authority=self.authority,
            support=self.support,
            evidence=EvidenceService(
                store=second_store,
                evidence=_CurrentEvidence(),
                clock=lambda: self.clock[0],
            ),
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-second",
        )
        request = m.StartContextRequest(
            repository_id="repo-1",
            request_id=m.RequestId("req-concurrent"),
            scope=m.EvidenceScope(paths=("src/a.py",)),
        )
        results: list[m.InvestigationContext] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def run(service: LifecycleService) -> None:
            barrier.wait()
            try:
                results.append(service.start_context(request))
            except BaseException as exc:  # noqa: BLE001 - surfaced below
                errors.append(exc)

        threads = [
            threading.Thread(target=run, args=(first,)),
            threading.Thread(target=run, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len({item.context_id.value for item in results}), 1)
        self.assertIn(results[0].context_id.value, {"ctx-first", "ctx-second"})

    # -- create ------------------------------------------------------------

    def test_create_records_and_replays(self) -> None:
        wire = _create_wire()
        receipt = _receipt(self.store, self.service.record(wire))
        self.assertEqual(
            receipt.accepted_understanding_ids,
            (
                understanding_identity(
                    m.RecordingIdentity(
                        repository_id="repo-1",
                        context_id=m.InvestigationContextId("ctx-1"),
                        request_id=m.RequestId("sub-create"),
                    )
                ),
            ),
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(receipt.replay_expires_at, NOW + RETENTION.replay_retention)
        replay = _receipt(self.store, self.service.record(wire))
        self.assertEqual(replay.committed_at, receipt.committed_at)
        with self.assertRaises(RecordingConflict):
            self.service.record(
                _create_wire(conclusion=_conclusion(statement="Different"))
            )

    def test_create_requires_admitted_source_support(self) -> None:
        unadmitted = _create_wire(
            submission="sub-unadmitted",
            conclusion=_conclusion(
                support=(w.SourceSupportWire(locator="src/missing.py"),)
            ),
        )
        with self.assertRaises(RecordingValidationError):
            self.service.record(unadmitted)
        # Membership cannot be forged for an observation that does not exist.
        with self.assertRaises(Exception):
            self.store.add_context_evidence("ctx-1", "obs-missing")

    def test_authority_reference_uses_declared_resolver(self) -> None:
        conclusion = _conclusion(
            support=(w.AuthoritySupportWire(authority_ref="auth-1"),)
        )
        receipt = _receipt(
            self.store,
            self.service.record(
                _create_wire(submission="sub-authority", conclusion=conclusion)
            ),
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(self.authority.requests, [("repo-1", "auth-1")] * 4)
        with self.assertRaises(RecordingValidationError):
            self.service.record(
                _create_wire(
                    submission="sub-authority-2",
                    conclusion=_conclusion(
                        support=(w.AuthoritySupportWire(authority_ref="auth-2"),)
                    ),
                )
            )

    def test_store_backed_authority_source(self) -> None:
        binding = m.AuthorityBinding(
            evidence_ref=_evidence("auth-ev-1"),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        self.store.register_repository(
            "repo-1", "/repo/one", authority_bindings=(binding,)
        )
        support = SupportService(
            store=self.store,
            evidence=_CurrentEvidence(),
            authority=self.store,
            clock=lambda: self.clock[0],
        )
        service = LifecycleService(
            store=self.store,
            authority=self.store,
            support=support,
            evidence=self.evidence_service,
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-2",
        )
        receipt = _receipt(
            self.store,
            service.record(
                _create_wire(
                    submission="sub-store-auth",
                    conclusion=_conclusion(
                        support=(w.AuthoritySupportWire(authority_ref="auth-ev-1"),)
                    ),
                )
            ),
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)

    def test_explicit_target_outside_context_scope_rejects(self) -> None:
        service = LifecycleService(
            store=self.store,
            authority=self.authority,
            support=self.support,
            evidence=self.evidence_service,
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-evidence",
        )
        context = service.start_context(
            m.StartContextRequest(
                repository_id="repo-1",
                request_id=m.RequestId("req-evidence"),
                scope=m.EvidenceScope(paths=("src/a.py",)),
                question=None,
            )
        )
        self.store.add_context_evidence(context.context_id.value, "obs-1")
        wire = w.RecordRequestWire(
            request_id="sub-scope",
            context=_context_ref(context.context_id.value),
            kind=m.RecordKind.UNDERSTANDING,
            surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="docs/other.md"),
            question="What is outside?",
            scope_paths=("docs/other.md",),
            conclusion="Outside scope",
            support=(w.AdmittedSourceSupportWire(observation_id="obs-1"),),
        )
        with self.assertRaises(RecordingValidationError):
            service.record(wire)

    def test_replay_survives_later_source_change(self) -> None:
        wire = _create_wire()
        receipt = _receipt(self.store, self.service.record(wire))
        # The receipt is immutable acceptance, not cached currentness.
        self.store._connection.execute(
            "UPDATE source_observations SET content_digest='sha256:changed'"
        )
        self.store._connection.commit()
        replay = _receipt(self.store, self.service.record(wire))
        self.assertEqual(replay.committed_at, receipt.committed_at)
        self.assertEqual(replay, receipt)

    # -- update chain ------------------------------------------------------

    def test_full_update_chain_preserves_history(self) -> None:
        self.service.record(_create_wire())
        target_id = self._version_conclusion_id("u:sub-create", 1)
        self.assertEqual(
            self._record_add(1, "sub-add").accepted_understanding_versions[0].value,
            2,
        )
        version_two = self.store.get_version("u:sub-create", 2)
        added_id = next(
            ref.conclusion_id.value
            for ref in version_two.conclusions
            if ref.conclusion_id.value != target_id
        )
        self.assertEqual(
            self._record_confirm(target_id, 2, "sub-confirm")
            .accepted_understanding_versions[0]
            .value,
            2,
        )
        self.assertEqual(
            self._record_correct(target_id, 2, "sub-correct")
            .accepted_understanding_versions[0]
            .value,
            3,
        )
        self.assertEqual(
            self._record_replace(target_id, 3, "sub-replace")
            .accepted_understanding_versions[0]
            .value,
            4,
        )
        version_four = self.store.get_version("u:sub-create", 4)
        replacement_id = next(
            ref.conclusion_id.value
            for ref in version_four.conclusions
            if ref.conclusion_id.value not in {target_id, added_id}
        )
        self.assertEqual(
            self._record_withdraw(replacement_id, 4, "sub-withdraw")
            .accepted_understanding_versions[0]
            .value,
            5,
        )
        version = self.store.get_version("u:sub-create", 5)
        membership = {
            (ref.conclusion_id.value, ref.revision.value) for ref in version.conclusions
        }
        self.assertEqual(membership, {(added_id, 1), (replacement_id, 2)})
        revisions = {
            (item.conclusion_id.value, item.revision.value)
            for item in self.store.get_conclusions("u:sub-create")
        }
        self.assertEqual(
            revisions,
            {
                (target_id, 1),
                (target_id, 2),
                (added_id, 1),
                (replacement_id, 1),
                (replacement_id, 2),
            },
        )

    def test_confirm_of_current_conclusion_is_a_noop(self) -> None:
        self.service.record(_create_wire())
        target_id = self._version_conclusion_id("u:sub-create", 1)
        receipt = self._record_confirm(target_id, 1, "sub-confirm")
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(
            self.store.get_understanding("u:sub-create").current_version.value,
            1,
        )

    def test_stale_expected_version_rejects_without_effect(self) -> None:
        self.service.record(_create_wire())
        self._record_add(1, "sub-add")
        with self.assertRaises(RecordingConflict):
            self._record_add(1, "sub-stale")
        self.assertEqual(
            self.store.get_understanding("u:sub-create").current_version.value,
            2,
        )

    # -- verification ------------------------------------------------------

    def test_discovery_support_requires_admission(self) -> None:
        observation = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-1"),
            repository_id="repo-1",
            scope=m.EvidenceScope(paths=("src",)),
            membership_fingerprint=(
                "sha256:" + __import__("hashlib").sha256(b"[]").hexdigest()
            ),
            captured_at=NOW,
        )
        self.store.put_discovery_observation(observation)
        conclusion = _conclusion(
            support=(w.AdmittedDiscoverySupportWire(observation_id="disc-1"),)
        )
        with self.assertRaises(RecordingValidationError):
            self.service.record(
                _create_wire(submission="sub-disc", conclusion=conclusion)
            )
        self.store.add_context_discovery_evidence("ctx-1", "disc-1")
        receipt = _receipt(
            self.store,
            self.service.record(
                _create_wire(submission="sub-disc", conclusion=conclusion)
            ),
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)

    def test_challenge_disposition_advances_revision(self) -> None:
        self.service.record(_create_wire())
        target_id = self._version_conclusion_id("u:sub-create", 1)
        self.store.create_challenge(
            create_challenge(
                challenge_id=m.ChallengeId("ch-1"),
                understanding_id=m.UnderstandingId("u:sub-create"),
                target_version=m.UnderstandingVersionNumber(1),
                target_conclusions=(
                    m.ConclusionRevisionRef(
                        understanding_id=m.UnderstandingId("u:sub-create"),
                        conclusion_id=m.ConclusionId(target_id),
                        revision=m.ConclusionRevisionNumber(1),
                    ),
                ),
                reason="the conclusion is disputed",
                evidence=(_evidence(),),
                provenance="test",
                now=NOW,
            )
        )
        result = self.service.record(
            w.RecordRequestWire(
                request_id="sub-ch",
                context=_context_ref("ctx-1"),
                kind=m.RecordKind.UNDERSTANDING,
                understanding_id="u:sub-create",
                expected_version=1,
                actions=w.RecordActionsWire(
                    confirm=(
                        w.ConfirmConclusionWire(
                            conclusion_id=target_id,
                            locator="src/a.py",
                        ),
                    )
                ),
                challenge_dispositions=(
                    w.UnresolvedDispositionWire(
                        challenge_id="ch-1",
                        expected_challenge_revision=1,
                        remaining_question="what evidence settles this?",
                        basis="the dispute remains open",
                    ),
                ),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        receipt = _receipt(self.store, result)
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 2)
        updated = self.store.get_challenge("ch-1")
        self.assertEqual(updated.challenge_revision.value, 2)
        self.assertEqual(updated.state, m.ChallengeState.UNRESOLVED)

    def test_verification_requires_admitted_observation(self) -> None:
        def wire(submission: str, observation: str) -> w.RecordRequestWire:
            return w.RecordRequestWire(
                request_id=submission,
                context=_context_ref("ctx-1"),
                kind=m.RecordKind.VERIFICATION,
                run=w.VerificationRunWire(
                    repository_id="repo-1",
                    scope_description="fixture",
                    scope_paths=("src/a.py",),
                    observations=(observation,),
                    command="python3 -m unittest",
                    scenario=None,
                    outcome=m.VerificationOutcome.PASS,
                    observed_at=NOW,
                    observer="test",
                ),
            )

        with self.assertRaises(RecordingValidationError) as raised:
            self.service.record(wire("sub-v-bad", "obs-unknown"))
        self.assertEqual(
            raised.exception.cause_kind,
            m.RejectionCauseKind.OBSERVATION_NOT_ADMITTED,
        )
        self.assertIn("locator", raised.exception.required_action)
        result = self.service.record(wire("sub-v", "obs-1"))
        assert isinstance(result, m.VerificationRecorded)
        run = self.store.get_verification_run(result.run_id.value)
        self.assertEqual(run.outcome, m.VerificationOutcome.PASS)

    def test_verification_accepts_evidence_only(self) -> None:
        wire = w.RecordRequestWire(
            request_id="sub-v-evidence",
            context=_context_ref("ctx-1"),
            kind=m.RecordKind.VERIFICATION,
            run=w.VerificationRunWire(
                repository_id="repo-1",
                scope_description="fixture",
                scope_paths=("src/a.py",),
                command="python3 -m unittest",
                scenario=None,
                outcome=m.VerificationOutcome.PASS,
                observed_at=NOW,
                observer="test",
                evidence=(w.SourceSupportWire(locator="src/a.py"),),
            ),
        )
        result = self.service.record(wire)
        assert isinstance(result, m.VerificationRecorded)
        run = self.store.get_verification_run(result.run_id.value)
        self.assertTrue(run.observations)

    def test_record_verification_accepts_evidence_only(self) -> None:
        request = w.RecordRequestWire(
            request_id="sub-v-wire",
            context=_context_ref("ctx-1"),
            kind=m.RecordKind.VERIFICATION,
            run=w.VerificationRunWire(
                repository_id="repo-1",
                scope_description="fixture",
                scope_paths=("src/a.py",),
                command="python3 -m unittest",
                scenario=None,
                outcome=m.VerificationOutcome.PASS,
                observed_at=NOW,
                observer="test",
                evidence=(w.SourceSupportWire(locator="src/a.py"),),
            ),
        )
        result = self.service.record(request)
        self.assertIsInstance(result, m.VerificationRecorded)

    # -- retention ---------------------------------------------------------

    def test_receipt_readable_after_context_expiry(self) -> None:
        receipt = _receipt(self.store, self.service.record(_create_wire()))
        self.clock[0] = NOW + RETENTION.context_lifetime + datetime.timedelta(minutes=1)
        identity = m.RecordingIdentity(
            repository_id="repo-1",
            context_id=m.InvestigationContextId("ctx-1"),
            request_id=m.RequestId("sub-create"),
        )
        self.assertEqual(self.service.receipt(identity), receipt)
        with self.assertRaises(Exception):
            self.service.record(
                _create_wire(
                    submission="sub-after-expiry",
                    conclusion=_conclusion("Later"),
                )
            )

    def test_replay_survives_context_reaping(self) -> None:
        receipt = _receipt(self.store, self.service.record(_create_wire()))
        self.clock[0] = NOW + RETENTION.context_lifetime + datetime.timedelta(minutes=1)
        self.store.reap_expired()
        self.assertIsNone(self.store.find_context_by_id("ctx-1"))
        self.assertEqual(self.store.get_receipt(receipt.identity), receipt)
        replay = _receipt(self.store, self.service.record(_create_wire()))
        self.assertEqual(replay, receipt)

    # -- context-free recording (L2 §4.2) --------------------------------

    def _service(self, context_id: str) -> LifecycleService:
        return LifecycleService(
            store=self.store,
            authority=self.authority,
            support=self.support,
            evidence=self.evidence_service,
            clock=lambda: self.clock[0],
            new_context_id=lambda: context_id,
        )

    def _context_free_create(self, submission: str = "sub-nc") -> w.RecordRequestWire:
        return w.RecordRequestWire(
            repository_id="repo-1",
            request_id=submission,
            kind=m.RecordKind.UNDERSTANDING,
            surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
            question="What does A do?",
            scope_paths=("src/a.py",),
            conclusion="A does X",
            locator="src/a.py",
        )

    def test_create_without_context_issues_one_internally(self) -> None:
        wire = self._context_free_create()
        receipt = _receipt(self.store, self._service("ctx-issued").record(wire))
        self.assertEqual(receipt.identity.context_id.value, "ctx-issued")
        self.assertEqual(receipt.accepted_understanding_ids[0].value, "u:sub-nc")
        context = self.store.find_context_by_id("ctx-issued")
        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.origin, m.ContextOrigin.EVIDENCE_ONLY)
        self.assertIn("src/a.py", context.scope.paths)
        self.assertEqual(
            _receipt(self.store, self._service("ctx-unused").record(wire)), receipt
        )

    def test_create_with_support_only_derives_scope_from_context(self) -> None:
        result = self.service.record(
            w.RecordRequestWire(
                request_id="sub-support-only",
                context=_context_ref("ctx-1"),
                kind=m.RecordKind.UNDERSTANDING,
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion="A is supported by the source.",
                support=(w.SourceSupportWire(locator="src/a.py"),),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        understanding_id = result.understanding_id.value
        target_id = self._version_conclusion_id(understanding_id, 1)
        revision = next(
            item
            for item in self.store.get_conclusions(understanding_id)
            if item.conclusion_id.value == target_id
        )
        assert isinstance(revision.content, m.SupportedConclusion)
        self.assertEqual(revision.content.scope.paths, ("src/a.py",))
        self.assertTrue(revision.content.support)

    def test_create_with_support_and_no_surface_derives_scope_from_context(
        self,
    ) -> None:
        result = self.service.record(
            w.RecordRequestWire(
                request_id="sub-support-only-no-surface",
                context=_context_ref("ctx-1"),
                kind=m.RecordKind.UNDERSTANDING,
                conclusion="A is supported by the source.",
                support=(w.SourceSupportWire(locator="src/a.py"),),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        understanding_id = result.understanding_id.value
        understanding = self.store.get_understanding(understanding_id)
        self.assertEqual(understanding.scope.paths, ("src/a.py",))
        target_id = self._version_conclusion_id(understanding_id, 1)
        revision = next(
            item
            for item in self.store.get_conclusions(understanding_id)
            if item.conclusion_id.value == target_id
        )
        assert isinstance(revision.content, m.SupportedConclusion)
        self.assertEqual(revision.content.scope.paths, ("src/a.py",))

    def test_create_without_context_or_question_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "question or context"):
            w.RecordRequestWire(
                repository_id="repo-1",
                request_id="sub-bound",
                kind=m.RecordKind.UNDERSTANDING,
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion="A does X",
                locator="src/a.py",
            )

    def test_update_without_context_reuses_the_understanding_scope(self) -> None:
        self.service.record(_create_wire())
        result = self._service("ctx-update").record(
            w.RecordRequestWire(
                repository_id="repo-1",
                request_id="sub-add-nc",
                kind=m.RecordKind.UNDERSTANDING,
                understanding_id="u:sub-create",
                expected_version=1,
                actions=w.RecordActionsWire(
                    add=(
                        w.AddConclusionWire(
                            conclusion="Another conclusion",
                            locator="src/a.py",
                        ),
                    )
                ),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        self.assertEqual(result.version.value, 2)
        context = self.store.find_context_by_id("ctx-update")
        self.assertIsNotNone(context)
        assert context is not None
        self.assertIn("src/a.py", context.scope.paths)

    # -- FD-37 premise effects --------------------------------------------

    def test_correct_names_the_affected_dependent(self) -> None:
        self.service.record(_create_wire())
        target_id = self._version_conclusion_id("u:sub-create", 1)
        dependent_context = m.InvestigationContext(
            context_id=m.InvestigationContextId("ctx-dep"),
            repository_id="repo-1",
            request_id=m.RequestId("req-dep"),
            request_digest=m.ContentDigest("sha256:dep"),
            origin=m.ContextOrigin.EVIDENCE_ONLY,
            state=m.ContextState.LIVE,
            scope=m.EvidenceScope(paths=("src/b.py",)),
            created_at=NOW,
            expires_at=NOW + RETENTION.context_lifetime,
        )
        self.store.put_context(dependent_context)
        base = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u:sub-create"),
            conclusion_id=m.ConclusionId(target_id),
            revision=m.ConclusionRevisionNumber(1),
        )
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    request_id=m.RequestId("sub-dependent"),
                    context_id=dependent_context.context_id,
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/b.py",
                ),
                target=m.ExplicitTarget(
                    question="What does B do?",
                    scope=m.EvidenceScope(paths=("src/b.py",)),
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="B relies on A.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/b.py",)),
                        support=(m.PremiseSupport(premise=base),),
                        basis=m.SemanticBasis(
                            derivation=m.DerivationKind.DERIVED_JOIN,
                            summary="joined premise",
                            input_refs=(),
                        ),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u:dependent"),
        )
        receipt = self._record_correct(target_id, 1, "sub-correct-deps")
        self.assertEqual(
            receipt.dependent_effects,
            (
                m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u:dependent"),
                    conclusion_id=m.ConclusionId("c-1"),
                    revision=m.ConclusionRevisionNumber(1),
                ),
            ),
        )

        # A confirming or additive transition invalidates no premise.
        add = self._record_add(2, "sub-add-after-correct")
        self.assertEqual(add.dependent_effects, ())

    # -- retention policy --------------------------------------------------

    def test_retention_policy_validation(self) -> None:
        with self.assertRaises(ValueError):
            m.LifecycleRetention(
                context_lifetime=datetime.timedelta(0),
                replay_retention=datetime.timedelta(hours=1),
            )
        with self.assertRaises(ValueError):
            m.LifecycleRetention(
                context_lifetime=datetime.timedelta(hours=2),
                replay_retention=datetime.timedelta(hours=1),
            )

    # -- one public record entry ------------------------------------------

    def _record_request(
        self,
        submission: str,
        *,
        context_id: str | None = None,
        surface: w.SurfaceWire | None = None,
        actions: w.RecordActionsWire | None = None,
        kind: m.RecordKind = m.RecordKind.UNDERSTANDING,
        action: m.SurfaceAction | None = None,
        question: str | None = "What does A do?",
        understanding_id: str | None = None,
        expected_version: int | None = None,
        expected_boundary_version: int | None = None,
        run: w.VerificationRunWire | None = None,
        challenge_dispositions: tuple[w.DispositionWire, ...] = (),
        scope_paths: tuple[str, ...] = ("src/a.py",),
        conclusion: _ConclusionSpec | None = None,
    ) -> w.RecordRequestWire:
        # This helper builds valid requests for each kind; the wire-level
        # fail-closed cases live in test_record_wire.py.
        if kind is not m.RecordKind.UNDERSTANDING or actions is not None:
            question = None
            scope_paths = ()
        flat: dict[str, object] = {}
        if conclusion is not None:
            admitted = [
                item
                for item in conclusion.support
                if isinstance(item, w.AdmittedSourceSupportWire)
            ]
            observation = (
                admitted[0].observation_id
                if len(admitted) == 1 and len(conclusion.support) == 1
                else None
            )
            support = () if observation is not None else conclusion.support
            locator = (
                conclusion.scope_paths[0]
                if observation is None and not support and conclusion.scope_paths
                else None
            )
            if context_id is not None and question is None:
                scope_paths = ()
            flat = {
                "conclusion": conclusion.statement,
                "assertion_nature": conclusion.assertion_nature,
                "locator": locator,
                "observation_id": observation,
                "support": support,
            }
        binding: dict[str, object] = (
            {"repository_id": "repo-1"}
            if context_id is None
            else {"context": _context_ref(context_id)}
        )
        return w.RecordRequestWire(
            request_id=submission,
            kind=kind,
            surface=surface,
            question=question,
            scope_paths=scope_paths,
            understanding_id=understanding_id,
            expected_version=expected_version,
            actions=actions,
            action=action,
            expected_boundary_version=expected_boundary_version,
            run=run,
            challenge_dispositions=challenge_dispositions,
            **binding,
            **flat,
        )

    def test_record_create_through_the_one_request(self) -> None:
        result = self.service.record(
            self._record_request(
                "sub-one-create",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        self.assertIsInstance(result, m.UnderstandingRecorded)
        assert isinstance(result, m.UnderstandingRecorded)
        self.assertEqual(result.qualification.state, m.SupportState.CURRENT)

    def test_record_create_accepts_a_question_context_without_reauthoring(
        self,
    ) -> None:
        result = self.service.record(
            self._record_request(
                "sub-context-bound-create",
                context_id="ctx-1",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                question=None,
                scope_paths=(),
                conclusion=_conclusion(),
            )
        )
        self.assertIsInstance(result, m.UnderstandingRecorded)
        assert isinstance(result, m.UnderstandingRecorded)
        self.assertEqual(result.qualification.state, m.SupportState.CURRENT)

    def test_context_bound_create_rejects_an_explicit_target(self) -> None:
        with self.assertRaises(Rejection) as raised:
            self.service.record(
                self._record_request(
                    "sub-context-bound-conflict",
                    context_id="ctx-1",
                    surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                    question="What does A do?",
                    scope_paths=(),
                    conclusion=_conclusion(),
                )
            )
        self.assertIs(
            raised.exception.cause_kind,
            m.RejectionCauseKind.CONTEXT_TARGET_CONFLICT,
        )

    def test_record_create_without_question_or_context_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "question or context"):
            self._record_request(
                "sub-unbound-create",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                question=None,
                conclusion=_conclusion(),
            )

    def test_create_without_surface_derives_from_one_scope_path(self) -> None:
        result = self.service.record(
            self._record_request(
                "sub-derived-surface",
                surface=None,
                question="What does A do?",
                scope_paths=("src/a.py",),
                conclusion=_conclusion(),
            )
        )
        self.assertIsInstance(result, m.UnderstandingRecorded)
        understanding = self.store.get_understanding("u:sub-derived-surface")
        self.assertEqual(understanding.surface.locator, "src/a.py")

    def test_create_without_surface_uses_the_question_context_scope(self) -> None:
        result = self.service.record(
            self._record_request(
                "sub-context-surface",
                context_id="ctx-1",
                surface=None,
                question=None,
                scope_paths=(),
                conclusion=_conclusion(),
            )
        )
        self.assertIsInstance(result, m.UnderstandingRecorded)
        understanding = self.store.get_understanding("u:sub-context-surface")
        self.assertEqual(understanding.surface.locator, "src/a.py")

    def test_create_without_surface_rejects_multiple_paths(self) -> None:
        with self.assertRaises(Rejection) as raised:
            self.service.record(
                self._record_request(
                    "sub-ambiguous-surface",
                    surface=None,
                    question="What does A do?",
                    scope_paths=("src/a.py", "src/b.py"),
                    conclusion=_conclusion(),
                )
            )
        self.assertIs(
            raised.exception.cause_kind,
            m.RejectionCauseKind.SURFACE_AMBIGUOUS,
        )

    def test_create_surface_must_agree_with_the_carried_scope(self) -> None:
        with self.assertRaises(Rejection) as raised:
            self.service.record(
                self._record_request(
                    "sub-mismatched-surface",
                    surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/b.py"),
                    question="What does A do?",
                    scope_paths=("src/a.py",),
                    conclusion=_conclusion(),
                )
            )
        self.assertIs(
            raised.exception.cause_kind,
            m.RejectionCauseKind.SURFACE_MISMATCH,
        )

    def test_surface_declaration_create_and_update(self) -> None:
        created = self.service.record(
            self._record_request(
                "surface-create",
                kind=m.RecordKind.SURFACE,
                action=m.SurfaceAction.CREATE,
                question=None,
                surface=w.SurfaceWire(
                    kind=m.SurfaceKind.SERVICE,
                    locator="billing",
                    boundary=w.SurfaceBoundaryWire(paths=("src",)),
                ),
            )
        )
        self.assertIsInstance(created, m.SurfaceDeclared)
        assert isinstance(created, m.SurfaceDeclared)
        self.assertEqual(created.surface.boundary_version, 1)

        updated = self.service.record(
            self._record_request(
                "surface-update",
                kind=m.RecordKind.SURFACE,
                action=m.SurfaceAction.UPDATE,
                question=None,
                expected_boundary_version=1,
                surface=w.SurfaceWire(
                    kind=m.SurfaceKind.SERVICE,
                    locator="billing",
                    boundary=w.SurfaceBoundaryWire(paths=("src", "tests")),
                ),
            )
        )
        self.assertIsInstance(updated, m.SurfaceDeclared)
        assert isinstance(updated, m.SurfaceDeclared)
        self.assertEqual(updated.surface.boundary_version, 2)
        self.assertEqual(updated.surface.boundary.paths, ("src", "tests"))

    def test_discovery_boundary_is_observed_inside_record(self) -> None:
        result = self.service.record(
            self._record_request(
                "sub-discovery",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion=_conclusion(
                    support=(
                        w.DiscoveryBoundarySupportWire(
                            scope=w.DiscoveryScopeWire(paths=("src",))
                        ),
                    )
                ),
            )
        )
        self.assertIsInstance(result, m.UnderstandingRecorded)
        observations = self.store.list_discovery_observations("repo-1")
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].scope.paths, ("src",))

    def test_record_update_through_actions(self) -> None:
        created = self.service.record(
            self._record_request(
                "sub-one-create",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.understanding_id.value
        target_id = self._version_conclusion_id(understanding_id, 1)

        updated = self.service.record(
            self._record_request(
                "sub-one-update",
                actions=w.RecordActionsWire(
                    correct=(
                        w.CorrectConclusionWire(
                            conclusion_id=target_id,
                            conclusion="A still does X, corrected.",
                            locator="src/a.py",
                        ),
                    )
                ),
                question=None,
                understanding_id=understanding_id,
                expected_version=1,
            )
        )
        self.assertIsInstance(updated, m.UnderstandingRecorded)
        assert isinstance(updated, m.UnderstandingRecorded)
        self.assertEqual(updated.version.value, 2)

    def test_record_verification_through_kind(self) -> None:
        result = self.service.record(
            self._record_request(
                "sub-verify",
                context_id="ctx-1",
                kind=m.RecordKind.VERIFICATION,
                question=None,
                run=w.VerificationRunWire(
                    repository_id="repo-1",
                    scope_description="unit",
                    scope_paths=("src/a.py",),
                    observations=("obs-1",),
                    command="pytest -q",
                    scenario=None,
                    outcome=m.VerificationOutcome.PASS,
                    observed_at=NOW,
                    observer="tester",
                ),
            )
        )
        self.assertIsInstance(result, m.VerificationRecorded)
        assert isinstance(result, m.VerificationRecorded)
        self.assertEqual(result.outcome, m.VerificationOutcome.PASS)

    def test_record_actions_apply_atomically(self) -> None:
        created = self.service.record(
            self._record_request(
                "sub-atomic-create",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.understanding_id.value
        target_id = self._version_conclusion_id(understanding_id, 1)
        updated = self.service.record(
            self._record_request(
                "sub-atomic-update",
                understanding_id=understanding_id,
                expected_version=1,
                question=None,
                actions=w.RecordActionsWire(
                    add=(
                        w.AddConclusionWire(
                            conclusion="A also emits line2.",
                            locator="src/a.py",
                        ),
                    ),
                    correct=(
                        w.CorrectConclusionWire(
                            conclusion_id=target_id,
                            conclusion="A emits line1 first.",
                            locator="src/a.py",
                        ),
                    ),
                ),
            )
        )
        assert isinstance(updated, m.UnderstandingRecorded)
        version = self.store.get_version(understanding_id, 2)
        added_id = next(
            ref.conclusion_id.value
            for ref in version.conclusions
            if ref.conclusion_id.value != target_id
        )
        self.assertEqual(
            {ref.conclusion_id.value for ref in version.conclusions},
            {target_id, added_id},
        )
        revisions = {
            (item.conclusion_id.value, item.revision.value): item
            for item in self.store.get_conclusions(understanding_id)
        }
        self.assertEqual(
            revisions[(target_id, 2)].content.statement, "A emits line1 first."
        )

    def test_replay_and_new_request_derive_add_identity_consistently(self) -> None:
        self.service.record(_create_wire())
        target_id = self._version_conclusion_id("u:sub-create", 1)
        first = self._record_add(1, "sub-add-derived")
        version_two = self.store.get_version("u:sub-create", 2)
        first_id = next(
            ref.conclusion_id.value
            for ref in version_two.conclusions
            if ref.conclusion_id.value != target_id
        )
        replay = self._record_add(1, "sub-add-derived")
        self.assertEqual(replay, first)
        self.assertEqual(
            self.store.get_understanding("u:sub-create").current_version.value, 2
        )
        self._record_add(2, "sub-add-derived-2")
        version_three = self.store.get_version("u:sub-create", 3)
        new_ids = {
            ref.conclusion_id.value
            for ref in version_three.conclusions
            if ref.conclusion_id.value != target_id
        }
        self.assertEqual(len(new_ids), 2)
        self.assertIn(first_id, new_ids)

    def test_record_actions_replace_and_withdraw(self) -> None:
        created = self.service.record(
            self._record_request(
                "sub-replace-create",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.understanding_id.value
        target_id = self._version_conclusion_id(understanding_id, 1)

        replaced = self.service.record(
            self._record_request(
                "sub-replace-through-actions",
                understanding_id=understanding_id,
                expected_version=1,
                question=None,
                actions=w.RecordActionsWire(
                    replace=(
                        w.ReplaceActionWire(
                            conclusion_id=target_id,
                            conclusion="A is now described by Z",
                            reason="A's behaviour changed.",
                            locator="src/a.py",
                        ),
                    )
                ),
            )
        )
        assert isinstance(replaced, m.UnderstandingRecorded)
        self.assertEqual(replaced.version.value, 2)
        replaced_version = self.store.get_version(understanding_id, 2)
        new_id = next(ref.conclusion_id.value for ref in replaced_version.conclusions)
        self.assertEqual(
            {ref.conclusion_id.value for ref in replaced_version.conclusions},
            {new_id},
        )

        withdrawn = self.service.record(
            self._record_request(
                "sub-withdraw-through-actions",
                understanding_id=understanding_id,
                expected_version=2,
                question=None,
                actions=w.RecordActionsWire(
                    withdraw=(
                        w.WithdrawActionWire(
                            conclusion_id=new_id,
                            reason="withdrawn after re-check",
                        ),
                    )
                ),
            )
        )
        assert isinstance(withdrawn, m.UnderstandingRecorded)
        self.assertEqual(withdrawn.version.value, 3)
        version = self.store.get_version(understanding_id, 3)
        self.assertEqual(
            {
                (ref.conclusion_id.value, ref.revision.value)
                for ref in version.conclusions
            },
            {(new_id, 2)},
        )
        withdrawn_revision = next(
            item
            for item in self.store.get_conclusions(understanding_id)
            if item.conclusion_id.value == new_id and item.revision.value == 2
        )
        self.assertIsInstance(withdrawn_revision.content, m.WithdrawnConclusion)

    def test_record_settles_a_challenge_through_dispositions(self) -> None:
        created = self.service.record(
            self._record_request(
                "sub-challenge-create",
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.understanding_id.value
        target_id = self._version_conclusion_id(understanding_id, 1)
        self.store.create_challenge(
            create_challenge(
                challenge_id=m.ChallengeId("ch-1"),
                understanding_id=m.UnderstandingId(understanding_id),
                target_version=m.UnderstandingVersionNumber(1),
                target_conclusions=(
                    m.ConclusionRevisionRef(
                        understanding_id=m.UnderstandingId(understanding_id),
                        conclusion_id=m.ConclusionId(target_id),
                        revision=m.ConclusionRevisionNumber(1),
                    ),
                ),
                reason="the conclusion is disputed",
                evidence=(_evidence(),),
                provenance="test",
                now=NOW,
            )
        )

        settled = self.service.record(
            self._record_request(
                "sub-challenge-settle",
                understanding_id=understanding_id,
                expected_version=1,
                question=None,
                actions=w.RecordActionsWire(
                    confirm=(
                        w.ConfirmConclusionWire(
                            conclusion_id=target_id,
                            locator="src/a.py",
                        ),
                    )
                ),
                challenge_dispositions=(
                    w.UnresolvedDispositionWire(
                        challenge_id="ch-1",
                        expected_challenge_revision=1,
                        remaining_question="what evidence settles this?",
                        basis="the dispute remains open",
                    ),
                ),
            )
        )
        assert isinstance(settled, m.UnderstandingRecorded)
        self.assertEqual(settled.version.value, 2)
        updated = self.store.get_challenge("ch-1")
        self.assertEqual(updated.challenge_revision.value, 2)
        self.assertEqual(updated.state, m.ChallengeState.UNRESOLVED)

    def test_record_accepts_every_support_kind(self) -> None:
        context = self.service.start_context(
            m.StartContextRequest(
                repository_id="repo-1",
                request_id=m.RequestId("req-support-context"),
                scope=m.EvidenceScope(paths=("src",)),
                question=None,
            )
        )
        context_id = context.context_id.value
        self.store.add_context_evidence(context_id, "obs-1")
        base = self.service.record(
            self._record_request(
                "sub-support-base",
                context_id=context_id,
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(base, m.UnderstandingRecorded)
        base_id = base.understanding_id.value
        base_target_id = self._version_conclusion_id(base_id, 1)

        observation = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-1"),
            repository_id="repo-1",
            scope=m.EvidenceScope(paths=("src",)),
            membership_fingerprint=(
                "sha256:" + __import__("hashlib").sha256(b"[]").hexdigest()
            ),
            captured_at=NOW,
        )
        self.store.put_discovery_observation(observation)
        self.store.add_context_discovery_evidence(context_id, "disc-1")

        support = (
            w.SourceSupportWire(locator="src/a.py"),
            w.AdmittedSourceSupportWire(observation_id="obs-1"),
            w.AuthoritySupportWire(authority_ref="auth-1"),
            w.PremiseSupportWire(
                understanding_id=base_id,
                conclusion_id=base_target_id,
                revision=1,
            ),
            w.DiscoveryBoundarySupportWire(scope=w.DiscoveryScopeWire(paths=("src",))),
            w.AdmittedDiscoverySupportWire(observation_id="disc-1"),
        )
        result = self.service.record(
            self._record_request(
                "sub-support-union",
                context_id=context_id,
                surface=w.SurfaceWire(kind=m.SurfaceKind.SYMBOL, locator="src/a.py::A"),
                question="What supports A?",
                scope_paths=("src/a.py::A",),
                conclusion=_conclusion(
                    "A is supported by every form.",
                    scope_paths=("src/a.py::A",),
                    support=support,
                ),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        understanding_id = result.understanding_id.value
        new_target_id = self._version_conclusion_id(understanding_id, 1)
        revision = next(
            item
            for item in self.store.get_conclusions(understanding_id)
            if item.conclusion_id.value == new_target_id and item.revision.value == 1
        )
        assert isinstance(revision.content, m.SupportedConclusion)
        kinds = [type(item) for item in revision.content.support]
        self.assertEqual(kinds.count(m.SourceSupport), 2)
        self.assertEqual(kinds.count(m.AuthoritySupportDependency), 1)
        self.assertEqual(kinds.count(m.PremiseSupport), 1)
        self.assertEqual(kinds.count(m.DiscoverySupport), 2)

    # -- surface declaration validation -----------------------------------

    def _declare_surface(
        self,
        submission: str,
        kind: m.SurfaceKind,
        locator: str,
        *,
        boundary: tuple[str, ...] | None = ("src",),
        parent: tuple[m.SurfaceKind, str] | None = None,
        action: m.SurfaceAction = m.SurfaceAction.CREATE,
        expected: int | None = None,
    ) -> m.RecordResult:
        return self.service.record(
            self._record_request(
                submission,
                kind=m.RecordKind.SURFACE,
                action=action,
                question=None,
                expected_boundary_version=expected,
                surface=w.SurfaceWire(
                    kind=kind,
                    locator=locator,
                    boundary=(
                        None
                        if boundary is None
                        else w.SurfaceBoundaryWire(paths=boundary)
                    ),
                    parent=(
                        None
                        if parent is None
                        else w.SurfaceKeyWire(kind=parent[0], locator=parent[1])
                    ),
                ),
            )
        )

    def test_surface_create_rejects_an_unknown_parent(self) -> None:
        with self.assertRaisesRegex(RecordingValidationError, "unknown parent surface"):
            self._declare_surface(
                "surface-unknown-parent",
                m.SurfaceKind.SERVICE,
                "billing",
                parent=(m.SurfaceKind.DOMAIN, "missing"),
            )

    def test_surface_create_rejects_self_parenting(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be its own parent"):
            self._declare_surface(
                "surface-self-parent",
                m.SurfaceKind.SERVICE,
                "billing",
                parent=(m.SurfaceKind.SERVICE, "billing"),
            )

    def test_surface_update_rejects_a_parent_cycle(self) -> None:
        self.assertIsInstance(
            self._declare_surface("surface-domain", m.SurfaceKind.DOMAIN, "platform"),
            m.SurfaceDeclared,
        )
        self.assertIsInstance(
            self._declare_surface(
                "surface-service",
                m.SurfaceKind.SERVICE,
                "billing",
                parent=(m.SurfaceKind.DOMAIN, "platform"),
            ),
            m.SurfaceDeclared,
        )
        with self.assertRaisesRegex(RecordingValidationError, "cycle"):
            self._declare_surface(
                "surface-cycle",
                m.SurfaceKind.DOMAIN,
                "platform",
                parent=(m.SurfaceKind.SERVICE, "billing"),
                action=m.SurfaceAction.UPDATE,
                expected=1,
            )

    def test_surface_update_stale_boundary_returns_rejected(self) -> None:
        self.assertIsInstance(
            self._declare_surface(
                "surface-cas-create", m.SurfaceKind.SERVICE, "billing"
            ),
            m.SurfaceDeclared,
        )
        with self.assertRaises(Rejection) as raised:
            self._declare_surface(
                "surface-cas-update",
                m.SurfaceKind.SERVICE,
                "billing",
                boundary=("src", "tests"),
                action=m.SurfaceAction.UPDATE,
                expected=5,
            )
        self.assertIs(
            raised.exception.cause_kind,
            m.RejectionCauseKind.SURFACE_CONFLICT,
        )
        self.assertEqual(raised.exception.current_boundary_version, 1)

    def test_surface_kind_conflict_returns_rejected(self) -> None:
        self.assertIsInstance(
            self._declare_surface(
                "surface-kind-create", m.SurfaceKind.SERVICE, "billing"
            ),
            m.SurfaceDeclared,
        )
        with self.assertRaises(Rejection) as raised:
            self._declare_surface(
                "surface-kind-conflict", m.SurfaceKind.DOMAIN, "billing"
            )
        self.assertIs(
            raised.exception.cause_kind,
            m.RejectionCauseKind.SURFACE_CONFLICT,
        )
        self.assertEqual(raised.exception.current_boundary_version, 1)

    def test_surface_parent_must_be_declared(self) -> None:
        self.store.put_surface(
            m.Surface(
                key=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/a.py",
                ),
                boundary=m.SurfaceBoundary(paths=("src/a.py",)),
            )
        )
        with self.assertRaisesRegex(
            RecordingValidationError, "declared service or domain"
        ):
            self._declare_surface(
                "surface-file-parent",
                m.SurfaceKind.SERVICE,
                "billing",
                parent=(m.SurfaceKind.FILE, "src/a.py"),
            )

    def test_path_surface_declaration_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "path surfaces are derived, not declared"
        ):
            self._declare_surface(
                "surface-file-boundary", m.SurfaceKind.FILE, "src/a.py"
            )

    def test_declared_surface_requires_a_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "service surface boundary requires"):
            self._declare_surface(
                "surface-no-boundary",
                m.SurfaceKind.SERVICE,
                "billing",
                boundary=None,
            )

    def test_surface_create_with_a_changed_boundary_is_rejected(self) -> None:
        self.assertIsInstance(
            self._declare_surface(
                "surface-dup-create", m.SurfaceKind.SERVICE, "billing"
            ),
            m.SurfaceDeclared,
        )
        with self.assertRaises(Rejection) as raised:
            self._declare_surface(
                "surface-dup-boundary",
                m.SurfaceKind.SERVICE,
                "billing",
                boundary=("src", "tests"),
            )
        self.assertIs(
            raised.exception.cause_kind,
            m.RejectionCauseKind.SURFACE_CONFLICT,
        )
        self.assertEqual(raised.exception.current_boundary_version, 1)

    def _scope_create(self, request="scope-create", **kwargs):
        return w.RecordRequestWire(
            repository_id="repo-1",
            request_id=request,
            kind=m.RecordKind.UNDERSTANDING,
            question="What is established?",
            conclusion="The scoped statement holds.",
            **kwargs,
        )

    def _assert_scopes(self, result, scope, locator):
        self.assertIsInstance(result, m.UnderstandingRecorded)
        uid = result.understanding_id.value
        understanding = self.store.get_understanding(uid)
        version = self.store.get_version(uid, 1)
        conclusion = self.store.get_version_conclusions(uid, 1)[0]
        self.assertEqual(understanding.scope, scope)
        self.assertEqual(version.scope, scope)
        self.assertEqual(conclusion.content.scope, scope)
        self.assertEqual(understanding.surface.locator, locator)
        self.assertIsInstance(result.status, m.SurfaceStatus)
        self.assertEqual(result.status.surface, understanding.surface)
        return uid

    def test_scope_create_forms_preserve_target_version_and_conclusion(self):
        forms = (
            {
                "scope_paths": ("src/a.py",),
                "support": (w.SourceSupportWire(locator="src/a.py"),),
            },
            {"locator": "src/a.py"},
            {
                "surface": w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                "support": (w.SourceSupportWire(locator="src/a.py"),),
            },
        )
        for index, form in enumerate(forms):
            with self.subTest(form=form):
                wire = self._scope_create(f"form-{index}", **form)
                wire = dataclasses.replace(wire, question=f"question {index}")
                result = self.service.record(wire)
                self._assert_scopes(
                    result, m.EvidenceScope(paths=("src/a.py",)), "src/a.py"
                )

    def test_multi_source_support_keeps_plan_semantic_scope(self):
        wire = self._scope_create(
            scope_paths=("docs/plan.md",),
            support=(
                w.SourceSupportWire(locator="src/a.py"),
                w.DiscoveryBoundarySupportWire(
                    scope=w.DiscoveryScopeWire(paths=("src",))
                ),
            ),
        )
        result = self.service.record(wire)
        self._assert_scopes(
            result, m.EvidenceScope(paths=("docs/plan.md",)), "docs/plan.md"
        )

    def test_repository_discovery_broadens_context_but_not_semantic_scope(self):
        wire = self._scope_create(
            scope_paths=("docs/plan.md",),
            support=(w.DiscoveryBoundarySupportWire(scope=w.DiscoveryScopeWire()),),
        )
        result = self.service.record(wire)
        self._assert_scopes(
            result, m.EvidenceScope(paths=("docs/plan.md",)), "docs/plan.md"
        )
        observation = self.store.list_discovery_observations("repo-1")[0]
        self.assertEqual(observation.scope, m.EvidenceScope())
        identity_context = self.store.get_context(
            _receipt(self.store, result).identity.context_id.value
        )
        self.assertEqual(identity_context.scope, m.EvidenceScope())

    def test_context_free_discovery_refs_reject_before_context_creation(self):
        wire = self._scope_create(
            scope_paths=("docs/plan.md",),
            support=(
                w.DiscoveryBoundarySupportWire(
                    scope=w.DiscoveryScopeWire(evidence_refs=("ev-1",))
                ),
            ),
        )
        with mock.patch.object(
            self.store, "resolve_context", wraps=self.store.resolve_context
        ) as issue:
            with self.assertRaises(RecordingValidationError) as raised:
                self.service.record(wire)
            self.assertEqual(
                raised.exception.cause_kind, m.RejectionCauseKind.CONTEXT_REQUIRED
            )
            self.assertIn("context that admitted", raised.exception.required_action)
            issue.assert_not_called()

    def test_discovery_scope_guard_runs_before_inventory(self):
        cases = (
            (("src",), ("src/service",), True),
            (("src/service",), ("src",), False),
            (("docs",), ("ui",), False),
            (("src",), (), False),
            ((), (), True),
            ((), ("src",), True),
        )
        for index, (outer, inner, accepted) in enumerate(cases):
            with self.subTest(outer=outer, inner=inner):
                context = self.service.start_context(
                    m.StartContextRequest(
                        repository_id="repo-1",
                        request_id=m.RequestId(f"discovery-{index}"),
                        scope=m.EvidenceScope(paths=outer),
                    )
                )
                with mock.patch.object(
                    self.evidence_service, "inventory_entries", return_value=()
                ) as inventory:
                    if accepted:
                        self.service._admit_discovery(
                            "repo-1",
                            context.context_id.value,
                            m.EvidenceScope(paths=inner),
                        )
                        inventory.assert_called_once()
                    else:
                        with self.assertRaises(RecordingValidationError) as raised:
                            self.service._admit_discovery(
                                "repo-1",
                                context.context_id.value,
                                m.EvidenceScope(paths=inner),
                            )
                        self.assertEqual(
                            raised.exception.cause_kind,
                            m.RejectionCauseKind.CONTEXT_SCOPE_CONFLICT,
                        )
                        inventory.assert_not_called()
                self.assertEqual(
                    self.store.get_context(context.context_id.value).scope,
                    context.scope,
                )

    def test_source_scope_guard_allows_new_members_and_unrestricted_context(self):
        for index, paths in enumerate((("src",), (), ("docs",))):
            with self.subTest(paths=paths):
                context = self.service.start_context(
                    m.StartContextRequest(
                        repository_id="repo-1",
                        request_id=m.RequestId(f"source-{index}"),
                        scope=m.EvidenceScope(paths=paths),
                    )
                )
                if paths == ("docs",):
                    with mock.patch.object(self.evidence_service, "admit") as admit:
                        with self.assertRaises(RecordingValidationError) as raised:
                            self.service._admit_source(
                                "repo-1", context.context_id.value, "src/a.py", ()
                            )
                        self.assertEqual(
                            raised.exception.cause_kind,
                            m.RejectionCauseKind.CONTEXT_SCOPE_CONFLICT,
                        )
                        admit.assert_not_called()
                else:
                    obs = self.service._admit_source(
                        "repo-1", context.context_id.value, "src/a.py", ()
                    )
                    self.assertTrue(
                        self.store.has_admitted_observation(
                            context.context_id.value, obs.value
                        )
                    )

    def test_context_binding_conflict_has_identity_recovery(self):
        with self.assertRaises(RecordingConflict) as raised:
            self.service.start_context(
                m.StartContextRequest(
                    repository_id="repo-1",
                    request_id=m.RequestId("req-1"),
                    scope=m.EvidenceScope(paths=("different",)),
                    question="Different?",
                )
            )
        self.assertEqual(
            raised.exception.cause_kind, m.RejectionCauseKind.CONTEXT_BINDING_CONFLICT
        )
        self.assertIn("original content", raised.exception.required_action)
        self.assertNotIn("version", raised.exception.required_action)

    def test_context_free_exact_replay_skips_context_and_admission_after_reap(self):
        wire = self._scope_create(locator="src/a.py")
        original = self.service.record(wire)
        self.clock[0] += datetime.timedelta(hours=2)
        self.store.reap_expired()
        with (
            mock.patch.object(
                self.service,
                "_resolve_record_request",
                side_effect=AssertionError("context derivation"),
            ),
            mock.patch.object(
                self.service, "_admit_source", side_effect=AssertionError("admission")
            ),
        ):
            replay = self.service.record(wire)
            self.assertEqual(
                _receipt(self.store, replay), _receipt(self.store, original)
            )
            with self.assertRaises(RecordingConflict) as raised:
                self.service.record(dataclasses.replace(wire, conclusion="Changed"))
            self.assertEqual(
                raised.exception.cause_kind, m.RejectionCauseKind.REPLAY_CONFLICT
            )

    def test_precommit_changed_request_is_binding_conflict(self):
        wire = self._scope_create(locator="missing.py")
        with self.assertRaises(RecordingValidationError):
            self.service.record(wire)
        with self.assertRaises(RecordingConflict) as raised:
            self.service.record(dataclasses.replace(wire, locator="src/a.py"))
        self.assertEqual(
            raised.exception.cause_kind, m.RejectionCauseKind.CONTEXT_BINDING_CONFLICT
        )
        self.service.record(
            dataclasses.replace(wire, request_id="corrected", locator="src/a.py")
        )

    def test_status_failure_preserves_committed_receipt_and_owner(self):
        wire = self._scope_create(locator="src/a.py")
        with mock.patch(
            "span.service.lifecycle.compose_surface_status",
            side_effect=OSError("inventory unavailable"),
        ):
            result = self.service.record(wire)
        self.assertIsInstance(result.status, m.SurfaceStatusUnavailable)
        self.assertEqual(result.status.surface.locator, "src/a.py")
        self.assertEqual(
            _receipt(self.store, self.service.record(wire)),
            _receipt(self.store, result),
        )
        with mock.patch(
            "span.service.lifecycle.compose_surface_status",
            side_effect=ValueError("programming defect"),
        ):
            with self.assertRaisesRegex(ValueError, "programming defect"):
                self.service.record(wire)

    def test_owner_read_failure_reports_unavailable_without_rejecting_acceptance(self):
        result = self.service.record(self._scope_create(locator="src/a.py"))
        with mock.patch.object(
            self.store, "get_understanding", side_effect=OSError("store unavailable")
        ):
            qualified = self.service.qualify_understanding(_receipt(self.store, result))
        self.assertEqual(_receipt(self.store, qualified), _receipt(self.store, result))
        self.assertIsInstance(qualified.qualification, m.SupportUnavailable)
        self.assertNotIn("store unavailable", qualified.qualification.reason)
        self.assertNotIn("OSError", qualified.qualification.reason)
        self.assertIsInstance(qualified.status, m.SurfaceStatusUnavailable)
        self.assertNotIn("store unavailable", qualified.status.reason)
        self.assertIsNone(qualified.status.surface)

    def test_complete_question_context_scope_refs_are_preserved(self):
        scope = m.EvidenceScope(evidence_refs=(_evidence(),))
        context = self.service.start_context(
            m.StartContextRequest(
                repository_id="repo-1",
                request_id=m.RequestId("ref-context"),
                scope=scope,
                question="Question with exact refs?",
            )
        )
        result = self.service.record(
            w.RecordRequestWire(
                request_id="ref-create",
                context=_context_ref(context.context_id.value),
                kind=m.RecordKind.UNDERSTANDING,
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion="A does X",
                locator="src/a.py",
            )
        )
        self._assert_scopes(result, scope, "src/a.py")

    def test_declared_owner_checks_semantic_members_not_support(self):
        for kind in (m.SurfaceKind.SERVICE, m.SurfaceKind.DOMAIN):
            key = m.SurfaceKey("repo-1", kind, kind.value.lower())
            self.store.put_surface(
                m.Surface(key=key, boundary=m.SurfaceBoundary(paths=("docs",)))
            )
            wire = self._scope_create(
                f"owner-{kind.value}",
                scope_paths=("docs/plan.md",),
                surface=w.SurfaceWire(kind=kind, locator=key.locator),
                support=(w.SourceSupportWire(locator="src/a.py"),),
            )
            result = self.service.record(wire)
            self._assert_scopes(
                result, m.EvidenceScope(paths=("docs/plan.md",)), key.locator
            )
            with self.assertRaises(Rejection) as raised:
                self.service.record(
                    dataclasses.replace(
                        wire,
                        request_id=f"outside-{kind.value}",
                        scope_paths=("docs/plan.md", "other.py"),
                    )
                )
            self.assertEqual(
                raised.exception.cause_kind, m.RejectionCauseKind.SURFACE_MISMATCH
            )
            self.assertIn("other.py", str(raised.exception))

    def test_verification_replay_does_not_admit_evidence_and_combines_observations(
        self,
    ):
        run = w.VerificationRunWire(
            repository_id="repo-1",
            scope_description="fixture",
            scope_paths=("src",),
            command="test",
            scenario=None,
            outcome=m.VerificationOutcome.PASS,
            observed_at=NOW,
            observer="test",
            observations=("obs-1",),
            evidence=(w.SourceSupportWire(locator="src/a.py"),),
        )
        wire = w.RecordRequestWire(
            request_id="verify-replay",
            context=_context_ref("ctx-1"),
            kind=m.RecordKind.VERIFICATION,
            run=run,
        )
        result = self.service.record(wire)
        self.assertIsInstance(result, m.VerificationRecorded)
        with (
            mock.patch.object(
                self.service,
                "_resolve_record_request",
                side_effect=AssertionError("resolve"),
            ),
            mock.patch.object(
                self.service, "_admit_source", side_effect=AssertionError("admit")
            ),
        ):
            self.assertEqual(
                _receipt(self.store, self.service.record(wire)),
                _receipt(self.store, result),
            )

    def test_postcommit_store_failures_preserve_acceptance_through_mcp(self):
        from span.ports.structural import StructuralSource
        from span.shell.context import compose_context
        from span.shell.mcp.adapter import McpAdapter

        context = compose_context(
            repository_id="repo-1",
            root="/repo/one",
            structural=mock.Mock(spec=StructuralSource),
            evidence=_CurrentEvidence(),
            store=self.store,
        )
        adapter = McpAdapter(contexts={"repo-1": context})
        for index, error in enumerate(
            (
                LifecycleStoreError("store read unavailable"),
                sqlite3.OperationalError("disk I/O error"),
            )
        ):
            with self.subTest(error=type(error).__name__):
                payload = {
                    "repository_id": "repo-1",
                    "request_id": f"postcommit-store-{index}",
                    "kind": "understanding",
                    "question": f"Operational failure {index}?",
                    "conclusion": "A does X",
                    "locator": "src/a.py",
                }
                with mock.patch.object(
                    self.store, "list_understandings", side_effect=error
                ):
                    result = adapter.dispatch("record", payload)
                self.assertFalse(result.is_error)
                response = result.structured_content
                self.assertEqual(response["$type"], "UnderstandingRecorded")
                self.assertEqual(
                    response["status"]["$type"], "SurfaceStatusUnavailable"
                )
                self.assertEqual(response["status"]["surface"]["locator"], "src/a.py")
                self.assertEqual(
                    response["qualification"]["$type"], "UnderstandingQualification"
                )
                retry = adapter.dispatch("record", payload).structured_content
                self.assertEqual(
                    retry["receipt_selector"], response["receipt_selector"]
                )
                self.assertEqual(retry["status"]["$type"], "SurfaceStatus")

    def test_verification_store_failure_preserves_accepted_receipt(self):
        wire = w.RecordRequestWire(
            request_id="verify-store-failure",
            context=_context_ref("ctx-1"),
            kind=m.RecordKind.VERIFICATION,
            run=w.VerificationRunWire(
                repository_id="repo-1",
                scope_description="source test",
                scope_paths=("src",),
                command="test",
                scenario=None,
                outcome=m.VerificationOutcome.PASS,
                observed_at=NOW,
                observer="test",
                observations=("obs-1",),
            ),
        )
        result = self.service.record(wire)
        for error in (
            LifecycleStoreError("read unavailable"),
            sqlite3.OperationalError("disk I/O error"),
        ):
            with (
                self.subTest(error=type(error).__name__),
                mock.patch.object(
                    self.support,
                    "evaluate_verification",
                    side_effect=error,
                ),
            ):
                replay = self.service.record(wire)
                self.assertEqual(
                    _receipt(self.store, replay), _receipt(self.store, result)
                )
                self.assertIsInstance(replay.qualification, m.SupportUnavailable)
                self.assertNotIn(str(error), replay.qualification.reason)
        with mock.patch.object(
            self.support,
            "evaluate_verification",
            side_effect=ValueError("contract defect"),
        ):
            with self.assertRaisesRegex(ValueError, "contract defect"):
                self.service.record(wire)

    def test_postcommit_owner_read_failure_preserves_receipt_without_owner(self):
        result = self.service.record(self._scope_create(locator="src/a.py"))
        for error in (
            LifecycleStoreError("read unavailable"),
            sqlite3.OperationalError("disk I/O error"),
        ):
            with (
                self.subTest(error=type(error).__name__),
                mock.patch.object(
                    self.store,
                    "get_understanding",
                    side_effect=error,
                ),
            ):
                qualified = self.service.qualify_understanding(
                    _receipt(self.store, result)
                )
                self.assertEqual(
                    _receipt(self.store, qualified), _receipt(self.store, result)
                )
                self.assertIsInstance(qualified.qualification, m.SupportUnavailable)
                self.assertIsInstance(qualified.status, m.SurfaceStatusUnavailable)
                self.assertIsNone(qualified.status.surface)

    def test_postcommit_programming_failures_are_not_operational_unavailability(self):
        result = self.service.record(self._scope_create(locator="src/a.py"))
        for error in (
            ValueError("bad contract"),
            sqlite3.ProgrammingError("bad query"),
            sqlite3.IntegrityError("bad invariant"),
        ):
            with (
                self.subTest(error=type(error).__name__),
                mock.patch.object(
                    self.store,
                    "list_understandings",
                    side_effect=error,
                ),
            ):
                with self.assertRaises(type(error)):
                    self.service.qualify_understanding(_receipt(self.store, result))

    def test_refs_only_semantic_scope_does_not_examine_unrelated_files(self):
        from span.service.surface_status import compose_surface_status
        from span.service.answer import AnswerService

        context = self.service.start_context(
            m.StartContextRequest(
                repository_id="repo-1",
                request_id=m.RequestId("coverage-ref-context"),
                question="What is established about A?",
                scope=m.EvidenceScope(evidence_refs=(_evidence(),)),
            )
        )
        self.service.record(
            w.RecordRequestWire(
                request_id="coverage-ref-create",
                context=_context_ref(context.context_id.value),
                kind=m.RecordKind.UNDERSTANDING,
                surface=w.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/a.py"),
                conclusion="A does X",
                locator="src/a.py",
            )
        )
        service_key = m.SurfaceKey("repo-1", m.SurfaceKind.SERVICE, "coverage-service")
        self.store.put_surface(
            m.Surface(key=service_key, boundary=m.SurfaceBoundary(paths=("src",)))
        )
        answer = AnswerService(
            store=self.store, support=self.support, evidence=self.evidence_service
        )
        with mock.patch.object(
            self.evidence_service,
            "inventory_paths",
            return_value=("src/a.py", "src/unexamined.py"),
        ):
            status = compose_surface_status(
                service_key,
                store=self.store,
                support=self.support,
                evidence=self.evidence_service,
            )
            self.assertEqual(status.unexamined, 1)
            answer_result = answer.ask(
                m.AskRequest(
                    repository_id="repo-1",
                    surface=m.SurfaceReference(
                        kind=m.SurfaceKind.FILE, locator="src/a.py"
                    ),
                )
            )
            self.assertIsInstance(answer_result, m.Answer)
            self.assertEqual(answer_result.status.unexamined, 0)
        unrelated = compose_surface_status(
            m.SurfaceKey("repo-1", m.SurfaceKind.FILE, "src/unexamined.py"),
            store=self.store,
            support=self.support,
            evidence=self.evidence_service,
        )
        self.assertEqual(unrelated.unexamined, 1)
        covered = compose_surface_status(
            m.SurfaceKey("repo-1", m.SurfaceKind.FILE, "src/a.py"),
            store=self.store,
            support=self.support,
            evidence=self.evidence_service,
        )
        self.assertEqual(covered.unexamined, 0)

    def test_repository_wide_semantic_scope_rejects_bounded_owner_before_admission(
        self,
    ):
        context = self.service.start_context(
            m.StartContextRequest(
                repository_id="repo-1",
                request_id=m.RequestId("whole-question"),
                scope=m.EvidenceScope(),
                question="How does the repository operate?",
            )
        )
        for index, (kind, owner) in enumerate(
            (
                (m.SurfaceKind.FILE, "src/a.py"),
                (m.SurfaceKind.FILE, "docs/unrelated.md"),
                (m.SurfaceKind.SYMBOL, "src/a.py:example"),
            )
        ):
            with (
                self.subTest(owner=owner),
                mock.patch.object(self.service, "_admit_source") as admit,
            ):
                with self.assertRaises(Rejection) as raised:
                    self.service.record(
                        w.RecordRequestWire(
                            request_id=f"whole-file-{index}",
                            context=_context_ref(context.context_id.value),
                            kind=m.RecordKind.UNDERSTANDING,
                            surface=w.SurfaceWire(kind=kind, locator=owner),
                            conclusion="The repository operates as described.",
                            locator="src/a.py",
                        )
                    )
                self.assertEqual(
                    raised.exception.cause_kind, m.RejectionCauseKind.SURFACE_MISMATCH
                )
                self.assertIn("repository-wide", str(raised.exception))
                self.assertIn(owner, str(raised.exception))
                admit.assert_not_called()
        self.assertEqual(self.store.list_understandings("repo-1"), ())

    def test_explicit_path_owner_rejects_every_outside_semantic_member(self):
        cases = (
            (m.SurfaceKind.FILE, "src/a.py", ("src/a.py", "src/b.py")),
            (m.SurfaceKind.SYMBOL, "src/a.py::f", ("src/b.py",)),
            (m.SurfaceKind.SYMBOL, "src/a.py::f", ("src/a.py::g",)),
            (m.SurfaceKind.SYMBOL, "src/a.py::f", ("src/a.py::f", "src/b.py::f")),
        )
        for index, (kind, owner, paths) in enumerate(cases):
            with (
                self.subTest(kind=kind, owner=owner, paths=paths),
                mock.patch.object(
                    self.service, "_admit_source", wraps=self.service._admit_source
                ) as admit,
            ):
                with self.assertRaises(Rejection) as raised:
                    self.service.record(
                        self._scope_create(
                            f"extra-member-{index}",
                            surface=w.SurfaceWire(kind=kind, locator=owner),
                            scope_paths=paths,
                            support=(w.SourceSupportWire(locator="src/a.py"),),
                        )
                    )
                self.assertEqual(
                    raised.exception.cause_kind, m.RejectionCauseKind.SURFACE_MISMATCH
                )
                self.assertIn(owner, str(raised.exception))
                self.assertIn(paths[-1], str(raised.exception))
                admit.assert_not_called()
        self.assertEqual(self.store.list_understandings("repo-1"), ())

    def test_explicit_symbol_owner_accepts_exact_scope_with_separate_file_support(self):
        symbol = "src/a.py::f"
        result = self.service.record(
            self._scope_create(
                "exact-symbol",
                surface=w.SurfaceWire(kind=m.SurfaceKind.SYMBOL, locator=symbol),
                scope_paths=(symbol,),
                support=(w.SourceSupportWire(locator="src/a.py"),),
            )
        )
        self._assert_scopes(result, m.EvidenceScope(paths=(symbol,)), symbol)
        self.assertEqual(result.status.surface.kind, m.SurfaceKind.SYMBOL)


if __name__ == "__main__":
    unittest.main()
