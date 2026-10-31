"""Canonical lifecycle contracts: model, identity, transitions, receipts.

These tests exercise the pure core only. They do not claim a live host
delivery, database transition, or product acceptance.
"""

from __future__ import annotations

import datetime
import unittest

from span.core import model as m
from span.core.identity import payload_digest, record_content_digest, recording_key
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    apply_challenge_dispositions,
    apply_update,
    build_receipt,
    create_challenge,
    create_understanding,
    receipt_decision,
)

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)
LATER = datetime.datetime(2026, 10, 31, 13, 0, tzinfo=datetime.timezone.utc)


def _evidence(locator: str = "src/a.py") -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev:{locator}"),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=locator,
        revision_or_fingerprint="sha256:abc",
        section_or_span="L1-L9",
    )


def _basis(summary: str = "read the source") -> m.SemanticBasis:
    return m.SemanticBasis(
        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        summary=summary,
        input_refs=(_evidence(),),
    )


def _support(locator: str = "src/a.py") -> tuple[m.SupportDependency, ...]:
    return (m.SourceSupport(observation_id=m.SourceObservationId(f"obs:{locator}")),)


def _scope(*paths: str) -> m.EvidenceScope:
    return m.EvidenceScope(paths=tuple(paths) or ("src/a.py",))


def _content(statement: str = "A does X", *paths: str) -> dict[str, object]:
    return {
        "statement": statement,
        "assertion_nature": m.AssertionNature.DESCRIPTIVE,
        "scope": _scope(*paths),
        "support": _support(),
        "basis": _basis(),
    }


def _proposed(
    conclusion_id: str = "c-1",
    statement: str = "A does X",
    *paths: str,
) -> m.ProposedConclusion:
    return m.ProposedConclusion(
        conclusion_id=m.ConclusionId(conclusion_id),
        **_content(statement, *paths),
    )


def _confirm(
    conclusion_id: str = "c-1",
    statement: str = "A does X",
    *paths: str,
) -> m.ConfirmConclusion:
    return m.ConfirmConclusion(
        conclusion_id=m.ConclusionId(conclusion_id),
        **_content(statement, *paths),
    )


def _correct(
    conclusion_id: str = "c-3",
    statement: str = "A actually does Z",
    *paths: str,
) -> m.CorrectConclusion:
    return m.CorrectConclusion(
        conclusion_id=m.ConclusionId(conclusion_id),
        **_content(statement, *paths),
    )


def _replace(
    old: m.ConclusionRevisionRef,
    new_conclusion_id: str = "c-5",
    statement: str = "A is replaced",
    *paths: str,
) -> m.ReplaceConclusion:
    return m.ReplaceConclusion(
        old=old,
        new_conclusion_id=m.ConclusionId(new_conclusion_id),
        replacement_basis=_basis("replacement"),
        **_content(statement, *paths),
    )


def _identity(submission: str = "sub-1") -> m.RecordingIdentity:
    return m.RecordingIdentity(
        repository_id="repo-1",
        context_id=m.InvestigationContextId("ctx-1"),
        submission_id=m.SubmissionId(submission),
    )


def _context(
    origin: m.ContextOrigin = m.ContextOrigin.QUESTION,
    *,
    question: str | None = "What does A do?",
    scope: m.EvidenceScope | None = None,
    state: m.ContextState = m.ContextState.LIVE,
) -> m.InvestigationContext:
    return m.InvestigationContext(
        context_id=m.InvestigationContextId("ctx-1"),
        repository_id="repo-1",
        request_id=m.RequestId("req-1"),
        request_digest=m.ContentDigest("sha256:request"),
        origin=origin,
        state=state,
        scope=scope or _scope(),
        created_at=NOW,
        question=question,
    )


def _create_command(
    *,
    target: m.UnderstandingTarget | None = None,
    conclusion_id: str = "c-1",
    statement: str = "A does X",
    paths: tuple[str, ...] = (),
) -> m.CreateUnderstandingCommand:
    return m.CreateUnderstandingCommand(
        identity=_identity(),
        target=target or m.ContextBoundTarget(),
        conclusions=(_proposed(conclusion_id, statement, *paths),),
    )


