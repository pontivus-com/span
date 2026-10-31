"""Lifecycle service boundary tests: contexts, wire resolution, recording."""

from __future__ import annotations

import datetime
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
from span.core.schema import record_wire as w
from span.service.lifecycle import LifecycleService
from span.service.support import SupportService
from span.shell.sqlite_store.lifecycle import LifecycleStore, SourceObservationRecord

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


class _CurrentEvidence:
    def list_inventory_entries(self, repository_id, scope, fingerprint_locators=()):
        return (), {locator: "abc" for locator in fingerprint_locators}


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


def _identity(submission: str = "sub-1") -> w.IdentityWire:
    return w.IdentityWire(
        repository_id="repo-1", context_id="ctx-1", submission_id=submission
    )


def _conclusion(
    conclusion_id: str = "c-1",
    statement: str = "A does X",
    *,
    scope_evidence_refs: tuple[str, ...] = (),
    basis_input_refs: tuple[str, ...] = (),
    support: tuple[w.SupportWire, ...] | None = None,
) -> w.ConclusionWire:
    return w.ConclusionWire(
        conclusion_id=conclusion_id,
        statement=statement,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        scope_paths=("src/a.py",),
        scope_evidence_refs=scope_evidence_refs,
        support=(
            support
            if support is not None
            else (w.SourceSupportWire(observation_id="obs-1"),)
        ),
        basis_derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        basis_summary="read source",
        basis_input_refs=basis_input_refs,
    )


def _create_wire(
    submission: str = "sub-create",
    *,
    conclusion: w.ConclusionWire | None = None,
) -> w.RecordCreateWire:
    return w.RecordCreateWire(
        identity=_identity(submission),
        target=w.ContextBoundTargetWire(),
        conclusions=(conclusion or _conclusion(),),
    )


class LifecycleServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = pathlib.Path(self._tmp.name) / "lifecycle.db"
        self.clock = [NOW]
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
        self.service = LifecycleService(
            store=self.store,
            authority=self.authority,
            support=self.support,
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-1",
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

    def _record_add(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self.service.add(
            w.RecordAddWire(
                identity=_identity(submission),
                understanding_id="u:ctx-1:sub-create",
                expected_version=expected,
                conclusion=_conclusion(conclusion_id, "Another conclusion"),
            )
        )

    def _record_confirm(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self.service.confirm(
            w.RecordConfirmWire(
                identity=_identity(submission),
                understanding_id="u:ctx-1:sub-create",
                expected_version=expected,
                conclusion=_conclusion(conclusion_id, "A does X, reassessed"),
            )
        )

    def _record_correct(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self.service.correct(
            w.RecordCorrectWire(
                identity=_identity(submission),
                understanding_id="u:ctx-1:sub-create",
                expected_version=expected,
                conclusion=_conclusion(conclusion_id, "A does Y"),
            )
        )

    def _record_replace(
        self, old_revision: int, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self.service.replace(
            w.RecordReplaceWire(
                identity=_identity(submission),
                understanding_id="u:ctx-1:sub-create",
                expected_version=expected,
                replacement=w.ReplaceWire(
                    old_understanding_id="u:ctx-1:sub-create",
                    old_conclusion_id="c-1",
                    old_revision=old_revision,
                    new_conclusion=_conclusion("c-3", "A is now described by Z"),
                    replacement_basis_derivation=(m.DerivationKind.EXPLICIT_EVIDENCE),
                    replacement_basis_summary="replacement evidence",
                    replacement_basis_input_refs=(),
                ),
            )
        )

    def _record_withdraw(
        self, conclusion_id: str, expected: int, submission: str
    ) -> m.RecordReceipt:
        return self.service.withdraw(
            w.RecordWithdrawWire(
                identity=_identity(submission),
                understanding_id="u:ctx-1:sub-create",
                expected_version=expected,
                withdrawal=w.WithdrawWire(
                    conclusion_id=conclusion_id,
                    basis_derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                    basis_summary="withdrawn after re-check",
                    basis_input_refs=(),
                ),
            )
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
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-first",
        )
        second = LifecycleService(
            store=second_store,
            authority=self.authority,
            support=self.support,
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
        receipt = self.service.create(wire)
        self.assertEqual(
            receipt.accepted_understanding_ids,
            (
                understanding_identity(
                    m.RecordingIdentity(
                        repository_id="repo-1",
                        context_id=m.InvestigationContextId("ctx-1"),
                        submission_id=m.SubmissionId("sub-create"),
                    )
                ),
            ),
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(receipt.replay_expires_at, NOW + RETENTION.replay_retention)
        replay = self.service.create(wire)
        self.assertEqual(replay.committed_at, receipt.committed_at)
        with self.assertRaises(RecordingConflict):
            self.service.create(
                _create_wire(conclusion=_conclusion(statement="Different"))
            )

    def test_create_requires_admitted_source_support(self) -> None:
        unadmitted = _create_wire(
            submission="sub-unadmitted",
            conclusion=_conclusion(
                support=(w.SourceSupportWire(observation_id="obs-unknown"),)
            ),
        )
        with self.assertRaises(RecordingValidationError):
            self.service.create(unadmitted)
        # Membership cannot be forged for an observation that does not exist.
        with self.assertRaises(Exception):
            self.store.add_context_evidence("ctx-1", "obs-missing")

    def test_evidence_reference_requires_admission(self) -> None:
        unadmitted = _create_wire(
            submission="sub-evidence",
            conclusion=_conclusion(
                scope_evidence_refs=("ev-2",), basis_input_refs=("ev-2",)
            ),
        )
        with self.assertRaises(RecordingValidationError):
            self.service.create(unadmitted)
        receipt = self.service.create(
            _create_wire(
                submission="sub-evidence-2",
                conclusion=_conclusion(
                    scope_evidence_refs=("ev-1",), basis_input_refs=("ev-1",)
                ),
            )
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(self.authority.requests, [])

    def test_authority_reference_uses_declared_resolver(self) -> None:
        conclusion = _conclusion(
            support=(w.AuthoritySupportWire(authority_ref="auth-1"),)
        )
        receipt = self.service.create(
            _create_wire(submission="sub-authority", conclusion=conclusion)
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)
        self.assertEqual(
            self.authority.requests,
            [("repo-1", "auth-1"), ("repo-1", "auth-1")],
        )
        with self.assertRaises(RecordingValidationError):
            self.service.create(
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
            clock=lambda: self.clock[0],
            new_context_id=lambda: "ctx-2",
        )
        receipt = service.create(
            _create_wire(
                submission="sub-store-auth",
                conclusion=_conclusion(
                    support=(w.AuthoritySupportWire(authority_ref="auth-ev-1"),)
                ),
            )
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)

    def test_explicit_target_outside_context_scope_rejects(self) -> None:
        service = LifecycleService(
            store=self.store,
            authority=self.authority,
            support=self.support,
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
        wire = w.RecordCreateWire(
            identity=w.IdentityWire(
                repository_id="repo-1",
                context_id=context.context_id.value,
                submission_id="sub-scope",
            ),
            target=w.ExplicitTargetWire(
                question="What is outside?",
                scope_paths=("docs/other.md",),
                scope_evidence_refs=(),
            ),
            conclusions=(_conclusion("c-1", "Outside scope"),),
        )
        with self.assertRaises(RecordingValidationError):
            service.create(wire)

    def test_replay_survives_later_source_change(self) -> None:
        wire = _create_wire()
        receipt = self.service.create(wire)
        # The receipt is immutable acceptance, not cached currentness.
        self.store._connection.execute(
            "UPDATE source_observations SET content_digest='sha256:changed'"
        )
        self.store._connection.commit()
        replay = self.service.create(wire)
        self.assertEqual(replay.committed_at, receipt.committed_at)
        self.assertEqual(replay, receipt)

    # -- update chain ------------------------------------------------------

    def test_full_update_chain_preserves_history(self) -> None:
        self.service.create(_create_wire())
        self.assertEqual(
            self._record_add("c-2", 1, "sub-add")
            .accepted_understanding_versions[0]
            .value,
            2,
        )
        self.assertEqual(
            self._record_confirm("c-1", 2, "sub-confirm")
            .accepted_understanding_versions[0]
            .value,
            3,
        )
        self.assertEqual(
            self._record_correct("c-1", 3, "sub-correct")
            .accepted_understanding_versions[0]
            .value,
            4,
        )
        self.assertEqual(
            self._record_replace(3, 4, "sub-replace")
            .accepted_understanding_versions[0]
            .value,
            5,
        )
        self.assertEqual(
            self._record_withdraw("c-3", 5, "sub-withdraw")
            .accepted_understanding_versions[0]
            .value,
            6,
        )
        version = self.store.get_version("u:ctx-1:sub-create", 6)
        membership = {
            (ref.conclusion_id.value, ref.revision.value) for ref in version.conclusions
        }
        self.assertEqual(membership, {("c-2", 1), ("c-3", 2)})
        revisions = {
            (item.conclusion_id.value, item.revision.value)
            for item in self.store.get_conclusions("u:ctx-1:sub-create")
        }
        self.assertEqual(
            revisions,
            {
                ("c-1", 1),
                ("c-1", 2),
                ("c-1", 3),
                ("c-2", 1),
                ("c-3", 1),
                ("c-3", 2),
            },
        )

    def test_stale_expected_version_rejects_without_effect(self) -> None:
        self.service.create(_create_wire())
        self._record_add("c-2", 1, "sub-add")
        with self.assertRaises(RecordingConflict):
            self._record_add("c-3", 1, "sub-stale")
        self.assertEqual(
            self.store.get_understanding("u:ctx-1:sub-create").current_version.value,
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
            support=(w.DiscoverySupportWire(observation_id="disc-1"),)
        )
        with self.assertRaises(RecordingValidationError):
            self.service.create(
                _create_wire(submission="sub-disc", conclusion=conclusion)
            )
        self.store.add_context_discovery_evidence("ctx-1", "disc-1")
        receipt = self.service.create(
            _create_wire(submission="sub-disc", conclusion=conclusion)
        )
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 1)

    def test_challenge_disposition_advances_revision(self) -> None:
        self.service.create(_create_wire())
        self.store.create_challenge(
            create_challenge(
                challenge_id=m.ChallengeId("ch-1"),
                understanding_id=m.UnderstandingId("u:ctx-1:sub-create"),
                target_version=m.UnderstandingVersionNumber(1),
                target_conclusions=(
                    m.ConclusionRevisionRef(
                        understanding_id=m.UnderstandingId("u:ctx-1:sub-create"),
                        conclusion_id=m.ConclusionId("c-1"),
                        revision=m.ConclusionRevisionNumber(1),
                    ),
                ),
                reason="the conclusion is disputed",
                evidence=(_evidence(),),
                provenance="test",
                now=NOW,
            )
        )
        receipt = self.service.update(
            w.RecordUpdateWire(
                identity=_identity("sub-ch"),
                understanding_id="u:ctx-1:sub-create",
                expected_version=1,
                confirm=(_conclusion("c-1", "A does X, reassessed"),),
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
        self.assertEqual(receipt.accepted_understanding_versions[0].value, 2)
        updated = self.store.get_challenge("ch-1")
        self.assertEqual(updated.challenge_revision.value, 2)
        self.assertEqual(updated.state, m.ChallengeState.UNRESOLVED)

    def test_verification_requires_admitted_observation(self) -> None:
        def wire(submission: str, observation: str) -> w.RecordVerificationWire:
            return w.RecordVerificationWire(
                identity=_identity(submission),
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

        with self.assertRaises(RecordingValidationError):
            self.service.verification(wire("sub-v-bad", "obs-unknown"))
        receipt = self.service.verification(wire("sub-v", "obs-1"))
        run = self.store.get_verification_run(
            receipt.accepted_verification_run_ids[0].value
        )
        self.assertEqual(run.outcome, m.VerificationOutcome.PASS)

    # -- retention ---------------------------------------------------------

    def test_receipt_readable_after_context_expiry(self) -> None:
        receipt = self.service.create(_create_wire())
        self.clock[0] = NOW + RETENTION.context_lifetime + datetime.timedelta(minutes=1)
        identity = m.RecordingIdentity(
            repository_id="repo-1",
            context_id=m.InvestigationContextId("ctx-1"),
            submission_id=m.SubmissionId("sub-create"),
        )
        self.assertEqual(self.service.receipt(identity), receipt)
        with self.assertRaises(Exception):
            self.service.create(
                _create_wire(
                    submission="sub-after-expiry",
                    conclusion=_conclusion("c-9", "Later"),
                )
            )

    def test_replay_survives_context_reaping(self) -> None:
        receipt = self.service.create(_create_wire())
        self.clock[0] = NOW + RETENTION.context_lifetime + datetime.timedelta(minutes=1)
        self.store.reap_expired()
        self.assertIsNone(self.store.find_context_by_id("ctx-1"))
        self.assertEqual(self.store.get_receipt(receipt.identity), receipt)
        replay = self.service.create(_create_wire())
        self.assertEqual(replay, receipt)

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


if __name__ == "__main__":
    unittest.main()
