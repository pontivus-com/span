"""Canonical reference-only record-wire projection tests."""

from __future__ import annotations

import datetime
import unittest

from span.core import model as m
from span.core.schema import from_wire, schema_for_request
from span.core.schema import record_wire as w

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)


def _evidence(reference: str) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(reference),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator="src/a.py",
    )


def _authority(reference: str) -> m.AuthorityBinding:
    return m.AuthorityBinding(
        evidence_ref=_evidence(reference),
        authority_kind=m.AuthorityKind.OTHER,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _resolver() -> w.RecordWireResolver:
    return w.RecordWireResolver(
        reference=_evidence,
        authority=_authority,
    )


def _conclusion(conclusion_id: str = "c-1") -> w.ConclusionWire:
    return w.ConclusionWire(
        conclusion_id=conclusion_id,
        statement="A does X",
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        scope_paths=("src/a.py",),
        scope_evidence_refs=("ev-1",),
        support=(w.SourceSupportWire(observation_id="obs-1"),),
        basis_derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        basis_summary="read source",
        basis_input_refs=("ev-1",),
    )


def _identity() -> w.IdentityWire:
    return w.IdentityWire(
        repository_id="repo-1",
        context_id="ctx-1",
        submission_id="sub-1",
    )


class RecordWireSchemaTest(unittest.TestCase):
    def test_component_schemas_are_object_roots(self):
        for root in (
            w.RecordCreateWire,
            w.RecordUpdateWire,
            w.RecordVerificationWire,
            w.RecordAddWire,
            w.RecordConfirmWire,
            w.RecordCorrectWire,
            w.RecordReplaceWire,
            w.RecordWithdrawWire,
            w.RecordChallengeWire,
        ):
            schema = schema_for_request(root)
            self.assertEqual(schema["type"], "object")
            self.assertIn("identity", schema["properties"])
            self.assertIn("$defs", schema)

    def test_create_wire_round_trips_canonically(self):
        value = w.RecordCreateWire(
            identity=_identity(),
            target=w.ExplicitTargetWire(
                question="What does A do?",
                scope_paths=("src/a.py",),
                scope_evidence_refs=(),
            ),
            conclusions=(_conclusion(),),
        )
        self.assertEqual(
            m.from_canonical(w.RecordCreateWire, m.to_canonical(value)),
            value,
        )


class RecordChallengeWireTest(unittest.TestCase):
    def test_challenge_maps_to_domain_command(self):
        wire = w.RecordChallengeWire(
            identity=_identity(),
            understanding_id="u-1",
            target_version=2,
            target_conclusions=(
                w.ChallengeConclusionRefWire(
                    understanding_id="u-1",
                    conclusion_id="c-1",
                    revision=2,
                ),
            ),
            reason="the conclusion is disputed",
            evidence_refs=("ev-1",),
            provenance="test",
        )
        command = w.challenge_command(wire, _resolver())
        self.assertEqual(command.understanding_id.value, "u-1")
        self.assertEqual(command.target_version.value, 2)
        self.assertEqual(command.target_conclusions[0].revision.value, 2)
        self.assertEqual(command.evidence[0].evidence_id.value, "ev-1")


class RecordActionWireTest(unittest.TestCase):
    def test_add_action_maps_to_one_domain_action(self):
        wire = w.RecordAddWire(
            identity=_identity(),
            understanding_id="u-1",
            expected_version=1,
            conclusion=_conclusion("c-2"),
        )
        command = w.add_command(wire, _resolver())
        self.assertEqual(len(command.add), 1)
        self.assertEqual(command.add[0].conclusion_id.value, "c-2")
        self.assertEqual(command.confirm, ())

    def test_confirm_action_maps_to_one_domain_action(self):
        wire = w.RecordConfirmWire(
            identity=_identity(),
            understanding_id="u-1",
            expected_version=2,
            conclusion=_conclusion("c-1"),
        )
        command = w.confirm_command(wire, _resolver())
        self.assertEqual(len(command.confirm), 1)
        self.assertEqual(command.confirm[0].conclusion_id.value, "c-1")

    def test_correct_action_maps_to_one_domain_action(self):
        wire = w.RecordCorrectWire(
            identity=_identity(),
            understanding_id="u-1",
            expected_version=3,
            conclusion=_conclusion("c-1"),
        )
        command = w.correct_command(wire, _resolver())
        self.assertEqual(len(command.correct), 1)

    def test_replace_action_maps_to_one_domain_action(self):
        wire = w.RecordReplaceWire(
            identity=_identity(),
            understanding_id="u-1",
            expected_version=4,
            replacement=w.ReplaceWire(
                old_understanding_id="u-1",
                old_conclusion_id="c-2",
                old_revision=1,
                new_conclusion=_conclusion("c-3"),
                replacement_basis_derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                replacement_basis_summary="replacement",
                replacement_basis_input_refs=("ev-1",),
            ),
        )
        command = w.replace_command(wire, _resolver())
        self.assertEqual(len(command.replace), 1)
        self.assertEqual(command.replace[0].new_conclusion_id.value, "c-3")

    def test_withdraw_action_maps_to_one_domain_action(self):
        wire = w.RecordWithdrawWire(
            identity=_identity(),
            understanding_id="u-1",
            expected_version=5,
            withdrawal=w.WithdrawWire(
                conclusion_id="c-3",
                basis_derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                basis_summary="withdrawn",
                basis_input_refs=("ev-1",),
            ),
        )
        command = w.withdraw_command(wire, _resolver())
        self.assertEqual(len(command.withdraw), 1)


class RecordWireMalformedTest(unittest.TestCase):
    def test_missing_required_wire_field_rejects(self):
        with self.assertRaises(ValueError):
            from_wire(w.RecordAddWire, {})

    def test_unknown_wire_field_rejects(self):
        with self.assertRaises(ValueError):
            from_wire(
                w.RecordVerificationWire,
                {
                    "identity": {
                        "repository_id": "repo-1",
                        "context_id": "ctx-1",
                        "submission_id": "sub-1",
                    },
                    "run": {},
                    "unexpected": True,
                },
            )


class RecordWireCodecTest(unittest.TestCase):
    def test_create_maps_to_domain_command(self):
        wire = w.RecordCreateWire(
            identity=_identity(),
            target=w.ContextBoundTargetWire(),
            conclusions=(_conclusion(),),
        )
        command = w.create_command(wire, _resolver())
        self.assertIsInstance(command, m.CreateUnderstandingCommand)
        self.assertEqual(command.identity.repository_id, "repo-1")
        self.assertIsInstance(command.target, m.ContextBoundTarget)
        self.assertEqual(command.conclusions[0].conclusion_id.value, "c-1")
        self.assertEqual(
            command.conclusions[0].basis.derivation,
            m.DerivationKind.EXPLICIT_EVIDENCE,
        )

    def test_update_maps_split_actions(self):
        wire = w.RecordUpdateWire(
            identity=_identity(),
            understanding_id="u-1",
            expected_version=1,
            add=(_conclusion("c-2"),),
            withdraw=(
                w.WithdrawWire(
                    conclusion_id="c-1",
                    basis_derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                    basis_summary="withdrawn",
                    basis_input_refs=("ev-1",),
                ),
            ),
        )
        command = w.update_command(wire, _resolver())
        self.assertIsInstance(command, m.UpdateUnderstandingCommand)
        self.assertEqual(command.expected_version.value, 1)
        self.assertEqual(command.add[0].conclusion_id.value, "c-2")
        self.assertEqual(command.withdraw[0].conclusion_id.value, "c-1")

    def test_verification_maps_to_domain_command(self):
        wire = w.RecordVerificationWire(
            identity=_identity(),
            run=w.VerificationRunWire(
                repository_id="repo-1",
                scope_description="probe",
                scope_paths=("src/a.py",),
                observations=("obs-1",),
                command="python3 -m unittest",
                scenario=None,
                outcome=m.VerificationOutcome.PASS,
                observed_at=NOW,
                observer="test",
            ),
        )
        command = w.verification_command(wire)
        self.assertIsInstance(command, m.RecordVerificationCommand)
        self.assertEqual(command.run.outcome, m.VerificationOutcome.PASS)
        self.assertEqual(command.run.observations[0].value, "obs-1")


if __name__ == "__main__":
    unittest.main()