def _created() -> tuple[
    m.Understanding,
    m.UnderstandingVersion,
    tuple[m.ConclusionRevision, ...],
]:
    transition = create_understanding(
        m.UnderstandingId("u-1"),
        _create_command(),
        _context(),
        NOW,
    )
    return transition.understanding, transition.new_version, transition.new_conclusions


def _update_command(
    *,
    expected: int = 1,
    add: tuple[m.ProposedConclusion, ...] = (),
    confirm: tuple[m.ConfirmConclusion, ...] = (),
    correct: tuple[m.CorrectConclusion, ...] = (),
    replace: tuple[m.ReplaceConclusion, ...] = (),
    withdraw: tuple[m.WithdrawConclusion, ...] = (),
    gaps: tuple[m.GapDraft, ...] | None = None,
    dispositions: tuple[m.ChallengeDisposition, ...] = (),
    submission: str = "sub-2",
) -> m.UpdateUnderstandingCommand:
    return m.UpdateUnderstandingCommand(
        identity=_identity(submission),
        understanding_id=m.UnderstandingId("u-1"),
        expected_version=m.UnderstandingVersionNumber(expected),
        add=add,
        confirm=confirm,
        correct=correct,
        replace=replace,
        withdraw=withdraw,
        gaps=gaps,
        challenge_dispositions=dispositions,
    )


class CanonicalRoundTripTest(unittest.TestCase):
    def test_create_command_round_trips(self):
        command = _create_command()
        self.assertEqual(
            m.from_canonical(m.CreateUnderstandingCommand, m.to_canonical(command)),
            command,
        )

    def test_update_command_round_trips_all_actions(self):
        command = _update_command(
            expected=1,
            add=(_proposed("c-2", "A also does Y"),),
            confirm=(_confirm("c-1"),),
            correct=(_correct("c-3"),),
            replace=(
                _replace(
                    m.ConclusionRevisionRef(
                        understanding_id=m.UnderstandingId("u-1"),
                        conclusion_id=m.ConclusionId("c-4"),
                        revision=m.ConclusionRevisionNumber(1),
                    ),
                    "c-5",
                ),
            ),
            withdraw=(
                m.WithdrawConclusion(
                    conclusion_id=m.ConclusionId("c-6"),
                    basis=_basis("no longer true"),
                ),
            ),
        )
        self.assertEqual(
            m.from_canonical(m.UpdateUnderstandingCommand, m.to_canonical(command)),
            command,
        )

    def test_unknown_tag_rejects(self):
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.CreateUnderstandingCommand, {"$type": "Unknown"})

    def test_missing_branch_field_rejects(self):
        encoded = m.to_canonical(_create_command())
        del encoded["conclusions"]
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.CreateUnderstandingCommand, encoded)


class IdentityDigestTest(unittest.TestCase):
    def test_content_digest_ignores_submission_identity(self):
        first = _create_command()
        second = m.CreateUnderstandingCommand(
            identity=_identity("sub-2"),
            target=first.target,
            conclusions=first.conclusions,
        )
        self.assertEqual(record_content_digest(first), record_content_digest(second))

    def test_content_digest_changes_with_content(self):
        first = _create_command()
        second = _create_command(statement="A does something else")
        self.assertNotEqual(record_content_digest(first), record_content_digest(second))

    def test_payload_digest_is_stable_and_order_independent(self):
        left = payload_digest({"b": 2, "a": 1})
        right = payload_digest({"a": 1, "b": 2})
        self.assertEqual(left, right)

    def test_recording_key_projects_the_identity(self):
        key = recording_key(_identity())
        self.assertEqual(key.repository_id, "repo-1")
        self.assertEqual(key.context_id.value, "ctx-1")
        self.assertEqual(key.submission_id.value, "sub-1")


class ReceiptDecisionTest(unittest.TestCase):
    def test_new_replay_and_conflict(self):
        command = _create_command()
        digest = record_content_digest(command)
        self.assertEqual(
            receipt_decision(None, command.identity, digest).kind,
            m.ReceiptDecisionKind.NEW,
        )
        receipt = build_receipt(
            command.identity,
            digest,
            NOW,
            understanding=(m.UnderstandingId("u-1"), m.UnderstandingVersionNumber(1)),
        )
        self.assertEqual(
            receipt_decision(receipt, command.identity, digest).kind,
            m.ReceiptDecisionKind.REPLAY,
        )
        self.assertEqual(
            receipt_decision(
                receipt, command.identity, m.ContentDigest("sha256:other")
            ).kind,
            m.ReceiptDecisionKind.CONFLICT,
        )

    def test_receipt_identity_mismatch_rejects(self):
        command = _create_command()
        receipt = build_receipt(
            command.identity,
            record_content_digest(command),
            NOW,
            understanding=(m.UnderstandingId("u-1"), m.UnderstandingVersionNumber(1)),
        )
        with self.assertRaises(RecordingConflict):
            receipt_decision(receipt, _identity("sub-other"), receipt.content_digest)


