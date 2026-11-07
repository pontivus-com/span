"""Lifecycle service boundary tests: contexts, wire resolution, recording."""

from __future__ import annotations

import dataclasses
import datetime
import itertools
import pathlib
import tempfile
import threading
import unittest

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


def _receipt(result: m.RecordResult) -> m.RecordReceipt:
    assert isinstance(result, m.UnderstandingRecorded)
    return result.receipt


def _create_wire(
    submission: str = "sub-create",
    *,
    conclusion: _ConclusionSpec | None = None,
) -> w.RecordRequestWire:
    spec = conclusion or _conclusion()
    return w.RecordRequestWire(
        repository_id="repo-1",
        request_id=submission,
        context_id="ctx-1",
        kind=m.RecordKind.UNDERSTANDING,
        surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
        conclusion=spec.statement,
        locator=spec.scope_paths[0] if spec.scope_paths else "src/a.py",
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
        result = self.service.record(
            w.RecordRequestWire(
                repository_id="repo-1",
                request_id=submission,
                context_id=context_id,
                kind=m.RecordKind.UNDERSTANDING,
                understanding_id=understanding_id,
                expected_version=expected,
                actions=actions,
            )
        )
        self.assertIsInstance(result, m.UnderstandingRecorded)
        return result

    def _record_add(self, expected: int, submission: str) -> m.RecordReceipt:
        return self._update(
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
        ).receipt

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
        return self._update(
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
        ).receipt

    def _record_correct(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self._update(
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
        ).receipt

    def _record_replace(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self._update(
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
        ).receipt

    def _record_withdraw(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self._update(
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
        ).receipt

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
        receipt = _receipt(self.service.record(wire))
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
        replay = _receipt(self.service.record(wire))
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
            self.service.record(
                _create_wire(submission="sub-authority", conclusion=conclusion)
            )
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(
            self.authority.requests,
            [
                ("repo-1", "auth-1"),
                ("repo-1", "auth-1"),
                ("repo-1", "auth-1"),
            ],
        )
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
            service.record(
                _create_wire(
                    submission="sub-store-auth",
                    conclusion=_conclusion(
                        support=(w.AuthoritySupportWire(authority_ref="auth-ev-1"),)
                    ),
                )
            )
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
            repository_id="repo-1",
            request_id="sub-scope",
            context_id=context.context_id.value,
            kind=m.RecordKind.UNDERSTANDING,
            surface=w.SurfaceWire(kind="FILE", locator="docs/other.md"),
            question="What is outside?",
            scope_paths=("docs/other.md",),
            conclusion="Outside scope",
            locator="docs/other.md",
            support=(w.AdmittedSourceSupportWire(observation_id="obs-1"),),
        )
        with self.assertRaises(RecordingValidationError):
            service.record(wire)

    def test_replay_survives_later_source_change(self) -> None:
        wire = _create_wire()
        receipt = _receipt(self.service.record(wire))
        # The receipt is immutable acceptance, not cached currentness.
        self.store._connection.execute(
            "UPDATE source_observations SET content_digest='sha256:changed'"
        )
        self.store._connection.commit()
        replay = _receipt(self.service.record(wire))
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
            self.service.record(
                _create_wire(submission="sub-disc", conclusion=conclusion)
            )
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
                repository_id="repo-1",
                request_id="sub-ch",
                context_id="ctx-1",
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
        receipt = result.receipt
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 2)
        updated = self.store.get_challenge("ch-1")
        self.assertEqual(updated.challenge_revision.value, 2)
        self.assertEqual(updated.state, m.ChallengeState.UNRESOLVED)

    def test_verification_requires_admitted_observation(self) -> None:
        def wire(submission: str, observation: str) -> w.RecordRequestWire:
            return w.RecordRequestWire(
                repository_id="repo-1",
                request_id=submission,
                context_id="ctx-1",
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
        run = self.store.get_verification_run(
            result.receipt.accepted_verification_run_ids[0].value
        )
        self.assertEqual(run.outcome, m.VerificationOutcome.PASS)

    def test_verification_accepts_evidence_only(self) -> None:
        wire = w.RecordRequestWire(
            repository_id="repo-1",
            request_id="sub-v-evidence",
            context_id="ctx-1",
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
        run = self.store.get_verification_run(
            result.receipt.accepted_verification_run_ids[0].value
        )
        self.assertTrue(run.observations)

    def test_record_verification_accepts_evidence_only(self) -> None:
        request = w.RecordRequestWire(
            repository_id="repo-1",
            request_id="sub-v-wire",
            context_id="ctx-1",
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
        receipt = _receipt(self.service.record(_create_wire()))
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
        receipt = _receipt(self.service.record(_create_wire()))
        self.clock[0] = NOW + RETENTION.context_lifetime + datetime.timedelta(minutes=1)
        self.store.reap_expired()
        self.assertIsNone(self.store.find_context_by_id("ctx-1"))
        self.assertEqual(self.store.get_receipt(receipt.identity), receipt)
        replay = _receipt(self.service.record(_create_wire()))
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
            surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
            question="What does A do?",
            scope_paths=("src/a.py",),
            conclusion="A does X",
            locator="src/a.py",
        )

    def test_create_without_context_issues_one_internally(self) -> None:
        wire = self._context_free_create()
        receipt = _receipt(self._service("ctx-issued").record(wire))
        self.assertEqual(receipt.identity.context_id.value, "ctx-issued")
        self.assertEqual(receipt.accepted_understanding_ids[0].value, "u:sub-nc")
        context = self.store.find_context_by_id("ctx-issued")
        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.origin, m.ContextOrigin.EVIDENCE_ONLY)
        self.assertIn("src/a.py", context.scope.paths)
        self.assertEqual(_receipt(self._service("ctx-unused").record(wire)), receipt)

    def test_create_with_support_only_derives_scope_from_context(self) -> None:
        result = self.service.record(
            w.RecordRequestWire(
                repository_id="repo-1",
                request_id="sub-support-only",
                context_id="ctx-1",
                kind=m.RecordKind.UNDERSTANDING,
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
                conclusion="A is supported by the source.",
                support=(w.SourceSupportWire(locator="src/a.py"),),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        understanding_id = result.receipt.accepted_understanding_ids[0].value
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
                repository_id="repo-1",
                request_id="sub-support-only-no-surface",
                context_id="ctx-1",
                kind=m.RecordKind.UNDERSTANDING,
                conclusion="A is supported by the source.",
                support=(w.SourceSupportWire(locator="src/a.py"),),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        understanding_id = result.receipt.accepted_understanding_ids[0].value
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
        with self.assertRaisesRegex(ValueError, "requires a question"):
            w.RecordRequestWire(
                repository_id="repo-1",
                request_id="sub-bound",
                kind=m.RecordKind.UNDERSTANDING,
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
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
        self.assertEqual(result.receipt.accepted_understanding_versions[0].value, 2)
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
            locator = conclusion.scope_paths[0] if conclusion.scope_paths else None
            if context_id is not None:
                scope_paths = ()
            flat = {
                "conclusion": conclusion.statement,
                "assertion_nature": conclusion.assertion_nature,
                "locator": locator if observation is None else None,
                "observation_id": observation,
                "support": support,
            }
        return w.RecordRequestWire(
            repository_id="repo-1",
            request_id=submission,
            context_id=context_id,
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
            **flat,
        )

    def test_record_create_through_the_one_request(self) -> None:
        result = self.service.record(
            self._record_request(
                "sub-one-create",
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
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
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
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
                    surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
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
        with self.assertRaisesRegex(ValueError, "requires a question"):
            self._record_request(
                "sub-unbound-create",
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
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
                    surface=w.SurfaceWire(kind="FILE", locator="src/b.py"),
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
                    kind="SERVICE",
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
                    kind="SERVICE",
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
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
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
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.receipt.accepted_understanding_ids[0].value
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
        self.assertEqual(updated.receipt.accepted_understanding_versions[0].value, 2)

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
        self.assertEqual(result.qualification.run.outcome, m.VerificationOutcome.PASS)

    def test_record_actions_apply_atomically(self) -> None:
        created = self.service.record(
            self._record_request(
                "sub-atomic-create",
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.receipt.accepted_understanding_ids[0].value
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
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.receipt.accepted_understanding_ids[0].value
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
        self.assertEqual(replaced.receipt.accepted_understanding_versions[0].value, 2)
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
        self.assertEqual(withdrawn.receipt.accepted_understanding_versions[0].value, 3)
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
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(created, m.UnderstandingRecorded)
        understanding_id = created.receipt.accepted_understanding_ids[0].value
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
        self.assertEqual(settled.receipt.accepted_understanding_versions[0].value, 2)
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
                surface=w.SurfaceWire(kind="FILE", locator="src/a.py"),
                conclusion=_conclusion(),
            )
        )
        assert isinstance(base, m.UnderstandingRecorded)
        base_id = base.receipt.accepted_understanding_ids[0].value
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
                surface=w.SurfaceWire(kind="SYMBOL", locator="src/a.py::A"),
                question="What supports A?",
                conclusion=_conclusion(
                    "A is supported by every form.",
                    support=support,
                ),
            )
        )
        assert isinstance(result, m.UnderstandingRecorded)
        understanding_id = result.receipt.accepted_understanding_ids[0].value
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
        kind: str,
        locator: str,
        *,
        boundary: tuple[str, ...] | None = ("src",),
        parent: tuple[str, str] | None = None,
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
                "SERVICE",
                "billing",
                parent=("DOMAIN", "missing"),
            )

    def test_surface_create_rejects_self_parenting(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be its own parent"):
            self._declare_surface(
                "surface-self-parent",
                "SERVICE",
                "billing",
                parent=("SERVICE", "billing"),
            )

    def test_surface_update_rejects_a_parent_cycle(self) -> None:
        self.assertIsInstance(
            self._declare_surface("surface-domain", "DOMAIN", "platform"),
            m.SurfaceDeclared,
        )
        self.assertIsInstance(
            self._declare_surface(
                "surface-service",
                "SERVICE",
                "billing",
                parent=("DOMAIN", "platform"),
            ),
            m.SurfaceDeclared,
        )
        with self.assertRaisesRegex(RecordingValidationError, "cycle"):
            self._declare_surface(
                "surface-cycle",
                "DOMAIN",
                "platform",
                parent=("SERVICE", "billing"),
                action=m.SurfaceAction.UPDATE,
                expected=1,
            )

    def test_surface_update_stale_boundary_returns_rejected(self) -> None:
        self.assertIsInstance(
            self._declare_surface("surface-cas-create", "SERVICE", "billing"),
            m.SurfaceDeclared,
        )
        with self.assertRaises(Rejection) as raised:
            self._declare_surface(
                "surface-cas-update",
                "SERVICE",
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
            self._declare_surface("surface-kind-create", "SERVICE", "billing"),
            m.SurfaceDeclared,
        )
        with self.assertRaises(Rejection) as raised:
            self._declare_surface("surface-kind-conflict", "DOMAIN", "billing")
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
                "SERVICE",
                "billing",
                parent=("FILE", "src/a.py"),
            )

    def test_path_surface_boundary_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "rejects a boundary"):
            self._declare_surface("surface-file-boundary", "FILE", "src/a.py")

    def test_declared_surface_requires_a_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a boundary"):
            self._declare_surface(
                "surface-no-boundary",
                "SERVICE",
                "billing",
                boundary=None,
            )

    def test_surface_create_with_a_changed_boundary_is_rejected(self) -> None:
        self.assertIsInstance(
            self._declare_surface("surface-dup-create", "SERVICE", "billing"),
            m.SurfaceDeclared,
        )
        with self.assertRaises(Rejection) as raised:
            self._declare_surface(
                "surface-dup-boundary",
                "SERVICE",
                "billing",
                boundary=("src", "tests"),
            )
        self.assertIs(
            raised.exception.cause_kind,
            m.RejectionCauseKind.SURFACE_CONFLICT,
        )
        self.assertEqual(raised.exception.current_boundary_version, 1)


if __name__ == "__main__":
    unittest.main()