class CreateUnderstandingTest(unittest.TestCase):
    def test_question_context_uses_bound_target(self):
        understanding, version, revisions = _created()
        self.assertEqual(version.version, m.UnderstandingVersionNumber(1))
        self.assertEqual(version.question, "What does A do?")
        self.assertEqual(len(version.conclusions), 1)
        self.assertEqual(revisions[0].revision, m.ConclusionRevisionNumber(1))

    def test_evidence_only_context_requires_explicit_target(self):
        command = _create_command(
            target=m.ExplicitTarget(
                question="What does A do?",
                scope=_scope(),
            )
        )
        transition = create_understanding(
            m.UnderstandingId("u-1"),
            command,
            _context(
                m.ContextOrigin.EVIDENCE_ONLY,
                question=None,
            ),
            NOW,
        )
        self.assertEqual(transition.new_version.question, "What does A do?")

    def test_evidence_only_context_rejects_context_bound_target(self):
        with self.assertRaises(RecordingValidationError):
            create_understanding(
                m.UnderstandingId("u-1"),
                _create_command(),
                _context(m.ContextOrigin.EVIDENCE_ONLY, question=None),
                NOW,
            )

    def test_question_context_rejects_re_authored_target(self):
        with self.assertRaises(RecordingValidationError):
            create_understanding(
                m.UnderstandingId("u-1"),
                _create_command(
                    target=m.ExplicitTarget(
                        question="What does A do?",
                        scope=_scope(),
                    )
                ),
                _context(),
                NOW,
            )

    def test_reconsideration_context_cannot_create(self):
        with self.assertRaises(RecordingValidationError):
            create_understanding(
                m.UnderstandingId("u-1"),
                _create_command(),
                _context(m.ContextOrigin.CHALLENGE),
                NOW,
            )

    def test_conclusion_scope_outside_understanding_rejects(self):
        with self.assertRaises(RecordingValidationError):
            create_understanding(
                m.UnderstandingId("u-1"),
                _create_command(statement="A does X", paths=("src/b.py",)),
                _context(),
                NOW,
            )

    def test_expired_context_rejects(self):
        with self.assertRaises(RecordingValidationError):
            create_understanding(
                m.UnderstandingId("u-1"),
                _create_command(),
                _context(state=m.ContextState.EXPIRED),
                NOW,
            )


class UpdateUnderstandingTest(unittest.TestCase):
    def test_confirm_advances_revision_and_retains_lineage(self):
        understanding, version, revisions = _created()
        transition = apply_update(
            understanding,
            version,
            revisions,
            _update_command(confirm=(_confirm("c-1"),)),
            _context(),
            LATER,
        )
        self.assertEqual(transition.new_version.version.value, 2)
        self.assertEqual(transition.new_version.conclusions[0].revision.value, 2)
        self.assertEqual(transition.new_conclusions[0].revision.value, 2)

    def test_add_preserves_unmentioned_membership(self):
        understanding, version, revisions = _created()
        transition = apply_update(
            understanding,
            version,
            revisions,
            _update_command(add=(_proposed("c-2", "A also does Y"),)),
            _context(),
            LATER,
        )
        lineages = {
            ref.conclusion_id.value for ref in transition.new_version.conclusions
        }
        self.assertEqual(lineages, {"c-1", "c-2"})
        first = next(
            ref
            for ref in transition.new_version.conclusions
            if ref.conclusion_id.value == "c-1"
        )
        self.assertEqual(first, version.conclusions[0])

    def test_withdraw_creates_explicit_withdrawal_revision(self):
        understanding, version, revisions = _created()
        transition = apply_update(
            understanding,
            version,
            revisions,
            _update_command(
                withdraw=(
                    m.WithdrawConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        basis=_basis("withdrawn"),
                    ),
                )
            ),
            _context(),
            LATER,
        )
        new_revision = transition.new_conclusions[0]
        self.assertIsInstance(new_revision.content, m.WithdrawnConclusion)
        self.assertEqual(transition.new_version.conclusions[0].revision.value, 2)

    def test_replace_removes_old_lineage_from_membership(self):
        understanding, version, revisions = _created()
        transition = apply_update(
            understanding,
            version,
            revisions,
            _update_command(replace=(_replace(version.conclusions[0], "c-2"),)),
            _context(),
            LATER,
        )
        self.assertEqual(
            [ref.conclusion_id.value for ref in transition.new_version.conclusions],
            ["c-2"],
        )
        self.assertEqual(transition.new_conclusions[0].conclusion_id.value, "c-2")

    def test_expected_version_mismatch_rejects(self):
        understanding, version, revisions = _created()
        with self.assertRaises(RecordingConflict):
            apply_update(
                understanding,
                version,
                revisions,
                _update_command(
                    expected=2,
                    confirm=(_confirm("c-1"),),
                ),
                _context(),
                LATER,
            )

    def test_empty_update_rejects(self):
        with self.assertRaises(ValueError):
            _update_command()

    def test_duplicate_conclusion_action_rejects(self):
        with self.assertRaises(ValueError):
            _update_command(
                confirm=(_confirm("c-1"),),
                correct=(_correct("c-1", "corrected"),),
            )


def _resulting_version(
    version: m.UnderstandingVersion,
    number: int,
) -> m.UnderstandingVersion:
    return m.UnderstandingVersion(
        understanding_id=version.understanding_id,
        version=m.UnderstandingVersionNumber(number),
        question=version.question,
        scope=version.scope,
        conclusions=version.conclusions,
        created_at=NOW,
        gaps=version.gaps,
        previous_version=version.version,
    )


class ChallengeTransitionTest(unittest.TestCase):
    def test_unresolved_disposition_advances_revision(self):
        understanding, version, revisions = _created()
        challenge = create_challenge(
            challenge_id=m.ChallengeId("ch-1"),
            understanding_id=m.UnderstandingId("u-1"),
            target_version=version.version,
            target_conclusions=version.conclusions,
            reason="why?",
            evidence=(_evidence(),),
            provenance="test",
            now=NOW,
        )
        effects = apply_challenge_dispositions(
            existing_challenges=(challenge,),
            dispositions=(
                m.UnresolvedChallengeDisposition(
                    challenge_id=m.ChallengeId("ch-1"),
                    expected_challenge_revision=m.ChallengeRevision(1),
                    remaining_question="still?",
                    basis="need more",
                ),
            ),
            resulting_understanding_id=m.UnderstandingId("u-1"),
            resulting_understanding=_resulting_version(version, 2),
            known_revisions=revisions,
            now=NOW,
        )
        self.assertEqual(effects[0].new_revision.value, 2)
        self.assertEqual(effects[0].state, m.ChallengeState.UNRESOLVED)
        self.assertEqual(effects[0].disposition.remaining_question, "still?")
        self.assertEqual(effects[0].disposition.basis, "need more")

    def test_resolved_disposition_records_resolution(self):
        understanding, version, revisions = _created()
        challenge = create_challenge(
            challenge_id=m.ChallengeId("ch-1"),
            understanding_id=m.UnderstandingId("u-1"),
            target_version=version.version,
            target_conclusions=version.conclusions,
            reason="why?",
            evidence=(_evidence(),),
            provenance="test",
            now=NOW,
        )
        effects = apply_challenge_dispositions(
            existing_challenges=(challenge,),
            dispositions=(
                m.ResolvedChallengeDisposition(
                    challenge_id=m.ChallengeId("ch-1"),
                    expected_challenge_revision=m.ChallengeRevision(1),
                    reasoning="confirmed by source",
                    resulting_understanding_id=m.UnderstandingId("u-1"),
                    resulting_version=m.UnderstandingVersionNumber(2),
                    conclusions=version.conclusions,
                    evidence=(_evidence(),),
                ),
            ),
            resulting_understanding_id=m.UnderstandingId("u-1"),
            resulting_understanding=_resulting_version(version, 2),
            known_revisions=revisions,
            now=NOW,
        )
        self.assertEqual(effects[0].state, m.ChallengeState.RESOLVED)
        self.assertIsNotNone(effects[0].resolution)

    def test_resolution_rejects_a_nonexistent_revision(self) -> None:
        understanding, version, revisions = _created()
        challenge = create_challenge(
            challenge_id=m.ChallengeId("ch-1"),
            understanding_id=m.UnderstandingId("u-1"),
            target_version=version.version,
            target_conclusions=version.conclusions,
            reason="why?",
            evidence=(_evidence(),),
            provenance="test",
            now=NOW,
        )
        with self.assertRaises(RecordingValidationError):
            apply_challenge_dispositions(
                existing_challenges=(challenge,),
                dispositions=(
                    m.ResolvedChallengeDisposition(
                        challenge_id=m.ChallengeId("ch-1"),
                        expected_challenge_revision=m.ChallengeRevision(1),
                        reasoning="settled",
                        resulting_understanding_id=m.UnderstandingId("u-1"),
                        resulting_version=m.UnderstandingVersionNumber(2),
                        conclusions=(
                            m.ConclusionRevisionRef(
                                understanding_id=m.UnderstandingId("u-1"),
                                conclusion_id=m.ConclusionId("never-existed"),
                                revision=m.ConclusionRevisionNumber(999),
                            ),
                        ),
                    ),
                ),
                resulting_understanding_id=m.UnderstandingId("u-1"),
                resulting_understanding=_resulting_version(version, 2),
                known_revisions=revisions,
                now=NOW,
            )

    def test_wrong_expected_revision_rejects(self):
        understanding, version, revisions = _created()
        challenge = create_challenge(
            challenge_id=m.ChallengeId("ch-1"),
            understanding_id=m.UnderstandingId("u-1"),
            target_version=version.version,
            target_conclusions=version.conclusions,
            reason="why?",
            evidence=(_evidence(),),
            provenance="test",
            now=NOW,
        )
        with self.assertRaises(RecordingConflict):
            apply_challenge_dispositions(
                existing_challenges=(challenge,),
                dispositions=(
                    m.UnresolvedChallengeDisposition(
                        challenge_id=m.ChallengeId("ch-1"),
                        expected_challenge_revision=m.ChallengeRevision(2),
                        remaining_question="still?",
                        basis="need more",
                    ),
                ),
                resulting_understanding_id=m.UnderstandingId("u-1"),
                resulting_understanding=_resulting_version(version, 2),
                known_revisions=revisions,
                now=NOW,
            )

    def test_unaddressed_challenge_is_unchanged(self):
        understanding, version, revisions = _created()
        effects = apply_challenge_dispositions(
            existing_challenges=(),
            dispositions=(),
            resulting_understanding_id=m.UnderstandingId("u-1"),
            resulting_understanding=_resulting_version(version, 2),
            known_revisions=revisions,
            now=NOW,
        )
        self.assertEqual(effects, ())

    def test_resolution_cannot_cite_another_understanding(self):
        understanding, version, revisions = _created()
        challenge = create_challenge(
            challenge_id=m.ChallengeId("ch-1"),
            understanding_id=m.UnderstandingId("u-1"),
            target_version=version.version,
            target_conclusions=version.conclusions,
            reason="why?",
            evidence=(_evidence(),),
            provenance="test",
            now=NOW,
        )
        with self.assertRaises(RecordingValidationError):
            apply_challenge_dispositions(
                existing_challenges=(challenge,),
                dispositions=(
                    m.ResolvedChallengeDisposition(
                        challenge_id=m.ChallengeId("ch-1"),
                        expected_challenge_revision=m.ChallengeRevision(1),
                        reasoning="settled",
                        resulting_understanding_id=m.UnderstandingId("u-1"),
                        resulting_version=m.UnderstandingVersionNumber(2),
                        conclusions=(
                            m.ConclusionRevisionRef(
                                understanding_id=m.UnderstandingId("u-2"),
                                conclusion_id=m.ConclusionId("c-other"),
                                revision=m.ConclusionRevisionNumber(1),
                            ),
                        ),
                    ),
                ),
                resulting_understanding_id=m.UnderstandingId("u-1"),
                resulting_understanding=_resulting_version(version, 2),
                known_revisions=revisions,
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
